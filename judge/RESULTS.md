# Results

## 3×9, 8 walls per player

Reproduced a first-player win after the central pawn advance. The public reference table already records this configuration as a first-player win.

## 3×9, 9 walls per player

The central advance is proved winning with a 35-ply upper bound.

### Monolithic run

- nodes: 1,909,467,037
- elapsed search: 452.349 s
- maximum resident set: 1,887,424 KiB

### Decomposed verification

All 35 legal Player-2 replies were reduced to 18 reflection classes and proved independently.

- `parallel_result proven=1 disproven=0 unresolved=0 total_depth=35`
- slowest class: representative 15, 2,514,031,626 nodes, 523.305 s
- aggregate wall time with 3 workers: 11m44s
- maximum resident set: 1,099,596 KiB

## 3×9, 10 walls per player

### Exact claim

The starting position is a first-player win in **exactly 35 plies**. A witness opening is the central pawn advance `(8,1) -> (7,1)`.

### Conservative upper-bound proof

- raw Player-2 replies after the opening: 35
- exact reflection classes: 18
- classes proved for Player 1: 18/18
- representative nodes, summed independently: 9,309,248,724
- representative search time, sequential sum: 1,805.5593 s
- upper bound from the initial position: 35 plies
- distance bound disabled: yes
- pawn-only table disabled: yes
- fresh process and transposition table per class: yes
- proof executable SHA-256: `ff11c2530a15c534922d4348f7cf0d9e66366f7742951fb38e8550a375e5837c`

### Matching lower bound

For each of the 18 reflection classes of Player 1's legal first moves, the solver fixes that move and exhaustively asks whether Player 1 can force a win in the remaining 32 plies.

- classes refuted: 18/18
- aggregate nodes: 3,553,060,577
- aggregate search time: 716.47244 s
- no win in 33 plies or fewer
- distance bound disabled: yes
- pawn-only table disabled: yes
- no timeout: yes

Because Player 1 can only win after one of Player 1's turns, a first-player win length is odd. Existence at 35 and non-existence through 33 therefore imply an exact minimax forcing horizon of 35 plies.

See `results/3x9_w10/final_result.json`, `results/3x9_w10/audit/core_only/summary.json` and `results/3x9_w10/audit/lower_bound_33/summary.json`.

## Validation status

The archived validation includes:

- 63,184 exhaustive legal-move comparisons on `4×3×3`, zero divergences;
- 51,408 exhaustive bounded-proof comparisons on `3×3×1`, zero divergences;
- 5,000 sampled proof comparisons on `4×3×2`, zero divergences;
- independently checked root and reply reflection partitions;
- independent count of 2,929,319 wall configurations and 24,832,956 one-wall transitions for `3×9×10`;
- clean sanitizer results on tractable cases.

The result is internally replicated and externally unverified by a separate full solver.

## 4×7, 7 walls per player

This public-frontier case remains unresolved, but the current audits establish that neither player can force a win within the first 26 plies:

- Player 1 cannot force a win within 25 plies;
- Player 2 cannot force a win within 26 plies;
- all 39 legal Player-1 first moves were fixed and refuted independently at the remaining 24-ply bound;
- aggregate Player-1 root audit: 4,888,712,130 nodes and 1,270.723 s of search;
- completed Player-2 depth-26 audit: 492,564,493 nodes at depth 26, 901,837,164 cumulative;
- 16,368,423 legal wall configurations and 155,145,930 one-wall transitions precomputed;
- distance bound and pawn-only table disabled;
- full 64-bit transposition keys and a fresh table for every Player-1 first move;
- the 39-move root action set matches the independent Python reference engine exactly.

See `results/4x7_w7/audit_lower_bound_25/summary.json`, `results/4x7_w7/audit_p2_lower_bound_26/summary.json` and the earlier exploratory manifests.

### Opening test at total depth 25

The highest-ranked pawn opening, `P(5,2)`, was fixed and searched independently for the remaining 24 plies. It does **not** force a Player-1 win within 25 plies.

- nodes: 1,232,686,204;
- elapsed search: 327.958 s;
- TT hits: 484,844,538;
- no timeout;
- distance bound and pawn-only table disabled.

This rules out the obvious forward-pawn witness at the first still-possible Player-1 win horizon, but does not refute other first moves or deeper wins.

### Central opening refuted at total depth 27

The central Player-1 opening `P(5,2)` does not force a win within 27 plies. Player 2 can answer with the central pawn move `P(1,2)`. From that state:

- Player 1 has 40 legal third moves;
- every third move was searched independently at the remaining 24-ply bound;
- all 40 searches terminate negatively, without unresolved branches;
- aggregate nodes: 3,591,324,070;
- aggregate TT hits: 1,464,909,655;
- aggregate sequential search time: 920.522 s;
- distance bound and pawn-only table disabled;
- fresh transposition table per third move.

This is an exact bounded refutation of one opening, not yet a complete no-win-through-27 result for the starting position. The remaining 38 Player-1 first moves still require a corresponding Player-2 refutation or a direct root audit.

See `results/4x7_w7/depth27_central_reply0_scan/summary.json`.

### Memory reduction for the next frontier

The engine now stores one goal-distance table per wall configuration and derives Player 2 distances through exact 180-degree rotation and player exchange. Reachability is represented by the same distance table (`255` means unreachable), removing two redundant bitmask arrays. On `4×7×7`, measured precompute RSS fell from roughly 2.95 GiB to 2.15 GiB, allowing a `2^27`-entry packed transposition table to fit in the available environment. The compact build reproduces the archived `3×9×10` branch node and hit counts exactly and passes the full differential suite.

## Lazy exact-search programme

A second exact engine now constructs wall configurations only when reached by the
current branch. It passes 2,500 independent random move comparisons, 500 random
bounded-proof comparisons and the exhaustive 51,408-query `3x3x1` proof grid.

On the same difficult `4x7x7` branch ending in `H(5,2)`, the lazy baseline uses
223,188,594 nodes and 47.25 search seconds. A corridor-specific ordering based on
the number of shortest-route choices reduces this to 15,323,311 nodes and 3.71
seconds. Combining that ordering with the exact wall-stock Pareto table reaches
12,875,101 nodes and 3.33 seconds.

The gain is branch-dependent. Stable named moves and full exact ordering portfolios
are therefore mandatory; shallow pilot searches have already been observed to
select the wrong full-depth ordering. See `docs/LAZY_ENGINE_RESULTS_2026-07-31.md`.
