#!/usr/bin/env python3
"""Independently verify Quoridor reflection and 180° player-swap symmetries."""
from __future__ import annotations
import argparse, random
from collections import deque
from quoridor_reference import ReferenceGame, State


def transform_walls(game: ReferenceGame, bits: int, rotate: bool) -> int:
    out=0
    for r in range(game.R):
        for c in range(game.C):
            if bits & game.wbit(r,c):
                rr=game.R-1-r if rotate else r
                cc=game.C-1-c
                out |= game.wbit(rr,cc)
    return out


def mirror(game: ReferenceGame,s:State)->State:
    def sq(q:int)->int:
        r,c=game.rc(q); return game.cell(r,game.W-1-c)
    return State(sq(s.p1),sq(s.p2),s.r1,s.r2,s.turn,
                 transform_walls(game,s.hwalls,False),transform_walls(game,s.vwalls,False))


def rotate_swap(game: ReferenceGame,s:State)->State:
    def sq(q:int)->int:
        r,c=game.rc(q); return game.cell(game.H-1-r,game.W-1-c)
    return State(sq(s.p2),sq(s.p1),s.r2,s.r1,1-s.turn,
                 transform_walls(game,s.hwalls,True),transform_walls(game,s.vwalls,True))


def reachable(game:ReferenceGame)->list[State]:
    root=game.initial(); seen={root}; q=deque([root])
    while q:
        s=q.popleft()
        if game.winner(s) is not None: continue
        for m in game.legal_moves(s):
            t=game.apply(s,m)
            if t not in seen: seen.add(t); q.append(t)
    return list(seen)


def child_set(game:ReferenceGame,s:State)->set[State]:
    if game.winner(s) is not None: return set()
    return {game.apply(s,m) for m in game.legal_moves(s)}


def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument('--width',type=int,default=3); ap.add_argument('--height',type=int,default=3)
    ap.add_argument('--walls',type=int,default=1); ap.add_argument('--samples',type=int,default=0); ap.add_argument('--seed',type=int,default=20260727)
    args=ap.parse_args(); g=ReferenceGame(args.width,args.height,args.walls); states=reachable(g)
    if args.samples and args.samples<len(states): states=random.Random(args.seed).sample(states,args.samples)
    for i,s in enumerate(states):
        m=mirror(g,s); r=rotate_swap(g,s)
        assert mirror(g,m)==s,(i,'mirror involution',s,m)
        assert rotate_swap(g,r)==s,(i,'rotation involution',s,r)
        wm=g.winner(s); assert g.winner(m)==wm,(i,'mirror winner')
        wr=g.winner(r); assert wr==(None if wm is None else 1-wm),(i,'rotate winner',wm,wr)
        assert {mirror(g,t) for t in child_set(g,s)}==child_set(g,m),(i,'mirror children',s)
        assert {rotate_swap(g,t) for t in child_set(g,s)}==child_set(g,r),(i,'rotate children',s)
    print({'status':'ok','states_checked':len(states),'width':args.width,'height':args.height,'walls':args.walls})
    return 0

if __name__=='__main__': raise SystemExit(main())
