#!/usr/bin/env python3
"""Build a compact machine-readable manifest from archived audit artifacts."""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
from solver_output import flat_metrics, normalize_legacy, parse_solver_output
from reflection_partition import json_digest, listing_audit, listing_audit_valid

HISTORICAL_NO_COUNTER_SOLVERS = {
    'ff11c2530a15c534922d4348f7cf0d9e66366f7742951fb38e8550a375e5837c',
}
EXPECTED_REPS_3X9=[0,1,3,5,7,9,11,13,15,17,19,21,23,25,27,29,31,33]

def load(path: Path):
    value=json.loads(path.read_text())
    if not isinstance(value,dict):raise ValueError(f'{path}: root must be an object')
    return value

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()

def artifact_inventory(paths:list[Path],root:Path)->tuple[list[dict],list[str]]:
    """Hash every file consumed by the audit so the manifest binds raw evidence."""
    rows:list[dict]=[];errors:list[str]=[]
    for path in paths:
        try:
            stat=path.stat()
            if not path.is_file():raise OSError('not a regular file')
            rows.append({'path':relative_posix(path,root),'bytes':stat.st_size,'sha256':sha256(path)})
        except OSError as error:
            errors.append(f'{path}: cannot inventory audited artifact ({error})')
    return rows,errors

def branch_artifact_paths(directory:Path,summary_path:Path,prefix:str)->list[Path]:
    paths=[summary_path]
    for rep in EXPECTED_REPS_3X9:
        stem=directory/f'{prefix}_{rep:02d}'
        paths.extend(stem.with_suffix(suffix) for suffix in ('.json','.out','.err'))
    return paths

def relative_posix(path: Path, root: Path) -> str:
    try:return path.relative_to(root).as_posix()
    except ValueError:return str(path)

def rooted(path:Path|None,root:Path,default:Path)->Path:
    value=default if path is None else path
    return value.resolve() if value.is_absolute() else (root/value).resolve()

def partition_binding(summary:dict,level:str,width:int,solver_digest:str)->tuple[dict[int,dict]|None,list[str]]:
    record=summary.get('move_partition');errors=[]
    if record is None:
        if counter_status(summary)=='recorded_zero':errors.append(f'current {level} audit lacks a named reflection partition')
        return None,errors
    if not isinstance(record,dict):return None,[f'{level} move_partition is not an object']
    audit=record.get('audit');raw_audit=None
    if isinstance(record.get('stdout'),str) and isinstance(record.get('stderr'),str):
        try:raw_audit=listing_audit(record['stderr']+'\n'+record['stdout'],level,width,EXPECTED_REPS_3X9)
        except ValueError:pass
    command=record.get('command')
    expected_tail=(['--width','3','--height','9','--walls','10','--root-index','0',
                    '--target','1','--list-second','--order','1'] if level=='second' else
                   ['--width','3','--height','9','--walls','10','--target','1','--list-root','--order','1'])
    valid=(type(record.get('schema_version')) is int and record.get('schema_version')==1
        and type(record.get('returncode')) is int and record.get('returncode')==0
        and isinstance(command,list) and len(command)>=1 and command[1:]==expected_tail
        and record.get('solver_sha256')==solver_digest
        and listing_audit_valid(audit,level,width,EXPECTED_REPS_3X9)
        and raw_audit==audit
        and record.get('partition_sha256')==json_digest(audit.get('partition')))
    if level=='second':
        valid=valid and audit.get('forced')=={'root':{'index':0,'move':'P(7,1)'}}
    else:valid=valid and audit.get('forced')=={}
    if not valid:return None,[f'{level} named reflection partition is invalid or stale']
    classes=audit['partition']['classes']
    return {row['representative']:row for row in classes},errors

def parse_result(path: Path):
    if not path.exists(): return None
    d=parse_solver_output(path.read_text())
    if not d: return None
    d.pop('_line',None)
    d['path']=str(path)
    return d

def counter_status(record: dict) -> str:
    """Describe immutable historical records without inventing zero counters."""
    values=[]
    if isinstance(record.get('branches'),list):
        values=[row.get('stalemates_seen') for row in record['branches']]
    elif 'aggregate_stalemates_seen' in record:
        values=[record.get('aggregate_stalemates_seen')]
    elif 'stalemates_seen' in record:
        values=[record.get('stalemates_seen')]
    if not values or any(value is None for value in values):return 'not_recorded'
    if any(isinstance(value,bool) or not isinstance(value,int) for value in values):return 'invalid'
    counts=values
    return 'recorded_zero' if all(value==0 for value in counts) else 'semantic_violation'

def record_solver_hashes(record: dict) -> set[str]:
    hashes:set[str]=set()
    value=record.get('solver_sha256')
    if isinstance(value,str):hashes.add(value.lower())
    elif isinstance(value,list):hashes.update(str(item).lower() for item in value)
    if isinstance(record.get('branches'),list):
        hashes.update(str(row['solver_sha256']).lower() for row in record['branches'] if isinstance(row,dict) and row.get('solver_sha256'))
    return hashes

def counter_acceptance(record: dict, artifact_hash: str) -> str:
    status=counter_status(record);artifact_hash=artifact_hash.lower()
    if record_solver_hashes(record)!={artifact_hash}:return 'rejected_solver_hash_mismatch'
    if status=='recorded_zero':return 'recorded_zero'
    if (status=='not_recorded' and artifact_hash in HISTORICAL_NO_COUNTER_SOLVERS
            ):
        return 'historical_hash_whitelist_missing_counter'
    return f'rejected_{status}'

def exact_int(value:object)->bool:
    return isinstance(value,int) and not isinstance(value,bool)

def command_value(command:object,flag:str)->str|None:
    if not isinstance(command,list):return None
    positions=[index for index,value in enumerate(command) if value==flag]
    if len(positions)!=1 or positions[0]+1>=len(command):return None
    return str(command[positions[0]+1])

def command_matches(record:dict,expected:dict[str,int],required_flags:set[str])->bool:
    command=record.get('command')
    return (isinstance(command,list) and all(command_value(command,flag)==str(value) for flag,value in expected.items())
            and required_flags.issubset(set(command)))

def raw_branch_evidence(
    record:dict,
    stem:Path,
    level:str,
    representative:int,
    class_map:dict[int,dict]|None,
)->tuple[dict,list[str],dict|None]:
    """Reparse the immutable stdout/stderr and bind an indexed branch to its move."""
    errors:list[str]=[]
    stdout_path=stem.with_suffix('.out');stderr_path=stem.with_suffix('.err')
    try:stdout=stdout_path.read_text();stderr=stderr_path.read_text()
    except OSError as error:return {},[f'{stem}: missing raw branch output ({error})'],None
    parsed=normalize_legacy(parse_solver_output(stdout))
    stored=normalize_legacy(record.get('parsed') if isinstance(record.get('parsed'),dict) else None)
    if not parsed:errors.append(f'{stdout_path}: no solver result line')
    if flat_metrics(parsed)!=flat_metrics(stored):errors.append(f'{stdout_path}: raw result disagrees with JSON record')
    try:audit=listing_audit(stderr+'\n'+stdout,level,3,EXPECTED_REPS_3X9)
    except ValueError as error:
        errors.append(f'{stderr_path}: invalid named move listing ({error})');return parsed,errors,None
    expected_class={row['representative']:row for row in audit['partition']['classes']}.get(representative)
    if expected_class is None:errors.append(f'{stderr_path}: representative {representative} is not in the named partition')
    if class_map is not None and expected_class!=class_map.get(representative):
        errors.append(f'{stderr_path}: branch reflection class disagrees with the summary preflight')
    expected_forced=(
        {'root':{'index':0,'move':'P(7,1)'},
         'second':{'index':representative,'move':expected_class['move']}}
        if level=='second' and expected_class is not None else
        {'root':{'index':representative,'move':expected_class['move']}}
        if level=='root' and expected_class is not None else None
    )
    if audit.get('forced')!=expected_forced:
        errors.append(f'{stderr_path}: forcing lines do not bind representative {representative}')
    return parsed,errors,audit

def validate_upper_archive(upper_dir:Path,walls:int,solver_digest:str,summary:dict)->list[str]:
    errors=[];raw_rows=[];raw_partition_hash=None
    class_map,partition_errors=partition_binding(summary,'second',3,solver_digest);errors.extend(partition_errors)
    expected_flags={'--no-bounds','--no-pawn-table'}
    for rep in EXPECTED_REPS_3X9:
        path=upper_dir/f'reply_{rep:02d}.json'
        try:record=load(path)
        except (FileNotFoundError,json.JSONDecodeError,ValueError) as error:
            errors.append(f'{path}: {error}');continue
        stem=upper_dir/f'reply_{rep:02d}'
        result,raw_errors,audit=raw_branch_evidence(record,stem,'second',rep,class_map)
        errors.extend(raw_errors)
        if audit is not None:
            digest=json_digest(audit['partition'])
            if raw_partition_hash is None:raw_partition_hash=digest
            elif digest!=raw_partition_hash:errors.append(f'{stem.with_suffix(".err")}: named partition differs across branches')
        expected={'--width':3,'--height':9,'--walls':walls,'--root-index':0,'--root-index2':rep,
                  '--target':1,'--start-depth':31,'--max-depth':35}
        valid=(exact_int(record.get('representative')) and record.get('representative')==rep
               and record.get('status')=='proved'
               and exact_int(record.get('returncode')) and record.get('returncode')==0
               and record.get('external_timeout') is False
               and record.get('solver_sha256')==solver_digest and command_matches(record,expected,expected_flags)
               and result.get('solved')==1 and result.get('winner')==1 and result.get('timeout')==0
               and exact_int(result.get('depth')) and result['depth'] in {31,33}
               and exact_int(result.get('nodes')))
        if class_map is not None:
            valid=(valid and record.get('reflection_class')==class_map.get(rep)
                   and record.get('move_partition_sha256')==summary['move_partition']['partition_sha256'])
        if not valid:errors.append(f'{path}: invalid proof record')
        else:raw_rows.append((rep,result,record))
    reps=[row[0] for row in raw_rows]
    aggregate=summary.get('branches')
    aggregate_by_rep={row.get('representative'):row for row in aggregate if isinstance(row,dict)} if isinstance(aggregate,list) else {}
    if len(aggregate_by_rep)!=len(EXPECTED_REPS_3X9):errors.append('upper aggregate branch coverage is not exact')
    for rep,result,_ in raw_rows:
        row=aggregate_by_rep.get(rep)
        if not isinstance(row,dict) or row.get('status')!='proved' or row.get('depth')!=result.get('depth') or row.get('nodes')!=result.get('nodes') or row.get('solver_sha256')!=solver_digest:
            errors.append(f'upper aggregate mismatch for representative {rep}')
    expected_summary=(summary.get('all_proved') is True and summary.get('records')==18
                      and summary.get('proved_representatives')==EXPECTED_REPS_3X9 and summary.get('unresolved')==[]
                      and summary.get('max_child_depth')==33 and summary.get('upper_bound_plies_from_start')==35
                      and reps==EXPECTED_REPS_3X9
                      and summary.get('aggregate_nodes')==sum(result['nodes'] for _,result,_ in raw_rows)
                      and record_solver_hashes(summary)=={solver_digest})
    if not expected_summary:errors.append('upper aggregate summary fields do not certify the expected 35-ply/18-class audit')
    return errors

def validate_lower_archive(lower_dir:Path,walls:int,solver_digest:str,summary:dict)->list[str]:
    errors=[];raw_rows=[];raw_partition_hash=None
    class_map,partition_errors=partition_binding(summary,'root',3,solver_digest);errors.extend(partition_errors)
    expected_flags={'--no-bounds','--no-pawn-table'}
    for rep in EXPECTED_REPS_3X9:
        path=lower_dir/f'root_{rep:02d}.json'
        try:record=load(path)
        except (FileNotFoundError,json.JSONDecodeError,ValueError) as error:
            errors.append(f'{path}: {error}');continue
        stem=lower_dir/f'root_{rep:02d}'
        result,raw_errors,audit=raw_branch_evidence(record,stem,'root',rep,class_map)
        errors.extend(raw_errors)
        if audit is not None:
            digest=json_digest(audit['partition'])
            if raw_partition_hash is None:raw_partition_hash=digest
            elif digest!=raw_partition_hash:errors.append(f'{stem.with_suffix(".err")}: named partition differs across branches')
        expected={'--width':3,'--height':9,'--walls':walls,'--root-index':rep,'--target':1,
                  '--start-depth':32,'--max-depth':32}
        valid=(exact_int(record.get('representative')) and record.get('representative')==rep
               and record.get('status')=='refuted'
               and exact_int(record.get('returncode')) and record.get('returncode')==0
               and record.get('external_timeout') is False
               and record.get('solver_sha256')==solver_digest and command_matches(record,expected,expected_flags)
               and result.get('solved')==0 and result.get('timeout')==0 and exact_int(result.get('nodes')))
        if class_map is not None:
            valid=(valid and record.get('reflection_class')==class_map.get(rep)
                   and record.get('move_partition_sha256')==summary['move_partition']['partition_sha256'])
        if not valid:errors.append(f'{path}: invalid lower-bound record')
        else:raw_rows.append((rep,result))
    reps=[row[0] for row in raw_rows]
    expected_summary=(summary.get('all_refuted') is True
                      and summary.get('refuted_representatives')==EXPECTED_REPS_3X9 and summary.get('unresolved')==[]
                      and summary.get('first_player_not_forced_within_plies_from_start')==33
                      and summary.get('no_bounds') is True and summary.get('no_pawn_table') is True
                      and reps==EXPECTED_REPS_3X9
                      and summary.get('aggregate_nodes')==sum(result['nodes'] for _,result in raw_rows)
                      and record_solver_hashes(summary)=={solver_digest})
    if not expected_summary:errors.append('lower aggregate summary fields do not certify the expected 33-ply/18-class audit')
    return errors

def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument('--root',type=Path,default=Path('.'))
    ap.add_argument('--walls',type=int,required=True)
    ap.add_argument('--upper-dir',type=Path)
    ap.add_argument('--upper-summary',type=Path)
    ap.add_argument('--lower-dir',type=Path)
    ap.add_argument('--lower-summary',type=Path)
    ap.add_argument('--solver',type=Path)
    ap.add_argument('--source',type=Path)
    ap.add_argument('--output',type=Path)
    args=ap.parse_args(); root=args.root.resolve(); w=args.walls
    if w!=10:ap.error('this exact-horizon manifest builder currently supports only --walls 10')
    base=root/f'results/3x9_w{w}'
    upper_dir=rooted(args.upper_dir,root,Path(f'results/3x9_w{w}/audit/core_only'))
    lower_dir=rooted(args.lower_dir,root,Path(f'results/3x9_w{w}/audit/lower_bound_33'))
    if args.upper_summary is None:
        upper_summary_path=upper_dir/'aggregate.json'
        if not upper_summary_path.exists():upper_summary_path=upper_dir/'summary.json'
    else:upper_summary_path=rooted(args.upper_summary,root,args.upper_summary)
    lower_summary_path=(lower_dir/'summary.json' if args.lower_summary is None
                        else rooted(args.lower_summary,root,args.lower_summary))
    core=load(upper_summary_path)
    lower=load(lower_summary_path)
    solver=rooted(args.solver,root,upper_dir/'solver')
    source=rooted(args.source,root,upper_dir/'solver.cpp')
    solver_digest=sha256(solver)
    upper_counter_acceptance=counter_acceptance(core,solver_digest)
    lower_counter_acceptance=counter_acceptance(lower,solver_digest)
    upper_integrity_errors=validate_upper_archive(upper_dir,w,solver_digest,core)
    lower_integrity_errors=validate_lower_archive(lower_dir,w,solver_digest,lower)
    upper_inventory,upper_inventory_errors=artifact_inventory(
        branch_artifact_paths(upper_dir,upper_summary_path,'reply'),root)
    lower_inventory,lower_inventory_errors=artifact_inventory(
        branch_artifact_paths(lower_dir,lower_summary_path,'root'),root)
    upper_integrity_errors.extend(upper_inventory_errors)
    lower_integrity_errors.extend(lower_inventory_errors)
    all_proved=not upper_integrity_errors and not upper_counter_acceptance.startswith('rejected_')
    all_refuted=not lower_integrity_errors and not lower_counter_acceptance.startswith('rejected_')
    exact_horizon=35 if all_proved and all_refuted else None
    manifest={
      'schema_version':1,
      'claim':{
        'width':3,'height':9,'walls_per_player':w,
        'winner':1 if all_proved else None,
        'witness_opening':'P(7,1)',
        'forced_win_upper_bound_plies':core.get('upper_bound_plies_from_start') if all_proved else None,
        'no_forced_win_within_plies':lower.get('first_player_not_forced_within_plies_from_start') if all_refuted else None,
        'exact_minimax_forcing_horizon_plies':exact_horizon,
        'external_replication_status':'not yet independently reproduced by a separate full solver',
      },
      'upper_bound_audit':core,
      'lower_bound_audit':lower,
      'trusted_optimizations_disabled':{
        'distance_bound':True,'pawn_only_table':True,
        'per_branch_fresh_process_and_tt':True,
      },
      'audit_integrity':{
        'upper_directory':relative_posix(upper_dir,root),
        'lower_directory':relative_posix(lower_dir,root),
        'upper_summary':relative_posix(upper_summary_path,root),
        'lower_summary':relative_posix(lower_summary_path,root),
        'expected_reflection_representatives':EXPECTED_REPS_3X9,
        'upper_bound_raw_records_valid':not upper_integrity_errors,
        'lower_bound_raw_records_valid':not lower_integrity_errors,
        'upper_bound_raw_stdout_stderr_and_named_forcing_valid':not upper_integrity_errors,
        'lower_bound_raw_stdout_stderr_and_named_forcing_valid':not lower_integrity_errors,
        'upper_bound_artifacts':upper_inventory,
        'lower_bound_artifacts':lower_inventory,
        'upper_bound_artifacts_sha256':json_digest(upper_inventory),
        'lower_bound_artifacts_sha256':json_digest(lower_inventory),
        'upper_bound_errors':upper_integrity_errors,
        'lower_bound_errors':lower_integrity_errors,
      },
      'stalemate_audit':{
        'semantics':'a non-terminal state with no legal action is false for both targets',
        'height_at_least_3_theorem_applies':True,
        'upper_bound_counter_status':counter_status(core),
        'lower_bound_counter_status':counter_status(lower),
        'upper_bound_counter_acceptance':upper_counter_acceptance,
        'lower_bound_counter_acceptance':lower_counter_acceptance,
        'historical_absence_is_not_zero':True,
      },
      'solver_artifact':{
        'path':relative_posix(solver,root),'sha256':solver_digest,
        'source_path':relative_posix(source,root),'source_sha256':sha256(source),
      },
    }
    if w==10:
        guarded=parse_result(base/'audit/guarded_no_symmetry_reply00/result.out')
        manifest['selected_no_symmetry_replication']=guarded
        cfg=load(root/'results/validation/config_count_3x9w10.out')
        manifest['independent_wall_configuration_count']=cfg
        manifest['validation_artifacts']={
          'exhaustive_legal_moves_4x3w3':'results/validation/exhaustive_4x3_w3.out',
          'exhaustive_proof_semantics_3x3w1':'results/validation/proof_diff_exhaustive_nott_nosym.out',
          'sampled_proof_semantics_4x3w2':'results/validation/proof_diff_4x3w2_core.out',
          'root_reflection_classes':'results/validation/root_class_audit.out',
          'reply_reflection_classes':'results/validation/reply_class_audit.out',
        }
    out=rooted(args.output,root,Path(f'results/3x9_w{w}/final_result.json'))
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
    print(out)
    return 0 if all_proved and all_refuted else 3
if __name__=='__main__': raise SystemExit(main())
