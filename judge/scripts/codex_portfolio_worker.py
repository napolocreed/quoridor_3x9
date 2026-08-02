#!/usr/bin/env python3
"""Run exact move-order portfolios with stable named positions.

Manifest JSONL format:
{
  "id": "4x7-h52-d24",
  "args": ["--width","4",...,"--third-move","H(5,2)"],
  "weights": [0, 40],
  "timeout": 1800
}

Each policy is an ordering policy only. All variants search the identical named
position and use the same exact proof semantics. The first variant that exits
normally with a parseable `timeout=0` result wins; remaining variants are killed.

An additional policy can be attached to every task without copying a manifest:

  --append-policy-json '{"name":"hint","args":["--flag","value"]}'

The normalized overlay becomes part of every atomic record and cache identity.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import hashlib
import json
import os
import re
import signal
import subprocess
import time
from pathlib import Path
from typing import Any
from solver_output import stalemate_counter_ok

KV_RE = re.compile(r"(?P<key>[A-Za-z_][A-Za-z0-9_]*)=(?P<value>[^\s]+)")
POLICY_VALUE_OPTIONS = {
    "--path-choice-weight", "--path-flow-weight", "--path-flow-cache-bits",
    "--tt-hint-first-mode",
}
POLICY_FLAG_OPTIONS = {"--no-tt-hint-first", "--no-tt-hint-transform"}
CO_WINNER_GRACE_SECONDS = 0.02


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def json_sha256(data: Any) -> str:
    encoded = json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def atomic_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    os.replace(tmp, path)


def scalar(value: str) -> Any:
    try:
        return int(value)
    except ValueError:
        try:
            return float(value)
        except ValueError:
            return value


def parsed_result(stdout: str) -> dict[str, Any] | None:
    for line in reversed(stdout.splitlines()):
        pairs = {m.group("key"): scalar(m.group("value")) for m in KV_RE.finditer(line)}
        if "nodes" in pairs and "timeout" in pairs:
            pairs["_line"] = line
            return pairs
    return None


def safe_id(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._") or "task"


def validate_policy_args(args: list[str], context: str) -> None:
    i = 0
    while i < len(args):
        option = args[i]
        if option in POLICY_FLAG_OPTIONS:
            i += 1
            continue
        if option in POLICY_VALUE_OPTIONS:
            if i + 1 >= len(args):
                raise ValueError(f"{context}: policy option {option!r} needs a value")
            i += 2
            continue
        raise ValueError(
            f"{context}: policy option {option!r} is not ordering-only; "
            "put position and proof-semantics options in task args"
        )


def exact_returncode(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value in {0, 1}


def exact_result(result: object) -> bool:
    if not isinstance(result, dict):
        return False
    solved = result.get("solved")
    timeout = result.get("timeout")
    if not (isinstance(solved, int) and not isinstance(solved, bool) and solved in {0, 1}):
        return False
    if not (isinstance(timeout, int) and not isinstance(timeout, bool) and timeout == 0):
        return False
    if solved == 1:
        winner = result.get("winner")
        if not (isinstance(winner, int) and not isinstance(winner, bool) and winner in {1, 2}):
            return False
    elif result.get("winner") is not None:
        return False
    return stalemate_counter_ok(result)


def cached_winner_valid(record: dict[str, Any]) -> bool:
    if not isinstance(record,dict):return False
    result = record.get("winner_result")
    policy = record.get("winner_policy")
    if not exact_result(result):
        return False
    policy_spec=next((item for item in record.get("policies",[]) if isinstance(item,dict) and item.get("name")==policy),None)
    if policy_spec is None or not isinstance(record.get("task_args"),list) or not isinstance(record.get("solver"),str):return False
    expected_command=[record["solver"],*map(str,record["task_args"]),*map(str,policy_spec.get("args",[]))]
    return any(
        variant.get("policy") == policy
        and exact_returncode(variant.get("returncode"))
        and variant.get("cancelled") is not True
        and variant.get("result") == result
        and variant.get("command")==expected_command
        and isinstance(variant.get("stdout"),str)
        and parsed_result(variant["stdout"])==result
        for variant in record.get("variants", [])
        if isinstance(variant, dict)
    )


def load_tasks(path: Path) -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []
    for no, raw in enumerate(path.read_text().splitlines(), 1):
        raw = raw.strip()
        if not raw or raw.startswith("#"):
            continue
        task = json.loads(raw)
        if not isinstance(task,dict):raise ValueError(f"invalid task at {path}:{no}: root must be an object")
        if not isinstance(task.get("id"), str) or not isinstance(task.get("args"), list):
            raise ValueError(f"invalid task at {path}:{no}")
        raw_env=task.get("env",{})
        if not isinstance(raw_env,dict):raise ValueError(f"invalid env at {path}:{no}")
        task["env"]={str(key):str(value) for key,value in sorted(raw_env.items(),key=lambda item:str(item[0]))}
        policies = task.get("policies")
        if policies is None:
            weights = task.get("weights", [0, 40])
            if not isinstance(weights, list) or not weights:
                raise ValueError(f"invalid weights at {path}:{no}")
            policies = [
                {"name": f"choice_{int(weight)}", "args": ["--path-choice-weight", str(int(weight))]}
                for weight in weights
            ]
        if not isinstance(policies, list) or not policies:
            raise ValueError(f"invalid policies at {path}:{no}")
        names: set[str] = set()
        normalized = []
        for policy in policies:
            if not isinstance(policy, dict) or not isinstance(policy.get("name"), str) or not isinstance(policy.get("args"), list):
                raise ValueError(f"invalid policy at {path}:{no}")
            name = policy["name"]
            if not name:
                raise ValueError(f"empty policy name at {path}:{no}")
            if name in names:
                raise ValueError(f"duplicate policy {name!r} at {path}:{no}")
            names.add(name)
            policy_args = [str(x) for x in policy["args"]]
            validate_policy_args(policy_args, f"{path}:{no} policy {name!r}")
            normalized.append({"name": name, "args": policy_args})
        task["policies"] = normalized
        tasks.append(task)
    if not tasks:raise ValueError("manifest must contain at least one task")
    ids=[safe_id(task["id"]) for task in tasks]
    if len(ids)!=len(set(ids)):raise ValueError("task ids must remain unique after filename normalization")
    if set(ids)&{"campaign","summary","portfolio_aggregate","portfolio_summary"}:raise ValueError("task id collides with a reserved output name")
    return tasks


def append_policy_overlays(tasks: list[dict[str, Any]], specifications: list[str]) -> None:
    for index, raw in enumerate(specifications, 1):
        try:
            policy = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid appended policy JSON #{index}: {exc}") from exc
        if not isinstance(policy, dict) or not isinstance(policy.get("name"), str) or not isinstance(policy.get("args"), list):
            raise ValueError(f"invalid appended policy #{index}: expected name and args list")
        normalized = {"name": policy["name"], "args": [str(x) for x in policy["args"]]}
        if not normalized["name"]:
            raise ValueError(f"invalid appended policy #{index}: name must not be empty")
        validate_policy_args(normalized["args"], f"appended policy {normalized['name']!r}")
        for task in tasks:
            if any(existing["name"] == normalized["name"] for existing in task["policies"]):
                raise ValueError(f"duplicate appended policy {normalized['name']!r} in task {task['id']!r}")
            task["policies"].append({"name": normalized["name"], "args": list(normalized["args"])})


def select_tasks(tasks: list[dict[str, Any]], requested: list[str]) -> list[dict[str, Any]]:
    if not requested:
        return tasks
    if len(requested) != len(set(requested)):
        raise ValueError("--task-id values must be unique")
    by_id = {task["id"]: task for task in tasks}
    missing = [task_id for task_id in requested if task_id not in by_id]
    if missing:
        raise ValueError(f"unknown --task-id values: {', '.join(missing)}")
    return [by_id[task_id] for task_id in requested]


def kill_process(proc: subprocess.Popen[str]) -> None:
    if proc.poll() is not None:
        return
    if os.name == "nt":
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
        return
    try:
        os.killpg(proc.pid, signal.SIGTERM)
        proc.wait(timeout=3)
    except (ProcessLookupError, subprocess.TimeoutExpired):
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def bind_campaign(outdir: Path, identity: dict[str, Any], force: bool) -> None:
    path = outdir / "campaign.json"
    if path.exists():
        try:
            old = json.loads(path.read_text())
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"malformed campaign identity {path}") from exc
        if old != identity:
            raise RuntimeError(f"campaign identity mismatch in {path}; use a fresh --outdir")
        return
    existing = [
        p for p in outdir.glob("*.json")
        if p.name not in {"summary.json", "portfolio_aggregate.json"}
    ]
    if existing and not force:
        raise RuntimeError(
            f"unbound portfolio records already exist in {outdir}; "
            "use --force once to adopt them or use a fresh --outdir"
        )
    atomic_json(path, identity)


def harvest_completed(running: dict[int, dict[str, Any]], variants: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for pid, row in list(running.items()):
        proc: subprocess.Popen[str] = row["proc"]
        rc = proc.poll()
        if rc is None:
            continue
        stdout, stderr = proc.communicate()
        result = parsed_result(stdout)
        item = {
            "policy": row["policy"], "policy_args": row["policy_args"],
            "command": row["command"], "returncode": rc,
            "elapsed_wall_seconds": time.monotonic() - row["started"],
            "result": result, "stdout": stdout, "stderr": stderr,
        }
        variants.append(item)
        del running[pid]
        if exact_returncode(rc) and exact_result(result):
            solver_seconds = result.get("seconds") if isinstance(result, dict) else None
            elapsed = float(solver_seconds) if isinstance(solver_seconds, (int, float)) else item["elapsed_wall_seconds"]
            item["_finish_estimate"] = row["started"] + elapsed
            candidates.append(item)
    return candidates


def run_portfolio(task: dict[str, Any], solver: Path, solver_hash: str,
                  worker_hash: str, parser_hash: str, worker_bundle_hash: str, outdir: Path,
                  default_timeout: float, force: bool) -> dict[str, Any]:
    tid = task["id"]
    record_path = outdir / f"{safe_id(tid)}.json"
    env_overlay=task["env"]
    if record_path.exists() and not force:
        try:
            old = json.loads(record_path.read_text())
            if (isinstance(old,dict) and old.get("status") == "completed" and old.get("id")==tid
                    and old.get("solver_sha256") == solver_hash
                    and old.get("worker_bundle_sha256") == worker_bundle_hash
                    and old.get("env")==env_overlay
                    and old.get("task_args") == task.get("args")
                    and old.get("policies") == task.get("policies")
                    and cached_winner_valid(old)):
                return {"id": tid, "status": "skipped", "path": str(record_path)}
        except json.JSONDecodeError:
            raise RuntimeError(f"malformed cached record {record_path}; use --force or a fresh --outdir")
        if not isinstance(old,dict):raise RuntimeError(f"cached record {record_path} must be an object; use --force or a fresh --outdir")
        same_identity=(old.get("id")==tid and old.get("solver_sha256")==solver_hash
                       and old.get("worker_bundle_sha256")==worker_bundle_hash
                       and old.get("task_args")==task.get("args") and old.get("policies")==task.get("policies")
                       and old.get("env")==env_overlay)
        if not same_identity or old.get("status")=="completed":
            raise RuntimeError(f"refusing to overwrite stale or completed record: {record_path}")

    timeout = float(task.get("timeout", default_timeout))
    base = [str(x) for x in task["args"]]
    if any(x in base for x in ("--root-index", "--root-index2", "--root-index3")):
        raise ValueError(f"{tid}: portfolio tasks must use stable --*-move labels, not indices")
    env = os.environ.copy()
    env.update(env_overlay)
    started = time.monotonic()
    running: dict[int, dict[str, Any]] = {}
    variants: list[dict[str, Any]] = []

    for policy in task["policies"]:
        command = [str(solver), *base, *policy["args"]]
        proc = subprocess.Popen(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                env=env, start_new_session=True)
        running[proc.pid] = {"policy": policy["name"], "policy_args": policy["args"],
                             "command": command, "proc": proc, "started": time.monotonic()}

    winner: dict[str, Any] | None = None
    try:
        while running and time.monotonic() - started < timeout:
            completed_candidates = harvest_completed(running, variants)
            if completed_candidates:
                time.sleep(CO_WINNER_GRACE_SECONDS)
                completed_candidates.extend(harvest_completed(running, variants))
                winner = min(completed_candidates, key=lambda item: (item["_finish_estimate"], item["policy"]))
                break
            time.sleep(0.05)
    finally:
        for row in running.values():
            proc = row["proc"]
            was_running = proc.poll() is None
            kill_process(proc)
            stdout, stderr = proc.communicate()
            variants.append({
                "policy": row["policy"], "policy_args": row["policy_args"],
                "command": row["command"], "returncode": proc.returncode,
                "cancelled": winner is not None and was_running,
                "elapsed_wall_seconds": time.monotonic() - row["started"],
                "result": parsed_result(stdout), "stdout": stdout, "stderr": stderr,
            })

    for item in variants:
        item.pop("_finish_estimate", None)
    record = {
        "id": tid,
        "status": "completed" if winner else "timeout_or_failure",
        "solver": str(solver),
        "solver_sha256": solver_hash,
        "worker_sha256": worker_hash,
        "parser_sha256": parser_hash,
        "worker_bundle_sha256": worker_bundle_hash,
        "task_args": task.get("args"),
        "env": env_overlay,
        "policies": task.get("policies"),
        "elapsed_wall_seconds": time.monotonic() - started,
        "winner_policy": winner["policy"] if winner else None,
        "winner_result": winner["result"] if winner else None,
        "variants": sorted(variants, key=lambda x: x["policy"]),
        "notes": task.get("notes"),
    }
    atomic_json(record_path, record)
    return {"id": tid, "status": record["status"], "winner_policy": record["winner_policy"],
            "elapsed": record["elapsed_wall_seconds"], "path": str(record_path)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--solver", type=Path, default=Path("bin/lazy_specialized_solver"))
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--outdir", type=Path, required=True)
    ap.add_argument("--jobs", type=int, default=1,
                    help="Concurrent portfolio tasks; actual processes = jobs × policies per task")
    ap.add_argument("--timeout", type=float, default=3600)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--append-policy-json", action="append", default=[], metavar="JSON",
                    help="append one {name,args} policy to every manifest task; repeatable")
    ap.add_argument("--append-policy-file", action="append", default=[], type=Path, metavar="PATH",
                    help="append a policy read from a JSON file; repeatable")
    ap.add_argument("--task-id", action="append", default=[], metavar="ID",
                    help="run only the named manifest task; repeatable")
    args = ap.parse_args()
    solver = args.solver.resolve()
    if not solver.is_file():
        ap.error(f"solver not found: {solver}")
    all_tasks = load_tasks(args.manifest)
    try:
        overlay_specs = list(args.append_policy_json)
        overlay_specs.extend(path.read_text(encoding="utf-8") for path in args.append_policy_file)
        append_policy_overlays(all_tasks, overlay_specs)
        tasks = select_tasks(all_tasks, args.task_id)
    except (OSError, ValueError) as exc:
        ap.error(str(exc))
    digest = sha256(solver)
    worker_path = Path(__file__).resolve()
    parser_path = worker_path.with_name("solver_output.py")
    worker_digest = sha256(worker_path)
    parser_digest = sha256(parser_path)
    worker_bundle_digest = json_sha256({
        "codex_portfolio_worker.py": worker_digest,
        "solver_output.py": parser_digest,
    })
    args.outdir.mkdir(parents=True, exist_ok=True)
    campaign_identity = {
        "schema_version": 1,
        "manifest_sha256": sha256(args.manifest),
        "task_universe_sha256": json_sha256(all_tasks),
        "solver_sha256": digest,
        "worker_bundle_sha256": worker_bundle_digest,
    }
    try:
        bind_campaign(args.outdir, campaign_identity, args.force)
    except RuntimeError as exc:
        ap.error(str(exc))
    print(json.dumps({"solver": str(solver), "sha256": digest,
                      "worker_sha256": worker_digest, "parser_sha256": parser_digest,
                      "worker_bundle_sha256": worker_bundle_digest,
                      "tasks": len(tasks),
                      "task_jobs": args.jobs}), flush=True)
    failed = 0
    with cf.ThreadPoolExecutor(max_workers=max(1, args.jobs)) as pool:
        futures = [pool.submit(run_portfolio, t, solver, digest, worker_digest,
                               parser_digest, worker_bundle_digest, args.outdir,
                               args.timeout, args.force) for t in tasks]
        for future in cf.as_completed(futures):
            row = future.result()
            print(json.dumps(row, sort_keys=True), flush=True)
            failed += row["status"] not in {"completed","skipped"}
    atomic_json(args.outdir / "summary.json", {
        "solver_sha256": digest, "worker_sha256": worker_digest,
        "parser_sha256": parser_digest, "worker_bundle_sha256": worker_bundle_digest,
        "campaign": campaign_identity,
        "task_ids": [task["id"] for task in tasks],
        "tasks": len(tasks), "failed": failed,
        "completed_unix": time.time(),
    })
    return 0 if failed == 0 else 3


if __name__ == "__main__":
    raise SystemExit(main())
