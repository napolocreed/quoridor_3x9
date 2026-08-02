#!/usr/bin/env python3
"""Acceptance, corruption, gzip, and no-overwrite checks for the SQLite verifier."""
from __future__ import annotations

from collections import deque
import gzip
import hashlib
import json
from pathlib import Path
import random
import subprocess
import sqlite3
import sys
import tempfile

from qcert_verify_sqlite import (
    build_wall_configuration_profile,
    declared_move_with_profile,
    legal_moves_with_profile,
)
from quoridor_reference import ReferenceGame


ROOT = Path(__file__).resolve().parents[1]
VERIFIER = ROOT / "reference" / "qcert_verify_sqlite.py"
JS_VERIFIER = ROOT / "reference" / "qcert_verify.mjs"
FIXTURE = ROOT / "results" / "validation" / "qcert" / "cert_3x3x0.jsonl"


def run(*arguments: str) -> tuple[int, dict[str, object], str]:
    completed = subprocess.run(
        [sys.executable, str(VERIFIER), *arguments],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise AssertionError(
            f"verifier did not emit one JSON result (rc={completed.returncode}): "
            f"stdout={completed.stdout!r} stderr={completed.stderr!r}"
        ) from error
    if not isinstance(result, dict):
        raise AssertionError(f"verifier result is not an object: {result!r}")
    return completed.returncode, result, completed.stderr


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def js_result(path: Path) -> tuple[int, dict[str, object]]:
    completed = subprocess.run(
        ["node", str(JS_VERIFIER), str(path)],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise AssertionError(
            f"JavaScript verifier emitted invalid JSON: rc={completed.returncode}, "
            f"stdout={completed.stdout!r}, stderr={completed.stderr!r}"
        ) from error
    if not isinstance(result, dict):
        raise AssertionError(f"JavaScript verifier result is not an object: {result!r}")
    return completed.returncode, result


def expect_accept(path: Path, *extra: str) -> dict[str, object]:
    code, result, stderr = run(str(path), *extra)
    if code != 0 or result.get("ok") is not True:
        raise AssertionError(
            f"valid certificate rejected: rc={code} result={result} stderr={stderr!r}"
        )
    return result


def expect_reject(path: Path, name: str) -> dict[str, object]:
    code, result, stderr = run(str(path))
    if code != 1 or result.get("ok") is not False:
        raise AssertionError(
            f"{name} corruption not rejected as certificate error: "
            f"rc={code} result={result} stderr={stderr!r}"
        )
    if not result.get("errors"):
        raise AssertionError(f"{name} rejection omitted diagnostics")
    return result


def move_label(move: tuple[str, int, int]) -> str:
    kind, first, second = move
    return f"P:{first}" if kind == "P" else f"{kind}:{first}:{second}"


def profile_differential() -> tuple[int, int, int]:
    """Exhaust every reachable non-terminal 3x3x1 state against the baseline."""
    game = ReferenceGame(3, 3, 1)
    queue = deque([game.initial()])
    seen = {game.initial()}
    profiles = {}
    states_checked = 0
    declared_moves_checked = 0
    while queue:
        state = queue.popleft()
        if game.winner(state) is not None:
            continue
        key = (state.hwalls, state.vwalls)
        profile = profiles.get(key)
        if profile is None:
            profile = profiles[key] = build_wall_configuration_profile(game, *key)
        expected = game.legal_moves(state)
        actual = legal_moves_with_profile(game, state, profile)
        if actual != expected:
            raise AssertionError(
                f"profiled legal moves diverged at {state}: {actual!r} != {expected!r}"
            )
        for move in expected:
            selected, _ = declared_move_with_profile(
                game, state, move_label(move), profile,
            )
            if selected != move:
                raise AssertionError(
                    f"declared move validation diverged at {state}: {move!r} -> {selected!r}"
                )
            declared_moves_checked += 1
        for impossible in ("P:999", "P:01", "H:99:0", "V:0:99", "X:0:0"):
            selected, _ = declared_move_with_profile(game, state, impossible, profile)
            if selected is not None:
                raise AssertionError(f"invalid declared move accepted: {state}, {impossible}")
        states_checked += 1
        for move in expected:
            child = game.apply(state, move)
            if child not in seen:
                seen.add(child)
                queue.append(child)
    return states_checked, len(profiles), declared_moves_checked


def large_profile_sample() -> tuple[int, int]:
    """Exercise 27-cell masks and the full 3x9 anchor geometry deterministically."""
    game = ReferenceGame(3, 9, 10)
    rng = random.Random(9_102_026)
    state = game.initial()
    profiles = {}
    samples = 300
    for sample in range(samples):
        if game.winner(state) is not None:
            state = game.initial()
        key = (state.hwalls, state.vwalls)
        profile = profiles.get(key)
        if profile is None:
            profile = profiles[key] = build_wall_configuration_profile(game, *key)
        expected = game.legal_moves(state)
        actual = legal_moves_with_profile(game, state, profile)
        if actual != expected:
            raise AssertionError(
                f"3x9 profile divergence at sample {sample}, {state}: "
                f"{actual!r} != {expected!r}"
            )
        state = game.apply(state, rng.choice(expected))
    return samples, len(profiles)


def main() -> None:
    profiled_states, profiled_configurations, declared_moves = profile_differential()
    large_samples, large_configurations = large_profile_sample()
    valid = FIXTURE.read_text(encoding="utf-8")
    lines = valid.rstrip("\n").splitlines()
    with tempfile.TemporaryDirectory(prefix="qcert-sqlite-check-") as directory:
        tmp = Path(directory)

        accepted = expect_accept(FIXTURE)
        expected_hash = "7f36036cce38918425b9bfb320224f5fd94a7a4ae1c513c700a7d50702842aae"
        expected = {
            "certificateSha256": expected_hash,
            "certificateBytes": 884,
            "compression": "none",
            "nodes": 9,
            "targetNodes": 6,
            "opponentNodes": 3,
            "edgesChecked": 13,
            "rootBudget": 4,
            "rootIsInitialPosition": True,
            "verifiedTransforms": ["identity"],
            "configProfiles": 1,
            "wallCandidateProfiles": 0,
            "profileWallCandidates": 0,
            "wallCandidatesChecked": 0,
        }
        for field, value in expected.items():
            if accepted.get(field) != value:
                raise AssertionError(
                    f"accepted result {field}={accepted.get(field)!r}, expected {value!r}"
                )
        if accepted.get("verifierSha256") != sha256(VERIFIER):
            raise AssertionError("result did not bind the executed verifier source")
        if accepted.get("rulesSha256") != sha256(ROOT / "reference" / "quoridor_reference.py"):
            raise AssertionError("result did not bind the Python rules source")
        claim = accepted.get("claim")
        if not isinstance(claim, dict) or claim.get("scope") != "initial-position":
            raise AssertionError(f"bad accepted claim: {claim!r}")
        database_report = accepted.get("database")
        if not isinstance(database_report, dict) or database_report != {
            "bytes": database_report.get("bytes"),
            "deletedOnExit": True,
            "mode": "temporary",
            "path": None,
        }:
            raise AssertionError(f"bad temporary database report: {database_report!r}")

        compressed = tmp / "cert_3x3x0.jsonl.gz"
        with gzip.open(compressed, "wt", encoding="utf-8", newline="\n") as stream:
            stream.write(valid)
        gzip_result = expect_accept(compressed)
        if gzip_result.get("compression") != "gzip":
            raise AssertionError(f"gzip was not auto-detected: {gzip_result}")
        if gzip_result.get("certificateSha256") != sha256(compressed):
            raise AssertionError("gzip result did not hash the exact compressed artifact")

        wall_branch = tmp / "wall_branch.jsonl"
        wall_branch.write_text(
            '{"type":"header","format":"qcert-1","width":3,"height":3,'
            '"walls":1,"target":0,"bound":1,"root":{"p1":4,"p2":1,'
            '"r1":1,"r2":0,"turn":0,"hw":0,"vw":4}}\n'
            '{"type":"node","p1":4,"p2":1,"r1":1,"r2":0,"turn":0,'
            '"hw":0,"vw":4,"d":1,"move":"P:0"}\n',
            encoding="utf-8",
            newline="\n",
        )
        wall_result = expect_accept(wall_branch)
        if (
            wall_result.get("configProfiles") != 1
            or wall_result.get("rootBudget") != 1
            or wall_result.get("edgesChecked") != 1
            or wall_result.get("claim", {}).get("scope") != "branch-position"
        ):
            raise AssertionError(f"wall-configured branch report is wrong: {wall_result}")

        corruptions = {
            "bad_budget": valid.replace('"d":4', '"d":0', 1),
            "non_decreasing_budget": valid.replace(
                '"d":3,"move":"P:4"', '"d":4,"move":"P:4"', 1,
            ),
            "illegal_move": valid.replace('"move":"P:7"', '"move":"H:0:0"', 1),
            "coverage_hole": "\n".join(lines[:-1]) + "\n",
            "root_over_bound": valid.replace('"bound":4', '"bound":3', 1),
            "duplicate_state": valid + lines[1] + "\n",
            "duplicate_member": valid.replace('"bound":4', '"bound":4,"bound":5', 1),
            "boolean_integer": valid.replace('"width":3', '"width":true', 1),
            "floating_integer": valid.replace('"height":3', '"height":3.0', 1),
            "exponent_integer": valid.replace('"bound":4', '"bound":4e0', 1),
            "unsafe_integer": valid.replace('"bound":4', '"bound":9007199254740992', 1),
            "bad_conservation": valid.replace('"r1":0', '"r1":1', 1),
            "nonstandard_number": valid.replace('"bound":4', '"bound":NaN', 1),
            "header_not_first": "\n".join([lines[1], lines[0], *lines[2:]]) + "\n",
        }
        second_pass_rejections = 0
        for name, text in corruptions.items():
            path = tmp / f"{name}.jsonl"
            path.write_text(text, encoding="utf-8", newline="\n")
            result = expect_reject(path, name)
            if result.get("edgesChecked", 0):
                second_pass_rejections += 1
        if second_pass_rejections < 3:
            raise AssertionError(
                f"expected several obligation-pass rejections, got {second_pass_rejections}"
            )

        gzip_framing = {
            "concatenated_gzip": gzip.compress(valid.encode("utf-8")) + gzip.compress(b"\n"),
            "trailing_gzip": gzip.compress(valid.encode("utf-8")) + b"trailing-data",
            "truncated_gzip": gzip.compress(valid.encode("utf-8"))[:-1],
        }
        for name, payload in gzip_framing.items():
            path = tmp / f"{name}.jsonl.gz"
            path.write_bytes(payload)
            result = expect_reject(path, name)
            if not any("gzip" in error for error in result["errors"]):
                raise AssertionError(f"{name} did not report gzip framing: {result}")

        # One byte-level corpus pins down the syntax shared by the independent
        # JavaScript and Python verifiers.  In particular JSON.parse otherwise
        # erases integer spellings, and Node's ordinary utf8 decoding replaces
        # malformed bytes instead of rejecting them.
        header_marker = b'"format":"qcert-1"'
        marker_at = valid.encode("utf-8").find(header_marker)
        if marker_at < 0:
            raise AssertionError("fixture format marker is absent")
        insert_at = marker_at + len(header_marker)
        valid_bytes = valid.encode("utf-8")
        invalid_utf8 = (
            valid_bytes[:insert_at] + b',"extra":"\xff"' + valid_bytes[insert_at:]
        )
        shared_syntax = {
            "shared_valid": (valid_bytes, True),
            "shared_float": (
                valid.replace('"height":3', '"height":3.0', 1).encode("utf-8"), False,
            ),
            "shared_exponent": (
                valid.replace('"bound":4', '"bound":4e0', 1).encode("utf-8"), False,
            ),
            "shared_extension_float": (
                valid.replace(
                    '"format":"qcert-1"', '"format":"qcert-1","extra":1.5', 1,
                ).encode("utf-8"), True,
            ),
            "shared_dotted_extension": (
                valid.replace(
                    '"format":"qcert-1"', '"format":"qcert-1","root.p1":1.5', 1,
                ).encode("utf-8"), True,
            ),
            "shared_cr_only": (valid.replace("\n", "\r").encode("utf-8"), True),
            "shared_bom": (b"\xef\xbb\xbf" + valid_bytes, False),
            "shared_invalid_utf8": (invalid_utf8, False),
            "shared_null_record": (valid_bytes + b"null\n", False),
        }
        for name, (payload, expected_ok) in shared_syntax.items():
            path = tmp / f"{name}.jsonl"
            path.write_bytes(payload)
            py_code, py_result, _ = run(str(path))
            js_code, js_verdict = js_result(path)
            expected_code = 0 if expected_ok else 1
            if (
                py_code != expected_code
                or js_code != expected_code
                or py_result.get("ok") is not expected_ok
                or js_verdict.get("ok") is not expected_ok
            ):
                raise AssertionError(
                    f"cross-verifier syntax divergence for {name}: "
                    f"python=({py_code},{py_result}), js=({js_code},{js_verdict})"
                )

        illegal_states = {
            "crossing": (
                '{"type":"header","format":"qcert-1","width":3,"height":3,'
                '"walls":2,"target":1,"bound":1,"root":{"p1":7,"p2":1,'
                '"r1":1,"r2":1,"turn":0,"hw":1,"vw":1}}\n',
                "crossing walls",
            ),
            "overlap": (
                '{"type":"header","format":"qcert-1","width":3,"height":3,'
                '"walls":2,"target":1,"bound":1,"root":{"p1":7,"p2":1,'
                '"r1":1,"r2":1,"turn":0,"hw":3,"vw":0}}\n',
                "overlapping horizontal walls",
            ),
            "mask_range": (
                '{"type":"header","format":"qcert-1","width":3,"height":3,'
                '"walls":1,"target":1,"bound":1,"root":{"p1":7,"p2":1,'
                '"r1":0,"r2":1,"turn":0,"hw":16,"vw":0}}\n',
                "wall mask outside anchor grid",
            ),
            "terminal_node": (
                '{"type":"header","format":"qcert-1","width":3,"height":3,'
                '"walls":0,"target":1,"bound":1,"root":{"p1":1,"p2":7,'
                '"r1":0,"r2":0,"turn":0,"hw":0,"vw":0}}\n',
                "terminal state appears in node index",
            ),
        }
        for name, (text, diagnostic) in illegal_states.items():
            path = tmp / f"{name}.jsonl"
            path.write_text(text, encoding="utf-8", newline="\n")
            result = expect_reject(path, name)
            if not any(diagnostic in error for error in result["errors"]):
                raise AssertionError(f"{name} missed diagnostic {diagnostic!r}: {result}")

        second_pass_illegal_states = {
            "indexed_crossing": (
                '{"type":"header","format":"qcert-1","width":3,"height":3,'
                '"walls":2,"target":1,"bound":1,"root":{"p1":7,"p2":1,'
                '"r1":2,"r2":2,"turn":0,"hw":0,"vw":0}}\n'
                '{"type":"node","p1":7,"p2":1,"r1":1,"r2":1,"turn":0,'
                '"hw":1,"vw":1,"d":1}\n',
                "crossing walls",
            ),
            "indexed_disconnected": (
                '{"type":"header","format":"qcert-1","width":4,"height":3,'
                '"walls":1,"target":1,"bound":1,"root":{"p1":10,"p2":2,'
                '"r1":1,"r2":1,"turn":0,"hw":0,"vw":0}}\n'
                '{"type":"node","p1":10,"p2":2,"r1":0,"r2":0,"turn":0,'
                '"hw":5,"vw":0,"d":1}\n',
                "has no goal path",
            ),
            "height_two_stalemate": (
                '{"type":"header","format":"qcert-1","width":3,"height":2,'
                '"walls":1,"target":1,"bound":1,"root":{"p1":4,"p2":1,'
                '"r1":0,"r2":0,"turn":0,"hw":0,"vw":3}}\n'
                '{"type":"node","p1":4,"p2":1,"r1":0,"r2":0,"turn":0,'
                '"hw":0,"vw":3,"d":1}\n',
                "state has no legal action",
            ),
        }
        for name, (text, diagnostic) in second_pass_illegal_states.items():
            path = tmp / f"{name}.jsonl"
            path.write_text(text, encoding="utf-8", newline="\n")
            result = expect_reject(path, name)
            if result.get("configProfiles") != 1:
                raise AssertionError(f"{name} did not reach profiled pass 2: {result}")
            if not any(diagnostic in error for error in result["errors"]):
                raise AssertionError(f"{name} missed diagnostic {diagnostic!r}: {result}")

        persistent = tmp / "persistent.sqlite3"
        persistent_result = expect_accept(FIXTURE, "--database", str(persistent))
        report = persistent_result.get("database")
        if not persistent.is_file() or not isinstance(report, dict):
            raise AssertionError("explicit SQLite database was not preserved")
        if report.get("mode") != "explicit" or report.get("path") != str(persistent.resolve()):
            raise AssertionError(f"bad explicit database report: {report!r}")
        connection = sqlite3.connect(persistent)
        try:
            if connection.execute("SELECT count(*) FROM nodes").fetchone()[0] != 9:
                raise AssertionError("persistent state index has the wrong cardinality")
            indexes = connection.execute("PRAGMA index_list(nodes)").fetchall()
            if not any(row[2] == 1 and row[3] == "pk" for row in indexes):
                raise AssertionError(f"state index lacks a UNIQUE primary key: {indexes}")
            stored_hash = json.loads(connection.execute(
                "SELECT value FROM metadata WHERE key='certificateSha256'"
            ).fetchone()[0])
            if stored_hash != expected_hash:
                raise AssertionError("persistent index metadata has the wrong artifact hash")
        finally:
            connection.close()
        before = sha256(persistent)
        code, refused, _ = run(str(FIXTURE), "--database", str(persistent))
        after = sha256(persistent)
        if code != 2 or refused.get("errorKind") != "operational" or before != after:
            raise AssertionError(
                f"existing database was not refused unchanged: rc={code} result={refused}"
            )

        missing = tmp / "missing.jsonl"
        code, missing_result, _ = run(str(missing))
        if code != 2 or missing_result.get("errorKind") != "operational":
            raise AssertionError(
                f"missing input did not return operational rc=2: {code}, {missing_result}"
            )

    print(json.dumps({
        "status": "ok",
        "acceptedNodes": accepted["nodes"],
        "plainAndGzipAccepted": True,
        "corruptionsRejected": (
            len(corruptions) + len(illegal_states)
            + len(second_pass_illegal_states) + len(gzip_framing)
        ),
        "gzipFramingRejected": len(gzip_framing),
        "illegalStatesRejected": len(illegal_states),
        "secondPassIllegalStatesRejected": len(second_pass_illegal_states),
        "wallConfiguredBranchAccepted": True,
        "heightTwoStalemateRejected": True,
        "provenanceHashesChecked": True,
        "crossVerifierSyntaxCases": len(shared_syntax),
        "secondPassRejections": second_pass_rejections,
        "existingDatabaseRefusedUnchanged": True,
        "exitCodesChecked": [0, 1, 2],
        "profileDifferentialStates": profiled_states,
        "profileDifferentialConfigurations": profiled_configurations,
        "declaredMovesDifferential": declared_moves,
        "largeProfileSamples": large_samples,
        "largeProfileConfigurations": large_configurations,
    }, separators=(",", ":"), sort_keys=True))


if __name__ == "__main__":
    main()
