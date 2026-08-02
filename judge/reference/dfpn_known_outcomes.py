#!/usr/bin/env python3
"""Small exact checks for the experimental bounded DF-PN solver."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

CASES = [
    # width, height, walls, target, winning depth, prior failing depth
    (3, 3, 0, 2, 4, 2),
    (3, 3, 1, 2, 8, 6),
    (4, 3, 3, 1, 13, 11),
    (3, 5, 3, 1, 19, 17),
    (3, 5, 4, 2, 22, 20),
]


def parse_line(text: str) -> dict[str, str]:
    line = next((line for line in reversed(text.splitlines()) if line.startswith("solved=")), "")
    if not line:
        raise RuntimeError(f"missing solver output: {text[-500:]}")
    return dict(token.split("=", 1) for token in line.split() if "=" in token)


def run(solver: Path, case: tuple[int, ...], depth: int, extra: list[str]) -> dict[str, str]:
    width, height, walls, target, *_ = case
    command = [
        str(solver), "--width", str(width), "--height", str(height),
        "--walls", str(walls), "--target", str(target), "--depth", str(depth),
        "--seconds", "30", "--reserve-nodes", "500000", "--max-nodes", "5000000",
        "--transition-cache-threshold", "1", *extra,
    ]
    completed = subprocess.run(command, text=True, capture_output=True, check=False, timeout=40)
    parsed = parse_line(completed.stdout)
    parsed["returncode"] = str(completed.returncode)
    return parsed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--solver", type=Path, default=Path("./bin/lazy_dfpn_solver"))
    parser.add_argument("--rank-priors", action="store_true")
    parser.add_argument("--incremental-cycle-safe", action="store_true")
    args = parser.parse_args()
    extra: list[str] = []
    if args.rank_priors:
        extra.append("--rank-priors")
    if args.incremental_cycle_safe:
        extra.append("--incremental-cycle-safe")

    results = []
    for case in CASES:
        width, height, walls, target, win_depth, fail_depth = case
        winning = run(args.solver, case, win_depth, extra)
        failing = run(args.solver, case, fail_depth, extra)
        ok = (
            winning.get("solved") == "1" and winning.get("value") == "1"
            and failing.get("solved") == "1" and failing.get("value") == "0"
            and winning.get("stalemates_seen") == "0" and failing.get("stalemates_seen") == "0"
        )
        results.append({
            "variant": f"{width}x{height}x{walls}", "target": target,
            "winning_depth": win_depth, "failing_depth": fail_depth,
            "winning": winning, "failing": failing, "ok": ok,
        })
    status = "ok" if all(item["ok"] for item in results) else "failed"
    print(json.dumps({"status": status, "extra": extra, "cases": results}, sort_keys=True))
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
