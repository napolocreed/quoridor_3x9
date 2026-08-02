#!/usr/bin/env python3
"""Synthetic cache-integrity checks for resumable audit harnesses."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import codex_compute_worker  # noqa: E402
import codex_portfolio_worker  # noqa: E402
import verify_4x7_w7_central_depth27 as verify_4x7  # noqa: E402
import verify_replies  # noqa: E402
import verify_root_lower_bound  # noqa: E402
from solver_output import COUNTER_OK, parse_solver_output  # noqa: E402
from reflection_partition import json_digest, listing_audit  # noqa: E402


def write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value) + "\n")


def expect_value_error(callable_) -> None:
    try:
        callable_()
    except ValueError:
        return
    raise AssertionError("expected ValueError")


def expect_runtime_error(callable_) -> None:
    try:
        callable_()
    except RuntimeError:
        return
    raise AssertionError("expected RuntimeError")


def main() -> int:
    digest = "a" * 64
    command = ["solver", "--test"]
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)

        upper_line = "width=3 height=9 walls=10 solved=1 winner=1 depth=33 nodes=1 tt_hits=0 cutoffs=0 pawn_table_hits=0 stalemates_seen=0 seconds=0.1 timeout=0"
        upper = {
            "status": "proved", "returncode": 0, "external_timeout": False,
            "solver_sha256": digest, "command": command,
            "representative": 0,
            "reflection_class": {"representative": 0, "move": "P(1,1)", "aliases": [0]},
            "move_partition_sha256": "p" * 64,
            "stalemate_counter_status": COUNTER_OK,
            "parsed": parse_solver_output(upper_line), "stdout": upper_line,
            "stderr": "upper-listing",
        }
        path = root / "upper.json"
        upper_out=root/"upper.out";upper_err=root/"upper.err"
        upper_out.write_text(upper_line);upper_err.write_text("upper-listing")
        write(path, upper)
        sanitized_upper = verify_replies.load_result(
            path, upper_out, upper_err, digest, command, 1, 0,
            upper["reflection_class"], "p" * 64,
        )
        assert sanitized_upper is not None
        upper["depth"] = 999
        write(path, upper)
        sanitized_upper = verify_replies.load_result(
            path, upper_out, upper_err, digest, command, 1, 0,
            upper["reflection_class"], "p" * 64,
        )
        assert sanitized_upper is not None and sanitized_upper["depth"] == 33
        upper_out.write_text(upper_line.replace("nodes=1", "nodes=2"))
        assert verify_replies.load_result(path, upper_out, upper_err, digest, command, 1, 0) is None
        upper_out.write_text(upper_line)
        upper["returncode"] = False
        write(path, upper)
        assert verify_replies.load_result(path, upper_out, upper_err, digest, command, 1, 0) is None
        upper["returncode"] = 0
        upper["representative"] = False
        write(path, upper)
        assert verify_replies.load_result(path, upper_out, upper_err, digest, command, 1, 0) is None
        upper["representative"] = 0
        upper["parsed"]["stalemates_seen"] = 2
        write(path, upper)
        assert verify_replies.load_result(path, upper_out, upper_err, digest, command, 1, 0) is None

        lower_line = "width=3 height=9 walls=10 solved=0 nodes=1 tt_hits=0 cutoffs=0 pawn_table_hits=0 stalemates_seen=0 seconds=0.1 timeout=0"
        lower = {
            "status": "refuted", "returncode": 0, "external_timeout": False,
            "solver_sha256": digest, "command": command,
            "representative": 0,
            "reflection_class": {"representative": 0, "move": "P(7,1)", "aliases": [0]},
            "move_partition_sha256": "q" * 64,
            "stalemate_counter_status": COUNTER_OK,
            "parsed": parse_solver_output(lower_line), "stdout": lower_line,
            "stderr": "lower-listing",
        }
        path = root / "lower.json"
        lower_out=root/"lower.out";lower_err=root/"lower.err"
        lower_out.write_text(lower_line);lower_err.write_text("lower-listing")
        write(path, lower)
        assert verify_root_lower_bound.existing(
            path, lower_out, lower_err, digest, command, 0,
            lower["reflection_class"], "q" * 64,
        ) is not None
        lower_err.write_text("changed-listing")
        assert verify_root_lower_bound.existing(
            path, lower_out, lower_err, digest, command, 0,
        ) is None
        lower_err.write_text("lower-listing")
        lower["returncode"] = False
        write(path, lower)
        assert verify_root_lower_bound.existing(path, lower_out, lower_err, digest, command, 0) is None
        lower["returncode"] = 0
        lower["representative"] = False
        write(path, lower)
        assert verify_root_lower_bound.existing(path, lower_out, lower_err, digest, command, 0) is None
        lower["representative"] = 0
        lower["parsed"].pop("stalemates_seen")
        write(path, lower)
        assert verify_root_lower_bound.existing(path, lower_out, lower_err, digest, command, 0) is None

        campaign = {
            "schema_version": 1, "solver": "solver", "solver_sha256": digest,
            "width": 4, "height": 7, "walls_per_player": 7,
            "root_index": 0, "root_move": "P(5,2)", "reply_index": 0,
            "reply_move": "P(1,2)", "target": 1, "remaining_depth": 24,
            "total_suffix": 25, "seconds_per_branch": 300,
            "tt_bits": 27, "order": 1,
            "no_bounds": True, "no_pawn_table": True,
            "moves_sha256": "m" * 64, "third_moves": 1,
        }
        branch_command = [
            "solver", "--width", "4", "--height", "7", "--walls", "7",
            "--root-index", "0", "--root-index2", "0", "--target", "1",
            "--child-depth", "24", "--seconds", "300",
            "--tt-bits", "27", "--order", "1",
            "--no-bounds", "--no-pawn-table", "--scan-current",
            "--scan-root-start", "0", "--scan-root-end", "0",
        ]
        branch = {
            "status": "refuted", "solver_sha256": digest, "child_depth": 24,
            "distance_bound": False, "pawn_only_table": False,
            "proven": False, "timeout": False, "stalemates_seen": 0,
            "stalemate_counter_status": COUNTER_OK,
            "nodes": 1, "tt_hits": 0, "seconds": 0.1,
            "task": 0, "representative": 0, "aliases": "0", "move": "P(4,2)",
            "total_suffix": 25, "fresh_tt": True, "campaign": campaign,
            "command": branch_command, "external_chunk_timeout": False,
            "raw_result_line": (
                "current_scan task=0 rep=0 aliases=0 move=P(4,2) "
                "proven=0 timeout=0 nodes=1 tt_hits=0 stalemates_seen=0 "
                "seconds=0.1 child_depth=24 total_suffix=25"
            ),
        }
        path = root / "branch.json"
        chunk_out=root/"chunk_00_00_1.out";chunk_err=root/"chunk_00_00_1.err"
        chunk_out.write_text(branch["raw_result_line"]+"\n")
        chunk_err.write_text(
            "forcing root[0] move=P(5,2)\nforcing second[0] move=P(1,2)\n"
        )
        branch["chunk_evidence"]={
            "stdout_file":chunk_out.name,"stdout_sha256":verify_4x7.sha256(chunk_out),
            "stderr_file":chunk_err.name,"stderr_sha256":verify_4x7.sha256(chunk_err),
            "returncode":1,"external_timeout":False,
        }
        write(path, branch)
        assert verify_4x7.classify_record(path, campaign, {"index": 0, "move": "P(4,2)", "score": 0}) is not None
        chunk_out.write_text(branch["raw_result_line"].replace("nodes=1","nodes=2")+"\n")
        assert verify_4x7.classify_record(path, campaign, {"index": 0, "move": "P(4,2)", "score": 0}) is None
        chunk_out.write_text(branch["raw_result_line"]+"\n")
        branch["proven"] = 2
        write(path, branch)
        assert verify_4x7.classify_record(path, campaign, {"index": 0, "move": "P(4,2)", "score": 0}) is None

        worker_stdout = "width=3 height=3 walls=1 solved=1 winner=2 depth=8 nodes=1 stalemates_seen=0 seconds=0.1 timeout=0"
        worker = {
            "status": "completed", "returncode": 0, "timed_out": False,
            "solver_sha256": digest, "command": command,
            "id": "task", "env": {}, "stdout": worker_stdout,
            "stalemate_counter_status": COUNTER_OK,
            "parsed_stdout": codex_compute_worker.parse_lines(worker_stdout),
        }
        path = root / "worker.json"
        write(path, worker)
        assert codex_compute_worker.existing_ok(path, digest, command, "task", {})
        worker["returncode"] = False
        write(path, worker)
        assert not codex_compute_worker.existing_ok(path, digest, command, "task", {})
        worker["returncode"] = 0
        worker["parsed_stdout"][0].pop("stalemates_seen")
        write(path, worker)
        assert not codex_compute_worker.existing_ok(path, digest, command)
        assert not codex_compute_worker.completed_output_valid(
            codex_compute_worker.parse_lines(worker_stdout.replace("timeout=0", "timeout=1"))
        )
        assert not codex_compute_worker.completed_output_valid(
            codex_compute_worker.parse_lines(worker_stdout.replace("solved=1", "solved=true"))
        )

        portfolio_stdout = "width=3 height=3 walls=1 solved=1 winner=2 depth=8 nodes=1 stalemates_seen=0 seconds=0.1 timeout=0"
        winner = codex_portfolio_worker.parsed_result(portfolio_stdout)
        portfolio = {
            "solver": "solver", "task_args": ["--test"],
            "policies": [{"name": "baseline", "args": []}],
            "winner_policy": "baseline", "winner_result": winner,
            "variants": [{"policy": "baseline", "returncode": 0, "result": winner,
                          "command": ["solver", "--test"], "stdout": portfolio_stdout}],
        }
        assert codex_portfolio_worker.cached_winner_valid(portfolio)
        portfolio["variants"][0]["returncode"] = False
        assert not codex_portfolio_worker.cached_winner_valid(portfolio)
        portfolio["variants"][0]["returncode"] = 0
        assert not codex_portfolio_worker.exact_result({**winner, "solved": False})
        portfolio["variants"][0]["returncode"] = 3
        assert not codex_portfolio_worker.cached_winner_valid(portfolio)

        # The legacy numeric representatives are safe only after the current
        # binary's named horizontal-reflection partition has been bound and
        # hashed. Exercise both cache schemas without launching a solver.
        upper_args = SimpleNamespace(
            solver=Path("solver"), width=3, height=9, walls=10,
            root_index=0, target=1, order=1, expected_root_move="P(7,1)",
            precompute_timeout=1,
        )
        upper_listing = (
            "forcing root[0] move=P(7,1)\n"
            "second[0] move=P(1,1) score=0\n"
            "second[1] move=H(0,0) score=1\n"
            "second[2] move=H(0,1) score=1\n"
        )
        upper_audit = listing_audit(upper_listing, "second", 3, [0, 1])
        upper_partition = {
            "schema_version": 1, "solver_sha256": digest,
            "command": verify_replies.partition_command(upper_args),
            "returncode": 0, "stdout": "", "stderr": upper_listing,
            "audit": upper_audit,
            "partition_sha256": json_digest(upper_audit["partition"]),
        }
        write(root / "reply_partition.json", upper_partition)
        assert verify_replies.load_reply_partition(upper_args, root, digest, [0, 1]) == upper_partition
        forged_upper_partition = {**upper_partition, "schema_version": True}
        write(root / "reply_partition.json", forged_upper_partition)
        expect_runtime_error(
            lambda: verify_replies.load_reply_partition(upper_args, root, digest, [0, 1])
        )
        forged_upper_partition = {
            **upper_partition,
            "command": [*upper_partition["command"], "--no-symmetry"],
        }
        write(root / "reply_partition.json", forged_upper_partition)
        expect_runtime_error(
            lambda: verify_replies.load_reply_partition(upper_args, root, digest, [0, 1])
        )
        forged_upper_partition = {
            **upper_partition,
            "stderr": upper_listing.replace("score=1", "score=2", 1),
        }
        write(root / "reply_partition.json", forged_upper_partition)
        expect_runtime_error(
            lambda: verify_replies.load_reply_partition(upper_args, root, digest, [0, 1])
        )
        write(root / "reply_partition.json", upper_partition)
        upper_branch_listing = upper_listing + "forcing second[0] move=P(1,1)\n"
        upper_branch_audit = verify_replies.reply_branch_listing_audit(
            upper_args, 0, upper_partition, "", upper_branch_listing
        )
        upper_branch_record = {
            "branch_identity_status": "ok", "stdout": "", "stderr": upper_branch_listing,
            "branch_listing_audit": upper_branch_audit,
            "branch_listing_sha256": json_digest(upper_branch_audit),
        }
        assert verify_replies.reply_branch_binding_valid(
            upper_branch_record, upper_args, 0, upper_partition
        )
        upper_branch_record["stderr"] = upper_branch_listing.replace(
            "forcing second[0] move=P(1,1)", "forcing second[1] move=H(0,0)"
        )
        assert not verify_replies.reply_branch_binding_valid(
            upper_branch_record, upper_args, 0, upper_partition
        )

        lower_args = SimpleNamespace(
            solver=Path("solver"), width=3, height=9, walls=10,
            order=1, precompute_timeout=1,
        )
        lower_listing = (
            "root[0] move=P(7,1) score=0\n"
            "root[1] move=H(0,0) score=1\n"
            "root[2] move=H(0,1) score=1\n"
        )
        lower_audit = listing_audit(lower_listing, "root", 3, [0, 1])
        lower_partition = {
            "schema_version": 1, "solver_sha256": digest,
            "command": verify_root_lower_bound.partition_command(lower_args),
            "returncode": 0, "stdout": "", "stderr": lower_listing,
            "audit": lower_audit,
            "partition_sha256": json_digest(lower_audit["partition"]),
        }
        write(root / "root_partition.json", lower_partition)
        assert verify_root_lower_bound.load_root_partition(lower_args, root, digest, [0, 1]) == lower_partition
        lower_branch_listing = lower_listing + "forcing root[0] move=P(7,1)\n"
        lower_branch_audit = verify_root_lower_bound.root_branch_listing_audit(
            lower_args, 0, lower_partition, "", lower_branch_listing
        )
        lower_branch_record = {
            "branch_identity_status": "ok", "stdout": "", "stderr": lower_branch_listing,
            "branch_listing_audit": lower_branch_audit,
            "branch_listing_sha256": json_digest(lower_branch_audit),
        }
        assert verify_root_lower_bound.root_branch_binding_valid(
            lower_branch_record, lower_args, 0, lower_partition
        )
        lower_branch_record["stderr"] = lower_branch_listing.replace(
            "forcing root[0] move=P(7,1)", "forcing root[1] move=H(0,0)"
        )
        assert not verify_root_lower_bound.root_branch_binding_valid(
            lower_branch_record, lower_args, 0, lower_partition
        )
        lower_partition["partition_sha256"] = "x" * 64
        write(root / "root_partition.json", lower_partition)
        expect_runtime_error(
            lambda: verify_root_lower_bound.load_root_partition(lower_args, root, digest, [0, 1])
        )

        central_args=SimpleNamespace(
            solver=Path("solver"),root_index=0,reply_index=0,
            expected_root_move="P(5,2)",expected_reply_move="P(1,2)",
            order=1,precompute_timeout=1,
        )
        central_stderr=(
            "forcing root[0] move=P(5,2)\n"
            "forcing second[0] move=P(1,2)\n"
            "third[0] move=P(4,2) score=7\n"
        )
        central_rows,_,_=verify_4x7.parse_third_listing("",central_stderr)
        central_cache={
            "schema_version":1,"solver_sha256":digest,
            "command":verify_4x7.list_command(central_args),
            "root_index":0,"root_move":"P(5,2)",
            "reply_index":0,"reply_move":"P(1,2)","order":1,
            "moves_sha256":json_digest(central_rows),"moves":central_rows,
            "stdout":"","stderr":central_stderr,
        }
        write(root/"third_moves.json",central_cache)
        assert verify_4x7.list_moves(central_args,root,digest)==central_cache
        central_cache["stderr"]=central_stderr.replace("score=7","score=8")
        write(root/"third_moves.json",central_cache)
        expect_runtime_error(lambda:verify_4x7.list_moves(central_args,root,digest))
        central_cache["stderr"]=central_stderr;central_cache["schema_version"]=True
        write(root/"third_moves.json",central_cache)
        expect_runtime_error(lambda:verify_4x7.list_moves(central_args,root,digest))

        # Every cache loader must reject a non-object JSON root deliberately,
        # rather than falling through to an AttributeError on list.get().
        list_root = root / "list-root.json"
        write(list_root, [])
        assert verify_replies.load_result(list_root, root/"missing.out", root/"missing.err", digest, command, 1) is None
        assert verify_root_lower_bound.existing(list_root, root/"missing.out", root/"missing.err", digest, command) is None
        assert not codex_compute_worker.existing_ok(list_root, digest, command)
        assert not codex_portfolio_worker.cached_winner_valid([])
        expect_runtime_error(lambda: verify_4x7.read_object(list_root))

        # Empty manifests, filename-normalization collisions, and output names
        # reserved by the workers must all fail before any solver is launched.
        empty_manifest = root / "empty.jsonl"
        empty_manifest.write_text("# comments do not make a task\n\n")
        expect_value_error(lambda: codex_compute_worker.load_tasks(empty_manifest))
        expect_value_error(lambda: codex_portfolio_worker.load_tasks(empty_manifest))

        collision_manifest = root / "collision.jsonl"
        collision_manifest.write_text(
            json.dumps({"id": "a/b", "args": []}) + "\n"
            + json.dumps({"id": "a?b", "args": []}) + "\n"
        )
        expect_value_error(lambda: codex_compute_worker.load_tasks(collision_manifest))
        expect_value_error(lambda: codex_portfolio_worker.load_tasks(collision_manifest))

        compute_reserved = root / "compute-reserved.jsonl"
        write(compute_reserved, {"id": "summary", "args": []})
        expect_value_error(lambda: codex_compute_worker.load_tasks(compute_reserved))
        for reserved in ("campaign", "summary", "portfolio_aggregate", "portfolio_summary"):
            portfolio_reserved = root / f"portfolio-reserved-{reserved}.jsonl"
            write(portfolio_reserved, {"id": reserved, "args": []})
            expect_value_error(lambda path=portfolio_reserved: codex_portfolio_worker.load_tasks(path))

        overlay_manifest = root / "portfolio-overlay.jsonl"
        write(overlay_manifest, {"id": "overlay", "args": [], "policies": [{"name": "baseline", "args": []}]})
        overlay_tasks = codex_portfolio_worker.load_tasks(overlay_manifest)
        codex_portfolio_worker.append_policy_overlays(
            overlay_tasks, [json.dumps({"name": "hint", "args": ["--tt-hint-first-mode", "opponent"]})]
        )
        assert overlay_tasks[0]["policies"][-1] == {
            "name": "hint", "args": ["--tt-hint-first-mode", "opponent"]
        }
        expect_value_error(lambda: codex_portfolio_worker.append_policy_overlays(overlay_tasks, ["not-json"]))
        expect_value_error(lambda: codex_portfolio_worker.append_policy_overlays(overlay_tasks, [json.dumps({"name": "hint", "args": []})]))
        expect_value_error(lambda: codex_portfolio_worker.append_policy_overlays(
            overlay_tasks, [json.dumps({"name": "unsafe", "args": ["--target", "2"]})]
        ))
        assert codex_portfolio_worker.select_tasks(overlay_tasks, ["overlay"]) == overlay_tasks
        expect_value_error(lambda: codex_portfolio_worker.select_tasks(overlay_tasks, ["missing"]))
        expect_value_error(lambda: codex_portfolio_worker.select_tasks(overlay_tasks, ["overlay", "overlay"]))

        campaign_dir = root / "portfolio-campaign"
        campaign_dir.mkdir()
        campaign_identity = {
            "schema_version": 1, "manifest_sha256": digest,
            "task_universe_sha256": digest, "solver_sha256": digest,
            "worker_bundle_sha256": digest,
        }
        codex_portfolio_worker.bind_campaign(campaign_dir, campaign_identity, False)
        codex_portfolio_worker.bind_campaign(campaign_dir, campaign_identity, False)
        changed_campaign = dict(campaign_identity, solver_sha256="b" * 64)
        expect_runtime_error(lambda: codex_portfolio_worker.bind_campaign(
            campaign_dir, changed_campaign, True
        ))

        # The portfolio summarizer creates a JSON aggregate in its input
        # directory. A second run must ignore that output instead of ingesting
        # it as a failed portfolio record.
        portfolio_dir = root / "portfolio-summary"
        portfolio_dir.mkdir()
        summary_record = {
            "id": "task", "status": "completed", "solver": "solver",
            "solver_sha256": digest, "worker_sha256": digest,
            "parser_sha256": digest, "worker_bundle_sha256": digest,
            "task_args": ["--test"], "env": {},
            "policies": [{"name": "baseline", "args": []}],
            "elapsed_wall_seconds": 0.1,
            "winner_policy": "baseline", "winner_result": winner,
            "variants": [{"policy": "baseline", "returncode": 0,
                          "result": winner, "command": ["solver", "--test"],
                          "stdout": portfolio_stdout}],
        }
        write(portfolio_dir / "campaign.json", {
            "schema_version": 1, "manifest_sha256": digest,
            "task_universe_sha256": digest, "solver_sha256": digest,
            "worker_bundle_sha256": digest,
        })
        write(portfolio_dir / "task.json", summary_record)
        summarize = Path(__file__).resolve().parents[1] / "scripts" / "summarize_portfolios.py"
        for _ in range(2):
            completed = subprocess.run(
                [sys.executable, str(summarize), str(portfolio_dir)],
                text=True, capture_output=True, check=False,
            )
            assert completed.returncode == 0, completed.stderr or completed.stdout
            aggregate = json.loads((portfolio_dir / "portfolio_aggregate.json").read_text())
            assert aggregate["records"] == 1
            assert aggregate["completed"] == 1
            assert aggregate["failed"] == 0
            assert aggregate["solver_hashes_complete_and_unique"]
            assert aggregate["worker_hashes_complete_and_unique"]
            assert aggregate["parser_hashes_complete_and_unique"]
            assert aggregate["worker_bundle_hashes_complete_and_unique"]
            assert aggregate["campaign_identity_present_and_matching"]
        csv_lines = (portfolio_dir / "portfolio_summary.csv").read_text().splitlines()
        assert len(csv_lines) == 2

        legacy_portfolio_dir = root / "portfolio-summary-missing-worker-hash"
        legacy_portfolio_dir.mkdir()
        legacy_record = dict(summary_record)
        legacy_record.pop("worker_sha256")
        write(legacy_portfolio_dir / "task.json", legacy_record)
        write(legacy_portfolio_dir / "campaign.json", {
            "schema_version": 1, "manifest_sha256": digest,
            "task_universe_sha256": digest, "solver_sha256": digest,
            "worker_bundle_sha256": digest,
        })
        completed = subprocess.run(
            [sys.executable, str(summarize), str(legacy_portfolio_dir)],
            text=True, capture_output=True, check=False,
        )
        assert completed.returncode == 3, completed.stderr or completed.stdout
        aggregate = json.loads((legacy_portfolio_dir / "portfolio_aggregate.json").read_text())
        assert not aggregate["worker_hashes_complete_and_unique"]

        forged = root / "forged"
        forged.mkdir()
        bad_line = "width=3 height=9 walls=10 solved=0 nodes=1 stalemates_seen=0 seconds=0.1 timeout=1"
        for index, representative in enumerate([0, 0]):
            stem=forged / f"reply_{index:02d}"
            write(stem.with_suffix(".json"), {
                "representative": representative, "status": "proved", "returncode": 124,
                "external_timeout": True, "solver_sha256": digest,
                "parsed": parse_solver_output(bad_line),
            })
            stem.with_suffix(".out").write_text(bad_line)
            stem.with_suffix(".err").write_text("")
        summary_path = root / "forged-summary.json"
        completed = subprocess.run([
            sys.executable, str(Path(__file__).resolve().parents[1] / "scripts" / "summarize_branch_audit.py"),
            str(forged), "--expected-records", "2", "--expected-reps", "0,1",
            "--counter-policy", "required", "--output", str(summary_path),
        ], text=True, capture_output=True, check=False)
        assert completed.returncode == 3
        forged_summary = json.loads(summary_path.read_text())
        assert not forged_summary["all_proved"] and forged_summary["duplicate_representatives"] == [0]

    print({
        "status": "ok",
        "cache_schemas": 5,
        "non_object_roots_rejected": 5,
        "empty_manifests_rejected": 2,
        "normalized_id_collisions_rejected": 2,
        "reserved_ids_rejected": 5,
        "portfolio_summary_runs": 2,
        "named_partition_caches": 3,
        "branch_identity_bindings": 2,
        "partition_cache_forgeries_rejected": 4,
        "forged_statuses_rejected": 14,
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
