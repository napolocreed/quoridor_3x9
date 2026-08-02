#!/usr/bin/env python3
"""Resumable bounded refutation of one named 4x7x7 central line.

The dense solver still selects the two prefix moves by index. This harness binds
those indices to the labels printed by the exact binary, binds every cached
third move to the enumeration command and solver hash, and never reuses a
branch record from another campaign.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from solver_output import COUNTER_OK, KV_RE, SEMANTIC_VIOLATION, parse_key_value_line, stalemate_counter_status


LIST_RE = re.compile(r"third\[(?P<index>\d+)\] move=(?P<move>\S+) score=(?P<score>-?\d+)")
FORCE_RE = re.compile(r"forcing (?P<level>root|second)\[(?P<index>\d+)\] move=(?P<move>\S+)")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def json_digest(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def atomic_json(path: Path, data: object) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    os.replace(tmp, path)


def read_object(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text())
    except FileNotFoundError:
        return None
    except json.JSONDecodeError as error:
        raise RuntimeError(f"malformed JSON cache: {path}") from error
    if not isinstance(value, dict):
        raise RuntimeError(f"cache root must be an object: {path}")
    return value


def list_command(args: argparse.Namespace) -> list[str]:
    return [
        str(args.solver), "--width", "4", "--height", "7", "--walls", "7",
        "--root-index", str(args.root_index), "--root-index2", str(args.reply_index),
        "--list-third", "--order", str(args.order),
    ]


def scan_command(args: argparse.Namespace, first: int, last: int) -> list[str]:
    return [
        str(args.solver), "--width", "4", "--height", "7", "--walls", "7",
        "--root-index", str(args.root_index), "--root-index2", str(args.reply_index),
        "--target", "1", "--child-depth", str(args.remaining_depth),
        "--seconds", str(args.seconds_per_branch), "--tt-bits", str(args.tt_bits),
        "--order", str(args.order), "--no-bounds", "--no-pawn-table",
        "--scan-current", "--scan-root-start", str(first), "--scan-root-end", str(last),
    ]


def valid_move_rows(rows: object) -> bool:
    return (
        isinstance(rows, list)
        and bool(rows)
        and all(isinstance(row, dict) and type(row.get("index")) is int
                and isinstance(row.get("move"), str) and type(row.get("score")) is int for row in rows)
        and [row["index"] for row in rows] == list(range(len(rows)))
        and len({row["move"] for row in rows}) == len(rows)
    )


def parse_third_listing(stdout:str,stderr:str)->tuple[list[dict[str,Any]],list[re.Match[str]],dict[str,tuple[int,str]]]:
    combined=stderr+"\n"+stdout
    rows=[
        {"index":int(match.group("index")),"move":match.group("move"),"score":int(match.group("score"))}
        for match in LIST_RE.finditer(combined)
    ]
    forced_matches=list(FORCE_RE.finditer(combined))
    forced={
        match.group("level"):(int(match.group("index")),match.group("move"))
        for match in forced_matches
    }
    return rows,forced_matches,forced


def list_moves(args: argparse.Namespace, outdir: Path, solver_hash: str) -> dict[str, Any]:
    cache = outdir / "third_moves.json"
    command = list_command(args)
    cached = read_object(cache)
    if cached is not None:
        rows = cached.get("moves")
        raw_stdout=cached.get("stdout");raw_stderr=cached.get("stderr")
        if isinstance(raw_stdout,str) and isinstance(raw_stderr,str):
            raw_rows,forced_matches,forced=parse_third_listing(raw_stdout,raw_stderr)
        else:
            raw_rows,forced_matches,forced=[],[],{}
        valid = (
            type(cached.get("schema_version")) is int
            and cached.get("schema_version") == 1
            and cached.get("solver_sha256") == solver_hash
            and cached.get("command") == command
            and cached.get("root_index") == args.root_index
            and cached.get("reply_index") == args.reply_index
            and cached.get("root_move") == args.expected_root_move
            and cached.get("reply_move") == args.expected_reply_move
            and cached.get("order") == args.order
            and valid_move_rows(rows)
            and raw_rows==rows
            and len(forced_matches)==2
            and forced=={
                "root":(args.root_index,args.expected_root_move),
                "second":(args.reply_index,args.expected_reply_move),
            }
            and cached.get("moves_sha256") == json_digest(rows)
            and isinstance(cached.get("root_move"), str)
            and isinstance(cached.get("reply_move"), str)
        )
        if not valid:
            raise RuntimeError(f"refusing stale or legacy move cache; use a fresh --outdir: {cache}")
        return cached

    completed = subprocess.run(
        command, text=True, capture_output=True,
        timeout=args.precompute_timeout, check=False,
    )
    rows,forced_matches,forced=parse_third_listing(completed.stdout,completed.stderr)
    if (
        completed.returncode != 0
        or not valid_move_rows(rows)
        or len(forced_matches) != 2
        or set(forced) != {"root", "second"}
        or forced.get("root", (None,))[0] != args.root_index
        or forced.get("second", (None,))[0] != args.reply_index
        or forced.get("root", (None, None))[1] != args.expected_root_move
        or forced.get("second", (None, None))[1] != args.expected_reply_move
    ):
        raise RuntimeError(f"could not enumerate bound third moves (rc={completed.returncode})\n{completed.stderr[-2000:]}")
    listing = {
        "schema_version": 1,
        "solver_sha256": solver_hash,
        "command": command,
        "root_index": args.root_index,
        "root_move": forced["root"][1],
        "reply_index": args.reply_index,
        "reply_move": forced["second"][1],
        "order": args.order,
        "moves_sha256": json_digest(rows),
        "moves": rows,
        "stdout":completed.stdout,
        "stderr":completed.stderr,
    }
    atomic_json(cache, listing)
    return listing


def campaign_metadata(args: argparse.Namespace, solver_hash: str, listing: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "solver": str(args.solver),
        "solver_sha256": solver_hash,
        "width": 4,
        "height": 7,
        "walls_per_player": 7,
        "root_index": args.root_index,
        "root_move": listing["root_move"],
        "reply_index": args.reply_index,
        "reply_move": listing["reply_move"],
        "target": 1,
        "remaining_depth": args.remaining_depth,
        "total_suffix": args.remaining_depth + 1,
        "seconds_per_branch": args.seconds_per_branch,
        "tt_bits": args.tt_bits,
        "order": args.order,
        "no_bounds": True,
        "no_pawn_table": True,
        "moves_sha256": listing["moves_sha256"],
        "third_moves": len(listing["moves"]),
    }


def command_value(command: list[Any], flag: str) -> str | None:
    positions = [index for index, value in enumerate(command) if value == flag]
    if len(positions) != 1 or positions[0] + 1 >= len(command):
        return None
    return str(command[positions[0] + 1])


def command_matches(command: object, campaign: dict[str, Any], task: int) -> bool:
    if not isinstance(command, list):
        return False
    seconds_per_branch = campaign.get("seconds_per_branch")
    if type(seconds_per_branch) is not int:
        return False
    try:
        first = int(command_value(command, "--scan-root-start") or "")
        last = int(command_value(command, "--scan-root-end") or "")
    except ValueError:
        return False
    expected = [
        campaign["solver"], "--width", "4", "--height", "7", "--walls", "7",
        "--root-index", str(campaign["root_index"]),
        "--root-index2", str(campaign["reply_index"]),
        "--target", "1", "--child-depth", str(campaign["remaining_depth"]),
        "--seconds", str(seconds_per_branch), "--tt-bits", str(campaign["tt_bits"]),
        "--order", str(campaign["order"]), "--no-bounds", "--no-pawn-table",
        "--scan-current", "--scan-root-start", str(first), "--scan-root-end", str(last),
    ]
    return (
        command == expected
        and type(campaign.get("third_moves")) is int
        and 0 <= first <= task <= last < campaign["third_moves"]
    )


def nonnegative_int(value: object) -> bool:
    return type(value) is int and value >= 0


def nonnegative_finite_number(value: object) -> bool:
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def parsed_branch_line(
    line: object,
    campaign: dict[str, Any],
    move: dict[str, Any],
) -> dict[str, Any] | None:
    if not isinstance(line, str) or not line.startswith("current_scan "):
        return None
    keys = [match.group("key") for match in KV_RE.finditer(line)]
    if len(keys) != len(set(keys)):
        return None
    parsed = parse_key_value_line(line)
    required = {
        "task", "rep", "aliases", "move", "proven", "timeout", "nodes",
        "tt_hits", "stalemates_seen", "seconds", "child_depth", "total_suffix",
    }
    task = move["index"]
    if not required.issubset(parsed):
        return None
    if (
        type(parsed["task"]) is not int
        or parsed["task"] != task
        or type(parsed["rep"]) is not int
        or parsed["rep"] != task
        or type(parsed["aliases"]) is not int
        or parsed["aliases"] != task
        or not isinstance(parsed["move"], str)
        or parsed["move"] != move["move"]
        or type(parsed["proven"]) is not int
        or parsed["proven"] not in (0, 1)
        or type(parsed["timeout"]) is not int
        or parsed["timeout"] not in (0, 1)
        or (parsed["proven"] == 1 and parsed["timeout"] == 1)
        or not nonnegative_int(parsed["nodes"])
        or not nonnegative_int(parsed["tt_hits"])
        or stalemate_counter_status(parsed) != COUNTER_OK
        or not nonnegative_finite_number(parsed["seconds"])
        or type(parsed["child_depth"]) is not int
        or parsed["child_depth"] != campaign["remaining_depth"]
        or type(parsed["total_suffix"]) is not int
        or parsed["total_suffix"] != campaign["total_suffix"]
    ):
        return None
    return parsed


def chunk_evidence_valid(path:Path,row:dict[str,Any],campaign:dict[str,Any])->bool:
    evidence=row.get("chunk_evidence")
    if not isinstance(evidence,dict):return False
    stdout_name=evidence.get("stdout_file");stderr_name=evidence.get("stderr_file")
    if (not isinstance(stdout_name,str) or not isinstance(stderr_name,str)
            or Path(stdout_name).name!=stdout_name or Path(stderr_name).name!=stderr_name):
        return False
    stdout_path=path.parent/stdout_name;stderr_path=path.parent/stderr_name
    try:stdout=stdout_path.read_text();stderr=stderr_path.read_text()
    except OSError:return False
    if (evidence.get("stdout_sha256")!=sha256(stdout_path)
            or evidence.get("stderr_sha256")!=sha256(stderr_path)):
        return False
    line=row.get("raw_result_line")
    if not isinstance(line,str) or stdout.splitlines().count(line)!=1:return False
    forced_matches=list(FORCE_RE.finditer(stderr))
    forced={m.group("level"):(int(m.group("index")),m.group("move")) for m in forced_matches}
    if (len(forced_matches)!=2 or forced!={
            "root":(campaign["root_index"],campaign["root_move"]),
            "second":(campaign["reply_index"],campaign["reply_move"]),
        }):return False
    if (type(evidence.get("external_timeout")) is not bool
            or evidence["external_timeout"]!=row.get("external_chunk_timeout")):
        return False
    rc=evidence.get("returncode")
    if evidence["external_timeout"]:
        return rc is None
    return type(rc) is int and not isinstance(rc,bool) and rc in (0,1,3)


def classify_record(path: Path, campaign: dict[str, Any], move: dict[str, Any]) -> tuple[str, dict[str, Any]] | None:
    row = read_object(path)
    if row is None:
        return None
    task = move["index"]
    parsed = parsed_branch_line(row.get("raw_result_line"), campaign, move)
    if parsed is None:
        return None
    parsed_proven = parsed["proven"] == 1
    parsed_timeout = parsed["timeout"] == 1
    binding_ok = (
        row.get("campaign") == campaign
        and row.get("solver_sha256") == campaign["solver_sha256"]
        and row.get("task") == task
        and row.get("representative") == task
        and str(row.get("aliases")) == str(task)
        and row.get("move") == move["move"]
        and row.get("child_depth") == campaign["remaining_depth"]
        and row.get("total_suffix") == campaign["total_suffix"]
        and row.get("distance_bound") is False
        and row.get("pawn_only_table") is False
        and row.get("fresh_tt") is True
        and command_matches(row.get("command"), campaign, task)
        and type(row.get("external_chunk_timeout")) is bool
        and row.get("stalemate_counter_status") == COUNTER_OK
        and chunk_evidence_valid(path,row,campaign)
        and nonnegative_int(row.get("nodes"))
        and row.get("nodes") == parsed["nodes"]
        and nonnegative_int(row.get("tt_hits"))
        and row.get("tt_hits") == parsed["tt_hits"]
        and nonnegative_int(row.get("stalemates_seen"))
        and row.get("stalemates_seen") == parsed["stalemates_seen"]
        and nonnegative_finite_number(row.get("seconds"))
        and float(row["seconds"]) == float(parsed["seconds"])
    )
    if not binding_ok:
        return None
    if type(row.get("proven")) is not bool or type(row.get("timeout")) is not bool:
        return None
    if row["proven"] != parsed_proven or row["timeout"] != parsed_timeout:
        return None
    if row["timeout"] or stalemate_counter_status(row) != COUNTER_OK:
        return None
    derived = "proved" if row["proven"] else "refuted"
    if row.get("status") != derived:
        return None
    return derived, row


def retryable_record(path: Path, campaign: dict[str, Any], move: dict[str, Any]) -> bool:
    row = read_object(path)
    if row is None:
        return False
    return (
        row.get("campaign") == campaign
        and row.get("task") == move["index"]
        and row.get("move") == move["move"]
        and row.get("status") == "unresolved"
        and row.get("timeout") is True
        and stalemate_counter_status(row) != SEMANTIC_VIOLATION
    )


def archive_attempt(path: Path) -> None:
    token = time.time_ns()
    shutil.move(path, path.parent / f"{path.stem}.attempt-{token}{path.suffix}")


def run_chunk(
    args: argparse.Namespace,
    outdir: Path,
    first: int,
    last: int,
    campaign: dict[str, Any],
    moves: list[dict[str, Any]],
) -> None:
    command = scan_command(args, first, last)
    started_ns=time.time_ns();started = time.time()
    wall_timeout = args.precompute_timeout + args.seconds_per_branch * (last - first + 1) + args.timeout_grace
    try:
        completed = subprocess.run(command, text=True, capture_output=True, timeout=wall_timeout, check=False)
        stdout, stderr = completed.stdout, completed.stderr
        external_timeout, returncode = False, completed.returncode
    except subprocess.TimeoutExpired as error:
        stdout, stderr = error.stdout or "", error.stderr or ""
        external_timeout, returncode = True, None
        if isinstance(stdout, bytes):
            stdout = stdout.decode(errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode(errors="replace")
    stamp = f"chunk_{first:02d}_{last:02d}_{started_ns}"
    stdout_path=outdir/f"{stamp}.out";stderr_path=outdir/f"{stamp}.err"
    stdout_path.write_text(stdout);stderr_path.write_text(stderr)
    chunk_evidence={
        "stdout_file":stdout_path.name,"stdout_sha256":sha256(stdout_path),
        "stderr_file":stderr_path.name,"stderr_sha256":sha256(stderr_path),
        "returncode":returncode,"external_timeout":external_timeout,
    }

    parsed_rows: list[tuple[str, dict[str, Any], dict[str, Any]]] = []
    found: set[int] = set()
    for line in stdout.splitlines():
        if not line.startswith("current_scan "):
            continue
        preliminary = parse_key_value_line(line)
        task = preliminary.get("task")
        if type(task) is not int or not first <= task <= last or task >= len(moves):
            raise RuntimeError(f"current_scan task outside requested range: {task!r}")
        expected = moves[task]
        parsed = parsed_branch_line(line, campaign, expected)
        if parsed is None:
            raise RuntimeError(f"malformed or misbound current_scan row: {line}")
        if task in found:
            raise RuntimeError(f"duplicate current_scan task: {task}")
        found.add(task)
        parsed_rows.append((line, parsed, expected))

    if not parsed_rows:
        raise RuntimeError(f"chunk {first}-{last} returned no parseable branch rows")

    emitted = [parsed["task"] for _, parsed, _ in parsed_rows]
    if emitted != list(range(first, emitted[-1] + 1)):
        raise RuntimeError(f"chunk {first}-{last} emitted a non-contiguous task sequence: {emitted}")
    proved_rows = [parsed for _, parsed, _ in parsed_rows if parsed["proven"] == 1]
    if len(proved_rows) > 1 or (proved_rows and parsed_rows[-1][1]["proven"] != 1):
        raise RuntimeError(f"chunk {first}-{last} did not stop at its first proved branch")
    if not external_timeout and not proved_rows and emitted[-1] != last:
        raise RuntimeError(f"completed chunk {first}-{last} omitted tasks after {emitted[-1]}")

    summary_lines = [line for line in stdout.splitlines() if line.startswith("current_scan_result ")]
    if not external_timeout:
        if len(summary_lines) != 1:
            raise RuntimeError(f"chunk {first}-{last} returned {len(summary_lines)} scan summaries")
        summary_keys = [match.group("key") for match in KV_RE.finditer(summary_lines[0])]
        if len(summary_keys) != len(set(summary_keys)):
            raise RuntimeError(f"duplicate field in scan summary: {summary_lines[0]}")
        summary = parse_key_value_line(summary_lines[0])
        summary_required = {
            "proven", "refuted", "child_proved", "child_refuted", "child_unresolved",
            "aggregate_nodes", "stalemates_seen", "aggregate_seconds", "total_suffix",
            "range", "tasks", "raw", "unique",
        }
        if not summary_required.issubset(summary):
            raise RuntimeError(f"incomplete scan summary: {summary}")
        child_proved = sum(parsed["proven"] == 1 for _, parsed, _ in parsed_rows)
        child_unresolved = sum(parsed["timeout"] == 1 for _, parsed, _ in parsed_rows)
        child_refuted = len(parsed_rows) - child_proved - child_unresolved
        complete_range = first == 0 and last == len(moves) - 1
        bounded_proof = child_proved > 0
        bounded_refutation = child_proved == 0 and child_unresolved == 0 and complete_range
        aggregate_nodes = sum(parsed["nodes"] for _, parsed, _ in parsed_rows)
        aggregate_stalemates = sum(parsed["stalemates_seen"] for _, parsed, _ in parsed_rows)
        aggregate_seconds = sum(float(parsed["seconds"]) for _, parsed, _ in parsed_rows)
        expected_returncode = 0 if bounded_proof else (3 if child_unresolved else 1)
        exact_summary = (
            type(summary["proven"]) is int
            and summary["proven"] == int(bounded_proof)
            and type(summary["refuted"]) is int
            and summary["refuted"] == int(bounded_refutation)
            and type(summary["child_proved"]) is int
            and summary["child_proved"] == child_proved
            and type(summary["child_refuted"]) is int
            and summary["child_refuted"] == child_refuted
            and type(summary["child_unresolved"]) is int
            and summary["child_unresolved"] == child_unresolved
            and type(summary["aggregate_nodes"]) is int
            and summary["aggregate_nodes"] == aggregate_nodes
            and type(summary["stalemates_seen"]) is int
            and summary["stalemates_seen"] == aggregate_stalemates
            and nonnegative_finite_number(summary["aggregate_seconds"])
            and math.isclose(
                float(summary["aggregate_seconds"]), aggregate_seconds,
                rel_tol=1e-4, abs_tol=1e-5 * max(1, len(parsed_rows)),
            )
            and type(summary["total_suffix"]) is int
            and summary["total_suffix"] == campaign["total_suffix"]
            and summary["range"] == f"{first}-{last}"
            and type(summary["tasks"]) is int
            and summary["tasks"] == len(moves)
            and type(summary["raw"]) is int
            and summary["raw"] == len(moves)
            and type(summary["unique"]) is int
            and summary["unique"] == 0
            and type(returncode) is int
            and returncode == expected_returncode
        )
        if not exact_summary:
            raise RuntimeError(
                f"scan summary/return code does not match emitted rows "
                f"(rc={returncode}, expected_rc={expected_returncode}): {summary}"
            )

    record_paths = [outdir / f"third_{parsed['task']:02d}.json" for _, parsed, _ in parsed_rows]
    existing = [path for path in record_paths if path.exists()]
    if existing:
        raise RuntimeError(f"refusing to overwrite branch record: {existing[0]}")

    for (line, parsed, expected), record_path in zip(parsed_rows, record_paths):
        task = parsed["task"]
        proven = parsed["proven"] == 1
        timeout = parsed["timeout"] == 1
        row = {
            "status": "unresolved" if timeout else ("proved" if proven else "refuted"),
            "task": task,
            "representative": task,
            "aliases": str(task),
            "move": expected["move"],
            "proven": proven,
            "timeout": timeout,
            "nodes": parsed["nodes"],
            "tt_hits": parsed["tt_hits"],
            "stalemates_seen": parsed["stalemates_seen"],
            "stalemate_counter_status": COUNTER_OK,
            "seconds": float(parsed["seconds"]),
            "child_depth": campaign["remaining_depth"],
            "total_suffix": campaign["total_suffix"],
            "solver_sha256": campaign["solver_sha256"],
            "distance_bound": False,
            "pawn_only_table": False,
            "fresh_tt": True,
            "command": command,
            "external_chunk_timeout": external_timeout,
            "chunk_evidence":chunk_evidence,
            "campaign": campaign,
            "raw_result_line": line,
        }
        atomic_json(record_path, row)
        print(json.dumps(row, sort_keys=True), flush=True)


def write_summary(
    args: argparse.Namespace,
    outdir: Path,
    campaign: dict[str, Any],
    moves: list[dict[str, Any]],
    classified: dict[int, tuple[str, dict[str, Any]]],
) -> dict[str, Any]:
    rows = [classified[index][1] for index in sorted(classified)]
    refuted = [row for row in rows if row["status"] == "refuted"]
    proved = [row for row in rows if row["status"] == "proved"]
    coverage_complete = len(rows) == len(moves)
    all_refuted = coverage_complete and not proved and len(refuted) == len(moves)
    classified_counters_ok = bool(rows) and all(stalemate_counter_status(row) == COUNTER_OK for row in rows)
    counters_complete_and_zero = coverage_complete and classified_counters_ok
    summary = {
        "all_third_moves_refuted": all_refuted,
        "coverage_complete": coverage_complete,
        "campaign": campaign,
        "variant": {"width": 4, "height": 7, "walls_per_player": 7},
        "opening": {"index": campaign["root_index"], "move": campaign["root_move"]},
        "opponent_reply": {"index": campaign["reply_index"], "move": campaign["reply_move"]},
        "first_player_opening_not_forced_within_plies": args.remaining_depth + 3 if all_refuted else None,
        "third_moves": len(moves),
        "classified": len(rows),
        "refuted": len(refuted),
        "proved": len(proved),
        "proved_third_moves": [{"task": row["task"], "move": row["move"]} for row in proved],
        "aggregate_nodes": sum(row["nodes"] for row in rows),
        "aggregate_tt_hits": sum(row["tt_hits"] for row in rows),
        "aggregate_stalemates_seen": sum(row["stalemates_seen"] for row in rows) if classified_counters_ok else None,
        "stalemate_counters_complete_and_zero": counters_complete_and_zero,
        "aggregate_search_seconds": sum(row["seconds"] for row in rows),
        "solver_sha256": campaign["solver_sha256"],
        "no_bounds": True,
        "no_pawn_table": True,
        "fresh_tt_per_third_move": True,
    }
    atomic_json(outdir / "summary.json", summary)
    print(json.dumps(summary, sort_keys=True))
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--solver", type=Path, default=Path("bin/frontier_solver"))
    parser.add_argument("--outdir", type=Path, default=Path("results/4x7_w7/audit_central_depth27"))
    parser.add_argument("--root-index", type=int, default=0)
    parser.add_argument("--reply-index", type=int, default=0)
    parser.add_argument("--expected-root-move", default="P(5,2)")
    parser.add_argument("--expected-reply-move", default="P(1,2)")
    parser.add_argument("--remaining-depth", type=int, default=24)
    parser.add_argument("--seconds-per-branch", type=int, default=300)
    parser.add_argument("--precompute-timeout", type=int, default=180)
    parser.add_argument("--timeout-grace", type=int, default=60)
    parser.add_argument("--tt-bits", type=int, default=27)
    parser.add_argument("--order", type=int, default=1)
    parser.add_argument("--chunk-size", type=int, default=5)
    parser.add_argument("--max-attempts", type=int, default=3)
    args = parser.parse_args()
    if args.chunk_size < 1 or args.max_attempts < 1:
        parser.error("--chunk-size and --max-attempts must be positive")
    args.solver = args.solver.resolve()
    if not args.solver.is_file():
        parser.error(f"solver not found: {args.solver}")
    args.outdir.mkdir(parents=True, exist_ok=True)
    solver_hash = sha256(args.solver)
    listing = list_moves(args, args.outdir, solver_hash)
    moves = listing["moves"]
    campaign = campaign_metadata(args, solver_hash, listing)

    while True:
        classified: dict[int, tuple[str, dict[str, Any]]] = {}
        missing: list[int] = []
        exhausted = False
        for move in moves:
            path = args.outdir / f"third_{move['index']:02d}.json"
            classification = classify_record(path, campaign, move)
            if classification is not None:
                classified[move["index"]] = classification
                continue
            if path.exists():
                if not retryable_record(path, campaign, move):
                    raise RuntimeError(f"refusing stale, malformed or semantically invalid branch cache: {path}")
                attempts = len(list(args.outdir.glob(f"third_{move['index']:02d}.attempt-*.json"))) + 1
                if attempts >= args.max_attempts:
                    exhausted = True
                    continue
                archive_attempt(path)
            missing.append(move["index"])

        if any(kind == "proved" for kind, _ in classified.values()) or exhausted:
            write_summary(args, args.outdir, campaign, moves, classified)
            return 3
        if not missing:
            summary = write_summary(args, args.outdir, campaign, moves, classified)
            return 0 if summary["all_third_moves_refuted"] else 3

        first = missing[0]
        last = first
        while last + 1 in missing and last - first + 1 < args.chunk_size:
            last += 1
        run_chunk(args, args.outdir, first, last, campaign, moves)


if __name__ == "__main__":
    raise SystemExit(main())
