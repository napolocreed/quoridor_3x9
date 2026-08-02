# Topological cycle gate experiment — 2026-08-01

## Question

Can the lazy solver avoid constructing a full child wall configuration when a
candidate wall is guaranteed not to disconnect either pawn from its goal?

The proposed gate comes from the planar dual of the pawn graph. Represent every
wall as two unit barrier edges on the `(height+1) × (width+1)` junction lattice.
Contract all perimeter junctions into one outside component. A candidate wall
passes through three junctions `a-b-c`.

If `a`, `b`, and `c` belong to three distinct existing barrier components, adding
`a-b` and `b-c` cannot create a new cycle. Since a newly disconnected region in
a planar grid must be bounded by a newly completed barrier cycle, the placement
cannot destroy reachability. It is therefore path-legal without a pawn-to-goal
BFS. If any two component labels coincide, the gate says only “unknown” and the
normal exact reachability check remains mandatory.

The gate is one-sided:

- `safe` means the placement is proven path-safe;
- `fallback` does not mean illegal.

## Independent exhaustive validation

`reference/cycle_gate_check.py` enumerates every structurally legal wall mask up
to the requested cap. For every candidate classified safe, it verifies that no
cell which could reach its player's goal before the wall loses that reachability
afterward.

Results:

| board | configurations | candidate additions | gate safe | fallback | false safe |
|---|---:|---:|---:|---:|---:|
| `4×3`, 3 walls/player | 301 | 988 | 238 (24.09%) | 750 | 0 |
| `3×5`, 4 walls/player | 1,880 | 8,108 | 1,980 (24.42%) | 6,128 | 0 |

Machine-readable outputs are under
`results/validation/cycle_gate_profile/`.

## Search-profile measurement

On the fixed `4×7×7` position

```text
P(5,2) P(1,2) H(5,2)
```

at remaining depth 16, the ordinary transition cache built 984,503 wall
transitions. The topological gate classified:

- 264,320 as immediately safe;
- 720,183 as requiring fallback;
- safe share: 26.85%.

The classification rate is therefore consistent across the exhaustive small
boards and a real frontier branch.

## Naive deferred-materialisation prototype

An experimental `--defer-cycle-safe` mode emits gate-safe wall children without
building their distance maps. The child configuration is materialised only if
search actually visits it. This mode passes the full 51,408-query `3×3×1`
bounded-proof differential test.

However, the current DFS engine requires child geometry for its strongest move
ordering and benefits heavily from its transition cache. Removing both costs
more than the deferred construction saves.

At the same `4×7×7` depth-16 position with TT22, using the final instrumented build:

| mode | nodes | search seconds | configurations |
|---|---:|---:|---:|
| normal lazy DFS | 8,140,570 | 1.94 | 330,505 |
| deferred gate with geometric proxy ordering | 10,061,655 | 3.40 | 507,069 |

The initial unscored deferred prototype was substantially worse again. The
geometric proxy recovered most of the node explosion but did not beat the
normal engine.

## Interpretation

The gate is sound and potentially useful, but it exposes an architectural
coupling:

> In the present DFS solver, child construction performs both legality work and
> the exact geometric evaluation used to order every child.

Avoiding construction also removes information that makes alpha-beta-style
cutoffs cheap. The gate should therefore not be promoted as a blanket DFS
optimization.

Its best expected use is in a search that materialises children incrementally:

1. bounded DF-PN or another AND/OR search expands only its current most-proving
   child;
2. an unmaterialised gate-safe wall can remain a compact move handle;
3. full distance maps are built only when that child is selected;
4. cycle-risk candidates still use the exact fallback immediately.

A second viable design is a two-stage DFS generator that refines only a small
number of top proxy-ranked safe walls, but that requires branch-family
benchmarks before it can be trusted. The current deferred mode remains an
experimental negative result and is disabled by default.


The clean benchmark artifacts are stored under
`results/validation/deferred_cycle_gate/final_*`. Earlier crash-debug outputs from
the first prototype were deliberately excluded from the research archive.
