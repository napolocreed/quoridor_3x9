#!/usr/bin/env python3
"""Regression for historical-vs-current stalemate evidence in final manifests."""
from __future__ import annotations

from copy import deepcopy
import tempfile
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from build_final_manifest import (  # noqa: E402
    EXPECTED_REPS_3X9,
    HISTORICAL_NO_COUNTER_SOLVERS,
    artifact_inventory,
    counter_acceptance,
    partition_binding,
    raw_branch_evidence,
)
from reflection_partition import json_digest, listing_audit  # noqa: E402


def synthetic_listing(level: str) -> str:
    """Return a complete width-3 listing with one singleton and 17 mirror pairs."""
    labels = ["P(4,1)"]
    labels.extend(label for row in range(9) for label in (f"P({row},0)", f"P({row},2)"))
    labels.extend(label for row in range(8) for label in (f"H({row},0)", f"H({row},1)"))
    assert len(labels) == 35
    lines = []
    if level == "second":
        lines.append("forcing root[0] move=P(7,1)")
    lines.extend(
        f"{level}[{index}] move={move} score={100 - index}"
        for index, move in enumerate(labels)
    )
    return "\n".join(lines) + "\n"


def partition_record(level: str, solver_hash: str) -> dict:
    text = synthetic_listing(level)
    audit = listing_audit(text, level, 3, EXPECTED_REPS_3X9)
    tail = (
        ["--width", "3", "--height", "9", "--walls", "10", "--root-index", "0",
         "--target", "1", "--list-second", "--order", "1"]
        if level == "second"
        else ["--width", "3", "--height", "9", "--walls", "10", "--target", "1",
              "--list-root", "--order", "1"]
    )
    return {
        "schema_version": 1,
        "returncode": 0,
        "command": ["synthetic-solver", *tail],
        "solver_sha256": solver_hash,
        "stdout": "",
        "stderr": text,
        "audit": audit,
        "partition_sha256": json_digest(audit["partition"]),
    }


def partition_rejected(summary: dict, level: str, solver_hash: str) -> bool:
    classes, errors = partition_binding(summary, level, 3, solver_hash)
    return classes is None and errors == [f"{level} named reflection partition is invalid or stale"]


def main() -> int:
    historical_hash = next(iter(HISTORICAL_NO_COUNTER_SOLVERS))
    historical = {"solver_sha256": historical_hash, "branches": [{"solver_sha256": historical_hash}]}
    assert counter_acceptance(historical, historical_hash) == "historical_hash_whitelist_missing_counter"

    violation = {"solver_sha256": historical_hash, "aggregate_stalemates_seen": 1}
    assert counter_acceptance(violation, historical_hash) == "rejected_semantic_violation"

    unrecognized = {"solver_sha256": "b" * 64}
    assert counter_acceptance(unrecognized, "b" * 64) == "rejected_not_recorded"

    current = {"solver_sha256": "c" * 64, "aggregate_stalemates_seen": 0}
    assert counter_acceptance(current, "c" * 64) == "recorded_zero"

    forged_hash = {"solver_sha256": "b" * 64, "aggregate_stalemates_seen": 0}
    assert counter_acceptance(forged_hash, "c" * 64) == "rejected_solver_hash_mismatch"

    mixed_hashes = {
        "solver_sha256": historical_hash,
        "branches": [{"solver_sha256": "d" * 64}],
    }
    assert counter_acceptance(mixed_hashes, historical_hash) == "rejected_solver_hash_mismatch"

    for false_zero in (False, 0.0, 0.5):
        malformed = {"solver_sha256": "c" * 64, "aggregate_stalemates_seen": false_zero}
        assert counter_acceptance(malformed, "c" * 64) == "rejected_invalid"

    partition_hash = "e" * 64
    valid_partitions = {}
    for level in ("second", "root"):
        record = partition_record(level, partition_hash)
        summary = {"move_partition": record, "aggregate_stalemates_seen": 0}
        classes, errors = partition_binding(summary, level, 3, partition_hash)
        assert errors == []
        assert classes is not None and list(classes) == EXPECTED_REPS_3X9
        assert sum(len(row["aliases"]) for row in classes.values()) == 35
        valid_partitions[level] = summary

    corruptions = []

    raw = deepcopy(valid_partitions["second"])
    raw["move_partition"]["stderr"] = raw["move_partition"]["stderr"].replace(
        "score=100", "score=999", 1
    )
    corruptions.append((raw, "second"))

    command = deepcopy(valid_partitions["second"])
    command["move_partition"]["command"][-1] = "0"
    corruptions.append((command, "second"))

    solver = deepcopy(valid_partitions["second"])
    solver["move_partition"]["solver_sha256"] = "f" * 64
    corruptions.append((solver, "second"))

    digest = deepcopy(valid_partitions["second"])
    digest["move_partition"]["partition_sha256"] = "0" * 64
    corruptions.append((digest, "second"))

    malformed_none = deepcopy(valid_partitions["second"])
    malformed_none["move_partition"]["audit"] = None
    corruptions.append((malformed_none, "second"))

    malformed_partial = deepcopy(valid_partitions["root"])
    malformed_partial["move_partition"]["audit"] = {"level": "root"}
    corruptions.append((malformed_partial, "root"))

    bool_returncode = deepcopy(valid_partitions["root"])
    bool_returncode["move_partition"]["returncode"] = False
    corruptions.append((bool_returncode, "root"))

    bool_schema = deepcopy(valid_partitions["root"])
    bool_schema["move_partition"]["schema_version"] = True
    corruptions.append((bool_schema, "root"))

    assert all(partition_rejected(summary, level, partition_hash) for summary, level in corruptions)

    # Archived audits keep stdout/stderr beside each JSON record. The manifest
    # builder must reparse both, including the actual forced move selected by
    # the indexed invocation, rather than trusting the cached parsed fields.
    with tempfile.TemporaryDirectory() as directory:
        tmp = Path(directory)
        stem = tmp / "reply_00"
        stdout = (
            "width=3 height=9 walls=10 solved=1 winner=1 depth=33 nodes=1 "
            "tt_hits=0 cutoffs=0 pawn_table_hits=0 seconds=0.1 timeout=0\n"
        )
        stderr = synthetic_listing("second") + "forcing second[0] move=P(4,1)\n"
        stem.with_suffix(".out").write_text(stdout)
        stem.with_suffix(".err").write_text(stderr)
        record = {
            "parsed": {
                "width": "3", "height": "9", "walls": "10", "solved": "1",
                "winner": "1", "depth": "33", "nodes": "1", "tt_hits": "0",
                "cutoffs": "0", "pawn_table_hits": "0", "seconds": "0.1",
                "timeout": "0",
            }
        }
        parsed, raw_errors, audit = raw_branch_evidence(record, stem, "second", 0, None)
        assert raw_errors == [] and parsed["nodes"] == 1 and audit is not None

        stem.with_suffix(".out").write_text(stdout.replace("nodes=1", "nodes=2"))
        _, raw_errors, _ = raw_branch_evidence(record, stem, "second", 0, None)
        assert any("disagrees with JSON" in error for error in raw_errors)

        stem.with_suffix(".out").write_text(stdout)
        stem.with_suffix(".err").write_text(stderr.replace(
            "forcing second[0] move=P(4,1)", "forcing second[0] move=P(0,0)"
        ))
        _, raw_errors, _ = raw_branch_evidence(record, stem, "second", 0, None)
        assert any("forcing lines" in error for error in raw_errors)

        inventory, inventory_errors = artifact_inventory(
            [stem.with_suffix(".out"), stem.with_suffix(".err")], tmp,
        )
        assert inventory_errors == [] and [row["path"] for row in inventory] == [
            "reply_00.out", "reply_00.err",
        ]
        original_digest = json_digest(inventory)
        stem.with_suffix(".out").write_text(stdout + "\n")
        changed, changed_errors = artifact_inventory(
            [stem.with_suffix(".out"), stem.with_suffix(".err")], tmp,
        )
        assert changed_errors == [] and json_digest(changed) != original_digest

    print({
        "status": "ok",
        "manifest_counter_cases": 9,
        "valid_named_partitions": 2,
        "partition_moves": 35,
        "partition_classes": 18,
        "partition_corruptions_rejected": len(corruptions),
        "raw_branch_corruptions_rejected": 2,
        "artifact_inventory_mutation_detected": True,
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
