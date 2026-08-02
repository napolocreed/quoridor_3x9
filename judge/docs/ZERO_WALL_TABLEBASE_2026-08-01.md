# Exact zero-wall tablebase experiment — 2026-08-01

## Result

The experiment is exact and passed every semantic gate, but it does not address
the current proof-search bottleneck.  It is retained as a negative result and is
not promoted into the supported lazy solver or the ordering portfolios.

The implementation is isolated by
`QSPEC_ZERO_WALL_TABLEBASE_EXPERIMENT`.  For a fixed wall configuration and
zero stock for both players, it solves the complete pawn graph for each target.
The stored value is the least rank

```text
rank_T(s) = min { d : Win(s, T, d) }
```

or infinity when the target cannot force its goal at any finite horizon.  Target
nodes use `1 + min`, opponent nodes use `1 + max` only after every non-empty
successor set has entered the attractor.  States outside the attractor remain
infinite, so cycles and draws do not need an acyclicity assumption.  A node with
no legal move remains false, matching the repository convention on height-two
boards as well as the no-stalemate theorem for height at least three.

On `4x7`, the raw graph has only `2 * 28 * 28 = 1,568` indices.  A FIFO
retrograde pass builds both targets together after a configurable number of TT
misses.  Completed tables are published atomically; the promoted build contains
none of this code.

## Validation

The independent Python recurrence agreed on:

- 2,000 sampled `3x3x1` requests;
- 2,000 sampled `4x3x2` requests;
- the complete 51,408-request `3x3x1` grid with immediate construction;
- the same complete grid with threshold 3 and capacity limited to one table;
- all 1,988 requests on reachable `3x2x1` states, including reachable pats.

A debug build also rechecked every finite and infinite entry against its Bellman
equation on `4x7x0`.  There were zero divergences.

## Why it does not help the exact frontier

The proof trees almost never reach a state where both stocks are exhausted:

| named position | remaining bound | proof nodes | eligible zero-stock nodes |
|---|---:|---:|---:|
| `P(5,2) P(1,2) H(5,2)` | 16 | 2,326,659 | 0 |
| `P(5,2) P(1,2) P(4,2)` | 18 | 47,214,750 | 0 |
| `P(7,1) V(1,0)` on `3x9x10` | 31 | 37,279,448 | 0 |

At bound 24 on `P(5,2) P(1,2) H(5,2)`, only 11,148 of 124,257,426
proof calls were eligible, and only 5,357 of those missed the TT.  Building a
table on the first miss produced 1,163 tables (7,368,768 bytes and 0.225 s of
retrograde work) but removed only 6,803 DFS calls, or 0.005475%.  Threshold 2
removed 5,531 calls while building 681 tables.  Neither configuration improved
wall time over the disabled control.

The mechanism is useful in a conventional `9x9` playing agent, which deliberately
evaluates exhausted-stock endings.  In bounded exact search, strong cutoffs and
the TT settle or avoid nearly all such states before the special case can pay for
itself.

Full commands, counters, machine metadata and hashes are in
`results/validation/zero_wall_tablebase/benchmark_windows_local.json`.

## Decision

Keep the wrapper and regression targets as an audited prototype.  Do not spend a
portfolio slot or production complexity on it.  The next experiment should act
before full successor generation—specifically, trying a legal TT hint before
materialising and ordering all siblings—because successor generation remains a
measured hot path and is exercised at millions of internal nodes rather than a
few thousand terminal-stock states.

The natural one-wall extension was subsequently profiled rather than guessed.
On the hard depth-24 branch, 162,244 unresolved TT probes at total stock one were
spread over 12,881 configurations; the hottest configuration had only 528.
That is far below the construction cost of a complete base-plus-one-wall
attractor.  The extension is also closed; see
`results/validation/endgame_layers/benchmark_windows_local.json`.
