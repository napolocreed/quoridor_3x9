# Bounded DF-PN prototype — 2026-08-01

## Purpose

The existing exact solver evaluates the bounded AND/OR recurrence with a
well-ordered depth-first search and monotone transposition facts. A previous
plain graph Proof-Number Search prototype expanded too broadly.

This experiment implements thresholded depth-first proof-number search (DF-PN)
with:

- remaining depth in the transposition key;
- horizontal and 180-degree canonicalization inherited from the lazy engine;
- saturating proof/disproof arithmetic;
- the `1+epsilon` progress rule;
- a compact child-edge arena;
- optional ordering-rank initial proof numbers;
- an optional incremental mode where topologically safe wall children remain
  unresolved move handles until selected;
- explicit node and time budgets.

The source is `experiments/solvers/lazy_dfpn_solver.cpp`. It is experimental and
is not used for reported frontier claims.

## Correctness checks

`reference/dfpn_known_outcomes.py` checks both sides of five exact horizons:

| variant | target | fails by | wins by |
|---|---:|---:|---:|
| 3×3×0 | Player 2 | 2 | 4 |
| 3×3×1 | Player 2 | 6 | 8 |
| 4×3×3 | Player 1 | 11 | 13 |
| 3×5×3 | Player 1 | 17 | 19 |
| 3×5×4 | Player 2 | 20 | 22 |

Uniform leaves, rank priors, and rank priors plus incremental cycle-safe edges
all return the expected values with `stalemates_seen=0`.

## Benchmark against plain PNS and DFS

Fixed refutation:

```text
4×7×7: P(5,2) P(1,2) H(5,2)
remaining depth 12, target Player 1
```

| method | result | work | seconds | RSS |
|---|---|---:|---:|---:|
| exact DFS | refuted | 1,315,111 nodes | 0.25 | 85 MiB |
| plain graph PNS | unresolved after 10 s | 96,256 expansions | 10.10 | 166 MiB |
| bounded DF-PN, uniform | refuted | 416,036 expansions | 2.65 | 497 MiB |
| DF-PN, rank priors | refuted | 286,199 expansions | 2.58 | 323 MiB |
| rank priors + incremental safe walls | refuted | 336,958 expansions | 3.24 | 343 MiB |

Thresholded DF-PN is a large improvement over the old PNS prototype, but remains
roughly ten times slower than the mature DFS on this branch. Rank priors reduce
graph size and memory, not wall-clock time. Incremental cycle-safe children
reduce graph nodes further but cause more recursive threshold work.

## Frontier-scale failure

On the known winning branch

```text
3×9×10: P(7,1) V(1,0)
remaining depth 31, target Player 1
```

DFS proves the win in 79,800,528 nodes and about 16.3 seconds. Rank-prior DF-PN
hits its five-million-node graph cap after about 15.4 seconds without solving:

- `pn = 19,556`
- `dn = 118,039`
- 1,691,210 expanded nodes
- 17,623,797 graph edges

This is not merely an implementation constant. The proof-number graph pays to
retain a large frontier that the DFS's cutoffs and monotone TT never need to
materialize simultaneously.

## Decision

Bounded DF-PN is semantically sound and substantially better than plain PNS, but
it is not promoted for the current frontier. The present exact DFS remains the
strong baseline.

Useful retained conclusions:

1. rank-based evaluation-function priors are valid and reduce DF-PN memory;
2. the topological gate can support unresolved wall handles correctly;
3. incremental materialization helps storage but not enough to overcome DF-PN's
   broad frontier;
4. a future revisit needs memory-bounded replacement, proof-number reuse from
   completed DFS subsearches, or a hybrid where DFS supplies exact child costs.

Raw outputs are under `results/validation/dfpn_prototype/`.
