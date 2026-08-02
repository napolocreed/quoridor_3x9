#!/usr/bin/env python3
"""Aggregate atomic per-reply JSON records from a verification directory."""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
from typing import Any, Mapping
from build_final_manifest import HISTORICAL_NO_COUNTER_SOLVERS
from solver_output import COUNTER_MISSING, COUNTER_OK, SEMANTIC_VIOLATION, flat_metrics, normalize_legacy, parse_solver_output, stalemate_counter_status

DEFAULT_REPS_3X9=[0,1,3,5,7,9,11,13,15,17,19,21,23,25,27,29,31,33]

def sha(path:Path)->str:
    h=hashlib.sha256();
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''):h.update(b)
    return h.hexdigest()

def exact_zero(value:Any)->bool:
    return isinstance(value,int) and not isinstance(value,bool) and value==0

def raw_result(record:Mapping[str,Any])->dict[str,Any]:
    if 'parsed' in record:
        raw=record.get('parsed')
        return normalize_legacy(raw if isinstance(raw,Mapping) else None)
    stdout=record.get('stdout')
    return normalize_legacy(parse_solver_output(stdout) if isinstance(stdout,str) else None)

def parsed_record(path:Path)->dict:
    d=json.loads(path.read_text())
    if not isinstance(d,dict):raise ValueError(f'{path}: record root must be an object')
    stdout_path=path.with_suffix('.out');stderr_path=path.with_suffix('.err')
    try:stdout=stdout_path.read_text();stderr=stderr_path.read_text()
    except OSError as error:raise ValueError(f'{path}: missing raw output sidecar ({error})') from error
    if 'stdout' in d and d.get('stdout')!=stdout:raise ValueError(f'{path}: embedded stdout differs from {stdout_path}')
    if 'stderr' in d and d.get('stderr')!=stderr:raise ValueError(f'{path}: embedded stderr differs from {stderr_path}')
    p=normalize_legacy(parse_solver_output(stdout))
    if not p:raise ValueError(f'{stdout_path}: no solver result line')
    if flat_metrics(p)!=flat_metrics(raw_result(d)):raise ValueError(f'{path}: cached parsed result differs from raw stdout')
    representative=d.get('representative')
    representative_valid=isinstance(representative,int) and not isinstance(representative,bool)
    proved=(representative_valid and exact_zero(d.get('returncode')) and d.get('external_timeout') is False
            and p.get('solved')==1 and p.get('winner')==1 and p.get('timeout')==0
            and isinstance(p.get('depth'),int) and not isinstance(p.get('depth'),bool)
            and isinstance(p.get('nodes'),int) and not isinstance(p.get('nodes'),bool))
    status='proved' if proved else 'unresolved'
    counter_status=stalemate_counter_status(p);raw_counter=p.get('stalemates_seen')
    counter_value=0 if counter_status==COUNTER_OK else raw_counter
    return {'representative':representative if representative_valid else int(path.stem.split('_')[-1]), 'status':status,
            'depth':int(p['depth']) if p.get('depth') else None,
            'nodes':int(p['nodes']) if p.get('nodes') else None,
            'tt_hits':int(p['tt_hits']) if p.get('tt_hits') else None,
            'cutoffs':int(p['cutoffs']) if p.get('cutoffs') else None,
            'pawn_table_hits':int(p['pawn_table_hits']) if p.get('pawn_table_hits') is not None else None,
            'stalemates_seen':counter_value,
            'stalemate_counter_status':counter_status,
            'seconds':float(p['seconds']) if p.get('seconds') else None,
            'solver_sha256':d.get('solver_sha256')}

def main()->int:
    ap=argparse.ArgumentParser();ap.add_argument('directory',type=Path);ap.add_argument('--output',type=Path)
    ap.add_argument('--expected-records',type=int,default=18)
    ap.add_argument('--expected-reps',default=','.join(map(str,DEFAULT_REPS_3X9)))
    ap.add_argument('--counter-policy',choices=('required','historical-missing'),default='required')
    args=ap.parse_args()
    if args.expected_records<=0:ap.error('--expected-records must be positive')
    expected=[int(value) for value in args.expected_reps.split(',') if value.strip()]
    if len(expected)!=args.expected_records or len(set(expected))!=len(expected):
        ap.error('--expected-reps must contain exactly --expected-records unique values')
    files=sorted(args.directory.glob('reply_*.json')); rows=[parsed_record(p) for p in files]
    proved=[r for r in rows if r['status']=='proved']; unresolved=[r['representative'] for r in rows if r['status']!='proved']
    counter_missing=[r['representative'] for r in rows if r['stalemate_counter_status']==COUNTER_MISSING]
    counter_violations=[r['representative'] for r in rows if r['stalemate_counter_status']==SEMANTIC_VIOLATION]
    representatives=[r['representative'] for r in rows];unique_representatives=set(representatives)
    duplicate_representatives=sorted({rep for rep in representatives if representatives.count(rep)>1})
    missing_representatives=sorted(set(expected)-unique_representatives)
    unexpected_representatives=sorted(unique_representatives-set(expected))
    coverage_complete=(len(rows)==args.expected_records and not duplicate_representatives
                       and not missing_representatives and not unexpected_representatives)
    search_all_proved=coverage_complete and not unresolved
    hashes=sorted({r['solver_sha256'] for r in rows if r['solver_sha256']})
    hashes_complete=len(hashes)==1 and all(r['solver_sha256'] for r in rows)
    historical_hash_ok=(set(hashes)==HISTORICAL_NO_COUNTER_SOLVERS and hashes_complete)
    counters_accepted=(not counter_violations and not counter_missing) if args.counter_policy=='required' else (not counter_violations and historical_hash_ok)
    all_proved=search_all_proved and counters_accepted and hashes_complete
    max_child_depth=max((r['depth'] for r in proved if r['depth'] is not None),default=None)
    out={'directory':str(args.directory),'records':len(rows),'search_all_proved':search_all_proved,
         'coverage_complete':coverage_complete,'expected_representatives':expected,
         'duplicate_representatives':duplicate_representatives,
         'missing_representatives':missing_representatives,
         'unexpected_representatives':unexpected_representatives,
         'solver_hashes_complete_and_unique':hashes_complete,
         'all_proved':all_proved,
         'proved_representatives':[r['representative'] for r in proved],'unresolved':unresolved,
         'stalemate_counter_policy':args.counter_policy,
         'stalemate_counters_accepted':counters_accepted,
         'stalemate_counter_missing_representatives':counter_missing,
         'stalemate_counter_violation_representatives':counter_violations,
         'aggregate_nodes':sum(r['nodes'] or 0 for r in proved),'aggregate_search_seconds':sum(r['seconds'] or 0 for r in proved),
         'max_child_depth':max_child_depth,
         'upper_bound_plies_from_start':max_child_depth+2 if all_proved and max_child_depth is not None else None,
         'pawn_table_hits':sum(r['pawn_table_hits'] or 0 for r in proved),
         'stalemates_seen':0 if rows and not counter_missing and not counter_violations else None,
         'solver_sha256':hashes,'branches':rows}
    text=json.dumps(out,indent=2,sort_keys=True)+'\n'; (args.output or args.directory/'aggregate.json').write_text(text); print(text,end='')
    return 0 if out['all_proved'] else 3
if __name__=='__main__':raise SystemExit(main())
