# Shortest-path-flow ordering experiment — 2026-08-01

## Hypothesis

`path_choice_weight` counts only how many immediate pawn moves remain on a
shortest path. A wall can instead be scored by the fraction of the complete
shortest-path DAG that it cuts.

For each `(wall configuration, player, pawn square)`, the supported lazy solver
now computes:

- distances from the pawn;
- distances to the goal row;
- capped forward and backward path counts on the shortest-path DAG;
- for every wall, the number of shortest paths using an edge that wall blocks.

The wall impact is the integer percentage on a 0–1000 scale. The ordering term is

```text
(impact_on_opponent - impact_on_mover) * path_flow_weight
```

before conversion to the target-player point of view. It changes ordering only.
No move is removed and no proof fact depends on the score.

A direct-mapped cache keyed by `(configuration id, player, pawn square)` stores
all wall impacts. Cache size is controlled by `--path-flow-cache-bits`; 18 bits
uses about 22 MiB per process and is the default portfolio setting.

## Deterministic reconstruction

The feature was first prototyped and then removed after an incorrect reading of
one timed pilot. Reimplementation from the archived outputs reproduces the old
search exactly, not merely the verdict:

- `H(5,2)`, depth 16: **2,326,659 nodes**, 544,616 TT hits;
- `P(4,2)`, depth 18: **47,214,748 nodes**, 12,223,522 TT hits.

This also exposed why stable move labels are mandatory: changing the ordering
changes child indices.

## Results

Fixed prefix:

```text
4×7×7: P(5,2) P(1,2)
```

### Wall third move `H(5,2)`

| remaining depth | policy | nodes | seconds in archived run |
|---:|---|---:|---:|
| 16 | baseline | 8,120,817 | 1.65 |
| 16 | path-flow 1 | **2,326,659** | **0.93** |
| 22 | baseline | 57,332,465 | 13.19 |
| 22 | path-flow 1 | **32,220,451** | **10.54** |
| 24 | path-flow 1 | 124,257,426 | 45.30 |
| 24 | path-choice 40 | **15,323,311** | **about 4.1** |

Path flow is useful here, but the simpler path-choice policy dominates at the
full archived horizon.

### Pawn third move `P(4,2)`

| remaining depth | policy | nodes | seconds in archived run |
|---:|---|---:|---:|
| 18 | baseline | 119,898,717 | 27.63 |
| 18 | path-choice 40 | 95,339,253 | 24.48 |
| 18 | path-flow 1 | **47,214,748** | **18.93** |

On this regime, path flow is the best tested policy. The current implementation
reproduces the 47,214,748-node result exactly; wall time is lower on the current
binary and machine, which is not used as a cross-build identity claim.

### Certified `3×9×10` branches with stable named moves

The earlier negative diagnosis on `3×9` used child indices after changing the
ordering. Because the ordering itself changes those indices, it did not hold the
position fixed. Named moves correct the protocol.

For the archived upper-bound representative

```text
P(7,1) V(1,0), target Player 1, remaining depth 31
```

| policy | nodes | seconds |
|---|---:|---:|
| baseline | 79,800,528 | 15.996 |
| path-choice 40 | 79,495,380 | 17.684 |
| path-flow 1 | **37,279,448** | **9.493** |

The three-policy race also selected `flow1`. Thus whole-path flow is not merely a
`4×7` specialization; it more than halves the node count on a branch belonging to
the certified `3×9×10` proof family.

A second named representative, `P(7,1) H(1,0)`, is solved by `flow1` at depth 31
in 89,887,471 nodes and 23.235 seconds. Interrupted exploratory runs of the other
policies are not treated as measurements.

A third representative supplies a complete baseline comparison:

| position | baseline | path-flow 1 |
|---|---:|---:|
| `P(7,1) V(5,0)` | 142,948,371 nodes, 29.857 s | **50,633,369 nodes, 13.173 s** |

The two completed vertical-reply comparisons therefore cut node count by about
53% and 65%. This is enough to justify the full 18-class campaign, not enough to
replace the portfolio with a single global policy.

### Cache size

On `P(7,1) V(1,0)`, increasing the direct-mapped path-flow cache from 16 to 18
bits lowers misses materially. Increasing from 18 to 20 bits saves only about
0.1 seconds while consuming roughly 69 MiB more per solver process. The compute
node default therefore remains 18 bits.

## Decision

Path flow is promoted as an **optional exact-ordering policy**, not as the global
default. The current evidence demonstrates at least two complementary specialists:

1. immediate shortest-path choice count (`path_choice_weight=40`);
2. whole shortest-path-flow impact (`path_flow_weight=1`).

Baseline ordering remains in the portfolio as the unmodified control and safety
net. It has not yet won a completed seed race, so calling it a third observed
regime would be numerically decorative rather than accurate.

The compute-node worker therefore races named policies on the same named
position and accepts the first exact completion. This costs cores but avoids the
observed horizon reversals. A shallow selector is still considered unsafe until
it is evaluated against completed full-depth proofs.

## Commands

```bash
./bin/lazy_specialized_solver \
  --width 4 --height 7 --walls 7 \
  --root-move 'P(5,2)' --second-move 'P(1,2)' --third-move 'P(4,2)' \
  --target 1 --start-depth 18 --max-depth 18 \
  --tt-bits 24 --transition-cache-threshold 1 \
  --path-flow-weight 1 --path-flow-cache-bits 18 \
  --no-bounds --no-pawn-table
```

Raw outputs are stored in `results/validation/path_flow_ordering/`.
