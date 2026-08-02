#!/usr/bin/env python3
"""Regression checks for typed result parsing and mandatory audit counters."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from solver_output import (  # noqa: E402
    COUNTER_MISSING,
    COUNTER_OK,
    SEMANTIC_VIOLATION,
    aggregate_stalemate_counter_status,
    parse_key_value_line,
    parse_solver_output,
    record_stalemate_counter_status,
    stalemate_counter_status,
)


def main() -> int:
    good = parse_solver_output("width=3 solved=1 nodes=42 stalemates_seen=0 seconds=0.1 timeout=0\n")
    missing = parse_key_value_line("solved=1 nodes=42 timeout=0")
    nonzero = parse_key_value_line("solved=1 nodes=42 stalemates_seen=2 timeout=0")
    malformed = parse_key_value_line("solved=1 nodes=42 stalemates_seen=oops timeout=0")
    boolean = {"stalemates_seen": False}
    integral_float = {"stalemates_seen": 0.0}
    fractional_float = {"stalemates_seen": 0.5}

    assert good is not None and good["nodes"] == 42
    assert stalemate_counter_status(good) == COUNTER_OK
    assert stalemate_counter_status(missing) == COUNTER_MISSING
    assert stalemate_counter_status(nonzero) == SEMANTIC_VIOLATION
    assert stalemate_counter_status(malformed) == SEMANTIC_VIOLATION
    assert stalemate_counter_status(boolean) == SEMANTIC_VIOLATION
    assert stalemate_counter_status(integral_float) == SEMANTIC_VIOLATION
    assert stalemate_counter_status(fractional_float) == SEMANTIC_VIOLATION
    forged = {"parsed": missing, "stalemates_seen": 0, "stalemate_counter_status": COUNTER_OK}
    assert record_stalemate_counter_status(forged) == COUNTER_MISSING
    assert aggregate_stalemate_counter_status([]) == COUNTER_MISSING
    assert aggregate_stalemate_counter_status([good, nonzero]) == SEMANTIC_VIOLATION
    print({"status": "ok", "counter_cases": 10})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
