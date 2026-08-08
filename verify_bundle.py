#!/usr/bin/env python3
"""Top-level integrity check for the publication bundle.

Usage:
    python3 verify_bundle.py [--no-fixtures] [--require-assets] [--quiet]

Checks, in order:

1. MANIFEST.sha256 — every listed file must exist and hash to the exact
   pinned SHA-256 (byte-strict; the repository ships a `.gitattributes`
   with `* -text` so checkouts are byte-identical on every platform).
   Also reports tracked-but-unlisted files when run inside a git checkout.
2. Internal consistency of the certificate registries: every part listed
   in emitter/aggregate/aggregate.json must appear in
   emitter/aggregate/EXPORTS.jsonl with the same SHA-256.
3. Release assets (the 18 multi-gigabyte qcert-1 parts, distributed as
   GitHub release assets, expected under emitter/aggregate/parts/): any
   part present locally is hashed and checked against EXPORTS.jsonl.
   Absent parts are reported as SKIPPED unless --require-assets is given.
4. Fast fixtures (skippable with --no-fixtures): the emitter Node test
   suite (requires `node`), as a smoke check that the bundle is runnable.

Exit code 0 iff everything checked passed (skips are not failures unless
--require-assets).
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
MANIFEST = os.path.join(ROOT, "MANIFEST.sha256")
EXPORTS = os.path.join(ROOT, "emitter", "aggregate", "EXPORTS.jsonl")
AGGREGATE = os.path.join(ROOT, "emitter", "aggregate", "aggregate.json")
PARTS_DIR = os.path.join(ROOT, "emitter", "aggregate", "parts")


def sha256_file(path, bufsize=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(bufsize)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def check_manifest(quiet):
    ok = mismatched = missing = 0
    bad = []
    listed = set()
    with open(MANIFEST, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line:
                continue
            digest, name = line.split(maxsplit=1)
            name = name.lstrip("*")
            listed.add(name)
            path = os.path.join(ROOT, name)
            if not os.path.isfile(path):
                missing += 1
                bad.append(("MISSING", name))
                continue
            if sha256_file(path) == digest.lower():
                ok += 1
            else:
                mismatched += 1
                bad.append(("MISMATCH", name))
    for status, name in bad:
        print(f"  {status}: {name}")
    print(f"[1] manifest: {ok} OK, {mismatched} mismatched, {missing} missing")

    unlisted = []
    if shutil.which("git") and os.path.isdir(os.path.join(ROOT, ".git")):
        tracked = subprocess.run(
            ["git", "-C", ROOT, "ls-files"],
            capture_output=True, text=True, check=True,
        ).stdout.splitlines()
        unlisted = [t for t in tracked if t not in listed and t != "MANIFEST.sha256"]
        for name in unlisted:
            print(f"  UNLISTED (tracked but not in manifest): {name}")
        if unlisted:
            print(f"[1] manifest coverage: {len(unlisted)} tracked files unlisted")
    return mismatched == 0 and missing == 0 and not unlisted


def load_exports():
    parts = {}
    with open(EXPORTS, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rec = json.loads(line)
                parts[os.path.basename(rec["path"])] = rec
    return parts


def check_registries():
    exports = load_exports()
    with open(AGGREGATE, encoding="utf-8") as f:
        agg = json.load(f)
    ok = True
    for part in agg["parts"]:
        base = os.path.basename(part["path"])
        rec = exports.get(base)
        if rec is None:
            print(f"  aggregate part not in EXPORTS.jsonl: {base}")
            ok = False
        elif rec["sha256_gz"].lower() != part["sha256"].lower():
            print(f"  SHA-256 disagreement between registries: {base}")
            ok = False
    print(f"[2] registries: {len(agg['parts'])} aggregate parts cross-checked "
          f"against EXPORTS.jsonl -> {'OK' if ok else 'FAILED'}")
    return ok


def check_assets(require):
    exports = load_exports()
    present = absent = failed = 0
    for base, rec in sorted(exports.items()):
        path = os.path.join(PARTS_DIR, base)
        if not os.path.isfile(path):
            absent += 1
            continue
        present += 1
        size_ok = os.path.getsize(path) == rec["bytes_gz"]
        hash_ok = size_ok and sha256_file(path) == rec["sha256_gz"].lower()
        if not hash_ok:
            failed += 1
            print(f"  ASSET FAILED: {base}")
    verdict = "FAILED" if failed or (require and absent) else "OK"
    print(f"[3] release assets: {present} present ({failed} failed), "
          f"{absent} absent ({'required' if require else 'skipped'}) -> {verdict}")
    return verdict == "OK"


def check_fixtures():
    node = shutil.which("node")
    if node is None:
        print("[4] fixtures: node not found -> SKIPPED")
        return True
    proc = subprocess.run(
        [node, "test.js"], cwd=os.path.join(ROOT, "emitter"),
        capture_output=True, text=True, timeout=900,
    )
    ok = proc.returncode == 0
    tail = (proc.stdout.strip().splitlines() or [""])[-1]
    print(f"[4] fixtures: emitter test suite -> {'OK' if ok else 'FAILED'} ({tail})")
    if not ok:
        sys.stdout.write(proc.stdout[-2000:] + proc.stderr[-2000:])
    return ok


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--no-fixtures", action="store_true",
                    help="skip the runnable-bundle smoke tests")
    ap.add_argument("--require-assets", action="store_true",
                    help="fail if any of the 18 release-asset parts is absent")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    results = [check_manifest(args.quiet), check_registries(),
               check_assets(args.require_assets)]
    if not args.no_fixtures:
        results.append(check_fixtures())

    if all(results):
        print("verify_bundle: PASS")
        return 0
    print("verify_bundle: FAIL")
    return 1


if __name__ == "__main__":
    sys.exit(main())
