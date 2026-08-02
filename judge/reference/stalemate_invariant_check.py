#!/usr/bin/env python3
"""Exhaustively test the no-stalemate invariant on small board configurations.

The mathematical argument lives in docs/PROOF_SEMANTICS.md. This script is not
its proof; it is a regression test over every structurally legal wall mask up to
the requested cap and every path-legal placement of two distinct pawns.
"""
from __future__ import annotations

import argparse
from dataclasses import replace

from quoridor_reference import P1, P2, ReferenceGame, State


def structural_configs(game: ReferenceGame, cap: int):
    """Yield each non-overlapping/crossing wall configuration once."""
    walls = [(ori, r, c) for ori in (0, 1) for r in range(game.R) for c in range(game.C)]

    def rec(start: int, placed: int, hw: int, vw: int):
        yield hw, vw
        if placed >= cap:
            return
        for i in range(start, len(walls)):
            ori, r, c = walls[i]
            if not game.wall_geometrically_legal(ori, r, c, hw, vw):
                continue
            bit = game.wbit(r, c)
            nhw = hw | bit if ori == 0 else hw
            nvw = vw | bit if ori == 1 else vw
            yield from rec(i + 1, placed + 1, nhw, nvw)

    yield from rec(0, 0, 0, 0)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--width", type=int, default=4)
    ap.add_argument("--height", type=int, default=3)
    ap.add_argument("--walls", type=int, default=3, help="walls per player")
    ap.add_argument("--cap", type=int, default=None, help="maximum total placed walls")
    args = ap.parse_args()

    game = ReferenceGame(args.width, args.height, args.walls)
    cap = 2 * args.walls if args.cap is None else args.cap
    checked_configs = 0
    checked_states = 0
    path_legal_states = 0
    terminal_states = 0

    for hw, vw in structural_configs(game, cap):
        checked_configs += 1
        for p1 in range(game.W * game.H):
            if not game.has_goal_path(p1, P1, hw, vw):
                continue
            for p2 in range(game.W * game.H):
                if p1 == p2 or not game.has_goal_path(p2, P2, hw, vw):
                    continue
                path_legal_states += 1
                for turn in (P1, P2):
                    checked_states += 1
                    s = State(p1, p2, args.walls, args.walls, turn, hw, vw)
                    if game.winner(s) is not None:
                        terminal_states += 1
                        continue
                    if not game.pawn_moves(s):
                        print({
                            "status": "counterexample",
                            "width": args.width,
                            "height": args.height,
                            "walls": args.walls,
                            "cap": cap,
                            "state": s,
                        })
                        return 1

    print({
        "status": "ok",
        "width": args.width,
        "height": args.height,
        "walls": args.walls,
        "cap": cap,
        "structural_configs": checked_configs,
        "path_legal_pawn_pairs": path_legal_states,
        "turn_states": checked_states,
        "terminal_turn_states": terminal_states,
        "zero_pawn_move_states": 0,
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
