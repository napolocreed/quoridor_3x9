# Transposition-table slot reuse experiment — 2026-08-02

## Result

The fixed-size transposition table used to hash every unresolved state twice:
once in `probe()` before recursive search and again in `record()` when that
search returned. For the two-way table, each address calculation evaluates
`mix64` twice.

The experimental path retains only the two immutable candidate slot indices
from the probe. On return it rereads both current keys and metadata, then runs
the unchanged replacement-quality rule. It does **not** retain the old hit,
empty slot, victim, value, hint or metadata: any of those can become stale while
descendants use the table.

The mechanism is exact and removes substantial deterministic work. On the
named `V(0,0)` depth-24 branch, 28,393,959 records reuse their probe slots. A
two-way table therefore avoids 56,787,918 calls to `mix64`, containing
113,575,836 64-bit multiplications.

Timing is scale-dependent on the local laptop. Two long runs favor reuse by
about 2%, while the sub-second calibration regresses. The path remains behind
`QSPEC_TT_SLOT_REUSE_EXPERIMENT`; it is not yet the supported default.

## Exactness argument

For a fixed table instance, capacity, associativity and masks never change.
Consequently the mapping

```text
key -> {candidate slot A, candidate slot B}
```

is invariant for the lifetime of a proof search. Recursive calls may replace
either slot, but they cannot change which slots the parent key maps to.
`record_from_probe()` therefore starts from the saved addresses and repeats all
state-dependent work at return time:

- compare the current full keys;
- reload the current metadata;
- recompute both replacement qualities if the key is absent;
- merge the new upper or lower bound;
- enforce the ordinary bound-consistency check;
- store the move and metadata exactly as `record()` does.

This preserves the physical TT layout and replacement decisions. Saving a
victim or empty-slot decision instead would be wrong because descendants can
invalidate it.

The release token is two `uint32_t` indices (8 bytes); TT size is capped at
`2^30`. Debug tokens additionally bind the table instance, key and
associativity and recompute the address before recording. The present table is
private and single-threaded. A future concurrent TT would need its own data-
race discipline even though the address invariant still holds.

## Validation

- debug unit exercise over both two-way and four-way tables: 8,000 parent
  records separated from their probes by interleaved replacement traffic;
- explicit winning/lower-bound merge checks and rejection of a token belonging
  to another table instance;
- 2,000 sampled `3x3x1` bounded-proof requests;
- 2,000 sampled `4x3x2` bounded-proof requests;
- all 51,408 bounded `3x3x1` requests;
- identical verdict, nodes, TT hits, cutoffs, cache counts, transition counts
  and stable forcing labels on every named `4x7` timing run;
- `stalemates_seen=0` throughout.

The profile counter is compiled only with
`QSPEC_TT_SLOT_REUSE_PROFILE`. It counts actual records, not probes or an
estimated upper bound.

## Local timing

Times use Windows process CPU time in alternating order while Claude's separate
certificate process was active. The long results are useful local evidence,
not a quiet-machine promotion benchmark.

| branch | runs per mode | baseline median CPU | reuse median CPU | change | paired result |
|---|---:|---:|---:|---:|---:|
| `V(0,0)`, d=24, ordinary ordering | 4 | 14.7734 s | 14.4141 s | -2.43% | 4 wins / 0 losses |
| `H(5,2)`, d=24, flow=1 | 2 | 40.0156 s | 39.1563 s | -2.15% | 1 win / 1 loss |
| `H(5,2)`, d=16, flow=1 | 6 | 0.7188 s | 0.7734 s | +7.61% | 1 win / 4 losses / 1 tie |

The long `H(5,2)` pair has strong thermal drift, so its median is descriptive;
the geometric mean of its two paired CPU ratios is -2.10%. The short case is
quantized at 15.625 ms and exposes a real possibility of code-layout overhead
when little work is available to amortize the token path. The full frontier is
dominated by long branches, but this mixed result is not enough to promote a
global default from a contended laptop.

## Decision

Retain the exact implementation, unit test and profiling wrapper. Do not add a
fifth policy arm: this changes neither move ordering nor the search tree. On the
quiet gaming PC, benchmark the same binary substitution over a small stratified
subset of the known 40 branches. If aggregate CPU time improves without a
material long-tail regression, use it uniformly for the subsequent open
depth-27 frontier; otherwise close it as a mechanically valid but
compiler-sensitive microoptimization.

Commands, hashes and raw timing rows are in
`results/validation/tt_slot_reuse/benchmark_windows_local.json`.
