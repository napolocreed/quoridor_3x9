#!/usr/bin/env python3
"""Differentially check bounded proof semantics against the independent Python engine."""
from __future__ import annotations
import argparse, random, subprocess, sys
from collections import deque
from functools import lru_cache
from pathlib import Path
from quoridor_reference import ReferenceGame, State


def reachable(game: ReferenceGame, limit: int | None = None) -> list[State]:
    root=game.initial(); seen={root}; q=deque([root]); out=[]
    while q:
        s=q.popleft(); out.append(s)
        if game.winner(s) is not None: continue
        for m in game.legal_moves(s):
            t=game.apply(s,m)
            if t not in seen:
                seen.add(t); q.append(t)
                if limit and len(seen)>=limit: return list(seen)
    return out


def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument('--solver',type=Path,default=Path('./bin/frontier_state_solve'))
    ap.add_argument('--width',type=int,default=3); ap.add_argument('--height',type=int,default=3)
    ap.add_argument('--walls',type=int,default=1); ap.add_argument('--samples',type=int,default=2000)
    ap.add_argument('--max-depth',type=int,default=9); ap.add_argument('--seed',type=int,default=72026)
    ap.add_argument('--no-bounds',action='store_true'); ap.add_argument('--no-pawn-table',action='store_true')
    ap.add_argument('--no-tt',action='store_true'); ap.add_argument('--no-symmetry',action='store_true'); ap.add_argument('--mirror-only',action='store_true')
    ap.add_argument('--defer-cycle-safe',action='store_true')
    ap.add_argument('--path-choice-weight',type=int,default=0)
    ap.add_argument('--path-flow-weight',type=int,default=0)
    ap.add_argument('--path-flow-cache-bits',type=int,default=18)
    ap.add_argument('--local-touch-refine',choices=('0','2','4','all'))
    ap.add_argument('--zero-wall-tablebase-threshold',type=int)
    ap.add_argument('--zero-wall-tablebase-max',type=int)
    ap.add_argument('--no-tt-hint-first',action='store_true')
    ap.add_argument('--no-tt-hint-transform',action='store_true')
    ap.add_argument('--tt-hint-first-mode',choices=('off','all','opponent','target','opponent-pawn','opponent-wall','order-only'))
    ap.add_argument('--transition-cache-threshold',type=int)
    ap.add_argument('--cache-reserve',type=int)
    ap.add_argument('--exhaustive-grid',action='store_true')
    args=ap.parse_args(); game=ReferenceGame(args.width,args.height,args.walls)
    states=reachable(game); rng=random.Random(args.seed)
    if args.exhaustive_grid:
        requests=[(s,target,depth) for s in states for target in range(2) for depth in range(1,args.max_depth+1)]
    else:
        requests=[]
        # Include every state at least once when the sample budget permits, then add random depths/targets.
        pool=states.copy(); rng.shuffle(pool)
        while len(requests)<args.samples:
            s=pool[len(requests)%len(pool)] if len(requests)<len(pool) else rng.choice(states)
            target=rng.randrange(2); depth=rng.randint(1,args.max_depth)
            requests.append((s,target,depth))

    @lru_cache(maxsize=None)
    def prove(s: State,target:int,depth:int)->bool:
        w=game.winner(s)
        if w is not None: return w==target
        # Same parity canonicalization as the C++ solver; logically equivalent for this objective.
        if ((s.turn==target) != (depth%2==1)): depth-=1
        if depth<=0: return False
        children=[game.apply(s,m) for m in game.legal_moves(s)]
        if not children: return False
        if s.turn==target: return any(prove(t,target,depth-1) for t in children)
        return all(prove(t,target,depth-1) for t in children)

    payload=''.join(f'{s.p1} {s.p2} {s.r1} {s.r2} {s.turn} {s.hwalls} {s.vwalls} {target} {depth}\n' for s,target,depth in requests)
    cmd=[str(args.solver.resolve()),'--width',str(args.width),'--height',str(args.height),'--walls',str(args.walls),'--tt-bits','18']
    if args.no_bounds: cmd.append('--no-bounds')
    if args.no_pawn_table: cmd.append('--no-pawn-table')
    if args.no_tt: cmd.append('--no-tt')
    if args.no_symmetry: cmd.append('--no-symmetry')
    if args.mirror_only: cmd.append('--mirror-only')
    if args.defer_cycle_safe: cmd.append('--defer-cycle-safe')
    if args.path_choice_weight: cmd += ['--path-choice-weight',str(args.path_choice_weight)]
    if args.path_flow_weight: cmd += ['--path-flow-weight',str(args.path_flow_weight),'--path-flow-cache-bits',str(args.path_flow_cache_bits)]
    if args.local_touch_refine is not None: cmd += ['--local-touch-refine',args.local_touch_refine]
    if args.zero_wall_tablebase_threshold is not None: cmd += ['--zero-wall-tablebase-threshold',str(args.zero_wall_tablebase_threshold)]
    if args.zero_wall_tablebase_max is not None: cmd += ['--zero-wall-tablebase-max',str(args.zero_wall_tablebase_max)]
    if args.no_tt_hint_first: cmd.append('--no-tt-hint-first')
    if args.no_tt_hint_transform: cmd.append('--no-tt-hint-transform')
    if args.tt_hint_first_mode is not None: cmd += ['--tt-hint-first-mode',args.tt_hint_first_mode]
    if args.transition_cache_threshold is not None: cmd += ['--transition-cache-threshold',str(args.transition_cache_threshold)]
    if args.cache_reserve is not None: cmd += ['--cache-reserve',str(args.cache_reserve)]
    cp=subprocess.run(cmd,input=payload,text=True,capture_output=True,check=False)
    if cp.returncode:
        print(cp.stderr,file=sys.stderr); return cp.returncode
    lines=cp.stdout.splitlines()
    if len(lines)!=len(requests):
        print(f'expected {len(requests)} lines got {len(lines)}',file=sys.stderr); return 1
    for i,(line,(s,target,depth)) in enumerate(zip(lines,requests)):
        parts=line.split(); got=parts[1]=='1'; expected=prove(s,target,depth)
        if got!=expected:
            print('MISMATCH',i,s,target,depth,expected,line,file=sys.stderr)
            return 1
    print({'status':'ok','requests':len(requests),'reachable_states':len(states),
           'width':args.width,'height':args.height,'walls':args.walls,
           'no_bounds':args.no_bounds,'no_pawn_table':args.no_pawn_table,'no_tt':args.no_tt,
           'no_symmetry':args.no_symmetry,'mirror_only':args.mirror_only,'exhaustive_grid':args.exhaustive_grid,
           'defer_cycle_safe':args.defer_cycle_safe,'path_choice_weight':args.path_choice_weight,
           'path_flow_weight':args.path_flow_weight,'path_flow_cache_bits':args.path_flow_cache_bits,
           'local_touch_refine':args.local_touch_refine,
           'zero_wall_tablebase_threshold':args.zero_wall_tablebase_threshold,
           'zero_wall_tablebase_max':args.zero_wall_tablebase_max,
           'no_tt_hint_first':args.no_tt_hint_first,
           'no_tt_hint_transform':args.no_tt_hint_transform,
           'tt_hint_first_mode':args.tt_hint_first_mode,
           'transition_cache_threshold':args.transition_cache_threshold,
           'cache_reserve':args.cache_reserve,
           'python_cache':prove.cache_info()._asdict()})
    return 0

if __name__=='__main__': raise SystemExit(main())
