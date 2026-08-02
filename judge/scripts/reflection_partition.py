"""Parse and validate move listings modulo horizontal reflection."""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any


MOVE_RE = re.compile(
    r"^(?P<level>root|second)\[(?P<index>\d+)\] "
    r"move=(?P<move>[PHV]\(\d+,\d+\)) score=(?P<score>-?\d+)\s*$",
    re.MULTILINE,
)
FORCE_RE = re.compile(
    r"^forcing (?P<level>root|second)\[(?P<index>\d+)\] "
    r"move=(?P<move>[PHV]\(\d+,\d+\))\s*$",
    re.MULTILINE,
)
LABEL_RE = re.compile(r"^(?P<kind>[PHV])\((?P<row>\d+),(?P<column>\d+)\)$")


def json_digest(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def parse_move_rows(text: str, level: str) -> list[dict[str, Any]]:
    matches = [match for match in MOVE_RE.finditer(text) if match.group("level") == level]
    rows = [
        {
            "index": int(match.group("index")),
            "move": match.group("move"),
            "score": int(match.group("score")),
        }
        for match in matches
    ]
    if not rows:
        raise ValueError(f"no {level} move listing found")
    indices = [row["index"] for row in rows]
    if indices != list(range(len(rows))):
        raise ValueError(f"{level} move indices are duplicated, missing or out of order: {indices}")
    if len({row["move"] for row in rows}) != len(rows):
        raise ValueError(f"{level} move labels are not unique")
    return rows


def parse_forced_moves(text: str) -> dict[str, dict[str, Any]]:
    forced: dict[str, dict[str, Any]] = {}
    for match in FORCE_RE.finditer(text):
        level = match.group("level")
        if level in forced:
            raise ValueError(f"duplicate forced {level} line")
        forced[level] = {"index": int(match.group("index")), "move": match.group("move")}
    return forced


def mirror_label(label: str, width: int) -> str:
    match = LABEL_RE.fullmatch(label)
    if match is None or width < 2:
        raise ValueError(f"invalid move label or width: {label!r}, width={width}")
    kind = match.group("kind")
    row = int(match.group("row"))
    column = int(match.group("column"))
    mirrored_column = width - 1 - column if kind == "P" else width - 2 - column
    if mirrored_column < 0:
        raise ValueError(f"move label is outside the reflected board: {label!r}")
    return f"{kind}({row},{mirrored_column})"


def validate_reflection_invariant_prefix(width: int, moves: list[str]) -> None:
    """Require the current position to be fixed by horizontal reflection.

    The standard initial position is reflection-invariant only on odd-width
    boards.  After forcing moves, every forced move must itself be fixed by the
    reflection; otherwise pairing the following children by mirrored labels is
    not a valid state-space reduction.
    """
    if type(width) is not int or width < 2 or width % 2 == 0:
        raise ValueError("horizontal-reflection reduction requires an odd board width")
    for move in moves:
        if mirror_label(move, width) != move:
            raise ValueError(
                f"forced prefix is not horizontal-reflection invariant: {move}"
            )


def reflection_classes(
    rows: list[dict[str, Any]],
    width: int,
    representatives: list[int],
) -> list[dict[str, Any]]:
    if not representatives or len(representatives) != len(set(representatives)):
        raise ValueError("reflection representatives must be non-empty and unique")
    if [row.get("index") for row in rows] != list(range(len(rows))):
        raise ValueError("move rows must have contiguous indices")
    labels = [row.get("move") for row in rows]
    if not all(isinstance(label, str) for label in labels) or len(set(labels)) != len(labels):
        raise ValueError("move rows must have unique string labels")
    by_label = {label: index for index, label in enumerate(labels)}
    unseen = set(range(len(rows)))
    classes: list[dict[str, Any]] = []
    for representative in representatives:
        if type(representative) is not int or representative not in unseen:
            raise ValueError(f"representative {representative!r} is absent or already covered")
        mirror = mirror_label(labels[representative], width)
        if mirror not in by_label:
            raise ValueError(f"mirror {mirror} of {labels[representative]} is absent")
        mate = by_label[mirror]
        aliases = sorted({representative, mate})
        if not set(aliases) <= unseen:
            raise ValueError(f"reflection class {aliases} overlaps an earlier class")
        unseen.difference_update(aliases)
        classes.append({
            "representative": representative,
            "move": labels[representative],
            "aliases": aliases,
            "alias_moves": [labels[index] for index in aliases],
        })
    if unseen:
        raise ValueError(f"reflection representatives leave moves uncovered: {sorted(unseen)}")
    return classes


def partition_record(
    rows: list[dict[str, Any]],
    width: int,
    representatives: list[int],
) -> dict[str, Any]:
    classes = reflection_classes(rows, width, representatives)
    return {
        "raw_moves": len(rows),
        "classes": classes,
        "covered_indices": sorted(index for item in classes for index in item["aliases"]),
        "moves_sha256": json_digest(rows),
    }


def listing_audit(
    text: str,
    level: str,
    width: int,
    representatives: list[int],
) -> dict[str, Any]:
    rows = parse_move_rows(text, level)
    return {
        "level": level,
        "moves": rows,
        "forced": parse_forced_moves(text),
        "partition": partition_record(rows, width, representatives),
    }


def listing_audit_valid(
    audit: object,
    level: str,
    width: int,
    representatives: list[int],
) -> bool:
    if not isinstance(audit, dict) or audit.get("level") != level:
        return False
    rows = audit.get("moves")
    if not isinstance(rows, list) or not isinstance(audit.get("forced"), dict):
        return False
    try:
        expected = partition_record(rows, width, representatives)
    except (TypeError, ValueError):
        return False
    return audit.get("partition") == expected


def bound_branch_listing_audit(
    text: str,
    level: str,
    width: int,
    representatives: list[int],
    expected_audit: object,
    expected_forced: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Bind one numeric branch invocation back to its named preflight listing."""
    if not listing_audit_valid(expected_audit, level, width, representatives):
        raise ValueError("invalid expected move-partition audit")
    assert isinstance(expected_audit, dict)  # narrowed by listing_audit_valid
    actual = listing_audit(text, level, width, representatives)
    if actual["moves"] != expected_audit["moves"]:
        raise ValueError(f"{level} move listing differs from the preflight")
    if actual["partition"] != expected_audit["partition"]:
        raise ValueError(f"{level} reflection partition differs from the preflight")
    if actual["forced"] != expected_forced:
        raise ValueError(
            f"forced branch identity differs: expected {expected_forced}, "
            f"got {actual['forced']}"
        )
    return actual
