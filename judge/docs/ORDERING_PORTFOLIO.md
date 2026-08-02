# Exact ordering portfolios

Move ordering changes cost, never proof semantics. Corridor positions show severe
algorithm-selection variance: one exact ordering can be more than ten times
faster on one branch and much slower on another.

## Stable position specification

Never identify a forced position by sorted child index when comparing orderings.
Use labels:

```bash
--root-move 'P(5,2)' \
--second-move 'P(1,2)' \
--third-move 'H(5,2)'
```

The portfolio worker rejects `--root-index`, `--root-index2` and `--root-index3`.
This guard was added after an apparently miraculous benchmark turned out to be
two different positions wearing the same integer.

## Policies

The current manifests race three exact policies:

```json
[
  {"name":"baseline","args":["--path-choice-weight","0"]},
  {"name":"choice40","args":["--path-choice-weight","40"]},
  {"name":"flow1","args":["--path-choice-weight","0","--path-flow-weight","1","--path-flow-cache-bits","18"]}
]
```

- `baseline` uses distance, stock and progress ordering;
- `choice40` rewards the number of immediate shortest-path continuations;
- `flow1` scores the fraction of the complete shortest-path DAG cut by a wall.

The last feature uses a direct-mapped 2^18-entry cache, about 22 MiB per process.
See `docs/SHORTEST_PATH_FLOW_ORDERING_2026-08-01.md`.

## Running a portfolio

```bash
python3 scripts/codex_portfolio_worker.py \
  --solver bin/lazy_specialized_solver \
  --manifest experiments/manifests/order_portfolio_smoke.jsonl \
  --outdir results/compute-node/order-smoke \
  --jobs 1
```

A task launches all listed policies concurrently. The first process returning a
parseable exact result with `timeout=0` wins; remaining process groups are
terminated. If several exact processes are first observed in the same polling
interval or the 20 ms co-winner grace, their solver-reported finish times break
the tie deterministically. Results are written atomically and skipped only when
solver hash, worker/parser bundle hash, arguments and policy definitions all
match.

POSIX cancellation targets the complete process group.  The Windows path
terminates the direct process and is supported for the current leaf solver
executables only; do not put a wrapper that spawns descendants in a Windows
portfolio policy.

Policy arguments are restricted to an explicit ordering-only whitelist.  A
policy cannot override the target, horizon, named moves, TT size or proof
semantics; those belong to the common task arguments.  Adding a new experimental
ordering option therefore requires a deliberate worker change and a new worker
bundle hash.

Legacy manifests containing `weights` remain accepted and are translated into
`choice_<weight>` policies.

### Experimental fourth arm without manifest duplication

The TT hint-first binary is inert by default.  To append the calibrated raw
opponent/flow policy to every task while keeping the original manifest and its
three controls unchanged:

```bash
make experimental-tt-hint-first
python3 scripts/codex_portfolio_worker.py \
  --solver bin/lazy_tt_hint_first_solver \
  --manifest experiments/manifests/4x7_w7_central_reply_portfolio.jsonl \
  --outdir results/compute-node/4x7-central-hint-ordering \
  --jobs 1 \
  --append-policy-file experiments/policies/flow1_hint_raw.json
```

The normalized appended policy is stored in every receipt and participates in
cache identity, so a record from a three-policy race cannot be mistaken for the
four-policy experiment.  Begin with `--jobs 1`: four TT26 processes already
compete for memory bandwidth.

Each output directory also receives `campaign.json`, binding the complete
normalized task universe, source manifest, solver binary and worker/parser
bundle.  A different campaign is rejected even with `--force`; use a fresh
directory.  `--force` can adopt a pre-campaign directory once, after which its
identity is sealed.

`--append-policy-json` accepts the same object inline when shell quoting is
reliable.  The versioned file form is preferred for PowerShell and production
receipts.

For a bounded pilot drawn from a production manifest, repeat `--task-id`:

```bash
python3 scripts/codex_portfolio_worker.py \
  --solver bin/lazy_tt_hint_first_solver \
  --manifest experiments/manifests/4x7_w7_central_reply_portfolio.jsonl \
  --outdir results/compute-node/4x7-hint-pilot \
  --jobs 1 \
  --append-policy-file experiments/policies/flow1_hint_raw.json \
  --task-id 4x7w7-central-reply-third-01-H5_2 \
  --task-id 4x7w7-central-reply-third-04-H1_2
```

Unknown or repeated task identifiers are rejected.  Selection does not alter
the task body, so a pilot and the later complete campaign use identical stable
positions and policy definitions.

## Campaigns

Reproduce the known central-reply branches and collect regime labels:

```bash
python3 scripts/codex_portfolio_worker.py \
  --solver bin/lazy_specialized_solver \
  --manifest experiments/manifests/4x7_w7_central_reply_portfolio.jsonl \
  --outdir results/compute-node/4x7-central-ordering \
  --jobs 2
python3 scripts/summarize_portfolios.py \
  results/compute-node/4x7-central-ordering
```

The former `3x9x10` ordering replay is retained only as an archived calibration
command.  The certificate programme is closed; do not schedule another complete
reproduction before the open `4x7` work:

```bash
python3 scripts/codex_portfolio_worker.py \
  --solver bin/lazy_specialized_solver \
  --manifest experiments/manifests/3x9_w10_upper_portfolio.jsonl \
  --outdir results/compute-node/3x9-w10-upper-ordering \
  --jobs 2
```

The seed representative `P(7,1) V(1,0)` is the reason this campaign moved ahead
of further blind depth: `flow1` reduced the exact proof from 79,800,528 to
37,279,448 nodes. Baseline remains a control policy, not a claimed winning regime.

Attack the next Player-1 frontier at total ply 27:

```bash
python3 scripts/codex_portfolio_worker.py \
  --solver bin/lazy_specialized_solver \
  --manifest experiments/manifests/4x7_w7_p1_depth27_frontier.jsonl \
  --outdir results/compute-node/4x7-p1-depth27 \
  --jobs 2
```

With a 32 GiB machine, start at two tasks concurrently. Three policies per task
means six solver processes. Increase only after measuring total throughput and
peak resident memory; twelve cores do not repeal memory bandwidth.

## Why not select from a shallow pilot?

Policy ranking reverses with both position and horizon. On one wall branch,
`choice40` dominates at depth 24. On the pawn branch `P(4,2)`, `flow1` cuts the
search from 119.9 million to 47.2 million nodes and beats both alternatives. A
shallow pilot can therefore select precisely the wrong full-depth algorithm with
considerable confidence, humanity's preferred confidence level.

A full race costs extra cores but remains exact and robust to reversals. Future
work may learn a selector from completed proofs, but it will be evaluated by
race regret, not by the photogenic nature of its model architecture.

Commit summaries and small JSON records. Keep very large raw logs or cache
snapshots as release artifacts or external archives, with SHA-256 files. Never
replace a completed proof record in place without preserving its solver hash and
command line.
