# Codex compute node

This document turns a gaming PC into a reproducible exact-search worker. The
current exact solver is CPU and memory-hierarchy bound. The GPU is intentionally
unused until the separate learned move-ordering programme begins.

## Recommended environment

Use WSL2 with a recent Ubuntu image or native Linux. From the repository root:

```bash
sudo apt update
sudo apt install -y build-essential python3 nodejs git time
make lazy
make lazy-smoke
```

The compiler should support C++20. `-march=native` is recommended for local
runs but the compiler version and binary SHA-256 must be archived with results.

## Current handoff checklist (2026-08-01)

The local Windows PC now has MinGW GCC 16.1 and has passed the solver gates, but
the gaming PC remains the campaign host.  Repeat this clean compute-node gate
after transfer and before a campaign:

```bash
git diff --check
make test
make lazy-smoke
make lazy-differential
make external-review-smoke
make qcert-smoke
make local-gate-check
make local-touch-smoke
make local-touch-differential
make local-touch-audit-small
make experimental-qcert-smoke
```

On MinGW, the Makefile disables the PE timestamp inserted by GNU ld.  Two
identical local builds then have the same SHA-256; this was checked directly
before the TT-hint pilot.  The flag is conditional and does not affect Linux.

When calibrating the experimental TT hint-first portfolio arm, also run:

```bash
make tt-hint-first-smoke
make tt-hint-first-differential
make tt-hint-first-audit-small
```

The separate wall-mask miss-token candidate has a much smaller gate:

```bash
make mask-index-probe-check
make mask-index-probe-smoke
make mask-index-probe-differential
make mask-index-probe-audit-small
```

After those pass, run a pinned alternating A/B of the supported and experimental
binaries on several named branches. Do not add another arm to the ordering
portfolio: this is one global cache implementation choice, and the local timing
signal was smaller than thermal variance.

The TT slot-reuse candidate follows the same binary-substitution rule:

```bash
make tt-slot-reuse-check
make tt-slot-reuse-smoke
make tt-slot-reuse-differential
make tt-slot-reuse-audit-small
```

It improved the two long local calibrations by about 2% but regressed the
sub-second case. Sample a few short, medium and long known branches with pinned
alternating runs. Do not add it as a fifth ordering arm; if accepted, rebuild
the single portfolio binary with the mechanism applied uniformly.

The candidate flags are `--tt-hint-first-mode opponent
--no-tt-hint-transform`.  The mechanism is not part of the supported lazy
binary and must not silently replace a baseline policy.
Use the manifest overlay documented in `ORDERING_PORTFOLIO.md` so the same
40 stable tasks race a fourth `flow1_hint_raw` arm.  The experimental binary is
inert without explicit hint flags, keeping the original three policies valid
controls under the same binary hash.  Prefer the versioned
`experiments/policies/flow1_hint_raw.json` overlay to shell-escaped inline JSON.
Every new portfolio record binds the solver binary and the worker/parser bundle
by SHA-256; `campaign.json` also binds the source manifest and complete
normalized task universe.  Copy the committed scripts to the compute node
before starting. A changed parser or worker intentionally invalidates resume
records instead of silently mixing orchestration semantics.

`experimental-qcert-smoke` checks only sol's comparative prototype; Claude owns
the production certificate extractor and verifier. Do not substitute the
prototype for the production `qcert2` pipeline. Archive `g++ --version`, the
exact command lines and SHA-256 hashes for every binary used after this gate.
`external-review-smoke` also runs the hash-locked clean-room stalemate
regressions, so the imported evidence is checked before any new claim is made.
`qcert-smoke` exercises both the in-memory clean-room verifier and the independent
Python/SQLite verifier. For a large export, put the persistent database on a
volume with sufficient free space and preserve the single JSON result:

```bash
mkdir -p /mnt/large/qcert-indexes
python3 reference/qcert_verify_sqlite.py certificate.jsonl.gz \
  --database /mnt/large/qcert-indexes/certificate.sqlite3 \
  --progress-every 250000 > certificate.verify.json
```

The command refuses an existing database path. Remove or rename a failed index
deliberately before retrying; the verifier never guesses that it is disposable.

The cache-first local touch gate specified in
`docs/LOCAL_CYCLE_GATE_2026-08-01.md` now compiles to a distinct experimental
binary under `QSPEC_LOCAL_TOUCH_GATE_EXPERIMENT`; the baseline binary is built
without that macro.  Its isolated dump and state-solve binaries have passed:

1. move-generation differentials on the existing lazy suite;
2. bounded-proof differentials;
3. the exhaustive `3x3x1` proof grid;
4. `false_safe=0` and identical named moves;
5. the baseline versus `K=0,2,4,all` benchmark on
   `P(5,2) P(1,2) H(5,2)` with transition threshold 1.

An independent audit found that the first calibration had omitted the existing
path-flow term from deferred proxy scores.  After correction, no partial K wins
the named branch; `K=all` exactly reproduces the baseline search and costs about
5% time.  Do not allocate a wider gaming-PC portfolio to this version.  Revisit
only after a proxy redesign and net-BFS instrumentation.

## First calibration

```bash
python3 scripts/codex_compute_worker.py \
  --solver bin/lazy_specialized_solver \
  --manifest experiments/manifests/codex_smoke.jsonl \
  --outdir results/compute-node/smoke \
  --jobs 1
```

Do not start a wide frontier scan until all three tasks finish with the expected
verdicts. The worker writes one atomic JSON record per task and resumes from
matching records after interruption.

## Parallelism

Each proof search is single-threaded. Parallelism is therefore across independent
branches. Begin with four workers, then compare total throughput at six and eight.
More workers are not automatically better because all processes compete for the
last-level CPU cache and memory bandwidth.

Approximate TT payload for the current 12-byte entry layout:

| `--tt-bits` | TT payload |
|---:|---:|
| 24 | 192 MiB |
| 25 | 384 MiB |
| 26 | 768 MiB |
| 27 | 1.5 GiB |

On the reference hard branch, TT26 was faster than TT27 even though TT27 expanded
fewer nodes. This is a memory-hierarchy effect, not an invitation to buy RAM until
latency develops manners.

For a 32 GiB machine, a sensible first frontier configuration is four to six
concurrent TT26 workers. Record wall time, nodes, TT hits and peak RSS before
increasing concurrency.

## Trusted and experimental modes

Final audit runs use:

```text
--no-bounds --no-pawn-table --transition-cache-threshold 1
```

The lazy configuration and transition caches contain only deterministic board
facts. They may be shared within a scan. Each proof branch still receives a fresh
transposition table.

Do not enable the following rejected defaults without a new benchmark:

- local per-configuration perfect TT;
- four-way TT at fixed total entry count;
- horizon stock capping;
- naive repeated stock-dominance probes.

## Result handling

Commit summaries and small JSON records. Keep very large raw logs or cache
snapshots as release artifacts or external archives, with SHA-256 files. Never
replace a completed proof record in place without preserving its solver hash and
command line.


## First compute-node campaign: known `4×7×7` branches

The `3x9x10` certificate programme is closed after Claude's aggregate receipt;
do not use the gaming PC to replicate it again.  Before spending hours on the
open depth-27 frontier, replay the known 40-branch central-reply family. Stable
names make the comparison valid across policies, and any verdict mismatch is
immediately a defect.

```bash
python3 scripts/codex_portfolio_worker.py \
  --solver bin/lazy_tt_hint_first_solver \
  --manifest experiments/manifests/4x7_w7_central_reply_portfolio.jsonl \
  --outdir results/compute-node/4x7-known-ordering \
  --jobs 1 \
  --append-policy-file experiments/policies/flow1_hint_raw.json
```

This first pass is the four-policy promotion gate.  Start at one portfolio task
(four TT26 processes), then increase only after measuring aggregate throughput
and resident memory on the target machine.

## Exact ordering portfolios

The supported worker races three exact move-ordering policies on stable named
positions:

```text
baseline : --path-choice-weight 0
choice40 : --path-choice-weight 40
flow1    : --path-flow-weight 1 --path-flow-cache-bits 18
```

`flow1` measures the fraction of the complete shortest-path DAG blocked by each
wall. It is not globally superior, but it wins a difficult pawn-move regime where
the immediate-choice policy does not.

Do not compare orderings with child indices because the ordering itself changes
those indices. For production campaigns use `scripts/codex_portfolio_worker.py`.
It accepts the first exact completion and cancels the other policy processes.

Start with:

```bash
python3 scripts/codex_portfolio_worker.py \
  --solver bin/lazy_specialized_solver \
  --manifest experiments/manifests/order_portfolio_smoke.jsonl \
  --outdir results/compute-node/order-smoke \
  --jobs 1
```

Then reproduce the 40 known central-reply branches before attacking the new
frontier. On a Ryzen 5900X with 32 GiB, begin with `--jobs 2`, which creates six
solver processes. See `docs/ORDERING_PORTFOLIO.md` for commands and memory
guidance.
