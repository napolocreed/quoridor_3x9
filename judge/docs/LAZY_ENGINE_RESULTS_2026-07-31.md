# Lazy exact engine, first experimental results

Date: 2026-07-31

## Purpose

The dense reference engine enumerates every structurally legal wall configuration
for a geometry before search. That is excellent for broad frontier sweeps, but a
single bounded branch may touch less than one percent of the universe. The lazy
engine keeps the proof semantics unchanged while constructing only configurations
and transitions reached by the requested branch.

The audited dense engine remains the publication reference. This document records
which lazy optimisations survived differential testing and which attractive ideas
failed their benchmark.

## Promoted mechanisms

### Incremental wall configurations

A child configuration differs from its parent by exactly one wall. The engine now:

1. clears only the two pawn edges blocked by that wall;
2. updates the structural wall-addition mask by removing the wall's conflict set;
3. recomputes the two small goal-distance maps;
4. inserts the result in the lazy mask cache.

It no longer rebuilds blocked edges or wall conflicts from the complete mask on
every cache miss.

### Adaptive transition cache

The raw lazy prototype still performed hundreds of millions of hash lookups for
already-known child wall masks. A configuration now receives a compact transition
array after it is expanded. Threshold 1 was fastest on the hard reference branch:
all structural children are remembered after the first expansion, but configurations
that are merely generated and never searched receive no transition array.

### Canonical-wall metadata

Each configuration records the minimum wall mask under the four exact board
symmetries and the transformations that attain it. Full-state TT canonicalisation
therefore usually evaluates one precomputed wall orientation rather than transforming
the complete wall mask at every node.

## Correctness checks

The specialised lazy solver passed:

- exact move-list equality at the first three plies of the `4x7x7` reference line;
- exact no-TT node equality on the `3x9x10` depth-11 branch: 41,284,776 nodes;
- six known small-variant winner/depth checks;
- 2,500 random move-generator comparisons against the independent Python engine;
- 500 random bounded-proof comparisons against the independent Python solver;
- exhaustive `3x3x1` bounded-proof comparison: 51,408 requests, zero disagreement.

The tests use the same documented rules as the audited dense solver. Search-node
counts may differ when TT capacity or representation differs, but no-TT counts are
identical.

## Benchmark results

### Hard `4x7x7` third-ply refutation branch

All lazy rows use incremental configurations, transition threshold 1 and a two-way
TT. Search verdicts are identical.

| Engine | TT | Nodes | Search seconds | Peak RSS |
|---|---:|---:|---:|---:|
| Dense audited | 27 | 222,310,853 | 53.37 | about 3.43 GiB including dense precompute |
| Lazy specialised | 24 | 242,529,460 | 50.98 | 454 MiB |
| Lazy specialised | 25 | 227,215,054 | 47.89 | 646 MiB |
| **Lazy specialised** | **26** | **223,188,594** | **47.25** | **1,030 MiB** |
| Lazy specialised | 27 | 222,301,018 | 52.52 | 1,798 MiB |

TT27 expands the fewest nodes but is slower than TT25/26. The additional table
capacity loses to memory latency and cache pressure. RAM capacity and useful search
speed remain distressingly different concepts.

Relative to the audited dense branch, TT26 reduces search wall time by about 11.5%
and avoids roughly twenty seconds of geometry precompute when the branch is run in
isolation.

### Representative `3x9x10` winning branch

| Engine | Nodes | Search seconds | Total process wall time |
|---|---:|---:|---:|
| Dense audited | 79,766,979 | 14.86 | about 18 s with precompute |
| Lazy specialised | 79,800,528 | 15.75 | 15.97 s |

The dense search loop remains slightly faster on this narrower configuration
universe, while lazy construction wins total isolated-branch time.

## Rejected defaults

### Per-configuration perfect TT

Hot configurations received direct arrays indexed by pawn positions, stocks and
turn. The hard branch slowed from about 60.0 to 63.9 seconds and RSS rose from about
549 to 781 MiB. The local table duplicates information already served reasonably by
the global TT and damages cache locality.

### Canonical configuration-data cache

Canonicalising configuration payloads under symmetry reduced hard-branch RSS from
about 549 to 394 MiB, but increased search time from 58.6 to 65.2 seconds before the
new transition cache. It remains a memory-constrained mode, not the default.

### Horizon stock capping

The reduction is exact, but its altered TT aliasing and move hints increased work on
the hard branch. Correct does not imply useful, a distinction software occasionally
finds offensive.

### Naive stock-dominance probes

For a fixed wall mask, total remaining walls is fixed. More target walls therefore
also means fewer opponent walls, giving a valid monotone dominance relation. Probing
nearby exact TT keys reduced nodes by 6 to 14 percent but increased wall time by 29
to 64 percent. The theorem is retained; the implementation is rejected. A compact
Pareto-bound TT is the next plausible form.

### Four-way TT at fixed entry count

It produced small wins on one shallow branch and a clear regression on the hard
branch. More ways with the same total entries reduced effective capacity and harmed
locality.

## Workload-dependent architecture

Lazy search is best for isolated branches and witness discovery. A broad scan can
accumulate millions of configurations and approach the dense universe. The research
programme will therefore use:

- lazy specialised search for exploration and difficult isolated branches;
- shared lazy caches inside branch families;
- dense precompute for broad final audits when expected coverage is high;
- fresh proof TTs per audited branch regardless of configuration-cache sharing.

This is not one universal solver. It is a portfolio selected by the shape of the
proof obligation, which is less aesthetically satisfying and considerably more
useful.

## Next experiments

1. compressed Pareto TT for exact wall-stock dominance;
2. bounded DF-PN on the fixed benchmark suite;
3. local retrograde promotion for repeatedly visited wall configurations;
4. persistent wall/configuration cache across resumable branch chunks;
5. independent Rust reproduction and certificate-oriented verification.


## Domain-specific ordering and exact wall-stock dominance

### Stable move identities

Ordering experiments originally selected forced positions by child index. That is
unsafe because changing a score changes the sorted move list: the same
`--root-index3 1` can denote a different move under a different ordering policy.
The supported solver now accepts stable labels:

```text
--root-move P(5,2) --second-move P(1,2) --third-move H(5,2)
```

Portfolio manifests reject index-based positions. This is a correctness property,
not merely a convenience.

### Shortest-path choice count

The distance maps already reveal how many legal neighbours continue along a
shortest route. The experimental ordering score adds

```text
weight × (target shortest-route choices - opponent shortest-route choices)
```

without changing the searched game or any pruning rule.

On the exact same difficult `4x7x7` position ending in `H(5,2)`:

| Ordering | Nodes | Search seconds |
|---|---:|---:|
| Baseline | 223,188,594 | 47.25 |
| Choice weight 40 | 15,323,311 | 3.57 |
| Choice weight 80 | 17,757,023 | 4.18 |
| Weight 40 + Pareto TT22 | 12,875,101 | 3.33 |

Weight 40 removes 93.1% of nodes and 92.4% of search time. The combined exact
mechanisms remove 94.2% of nodes.

The result is strongly branch-dependent. On the representative `3x9x10` position
ending in `V(1,0)`, weight 40 leaves the node count almost unchanged and increases
runtime. On the hard `4x7x7` pawn continuation `P(4,2)`, weight 40 fails to finish
within the 240-second experimental cap even though the baseline dense proof took
about 208 seconds. Negative weights also failed to rescue that branch.

Shallow pilots are not reliable selectors: at depth 16, weight 40 is slightly
faster than baseline on `P(4,2)`, yet it is dramatically worse at depth 24. The
ordering undergoes a horizon-dependent regime change. The safe exploitation is
therefore a **full exact portfolio race** between a small number of orderings, with
all variants forced by stable move labels and the losers cancelled after the first
exact completion.

### Compact Pareto table for wall stocks

For a fixed wall mask, the total number of unplayed walls is fixed. If the target
has more of those walls, the opponent necessarily has fewer. A target win is
therefore monotone upward in target wall stock, while a failed bounded proof is
monotone downward.

A separate direct-mapped Pareto table stores these monotone bounds without probing
many neighbouring global-TT keys. It passed the exhaustive 51,408-query
`3x3x1` proof differential with zero disagreement.

| Position | Baseline nodes / seconds | Pareto nodes / seconds |
|---|---:|---:|
| Hard `4x7x7 H(5,2)` | 223,188,594 / 47.25 | 175,336,410 / 42.84 (TT24) |
| `3x9x10 V(1,0)` | 79,800,528 / 15.75 | 56,275,250 / 11.88 (TT24) |

The Pareto table is a candidate for promotion after broader branch validation. Its
larger forms eventually lose to memory latency, so bigger again remains the least
creative benchmark strategy available.

### Proof-number search result

A basic graph Proof-Number Search implementation solves tiny variants compactly,
but fails to finish even a shallow `4x7` benchmark that DFS resolves in
milliseconds. Uniform proof/disproof initialization is pathological for this game.
Only a memory-bounded DF-PN design with domain-derived initialization remains on
the research path.

## Compute-node portfolio

`scripts/codex_portfolio_worker.py` races exact orderings on identical named
positions and atomically records the winner and cancelled variants. Two manifests
are prepared:

- `4x7_w7_central_reply_portfolio.jsonl`: reproduces 40 known branches and creates
  a labelled dataset of ordering regimes;
- `4x7_w7_p1_depth27_frontier.jsonl`: attacks every first move at the next open
  Player-1 horizon.

The first campaign is both an audit and a data-collection experiment. The second is
actual frontier work. This keeps the gaming PC from becoming an expensive device
for rediscovering which heuristic was lucky once.
