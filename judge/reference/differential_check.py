#!/usr/bin/env python3
"""Compare legal move generation in the optimized C++ engine and simple Python reference."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

from quoridor_reference import ReferenceGame, State


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dump", type=Path, default=Path("./bin/frontier_dump"))
    ap.add_argument("--width", type=int, default=4)
    ap.add_argument("--height", type=int, default=3)
    ap.add_argument("--walls", type=int, default=3)
    ap.add_argument("--samples", type=int, default=500)
    ap.add_argument("--seed", type=int, default=12345)
    ap.add_argument("--exhaustive", action="store_true")
    ap.add_argument("--local-touch-refine", choices=("0", "2", "4", "all"))
    args = ap.parse_args()

    dump = args.dump.resolve()
    if not dump.exists():
        raise SystemExit(f"missing dump executable: {dump}")

    game = ReferenceGame(args.width, args.height, args.walls)
    cmd = [
        str(dump),
        "--width", str(args.width),
        "--height", str(args.height),
        "--walls", str(args.walls),
        "--samples", str(args.samples),
        "--seed", str(args.seed),
    ]
    if args.exhaustive:
        cmd.append("--exhaustive")
    if args.local_touch_refine is not None:
        cmd.extend(("--local-touch-refine", args.local_touch_refine))
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, text=True)
    checked = 0
    assert proc.stdout
    for line in proc.stdout:
        item = json.loads(line)
        state = State(
            item["p1"], item["p2"], item["r1"], item["r2"],
            item["turn"], item["hw"], item["vw"],
        )
        py_moves: list[str] = []
        for typ, a, b in game.legal_moves(state):
            py_moves.append(f"P:{a}" if typ == "P" else f"{typ}:{a}:{b}")
        py_moves.sort()
        cpp_moves = sorted(item["moves"])
        if py_moves != cpp_moves:
            print("MISMATCH", json.dumps(item), file=sys.stderr)
            print("PY only", sorted(set(py_moves) - set(cpp_moves)), file=sys.stderr)
            print("CPP only", sorted(set(cpp_moves) - set(py_moves)), file=sys.stderr)
            proc.kill()
            return 1
        checked += 1

    rc = proc.wait()
    if rc:
        return rc
    print(json.dumps({
        "status": "ok",
        "checked": checked,
        "width": args.width,
        "height": args.height,
        "walls": args.walls,
        "seed": args.seed,
        "dump": str(dump),
        "exhaustive": args.exhaustive,
        "local_touch_refine": args.local_touch_refine,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
