#!/usr/bin/env python3
"""Audit the 35-to-18 reply-class partition without using C++ canonical keys."""
from __future__ import annotations
import argparse, json, re
from pathlib import Path

MOVE_RE = re.compile(r"second\[(\d+)\] move=([PHV])\((\d+),(\d+)\)")
CLASS_RE = re.compile(r"child_rep=(\d+) aliases=([0-9,]+)")

def mirror(move: tuple[str,int,int], width: int) -> tuple[str,int,int]:
    typ,r,c=move
    if typ=='P':
        return typ,r,width-1-c
    # Wall anchors have width-1 columns. Reflection maps c -> (width-2)-c.
    return typ,r,(width-2)-c

def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument('--branch-stderr',type=Path,required=True)
    ap.add_argument('--class-log',type=Path,required=True)
    ap.add_argument('--width',type=int,default=3)
    args=ap.parse_args()

    moves={int(i):(typ,int(r),int(c)) for i,typ,r,c in MOVE_RE.findall(args.branch_stderr.read_text())}
    classes=[]
    for rep,aliases in CLASS_RE.findall(args.class_log.read_text()):
        classes.append((int(rep),[int(x) for x in aliases.split(',')]))
    covered=sorted(i for _,aa in classes for i in aa)
    assert covered==list(range(35)),covered
    assert len(classes)==18,len(classes)
    for rep,aa in classes:
        assert rep==aa[0]
        assert len(aa) in (1,2)
        if len(aa)==1:
            assert mirror(moves[aa[0]],args.width)==moves[aa[0]],(aa,moves[aa[0]])
        else:
            assert mirror(moves[aa[0]],args.width)==moves[aa[1]],(aa,moves[aa[0]],moves[aa[1]])
            assert mirror(moves[aa[1]],args.width)==moves[aa[0]]
    print(json.dumps({'status':'ok','raw_replies':len(moves),'classes':len(classes),'covered':covered}))
    return 0

if __name__=='__main__':
    raise SystemExit(main())
