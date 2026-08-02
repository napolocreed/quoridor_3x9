#!/usr/bin/env python3
"""Regression for the named 35-to-18 reflection partitions used by audits."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from reflection_partition import (  # noqa: E402
    bound_branch_listing_audit,
    listing_audit,
    parse_move_rows,
    partition_record,
    validate_reflection_invariant_prefix,
)


REPS = [0, 1, 3, 5, 7, 9, 11, 13, 15, 17, 19, 21, 23, 25, 27, 29, 31, 33]


def rejected(callable_) -> bool:
    try:
        callable_()
    except ValueError:
        return True
    return False


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    root_text = (root / "results/3x9_w10/reply_classes.err").read_text()
    reply_text = (root / "results/3x9_w10/branches/reply_00.err").read_text()
    root_rows = parse_move_rows(root_text, "root")
    reply_rows = parse_move_rows(reply_text, "second")
    root_partition = partition_record(root_rows, 3, REPS)
    reply_partition = partition_record(reply_rows, 3, REPS)

    assert root_partition["raw_moves"] == reply_partition["raw_moves"] == 35
    assert len(root_partition["classes"]) == len(reply_partition["classes"]) == 18
    assert root_partition["classes"][0]["move"] == "P(7,1)"
    assert root_partition["classes"][8]["move"] == "H(7,0)"
    assert root_partition["classes"][9]["move"] == "P(8,0)"
    assert reply_partition["classes"][0]["move"] == "P(1,1)"
    assert reply_partition["classes"][8]["move"] == "P(0,0)"
    assert reply_partition["classes"][-1]["move"] == "H(7,0)"

    assert rejected(lambda: partition_record(root_rows, 3, REPS[:-1]))
    duplicate = [dict(row) for row in root_rows]
    duplicate[2]["move"] = duplicate[1]["move"]
    assert rejected(lambda: partition_record(duplicate, 3, REPS))

    validate_reflection_invariant_prefix(3, ["P(7,1)"])
    assert rejected(lambda: validate_reflection_invariant_prefix(4, []))
    assert rejected(lambda: validate_reflection_invariant_prefix(3, ["P(7,0)"]))

    reply_audit = listing_audit(reply_text, "second", 3, REPS)
    forced = {
        "root": {"index": 0, "move": "P(7,1)"},
        "second": {"index": 0, "move": "P(1,1)"},
    }
    assert bound_branch_listing_audit(
        reply_text, "second", 3, REPS, reply_audit, forced
    )["forced"] == forced
    assert rejected(lambda: bound_branch_listing_audit(
        reply_text, "second", 3, REPS, reply_audit,
        {**forced, "second": {"index": 1, "move": "H(0,0)"}},
    ))
    reordered = reply_text.replace(
        "second[1] move=H(0,0)", "second[1] move=H(0,1)", 1
    ).replace(
        "second[2] move=H(0,1)", "second[2] move=H(0,0)", 1
    )
    assert rejected(lambda: bound_branch_listing_audit(
        reordered, "second", 3, REPS, reply_audit, forced
    ))

    print({
        "status": "ok",
        "root_moves": root_partition["raw_moves"],
        "reply_moves": reply_partition["raw_moves"],
        "reflection_classes": len(REPS),
        "malformed_partitions_rejected": 2,
        "unsound_reflection_prefixes_rejected": 2,
        "wrong_forced_branch_rejected": 1,
        "changed_ordering_rejected": 1,
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
