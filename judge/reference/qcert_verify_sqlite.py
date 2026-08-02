#!/usr/bin/env python3
"""Streaming, disk-backed verifier for qcert-1 strategy certificates.

The verifier deliberately uses :mod:`quoridor_reference` rather than either
the C++ solver or the clean-room JavaScript verifier.  The first pass validates
and indexes every non-terminal state in SQLite.  The second pass regenerates
the certified strategy obligations and resolves children through the unique
on-disk state index.
"""
from __future__ import annotations

import argparse
from collections import deque
from contextlib import contextmanager
from dataclasses import dataclass
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import time
from typing import Any, Iterable, TextIO
import zlib

import quoridor_reference as rules_engine_module
from quoridor_reference import P1, P2, ReferenceGame, State


MAX_SAFE_INTEGER = (1 << 53) - 1
ERROR_SAMPLE_LIMIT = 20
INSERT_BATCH = 50_000
STATE_FIELDS = ("p1", "p2", "r1", "r2", "turn", "hw", "vw")


def _source_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


VERIFIER_SOURCE = Path(__file__).resolve()
RULES_SOURCE = Path(rules_engine_module.__file__).resolve()
VERIFIER_SHA256 = _source_sha256(VERIFIER_SOURCE)
RULES_SHA256 = _source_sha256(RULES_SOURCE)


class DuplicateMemberError(ValueError):
    """Raised when one JSON object contains the same decoded key twice."""


class OperationalError(RuntimeError):
    """An invocation, filesystem, or SQLite failure rather than a bad cert."""


class HashingRawReader(io.RawIOBase):
    """Hash exactly the bytes consumed from one already-open file descriptor."""

    def __init__(self, raw: io.BufferedReader) -> None:
        super().__init__()
        self.raw = raw
        self.digest = hashlib.sha256()
        self.bytes_read = 0

    def readable(self) -> bool:
        return True

    def readinto(self, buffer: bytearray | memoryview) -> int:
        data = self.raw.read(len(buffer))
        if not data:
            return 0
        buffer[:len(data)] = data
        self.digest.update(data)
        self.bytes_read += len(data)
        return len(data)

    def close(self) -> None:
        if not self.closed:
            try:
                self.raw.close()
            finally:
                super().close()


class StrictGzipReader(io.RawIOBase):
    """One-member gzip decoder that rejects any concatenated/trailing bytes."""

    INPUT_BLOCK = 64 * 1024

    def __init__(self, source: HashingRawReader) -> None:
        super().__init__()
        self.source = source
        self.decoder = zlib.decompressobj(16 + zlib.MAX_WBITS)
        self.compressed = b""
        self.finished = False

    def readable(self) -> bool:
        return True

    def _read_compressed(self) -> bytes:
        return self.source.read(self.INPUT_BLOCK)

    def _finish_member(self) -> None:
        if self.decoder.unused_data:
            raise gzip.BadGzipFile("trailing data or concatenated gzip member")
        extra = self.source.read(1)
        if extra:
            raise gzip.BadGzipFile("trailing data or concatenated gzip member")
        self.finished = True

    def readinto(self, buffer: bytearray | memoryview) -> int:
        if self.finished:
            return 0
        wanted = len(buffer)
        if wanted == 0:
            return 0
        output = bytearray()
        while len(output) < wanted and not self.finished:
            if not self.compressed:
                self.compressed = self._read_compressed()
                if not self.compressed:
                    if not self.decoder.eof:
                        raise gzip.BadGzipFile("truncated gzip stream")
                    self._finish_member()
                    break
            try:
                decoded = self.decoder.decompress(
                    self.compressed, wanted - len(output),
                )
            except zlib.error as error:
                raise gzip.BadGzipFile(f"invalid gzip stream: {error}") from error
            output.extend(decoded)
            self.compressed = self.decoder.unconsumed_tail
            if self.decoder.unused_data:
                raise gzip.BadGzipFile("trailing data or concatenated gzip member")
            if self.decoder.eof:
                self._finish_member()
            elif not decoded and not self.compressed:
                # The decoder consumed its block but needs more input.
                continue
        buffer[:len(output)] = output
        return len(output)

    def close(self) -> None:
        if not self.closed:
            try:
                self.source.close()
            finally:
                super().close()


class JsonArgumentParser(argparse.ArgumentParser):
    """Keep command-line failures machine-readable as well."""

    def error(self, message: str) -> None:
        print(json.dumps({
            "ok": False,
            "errorKind": "usage",
            "errorCount": 1,
            "errors": [message],
        }, separators=(",", ":")))
        raise SystemExit(2)


class ErrorCollector:
    def __init__(self) -> None:
        self.count = 0
        self.samples: list[str] = []

    def fail(self, message: str) -> None:
        self.count += 1
        if len(self.samples) < ERROR_SAMPLE_LIMIT:
            self.samples.append(message)


def _object_without_duplicate_members(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateMemberError(f"duplicate member name: {key}")
        result[key] = value
    return result


def _reject_nonstandard_constant(value: str) -> None:
    raise ValueError(f"non-standard JSON constant: {value}")


def parse_json_record(text: str) -> Any:
    return json.loads(
        text,
        object_pairs_hook=_object_without_duplicate_members,
        parse_constant=_reject_nonstandard_constant,
    )


def is_safe_integer(value: Any) -> bool:
    # bool is an int subclass in Python and must be rejected explicitly.
    return type(value) is int and -MAX_SAFE_INTEGER <= value <= MAX_SAFE_INTEGER


def _state_from_record(record: dict[str, Any]) -> State:
    return State(
        record["p1"], record["p2"], record["r1"], record["r2"],
        record["turn"], record["hw"], record["vw"],
    )


def _state_key(state: State) -> tuple[int, int, int, int, int, int, int]:
    return (
        state.hwalls, state.vwalls, state.p1, state.p2,
        state.r1, state.r2, state.turn,
    )


def _record_key(record: dict[str, Any]) -> tuple[int, int, int, int, int, int, int]:
    return (
        record["hw"], record["vw"], record["p1"], record["p2"],
        record["r1"], record["r2"], record["turn"],
    )


def _key_text(key: Iterable[int]) -> str:
    return ",".join(str(value) for value in key)


def _wall_geometry_errors(hw: int, vw: int, game: ReferenceGame) -> list[str]:
    errors: list[str] = []
    for row in range(game.R):
        for col in range(game.C):
            index = row * game.C + col
            bit = 1 << index
            if hw & bit and vw & bit:
                errors.append(f"crossing walls at {row},{col}")
            if hw & bit and col + 1 < game.C and hw & (bit << 1):
                errors.append(f"overlapping horizontal walls at {row},{col}")
            if vw & bit and row + 1 < game.R and vw & (bit << game.C):
                errors.append(f"overlapping vertical walls at {row},{col}")
    return errors


@dataclass(frozen=True, slots=True)
class WallCandidate:
    move: tuple[str, int, int]
    label: str
    player1_goal_cells: int
    player2_goal_cells: int


@dataclass(slots=True)
class WallConfigurationProfile:
    hw: int
    vw: int
    geometry_errors: tuple[str, ...]
    player1_goal_cells: int
    player2_goal_cells: int
    candidates: tuple[WallCandidate, ...] | None = None
    by_label: dict[str, WallCandidate] | None = None


def _goal_connectivity_masks(
    game: ReferenceGame, hw: int, vw: int,
) -> tuple[int, int]:
    """Cells connected to rows 0 and H-1 in one component traversal."""
    unseen = (1 << (game.W * game.H)) - 1
    top_cells = 0
    bottom_cells = 0
    while unseen:
        seed_bit = unseen & -unseen
        seed = seed_bit.bit_length() - 1
        component = seed_bit
        unseen ^= seed_bit
        queue = deque([seed])
        touches_top = seed < game.W
        touches_bottom = seed >= (game.H - 1) * game.W
        while queue:
            cell = queue.popleft()
            for neighbor in game.neighbors_plain(cell, hw, vw):
                bit = 1 << neighbor
                if unseen & bit:
                    unseen ^= bit
                    component |= bit
                    queue.append(neighbor)
                    row, _ = game.rc(neighbor)
                    touches_top |= row == 0
                    touches_bottom |= row == game.H - 1
        if touches_top:
            top_cells |= component
        if touches_bottom:
            bottom_cells |= component
    return top_cells, bottom_cells


def _build_configuration_profile(
    game: ReferenceGame, hw: int, vw: int,
) -> WallConfigurationProfile:
    top, bottom = _goal_connectivity_masks(game, hw, vw)
    return WallConfigurationProfile(
        hw=hw,
        vw=vw,
        geometry_errors=tuple(_wall_geometry_errors(hw, vw, game)),
        player1_goal_cells=top,
        player2_goal_cells=bottom,
    )


def _populate_wall_candidates(
    game: ReferenceGame, profile: WallConfigurationProfile,
) -> tuple[WallCandidate, ...]:
    if profile.candidates is not None:
        return profile.candidates
    hw, vw = profile.hw, profile.vw
    candidates: list[WallCandidate] = []
    for orient, kind in ((0, "H"), (1, "V")):
        for row in range(game.R):
            for col in range(game.C):
                if not game.wall_geometrically_legal(orient, row, col, hw, vw):
                    continue
                bit = game.wbit(row, col)
                next_hw = hw | bit if orient == 0 else hw
                next_vw = vw | bit if orient == 1 else vw
                top, bottom = _goal_connectivity_masks(game, next_hw, next_vw)
                move = (kind, row, col)
                candidates.append(WallCandidate(
                    move=move,
                    label=_move_label(move),
                    player1_goal_cells=top,
                    player2_goal_cells=bottom,
                ))
    profile.candidates = tuple(candidates)
    profile.by_label = {
        candidate.label: candidate for candidate in profile.candidates
    }
    return profile.candidates


def build_wall_configuration_profile(
    game: ReferenceGame, hw: int, vw: int,
) -> WallConfigurationProfile:
    """Precompute exact pawn-independent path tests for every wall addition."""
    profile = _build_configuration_profile(game, hw, vw)
    _populate_wall_candidates(game, profile)
    return profile


def _candidate_preserves_paths(candidate: WallCandidate, state: State) -> bool:
    return bool(
        candidate.player1_goal_cells & (1 << state.p1)
        and candidate.player2_goal_cells & (1 << state.p2)
    )


def legal_moves_with_profile(
    game: ReferenceGame,
    state: State,
    profile: WallConfigurationProfile | None = None,
) -> list[tuple[str, int, int]]:
    """Exact `ReferenceGame.legal_moves`, with wall-path BFS moved to a profile."""
    moves = [("P", cell, -1) for cell in game.pawn_moves(state)]
    remaining = state.r1 if state.turn == P1 else state.r2
    if remaining <= 0:
        return moves
    if profile is None:
        profile = build_wall_configuration_profile(game, state.hwalls, state.vwalls)
    if (profile.hw, profile.vw) != (state.hwalls, state.vwalls):
        raise ValueError("wall profile does not match state")
    candidates = _populate_wall_candidates(game, profile)
    moves.extend(
        candidate.move
        for candidate in candidates
        if _candidate_preserves_paths(candidate, state)
    )
    return moves


def declared_move_with_profile(
    game: ReferenceGame,
    state: State,
    label: str,
    profile: WallConfigurationProfile | None = None,
) -> tuple[tuple[str, int, int] | None, int]:
    """Validate one existential move; return it and wall bit-tests performed."""
    for cell in game.pawn_moves(state):
        move = ("P", cell, -1)
        if _move_label(move) == label:
            return move, 0
    remaining = state.r1 if state.turn == P1 else state.r2
    if remaining <= 0:
        return None, 0
    if not (label.startswith("H:") or label.startswith("V:")):
        return None, 0
    if profile is None:
        profile = build_wall_configuration_profile(game, state.hwalls, state.vwalls)
    if (profile.hw, profile.vw) != (state.hwalls, state.vwalls):
        raise ValueError("wall profile does not match state")
    _populate_wall_candidates(game, profile)
    assert profile.by_label is not None
    candidate = profile.by_label.get(label)
    if candidate is None:
        return None, 0
    return (
        candidate.move if _candidate_preserves_paths(candidate, state) else None,
        1,
    )


def state_legality_errors(
    record: dict[str, Any],
    header: dict[str, Any],
    game: ReferenceGame,
    *,
    require_budget: bool = True,
    defer_wall_graph: bool = False,
) -> list[str]:
    errors: list[str] = []
    for field in STATE_FIELDS:
        if not is_safe_integer(record.get(field)):
            errors.append(f"{field} is not a safe integer")
    if require_budget and (
        not is_safe_integer(record.get("d")) or record.get("d", 0) < 1
    ):
        errors.append("d is not a positive safe integer")
    if errors:
        return errors

    p1, p2 = record["p1"], record["p2"]
    r1, r2 = record["r1"], record["r2"]
    turn, hw, vw = record["turn"], record["hw"], record["vw"]
    cells = game.W * game.H

    if p1 < 0 or p1 >= cells or p2 < 0 or p2 >= cells:
        errors.append("pawn outside board")
    if p1 == p2:
        errors.append("pawns overlap")
    if turn not in (P1, P2):
        errors.append("turn is not 0 or 1")
    if r1 < 0 or r1 > header["walls"] or r2 < 0 or r2 > header["walls"]:
        errors.append("wall stock outside range")

    mask_limit = 1 << game.S
    masks_in_range = 0 <= hw < mask_limit and 0 <= vw < mask_limit
    if not masks_in_range:
        errors.append("wall mask outside anchor grid")
    if masks_in_range:
        if not defer_wall_graph:
            errors.extend(_wall_geometry_errors(hw, vw, game))
        if r1 + r2 + hw.bit_count() + vw.bit_count() != 2 * header["walls"]:
            errors.append("wall conservation violated")

    pawns_in_range = 0 <= p1 < cells and 0 <= p2 < cells
    if masks_in_range and pawns_in_range:
        if not defer_wall_graph:
            if not game.has_goal_path(p1, P1, hw, vw):
                errors.append("Player 1 has no goal path")
            if not game.has_goal_path(p2, P2, hw, vw):
                errors.append("Player 2 has no goal path")
        if game.winner(_state_from_record(record)) is not None:
            errors.append("terminal state appears in node index")
    return errors


def header_errors(record: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if record.get("type") != "header":
        errors.append("first record is not a header")
    if record.get("format") != "qcert-1":
        errors.append(f"unsupported format {record.get('format')}")
    for field in ("width", "height", "walls", "target", "bound"):
        if not is_safe_integer(record.get(field)):
            errors.append(f"header {field} is not a safe integer")
    if errors:
        return errors

    width, height = record["width"], record["height"]
    if width < 2 or height < 2 or width * height > 255:
        errors.append("unsupported board dimensions")
    anchors = (width - 1) * (height - 1)
    if anchors < 1 or anchors > 31:
        errors.append("qcert-1 verifier supports 1..31 anchors")
    if record["walls"] < 0 or record["walls"] > 255:
        errors.append("walls outside supported range")
    if record["target"] not in (P1, P2):
        errors.append("target is not 0 or 1")
    if record["bound"] < 1:
        errors.append("bound is not positive")
    root = record.get("root")
    if not isinstance(root, dict):
        errors.append("root is not an object")
    return errors


def _move_label(move: tuple[str, int, int]) -> str:
    kind, first, second = move
    if kind == "P":
        return f"P:{first}"
    return f"{kind}:{first}:{second}"


def _short(value: Any, limit: int = 160) -> str:
    text = str(value)
    return text if len(text) <= limit else text[:limit] + "..."


@contextmanager
def _open_hashed_jsonl(path: Path) -> Iterable[tuple[TextIO, HashingRawReader, bool]]:
    """Yield decoded JSONL and an exact-byte tracker over the same descriptor."""
    try:
        raw = path.open("rb")
    except OSError as error:
        raise OperationalError(f"cannot open certificate: {error}") from error
    try:
        magic = raw.read(2)
        raw.seek(0)
    except OSError as error:
        raw.close()
        raise OperationalError(f"cannot inspect certificate: {error}") from error

    tracker = HashingRawReader(raw)
    compressed = magic == b"\x1f\x8b"
    binary: io.BufferedReader
    if compressed:
        binary = io.BufferedReader(StrictGzipReader(tracker))
    else:
        binary = io.BufferedReader(tracker)
    text = io.TextIOWrapper(binary, encoding="utf-8", errors="strict", newline=None)
    try:
        yield text, tracker, compressed
    finally:
        text.close()


def _database_sidecars(path: Path) -> tuple[Path, ...]:
    return (
        path,
        Path(str(path) + "-wal"),
        Path(str(path) + "-shm"),
        Path(str(path) + "-journal"),
    )


def _assert_database_available(path: Path) -> None:
    sidecars = _database_sidecars(path)
    if any(candidate.exists() for candidate in sidecars):
        raise OperationalError(f"refusing to overwrite database or sidecar: {path}")
    if not path.parent.is_dir():
        raise OperationalError(f"database parent directory does not exist: {path.parent}")


def _reserve_database(path: Path) -> None:
    _assert_database_available(path)
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_RDWR, 0o600)
        os.close(descriptor)
    except FileExistsError as error:
        raise OperationalError(f"refusing to overwrite database: {path}") from error
    except OSError as error:
        raise OperationalError(f"cannot create database: {error}") from error


def _configure_database(connection: sqlite3.Connection) -> None:
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA synchronous=NORMAL")
    connection.execute("PRAGMA temp_store=FILE")
    connection.execute("PRAGMA cache_size=-65536")
    connection.execute("PRAGMA mmap_size=268435456")
    connection.executescript("""
        CREATE TABLE nodes (
            hw INTEGER NOT NULL,
            vw INTEGER NOT NULL,
            p1 INTEGER NOT NULL,
            p2 INTEGER NOT NULL,
            r1 INTEGER NOT NULL,
            r2 INTEGER NOT NULL,
            turn INTEGER NOT NULL,
            d INTEGER NOT NULL,
            move TEXT,
            line_no INTEGER NOT NULL,
            PRIMARY KEY (hw, vw, p1, p2, r1, r2, turn)
        ) WITHOUT ROWID;
        CREATE TABLE metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        ) WITHOUT ROWID;
    """)
    connection.commit()


def _insert_metadata(connection: sqlite3.Connection, key: str, value: Any) -> None:
    connection.execute(
        "INSERT OR REPLACE INTO metadata(key,value) VALUES (?,?)",
        (key, json.dumps(value, separators=(",", ":"), sort_keys=True)),
    )


def _database_size(path: Path) -> int:
    total = 0
    for candidate in (path, Path(str(path) + "-wal"), Path(str(path) + "-shm")):
        try:
            total += candidate.stat().st_size
        except FileNotFoundError:
            pass
    return total


def _progress(enabled_every: int, phase: str, count: int) -> None:
    if enabled_every and count and count % enabled_every == 0:
        print(f"qcert sqlite verifier: {phase} {count:,}", file=sys.stderr, flush=True)


def verify_certificate(
    certificate: str | os.PathLike[str],
    *,
    database: str | os.PathLike[str] | None = None,
    temp_dir: str | os.PathLike[str] | None = None,
    progress_every: int = 0,
) -> dict[str, Any]:
    started = time.monotonic()
    source = Path(certificate).resolve()
    if not source.is_file():
        raise OperationalError(f"certificate is not a regular file: {source}")
    if progress_every < 0:
        raise OperationalError("progress interval must be non-negative")
    if database is not None and temp_dir is not None:
        raise OperationalError("--temp-dir cannot be combined with --database")

    temporary: tempfile.TemporaryDirectory[str] | None = None
    explicit_database_path: Path | None = None
    if database is not None:
        explicit_database_path = Path(database).resolve()
        # Fail before hashing a potentially multi-gigabyte input.  The later
        # O_EXCL reservation closes the race between this check and creation.
        _assert_database_available(explicit_database_path)
    elif temp_dir is not None and not Path(temp_dir).is_dir():
        raise OperationalError(f"temporary database directory does not exist: {temp_dir}")

    if explicit_database_path is None:
        try:
            temporary = tempfile.TemporaryDirectory(prefix="qcert-verify-", dir=temp_dir)
        except OSError as error:
            raise OperationalError(f"cannot create temporary database directory: {error}") from error
        database_path = Path(temporary.name) / "certificate.sqlite3"
        database_mode = "temporary"
    else:
        database_path = explicit_database_path
        database_mode = "explicit"

    try:
        _reserve_database(database_path)
    except Exception:
        if temporary is not None:
            temporary.cleanup()
        raise
    errors = ErrorCollector()
    header: dict[str, Any] | None = None
    game: ReferenceGame | None = None
    root_valid = False
    root_is_initial = False
    root_budget: int | None = None
    nodes = 0
    target_nodes = 0
    opponent_nodes = 0
    edges_checked = 0
    configuration_profiles = 0
    wall_candidate_profiles = 0
    profile_wall_candidates = 0
    wall_candidates_checked = 0
    ingest_seconds = 0.0
    verify_seconds = 0.0
    certificate_hash: str | None = None
    certificate_bytes: int | None = None
    compressed = False
    connection: sqlite3.Connection | None = None

    try:
        try:
            connection = sqlite3.connect(database_path)
            _configure_database(connection)
        except sqlite3.Error as error:
            raise OperationalError(f"cannot initialize SQLite database: {error}") from error

        ingest_started = time.monotonic()
        first_nonempty_seen = False
        insert = connection.cursor()
        connection.execute("BEGIN")
        try:
            with _open_hashed_jsonl(source) as (stream, artifact, compressed):
                for line_number, raw_line in enumerate(stream, 1):
                    line = raw_line.strip()
                    if not line:
                        continue
                    is_first = not first_nonempty_seen
                    first_nonempty_seen = True
                    try:
                        record = parse_json_record(line)
                    except DuplicateMemberError as error:
                        errors.fail(f"line {line_number}: {error}")
                        continue
                    except (json.JSONDecodeError, ValueError) as error:
                        errors.fail(f"line {line_number}: invalid JSON ({error})")
                        continue
                    if not isinstance(record, dict):
                        errors.fail(f"line {line_number}: record is not an object")
                        continue

                    record_type = record.get("type")
                    if is_first:
                        if record_type != "header":
                            errors.fail(f"line {line_number}: first record is not a header")
                            continue
                        header = record
                        problems = header_errors(record)
                        for problem in problems:
                            errors.fail(f"line {line_number}: {problem}")
                        if not problems:
                            game = ReferenceGame(record["width"], record["height"], record["walls"])
                            root_problems = state_legality_errors(
                                record["root"], record, game, require_budget=False,
                            )
                            for problem in root_problems:
                                errors.fail(f"header root: {problem}")
                            root_valid = not root_problems
                            if root_valid:
                                root_is_initial = _state_from_record(record["root"]) == game.initial()
                            _insert_metadata(connection, "header", record)
                        continue

                    if record_type == "header":
                        errors.fail(f"line {line_number}: multiple headers")
                        continue
                    if record_type != "node":
                        errors.fail(f"line {line_number}: unknown record type {record_type}")
                        continue
                    if header is None or game is None:
                        errors.fail(f"line {line_number}: node before a valid header")
                        continue

                    # Graph legality is configuration-local and is checked in
                    # the ordered second pass once per (hw,vw), not twice per
                    # certificate node.
                    problems = state_legality_errors(
                        record, header, game, defer_wall_graph=True,
                    )
                    for problem in problems:
                        errors.fail(f"line {line_number}: {problem}")
                    has_move = "move" in record
                    move_problem = False
                    if record.get("turn") == header["target"]:
                        if not has_move or not isinstance(record.get("move"), str) or not record.get("move"):
                            errors.fail(f"line {line_number}: target node lacks a move")
                            move_problem = True
                    elif has_move:
                        errors.fail(f"line {line_number}: opponent node contains a move")
                        move_problem = True
                    if problems or move_problem:
                        continue

                    key = _record_key(record)
                    try:
                        insert.execute(
                            """INSERT INTO nodes
                               (hw,vw,p1,p2,r1,r2,turn,d,move,line_no)
                               VALUES (?,?,?,?,?,?,?,?,?,?)""",
                            (*key, record["d"], record.get("move"), line_number),
                        )
                    except sqlite3.IntegrityError:
                        previous = connection.execute(
                            """SELECT line_no FROM nodes
                               WHERE hw=? AND vw=? AND p1=? AND p2=?
                                 AND r1=? AND r2=? AND turn=?""",
                            key,
                        ).fetchone()
                        where = f" (first at line {previous[0]})" if previous else ""
                        errors.fail(
                            f"line {line_number}: duplicate state {_key_text(key)}{where}"
                        )
                        continue
                    nodes += 1
                    _progress(progress_every, "indexed nodes", nodes)
                    if nodes % INSERT_BATCH == 0:
                        connection.commit()
                        connection.execute("BEGIN")
                # Reaching decoded EOF proves that the tracker consumed the
                # complete physical artifact, including the gzip trailer.
                certificate_hash = artifact.digest.hexdigest()
                certificate_bytes = artifact.bytes_read
        except (UnicodeError, gzip.BadGzipFile, EOFError) as error:
            errors.fail(f"invalid encoded input: {error}")
        except OSError as error:
            raise OperationalError(f"error while reading certificate: {error}") from error
        finally:
            connection.commit()
            insert.close()
        if header is None:
            errors.fail("no valid header")
        ingest_seconds = time.monotonic() - ingest_started

        if errors.count == 0 and header is not None and game is not None:
            verify_started = time.monotonic()
            target = header["target"]
            scan = connection.cursor()
            lookup = connection.cursor()
            current_profile_key: tuple[int, int] | None = None
            current_profile: WallConfigurationProfile | None = None

            def profile_for(state: State) -> WallConfigurationProfile:
                nonlocal current_profile_key, current_profile
                nonlocal configuration_profiles
                key = (state.hwalls, state.vwalls)
                if current_profile is None or current_profile_key != key:
                    current_profile = _build_configuration_profile(
                        game, state.hwalls, state.vwalls,
                    )
                    current_profile_key = key
                    configuration_profiles += 1
                return current_profile

            def wall_candidates_for(
                profile: WallConfigurationProfile,
            ) -> tuple[WallCandidate, ...]:
                nonlocal wall_candidate_profiles, profile_wall_candidates
                if profile.candidates is None:
                    candidates = _populate_wall_candidates(game, profile)
                    wall_candidate_profiles += 1
                    profile_wall_candidates += len(candidates)
                return profile.candidates

            def check_child(child: State, parent_d: int, context: str) -> None:
                nonlocal edges_checked
                edges_checked += 1
                winner = game.winner(child)
                if winner is not None:
                    if winner != target:
                        errors.fail(f"terminal child loses for target ({context})")
                    return
                found = lookup.execute(
                    """SELECT d FROM nodes
                       WHERE hw=? AND vw=? AND p1=? AND p2=?
                         AND r1=? AND r2=? AND turn=?""",
                    _state_key(child),
                ).fetchone()
                if found is None:
                    errors.fail(f"non-terminal child is uncovered ({context})")
                elif found[0] > parent_d - 1:
                    errors.fail(
                        f"child budget {found[0]} exceeds {parent_d - 1} ({context})"
                    )

            query = """SELECT hw,vw,p1,p2,r1,r2,turn,d,move,line_no FROM nodes
                       ORDER BY hw,vw,p1,p2,r1,r2,turn"""
            for row in scan.execute(query):
                hw, vw, p1, p2, r1, r2, turn, rank, declared_move, line_number = row
                state = State(p1, p2, r1, r2, turn, hw, vw)
                key = _state_key(state)
                configuration = profile_for(state)
                graph_problem = False
                for problem in configuration.geometry_errors:
                    errors.fail(f"{problem} at state {_key_text(key)}")
                    graph_problem = True
                if not configuration.player1_goal_cells & (1 << p1):
                    errors.fail(f"Player 1 has no goal path at state {_key_text(key)}")
                    graph_problem = True
                if not configuration.player2_goal_cells & (1 << p2):
                    errors.fail(f"Player 2 has no goal path at state {_key_text(key)}")
                    graph_problem = True
                if graph_problem:
                    continue
                if turn == target:
                    target_nodes += 1
                    remaining = state.r1 if turn == P1 else state.r2
                    wall_profile = (
                        configuration
                        if remaining > 0 and (
                            declared_move.startswith("H:")
                            or declared_move.startswith("V:")
                        )
                        else None
                    )
                    if wall_profile is not None:
                        wall_candidates_for(wall_profile)
                    chosen, checked = declared_move_with_profile(
                        game, state, declared_move, wall_profile,
                    )
                    wall_candidates_checked += checked
                    if chosen is None:
                        errors.fail(
                            f"declared move {_short(declared_move)} is illegal at {_key_text(key)}"
                        )
                        continue
                    check_child(
                        game.apply(state, chosen), rank,
                        f"via {declared_move} from {_key_text(key)}",
                    )
                else:
                    opponent_nodes += 1
                    moves = [("P", cell, -1) for cell in game.pawn_moves(state)]
                    remaining = state.r1 if turn == P1 else state.r2
                    if remaining > 0:
                        wall_profile = configuration
                        candidates = wall_candidates_for(wall_profile)
                        wall_candidates_checked += len(candidates)
                        moves.extend(
                            candidate.move
                            for candidate in candidates
                            if _candidate_preserves_paths(candidate, state)
                        )
                    if not moves:
                        errors.fail(f"state has no legal action {_key_text(key)}")
                        continue
                    for move in moves:
                        label = _move_label(move)
                        check_child(
                            game.apply(state, move), rank,
                            f"via {label} from {_key_text(key)}",
                        )
                _progress(progress_every, "verified nodes", target_nodes + opponent_nodes)
            scan.close()
            lookup.close()

            if root_valid:
                root_key = _record_key(header["root"])
                found = connection.execute(
                    """SELECT d FROM nodes
                       WHERE hw=? AND vw=? AND p1=? AND p2=?
                         AND r1=? AND r2=? AND turn=?""",
                    root_key,
                ).fetchone()
                if found is None:
                    errors.fail("root is absent from node index")
                else:
                    root_budget = found[0]
                    if root_budget > header["bound"]:
                        errors.fail(
                            f"root budget {root_budget} exceeds bound {header['bound']}"
                        )
            verify_seconds = time.monotonic() - verify_started

        if certificate_hash is not None:
            _insert_metadata(connection, "certificateSha256", certificate_hash)
            _insert_metadata(connection, "certificateBytes", certificate_bytes)
        _insert_metadata(connection, "verifierSha256", VERIFIER_SHA256)
        _insert_metadata(connection, "rulesSha256", RULES_SHA256)
        _insert_metadata(connection, "nodes", nodes)
        _insert_metadata(connection, "verificationErrorCount", errors.count)
        connection.commit()
        try:
            connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        except sqlite3.Error:
            # The main database is already complete; size reporting may include WAL.
            pass
        connection.close()
        connection = None
        database_bytes = _database_size(database_path)
        claim = None
        if header is not None and game is not None:
            claim = {
                "scope": "initial-position" if root_is_initial else "branch-position",
                "width": header["width"],
                "height": header["height"],
                "walls": header["walls"],
                "winner": header["target"] + 1,
                "bound": header["bound"],
                "root": header["root"],
            }
        seconds = time.monotonic() - started
        return {
            "ok": errors.count == 0,
            "file": str(source),
            "certificateSha256": certificate_hash,
            "certificateBytes": certificate_bytes,
            "verifierSha256": VERIFIER_SHA256,
            "rulesSha256": RULES_SHA256,
            "compression": "gzip" if compressed else "none",
            "claim": claim,
            "rootIsInitialPosition": root_is_initial,
            "rootBudget": root_budget,
            "verifiedTransforms": ["identity"] if errors.count == 0 else [],
            "nodes": nodes,
            "targetNodes": target_nodes,
            "opponentNodes": opponent_nodes,
            "edgesChecked": edges_checked,
            "configProfiles": configuration_profiles,
            "wallCandidateProfiles": wall_candidate_profiles,
            "profileWallCandidates": profile_wall_candidates,
            "wallCandidatesChecked": wall_candidates_checked,
            "errorCount": errors.count,
            "errors": errors.samples,
            "database": {
                "mode": database_mode,
                "path": str(database_path) if database_mode == "explicit" else None,
                "bytes": database_bytes,
                "deletedOnExit": database_mode == "temporary",
            },
            "ingestSeconds": round(ingest_seconds, 3),
            "verifySeconds": round(verify_seconds, 3),
            "seconds": round(seconds, 3),
        }
    except sqlite3.Error as error:
        raise OperationalError(f"SQLite failure: {error}") from error
    finally:
        if connection is not None:
            connection.close()
        if temporary is not None:
            temporary.cleanup()


def _parser() -> JsonArgumentParser:
    parser = JsonArgumentParser(description=__doc__)
    parser.add_argument("certificate", help="qcert-1 JSONL file (plain or gzip)")
    parser.add_argument(
        "--database",
        help="persistent SQLite path; must not already exist",
    )
    parser.add_argument(
        "--temp-dir",
        help="parent for the automatically removed temporary database",
    )
    parser.add_argument(
        "--progress-every",
        type=int,
        default=0,
        metavar="N",
        help="report each N indexed/verified nodes on stderr (default: quiet)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = verify_certificate(
            args.certificate,
            database=args.database,
            temp_dir=args.temp_dir,
            progress_every=args.progress_every,
        )
    except OperationalError as error:
        result = {
            "ok": False,
            "file": str(Path(args.certificate).resolve()),
            "errorKind": "operational",
            "errorCount": 1,
            "errors": [str(error)],
        }
        code = 2
    except KeyboardInterrupt:
        result = {
            "ok": False,
            "file": str(Path(args.certificate).resolve()),
            "errorKind": "interrupted",
            "errorCount": 1,
            "errors": ["verification interrupted"],
        }
        code = 2
    except Exception as error:  # Preserve the CLI's JSON/exit-code contract.
        result = {
            "ok": False,
            "file": str(Path(args.certificate).resolve()),
            "errorKind": "internal",
            "errorCount": 1,
            "errors": [f"{type(error).__name__}: {error}"],
        }
        code = 2
    else:
        code = 0 if result["ok"] else 1
    result.setdefault("verifierSha256", VERIFIER_SHA256)
    result.setdefault("rulesSha256", RULES_SHA256)
    print(json.dumps(result, separators=(",", ":"), sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
