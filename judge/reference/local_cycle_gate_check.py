#!/usr/bin/env python3
"""Validate the allocation-free local subset of the planar-dual cycle gate.

A junction is touched when it is on the contracted perimeter or incident to an
existing wall segment. If at most one of a candidate wall's three junctions is
touched, its other junctions are distinct singleton dual components. The full
three-component gate therefore accepts it without constructing a DSU.
"""
from __future__ import annotations

import argparse
import json

from cycle_gate_check import components, reachable_cells, wall_junctions
from quoridor_reference import P1, P2, ReferenceGame
from stalemate_invariant_check import structural_configs


def incident_wall_masks(game: ReferenceGame) -> list[int]:
    count = (game.W + 1) * (game.H + 1)
    masks = [0] * count
    for orient in (0, 1):
        for r in range(game.R):
            for c in range(game.C):
                wall = orient * game.S + r * game.C + c
                for junction in wall_junctions(game, orient, r, c):
                    masks[junction] |= 1 << wall
    return masks


def boundary_junction(game: ReferenceGame, junction: int) -> bool:
    row, column = divmod(junction, game.W + 1)
    return row in (0, game.H) or column in (0, game.W)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--width", type=int, default=4)
    ap.add_argument("--height", type=int, default=3)
    ap.add_argument("--walls", type=int, default=3)
    ap.add_argument("--cap", type=int, default=None)
    args = ap.parse_args()

    game = ReferenceGame(args.width, args.height, args.walls)
    cap = 2 * args.walls if args.cap is None else args.cap
    incident = incident_wall_masks(game)
    configs = candidates = dsu_safe = local_safe = false_safe = 0

    for hw, vw in structural_configs(game, cap):
        configs += 1
        combined = hw | (vw << game.S)
        labels = components(game, hw, vw)
        before = [reachable_cells(game, player, hw, vw) for player in (P1, P2)]
        for orient in (0, 1):
            for r in range(game.R):
                for c in range(game.C):
                    if not game.wall_geometrically_legal(orient, r, c, hw, vw):
                        continue
                    candidates += 1
                    junctions = wall_junctions(game, orient, r, c)
                    full_safe = len({labels[j] for j in junctions}) == 3
                    dsu_safe += full_safe
                    touched = sum(boundary_junction(game, j) or bool(combined & incident[j]) for j in junctions)
                    if touched > 1:
                        continue
                    local_safe += 1
                    if not full_safe:
                        raise AssertionError("local gate is not a subset of the exact dual-component gate")

                    bit = game.wbit(r, c)
                    nhw = hw | bit if orient == 0 else hw
                    nvw = vw | bit if orient == 1 else vw
                    after = [reachable_cells(game, player, nhw, nvw) for player in (P1, P2)]
                    if any(before[player] - after[player] for player in (P1, P2)):
                        false_safe += 1
                        raise AssertionError(f"local gate lost connectivity at {(hw, vw, orient, r, c)}")

    result = {
        "status": "ok",
        "width": game.W,
        "height": game.H,
        "walls": game.walls,
        "cap": cap,
        "configs": configs,
        "candidates": candidates,
        "dsu_safe": dsu_safe,
        "local_safe": local_safe,
        "local_fraction": local_safe / candidates if candidates else 0.0,
        "dsu_safe_captured": local_safe / dsu_safe if dsu_safe else 1.0,
        "false_safe": false_safe,
    }
    print(json.dumps(result, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
