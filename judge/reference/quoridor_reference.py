#!/usr/bin/env python3
"""Small, deliberately simple Quoridor reference solver.

This is not optimized. It exists to independently validate the C++ frontier
solver on small boards. Coordinates are (row, column). Player 1 starts on the
bottom row and aims for row 0; player 2 starts on row 0 and aims for H-1.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from collections import deque
import argparse
import json
from typing import Iterable, Iterator

P1, P2 = 0, 1

@dataclass(frozen=True, slots=True)
class State:
    p1: int
    p2: int
    r1: int
    r2: int
    turn: int
    hwalls: int
    vwalls: int

class ReferenceGame:
    def __init__(self, width: int, height: int, walls: int):
        if width < 2 or height < 2:
            raise ValueError("board dimensions must be >= 2")
        self.W = width
        self.H = height
        self.C = width - 1
        self.R = height - 1
        self.S = self.C * self.R
        self.walls = walls

    def cell(self, r: int, c: int) -> int:
        return r * self.W + c

    def rc(self, q: int) -> tuple[int, int]:
        return divmod(q, self.W)

    def initial(self, p1_walls: int | None = None, p2_walls: int | None = None) -> State:
        c = self.W // 2
        return State(
            self.cell(self.H - 1, c), self.cell(0, c),
            self.walls if p1_walls is None else p1_walls,
            self.walls if p2_walls is None else p2_walls,
            P1, 0, 0,
        )

    def wbit(self, r: int, c: int) -> int:
        return 1 << (r * self.C + c)

    def blocked(self, a: int, b: int, hw: int, vw: int) -> bool:
        ra, ca = self.rc(a)
        rb, cb = self.rc(b)
        if abs(ra - rb) + abs(ca - cb) != 1:
            raise ValueError("blocked() requires adjacent cells")
        if ra != rb:  # vertical movement, blocked by horizontal wall
            r = min(ra, rb)
            # Edge at column c can be covered by H(r,c) or H(r,c-1).
            c = ca
            if c < self.C and (hw & self.wbit(r, c)):
                return True
            if c > 0 and (hw & self.wbit(r, c - 1)):
                return True
            return False
        # horizontal movement, blocked by vertical wall
        c = min(ca, cb)
        r = ra
        if r < self.R and (vw & self.wbit(r, c)):
            return True
        if r > 0 and (vw & self.wbit(r - 1, c)):
            return True
        return False

    def neighbors_plain(self, q: int, hw: int, vw: int) -> Iterator[int]:
        r, c = self.rc(q)
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nr, nc = r + dr, c + dc
            if 0 <= nr < self.H and 0 <= nc < self.W:
                nq = self.cell(nr, nc)
                if not self.blocked(q, nq, hw, vw):
                    yield nq

    def has_goal_path(self, start: int, player: int, hw: int, vw: int) -> bool:
        goal = 0 if player == P1 else self.H - 1
        seen = {start}
        dq = deque([start])
        while dq:
            q = dq.popleft()
            r, _ = self.rc(q)
            if r == goal:
                return True
            for nq in self.neighbors_plain(q, hw, vw):
                if nq not in seen:
                    seen.add(nq)
                    dq.append(nq)
        return False

    def pawn_moves(self, s: State) -> list[int]:
        me = s.p1 if s.turn == P1 else s.p2
        opp = s.p2 if s.turn == P1 else s.p1
        rm, cm = self.rc(me)
        ro, co = self.rc(opp)
        out: list[int] = []
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nr, nc = rm + dr, cm + dc
            if not (0 <= nr < self.H and 0 <= nc < self.W):
                continue
            adj = self.cell(nr, nc)
            if self.blocked(me, adj, s.hwalls, s.vwalls):
                continue
            if adj != opp:
                out.append(adj)
                continue
            # Opponent is adjacent. Jump straight if possible.
            jr, jc = ro + dr, co + dc
            if 0 <= jr < self.H and 0 <= jc < self.W:
                jump = self.cell(jr, jc)
                if not self.blocked(opp, jump, s.hwalls, s.vwalls):
                    out.append(jump)
                    continue
            # Otherwise move diagonally around the opponent.
            for pdr, pdc in ((-dc, -dr), (dc, dr)):
                sr, sc = ro + pdr, co + pdc
                if 0 <= sr < self.H and 0 <= sc < self.W:
                    side = self.cell(sr, sc)
                    if not self.blocked(opp, side, s.hwalls, s.vwalls):
                        out.append(side)
        return sorted(set(out))

    def wall_geometrically_legal(self, orient: int, r: int, c: int, hw: int, vw: int) -> bool:
        bit = self.wbit(r, c)
        if orient == 0:  # horizontal
            if hw & bit or vw & bit:  # same anchor or crossing
                return False
            if c > 0 and hw & self.wbit(r, c - 1):
                return False
            if c + 1 < self.C and hw & self.wbit(r, c + 1):
                return False
        else:
            if vw & bit or hw & bit:
                return False
            if r > 0 and vw & self.wbit(r - 1, c):
                return False
            if r + 1 < self.R and vw & self.wbit(r + 1, c):
                return False
        return True

    def legal_moves(self, s: State) -> list[tuple[str, int, int]]:
        result: list[tuple[str, int, int]] = [("P", q, -1) for q in self.pawn_moves(s)]
        rem = s.r1 if s.turn == P1 else s.r2
        if rem <= 0:
            return result
        for orient, label in ((0, "H"), (1, "V")):
            for r in range(self.R):
                for c in range(self.C):
                    if not self.wall_geometrically_legal(orient, r, c, s.hwalls, s.vwalls):
                        continue
                    bit = self.wbit(r, c)
                    nhw = s.hwalls | bit if orient == 0 else s.hwalls
                    nvw = s.vwalls | bit if orient == 1 else s.vwalls
                    if self.has_goal_path(s.p1, P1, nhw, nvw) and self.has_goal_path(s.p2, P2, nhw, nvw):
                        result.append((label, r, c))
        return result

    def apply(self, s: State, move: tuple[str, int, int]) -> State:
        typ, a, b = move
        p1, p2, r1, r2, hw, vw = s.p1, s.p2, s.r1, s.r2, s.hwalls, s.vwalls
        if typ == "P":
            if s.turn == P1:
                p1 = a
            else:
                p2 = a
        else:
            bit = self.wbit(a, b)
            if typ == "H":
                hw |= bit
            elif typ == "V":
                vw |= bit
            else:
                raise ValueError(move)
            if s.turn == P1:
                r1 -= 1
            else:
                r2 -= 1
        return State(p1, p2, r1, r2, 1 - s.turn, hw, vw)

    def winner(self, s: State) -> int | None:
        r1, _ = self.rc(s.p1)
        r2, _ = self.rc(s.p2)
        if r1 == 0:
            return P1
        if r2 == self.H - 1:
            return P2
        return None

    def minimal_proof(self, target: int, max_depth: int, root: State | None = None) -> tuple[bool, int | None, int]:
        nodes = 0

        @lru_cache(maxsize=None)
        def prove(s: State, depth: int) -> bool:
            nonlocal nodes
            nodes += 1
            win = self.winner(s)
            if win is not None:
                return win == target
            if depth == 0:
                return False
            moves = self.legal_moves(s)
            if not moves:
                return False
            if s.turn == target:
                return any(prove(self.apply(s, m), depth - 1) for m in moves)
            return all(prove(self.apply(s, m), depth - 1) for m in moves)

        root = self.initial() if root is None else root
        first_depth = 1 if root.turn == target else 2
        for depth in range(first_depth, max_depth + 1, 2):
            if prove(root, depth):
                return True, depth, nodes
        return False, None, nodes


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--width", type=int, default=3)
    ap.add_argument("--height", type=int, default=3)
    ap.add_argument("--walls", type=int, default=0)
    ap.add_argument("--target", type=int, choices=(1, 2), default=1)
    ap.add_argument("--max-depth", type=int, default=20)
    ap.add_argument("--dump-initial-moves", action="store_true")
    args = ap.parse_args()
    g = ReferenceGame(args.width, args.height, args.walls)
    if args.dump_initial_moves:
        print(json.dumps(g.legal_moves(g.initial())))
        return
    solved, depth, nodes = g.minimal_proof(args.target - 1, args.max_depth)
    print(json.dumps({
        "width": args.width, "height": args.height, "walls": args.walls,
        "target": args.target, "solved": solved, "depth": depth, "nodes": nodes,
    }))

if __name__ == "__main__":
    main()
