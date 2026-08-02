#!/usr/bin/env python3
"""Independent transfer-matrix count of geometrically legal wall configurations."""
from __future__ import annotations
import argparse,collections,itertools,json

def row_states(columns:int):
    out=[]
    for cells in itertools.product(range(3),repeat=columns): # 0 empty, 1 H, 2 V
        if any(cells[i]==cells[i+1]==1 for i in range(columns-1)):continue
        v=sum((x==2)<<i for i,x in enumerate(cells))
        out.append((v,sum(x!=0 for x in cells),cells))
    return out

def count(width:int,height:int,max_walls:int|None):
    C=width-1;R=height-1;rows=row_states(C)
    # (previous vertical mask, total walls) -> number of row sequences.
    dp={(0,0):1}
    for _ in range(R):
        nd=collections.defaultdict(int)
        for (prev,n),ways in dp.items():
            for v,k,_ in rows:
                if prev&v:continue
                nn=n+k
                if max_walls is None or nn<=max_walls:nd[(v,nn)]+=ways
        dp=nd
    hist=collections.Counter()
    for (_,n),ways in dp.items():hist[n]+=ways
    return rows,hist

def main()->int:
    ap=argparse.ArgumentParser();ap.add_argument('--width',type=int,default=3);ap.add_argument('--height',type=int,default=9)
    ap.add_argument('--walls-each',type=int,default=10);a=ap.parse_args();limit=min(2*a.walls_each,2*(a.width-1)*(a.height-1))
    rows,hist=count(a.width,a.height,limit)
    print(json.dumps({'width':a.width,'height':a.height,'walls_each':a.walls_each,'row_states':len(rows),
                      'max_total_walls':limit,'configurations':sum(hist.values()),
                      'directed_single_wall_additions':sum(k*v for k,v in hist.items()),
                      'count_by_placed_walls':dict(sorted(hist.items()))},sort_keys=True))
    return 0
if __name__=='__main__':raise SystemExit(main())
