#!/usr/bin/env python3
"""Resumable exact lower-bound audit over first-move reflection classes.

For each representative first move, fix that move and ask whether Player 1 can
force a win within the remaining bounded horizon. A completed `solved=0,
timeout=0` search is an exact refutation of that first move at the requested
horizon when run with `--no-bounds --no-pawn-table`.
"""
from __future__ import annotations
import argparse, concurrent.futures, hashlib, json, os, shutil, subprocess, time
from pathlib import Path
from solver_output import COUNTER_OK, flat_metrics, parse_solver_output, normalize_legacy, stalemate_counter_status
from reflection_partition import (bound_branch_listing_audit, json_digest, listing_audit,
                                  listing_audit_valid, validate_reflection_invariant_prefix)

DEFAULT_REPS_3X9=[0,1,3,5,7,9,11,13,15,17,19,21,23,25,27,29,31,33]
def sha256(path:Path)->str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''): h.update(b)
    return h.hexdigest()

def partition_command(args:argparse.Namespace)->list[str]:
    return [str(args.solver),'--width',str(args.width),'--height',str(args.height),
            '--walls',str(args.walls),'--target','1','--list-root','--order',str(args.order)]

def load_root_partition(args:argparse.Namespace,outdir:Path,solver_hash:str,expected_reps:list[int])->dict:
    validate_reflection_invariant_prefix(args.width, [])
    cache=outdir/'root_partition.json';command=partition_command(args)
    if cache.exists():
        try:record=json.loads(cache.read_text())
        except json.JSONDecodeError as error:raise RuntimeError(f'malformed move-partition cache: {cache}') from error
        audit=record.get('audit') if isinstance(record,dict) else None
        raw_audit=None
        if isinstance(record,dict) and isinstance(record.get('stdout'),str) and isinstance(record.get('stderr'),str):
            try:raw_audit=listing_audit(record['stderr']+'\n'+record['stdout'],'root',args.width,expected_reps)
            except ValueError:pass
        valid=(isinstance(record,dict) and type(record.get('schema_version')) is int and record.get('schema_version')==1
               and type(record.get('returncode')) is int and record.get('returncode')==0
               and record.get('solver_sha256')==solver_hash and record.get('command')==command
               and listing_audit_valid(audit,'root',args.width,expected_reps)
               and raw_audit==audit
               and record.get('partition_sha256')==json_digest(audit.get('partition'))
               and audit.get('forced')=={})
        if not valid:raise RuntimeError(f'refusing stale or invalid move-partition cache: {cache}')
        return record
    try:completed=subprocess.run(command,text=True,capture_output=True,timeout=args.precompute_timeout,check=False)
    except subprocess.TimeoutExpired as error:raise RuntimeError('timed out while enumerating the named root partition') from error
    combined=completed.stderr+'\n'+completed.stdout
    try:audit=listing_audit(combined,'root',args.width,expected_reps)
    except ValueError as error:raise RuntimeError(f'could not validate root reflection classes: {error}') from error
    if completed.returncode!=0 or audit['forced']!={}:
        raise RuntimeError(f'root partition enumeration failed (rc={completed.returncode}, forced={audit["forced"]})')
    record={'schema_version':1,'solver_sha256':solver_hash,'command':command,
            'returncode':completed.returncode,'stdout':completed.stdout,'stderr':completed.stderr,'audit':audit,
            'partition_sha256':json_digest(audit['partition'])}
    tmp=cache.with_suffix('.json.tmp');tmp.write_text(json.dumps(record,indent=2,sort_keys=True)+'\n');os.replace(tmp,cache)
    return record

def exact_zero(value:object)->bool:
    return isinstance(value,int) and not isinstance(value,bool) and value==0

def root_branch_listing_audit(args:argparse.Namespace,representative:int,partition:dict,
                              stdout:str,stderr:str)->dict:
    classes=partition['audit']['partition']['classes']
    expected_reps=[row['representative'] for row in classes]
    by_representative={row['representative']:row for row in classes}
    reflection_class=by_representative[representative]
    expected_forced={'root':{'index':representative,'move':reflection_class['move']}}
    return bound_branch_listing_audit(stderr+'\n'+stdout,'root',args.width,expected_reps,
                                      partition['audit'],expected_forced)

def root_branch_binding_valid(record:dict,args:argparse.Namespace,representative:int,
                              partition:dict)->bool:
    if (record.get('branch_identity_status')!='ok'
            or not isinstance(record.get('stdout'),str)
            or not isinstance(record.get('stderr'),str)):
        return False
    try:audit=root_branch_listing_audit(args,representative,partition,record['stdout'],record['stderr'])
    except (KeyError,TypeError,ValueError):return False
    return (record.get('branch_listing_audit')==audit
            and record.get('branch_listing_sha256')==json_digest(audit))

def existing(path:Path,stdout_path:Path,stderr_path:Path,solver_hash:str,command:list[str],representative:int|None=None,
             reflection_class:dict|None=None,partition_sha256:str|None=None)->dict|None:
    try:d=json.loads(path.read_text())
    except (FileNotFoundError,json.JSONDecodeError):return None
    if not isinstance(d,dict):return None
    try:raw_stdout=stdout_path.read_text();raw_stderr=stderr_path.read_text()
    except OSError:return None
    if d.get('stdout')!=raw_stdout or d.get('stderr')!=raw_stderr:return None
    raw=d.get('parsed') if isinstance(d.get('parsed'),dict) else None;p=normalize_legacy(raw)
    from_raw=normalize_legacy(parse_solver_output(raw_stdout))
    if flat_metrics(from_raw)!=flat_metrics(p):return None
    p=from_raw
    valid=(d.get('status')=='refuted' and exact_zero(d.get('returncode')) and d.get('external_timeout') is False
           and p.get('solved')==0 and p.get('timeout')==0 and stalemate_counter_status(p)==COUNTER_OK
           and d.get('solver_sha256')==solver_hash and d.get('command')==command)
    if representative is not None:
        cached_rep=d.get('representative')
        valid=valid and isinstance(cached_rep,int) and not isinstance(cached_rep,bool) and cached_rep==representative
    if reflection_class is not None:valid=valid and d.get('reflection_class')==reflection_class
    if partition_sha256 is not None:valid=valid and d.get('move_partition_sha256')==partition_sha256
    if not valid:return None
    sanitized=dict(d);sanitized['parsed']=p;sanitized.update(flat_metrics(p));return sanitized

def archive_retryable_attempt(stem:Path)->None:
    token=time.time_ns()
    for suffix in ('.json','.out','.err'):
        path=stem.with_suffix(suffix)
        if path.exists():shutil.move(path,stem.parent/f'{stem.name}.attempt-{token}{suffix}')

def run_one(args:argparse.Namespace,rep:int,outdir:Path,solver_hash:str,partition:dict)->dict:
    stem=outdir/f'root_{rep:02d}'; result=stem.with_suffix('.json')
    cmd=[str(args.solver),'--width',str(args.width),'--height',str(args.height),'--walls',str(args.walls),
         '--root-index',str(rep),'--target','1','--start-depth',str(args.remaining_depth),
         '--max-depth',str(args.remaining_depth),'--seconds',str(args.seconds),'--tt-bits',str(args.tt_bits),
         '--order',str(args.order),'--no-bounds','--no-pawn-table']
    if args.no_symmetry:cmd.append('--no-symmetry')
    if args.mirror_only:cmd.append('--mirror-only')
    classes={row['representative']:row for row in partition['audit']['partition']['classes']}
    reflection_class=classes[rep];partition_sha256=partition['partition_sha256']
    old=existing(result,stem.with_suffix('.out'),stem.with_suffix('.err'),solver_hash,cmd,rep,reflection_class,partition_sha256)
    if old is not None and root_branch_binding_valid(old,args,rep,partition):return old
    if result.exists():
        try:stale=json.loads(result.read_text())
        except json.JSONDecodeError as error:raise RuntimeError(f'malformed cached record {result}; use a fresh --outdir') from error
        if not isinstance(stale,dict):raise RuntimeError(f'cached record {result} must be an object; use a fresh --outdir')
        if stale.get('solver_sha256')!=solver_hash or stale.get('command')!=cmd:
            raise RuntimeError(f'refusing to overwrite record from another solver or command: {result}')
        if stale.get('status') in {'proved','refuted','completed'}:
            raise RuntimeError(f'refusing to overwrite completed record that fails current audit checks: {result}')
        archive_retryable_attempt(stem)
    started=time.time()
    try:
        cp=subprocess.run(cmd,text=True,capture_output=True,timeout=args.seconds+args.timeout_grace,check=False)
        stdout,stderr,rc,external=cp.stdout,cp.stderr,cp.returncode,False
    except subprocess.TimeoutExpired as exc:
        stdout,stderr,rc,external=exc.stdout or '',exc.stderr or '',124,True
        if isinstance(stdout,bytes):stdout=stdout.decode(errors='replace')
        if isinstance(stderr,bytes):stderr=stderr.decode(errors='replace')
    stem.with_suffix('.out').write_text(stdout);stem.with_suffix('.err').write_text(stderr)
    branch_listing=None;branch_identity_error=None
    try:branch_listing=root_branch_listing_audit(args,rep,partition,stdout,stderr)
    except (KeyError,TypeError,ValueError) as error:branch_identity_error=str(error)
    branch_identity_ok=branch_listing is not None
    parsed=parse_solver_output(stdout) or {}
    counter_status=stalemate_counter_status(parsed)
    refuted=(rc==0 and branch_identity_ok and parsed.get('solved')==0 and parsed.get('timeout')==0 and not external and counter_status==COUNTER_OK)
    data={'status':'refuted' if refuted else 'unresolved','representative':rep,'command':cmd,'returncode':rc,
          'external_timeout':external,'elapsed_wall_seconds':time.time()-started,'solver_sha256':solver_hash,
          'reflection_class':reflection_class,'move_partition_sha256':partition_sha256,
          'branch_identity_status':'ok' if branch_identity_ok else 'mismatch',
          'branch_identity_error':branch_identity_error,'branch_listing_audit':branch_listing,
          'branch_listing_sha256':json_digest(branch_listing) if branch_listing is not None else None,
          'stdout':stdout,'stderr':stderr,
          'stalemate_counter_status':counter_status,'parsed':parsed,
          **flat_metrics(parsed)}
    tmp=result.with_suffix('.json.tmp');tmp.write_text(json.dumps(data,indent=2,sort_keys=True)+'\n');os.replace(tmp,result)
    print(json.dumps(data,sort_keys=True),flush=True);return data

def main()->int:
    ap=argparse.ArgumentParser();ap.add_argument('--solver',type=Path,required=True);ap.add_argument('--outdir',type=Path,required=True)
    ap.add_argument('--width',type=int,default=3);ap.add_argument('--height',type=int,default=9);ap.add_argument('--walls',type=int,default=10)
    ap.add_argument('--remaining-depth',type=int,default=32);ap.add_argument('--seconds',type=int,default=1800)
    ap.add_argument('--timeout-grace',type=int,default=90);ap.add_argument('--precompute-timeout',type=int,default=900)
    ap.add_argument('--tt-bits',type=int,default=26)
    ap.add_argument('--order',type=int,default=1);ap.add_argument('--jobs',type=int,default=1)
    ap.add_argument('--no-symmetry',action='store_true');ap.add_argument('--mirror-only',action='store_true')
    ap.add_argument('--reps',default=','.join(map(str,DEFAULT_REPS_3X9)))
    ap.add_argument('--expected-reps',default=','.join(map(str,DEFAULT_REPS_3X9)))
    args=ap.parse_args()
    if args.jobs<1:ap.error('--jobs must be positive')
    try:validate_reflection_invariant_prefix(args.width,[])
    except ValueError as error:ap.error(str(error))
    args.solver=args.solver.resolve();args.outdir.mkdir(parents=True,exist_ok=True)
    reps=[int(x) for x in args.reps.split(',') if x.strip()];expected=[int(x) for x in args.expected_reps.split(',') if x.strip()];solver_hash=sha256(args.solver)
    if not reps:ap.error('--reps must contain at least one representative')
    if not expected or len(set(expected))!=len(expected):ap.error('--expected-reps must contain unique representatives')
    if len(set(reps))!=len(reps):ap.error('--reps must not contain duplicates')
    if not set(reps)<=set(expected):ap.error('--reps contains a representative outside --expected-reps')
    partition=load_root_partition(args,args.outdir,solver_hash,expected)
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
        rows=list(pool.map(lambda r:run_one(args,r,args.outdir,solver_hash,partition),reps))
    unresolved=[r['representative'] for r in rows if r['status']!='refuted']
    parsed=[normalize_legacy(r.get('parsed') or r) for r in rows if r['status']=='refuted']
    counter_complete=all(stalemate_counter_status(normalize_legacy(r.get('parsed') or {}))==COUNTER_OK for r in rows)
    selection_all_refuted=len(rows)==len(reps) and not unresolved and counter_complete
    coverage_complete=len(reps)==len(expected) and set(reps)==set(expected)
    summary={'selection_all_refuted':selection_all_refuted,'coverage_complete':coverage_complete,
             'all_refuted':selection_all_refuted and coverage_complete,
             'records':len(rows),
             'selected_representatives':reps,'expected_representatives':expected,
             'refuted_representatives':[r['representative'] for r in rows if r['status']=='refuted'],
             'unresolved':unresolved,'first_player_not_forced_within_plies_from_start':args.remaining_depth+1 if selection_all_refuted and coverage_complete else None,
             'solver_sha256':solver_hash,'no_bounds':True,'no_pawn_table':True,'no_symmetry':args.no_symmetry,
             'mirror_only':args.mirror_only,'aggregate_nodes':sum(int(p.get('nodes',0)) for p in parsed),
             'aggregate_search_seconds':sum(float(p.get('seconds',0)) for p in parsed),
             'stalemate_counters_complete_and_zero':counter_complete,
             'aggregate_stalemates_seen':0 if counter_complete else None,
             'move_partition':partition}
    (args.outdir/'summary.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n');print(json.dumps(summary,sort_keys=True))
    return 0 if summary['all_refuted'] else 3
if __name__=='__main__':raise SystemExit(main())
