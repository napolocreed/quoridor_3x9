# Cache-first local cycle gate experiment - 2026-08-01

## Result

The allocation-free condition

```text
at most one of the candidate wall's three junctions is touched
```

is a sound subset of the full planar-dual cycle gate. A junction is touched
when it belongs to the contracted perimeter or is incident to an existing wall
segment. Every untouched junction is a singleton dual component. If at most one
of `a,b,c` is touched, the other two are distinct singletons and none can share
the touched component. The three component labels are therefore pairwise
distinct, so adding `a-b-c` cannot close a dual cycle or split a primal cell
component.

`reference/local_cycle_gate_check.py` verifies both implications mechanically:

1. every locally-safe candidate is accepted by the full DSU gate;
2. adding it preserves the complete set of goal-reachable cells for both
   players, not merely the two current pawn paths.

## Exhaustive measurements

| board | candidates | full DSU safe | local safe | DSU-safe captured | false safe |
|---|---:|---:|---:|---:|---:|
| `4x3`, 3 walls/player | 988 | 238 | 216 | 90.76% | 0 |
| `4x4`, 3 walls/player | 22,460 | 5,590 | 4,734 | 84.69% | 0 |
| `3x5`, 4 walls/player | 8,108 | 1,980 | 1,788 | 90.30% | 0 |
| `5x3`, 3 walls/player | 8,092 | 1,980 | 1,788 | 90.30% | 0 |
| `2x4`, 2 walls/player | 41 | 7 | 7 | 100% | 0 |
| `2x2`, 1 wall/player | 2 | 0 | 0 | n/a | 0 |

The compact output is archived in
`results/validation/local_cycle_gate/exhaustive.jsonl`.

The local test captures about 22% of all structural candidates and about 90%
of the full DSU gate's proven-safe cases, with only three bit-mask intersections
and boundary flags. It needs no per-configuration DSU labels.

## Required engine architecture

This result does **not** promote the old `--defer-cycle-safe` implementation.
That prototype classified before exploiting the configuration cache, disabled
the transition cache, lost the incremental parent on materialisation and damaged
move ordering. Its negative benchmark remains valid.

A meaningful implementation must be cache-first:

1. form the child wall mask and probe the exact configuration cache;
2. on a hit, emit the exact child and retain exact ordering;
3. on a miss, run the local gate;
4. emit a compact `{parent_cfg, wall}` handle for a locally-safe miss;
5. build fallback children immediately with the usual BFS legality test;
6. when a handle is selected, call `ensure_child_config(mask,parent_cfg,wall)`
   so incremental construction is preserved.

Transition-cache entries must distinguish resolved child IDs from unresolved
safe handles. Replaying an unresolved entry should probe the configuration cache
again and replace the handle with a resolved ID after another path materialises
the same child.

The ordering experiment needs a refinement parameter `K`: materialise the best
`K` proxy-ranked handles before the final sort, with `K = 0,2,4,all`. This tests
whether most BFS work can be avoided without repeating the node explosion of
the blanket deferred prototype.

## Isolated C++ implementation blueprint

The experimental binary should be a one-line wrapper in
`experiments/solvers/lazy_local_touch_gate_solver.cpp`:

```cpp
#define QSPEC_LOCAL_TOUCH_GATE_EXPERIMENT 1
#include "../../src/lazy_specialized_solver.cpp"
```

Every state, cache, generation and search-hot-path addition to
`src/lazy_specialized_solver.cpp` is under that macro.  One shared driver repair
is intentionally outside it: `--scan-current` materialises a selected root before
generating its children.  This also makes the older `--defer-cycle-safe` driver
safe after a deferred third move; ordinary promoted solve paths are unchanged.
Subclassing is not appropriate because the relevant caches are private and
generation is not virtual; copying the solver would instead create an
unauditable fork.

The experimental `State` needs one field:

```cpp
uint32_t deferred_ref = UINT32_MAX;
```

Encode `(parent_cfg_id << 6) | wall` and use `cfg_id == UINT32_MAX` for an
unmaterialised state. Reserve transition child ID `(1u << 26) - 1`; real
configuration IDs must stay below it. The existing 26+6 transition packing can
then represent either a resolved child or the reserved ID plus a wall number.
The fixed geometry required by the gate is only:

```text
junction_incident_walls[64]  wall bits incident to each junction
boundary_junctions           perimeter-junction bit set
```

This costs about 512 bytes per experimental engine and four bytes per
experimental state. It does not require DSU labels per configuration.

The exact transition order is normative for the experiment:

1. A resolved transition entry emits its exact child directly.
2. A pending transition entry probes the global configuration cache. A hit
   patches the entry to the exact ID; a miss emits the deferred handle.
3. While building a transition entry, probe the global cache first. Store an
   exact ID on hit, the pending sentinel on a locally-safe miss, and otherwise
   build the fallback child with the usual incremental BFS path.
4. Without a transition entry, use the same cache-hit / local-safe-miss /
   fallback-miss ordering.
5. Resolving a handle must call
   `ensure_child_config(child_mask, parent_cfg_id, wall)`, never the full
   `ensure_config(child_mask)`. A child materialised by another path between
   emission and resolution therefore becomes a normal cache hit.

Proxy context (distance maps, shortest-path choices and base score) should be
constructed lazily only when the first safe miss is actually emitted. The
existing path-flow impact is computed from the parent configuration and its
exact `(flow_op[wall] - flow_me[wall]) * path_flow_weight` term must be present
in the deferred proxy as well as in exact child scoring.
Debug builds should reject calls to `canonical_key()` or `config_by_id()` on
an unresolved state.

The first implementation should not refactor a known-missing cache insertion:
a fallback may repeat one hash probe before its two BFS passes. That keeps the
baseline path small; profile evidence can justify a specialised insertion API
later.

## Counters and benchmark protocol

Record at least:

- exact cache hits before the gate;
- locally-safe misses and fallback misses;
- unresolved handles emitted, replayed, resolved and pruned without resolution;
- exact BFS/configurations avoided;
- refined handles and ordering changes;
- nodes, TT hits, wall-clock time, peak RSS and total cache bytes.

Use distinct counters for initial cache misses, deferred resolve hits and
deferred resolve builds. `deferred_emitted - deferred_resolved` is not a sound
estimate of saved BFS work because copied children can be resolved more than
once during iterative deepening. Count handles skipped by cutoffs in the proof
loop, and call a BFS avoided only when no configuration was actually built.

Compare the promoted baseline (transition threshold 1) against each `K` on the
same named positions, starting with `P(5,2) P(1,2) H(5,2)`. Child indices are
not stable enough for this benchmark. Exhaustive move and bounded-proof
differentials remain mandatory before any promotion.

## Status

The mathematical/local classification and the isolated C++ handle experiment
are now implemented.  The production path remains selected when
`QSPEC_LOCAL_TOUCH_GATE_EXPERIMENT` is absent; the experimental executable is
the one-line wrapper
`experiments/solvers/lazy_local_touch_gate_solver.cpp`.

The implementation follows the cache-first order above.  A pending transition
uses child ID `(1 << 26) - 1`; its wall remains in the low six packed bits.  An
unresolved state holds `(parent_cfg << 6) | wall`, and resolution calls
`ensure_child_config(child_mask, parent_cfg, wall)`.  The old full-mask
`ensure_config()` route is not used for these handles.  `--defer-cycle-safe` is
rejected by the experimental binary so that the old prototype and this
experiment cannot be accidentally combined.

The output counters distinguish:

- `local_touch_exact_hits`, `local_touch_safe_misses`, and
  `local_touch_fallback_misses` at the initial cache-first classification;
- `deferred_replayed` and `deferred_patched` for pending transition entries;
- `deferred_resolve_hits` and `deferred_resolve_builds` for selected handles;
- `deferred_pruned` and `deferred_pruned_uncached` at proof cutoffs;
- `bfs_passes_avoided`, exactly twice the number of skipped handles whose mask
  was still absent from the global cache at that cutoff;
- `deferred_refined` and `refinement_order_changes` for the K experiment.

The avoided-BFS counter is deliberately event-based, not a count of unique wall
masks: the same state can be emitted again under iterative deepening.  It only
increments when that particular skipped handle would have required a new
configuration at the moment of the cutoff.  It is a raw count of two potential
configuration-construction BFS passes per such event, not a net saving: proxy
setup itself runs two `distances_from` BFS passes per generation, and repeated
masks may be counted again.

## Validation of the handle implementation

The MinGW GCC 16.1 build on 2026-08-01 passed:

- move-generation differential checks for every K on 1,000 `4x3x3`, 1,000
  `3x5x4`, and 500 `3x9x8` sampled states (10,000 checks total);
- 500 sampled bounded-proof requests for each of `K=0,2,4,all`;
- the complete 51,408-request `3x3x1` bounded-proof grid for each K, or 205,632
  checked requests in total;
- 1,000 further sampled requests at transition threshold zero for both `K=0`
  and `K=all`, exercising the non-transition-cache path;
- 1,000 sampled requests at transition threshold two with `K=2`, exercising a
  mix of direct generation and later transition-cache construction;
- 1,000 independent-reference proof requests with path-flow weight 1 and
  `K=2`, exercising the exact proxy term restored after audit;
- debug-build handle assertions and the standard `3x3x1` depth-8 smoke;
- a named three-wall regression, `H(1,0) H(4,2) H(2,1)`, which leaves the
  selected third child deferred at `K=0` and then enters `--scan-current`.

All verdicts agreed with the independent Python reference and all solver runs
reported `stalemates_seen=0`.

The Makefile targets are `experimental-local-touch`, `local-touch-smoke`,
`local-touch-differential`, and `local-touch-audit-small`.

## First same-position benchmark

The first benchmark used the required named line
`P(5,2) P(1,2) H(5,2)`, target Player 1, exact bound 16, transition threshold
1, path-flow weight 1, and TT25.  Every process printed the three requested
move labels; their sorted indices were allowed to differ.  Times are medians of
five fresh processes on an AMD Ryzen 5 220 under Windows 11 with GCC 16.1.

| mode | nodes | median solver s | cache configs | peak RSS MiB |
|---|---:|---:|---:|---:|
| promoted baseline | 2,326,659 | 0.9867 | 161,170 | 442.2 |
| local touch, K=0 | 2,718,848 | 1.1358 | 189,124 | 441.4 |
| local touch, K=2 | 2,516,514 | 1.1893 | 173,096 | 434.8 |
| local touch, K=4 | 2,326,336 | 1.0201 | 160,877 | 433.4 |
| local touch, K=all | 2,326,659 | 1.0380 | 161,170 | 433.7 |

Claude's independent certificate-extraction jobs were active during this
calibration.  Variant order followed the archived mixed schedule, but these are
deliberately labelled contention-bearing comparative times rather than
clean-machine absolute timings.

The first calibration incorrectly omitted the existing path-flow term from
deferred proxy scores.  Its apparent `K=2` gain therefore mixed the local-touch
gate with a second ordering change and is invalid.  After restoring the exact
parent-derived term, `K=0` increases nodes by 16.86% and median solver time by
15.11%; `K=2` increases them by 8.16% and 20.53%.  `K=4` is within 0.014% of
baseline nodes but remains 3.38% slower.  No partial K wins this branch.

`K=all` exactly reproduces baseline verdict, nodes, TT hits, cutoffs,
configuration count and transition hits/builds/entries; its 5.19% median time
overhead is the corrected cost-control result.  Partial refinement still lets
approximate proxy/exact score interactions change the global move order, while
proxy setup adds two BFS passes of its own.  The current design is therefore a
documented negative result, not a portfolio candidate.  It should not be
revisited without a proxy redesign and net, rather than event-level, BFS
instrumentation.

The compact commands, hashes, counters, timing summary and RSS measurements are
archived in
`results/validation/local_touch_gate/cache_first_benchmark_windows_local.json`.
The compact receipt substantiates the performance comparison and retains all
timing samples, return codes and stable forcing lines. Verdict and stalemate
agreement are supported by the separate exhaustive and sampled differential
suites rather than retained per-run benchmark stdout.
The archive retains all five solver/wall/RSS samples, return codes, forcing
lines and transition-entry counts for each mode.  A wider `K=2` portfolio is no
longer justified by this implementation.
