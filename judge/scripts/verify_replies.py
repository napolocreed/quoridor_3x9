#!/usr/bin/env python3
"""Resumable independent verification of reply classes after a forced opening.

Each representative is solved in a fresh process and recorded atomically. Completed
results are skipped on restart, so an interrupted run loses only in-flight branches.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
from solver_output import COUNTER_OK, flat_metrics, normalize_legacy, parse_solver_output, stalemate_counter_status
from reflection_partition import (
    bound_branch_listing_audit,
    json_digest,
    listing_audit,
    listing_audit_valid,
    validate_reflection_invariant_prefix,
)

DEFAULT_REPS_3X9 = [0, 1, 3, 5, 7, 9, 11, 13, 15, 17, 19, 21, 23, 25, 27, 29, 31, 33]
def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def partition_command(args: argparse.Namespace) -> list[str]:
    return [
        str(args.solver),
        "--width", str(args.width), "--height", str(args.height),
        "--walls", str(args.walls), "--root-index", str(args.root_index),
        "--target", str(args.target), "--list-second", "--order", str(args.order),
    ]


def load_reply_partition(
    args: argparse.Namespace,
    outdir: Path,
    solver_hash: str,
    expected_reps: list[int],
) -> dict:
    validate_reflection_invariant_prefix(args.width, [args.expected_root_move])
    cache = outdir / "reply_partition.json"
    command = partition_command(args)
    if cache.exists():
        try:
            record = json.loads(cache.read_text())
        except json.JSONDecodeError as error:
            raise RuntimeError(f"malformed move-partition cache: {cache}") from error
        audit = record.get("audit") if isinstance(record, dict) else None
        forced = audit.get("forced", {}) if isinstance(audit, dict) else {}
        raw_audit = None
        if isinstance(record, dict) and isinstance(record.get("stdout"), str) and isinstance(record.get("stderr"), str):
            try:
                raw_audit = listing_audit(
                    record["stderr"] + "\n" + record["stdout"],
                    "second", args.width, expected_reps,
                )
            except ValueError:
                pass
        valid = (
            isinstance(record, dict)
            and type(record.get("schema_version")) is int
            and record.get("schema_version") == 1
            and type(record.get("returncode")) is int
            and record.get("returncode") == 0
            and record.get("solver_sha256") == solver_hash
            and record.get("command") == command
            and listing_audit_valid(audit, "second", args.width, expected_reps)
            and raw_audit == audit
            and record.get("partition_sha256") == json_digest(audit.get("partition"))
            and forced == {"root": {"index": args.root_index, "move": args.expected_root_move}}
        )
        if not valid:
            raise RuntimeError(f"refusing stale or invalid move-partition cache: {cache}")
        return record

    try:
        completed = subprocess.run(
            command, text=True, capture_output=True,
            timeout=args.precompute_timeout, check=False,
        )
    except subprocess.TimeoutExpired as error:
        raise RuntimeError("timed out while enumerating the named reply partition") from error
    combined = completed.stderr + "\n" + completed.stdout
    try:
        audit = listing_audit(combined, "second", args.width, expected_reps)
    except ValueError as error:
        raise RuntimeError(f"could not validate reply reflection classes: {error}") from error
    expected_forced = {"root": {"index": args.root_index, "move": args.expected_root_move}}
    if completed.returncode != 0 or audit["forced"] != expected_forced:
        raise RuntimeError(
            f"reply partition is not bound to {args.expected_root_move} "
            f"(rc={completed.returncode}, forced={audit['forced']})"
        )
    record = {
        "schema_version": 1,
        "solver_sha256": solver_hash,
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "audit": audit,
        "partition_sha256": json_digest(audit["partition"]),
    }
    tmp = cache.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    os.replace(tmp, cache)
    return record


def exact_zero(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value == 0


def reply_branch_listing_audit(
    args: argparse.Namespace,
    representative: int,
    partition: dict,
    stdout: str,
    stderr: str,
) -> dict:
    classes = partition["audit"]["partition"]["classes"]
    expected_reps = [row["representative"] for row in classes]
    by_representative = {row["representative"]: row for row in classes}
    reflection_class = by_representative[representative]
    expected_forced = {
        "root": {"index": args.root_index, "move": args.expected_root_move},
        "second": {"index": representative, "move": reflection_class["move"]},
    }
    return bound_branch_listing_audit(
        stderr + "\n" + stdout,
        "second",
        args.width,
        expected_reps,
        partition["audit"],
        expected_forced,
    )


def reply_branch_binding_valid(
    record: dict,
    args: argparse.Namespace,
    representative: int,
    partition: dict,
) -> bool:
    if (
        record.get("branch_identity_status") != "ok"
        or not isinstance(record.get("stdout"), str)
        or not isinstance(record.get("stderr"), str)
    ):
        return False
    try:
        audit = reply_branch_listing_audit(
            args, representative, partition, record["stdout"], record["stderr"]
        )
    except (KeyError, TypeError, ValueError):
        return False
    return (
        record.get("branch_listing_audit") == audit
        and record.get("branch_listing_sha256") == json_digest(audit)
    )


def load_result(
    path: Path,
    stdout_path: Path,
    stderr_path: Path,
    solver_hash: str,
    command: list[str],
    target: int,
    representative: int | None = None,
    reflection_class: dict | None = None,
    partition_sha256: str | None = None,
) -> dict | None:
    try:
        data = json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return None
    if not isinstance(data,dict):
        return None
    try:
        raw_stdout=stdout_path.read_text();raw_stderr=stderr_path.read_text()
    except OSError:
        return None
    if data.get("stdout")!=raw_stdout or data.get("stderr")!=raw_stderr:
        return None
    raw_parsed=data.get("parsed") if isinstance(data.get("parsed"),dict) else None
    parsed = normalize_legacy(raw_parsed)
    from_raw=normalize_legacy(parse_solver_output(raw_stdout))
    if flat_metrics(from_raw)!=flat_metrics(parsed):return None
    parsed=from_raw
    if not (
        data.get("status") == "proved"
        and exact_zero(data.get("returncode"))
        and data.get("external_timeout") is False
        and parsed.get("solved") == 1
        and parsed.get("winner") == target
        and parsed.get("timeout") == 0
        and stalemate_counter_status(parsed) == COUNTER_OK
    ):
        return None
    if data.get("solver_sha256") != solver_hash or data.get("command") != command:
        return None
    if representative is not None:
        cached_rep = data.get("representative")
        if not (isinstance(cached_rep, int) and not isinstance(cached_rep, bool) and cached_rep == representative):
            return None
    if reflection_class is not None and data.get("reflection_class") != reflection_class:
        return None
    if partition_sha256 is not None and data.get("move_partition_sha256") != partition_sha256:
        return None
    sanitized = dict(data)
    sanitized["parsed"] = parsed
    sanitized.update(flat_metrics(parsed))
    return sanitized


def archive_retryable_attempt(stem:Path)->None:
    token=time.time_ns()
    for suffix in (".json",".out",".err"):
        path=stem.with_suffix(suffix)
        if path.exists():
            archived=stem.parent/f"{stem.name}.attempt-{token}{suffix}"
            shutil.move(path,archived)


def run_one(
    args: argparse.Namespace,
    rep: int,
    outdir: Path,
    solver_hash: str,
    partition: dict,
) -> dict:
    stem = outdir / f"reply_{rep:02d}"
    result_path = stem.with_suffix(".json")
    cmd = [
        str(args.solver),
        "--width", str(args.width), "--height", str(args.height),
        "--walls", str(args.walls),
        "--root-index", str(args.root_index),
        "--root-index2", str(rep),
        "--target", str(args.target),
        "--start-depth", str(args.start_depth),
        "--max-depth", str(args.max_depth),
        "--seconds", str(args.seconds),
        "--tt-bits", str(args.tt_bits),
        "--order", str(args.order),
    ]
    if args.no_bounds:
        cmd.append("--no-bounds")
    if args.no_pawn_table:
        cmd.append("--no-pawn-table")
    if args.no_tt:
        cmd.append("--no-tt")
    if args.no_symmetry:
        cmd.append("--no-symmetry")
    if args.mirror_only:
        cmd.append("--mirror-only")
    classes = {
        row["representative"]: row
        for row in partition["audit"]["partition"]["classes"]
    }
    reflection_class = classes[rep]
    partition_sha256 = partition["partition_sha256"]
    previous = load_result(
        result_path, stem.with_suffix(".out"), stem.with_suffix(".err"),
        solver_hash, cmd, args.target, rep,
        reflection_class, partition_sha256,
    )
    if previous and reply_branch_binding_valid(previous, args, rep, partition):
        return previous
    if result_path.exists():
        try:stale=json.loads(result_path.read_text())
        except json.JSONDecodeError as error:raise RuntimeError(f"malformed cached record {result_path}; use a fresh --outdir") from error
        if not isinstance(stale,dict):raise RuntimeError(f"cached record {result_path} must be an object; use a fresh --outdir")
        if stale.get("solver_sha256")!=solver_hash or stale.get("command")!=cmd:
            raise RuntimeError(f"refusing to overwrite record from another solver or command: {result_path}")
        if stale.get("status") in {"proved","refuted","completed"}:
            raise RuntimeError(f"refusing to overwrite completed record that fails current audit checks: {result_path}")
        archive_retryable_attempt(stem)
    started = time.time()
    try:
        cp = subprocess.run(
            cmd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=args.seconds + args.timeout_grace,
            check=False,
        )
        timed_out_externally = False
        stdout, stderr, rc = cp.stdout, cp.stderr, cp.returncode
    except subprocess.TimeoutExpired as exc:
        timed_out_externally = True
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        if isinstance(stdout, bytes): stdout = stdout.decode(errors="replace")
        if isinstance(stderr, bytes): stderr = stderr.decode(errors="replace")
        rc = 124

    stem.with_suffix(".out").write_text(stdout)
    stem.with_suffix(".err").write_text(stderr)
    branch_listing = None
    branch_identity_error = None
    try:
        branch_listing = reply_branch_listing_audit(args, rep, partition, stdout, stderr)
    except (KeyError, TypeError, ValueError) as error:
        branch_identity_error = str(error)
    branch_identity_ok = branch_listing is not None
    parsed = parse_solver_output(stdout) or {}
    solved = parsed.get("solved") == 1
    winner = parsed.get("winner")
    internal_complete = parsed.get("timeout") == 0
    counter_status = stalemate_counter_status(parsed)
    status = "proved" if rc == 0 and not timed_out_externally and branch_identity_ok and solved and winner == args.target and internal_complete and counter_status == COUNTER_OK else "unresolved"
    data = {
        "status": status,
        "representative": rep,
        "command": cmd,
        "returncode": rc,
        "external_timeout": timed_out_externally,
        "elapsed_wall_seconds": time.time() - started,
        "solver_sha256": solver_hash,
        "reflection_class": reflection_class,
        "move_partition_sha256": partition_sha256,
        "branch_identity_status": "ok" if branch_identity_ok else "mismatch",
        "branch_identity_error": branch_identity_error,
        "branch_listing_audit": branch_listing,
        "branch_listing_sha256": json_digest(branch_listing) if branch_listing is not None else None,
        "stalemate_counter_status": counter_status,
        "stdout": stdout,
        "stderr": stderr,
        "parsed": parsed,
        **flat_metrics(parsed),
    }
    tmp = result_path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    os.replace(tmp, result_path)
    print(json.dumps(data, sort_keys=True), flush=True)
    return data


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--solver", type=Path, required=True)
    p.add_argument("--outdir", type=Path, required=True)
    p.add_argument("--width", type=int, default=3)
    p.add_argument("--height", type=int, default=9)
    p.add_argument("--walls", type=int, required=True)
    p.add_argument("--root-index", type=int, default=0)
    p.add_argument("--expected-root-move", default="P(7,1)")
    p.add_argument("--target", type=int, default=1)
    p.add_argument("--start-depth", type=int, default=31)
    p.add_argument("--max-depth", type=int, default=33)
    p.add_argument("--seconds", type=int, default=900)
    p.add_argument("--timeout-grace", type=int, default=90)
    p.add_argument("--precompute-timeout", type=int, default=900)
    p.add_argument("--tt-bits", type=int, default=24)
    p.add_argument("--order", type=int, default=1)
    p.add_argument("--jobs", type=int, default=2)
    p.add_argument("--no-bounds", action="store_true")
    p.add_argument("--no-pawn-table", action="store_true")
    p.add_argument("--no-tt", action="store_true")
    p.add_argument("--no-symmetry", action="store_true")
    p.add_argument("--mirror-only", action="store_true")
    p.add_argument("--reps", default=",".join(map(str, DEFAULT_REPS_3X9)))
    p.add_argument("--expected-reps", default=",".join(map(str, DEFAULT_REPS_3X9)))
    args = p.parse_args()
    if args.jobs < 1:
        p.error("--jobs must be positive")
    try:
        validate_reflection_invariant_prefix(args.width, [args.expected_root_move])
    except ValueError as error:
        p.error(str(error))
    args.solver = args.solver.resolve()
    args.outdir.mkdir(parents=True, exist_ok=True)
    reps = [int(x) for x in args.reps.split(",") if x.strip()]
    if not reps:
        p.error("--reps must contain at least one representative")
    expected=[int(x) for x in args.expected_reps.split(",") if x.strip()]
    if not expected or len(set(expected))!=len(expected):p.error("--expected-reps must contain unique representatives")
    if len(set(reps))!=len(reps):p.error("--reps must not contain duplicates")
    if not set(reps)<=set(expected):p.error("--reps contains a representative outside --expected-reps")
    solver_hash = sha256(args.solver)
    partition = load_reply_partition(args, args.outdir, solver_hash, expected)

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
        results = list(pool.map(lambda r: run_one(args, r, args.outdir, solver_hash, partition), reps))

    branches = []
    for result in results:
        parsed = normalize_legacy(result.get("parsed") or {})
        branches.append({
            "representative": result["representative"],
            "move": result["reflection_class"]["move"],
            "aliases": result["reflection_class"]["aliases"],
            "status": result["status"],
            "depth": parsed.get("depth"),
            "nodes": parsed.get("nodes"),
            "tt_hits": parsed.get("tt_hits"),
            "cutoffs": parsed.get("cutoffs"),
            "pawn_table_hits": parsed.get("pawn_table_hits"),
            "stalemates_seen": parsed.get("stalemates_seen"),
            "seconds": parsed.get("seconds"),
            "solver_sha256": solver_hash,
        })
    proved = [row["representative"] for row in branches if row["status"] == "proved"]
    unresolved = [row["representative"] for row in branches if row["status"] != "proved"]
    proved_depths = [row["depth"] for row in branches
                     if row["status"] == "proved" and type(row.get("depth")) is int]
    counter_complete = all(stalemate_counter_status(normalize_legacy(r.get("parsed") or {})) == COUNTER_OK for r in results)
    selection_all_proved=not unresolved and counter_complete
    coverage_complete=len(reps)==len(expected) and set(reps)==set(expected)
    summary = {
        "selection_all_proved": selection_all_proved,
        "coverage_complete": coverage_complete,
        "all_proved": selection_all_proved and coverage_complete,
        "records": len(branches),
        "search_all_proved": selection_all_proved and coverage_complete,
        "selected_representatives": reps,
        "expected_representatives": expected,
        "proved": proved,
        "proved_representatives": proved,
        "unresolved": unresolved,
        "max_child_depth": max(proved_depths) if proved_depths else None,
        "forced_win_upper_bound_plies_from_start": (max(proved_depths) + 2) if selection_all_proved and coverage_complete and proved_depths else None,
        "upper_bound_plies_from_start": (max(proved_depths) + 2) if selection_all_proved and coverage_complete and proved_depths else None,
        "aggregate_nodes": sum(row["nodes"] for row in branches if type(row.get("nodes")) is int),
        "aggregate_search_seconds": sum(float(row["seconds"]) for row in branches if type(row.get("seconds")) in (int, float)),
        "solver_sha256": solver_hash,
        "no_bounds": args.no_bounds,
        "no_pawn_table": args.no_pawn_table,
        "no_tt": args.no_tt,
        "no_symmetry": args.no_symmetry,
        "mirror_only": args.mirror_only,
        "stalemate_counters_complete_and_zero": counter_complete,
        "aggregate_stalemates_seen": 0 if counter_complete else None,
        "stalemates_seen": 0 if counter_complete else None,
        "move_partition": partition,
        "branches": branches,
    }
    (args.outdir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, sort_keys=True))
    return 0 if summary["all_proved"] else 3

if __name__ == "__main__":
    raise SystemExit(main())
