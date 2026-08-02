#!/usr/bin/env python3
"""Summarize portfolio-worker JSON records as CSV and aggregate JSON."""
from __future__ import annotations
import argparse,csv,hashlib,json,statistics
from collections import Counter
from pathlib import Path
from solver_output import COUNTER_OK, stalemate_counter_status
from codex_portfolio_worker import cached_winner_valid

def sha256(path:Path)->str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1<<20),b''):h.update(block)
    return h.hexdigest()

def main()->int:
    ap=argparse.ArgumentParser();ap.add_argument('directory',type=Path);ap.add_argument('--csv',type=Path);args=ap.parse_args()
    rows=[]
    for p in sorted(args.directory.glob('*.json')):
        if p.name in {'campaign.json','summary.json','portfolio_aggregate.json'}:continue
        try:
            with p.open() as handle:d=json.load(handle)
        except json.JSONDecodeError:continue
        if not isinstance(d,dict):continue
        wr=d.get('winner_result') or {}
        valid=d.get('status')=='completed' and cached_winner_valid(d)
        rows.append({'id':d.get('id'),'status':'completed' if valid else 'invalid','policy':d.get('winner_policy',d.get('winner_weight')),'elapsed':d.get('elapsed_wall_seconds'),'nodes':wr.get('nodes'),'solved':wr.get('solved'),'winner':wr.get('winner'),'depth':wr.get('depth'),'stalemates_seen':wr.get('stalemates_seen'),'stalemate_counter_status':stalemate_counter_status(wr),'solver_sha256':d.get('solver_sha256'),'worker_sha256':d.get('worker_sha256'),'parser_sha256':d.get('parser_sha256'),'worker_bundle_sha256':d.get('worker_bundle_sha256'),'path':str(p)})
    counts=Counter(str(r['policy']) for r in rows if r['status']=='completed')
    completed=[r for r in rows if r['status']=='completed']
    hashes={r['solver_sha256'] for r in completed if r['solver_sha256']}
    hashes_ok=bool(completed) and len(hashes)==1 and all(r['solver_sha256'] for r in completed)
    worker_hashes={r['worker_sha256'] for r in completed if r['worker_sha256']}
    worker_hashes_ok=bool(completed) and len(worker_hashes)==1 and all(r['worker_sha256'] for r in completed)
    parser_hashes={r['parser_sha256'] for r in completed if r['parser_sha256']}
    parser_hashes_ok=bool(completed) and len(parser_hashes)==1 and all(r['parser_sha256'] for r in completed)
    bundle_hashes={r['worker_bundle_sha256'] for r in completed if r['worker_bundle_sha256']}
    bundle_hashes_ok=bool(completed) and len(bundle_hashes)==1 and all(r['worker_bundle_sha256'] for r in completed)
    try:
        campaign=json.loads((args.directory/'campaign.json').read_text())
    except (OSError,json.JSONDecodeError):
        campaign=None
    campaign_ok=(isinstance(campaign,dict) and len(hashes)==1 and campaign.get('solver_sha256') in hashes
                 and len(bundle_hashes)==1 and campaign.get('worker_bundle_sha256') in bundle_hashes
                 and isinstance(campaign.get('manifest_sha256'),str)
                 and isinstance(campaign.get('task_universe_sha256'),str))
    counters_ok=bool(completed) and all(r['stalemate_counter_status']==COUNTER_OK for r in completed)
    summary={'records':len(rows),'completed':len(completed),'failed':len(rows)-len(completed),'winner_policies':dict(counts),'solver_hashes_complete_and_unique':hashes_ok,'worker_hashes_complete_and_unique':worker_hashes_ok,'parser_hashes_complete_and_unique':parser_hashes_ok,'worker_bundle_hashes_complete_and_unique':bundle_hashes_ok,'campaign_identity_present_and_matching':campaign_ok,'stalemate_counters_complete_and_zero':counters_ok,'summarizer_sha256':sha256(Path(__file__).resolve()),'total_elapsed':sum(float(r['elapsed'] or 0) for r in rows),'median_elapsed':statistics.median([float(r['elapsed']) for r in completed]) if completed else None}
    print(json.dumps(summary,indent=2,sort_keys=True))
    target=args.csv or args.directory/'portfolio_summary.csv'
    with target.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]) if rows else ['id']);w.writeheader();w.writerows(rows)
    (args.directory/'portfolio_aggregate.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n')
    return 0 if rows and summary['failed']==0 and counters_ok and hashes_ok and worker_hashes_ok and parser_hashes_ok and bundle_hashes_ok and campaign_ok else 3
if __name__=='__main__':raise SystemExit(main())
