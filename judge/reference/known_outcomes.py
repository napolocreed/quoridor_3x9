#!/usr/bin/env python3
"""Regression checks against exact small-board outcomes reproduced independently/publicly."""
from __future__ import annotations
import argparse, json, re, subprocess, sys
from pathlib import Path

CASES = [
    # width, height, walls, winner, max depth
    (3, 3, 0, 2, 12),
    (4, 3, 2, 2, 24),
    (4, 3, 3, 1, 24),
    (3, 5, 3, 1, 28),
    (3, 5, 4, 2, 32),
]
PAT = re.compile(r"solved=1 winner=(\d+) depth=(\d+).*stalemates_seen=0")

def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument('--solver',type=Path,default=Path('./bin/frontier_solver'))
    args=ap.parse_args()
    solver=args.solver.resolve()
    results=[]
    for w,h,walls,winner,max_depth in CASES:
        cmd=[str(solver),'--width',str(w),'--height',str(h),'--walls',str(walls),
             '--target',str(winner),'--seconds','120','--max-depth',str(max_depth),'--tt-bits','20']
        cp=subprocess.run(cmd,text=True,capture_output=True,check=False)
        m=PAT.search(cp.stdout)
        ok=cp.returncode==0 and m is not None and int(m.group(1))==winner
        item={'width':w,'height':h,'walls':walls,'expected_winner':winner,
              'ok':ok,'stdout':cp.stdout.strip(),'returncode':cp.returncode}
        results.append(item)
        print(json.dumps(item,sort_keys=True))
        if not ok:
            print(cp.stderr,file=sys.stderr)
            return 1
    print(json.dumps({'status':'ok','cases':len(results)},sort_keys=True))
    return 0

if __name__=='__main__':
    raise SystemExit(main())
