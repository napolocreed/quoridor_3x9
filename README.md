# Exactly 35: Certified Solving of 3×9 Quoridor — Publication Artifacts

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.21763852.svg)](https://doi.org/10.5281/zenodo.21763852)

This bundle contains everything needed to **check** the results of the paper
(`paper/main.pdf`) without trusting any solver: sources, proof journals,
certificates, receipts, and the independent verifiers. It is a curated,
byte-pinned copy of two working research trees (see *Provenance*).

**Headline claims.** On the 3×9 board, the first player wins with 9 and with
10 walls per player; with 10 walls the forcing horizon is **exactly 35
plies**. The winning claim is backed by a solver-independent certificate
stack, verified end to end by two independent verifiers of different
architectures.

## Layout

| Directory | Contents | Origin |
|---|---|---|
| `emitter/` | Replication solver (`qsolve.cpp`), certificate pipeline (`qcert2`, `qexport`, `qmerge`), clean-room verifiers (`verify_cert.py`, `qverify.cpp`), proof journals (`replication/`, `replication9/`), aggregate manifest + acceptance receipt (`aggregate/`), theorems (`STALEMATE_THEOREM.md`, `RACE_ZUGZWANG*.md`), experiments, coordination notes | Claude's tree (`claude-help/`) |
| `judge/` | Primary solver and audit apparatus (`src/`, `scripts/`), reference rule engines and verifiers (`reference/`, incl. the frozen SQLite qcert verifier), format specs (`docs/`), validation receipts (`results/`), run logs | sol's tree (`quoridor-frontier-research/`), copied verbatim minus `build/`, `bin/` |
| `paper/` | `main.tex`, `ref.bib`, compiled `main.pdf`, evidence matrix (`results/`, `issues/`) | paper tree |

The two solver/verifier trees are **disjoint by construction** (no shared
code); this physical separation is the paper's methodology, preserved here.

## Claims → artifacts

| Paper claim | Where to look |
|---|---|
| Upper bound 35 (primary audit, 9.31G nodes) | `judge/results/3x9_w10/`, `judge/RESULTS.md` |
| Lower bound 33-refutations (primary, 3.55G nodes) | `judge/results/3x9_w10/audit/lower_bound_33/`, `judge/RESULTS.md` |
| Replication (both bounds, separate architecture) | `emitter/replication/AGGREGATE_upper_pc.json`, `AGGREGATE_lower.json`, `lower_*.json`, `PIPELINE.log`, `LOWER.log` |
| 18 certificate parts, exhaustive clean-room check (612,890,536 expansions, 0 violations, 1,262.6 s) | `emitter/replication/EXHAUSTIVE.log`, `AGGREGATE_exhaustive.json`; verifier: `emitter/qverify.cpp` |
| Cross-architecture part acceptance (H10, 9,836,857 nodes) | `judge/results/validation/qcert/H10_sqlite_verification_2026-08-01.json` |
| **Aggregate acceptance (root claim, derived bound 35)** | `emitter/aggregate/AGGREGATE_VERIFY_RECEIPT.json` (`ok:true`), manifest `aggregate.json`, part registry `EXPORTS.jsonl`; verifier: `judge/reference/qcert_aggregate_verify.py` |
| No-stalemate theorem (H≥3, sharp at H=2) | `emitter/STALEMATE_THEOREM.md`, `emitter/qscan.mjs`, `emitter/results-stalemate/` |
| Race dichotomy + adversarially audited proof | `emitter/RACE_ZUGZWANG.md`, `RACE_ZUGZWANG_PROOF.md` (audit A1–A10 inside), sweeps `racesweep.mjs`, `race_param.mjs` |
| Certificates as refutation oracles (−19.9% nodes / −34.4% time) | `emitter/replication/LOWERSEED.log`, `lowerseed_*.json`; implementation: `--tt-seed` in `emitter/qsolve.cpp` |
| Learned-ordering feasibility probe (97% top-3) | `emitter/EXPERIENCE_DATASET.md`, `train_probe*.py`, weights `emitter/dataset/*.npz` |
| 3×9×9 upper bound (win ≤ 35) | `emitter/replication9/` |
| 4×7×7 partial bounds | `judge/results/`, `judge/RESULTS.md` |
| Format specifications | `judge/docs/CERTIFICATE_FORMAT.md`, `judge/docs/QCERT_AGGREGATE_FORMAT.md`; emitter-side mirror: `emitter/CERTIFICATE_FORMAT.md` |

## Large binaries (GitHub Releases, not in-tree)

The certificate **parts** are too large for a repository and ship as release
assets; their integrity is already pinned inside this tree:

- 18 gzipped `qcert-1` parts (~3.1 GiB total, largest 1.17 GiB): SHA-256 of
  every stored `.gz` (and of the raw JSONL) in `emitter/aggregate/EXPORTS.jsonl`
  and in the manifest `aggregate.json`. Place them under
  `emitter/aggregate/parts/` to run the aggregate verifier.
- 18 binary strategy parts (1,529,384,992 bytes, 191,173,124 sorted
  state–move pairs, zero order/duplication faults per `qmerge --mode check`).
- The raw H10 export (881,735,925 bytes) is pinned at SHA-256
  `961df2b3b91ba136404f5a24fd2a98c1ed886a3443ab5cfd71f4abddbaeff1d4` by the
  cross-verification receipt.
- CertMap memos (`work/memo_*.bin`, ~8 GiB) are **regenerable** from the
  pipeline (`orchestrate.py`) and are not published.

## How to verify (quickstart)

Everything below is single-machine, no network. Toolchain used: g++ ≥ 13
(`-O3 -std=c++20`), Python ≥ 3.10, Node ≥ 20.

```bash
# 0. Bundle integrity: byte-strict manifest check, certificate-registry
#    cross-check, release-asset hashes (for any parts present), fast fixtures.
#    Run in CI on every push (.github/workflows/verify.yml).
python3 verify_bundle.py
# 1. Rules self-test + one branch proof (minutes)
g++ -O3 -std=c++20 -o qsolve emitter/qsolve.cpp
./qsolve --mode selftest --games 200 --plies 200
./qsolve --mode branch --first "P(7,1)" --second "H(1,0)" --target 1 \
  --start-depth 31 --max-depth 31 --tt-bits 25 --cache-bits 22

# 2. Exhaustive clean-room check of one certificate part (seconds–minutes)
g++ -O3 -std=c++20 -o qverify emitter/qverify.cpp
./qverify --part <H10.bin from Releases> --reply "H(1,0)" --memo-bits 25

# 3. Independent cross-architecture check of one qcert-1 part (~20 min)
python judge/reference/qcert_verify_sqlite.py <H10.qcert1.jsonl.gz>

# 4. The root claim, end to end (~8.4 h; needs the 18 .gz parts in place)
python judge/reference/qcert_aggregate_verify.py \
  emitter/aggregate/aggregate.json --artifact-root emitter/aggregate
```

Expected outputs (node counts, hashes, timings) for every step are in the
proof journals cited above; the aggregate run must end with `ok: true` and
`derivedBound: 35`.

## Conventions warning

The two trees use **opposite board orientations** (documented in each);
the paper fixes a single convention in §2 and all paper coordinates follow
it. Never mix coordinates from both trees without converting.

## Provenance and integrity

- This bundle is a **copy** assembled on 2026-08-02/03; the working trees
  remain canonical and untouched.
- `MANIFEST.sha256` covers every tracked file of this repository (except
  itself) and hashes the **exact committed bytes**. A `.gitattributes` with
  `* -text` disables all end-of-line conversion, so any `git clone` — on any
  OS — satisfies `sha256sum -c MANIFEST.sha256`. The manifest is regenerated
  from `git ls-files` at release time and checked in CI on every push;
  `python3 verify_bundle.py` is the one-command entry point (manifest +
  registry cross-checks + release-asset hashes + fast fixtures).
- Full run logs of the primary 4×7 exploration campaign
  (`judge/runlogs/4x7_w7/`) remain in the canonical working tree and are not
  part of this bundle; the machine-readable audit records they summarize are
  under `judge/results/4x7_w7/`.
- Pinned identity of this bundle: Zenodo archive DOI
  [10.5281/zenodo.21763852](https://doi.org/10.5281/zenodo.21763852);
  the corresponding Git commit SHA and release tag are recorded on the
  Zenodo deposit and on the GitHub release page. The multi-gigabyte
  certificate parts are separately hashed release assets, pinned in-tree by
  `emitter/aggregate/EXPORTS.jsonl` and `aggregate.json`.
- `judge/` was copied verbatim (minus compiled `build/`, `bin/` and the
  `runlogs/` noted above). Its inner `SHA256SUMS` is a historical record of
  sol's original working tree, kept for provenance — it is **not** the
  integrity manifest of this bundle (only `MANIFEST.sha256` is). The frozen
  cross-verifier `reference/qcert_verify_sqlite.py` matches the
  receipt-pinned SHA-256
  `d8addf93a09a7f01693ebb09490801346a1368450ddf3b15c340c9fc39bdfa93`.
- The research was carried out by two mutually auditing AI systems under
  the direction of the human author; the coordination notes in both trees
  are part of the record (see the paper's Acknowledgments and Disclosure).
