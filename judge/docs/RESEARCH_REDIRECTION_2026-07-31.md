# Research redirection: from deeper brute force to structure-aware solving

Date: 2026-07-31

## Executive decision

The audited bounded-proof engine remains the reference implementation. It has produced exact, reproducible results, including the 35-ply result for `3×9×10`. However, continuing the `4×7×7` frontier primarily by raising the depth and splitting more root branches is no longer the highest-value use of compute.

The next research cycle will separate three goals:

1. **Preserve the trusted exact baseline.** No speculative optimization enters the audited solver without differential tests and branch-level reproduction.
2. **Remove the global wall-precompute bottleneck.** Build an on-demand or hybrid wall-configuration engine and measure whether its memory savings can buy a substantially larger transposition table or useful parallelism.
3. **Replace uninformed bounded DFS where appropriate.** Prototype bounded DF-PN, strategy reuse across horizons, and independent proof verification.

The brute-force `4×7×7` depth-27 scan is paused until at least the lazy-configuration and bounded-DFPN prototypes have been benchmarked on the fixed branch suite.

## What the current engine does well

- Exact legal move generation with independent Python comparison.
- Bounded existential/universal proof semantics with monotone TT depth facts.
- Deterministic decomposition into independently auditable branches.
- Horizontal and player-swapping symmetry checks.
- Conservative audit mode with fresh tables and optional pruning modules disabled.
- Resumable JSON artifacts and reproducible commands.

This makes it a good **oracle and verifier** for future experimental engines, even if it is not the final scalable architecture.

## Profile of the current bottleneck

A `gprof` run on a known `3×9×10` proof branch attributed roughly:

- 64% of self time to recursive bounded proof search;
- 21% to successor generation;
- 10% to global wall-state precomputation.

The more important result is configuration reuse.

### `3×9×10` representative branch

- search nodes: 79,766,979
- globally enumerated wall configurations: 2,929,319
- distinct configurations reached as search nodes: 124,704
- distinct configurations generated as children: 135,351
- generated fraction of the global universe: 4.6206%

### `4×7×7` representative third-ply branch

- search nodes: 3,729,954
- globally enumerated wall configurations: 16,368,423
- distinct configurations reached as search nodes: 36,274
- distinct configurations generated as children: 52,004
- generated fraction of the global universe: 0.31771%

The current architecture therefore pays memory and construction cost for a wall universe of which a bounded branch may use less than one third of one percent, even after counting generated children rather than only visited nodes. This is the clearest structural inefficiency found so far.

## Priority 1: demand-driven wall configurations

### Prototype design

Represent the wall mask directly in the search state. For the current narrow boards, the structural wall slots fit inside 64 bits. Maintain a bounded cache keyed by wall mask containing only hot derived data:

- clear pawn-movement edges;
- goal reachability;
- shortest goal distances;
- legal structural additions or a compact legal-add mask;
- canonical reflected/rotated mask when profitable.

Cold entries are generated with bit-parallel graph operations and evicted by age or frequency. A hybrid version may precompute low-wall layers and lazily construct the deeper layers that dominate the actual search.

### Acceptance criteria

The prototype must:

- return identical legal moves and bounded proof values on the differential suite;
- reduce peak RSS by at least 40% on `4×7×7`;
- achieve a geometric-mean slowdown below 2× on the fixed branch suite, or offset a larger slowdown by enabling enough TT capacity or parallelism to reduce total solve time;
- preserve a deterministic audit mode.

If it fails those criteria, retain the global engine and pursue compressed storage instead.

## Priority 2: bounded DF-PN

The current recursion follows depth-first AND/OR search with static ordering. Quoridor branches are highly non-uniform: a single adversarial reply can refute an opening, while a candidate proof requires every reply. This is the regime for which proof-number methods were designed.

The first implementation will be **bounded-horizon DF-PN**. Remaining depth is part of the state, making the search acyclic even though the unbounded game can repeat. The prototype should include:

- proof and disproof thresholds;
- transposition-aware bookkeeping;
- Threshold Controlling Algorithm safeguards;
- optional heuristic initialization from exact path and wall features;
- deterministic single-threaded mode before parallelization.

### Acceptance criteria

Use a frozen benchmark set containing easy and hard `3×9×10` reply classes and `4×7×7` third-ply branches. Continue only if DF-PN improves geometric-mean expanded nodes or wall time by at least 25%, without pathological regressions on the hardest branch.

## Priority 3: strategy reuse rather than table amnesia

Fresh transposition tables are useful for final audits but wasteful during exploration. A separate persistent strategy store should retain:

- best proving move for existential nodes;
- best refuting move for universal nodes;
- deepest successful and failed horizons;
- compact proof skeletons from completed branch scans.

Depth `d` counterstrategies should seed move ordering at depth `d+2`. Shared exploratory state must never replace the final fresh-table rerun.

## Priority 4: proof artifacts and independent checking

The largest scientific weakness is not speed but correlated trust. The result still depends on one C++ transition/search implementation.

Two independent verification tracks are justified:

1. adapt the public Rust solver to accept fixed states and bounded branch queries;
2. emit a compact strategy DAG or bounded QBF instance with a mechanically checkable certificate.

A simple checker should be smaller than the solver and verify only:

- every existential certificate node supplies one legal child;
- every universal certificate node covers all legal children;
- every leaf is terminal within the stated horizon;
- hashes and state serialization are consistent.

The certificate may initially be large. Transposition compression and chunked verification are later engineering problems, not reasons to avoid producing one.

## Secondary engineering experiments

These are useful, but subordinate to the architectural work:

- add TT generations using currently unused metadata bits;
- benchmark four-way cache-line buckets against the current two-choice TT;
- pre-probe child keys to prioritize cached decisive children;
- pack 24-bit configuration IDs and symmetry maps in the global engine;
- free construction-only arrays after precomputation;
- precompute row/column lookup arrays to remove hot integer divisions;
- replace insertion sort with partial selection or score buckets;
- benchmark mirror-only canonicalization against full player-swapping symmetry.

A preliminary branch test shows that horizontal reflection is essential, while the additional 180-degree player-swap symmetry provides little benefit on at least one `3×9×10` branch. This needs a suite-wide benchmark before simplification.

## High-risk research probes

### ZDD or frontier-based wall-family representation

The legal wall masks form a constrained set family and are a natural candidate for ZDD compression. The uncertainty is random-access performance: exact search needs fast successor generation, path legality and canonicalization, not merely compact enumeration. Prototype only the wall-family index before attempting a solver rewrite.

### Symbolic layer solving

Wall placement is monotone, so the configuration graph is a DAG. A possible solver processes configurations from more walls to fewer walls and symbolically solves all pawn-position states associated with selected hot configurations. A threshold-based hybrid could promote a frequently revisited configuration into a complete local pawn-state table.

### QBF

Bounded winning strategy maps directly to alternating quantifiers by ply. A QBF encoding is attractive primarily as an independent verification and certificate route. It should first target selected `3×9×10` branches, then the complete 35-ply claim if the encoding remains tractable.

## Experimental governance

Maintain separate branches:

- `main`: audited exact baseline;
- `experimental/lazy-config`;
- `experimental/dfpn`;
- `experimental/certificates`.

Every optimization is evaluated on the same benchmark manifest and records:

- result and proof depth;
- nodes and generated moves;
- wall time and precompute time;
- peak RSS;
- TT hit, replacement and occupancy statistics;
- distinct wall configurations touched;
- compiler and executable hash.

The benchmark suite, not intuition, decides promotion. The purpose is not to make the code look sophisticated. It is to remove enough state-space cost to cross a frontier that the reference architecture cannot.
