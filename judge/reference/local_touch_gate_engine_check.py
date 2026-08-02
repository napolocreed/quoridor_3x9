#!/usr/bin/env python3
"""Runtime invariants for the isolated cache-first local-touch solver."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def metrics(line: str) -> dict[str, str]:
    return {
        field.split("=", 1)[0]: field.split("=", 1)[1]
        for field in line.split()
        if "=" in field
    }


def run(solver: Path, refine: str) -> dict[str, str]:
    command = [
        str(solver.resolve()),
        "--width", "3",
        "--height", "3",
        "--walls", "1",
        "--target", "2",
        "--start-depth", "8",
        "--max-depth", "8",
        "--seconds", "30",
        "--tt-bits", "20",
        "--transition-cache-threshold", "1",
        "--local-touch-refine", refine,
    ]
    completed = subprocess.run(command, text=True, capture_output=True, check=False)
    if completed.returncode:
        raise AssertionError(
            f"K={refine} failed with {completed.returncode}: {completed.stderr}"
        )
    lines = completed.stdout.strip().splitlines()
    if len(lines) != 1:
        raise AssertionError(f"K={refine} produced {len(lines)} result lines")
    result = metrics(lines[0])
    expected = {"solved": "1", "winner": "2", "depth": "8", "nodes": "127",
                "stalemates_seen": "0", "timeout": "0", "local_touch_refine": refine}
    for key, value in expected.items():
        if result.get(key) != value:
            raise AssertionError(f"K={refine}: expected {key}={value}, got {result.get(key)!r}")
    required = (
        "local_touch_exact_hits", "local_touch_safe_misses",
        "local_touch_fallback_misses", "deferred_emitted", "deferred_replayed",
        "deferred_patched", "deferred_resolved", "deferred_resolve_hits",
        "deferred_resolve_builds", "deferred_pruned",
        "deferred_pruned_uncached", "bfs_passes_avoided", "deferred_refined",
        "refinement_order_changes",
    )
    values = {key: int(result[key]) for key in required}
    if min(values["local_touch_exact_hits"], values["local_touch_safe_misses"],
           values["local_touch_fallback_misses"], values["deferred_replayed"],
           values["deferred_patched"], values["deferred_resolve_builds"]) <= 0:
        raise AssertionError(f"K={refine}: cache-first paths were not all exercised")
    if values["deferred_resolved"] != values["deferred_resolve_hits"] + values["deferred_resolve_builds"]:
        raise AssertionError(f"K={refine}: resolve accounting does not balance")
    if values["deferred_emitted"] != values["deferred_replayed"] - values["deferred_patched"]:
        raise AssertionError(f"K={refine}: pending replay accounting does not balance")
    if values["deferred_pruned_uncached"] > values["deferred_pruned"]:
        raise AssertionError(f"K={refine}: uncached prunes exceed all prunes")
    if values["bfs_passes_avoided"] != 2 * values["deferred_pruned_uncached"]:
        raise AssertionError(f"K={refine}: avoided BFS accounting does not balance")
    if refine == "0" and values["deferred_refined"] != 0:
        raise AssertionError("K=0 refined a handle")
    if refine == "all" and values["deferred_refined"] != values["local_touch_safe_misses"]:
        raise AssertionError("K=all did not refine every initially safe miss")
    return result


def expect_rejected(solver: Path, extra: list[str], fragment: str) -> None:
    completed = subprocess.run(
        [str(solver.resolve()), "--width", "3", "--height", "3", "--walls", "1", *extra],
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 2 or fragment not in completed.stderr:
        raise AssertionError(
            f"expected rejection containing {fragment!r}, got rc={completed.returncode}: "
            f"{completed.stderr!r}"
        )


def run_scan_after_deferred_third_wall(solver: Path) -> None:
    """Regression: --scan-current must materialise a selected deferred root."""
    command = [
        str(solver.resolve()),
        "--width", "4",
        "--height", "7",
        "--walls", "7",
        "--root-move", "H(1,0)",
        "--second-move", "H(4,2)",
        "--third-move", "H(2,1)",
        "--target", "1",
        "--scan-current",
        "--scan-root-start", "0",
        "--scan-root-end", "0",
        "--child-depth", "1",
        "--seconds", "10",
        "--tt-bits", "20",
        "--transition-cache-threshold", "1",
        "--local-touch-refine", "0",
    ]
    completed = subprocess.run(command, text=True, capture_output=True, check=False)
    # scan-current uses 0/1 as semantic proof/refutation statuses; a timeout
    # (3) is not acceptable for this deterministic one-ply regression.
    if completed.returncode not in (0, 1):
        raise AssertionError(
            "scan-current after deferred third wall failed with "
            f"{completed.returncode}: {completed.stderr}"
        )
    if "current_scan task=0" not in completed.stdout:
        raise AssertionError(
            "scan-current after deferred third wall produced no task record: "
            f"{completed.stdout!r}"
        )
    if "timeout=0" not in completed.stdout:
        raise AssertionError(
            "scan-current after deferred third wall did not finish exactly: "
            f"{completed.stdout!r}"
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--solver", type=Path, default=Path("./bin/lazy_local_touch_gate_solver"))
    args = parser.parse_args()
    results = {refine: run(args.solver, refine) for refine in ("0", "2", "4", "all")}
    run_scan_after_deferred_third_wall(args.solver)
    expect_rejected(args.solver, ["--local-touch-refine", "1"], "refinement must be 0, 2, 4, or all")
    expect_rejected(args.solver, ["--defer-cycle-safe"], "incompatible with the cache-first local-touch experiment")
    print({
        "status": "ok",
        "refinements": list(results),
        "nodes": {key: int(value["nodes"]) for key, value in results.items()},
        "scan_after_deferred_third_wall": "ok",
        "invalid_modes_rejected": 2,
    })
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AssertionError, KeyError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        raise SystemExit(1)
