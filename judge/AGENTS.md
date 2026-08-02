# Corridor research instructions

## Scientific objective

Extend exact computational knowledge of reduced Quoridor/Corridor variants and
build a strong, auditable solver. Never describe a bounded or heuristic result as
a solved game. Every claim must identify the rules, target player, horizon, solver
hash, command line and validation status.

## Trusted baseline

- `src/frontier_solver.cpp`: audited dense reference engine.
- `src/lazy_specialized_solver.cpp`: supported lazy exact engine for isolated
  branches.
- `reference/quoridor_reference.py`: deliberately simple independent rules engine.
- `make test`, `make lazy-smoke`, `make lazy-differential`: required before a
  solver commit.

The lazy solver's `--no-bounds --no-pawn-table` flags are accepted for protocol
compatibility; its exact core does not use those specialised modules.

## Stable positions

Ordering changes sorted child indices. Never compare algorithms using
`--root-index`, `--root-index2` or `--root-index3`. Use named moves such as:

```text
--root-move P(5,2) --second-move P(1,2) --third-move H(5,2)
```

Any benchmark that does not establish identical move labels is invalid.

## Current promoted mechanisms

- lazy wall configurations;
- incremental child configuration construction;
- transition cache threshold 1;
- two-way TT, normally TT26 on 32 GiB compute nodes;
- exact named-move forcing;
- optional path-choice ordering, normally raced at weights 0 and 40 rather than
  selected globally.

## Experimental mechanisms

Experimental solver source belongs in `experiments/solvers/`; proof-extraction
and analysis utilities belong in `experiments/tools/`. Promotion requires:

1. move-generation differential tests;
2. bounded-proof differential tests;
3. exhaustive `3x3x1` proof grid when search semantics or TT inference changes;
4. same-position benchmark suite;
5. a documented failure mode and memory cost.

The compact Pareto wall-stock TT is promising but not yet a default. Basic PNS,
naive repeated dominance probes and local perfect per-configuration TTs are
negative results, not hidden defaults.

The opponent-turn TT hint-first path is also experimental.  Its raw-hint mode
is exact because an invalid symmetry-relative hint falls back to full generation,
but local results are bimodal across named branches.  Do not make it a global
default before the known 40-branch portfolio suite.  Canonical hint transforms
cost more than they save in the current prototype.

The TT slot-reuse path is a mechanical binary substitution, not an ordering
policy. It reuses only immutable candidate addresses and rereads table contents
after recursion. Long local branches improved by about 2%, while a sub-second
branch regressed. Do not add it as a portfolio arm; decide it on a small quiet-
machine A/B sample, then apply it uniformly or close it.

## Compute campaigns

Use `scripts/codex_portfolio_worker.py` for ordering races and atomic resumable
records. Start with the known 40-branch central-reply campaign before the open
Player-1 depth-27 frontier. Run `scripts/summarize_portfolios.py` after each batch.

Do not commit multi-gigabyte raw caches. Commit compact JSON summaries and hashes;
store large artifacts separately. Never overwrite an exact record produced by a
different solver hash.

## Research discipline

Prefer game-specific reductions over generic search folklore, but test both.
Record attractive failures. Optimize total frontier throughput, not one benchmark.
A faster wrong position is still wrong, merely with better latency.
