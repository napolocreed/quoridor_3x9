#!/usr/bin/env python3
"""Resumable subprocess worker for exact corridor research experiments.

Each JSONL task contains at least:
  {"id": "task-name", "args": ["--width", "4", ...]}
Optional fields: timeout, env, notes.

The worker hashes the solver, writes one atomic JSON record per task, and skips
completed matching records. Tasks are independent at the proof level; use a
single task containing --scan-current when wall-configuration cache sharing is
wanted inside a branch family.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from solver_output import COUNTER_OK, aggregate_stalemate_counter_status, parse_key_value_line


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def atomic_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    os.replace(tmp, path)


def parse_lines(text: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in text.splitlines():
        pairs = parse_key_value_line(line)
        if pairs:
            pairs["_line"] = line
            rows.append(pairs)
    return rows


def audit_counter_status(rows: list[dict[str, Any]]) -> str:
    result_rows = [row for row in rows if "nodes" in row and "timeout" in row]
    return aggregate_stalemate_counter_status(result_rows)


def completed_output_valid(rows: list[dict[str, Any]]) -> bool:
    """Require every emitted search result to be a completed exact query."""
    result_rows=[row for row in rows if "nodes" in row and "timeout" in row]
    if not result_rows or aggregate_stalemate_counter_status(result_rows)!=COUNTER_OK:
        return False
    for row in result_rows:
        if type(row.get("nodes")) is not int or row["nodes"]<0:
            return False
        if type(row.get("timeout")) is not int or row["timeout"]!=0:
            return False
        if "solved" in row:
            if type(row["solved"]) is not int or row["solved"] not in (0,1):
                return False
            if row["solved"]==1:
                if type(row.get("winner")) is not int or row["winner"] not in (1,2):
                    return False
            elif "winner" in row:
                return False
        elif "proven" in row:
            if type(row["proven"]) is not int or row["proven"] not in (0,1):
                return False
        else:
            return False
    return True


def safe_id(raw: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", raw).strip("._") or "task"


def exact_returncode(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value in {0, 1}


def load_tasks(path: Path) -> list[dict[str, Any]]:
    tasks = []
    for no, line in enumerate(path.read_text().splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        task = json.loads(line)
        if not isinstance(task,dict):
            raise ValueError(f"invalid task at {path}:{no}: root must be an object")
        if not isinstance(task.get("id"), str) or not isinstance(task.get("args"), list):
            raise ValueError(f"invalid task at {path}:{no}")
        raw_env=task.get("env",{})
        if not isinstance(raw_env,dict):raise ValueError(f"invalid env at {path}:{no}")
        task["env"]={str(key):str(value) for key,value in sorted(raw_env.items(),key=lambda item:str(item[0]))}
        tasks.append(task)
    if not tasks:raise ValueError("manifest must contain at least one task")
    ids = [safe_id(t["id"]) for t in tasks]
    if len(ids) != len(set(ids)):raise ValueError("task ids must remain unique after filename normalization")
    if "summary" in ids:raise ValueError("task id 'summary' is reserved")
    return tasks


def existing_ok(path: Path, solver_hash: str, command: list[str],task_id:str|None=None,env_overlay:dict[str,str]|None=None) -> bool:
    try:
        row = json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return False
    if not isinstance(row,dict):return False
    parsed = row.get("parsed_stdout")
    raw_stdout=row.get("stdout")
    if not isinstance(raw_stdout,str) or parse_lines(raw_stdout)!=parsed:return False
    return (row.get("status") == "completed" and exact_returncode(row.get("returncode"))
            and row.get("timed_out") is False and isinstance(parsed,list)
            and completed_output_valid(parsed)
            and row.get("solver_sha256") == solver_hash and row.get("command") == command
            and (task_id is None or row.get("id")==task_id)
            and (env_overlay is None or row.get("env")==env_overlay))


def run_one(task: dict[str, Any], solver: Path, solver_hash: str, outdir: Path, default_timeout: float, force: bool) -> dict[str, Any]:
    tid = task["id"]
    path = outdir / f"{safe_id(tid)}.json"
    command = [str(solver), *map(str, task["args"])]
    env_overlay=task["env"]
    if not force and existing_ok(path, solver_hash, command,tid,env_overlay):
        return {"id": tid, "status": "skipped", "path": str(path)}

    if path.exists() and not force:
        try:stale=json.loads(path.read_text())
        except json.JSONDecodeError as error:raise RuntimeError(f"malformed cached record {path}; use --force or a fresh --outdir") from error
        if not isinstance(stale,dict):raise RuntimeError(f"cached record {path} must be an object; use --force or a fresh --outdir")
        same_identity=(stale.get("id")==tid and stale.get("solver_sha256")==solver_hash
                       and stale.get("command")==command and stale.get("env")==env_overlay)
        if not same_identity or stale.get("status")=="completed":
            raise RuntimeError(f"refusing to overwrite stale or completed record: {path}")

    env = os.environ.copy()
    env.update(env_overlay)
    timeout = float(task.get("timeout", default_timeout))
    started = time.time()
    try:
        cp = subprocess.run(command, text=True, capture_output=True, env=env, timeout=timeout, check=False)
        stdout, stderr = cp.stdout, cp.stderr
        status = "completed" if cp.returncode in {0, 1} else ("unresolved" if cp.returncode == 3 else "failed")
        timed_out = False
        returncode = cp.returncode
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout.decode(errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        stderr = exc.stderr.decode(errors="replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        status, timed_out, returncode = "timeout", True, None

    parsed_stdout = parse_lines(stdout)
    counter_status = audit_counter_status(parsed_stdout)
    if status == "completed" and not completed_output_valid(parsed_stdout):
        status = "invalid_audit"
    record = {
        "id": tid,
        "status": status,
        "timed_out": timed_out,
        "returncode": returncode,
        "started_unix": started,
        "elapsed_wall_seconds": time.time() - started,
        "solver": str(solver),
        "solver_sha256": solver_hash,
        "command": command,
        "env": env_overlay,
        "notes": task.get("notes"),
        "stalemate_counter_status": counter_status,
        "parsed_stdout": parsed_stdout,
        "stdout": stdout,
        "stderr": stderr,
    }
    atomic_json(path, record)
    return {"id": tid, "status": status, "path": str(path), "elapsed": record["elapsed_wall_seconds"]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--solver", type=Path, default=Path("bin/lazy_specialized_solver"))
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--outdir", type=Path, required=True)
    ap.add_argument("--jobs", type=int, default=1)
    ap.add_argument("--timeout", type=float, default=3600)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    args.solver = args.solver.resolve()
    if not args.solver.is_file():
        ap.error(f"solver not found: {args.solver}")
    tasks = load_tasks(args.manifest)
    solver_hash = sha256(args.solver)
    args.outdir.mkdir(parents=True, exist_ok=True)

    print(json.dumps({"solver": str(args.solver), "sha256": solver_hash, "tasks": len(tasks), "jobs": args.jobs}), flush=True)
    failed = 0
    with cf.ThreadPoolExecutor(max_workers=max(1, args.jobs)) as pool:
        futs = [pool.submit(run_one, task, args.solver, solver_hash, args.outdir, args.timeout, args.force) for task in tasks]
        for fut in cf.as_completed(futs):
            row = fut.result()
            print(json.dumps(row, sort_keys=True), flush=True)
            failed += row["status"] in {"failed", "timeout", "unresolved", "invalid_audit"}

    summary = {
        "solver_sha256": solver_hash,
        "manifest": str(args.manifest),
        "tasks": len(tasks),
        "failed_or_timeout": failed,
        "failed_or_unresolved": failed,
        "completed_at_unix": time.time(),
    }
    atomic_json(args.outdir / "summary.json", summary)
    return 0 if failed == 0 else 3


if __name__ == "__main__":
    raise SystemExit(main())
