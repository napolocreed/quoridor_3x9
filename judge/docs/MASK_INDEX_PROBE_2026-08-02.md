# Flat wall-mask index miss-token experiment — 2026-08-02

## Result

Every newly materialized wall configuration used to traverse the same open-
addressing cluster twice: once in `find()`, which ended at the first empty slot,
and again in `insert_raw()`. No index mutation occurs while the configuration's
distances and metadata are built, so the miss slot is an exact insertion token.

The experimental path reuses that token. If the insertion crosses the 70% load
threshold, it performs the historical rehash and insertion instead. A debug
generation number rejects stale tokens. This preserves the physical table
layout, configuration identifiers and search tree exactly.

The optimization is structurally successful but the local timing result is
inconclusive. On a production-reserve `4x7x7` branch it removed 981,888 hash
computations and 1,046,462 slot reads, but an alternating four-pair run had large
thermal variance: median process CPU time moved from 17.2734 to 16.9375 seconds
(1.94% faster), while two individual pairs favored each binary and ranged from
4.8% regression to 6.8% improvement. It remains isolated behind
`QSPEC_MASK_INDEX_PROBE_EXPERIMENT`; it is not promoted on this evidence.

## Exact mechanism

`FlatMaskIndex::probe()` returns either the stored value or a miss token naming
the first empty slot. In debug builds the token also binds the key and index
generation. `ensure_config()` and `ensure_child_config()` finish constructing
the new value before calling `insert_at_miss()`.

The insertion has two cases:

1. below the load threshold, write the key/value directly into the token slot;
2. at the threshold, double and rebuild the table, then use the old
   `insert_raw()` path because the token slot is no longer meaningful.

The timed binary contains no profiling increments. A distinct
`QSPEC_MASK_INDEX_PROBE_PROFILE` build reports token reuse, avoided slot reads
and rehash fallbacks.

## Validation

- debug unit test: hit, miss, direct insertion, stale-token rejection and the
  exact 70% rehash boundary;
- 2,000 sampled `3x3x1` requests;
- 2,000 sampled `4x3x2` requests with `--cache-reserve 16` to force repeated
  rehashes;
- all 51,408 bounded `3x3x1` requests, also with reserve 16;
- identical verdict, nodes, TT hits, cutoffs, configuration counts and
  transition counts on every named A/B run;
- `stalemates_seen=0` throughout the `4x7` measurements.

The profile identity holds:

```text
mask_probe_reused + mask_probe_rehash_fallbacks == cache_misses
```

| branch | cache reserve | cache misses | reused | rehash fallbacks | slot reads saved |
|---|---:|---:|---:|---:|---:|
| `H(5,2)`, d=16, flow1 | 65,536 | 161,170 | 161,169 | 1 | 371,897 |
| `V(0,0)`, d=24 | 3,000,000 | 981,888 | 981,888 | 0 | 1,046,462 |

The large production reserve deliberately keeps the table sparse, explaining
why the second row saves only 1.066 slot reads per insertion in addition to one
hash computation.

## Decision

Keep the exact implementation and its tests as an experimental candidate. Do
not replace the supported lazy solver or multiply the 40-branch policy campaign
with another binary. A quiet, affinity-controlled A/B on the gaming PC may
promote it if several representative branches show a stable positive geometric
mean without a tail regression. Otherwise close it as a useful structural
cleanup whose effect is below system noise under the production reserve.

Machine-readable commands, hashes and raw timing rows are in
`results/validation/mask_index_probe/benchmark_windows_local.json`.
