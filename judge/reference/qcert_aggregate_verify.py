#!/usr/bin/env python3
"""Independent verifier for a qcert-aggregate-1 branch-certificate bundle.

The aggregate manifest is intentionally not an index of trusted search output.
The verifier regenerates the initial position, the declared winning first move,
and every opponent reply with :mod:`quoridor_reference`.  Each distinct
horizontal-reflection orbit is then bound to one independently verified
qcert-1 artifact.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import sys
import time
from typing import Any, Callable

from qcert_verify_sqlite import (
    OperationalError,
    RULES_SHA256,
    VERIFIER_SHA256 as QCERT_VERIFIER_SHA256,
    verify_certificate,
)
from quoridor_reference import P1, P2, ReferenceGame, State


MAX_SAFE_INTEGER = (1 << 53) - 1
STATE_FIELDS = ("p1", "p2", "r1", "r2", "turn", "hw", "vw")
TOP_FIELDS = frozenset(("type", "format", "claim", "parts", "replies"))
CLAIM_FIELDS = frozenset((
    "width", "height", "walls", "target", "bound", "root", "witness",
))
PART_FIELDS = frozenset(("id", "path", "sha256", "bound", "root"))
REPLY_FIELDS = frozenset(("move", "part", "transform"))
STATE_FIELD_SET = frozenset(STATE_FIELDS)
TRANSFORMS = frozenset(("identity", "mirror-columns"))
ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z")
SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
AGGREGATE_VERIFIER_SOURCE = Path(__file__).resolve()
AGGREGATE_VERIFIER_SHA256 = hashlib.sha256(
    AGGREGATE_VERIFIER_SOURCE.read_bytes()
).hexdigest()

PUBLISHED_CLAIM = {
    "width": 3,
    "height": 9,
    "walls": 10,
    "target": P1,
    "bound": 35,
    "root": {
        "p1": 25, "p2": 1, "r1": 10, "r2": 10,
        "turn": P1, "hw": 0, "vw": 0,
    },
    "witness": "P:22",
}
PUBLISHED_REPRESENTATIVES = frozenset(
    ["P:4", "P:0"]
    + [f"H:{row}:0" for row in range(8)]
    + [f"V:{row}:0" for row in range(8)]
)


class DuplicateMemberError(ValueError):
    """One JSON object contained the same decoded member name twice."""


class AggregateValidationError(ValueError):
    """The manifest or one of its certificate claims is invalid."""


class JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        print(json.dumps({
            "ok": False,
            "errorKind": "usage",
            "errorCount": 1,
            "errors": [message],
        }, separators=(",", ":"), sort_keys=True))
        raise SystemExit(2)


def _object_without_duplicate_members(
    pairs: list[tuple[str, Any]],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateMemberError(f"duplicate member name: {key}")
        result[key] = value
    return result


def _reject_nonstandard_constant(value: str) -> None:
    raise ValueError(f"non-standard JSON constant: {value}")


def parse_manifest(path: Path) -> tuple[dict[str, Any], str, int]:
    try:
        artifact = path.read_bytes()
        text = artifact.decode("utf-8", errors="strict")
    except (OSError, UnicodeError) as error:
        raise OperationalError(f"cannot read aggregate manifest: {error}") from error
    try:
        value = json.loads(
            text,
            object_pairs_hook=_object_without_duplicate_members,
            parse_constant=_reject_nonstandard_constant,
        )
    except (json.JSONDecodeError, DuplicateMemberError, ValueError) as error:
        raise AggregateValidationError(f"invalid aggregate JSON: {error}") from error
    if not isinstance(value, dict):
        raise AggregateValidationError("aggregate JSON is not an object")
    return value, hashlib.sha256(artifact).hexdigest(), len(artifact)


def _closed_object(value: Any, fields: frozenset[str], context: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise AggregateValidationError(f"{context} is not an object")
    actual = frozenset(value)
    if actual != fields:
        missing = sorted(fields - actual)
        extra = sorted(actual - fields)
        raise AggregateValidationError(
            f"{context} has wrong members (missing={missing}, extra={extra})"
        )
    return value


def _safe_integer(value: Any, context: str) -> int:
    # bool is an int subclass and is deliberately not accepted.
    if type(value) is not int or not -MAX_SAFE_INTEGER <= value <= MAX_SAFE_INTEGER:
        raise AggregateValidationError(f"{context} is not a JSON safe integer")
    return value


def _state_from_object(value: Any, context: str) -> State:
    record = _closed_object(value, STATE_FIELD_SET, context)
    numbers = {field: _safe_integer(record[field], f"{context}.{field}")
               for field in STATE_FIELDS}
    return State(
        numbers["p1"], numbers["p2"], numbers["r1"], numbers["r2"],
        numbers["turn"], numbers["hw"], numbers["vw"],
    )


def state_object(state: State) -> dict[str, int]:
    return {
        "p1": state.p1,
        "p2": state.p2,
        "r1": state.r1,
        "r2": state.r2,
        "turn": state.turn,
        "hw": state.hwalls,
        "vw": state.vwalls,
    }


def move_label(move: tuple[str, int, int]) -> str:
    kind, first, second = move
    if kind == "P":
        return f"P:{first}"
    return f"{kind}:{first}:{second}"


def _move_sort_key(label: str) -> tuple[str, int, int]:
    fields = label.split(":")
    try:
        if len(fields) == 2 and fields[0] == "P":
            return fields[0], int(fields[1]), -1
        if len(fields) == 3 and fields[0] in ("H", "V"):
            return fields[0], int(fields[1]), int(fields[2])
    except ValueError:
        pass
    raise AggregateValidationError(f"non-canonical move label: {label!r}")


def mirror_state(game: ReferenceGame, state: State) -> State:
    def mirror_cell(cell: int) -> int:
        row, column = divmod(cell, game.W)
        return row * game.W + (game.W - 1 - column)

    def mirror_mask(mask: int) -> int:
        result = 0
        for row in range(game.R):
            for column in range(game.C):
                source = 1 << (row * game.C + column)
                if mask & source:
                    target_column = game.C - 1 - column
                    result |= 1 << (row * game.C + target_column)
        return result

    return State(
        mirror_cell(state.p1), mirror_cell(state.p2),
        state.r1, state.r2, state.turn,
        mirror_mask(state.hwalls), mirror_mask(state.vwalls),
    )


def mirror_move_label(game: ReferenceGame, label: str) -> str:
    kind, first, second = _move_sort_key(label)
    if kind == "P":
        row, column = divmod(first, game.W)
        return f"P:{row * game.W + game.W - 1 - column}"
    return f"{kind}:{first}:{game.C - 1 - second}"


def _children(game: ReferenceGame, state: State) -> set[State]:
    return {game.apply(state, move) for move in game.legal_moves(state)}


def check_mirror_automorphism(game: ReferenceGame, state: State) -> None:
    mirrored = mirror_state(game, state)
    if mirror_state(game, mirrored) != state:
        raise AggregateValidationError("horizontal reflection is not an involution")
    if game.winner(mirrored) != game.winner(state):
        raise AggregateValidationError("horizontal reflection changed the winner")
    reflected_children = {mirror_state(game, child) for child in _children(game, state)}
    if reflected_children != _children(game, mirrored):
        raise AggregateValidationError(
            "horizontal reflection did not preserve the regenerated child set"
        )
    labels = {move_label(move) for move in game.legal_moves(state)}
    mirrored_labels = {move_label(move) for move in game.legal_moves(mirrored)}
    if {mirror_move_label(game, label) for label in labels} != mirrored_labels:
        raise AggregateValidationError(
            "horizontal reflection did not preserve the regenerated move labels"
        )


def _resolve_part_path(artifact_root: Path, value: Any, context: str) -> Path:
    if not isinstance(value, str) or not value:
        raise AggregateValidationError(f"{context} is not a non-empty string")
    if "\\" in value or ":" in value or "\x00" in value:
        raise AggregateValidationError(f"{context} is not a portable relative path")
    relative = PurePosixPath(value)
    if relative.is_absolute() or str(relative) != value:
        raise AggregateValidationError(f"{context} is not a normalized relative path")
    if any(part in ("", ".", "..") for part in relative.parts):
        raise AggregateValidationError(f"{context} contains a forbidden path component")
    candidate = artifact_root.joinpath(*relative.parts)
    try:
        resolved = candidate.resolve(strict=True)
    except OSError as error:
        raise OperationalError(f"cannot resolve {context}: {error}") from error
    try:
        resolved.relative_to(artifact_root)
    except ValueError as error:
        raise AggregateValidationError(f"{context} escapes --artifact-root") from error
    if not resolved.is_file():
        raise OperationalError(f"{context} is not a regular file: {resolved}")
    return resolved


def _published_profile_matches(claim: dict[str, Any]) -> bool:
    return claim == PUBLISHED_CLAIM


def _certificate_claim_expected(
    part: dict[str, Any], claim: dict[str, Any],
) -> dict[str, Any]:
    return {
        "scope": "branch-position",
        "width": claim["width"],
        "height": claim["height"],
        "walls": claim["walls"],
        "winner": claim["target"] + 1,
        "bound": part["bound"],
        "root": part["root"],
    }


PartVerifier = Callable[..., dict[str, Any]]


def verify_aggregate(
    manifest_path: str | os.PathLike[str],
    artifact_root: str | os.PathLike[str],
    *,
    temp_dir: str | os.PathLike[str] | None = None,
    progress_every: int = 0,
    part_verifier: PartVerifier = verify_certificate,
) -> dict[str, Any]:
    """Verify one aggregate and return a machine-readable successful report.

    Invalid proof data raises :class:`AggregateValidationError`; filesystem and
    SQLite failures raise :class:`OperationalError`.  ``part_verifier`` exists
    to make the aggregation logic independently unit-testable; the CLI always
    uses the disk-backed qcert-1 verifier.
    """
    started = time.monotonic()
    manifest_file = Path(manifest_path).resolve()
    if not manifest_file.is_file():
        raise OperationalError(f"aggregate manifest is not a regular file: {manifest_file}")
    try:
        root_path = Path(artifact_root).resolve(strict=True)
    except OSError as error:
        raise OperationalError(f"cannot resolve --artifact-root: {error}") from error
    if not root_path.is_dir():
        raise OperationalError(f"--artifact-root is not a directory: {root_path}")
    if temp_dir is not None and not Path(temp_dir).is_dir():
        raise OperationalError(f"temporary database directory does not exist: {temp_dir}")
    if type(progress_every) is not int or progress_every < 0:
        raise OperationalError("progress interval must be a non-negative integer")

    parsed, manifest_hash, manifest_bytes = parse_manifest(manifest_file)
    aggregate = _closed_object(parsed, TOP_FIELDS, "aggregate")
    if aggregate["type"] != "aggregate":
        raise AggregateValidationError("aggregate.type is not 'aggregate'")
    if aggregate["format"] != "qcert-aggregate-1":
        raise AggregateValidationError(
            f"unsupported aggregate format: {aggregate['format']!r}"
        )

    claim = _closed_object(aggregate["claim"], CLAIM_FIELDS, "claim")
    width = _safe_integer(claim["width"], "claim.width")
    height = _safe_integer(claim["height"], "claim.height")
    walls = _safe_integer(claim["walls"], "claim.walls")
    target = _safe_integer(claim["target"], "claim.target")
    bound = _safe_integer(claim["bound"], "claim.bound")
    if width < 2 or height < 3 or width * height > 255:
        raise AggregateValidationError("unsupported board dimensions (need W>=2, H>=3, W*H<=255)")
    anchors = (width - 1) * (height - 1)
    if anchors < 1 or anchors > 31:
        raise AggregateValidationError("aggregate verifier supports 1..31 anchors")
    if walls < 0 or walls > 255:
        raise AggregateValidationError("claim.walls is outside 0..255")
    if target not in (P1, P2):
        raise AggregateValidationError("claim.target is not 0 or 1")
    if bound < 3:
        raise AggregateValidationError("claim.bound is too small for a two-ply decomposition")
    claim_root = _state_from_object(claim["root"], "claim.root")
    witness = claim["witness"]
    if not isinstance(witness, str) or not witness:
        raise AggregateValidationError("claim.witness is not a non-empty string")

    game = ReferenceGame(width, height, walls)
    if claim_root != game.initial():
        raise AggregateValidationError("claim.root is not the regenerated initial position")
    if mirror_state(game, claim_root) != claim_root:
        raise AggregateValidationError(
            "claim.root is not fixed by horizontal reflection"
        )
    if claim_root.turn != target:
        raise AggregateValidationError("claim root is not a target-to-move position")
    root_moves = {move_label(move): move for move in game.legal_moves(claim_root)}
    opening = root_moves.get(witness)
    if opening is None:
        raise AggregateValidationError("claim.witness is not a regenerated legal root move")
    post_opening = game.apply(claim_root, opening)
    if game.winner(post_opening) is not None:
        raise AggregateValidationError("aggregate witness is terminal; no branch aggregate is needed")
    if post_opening.turn == target:
        raise AggregateValidationError("witness did not pass the turn to the opponent")
    if mirror_state(game, post_opening) != post_opening:
        raise AggregateValidationError(
            "claim.witness does not leave a reflection-invariant prefix"
        )
    response_moves = game.legal_moves(post_opening)
    if not response_moves:
        raise AggregateValidationError("post-witness state has no legal opponent response")
    response_states = {
        move_label(move): game.apply(post_opening, move) for move in response_moves
    }
    if len(response_states) != len(response_moves):
        raise AggregateValidationError("regenerated opponent move labels are not unique")
    state_to_response: dict[State, str] = {}
    for label, state in response_states.items():
        if state in state_to_response:
            raise AggregateValidationError("two opponent responses reach the same raw state")
        state_to_response[state] = label
    check_mirror_automorphism(game, claim_root)
    check_mirror_automorphism(game, post_opening)

    raw_parts = aggregate["parts"]
    if not isinstance(raw_parts, list) or not raw_parts:
        raise AggregateValidationError("parts is not a non-empty array")
    parts: dict[str, dict[str, Any]] = {}
    resolved_paths: set[Path] = set()
    raw_paths: set[str] = set()
    for index, value in enumerate(raw_parts):
        context = f"parts[{index}]"
        part = _closed_object(value, PART_FIELDS, context)
        part_id = part["id"]
        if not isinstance(part_id, str) or ID_RE.fullmatch(part_id) is None:
            raise AggregateValidationError(f"{context}.id is not a portable identifier")
        if part_id in parts:
            raise AggregateValidationError(f"duplicate part id: {part_id}")
        raw_path = part["path"]
        if not isinstance(raw_path, str):
            raise AggregateValidationError(f"{context}.path is not a string")
        if raw_path in raw_paths:
            raise AggregateValidationError(f"duplicate part path: {raw_path}")
        resolved_path = _resolve_part_path(root_path, raw_path, f"{context}.path")
        if resolved_path in resolved_paths:
            raise AggregateValidationError(
                f"two part paths resolve to the same artifact: {resolved_path}"
            )
        for earlier in resolved_paths:
            try:
                same_file = os.path.samefile(resolved_path, earlier)
            except OSError as error:
                raise OperationalError(
                    f"cannot compare part artifact identities: {error}"
                ) from error
            if same_file:
                raise AggregateValidationError(
                    f"two part paths alias the same file: {raw_path} and "
                    f"{earlier.relative_to(root_path).as_posix()}"
                )
        digest = part["sha256"]
        if not isinstance(digest, str) or SHA256_RE.fullmatch(digest) is None:
            raise AggregateValidationError(f"{context}.sha256 is not lowercase SHA-256")
        part_bound = _safe_integer(part["bound"], f"{context}.bound")
        if part_bound < 1 or part_bound > bound - 2:
            raise AggregateValidationError(f"{context}.bound is outside 1..claim.bound-2")
        part_root = _state_from_object(part["root"], f"{context}.root")
        normalized = dict(part)
        normalized["root"] = state_object(part_root)
        normalized["resolved_path"] = resolved_path
        parts[part_id] = normalized
        raw_paths.add(raw_path)
        resolved_paths.add(resolved_path)

    raw_replies = aggregate["replies"]
    if not isinstance(raw_replies, list) or not raw_replies:
        raise AggregateValidationError("replies is not a non-empty array")
    replies_by_move: dict[str, dict[str, str]] = {}
    mappings_by_part: dict[str, list[dict[str, str]]] = {part_id: [] for part_id in parts}
    for index, value in enumerate(raw_replies):
        context = f"replies[{index}]"
        reply = _closed_object(value, REPLY_FIELDS, context)
        move = reply["move"]
        part_id = reply["part"]
        transform = reply["transform"]
        if not isinstance(move, str) or not move:
            raise AggregateValidationError(f"{context}.move is not a non-empty string")
        if move in replies_by_move:
            raise AggregateValidationError(f"duplicate response mapping: {move}")
        if not isinstance(part_id, str) or part_id not in parts:
            raise AggregateValidationError(f"{context}.part references an unknown part")
        if transform not in TRANSFORMS:
            raise AggregateValidationError(f"{context}.transform is unsupported")
        normalized_reply = {"move": move, "part": part_id, "transform": transform}
        replies_by_move[move] = normalized_reply
        mappings_by_part[part_id].append(normalized_reply)
    actual_moves = set(replies_by_move)
    expected_moves = set(response_states)
    if actual_moves != expected_moves:
        raise AggregateValidationError(
            "reply mapping differs from regenerated legal responses "
            f"(missing={sorted(expected_moves - actual_moves)}, "
            f"extra={sorted(actual_moves - expected_moves)})"
        )

    identity_representatives: set[str] = set()
    for part_id, part in parts.items():
        mappings = mappings_by_part[part_id]
        identities = [item for item in mappings if item["transform"] == "identity"]
        mirrors = [item for item in mappings if item["transform"] == "mirror-columns"]
        if len(identities) != 1:
            raise AggregateValidationError(
                f"part {part_id} must have exactly one identity response"
            )
        identity_move = identities[0]["move"]
        root_state = _state_from_object(part["root"], f"part {part_id}.root")
        if root_state != response_states[identity_move]:
            raise AggregateValidationError(
                f"part {part_id} root differs from its regenerated identity response"
            )
        reflected_root = mirror_state(game, root_state)
        reflected_move = state_to_response.get(reflected_root)
        if reflected_move is None:
            raise AggregateValidationError(
                f"part {part_id} reflected root is not a regenerated response"
            )
        canonical = min((identity_move, reflected_move), key=_move_sort_key)
        if identity_move != canonical:
            raise AggregateValidationError(
                f"part {part_id} identity response is not the canonical reflection representative"
            )
        expected_mirrors = [] if reflected_move == identity_move else [reflected_move]
        if len(mirrors) != len(expected_mirrors) or (
            mirrors and mirrors[0]["move"] != expected_mirrors[0]
        ):
            raise AggregateValidationError(
                f"part {part_id} does not exactly cover its reflection orbit"
            )
        if len(mappings) != 1 + len(expected_mirrors):
            raise AggregateValidationError(f"part {part_id} has redundant mappings")
        identity_representatives.add(identity_move)
        check_mirror_automorphism(game, root_state)

    if len(parts) != len(identity_representatives):
        raise AggregateValidationError("part/reflection-orbit cardinality mismatch")
    derived_bound = 2 + max(part["bound"] for part in parts.values())
    if derived_bound != bound:
        raise AggregateValidationError(
            f"derived bound is {derived_bound}, not claim.bound {bound}"
        )

    published_profile = _published_profile_matches(claim)
    if published_profile:
        if len(response_states) != 35 or len(parts) != 18:
            raise AggregateValidationError(
                "published 3x9x10 profile must regenerate 35 replies in 18 orbits"
            )
        if identity_representatives != PUBLISHED_REPRESENTATIVES:
            raise AggregateValidationError(
                "published profile has the wrong canonical representative labels"
            )

    part_reports: list[dict[str, Any]] = []
    for number, (part_id, part) in enumerate(parts.items(), 1):
        print(
            f"qcert aggregate verifier: part {number}/{len(parts)} {part_id}",
            file=sys.stderr,
            flush=True,
        )
        try:
            result = part_verifier(
                part["resolved_path"],
                temp_dir=temp_dir,
                progress_every=progress_every,
            )
        except OperationalError:
            raise
        except Exception as error:
            raise AggregateValidationError(
                f"part {part_id} verifier failed: {type(error).__name__}: {error}"
            ) from error
        if not isinstance(result, dict):
            raise AggregateValidationError(f"part {part_id} verifier returned no result object")
        if result.get("ok") is not True:
            raise AggregateValidationError(
                f"part {part_id} qcert-1 verification failed: {result.get('errors')}"
            )
        if result.get("certificateSha256") != part["sha256"]:
            raise AggregateValidationError(
                f"part {part_id} stored-byte SHA-256 differs from the manifest"
            )
        expected_claim = _certificate_claim_expected(part, claim)
        if result.get("claim") != expected_claim:
            raise AggregateValidationError(
                f"part {part_id} verified claim differs from the manifest binding"
            )
        if result.get("rootIsInitialPosition") is not False:
            raise AggregateValidationError(f"part {part_id} is not a branch certificate")
        if result.get("verifiedTransforms") != ["identity"]:
            raise AggregateValidationError(
                f"part {part_id} qcert verifier did not report identity verification"
            )
        if result.get("verifierSha256") != QCERT_VERIFIER_SHA256:
            raise AggregateValidationError(
                f"part {part_id} reported a different qcert verifier source"
            )
        if result.get("rulesSha256") != RULES_SHA256:
            raise AggregateValidationError(
                f"part {part_id} reported a different rules-engine source"
            )
        root_budget = result.get("rootBudget")
        if type(root_budget) is not int or not 1 <= root_budget <= part["bound"]:
            raise AggregateValidationError(f"part {part_id} has an invalid verified root rank")
        part_reports.append({
            "id": part_id,
            "path": part["path"],
            "sha256": part["sha256"],
            "bound": part["bound"],
            "rootBudget": root_budget,
            "nodes": result.get("nodes"),
            "edgesChecked": result.get("edgesChecked"),
            "bytes": result.get("certificateBytes"),
            "verifierSha256": result.get("verifierSha256"),
            "rulesSha256": result.get("rulesSha256"),
        })

    return {
        "ok": True,
        "format": "qcert-aggregate-1",
        "manifest": str(manifest_file),
        "manifestSha256": manifest_hash,
        "manifestBytes": manifest_bytes,
        "aggregateVerifierSha256": AGGREGATE_VERIFIER_SHA256,
        "qcertVerifierSha256": QCERT_VERIFIER_SHA256,
        "rulesSha256": RULES_SHA256,
        "artifactRoot": str(root_path),
        "claim": {
            "scope": "initial-position",
            "width": width,
            "height": height,
            "walls": walls,
            "winner": target + 1,
            "bound": bound,
            "root": state_object(claim_root),
            "witness": witness,
        },
        "published3x9w10Profile": published_profile,
        "prefixPlies": 2,
        "suffixBound": max(part["bound"] for part in parts.values()),
        "derivedBound": derived_bound,
        "regeneratedReplies": len(response_states),
        "reflectionOrbits": len(parts),
        "identityRepresentatives": sorted(identity_representatives, key=_move_sort_key),
        "verifiedTransforms": ["identity", "mirror-columns"],
        "mirrorProofBasis": "rule-automorphism",
        "trustedPrecomputedListings": False,
        "parts": part_reports,
        "seconds": round(time.monotonic() - started, 3),
    }


def _parser() -> JsonArgumentParser:
    parser = JsonArgumentParser(description=__doc__)
    parser.add_argument("manifest", help="qcert-aggregate-1 JSON manifest")
    parser.add_argument(
        "--artifact-root",
        required=True,
        help="directory against which every manifest part path is resolved",
    )
    parser.add_argument(
        "--temp-dir",
        help="parent directory for each temporary qcert SQLite database",
    )
    parser.add_argument(
        "--progress-every",
        type=int,
        default=0,
        metavar="N",
        help="forward qcert progress every N nodes (default: quiet)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = verify_aggregate(
            args.manifest,
            args.artifact_root,
            temp_dir=args.temp_dir,
            progress_every=args.progress_every,
        )
        code = 0
    except AggregateValidationError as error:
        result = {
            "ok": False,
            "errorKind": "invalid",
            "errorCount": 1,
            "errors": [str(error)],
        }
        code = 1
    except OperationalError as error:
        result = {
            "ok": False,
            "errorKind": "operational",
            "errorCount": 1,
            "errors": [str(error)],
        }
        code = 2
    except KeyboardInterrupt:
        result = {
            "ok": False,
            "errorKind": "interrupted",
            "errorCount": 1,
            "errors": ["verification interrupted"],
        }
        code = 2
    except Exception as error:  # Preserve the CLI JSON/exit-code contract.
        result = {
            "ok": False,
            "errorKind": "internal",
            "errorCount": 1,
            "errors": [f"{type(error).__name__}: {error}"],
        }
        code = 2
    result.setdefault("aggregateVerifierSha256", AGGREGATE_VERIFIER_SHA256)
    result.setdefault("qcertVerifierSha256", QCERT_VERIFIER_SHA256)
    result.setdefault("rulesSha256", RULES_SHA256)
    print(json.dumps(result, separators=(",", ":"), sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
