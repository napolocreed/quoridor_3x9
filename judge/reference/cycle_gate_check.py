#!/usr/bin/env python3
"""Validate the topological no-cycle gate against exact path checks.

For a fixed wall configuration, contract all perimeter junctions into one
outside component. A candidate wall consists of two unit barrier edges through
three junctions. If the three junctions lie in distinct barrier components, the
wall creates no new cycle in the barrier graph. The proposed gate declares such
placements path-safe without running pawn-to-goal BFS.

This script exhaustively checks that every gate-approved candidate preserves
reachability from every previously goal-reachable cell, on small boards.
"""
from __future__ import annotations

import argparse
from collections import deque

from quoridor_reference import P1, P2, ReferenceGame
from stalemate_invariant_check import structural_configs


class DSU:
    def __init__(self, n: int):
        self.p = list(range(n))

    def find(self, x: int) -> int:
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a: int, b: int) -> None:
        a, b = self.find(a), self.find(b)
        if a != b:
            self.p[b] = a


def wall_junctions(game: ReferenceGame, orient: int, r: int, c: int) -> tuple[int, int, int]:
    jw = game.W + 1
    if orient == 0:  # H(r,c): horizontal segment on junction row r+1
        return ((r + 1) * jw + c, (r + 1) * jw + c + 1, (r + 1) * jw + c + 2)
    return (r * jw + c + 1, (r + 1) * jw + c + 1, (r + 2) * jw + c + 1)


def components(game: ReferenceGame, hw: int, vw: int) -> list[int]:
    jw, jh = game.W + 1, game.H + 1
    dsu = DSU(jw * jh)
    boundary = 0
    for r in range(jh):
        for c in range(jw):
            if r in (0, game.H) or c in (0, game.W):
                dsu.union(boundary, r * jw + c)
    for orient, mask in ((0, hw), (1, vw)):
        while mask:
            bit = mask & -mask
            z = bit.bit_length() - 1
            mask ^= bit
            r, c = divmod(z, game.C)
            a, b, d = wall_junctions(game, orient, r, c)
            dsu.union(a, b)
            dsu.union(b, d)
    return [dsu.find(i) for i in range(jw * jh)]


def reachable_cells(game: ReferenceGame, player: int, hw: int, vw: int) -> set[int]:
    goal_row = 0 if player == P1 else game.H - 1
    seen = {game.cell(goal_row, c) for c in range(game.W)}
    q = deque(seen)
    while q:
        x = q.popleft()
        for y in game.neighbors_plain(x, hw, vw):
            if y not in seen:
                seen.add(y)
                q.append(y)
    return seen


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--width", type=int, default=4)
    ap.add_argument("--height", type=int, default=3)
    ap.add_argument("--walls", type=int, default=3)
    ap.add_argument("--cap", type=int, default=None)
    args = ap.parse_args()
    game = ReferenceGame(args.width, args.height, args.walls)
    cap = 2 * args.walls if args.cap is None else args.cap

    configs = candidates = safe = fallback = 0
    for hw, vw in structural_configs(game, cap):
        configs += 1
        labels = components(game, hw, vw)
        before = [reachable_cells(game, pl, hw, vw) for pl in (P1, P2)]
        for orient in (0, 1):
            for r in range(game.R):
                for c in range(game.C):
                    if not game.wall_geometrically_legal(orient, r, c, hw, vw):
                        continue
                    candidates += 1
                    a, b, d = wall_junctions(game, orient, r, c)
                    gate_safe = len({labels[a], labels[b], labels[d]}) == 3
                    if not gate_safe:
                        fallback += 1
                        continue
                    safe += 1
                    bit = game.wbit(r, c)
                    nhw = hw | bit if orient == 0 else hw
                    nvw = vw | bit if orient == 1 else vw
                    after = [reachable_cells(game, pl, nhw, nvw) for pl in (P1, P2)]
                    for pl in (P1, P2):
                        lost = before[pl] - after[pl]
                        if lost:
                            print({
                                "status": "counterexample",
                                "width": args.width,
                                "height": args.height,
                                "walls": args.walls,
                                "cap": cap,
                                "hw": hw,
                                "vw": vw,
                                "candidate": ("H" if orient == 0 else "V", r, c),
                                "player": pl + 1,
                                "lost_cells": sorted(lost),
                            })
                            return 1

    print({
        "status": "ok",
        "width": args.width,
        "height": args.height,
        "walls": args.walls,
        "cap": cap,
        "configs": configs,
        "candidates": candidates,
        "gate_safe": safe,
        "fallback": fallback,
        "safe_fraction": safe / candidates if candidates else 0.0,
        "false_safe": 0,
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
