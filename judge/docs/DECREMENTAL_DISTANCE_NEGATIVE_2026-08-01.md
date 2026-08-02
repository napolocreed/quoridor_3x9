# Decremental shortest-path prototype — negative result (2026-08-01)

## Hypothesis

A wall removes only two pawn-graph edges, so the child goal-distance maps might
be updated locally from the parent instead of recomputed by two full BFS passes.
The prototype seeded the removed-edge endpoints and propagated only distance
increases until the Bellman equations reached a fixed point.

The update is exact for edge deletions. A validation mode recomputed both BFS
maps after every child and found no mismatch on the fixed frontier benchmark.

## Benchmark

Position:

```text
4×7×7: P(5,2) P(1,2) H(5,2)
remaining depth 16, target Player 1, TT22
```

| mode | nodes | search seconds | RSS | distance-cell increases |
|---|---:|---:|---:|---:|
| ordinary full BFS | 8,140,570 | 1.94 | 118 MiB | n/a |
| decremental fixed point | 8,140,570 | 5.13 | 118 MiB | 634,025,579 |

The Boolean result, node count, TT hits, and cutoffs are identical. The
incremental algorithm is about 2.6 times slower.

## Why it loses

The board has only 28 cells. A full bit-parallel BFS is cheap and has predictable
memory access. A wall can invalidate a large shortest-path plateau, causing the
local relaxation to revisit cells repeatedly. Across 330,505 child
configurations, 661,008 goal-map updates triggered more than 634 million cell
increases.

The apparent locality of the graph edit therefore does not imply locality of
the shortest-path repair. The prototype is rejected and is not retained in the
supported solver. A future dynamic-distance attempt would need a fundamentally
different representation, such as level-set support counts, rather than a queue
of repeated Bellman relaxations.

Artifacts are under `results/validation/decremental_distance/`.
