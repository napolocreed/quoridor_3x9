#!/usr/bin/env python3
"""Differential-check qcert wall profiles on states from an accepted SQLite index.

This utility does no game-tree search.  It deterministically selects distinct
wall configurations from a persistent qcert SQLite index, selects one indexed
state per configuration, and compares the optimized
``legal_moves_with_profile`` result against ``ReferenceGame.legal_moves``.

The report binds the sample to the complete database and certificate bytes and
to the exact verifier/rules sources recorded by the accepted index.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import time
from typing import Any, Iterable

import qcert_verify_sqlite as qcert
from quoridor_reference import P1, P2, ReferenceGame, State


SAMPLE_ALGORITHM = "wall-count-stratified-sha256-v1"
STATE_ALGORITHM = "minimum-sha256-per-configuration-v1"
DEFAULT_SEED = "qcert-H10-profile-differential-2026-08-01"
HASH_BLOCK = 8 * 1024 * 1024


def _sha256_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(HASH_BLOCK), b""):
            digest.update(block)
            size += len(block)
    return digest.hexdigest(), size


def _sqlite_sidecar_bytes(path: Path) -> dict[str, int]:
    return {
        name: candidate.stat().st_size if candidate.exists() else 0
        for name, candidate in (
            ("wal", Path(str(path) + "-wal")),
            ("shm", Path(str(path) + "-shm")),
            ("journal", Path(str(path) + "-journal")),
        )
    }


def _reject_nonempty_sqlite_data_sidecars(sizes: dict[str, int]) -> None:
    nonempty = {
        name: size for name, size in sizes.items()
        if name in ("wal", "journal") and size != 0
    }
    if nonempty:
        raise ValueError(
            "immutable SQLite input has non-empty data sidecars: "
            + ", ".join(f"{name}={size}" for name, size in sorted(nonempty.items()))
        )


def _metadata(connection: sqlite3.Connection) -> dict[str, Any]:
    return {
        key: json.loads(value)
        for key, value in connection.execute(
            "SELECT key,value FROM metadata ORDER BY key"
        )
    }


def _selection_digest(seed: str, values: Iterable[int]) -> bytes:
    material = seed + "\0" + ",".join(str(value) for value in values)
    return hashlib.sha256(material.encode("ascii")).digest()


def _stratified_configurations(
    configurations: list[tuple[int, int]], wanted: int, seed: str,
) -> tuple[list[tuple[int, int]], dict[int, int], dict[int, int]]:
    """Sample configurations proportionally by number of placed walls.

    Every non-empty wall-count stratum receives one slot before the remaining
    slots are apportioned with Hamilton's largest-remainder method.  Within a
    stratum, SHA-256 ranking avoids dependence on SQLite's numeric mask order.
    """
    if wanted <= 0:
        raise ValueError("sample size must be positive")
    wanted = min(wanted, len(configurations))
    by_walls: dict[int, list[tuple[int, int]]] = defaultdict(list)
    for hw, vw in configurations:
        by_walls[hw.bit_count() + vw.bit_count()].append((hw, vw))
    population = {walls: len(items) for walls, items in sorted(by_walls.items())}

    strata = sorted(by_walls)
    allocation = {walls: 0 for walls in strata}
    if wanted >= len(strata):
        for walls in strata:
            allocation[walls] = 1
        remaining = wanted - len(strata)
        capacity_total = len(configurations) - len(strata)
        if remaining and capacity_total:
            remainders: list[tuple[int, int]] = []
            assigned = 0
            for walls in strata:
                capacity = len(by_walls[walls]) - 1
                numerator = remaining * capacity
                extra, remainder = divmod(numerator, capacity_total)
                allocation[walls] += extra
                assigned += extra
                remainders.append((remainder, walls))
            for _, walls in sorted(remainders, key=lambda item: (-item[0], item[1])):
                if assigned >= remaining:
                    break
                if allocation[walls] < len(by_walls[walls]):
                    allocation[walls] += 1
                    assigned += 1
    else:
        # This branch is useful for quick local probes.  Production samples are
        # larger than the number of strata and therefore exercise every one.
        ranked_strata = sorted(
            strata,
            key=lambda walls: _selection_digest(seed + ":stratum", (walls,)),
        )
        for walls in ranked_strata[:wanted]:
            allocation[walls] = 1

    selected: list[tuple[int, int]] = []
    for walls in strata:
        ranked = sorted(
            by_walls[walls],
            key=lambda masks: (
                _selection_digest(seed + ":configuration", (walls, *masks)),
                masks,
            ),
        )
        selected.extend(ranked[:allocation[walls]])
    selected.sort(
        key=lambda masks: (
            masks[0].bit_count() + masks[1].bit_count(),
            _selection_digest(seed + ":configuration", masks),
            masks,
        )
    )
    if len(selected) != wanted or len(set(selected)) != wanted:
        raise AssertionError("configuration sampler did not return the requested set")
    selected_counts = Counter(hw.bit_count() + vw.bit_count() for hw, vw in selected)
    return selected, population, dict(sorted(selected_counts.items()))


def _representative_state(
    connection: sqlite3.Connection, hw: int, vw: int, seed: str,
) -> tuple[State, int, str | None, int, int]:
    rows = connection.execute(
        """SELECT p1,p2,r1,r2,turn,d,move,line_no FROM nodes
           WHERE hw=? AND vw=? ORDER BY p1,p2,r1,r2,turn""",
        (hw, vw),
    )
    best: tuple[bytes, tuple[int, int, int, int, int, int, str | None, int]] | None = None
    count = 0
    for p1, p2, r1, r2, turn, rank, move, line_no in rows:
        count += 1
        values = (hw, vw, p1, p2, r1, r2, turn, rank, line_no)
        candidate = (
            _selection_digest(seed + ":state", values),
            (p1, p2, r1, r2, turn, rank, move, line_no),
        )
        if best is None or candidate < best:
            best = candidate
    if best is None:
        raise AssertionError(f"configuration {hw},{vw} contains no states")
    p1, p2, r1, r2, turn, rank, move, line_no = best[1]
    return State(p1, p2, r1, r2, turn, hw, vw), rank, move, line_no, count


def _moves_json(moves: Iterable[tuple[str, int, int]]) -> list[list[Any]]:
    return [list(move) for move in sorted(moves)]


def _move_label(move: tuple[str, int, int]) -> str:
    kind, first, second = move
    return f"P:{first}" if kind == "P" else f"{kind}:{first}:{second}"


def _connectivity_mask_differential(
    game: ReferenceGame,
    profile: qcert.WallConfigurationProfile,
) -> tuple[dict[str, Any] | None, int, int, int]:
    """Compare every optimized goal mask bit with a fresh reference BFS."""
    base_tests = 0
    candidate_tests = 0

    def compare(
        hw: int, vw: int, masks: tuple[int, int], context: str,
    ) -> dict[str, Any] | None:
        nonlocal base_tests, candidate_tests
        for player, mask in ((P1, masks[0]), (P2, masks[1])):
            for cell in range(game.W * game.H):
                optimized = bool(mask & (1 << cell))
                naive = game.has_goal_path(cell, player, hw, vw)
                if context == "base":
                    base_tests += 1
                else:
                    candidate_tests += 1
                if optimized != naive:
                    return {
                        "context": context,
                        "hw": hw,
                        "vw": vw,
                        "player": player,
                        "cell": cell,
                        "optimized": optimized,
                        "naive": naive,
                    }
        return None

    divergence = compare(
        profile.hw,
        profile.vw,
        (profile.player1_goal_cells, profile.player2_goal_cells),
        "base",
    )
    if divergence is not None:
        return divergence, base_tests, candidate_tests, 0

    assert profile.candidates is not None
    candidates_checked = 0
    for candidate in profile.candidates:
        kind, row, col = candidate.move
        bit = game.wbit(row, col)
        next_hw = profile.hw | bit if kind == "H" else profile.hw
        next_vw = profile.vw | bit if kind == "V" else profile.vw
        divergence = compare(
            next_hw,
            next_vw,
            (candidate.player1_goal_cells, candidate.player2_goal_cells),
            candidate.label,
        )
        candidates_checked += 1
        if divergence is not None:
            return divergence, base_tests, candidate_tests, candidates_checked
    return None, base_tests, candidate_tests, candidates_checked


def _invalid_wall_labels(
    game: ReferenceGame,
    state: State,
    profile: qcert.WallConfigurationProfile,
    legal_labels: set[str],
    seed: str,
    wanted: int = 2,
) -> list[tuple[str, str]]:
    """Choose deterministic rejected labels, preferring distinct reasons."""
    all_labels = [
        f"{kind}:{row}:{col}"
        for kind in ("H", "V")
        for row in range(game.R)
        for col in range(game.C)
    ]
    assert profile.by_label is not None
    remaining = state.r1 if state.turn == P1 else state.r2
    candidates: list[tuple[bytes, str, str]] = []
    state_key = (
        state.hwalls, state.vwalls, state.p1, state.p2,
        state.r1, state.r2, state.turn,
    )
    for label in all_labels:
        if label in legal_labels:
            continue
        candidate = profile.by_label.get(label)
        if remaining <= 0:
            reason = "no-mover-stock"
        elif candidate is None:
            reason = "geometrically-invalid"
        else:
            preserves_paths = bool(
                candidate.player1_goal_cells & (1 << state.p1)
                and candidate.player2_goal_cells & (1 << state.p2)
            )
            if preserves_paths:
                raise AssertionError(
                    f"wall label {label} is profile-legal but absent from naive moves"
                )
            reason = "path-invalid"
        material = (
            seed + ":invalid-label\0" + ",".join(map(str, state_key))
            + "\0" + label
        )
        candidates.append((hashlib.sha256(material.encode("ascii")).digest(), label, reason))
    candidates.sort()
    if len(candidates) < wanted:
        raise AssertionError("not enough rejected wall labels for negative probes")

    chosen: list[tuple[str, str]] = []
    if remaining > 0:
        # When available, exercise both the geometry lookup rejection and the
        # candidate path-mask rejection before filling from the global ranking.
        for desired_reason in ("geometrically-invalid", "path-invalid"):
            found = next(
                ((label, reason) for _, label, reason in candidates
                 if reason == desired_reason),
                None,
            )
            if found is not None:
                chosen.append(found)
    for _, label, reason in candidates:
        if len(chosen) >= wanted:
            break
        if all(existing_label != label for existing_label, _ in chosen):
            chosen.append((label, reason))
    return chosen[:wanted]


def _range(values: Iterable[int]) -> list[int]:
    materialized = list(values)
    return [min(materialized), max(materialized)]


def check(
    database_path: Path,
    certificate_path: Path,
    *,
    sample_configurations: int,
    seed: str,
    expected_database_sha256: str | None,
    expected_certificate_sha256: str | None,
    expected_verifier_sha256: str | None,
    expected_rules_sha256: str | None,
) -> dict[str, Any]:
    started = time.monotonic()
    database_path = database_path.resolve(strict=True)
    certificate_path = certificate_path.resolve(strict=True)
    checker_path = Path(__file__).resolve()

    database_sha256, database_bytes = _sha256_file(database_path)
    certificate_sha256, certificate_bytes = _sha256_file(certificate_path)
    checker_sha256, _ = _sha256_file(checker_path)
    sidecars_before = _sqlite_sidecar_bytes(database_path)
    _reject_nonempty_sqlite_data_sidecars(sidecars_before)

    expected = {
        "database": expected_database_sha256,
        "certificate": expected_certificate_sha256,
        "verifier": expected_verifier_sha256,
        "rules": expected_rules_sha256,
    }
    actual = {
        "database": database_sha256,
        "certificate": certificate_sha256,
        "verifier": qcert.VERIFIER_SHA256,
        "rules": qcert.RULES_SHA256,
    }
    for name, wanted in expected.items():
        if wanted is not None and actual[name] != wanted.lower():
            raise ValueError(
                f"{name} SHA-256 mismatch: expected {wanted.lower()}, got {actual[name]}"
            )

    uri = database_path.as_uri() + "?mode=ro&immutable=1"
    connection = sqlite3.connect(uri, uri=True)
    try:
        quick_check = connection.execute("PRAGMA quick_check").fetchone()[0]
        if quick_check != "ok":
            raise ValueError(f"SQLite quick_check failed: {quick_check}")
        metadata = _metadata(connection)
        required_metadata = {
            "certificateSha256", "certificateBytes", "verifierSha256",
            "rulesSha256", "verificationErrorCount", "header", "nodes",
        }
        missing = sorted(required_metadata - metadata.keys())
        if missing:
            raise ValueError(f"SQLite metadata is missing {missing}")
        bindings = {
            "certificateSha256": certificate_sha256,
            "certificateBytes": certificate_bytes,
            "verifierSha256": qcert.VERIFIER_SHA256,
            "rulesSha256": qcert.RULES_SHA256,
        }
        for key, value in bindings.items():
            if metadata[key] != value:
                raise ValueError(
                    f"SQLite metadata {key} mismatch: {metadata[key]!r} != {value!r}"
                )
        if metadata["verificationErrorCount"] != 0:
            raise ValueError("SQLite index was not produced by an accepting verification")

        header = metadata["header"]
        game = ReferenceGame(header["width"], header["height"], header["walls"])
        configurations = list(connection.execute(
            "SELECT DISTINCT hw,vw FROM nodes ORDER BY hw,vw"
        ))
        selected, config_population, selected_by_walls = _stratified_configurations(
            configurations, sample_configurations, seed,
        )

        turn_counts: Counter[int] = Counter()
        mover_stock_counts: Counter[int] = Counter()
        stock_pairs: set[tuple[int, int]] = set()
        p1_cells: set[int] = set()
        p2_cells: set[int] = set()
        pawn_pairs: set[tuple[int, int]] = set()
        ranks: list[int] = []
        states_per_configuration: list[int] = []
        legal_move_counts: list[int] = []
        move_type_counts: Counter[str] = Counter()
        states_with_wall_moves = 0
        states_without_mover_walls = 0
        target_declared_nodes = 0
        target_declared_type_counts: Counter[str] = Counter()
        target_declared_wall_bit_tests = 0
        invalid_label_attempts = 0
        invalid_label_rejections = 0
        invalid_label_reason_counts: Counter[str] = Counter()
        profiles_with_invalid_reason: Counter[str] = Counter()
        base_connectivity_mask_tests = 0
        candidate_connectivity_mask_tests = 0
        connectivity_wall_candidates_checked = 0

        for index, (hw, vw) in enumerate(selected, 1):
            state, rank, declared_move, line_no, config_states = _representative_state(
                connection, hw, vw, seed,
            )
            profile = qcert.build_wall_configuration_profile(game, hw, vw)
            (
                connectivity_divergence,
                base_mask_tests,
                candidate_mask_tests,
                profile_candidates_checked,
            ) = _connectivity_mask_differential(game, profile)
            base_connectivity_mask_tests += base_mask_tests
            candidate_connectivity_mask_tests += candidate_mask_tests
            connectivity_wall_candidates_checked += profile_candidates_checked
            if connectivity_divergence is not None:
                return {
                    "ok": False,
                    "status": "connectivity-mask-divergence",
                    "sampleIndex": index,
                    "configuration": {"hw": hw, "vw": vw},
                    "divergence": connectivity_divergence,
                    "databaseSha256": database_sha256,
                    "certificateSha256": certificate_sha256,
                    "verifierSha256": qcert.VERIFIER_SHA256,
                    "rulesSha256": qcert.RULES_SHA256,
                    "checkerSha256": checker_sha256,
                    "seconds": round(time.monotonic() - started, 3),
                }
            optimized = qcert.legal_moves_with_profile(game, state, profile)
            naive = game.legal_moves(state)
            optimized_counter = Counter(optimized)
            naive_counter = Counter(naive)
            if optimized_counter != naive_counter:
                return {
                    "ok": False,
                    "status": "divergence",
                    "sampleIndex": index,
                    "configuration": {"hw": hw, "vw": vw},
                    "state": {
                        "p1": state.p1, "p2": state.p2,
                        "r1": state.r1, "r2": state.r2,
                        "turn": state.turn, "hw": hw, "vw": vw,
                        "d": rank, "move": declared_move, "line": line_no,
                    },
                    "optimizedMoves": _moves_json(optimized),
                    "naiveMoves": _moves_json(naive),
                    "optimizedOnly": _moves_json(
                        (optimized_counter - naive_counter).elements()
                    ),
                    "naiveOnly": _moves_json(
                        (naive_counter - optimized_counter).elements()
                    ),
                    "databaseSha256": database_sha256,
                    "certificateSha256": certificate_sha256,
                    "verifierSha256": qcert.VERIFIER_SHA256,
                    "rulesSha256": qcert.RULES_SHA256,
                    "checkerSha256": checker_sha256,
                    "seconds": round(time.monotonic() - started, 3),
                }

            naive_by_label = {_move_label(move): move for move in naive}
            if len(naive_by_label) != len(naive):
                raise AssertionError("naive move list contains duplicate labels")
            if state.turn == header["target"]:
                target_declared_nodes += 1
                if not isinstance(declared_move, str):
                    return {
                        "ok": False,
                        "status": "declared-move-divergence",
                        "sampleIndex": index,
                        "reason": "target node has no declared move",
                        "line": line_no,
                        "databaseSha256": database_sha256,
                        "certificateSha256": certificate_sha256,
                        "verifierSha256": qcert.VERIFIER_SHA256,
                        "rulesSha256": qcert.RULES_SHA256,
                        "checkerSha256": checker_sha256,
                    }
                optimized_declared, wall_bit_tests = qcert.declared_move_with_profile(
                    game, state, declared_move, profile,
                )
                naive_declared = naive_by_label.get(declared_move)
                if optimized_declared != naive_declared or naive_declared is None:
                    return {
                        "ok": False,
                        "status": "declared-move-divergence",
                        "sampleIndex": index,
                        "line": line_no,
                        "declaredMove": declared_move,
                        "optimizedMove": (
                            list(optimized_declared)
                            if optimized_declared is not None else None
                        ),
                        "naiveMove": (
                            list(naive_declared) if naive_declared is not None else None
                        ),
                        "databaseSha256": database_sha256,
                        "certificateSha256": certificate_sha256,
                        "verifierSha256": qcert.VERIFIER_SHA256,
                        "rulesSha256": qcert.RULES_SHA256,
                        "checkerSha256": checker_sha256,
                    }
                target_declared_type_counts[optimized_declared[0]] += 1
                target_declared_wall_bit_tests += wall_bit_tests

            invalid_reasons_in_profile: set[str] = set()
            for invalid_label, invalid_reason in _invalid_wall_labels(
                game, state, profile, set(naive_by_label), seed,
            ):
                invalid_label_attempts += 1
                rejected, _ = qcert.declared_move_with_profile(
                    game, state, invalid_label, profile,
                )
                if rejected is not None:
                    return {
                        "ok": False,
                        "status": "invalid-label-accepted",
                        "sampleIndex": index,
                        "line": line_no,
                        "label": invalid_label,
                        "classifiedReason": invalid_reason,
                        "optimizedMove": list(rejected),
                        "databaseSha256": database_sha256,
                        "certificateSha256": certificate_sha256,
                        "verifierSha256": qcert.VERIFIER_SHA256,
                        "rulesSha256": qcert.RULES_SHA256,
                        "checkerSha256": checker_sha256,
                    }
                invalid_label_rejections += 1
                invalid_label_reason_counts[invalid_reason] += 1
                invalid_reasons_in_profile.add(invalid_reason)
            profiles_with_invalid_reason.update(invalid_reasons_in_profile)

            turn_counts[state.turn] += 1
            mover_stock = state.r1 if state.turn == P1 else state.r2
            mover_stock_counts[mover_stock] += 1
            stock_pairs.add((state.r1, state.r2))
            p1_cells.add(state.p1)
            p2_cells.add(state.p2)
            pawn_pairs.add((state.p1, state.p2))
            ranks.append(rank)
            states_per_configuration.append(config_states)
            legal_move_counts.append(len(naive))
            move_type_counts.update(move[0] for move in naive)
            states_with_wall_moves += any(move[0] != "P" for move in naive)
            states_without_mover_walls += mover_stock == 0

        coverage_checks = {
            "atLeast1000DistinctConfigurations": len(selected) >= 1000,
            "bothTurns": set(turn_counts) == {P1, P2},
            "multipleStockPairs": len(stock_pairs) >= 4,
            "multipleP1Cells": len(p1_cells) >= 3,
            "multipleP2Cells": len(p2_cells) >= 3,
            "multiplePawnPairs": len(pawn_pairs) >= 10,
            "multipleWallCountStrata": len(selected_by_walls) >= 3,
            "wallAndPawnOnlyMoveSets": (
                states_with_wall_moves > 0 and states_without_mover_walls > 0
            ),
            "allTargetDeclaredMovesMatchedNaive": (
                target_declared_nodes == turn_counts[header["target"]]
            ),
            "twoInvalidLabelsRejectedPerProfile": (
                invalid_label_attempts == 2 * len(selected)
                and invalid_label_rejections == invalid_label_attempts
            ),
        }
        if not all(coverage_checks.values()):
            raise ValueError(f"sample coverage gate failed: {coverage_checks}")

        # Rehash after the read-only scan so the receipt also detects a
        # concurrent replacement or mutation of the persistent index.
        database_sha256_after, database_bytes_after = _sha256_file(database_path)
        if (database_sha256_after, database_bytes_after) != (
            database_sha256, database_bytes,
        ):
            raise ValueError("SQLite index changed while the differential check ran")
        sidecars_after = _sqlite_sidecar_bytes(database_path)
        _reject_nonempty_sqlite_data_sidecars(sidecars_after)

        return {
            "ok": True,
            "status": "no-divergence",
            "scope": "move-generation-only; no proof search performed",
            "sample": {
                "seed": seed,
                "configurationAlgorithm": SAMPLE_ALGORITHM,
                "stateAlgorithm": STATE_ALGORITHM,
                "populationConfigurations": len(configurations),
                "sampledConfigurations": len(selected),
                "sampledStates": len(selected),
                "configurationFraction": len(selected) / len(configurations),
                "nodeFraction": len(selected) / metadata["nodes"],
                "configurationWallCountPopulation": {
                    str(key): value for key, value in config_population.items()
                },
                "configurationWallCountSample": {
                    str(key): value for key, value in selected_by_walls.items()
                },
            },
            "comparison": {
                "optimized": "qcert_verify_sqlite.legal_moves_with_profile",
                "naive": "quoridor_reference.ReferenceGame.legal_moves",
                "comparison": "exact move multiset",
                "divergences": 0,
                "statesCompared": len(selected),
                "legalMoveCountRange": _range(legal_move_counts),
                "legalMovesCompared": sum(legal_move_counts),
                "moveTypeCounts": dict(sorted(move_type_counts.items())),
                "targetDeclaredMoves": {
                    "nodesChecked": target_declared_nodes,
                    "typeCounts": dict(sorted(target_declared_type_counts.items())),
                    "wallBitTests": target_declared_wall_bit_tests,
                    "allMatchedNaiveMembership": True,
                },
                "invalidDeclaredLabels": {
                    "attempted": invalid_label_attempts,
                    "rejected": invalid_label_rejections,
                    "perSampledProfile": 2,
                    "reasonCounts": dict(sorted(invalid_label_reason_counts.items())),
                    "profilesByExercisedReason": dict(
                        sorted(profiles_with_invalid_reason.items())
                    ),
                },
                "connectivityMasks": {
                    "optimized": "qcert goal-connectivity bit masks",
                    "naive": "ReferenceGame.has_goal_path BFS",
                    "allBoardCells": game.W * game.H,
                    "baseMaskTests": base_connectivity_mask_tests,
                    "wallCandidatesChecked": connectivity_wall_candidates_checked,
                    "candidateMaskTests": candidate_connectivity_mask_tests,
                    "divergences": 0,
                },
            },
            "coverage": {
                "checks": coverage_checks,
                "turnCounts": {"P1": turn_counts[P1], "P2": turn_counts[P2]},
                "moverStockRange": _range(mover_stock_counts.elements()),
                "moverStockCounts": {
                    str(key): value for key, value in sorted(mover_stock_counts.items())
                },
                "uniqueStockPairs": len(stock_pairs),
                "uniqueP1Cells": len(p1_cells),
                "uniqueP2Cells": len(p2_cells),
                "uniquePawnPairs": len(pawn_pairs),
                "rankRange": _range(ranks),
                "statesPerConfigurationRange": _range(states_per_configuration),
                "statesWithWallMoves": states_with_wall_moves,
                "statesWithoutMoverWalls": states_without_mover_walls,
            },
            "artifacts": {
                "database": {
                    "path": str(database_path),
                    "sha256": database_sha256,
                    "bytes": database_bytes,
                    "quickCheck": quick_check,
                    "hashStableDuringRun": True,
                    "sidecarBytesBefore": sidecars_before,
                    "sidecarBytesAfter": sidecars_after,
                    "nonemptyWalOrJournalRejected": True,
                    "metadataNodes": metadata["nodes"],
                    "metadataVerificationErrorCount": metadata["verificationErrorCount"],
                },
                "certificate": {
                    "path": str(certificate_path),
                    "sha256": certificate_sha256,
                    "bytes": certificate_bytes,
                },
                "verifierSha256": qcert.VERIFIER_SHA256,
                "rulesSha256": qcert.RULES_SHA256,
                "checkerSha256": checker_sha256,
                "metadataBindingsMatch": True,
                "explicitExpectedHashesMatch": all(value is not None for value in expected.values()),
            },
            "claim": {
                "width": header["width"], "height": header["height"],
                "walls": header["walls"], "target": header["target"],
                "bound": header["bound"], "root": header["root"],
            },
            "python": sys.version.split()[0],
            "sqlite": sqlite3.sqlite_version,
            "seconds": round(time.monotonic() - started, 3),
        }
    finally:
        connection.close()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("database", type=Path, help="accepted persistent qcert SQLite index")
    parser.add_argument("certificate", type=Path, help="certificate indexed by the database")
    parser.add_argument("--sample-configurations", type=int, default=1500)
    parser.add_argument("--seed", default=DEFAULT_SEED)
    parser.add_argument("--expected-database-sha256")
    parser.add_argument("--expected-certificate-sha256")
    parser.add_argument("--expected-verifier-sha256")
    parser.add_argument("--expected-rules-sha256")
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        result = check(
            args.database,
            args.certificate,
            sample_configurations=args.sample_configurations,
            seed=args.seed,
            expected_database_sha256=args.expected_database_sha256,
            expected_certificate_sha256=args.expected_certificate_sha256,
            expected_verifier_sha256=args.expected_verifier_sha256,
            expected_rules_sha256=args.expected_rules_sha256,
        )
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result["ok"] else 1
    except (OSError, sqlite3.Error, ValueError, AssertionError) as error:
        print(json.dumps({
            "ok": False,
            "status": "operational-error",
            "error": str(error),
        }, indent=2, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
