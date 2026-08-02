#!/usr/bin/env python3
"""Audit the 35 initial moves and the 18 horizontal-reflection representatives."""
from __future__ import annotations
import argparse,json,re
from pathlib import Path
MOVE_RE=re.compile(r"root\[(\d+)\] move=([PHV])\((\d+),(\d+)\)")
DEFAULT=[0,1,3,5,7,9,11,13,15,17,19,21,23,25,27,29,31,33]
def mirror(m:tuple[str,int,int],width:int)->tuple[str,int,int]:
    t,r,c=m
    return (t,r,width-1-c) if t=='P' else (t,r,(width-2)-c)
def main()->int:
    ap=argparse.ArgumentParser();ap.add_argument('--root-log',type=Path,required=True);ap.add_argument('--width',type=int,default=3)
    ap.add_argument('--representatives',default=','.join(map(str,DEFAULT)));a=ap.parse_args()
    moves={int(i):(t,int(r),int(c)) for i,t,r,c in MOVE_RE.findall(a.root_log.read_text())}
    reps=[int(x) for x in a.representatives.split(',') if x.strip()]
    assert sorted(moves)==list(range(35)),sorted(moves)
    unseen=set(moves);classes=[]
    for rep in reps:
        assert rep in unseen,(rep,'not unseen')
        mate=next(i for i,m in moves.items() if m==mirror(moves[rep],a.width))
        aliases=sorted({rep,mate});classes.append((rep,aliases));unseen.difference_update(aliases)
    assert not unseen,sorted(unseen)
    assert len(classes)==18
    print(json.dumps({'status':'ok','raw_moves':len(moves),'classes':classes,'covered':sorted(i for _,aa in classes for i in aa)}))
    return 0
if __name__=='__main__':raise SystemExit(main())
