#!/usr/bin/env python3
"""Regression for the reachable height-2 stalemate and no-action convention."""
from __future__ import annotations

from quoridor_reference import P1, P2, ReferenceGame


def main() -> int:
    game = ReferenceGame(3, 2, 1)
    state = game.initial()
    line = [("V", 0, 0), ("V", 0, 1)]
    for move in line:
        if move not in game.legal_moves(state):
            raise AssertionError(f"counterexample move unexpectedly illegal: {move}")
        state = game.apply(state, move)

    if game.winner(state) is not None:
        raise AssertionError("stalemate witness is terminal")
    if game.pawn_moves(state) or game.legal_moves(state):
        raise AssertionError("height-2 witness still has a legal action")
    if (state.p1, state.p2, state.hwalls, state.vwalls, state.turn) != (4, 1, 0, 3, P1):
        raise AssertionError(f"unexpected witness encoding: {state}")
    if not game.has_goal_path(state.p1, P1, state.hwalls, state.vwalls):
        raise AssertionError("Player 1 path invariant lost")
    if not game.has_goal_path(state.p2, P2, state.hwalls, state.vwalls):
        raise AssertionError("Player 2 path invariant lost")

    for target in (P1, P2):
        solved, depth, _ = game.minimal_proof(target, 6, root=state)
        if solved or depth is not None:
            raise AssertionError(f"no-action state proved for target {target}")

    print({
        "status": "ok",
        "variant": "3x2x1",
        "line": ["V(0,0)", "V(0,1)"],
        "state": state,
        "both_targets_false": True,
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
