"""Parse the solver's stable whitespace-separated key=value result line."""
from __future__ import annotations

import re
from typing import Any, Mapping

KV_RE = re.compile(r"(?P<key>[A-Za-z_][A-Za-z0-9_]*)=(?P<value>[^\s]+)")
INT_KEYS = {
    "width", "height", "walls", "solved", "winner", "depth", "nodes",
    "tt_hits", "cutoffs", "pawn_table_hits", "stalemates_seen", "timeout",
}
FLOAT_KEYS = {"seconds"}
CANONICAL_KEYS = (
    "width", "height", "walls", "solved", "winner", "depth", "nodes",
    "tt_hits", "cutoffs", "pawn_table_hits", "stalemates_seen", "seconds",
    "timeout",
)
COUNTER_OK = "counter_ok"
COUNTER_MISSING = "counter_missing"
SEMANTIC_VIOLATION = "semantic_violation"


def scalar(key: str, value: str) -> Any:
    if key in INT_KEYS:
        try:
            return int(value)
        except ValueError:
            return value
    if key in FLOAT_KEYS:
        try:
            return float(value)
        except ValueError:
            return value
    try:
        return int(value)
    except ValueError:
        try:
            return float(value)
        except ValueError:
            return value


def parse_key_value_line(line: str) -> dict[str, Any]:
    """Parse one whitespace-separated key=value line into typed values."""
    pairs = {m.group("key"): scalar(m.group("key"), m.group("value")) for m in KV_RE.finditer(line)}
    if pairs:
        pairs["_line"] = line
    return pairs


def parse_solver_output(text: str) -> dict[str, Any] | None:
    """Return the last result-like line as typed values."""
    for line in reversed(text.splitlines()):
        pairs = parse_key_value_line(line)
        if "nodes" in pairs and "timeout" in pairs:
            return pairs
    return None


def normalize_legacy(parsed: Mapping[str, Any] | None) -> dict[str, Any]:
    """Normalize old regex dictionaries whose values were strings and pawn was aliased."""
    if not parsed:
        return {}
    out: dict[str, Any] = {}
    for key, value in parsed.items():
        canonical = "pawn_table_hits" if key == "pawn" else key
        if value is None or value == "":
            continue
        out[canonical] = scalar(canonical, str(value))
    return out


def flat_metrics(parsed: Mapping[str, Any] | None) -> dict[str, Any]:
    p = normalize_legacy(parsed)
    return {key: p[key] for key in CANONICAL_KEYS if key in p}


def stalemate_counter_status(parsed: Mapping[str, Any] | None) -> str:
    """Classify the audit counter without ever treating absence as zero."""
    p = normalize_legacy(parsed)
    if "stalemates_seen" not in p:
        return COUNTER_MISSING
    value = p["stalemates_seen"]
    if isinstance(value, bool) or not isinstance(value, int):
        return SEMANTIC_VIOLATION
    return COUNTER_OK if value == 0 else SEMANTIC_VIOLATION


def stalemate_counter_ok(parsed: Mapping[str, Any] | None) -> bool:
    return stalemate_counter_status(parsed) == COUNTER_OK


def record_stalemate_counter_status(record: Mapping[str, Any], parsed_key: str = "parsed") -> str:
    """Recompute a cached record's status from its raw parsed payload when present."""
    if parsed_key in record:
        parsed = record.get(parsed_key)
        return stalemate_counter_status(parsed if isinstance(parsed, Mapping) else None)
    return stalemate_counter_status(record)


def aggregate_stalemate_counter_status(records: list[Mapping[str, Any]]) -> str:
    """Require at least one result row and classify all counters conservatively."""
    if not records:
        return COUNTER_MISSING
    statuses = [stalemate_counter_status(record) for record in records]
    if SEMANTIC_VIOLATION in statuses:
        return SEMANTIC_VIOLATION
    if COUNTER_MISSING in statuses:
        return COUNTER_MISSING
    return COUNTER_OK
