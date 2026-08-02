#!/usr/bin/env python3
"""End-to-end, corruption, and reflection checks for qcert-aggregate-1."""
from __future__ import annotations

from collections import deque
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from qcert_aggregate_verify import (
    AggregateValidationError,
    PUBLISHED_CLAIM,
    PUBLISHED_REPRESENTATIVES,
    check_mirror_automorphism,
    mirror_state,
    move_label,
    state_object,
    verify_aggregate,
)
from quoridor_reference import ReferenceGame


ROOT = Path(__file__).resolve().parents[1]
VERIFIER = ROOT / "reference" / "qcert_aggregate_verify.py"
QCERT_VERIFIER = ROOT / "reference" / "qcert_verify_sqlite.py"
RULES_ENGINE = ROOT / "reference" / "quoridor_reference.py"
FIXTURE = ROOT / "results" / "validation" / "qcert-aggregate"


def run(manifest: Path, artifact_root: Path) -> tuple[int, dict[str, object], str]:
    completed = subprocess.run(
        [
            sys.executable,
            str(VERIFIER),
            str(manifest),
            "--artifact-root",
            str(artifact_root),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise AssertionError(
            f"verifier emitted invalid JSON (rc={completed.returncode}): "
            f"stdout={completed.stdout!r} stderr={completed.stderr!r}"
        ) from error
    if not isinstance(result, dict):
        raise AssertionError(f"verifier result is not an object: {result!r}")
    return completed.returncode, result, completed.stderr


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, separators=(",", ":"), sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def expect_reject(
    root: Path,
    name: str,
    value: object | None = None,
    *,
    raw: str | None = None,
) -> dict[str, object]:
    path = root / f"reject-{name}.json"
    if raw is not None:
        path.write_text(raw, encoding="utf-8", newline="\n")
    else:
        write_json(path, value)
    code, result, stderr = run(path, root)
    if code != 1 or result.get("ok") is not False or result.get("errorKind") != "invalid":
        raise AssertionError(
            f"{name} was not rejected as invalid proof data: "
            f"rc={code}, result={result}, stderr={stderr!r}"
        )
    if not result.get("errors"):
        raise AssertionError(f"{name} rejection omitted diagnostics")
    return result


def production_partition_check() -> tuple[int, int]:
    game = ReferenceGame(3, 9, 10)
    root = game.initial()
    opening = next(move for move in game.legal_moves(root) if move_label(move) == "P:22")
    post_opening = game.apply(root, opening)
    replies = {move_label(move): game.apply(post_opening, move)
               for move in game.legal_moves(post_opening)}
    state_to_label = {state: label for label, state in replies.items()}
    representatives: set[str] = set()
    seen: set[str] = set()
    for label, state in replies.items():
        if label in seen:
            continue
        mate = state_to_label[mirror_state(game, state)]
        # Reflected pairs always share kind and row, so numeric labels sort by
        # their final cell/anchor coordinate here.
        def key(item: str) -> tuple[str, tuple[int, ...]]:
            fields = item.split(":")
            return fields[0], tuple(int(field) for field in fields[1:])
        representative = min((label, mate), key=key)
        representatives.add(representative)
        seen.update((label, mate))
    if len(replies) != 35 or len(representatives) != 18:
        raise AssertionError(
            f"production geometry changed: replies={len(replies)}, "
            f"orbits={len(representatives)}"
        )
    if representatives != PUBLISHED_REPRESENTATIVES:
        raise AssertionError(
            f"production representatives changed: {sorted(representatives)}"
        )
    return len(replies), len(representatives)


def production_manifest_check(root: Path) -> dict[str, object]:
    """Exercise the exact 35-reply/18-part glue with a typed fake part oracle.

    Real qcert verification is covered end-to-end by the small fixture.  This
    larger structural test isolates the production partition without creating
    eighteen enormous strategy DAGs.
    """
    game = ReferenceGame(3, 9, 10)
    initial = game.initial()
    opening = next(move for move in game.legal_moves(initial) if move_label(move) == "P:22")
    post_opening = game.apply(initial, opening)
    responses = {move_label(move): game.apply(post_opening, move)
                 for move in game.legal_moves(post_opening)}
    state_to_move = {state: label for label, state in responses.items()}

    def label_key(label: str) -> tuple[str, tuple[int, ...]]:
        fields = label.split(":")
        return fields[0], tuple(int(field) for field in fields[1:])

    canonical_for: dict[str, str] = {}
    for label, state in responses.items():
        mate = state_to_move[mirror_state(game, state)]
        canonical_for[label] = min((label, mate), key=label_key)

    identifiers = {
        representative: "part-" + representative.replace(":", "-")
        for representative in sorted(set(canonical_for.values()), key=label_key)
    }
    parts: list[dict[str, object]] = []
    by_filename: dict[str, dict[str, object]] = {}
    for representative, part_id in identifiers.items():
        filename = f"{part_id}.qcert1"
        path = root / filename
        path.write_bytes((representative + "\n").encode())
        part = {
            "id": part_id,
            "path": filename,
            "sha256": digest(path),
            "bound": 33,
            "root": state_object(responses[representative]),
        }
        parts.append(part)
        by_filename[filename] = part
    replies = [
        {
            "move": label,
            "part": identifiers[canonical_for[label]],
            "transform": "identity" if label == canonical_for[label]
                         else "mirror-columns",
        }
        for label in sorted(responses, key=label_key)
    ]
    manifest = {
        "type": "aggregate",
        "format": "qcert-aggregate-1",
        "claim": copy.deepcopy(PUBLISHED_CLAIM),
        "parts": parts,
        "replies": replies,
    }
    manifest_path = root / "production-structure.json"
    write_json(manifest_path, manifest)

    def fake_part_verifier(path: Path, **_: object) -> dict[str, object]:
        part = by_filename[path.name]
        return {
            "ok": True,
            "certificateSha256": part["sha256"],
            "certificateBytes": path.stat().st_size,
            "claim": {
                "scope": "branch-position",
                "width": 3,
                "height": 9,
                "walls": 10,
                "winner": 1,
                "bound": 33,
                "root": part["root"],
            },
            "rootIsInitialPosition": False,
            "verifiedTransforms": ["identity"],
            "verifierSha256": digest(QCERT_VERIFIER),
            "rulesSha256": digest(RULES_ENGINE),
            "rootBudget": 33,
            "nodes": 1,
            "edgesChecked": 1,
        }

    result = verify_aggregate(
        manifest_path,
        root,
        part_verifier=fake_part_verifier,
    )
    expected = {
        "published3x9w10Profile": True,
        "regeneratedReplies": 35,
        "reflectionOrbits": 18,
        "derivedBound": 35,
    }
    for field, value in expected.items():
        if result.get(field) != value:
            raise AssertionError(
                f"production aggregate {field}={result.get(field)!r}, expected {value!r}"
            )
    provenance_corruptions = 0
    for source_field in ("verifierSha256", "rulesSha256"):
        def wrong_source(path: Path, *, _field: str = source_field, **kwargs: object) -> dict[str, object]:
            report = fake_part_verifier(path, **kwargs)
            report[_field] = "0" * 64
            return report

        try:
            verify_aggregate(manifest_path, root, part_verifier=wrong_source)
        except AggregateValidationError as error:
            if "different" not in str(error):
                raise AssertionError(
                    f"wrong {source_field} produced an unrelated diagnostic: {error}"
                ) from error
            provenance_corruptions += 1
        else:
            raise AssertionError(f"wrong {source_field} was accepted")
    result["testProvenanceCorruptionsRejected"] = provenance_corruptions
    return result


def metamorphic_check() -> int:
    game = ReferenceGame(3, 3, 1)
    initial = game.initial()
    queue = deque([initial])
    seen = {initial}
    while queue:
        state = queue.popleft()
        check_mirror_automorphism(game, state)
        if game.winner(state) is not None:
            continue
        for move in game.legal_moves(state):
            child = game.apply(state, move)
            if child not in seen:
                seen.add(child)
                queue.append(child)
    if len(seen) != 2856:
        raise AssertionError(f"unexpected 3x3x1 reachable-state count: {len(seen)}")
    return len(seen)


def main() -> None:
    code, accepted, stderr = run(FIXTURE / "aggregate.json", FIXTURE)
    if code != 0 or accepted.get("ok") is not True:
        raise AssertionError(
            f"valid aggregate rejected: rc={code}, result={accepted}, stderr={stderr!r}"
        )
    expected = {
        "derivedBound": 5,
        "suffixBound": 3,
        "regeneratedReplies": 3,
        "reflectionOrbits": 2,
        "identityRepresentatives": ["P:0", "P:4"],
        "verifiedTransforms": ["identity", "mirror-columns"],
        "mirrorProofBasis": "rule-automorphism",
        "published3x9w10Profile": False,
        "trustedPrecomputedListings": False,
        "manifestSha256": digest(FIXTURE / "aggregate.json"),
        "manifestBytes": (FIXTURE / "aggregate.json").stat().st_size,
        "aggregateVerifierSha256": digest(VERIFIER),
        "qcertVerifierSha256": digest(QCERT_VERIFIER),
        "rulesSha256": digest(RULES_ENGINE),
    }
    for field, value in expected.items():
        if accepted.get(field) != value:
            raise AssertionError(
                f"accepted {field}={accepted.get(field)!r}, expected {value!r}"
            )
    part_reports = accepted.get("parts")
    if not isinstance(part_reports, list) or len(part_reports) != 2:
        raise AssertionError(f"accepted part reports are incomplete: {part_reports!r}")

    production_replies, production_orbits = production_partition_check()
    metamorphic_states = metamorphic_check()

    valid = json.loads((FIXTURE / "aggregate.json").read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(prefix="qcert-aggregate-check-") as directory:
        tmp = Path(directory)
        shutil.copy2(FIXTURE / "branch_left.jsonl", tmp / "branch_left.jsonl")
        shutil.copy2(FIXTURE / "branch_center.jsonl", tmp / "branch_center.jsonl")
        production_manifest = production_manifest_check(tmp)

        mutated_manifest = tmp / "valid-whitespace-mutation.json"
        mutated_manifest.write_bytes((FIXTURE / "aggregate.json").read_bytes() + b" \n")
        mutation_code, mutation_result, mutation_stderr = run(mutated_manifest, tmp)
        if mutation_code != 0 or mutation_result.get("ok") is not True:
            raise AssertionError(
                f"valid manifest byte mutation was rejected: rc={mutation_code}, "
                f"result={mutation_result}, stderr={mutation_stderr!r}"
            )
        if mutation_result.get("manifestSha256") != digest(mutated_manifest):
            raise AssertionError("manifest report did not hash the exact parsed bytes")
        if mutation_result.get("manifestBytes") != mutated_manifest.stat().st_size:
            raise AssertionError("manifest report did not count the exact parsed bytes")
        if mutation_result.get("manifestSha256") == accepted.get("manifestSha256"):
            raise AssertionError("manifest byte mutation did not change the reported hash")

        corruptions: list[tuple[str, object]] = []

        def changed(mutator: object) -> dict[str, object]:
            value = copy.deepcopy(valid)
            assert callable(mutator)
            mutator(value)
            return value

        corruptions.extend([
            ("extra_top", changed(lambda x: x.update({"extra": 0}))),
            ("extra_claim", changed(lambda x: x["claim"].update({"extra": 0}))),
            ("extra_root", changed(lambda x: x["claim"]["root"].update({"extra": 0}))),
            ("extra_part", changed(lambda x: x["parts"][0].update({"extra": 0}))),
            ("extra_reply", changed(lambda x: x["replies"][0].update({"extra": 0}))),
            ("boolean_integer", changed(lambda x: x["claim"].update({"width": True}))),
            ("floating_integer", changed(lambda x: x["claim"].update({"height": 4.0}))),
            ("unsafe_integer", changed(
                lambda x: x["claim"].update({"bound": 9007199254740992})
            )),
            ("non_initial_root", changed(lambda x: x["claim"]["root"].update({"p1": 9}))),
            ("illegal_witness", changed(lambda x: x["claim"].update({"witness": "P:0"}))),
            ("asymmetric_witness", changed(
                lambda x: x["claim"].update({"witness": "P:9"})
            )),
            ("bad_derived_bound", changed(lambda x: x["claim"].update({"bound": 7}))),
            ("uppercase_hash", changed(
                lambda x: x["parts"][0].update({"sha256": x["parts"][0]["sha256"].upper()})
            )),
            ("wrong_hash", changed(
                lambda x: x["parts"][0].update({"sha256": "0" * 64})
            )),
            ("duplicate_id", changed(lambda x: x["parts"][1].update({"id": "pawn-left"}))),
            ("duplicate_path", changed(
                lambda x: x["parts"][1].update({"path": "branch_left.jsonl"})
            )),
            ("normalized_path", changed(
                lambda x: x["parts"][0].update({"path": "./branch_left.jsonl"})
            )),
            ("absolute_path", changed(
                lambda x: x["parts"][0].update({
                    "path": (tmp / "branch_left.jsonl").resolve().as_posix(),
                })
            )),
            ("drive_style_path", changed(
                lambda x: x["parts"][0].update({"path": "C:/outside.jsonl"})
            )),
            ("traversal_path", changed(
                lambda x: x["parts"][0].update({"path": "../branch_left.jsonl"})
            )),
            ("missing_reply", changed(lambda x: x["replies"].pop())),
            ("extra_reply_move", changed(
                lambda x: x["replies"][1].update({"move": "P:99"})
            )),
            ("duplicate_reply", changed(
                lambda x: x["replies"].append(copy.deepcopy(x["replies"][0]))
            )),
            ("unknown_transform", changed(
                lambda x: x["replies"][1].update({"transform": "rotate"})
            )),
            ("wrong_orbit_transform", changed(
                lambda x: x["replies"][1].update({"transform": "identity"})
            )),
            ("part_root_mismatch", changed(
                lambda x: x["parts"][0]["root"].update({"p2": 1})
            )),
        ])

        def reverse_representative(value: dict[str, object]) -> None:
            value["parts"][0]["root"]["p2"] = 2  # type: ignore[index]
            value["replies"][0]["transform"] = "mirror-columns"  # type: ignore[index]
            value["replies"][1]["transform"] = "identity"  # type: ignore[index]

        corruptions.append(("noncanonical_representative", changed(reverse_representative)))

        third = tmp / "unused.jsonl"
        shutil.copy2(tmp / "branch_center.jsonl", third)

        def add_unused(value: dict[str, object]) -> None:
            unused = copy.deepcopy(value["parts"][1])  # type: ignore[index]
            unused["id"] = "unused"
            unused["path"] = "unused.jsonl"
            value["parts"].append(unused)  # type: ignore[union-attr]

        corruptions.append(("unused_part", changed(add_unused)))

        for name, value in corruptions:
            expect_reject(tmp, name, value)

        canonical_text = json.dumps(valid, separators=(",", ":"), sort_keys=True)
        duplicate_member = canonical_text.replace(
            '"format":"qcert-aggregate-1"',
            '"format":"qcert-aggregate-1","format":"qcert-aggregate-1"',
            1,
        )
        expect_reject(tmp, "duplicate_member", raw=duplicate_member)
        nan_number = canonical_text.replace('"bound":5', '"bound":NaN', 1)
        expect_reject(tmp, "nonstandard_number", raw=nan_number)

        bad_certificate = tmp / "bad_certificate.jsonl"
        bad_text = (tmp / "branch_left.jsonl").read_text(encoding="utf-8").replace(
            '"move":"P:4"', '"move":"P:11"', 1,
        )
        bad_certificate.write_text(bad_text, encoding="utf-8", newline="\n")

        def bind_bad_certificate(value: dict[str, object]) -> None:
            value["parts"][0]["path"] = "bad_certificate.jsonl"  # type: ignore[index]
            value["parts"][0]["sha256"] = digest(bad_certificate)  # type: ignore[index]

        expect_reject(tmp, "invalid_qcert_part", changed(bind_bad_certificate))

        wrong_header = tmp / "wrong_header_bound.jsonl"
        header_text = (tmp / "branch_left.jsonl").read_text(encoding="utf-8").replace(
            '"bound":3', '"bound":4', 1,
        )
        wrong_header.write_text(header_text, encoding="utf-8", newline="\n")

        def bind_wrong_header(value: dict[str, object]) -> None:
            value["parts"][0]["path"] = "wrong_header_bound.jsonl"  # type: ignore[index]
            value["parts"][0]["sha256"] = digest(wrong_header)  # type: ignore[index]

        expect_reject(tmp, "qcert_claim_binding", changed(bind_wrong_header))

        outside = tmp.parent / f"{tmp.name}-outside.jsonl"
        shutil.copy2(tmp / "branch_left.jsonl", outside)
        symlink_checked = False
        link = tmp / "escape.jsonl"
        try:
            os.symlink(outside, link)
        except OSError:
            pass
        else:
            symlink_checked = True

            def bind_escape(value: dict[str, object]) -> None:
                value["parts"][0]["path"] = "escape.jsonl"  # type: ignore[index]

            expect_reject(tmp, "symlink_escape", changed(bind_escape))
        finally:
            outside.unlink(missing_ok=True)

        hardlink_checked = False
        hardlink = tmp / "hardlink-center.jsonl"
        try:
            os.link(tmp / "branch_center.jsonl", hardlink)
        except OSError:
            pass
        else:
            hardlink_checked = True

            def bind_hardlink_alias(value: dict[str, object]) -> None:
                value["parts"][0]["path"] = "hardlink-center.jsonl"  # type: ignore[index]

            expect_reject(tmp, "hardlink_alias", changed(bind_hardlink_alias))

        code, missing_result, _ = run(tmp / "missing-manifest.json", tmp)
        if code != 2 or missing_result.get("errorKind") != "operational":
            raise AssertionError(
                f"missing manifest did not return operational rc=2: "
                f"rc={code}, result={missing_result}"
            )

    print(json.dumps({
        "status": "ok",
        "fixtureParts": 2,
        "fixtureReplies": 3,
        "productionReplies": production_replies,
        "productionReflectionOrbits": production_orbits,
        "productionManifestAccepted": production_manifest["published3x9w10Profile"],
        "metamorphicReachableStates": metamorphic_states,
        "corruptionsRejected": (
            len(corruptions) + 4 + int(symlink_checked) + int(hardlink_checked)
        ),
        "symlinkEscapeChecked": symlink_checked,
        "hardlinkAliasChecked": hardlink_checked,
        "manifestByteMutationBound": True,
        "sourceProvenanceBound": True,
        "sourceProvenanceCorruptionsRejected": production_manifest[
            "testProvenanceCorruptionsRejected"
        ],
        "partVerifier": "sqlite",
        "exitCodesChecked": [0, 1, 2],
    }, separators=(",", ":"), sort_keys=True))


if __name__ == "__main__":
    main()
