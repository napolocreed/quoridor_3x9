# The stalemate question, closed

**Claim under review** (sol's conjecture): a legal, non-terminal state always
grants the player to move at least one pawn move, so the `n == 0` branch of the
bounded-proof recurrence is unreachable and the documented semantics/code
divergence (empty conjunction = `true` vs. code returning `false`) is dead code.

**Result**: the conjecture is **true for every board of height H ≥ 3** — which
covers every variant studied in this repository — and **false for H = 2**,
where stalemates are reachable within two plies. The proof below is elementary
and needs *both* pawns' path invariants; the mover's invariant alone is not
sufficient, which is why the natural first proof sketch does not go through.

All references are to `docs/RULES.md` conventions: rows `0..H-1` top to bottom,
Player 1 starts at `(H-1, ⌊W/2⌋)` and wins on row `0`, Player 2 starts at
`(0, ⌊W/2⌋)` and wins on row `H-1`.

---

## Lemma 1 (path invariant)

*In every state reachable from the initial position, each pawn's cell lies in
the same wall-connectivity component as at least one cell of that pawn's goal
row.*

Here "wall-connectivity" means the graph on cells whose edges are the
orthogonally adjacent pairs not blocked by a wall; pawns never block edges of
this graph. (RULES.md defines the wall-legality check on "unblocked orthogonal
cell edges" — pawns are not walls; the pawn-transparent reading is an
inference from that text, adopted identically by the C++ engine, the Python
reference and `qref.mjs`.)

**Proof.** By induction over the move sequence.

*Base.* The initial position has no walls; the board is a single component
containing all rows.

*Wall placement.* Legality explicitly requires that, after placement, each pawn
has a path from its current cell to its own goal row. This is precisely the
invariant.

*Pawn move.* Walls are unchanged, so components are unchanged; it suffices to
show the moving pawn stays in its component.

- **Step** to an adjacent cell: the traversed edge is unblocked, so origin and
  destination are in the same component.
- **Straight jump** over the opponent at `n` to `z`: the edges `p–n` and `n–z`
  are both required to be unblocked, so `p` and `z` are connected through `n`.
- **Diagonal** to a perpendicular neighbour `z` of the opponent at `n`: the
  edges `p–n` (approach) and `n–z` (rule: "whose connecting edge is clear") are
  unblocked, so again `p` and `z` are connected through `n`.

The non-moving pawn does not move. ∎

Two reading notes. (a) The jump/diagonal cases assume the approach edge `p–n`
is unblocked — RULES.md's special-move clause ("when the opposing pawn
occupies **that adjacent cell**") refers back to a cell reachable over an
unblocked shared edge, and every implementation reads it that way. Under the
alternative reading (special moves across a blocked approach edge) the
*Theorem* below survives a fortiori — more available moves only helps the
mover — but this lemma's diagonal case needs the presupposition. (b) With two
pawns, jump and diagonal destinations are never occupied: the only other pawn
sits at `p`, in the approach direction. The case analysis would need care in
hypothetical >2-pawn variants.

Note the invariant is enforced for **both** pawns at every wall placement, and
this is what the theorem consumes: knowing only that *the mover* keeps a path
is not enough (see the Tightness section).

## Theorem (no stalemate for H ≥ 3)

Call a state **legal** when the two pawns occupy distinct cells and each pawn's
cell lies in the same wall-connectivity component as a cell of its goal row —
exactly the enumeration domain of `frontier_dump --exhaustive`, with no
reachability requirement. By Lemma 1, every reachable state is legal.

*On any board with `H ≥ 3` (any `W ≥ 1`, any wall stocks), every **legal**
non-terminal state grants the player to move at least one **pawn** move.*

In particular, a state with zero legal moves (pawn or wall) is unreachable —
indeed not even legal — the `n == 0` branch of the recurrence never executes,
and the semantics/code divergence cannot affect any proof on such boards. Note
the theorem needs neither reachability nor stock consistency: it holds on the
strict superset that the exhaustive audits enumerate. (The superset is strict:
on `4×3×3` there are 63,184 legal non-terminal states but only 62,732
reachable ones — 452 legal states are unreachable.)

**Proof.** Suppose for contradiction that in some legal non-terminal state
the player to move — call them A, pawn at `p`, goal row `g_A` — has no legal
pawn move. Write B for the opponent, pawn at `n_B`, goal row `g_B`;
`{g_A, g_B} = {0, H-1}`.

1. **`p` has at least one unblocked neighbour.** The state is non-terminal, so
   `p` is not on row `g_A`. By legality, `p`'s component contains a cell of row
   `g_A`, hence a cell other than `p`, hence the component has ≥ 2 cells and
   `p` has an unblocked edge.

2. **Every unblocked neighbour of `p` is occupied by B.** An empty unblocked
   neighbour is always a legal step. There is only one opponent, so `p` has
   *exactly one* unblocked neighbour, namely B's cell `n = n_B`.

3. **`n`'s only unblocked edge is `n–p`.** Since A has no legal move:
   - the straight jump fails, so the cell behind `n` (in direction `p → n`)
     is out of bounds or its edge from `n` is blocked;
   - by the rules, diagonals are then available, and both fail: each
     perpendicular neighbour of `n` is out of bounds or its edge from `n` is
     blocked.
   The four potential edges at `n` are: toward `p` (unblocked, by step 2),
   straight behind, and the two perpendiculars. Hence `n`'s unblocked edges
   are exactly `{n–p}`.

4. **The component of `p` is exactly `{p, n}`.** By steps 2 and 3.

5. **Contradiction.** Applying legality to A: row `g_A` intersects `{p, n}`;
   `p` is not on `g_A` (non-terminal), so `row(n) = g_A`. Applying legality to
   B: row `g_B` intersects `{p, n}`; `n` is not on `g_B` (non-terminal), so
   `row(p) = g_B`. Thus `{row(p), row(n)} = {0, H-1}`. But `p` and `n` are
   orthogonally adjacent, so `|row(p) − row(n)| ≤ 1`, forcing `H − 1 ≤ 1`,
   i.e. `H ≤ 2`. Contradiction with `H ≥ 3`. ∎

Two remarks on why the proof is shaped this way:

- Step 5 uses the invariant **twice**, once per pawn. A proof using only the
  mover's path (as in the natural sketch: "the first vertex of the mover's
  shortest path is either free, jumpable, or bypassable") is unrepairable,
  because the blocked-in configuration of step 4 is perfectly compatible with
  the mover having a path to its goal — the path simply runs through the
  opponent's cell. What makes it impossible for H ≥ 3 is that the *opponent*
  must simultaneously reach the *other* end of the board from inside the same
  two-cell prison.
- The theorem is strictly stronger than "no stalemate": it guarantees a pawn
  move even when the mover has walls in stock. So `stalemates_seen == 0` is a
  theorem for H ≥ 3, not an empirical observation, though the counter should
  stay in the audits as an implementation tripwire.

## Tightness: H = 2 stalemates are reachable

The bound `H ≥ 3` is sharp. On the `2×3` board (W=3, H=2) with ≥ 1 wall per
player, the following two-ply line reaches a stalemate:

- Initial: P1 at `(1,1)`, P2 at `(0,1)`. Anchors: `(0,0)` and `(0,1)`.
- **Ply 1** — P1 plays `V(0,0)`: blocks edges `(0,0)–(0,1)` and `(1,0)–(1,1)`.
  Both pawns keep vertical paths through the central column. Legal.
- **Ply 2** — P2 plays `V(0,1)`: blocks `(0,1)–(0,2)` and `(1,1)–(1,2)`.
  The central column `{(0,1),(1,1)}` is now sealed off, but P1 still reaches
  row 0 at `(0,1)` and P2 still reaches row 1 at `(1,1)`. Legal.
- **Ply 3** — P1 to move: the only unblocked neighbour `(0,1)` is occupied;
  the straight jump lands out of bounds; both diagonals `(0,0)`, `(0,2)` have
  blocked connecting edges. No pawn move. Both anchors are occupied, so no
  wall placement exists either — even if P1 still has walls in stock.
  **Zero legal moves.**

This state realizes exactly the two-cell-prison of step 4 above: `row(n) = 0 =
g_A` and `row(p) = 1 = g_B`, which adjacency permits only when `H = 2`.

Consequence: on H = 2 boards the stalemate convention is *semantically
meaningful*. With A the stalemated player, the documented semantics (empty
conjunction over the opponent's replies = `true`) makes stalemate a **loss for
the player to move** when the target is B (`Win(s, B, d)` = true, `Win(s, A,
d)` = false since an empty disjunction is false either way), while the current
code makes it a neutral dead end (both targets false). Exhaustive solves of
H = 2 variants under both conventions are the right regression artifact: they
pin down exactly which states change verdicts, and confirm the root value does
or does not move.

For every variant in this repository's experimental range (`3×9`, `4×3`,
`4×7`, `3×3`, and all H ≥ 3 smalls), the theorem applies and the divergence is
formally dead code. The recommended resolution:

1. keep the code's `false` (or an `abort()`) in the `n == 0` branch,
   documented as unreachable-for-H≥3 with a pointer to this theorem;
2. keep `stalemates_seen` in every audit;
3. state in `PROOF_SEMANTICS.md` that published claims are restricted to
   H ≥ 3 boards, or fix the convention explicitly before ever touching H = 2.

## Mechanical verification

`qscan.mjs` (same clean-room engine as `qref.mjs`) provides two independent
exhaustive checks on small variants:

- `scan` — forward BFS over all **reachable** states: verifies Lemma 1's
  invariant on every state, counts zero-pawn-move and zero-legal-move states,
  records minimal-ply stalemate witnesses;
- `scan-legal` — direct enumeration of the **legal superset** in the exact
  sense of `frontier_dump --exhaustive` (geometric wall legality, both-pawn
  goal connectivity, non-terminal, stock splits, both turns): counts
  zero-pawn-move states over the full domain of the theorem. On `4×3×3` this
  independently reproduces the archived count of **63,184** legal non-terminal
  states, with zero pawn-move-less states.
- `solve-both` — for H = 2 variants, solves the root under both stalemate
  conventions and compares;
- `diff-states` — the sharp version of the H = 2 demonstration: compares
  `Win(s, T, d)` under both conventions for **every** reachable state and both
  targets. Measured: 7 diverging verdicts on `3×2×1` (d=12), 12 on `3×2×2`,
  42 on `4×2×2` (d=14) — the first diverging state is exactly the tightness
  witness above. The convention is semantically live on H = 2, provably dead
  for H ≥ 3.

Exit codes encode the theorem: finding a pawn-move-less state on an H ≥ 3
variant makes `scan`/`scan-legal` exit 5; on H = 2 it is expected and exits 0.

## Verification summary (2026-08-01)

All runs archived in `results-stalemate/`.

- Reachable scans (`scan`), H ≥ 3: 15 variants (`3×3`, `4×3`, `5×3`, `3×4`,
  `4×4`, `3×5` × stocks), ≈ 1.9 M states — invariant violations: 0;
  pawn-move-less non-terminal states: 0.
- Legal-superset scans (`scan-legal`), H ≥ 3: 8 variants, ≈ 3.4 M states —
  pawn-move-less: 0. Independently reproduces the archived C++ count of
  63,184 legal non-terminal states on `4×3×3`.
- Adversarial counterexample hunt (independent scripts, `hunt_*.mjs`):
  ≈ 17.8 M legal states over degenerate topologies (`1×3`, `1×5`, `1×9`,
  `2×3`, `2×4`, `2×5`, `2×8`, `6×3`, `7×3`) — pawn-move-less H ≥ 3 states: 0.
  A pawn-move generator re-implemented from RULES.md alone agreed with
  `qref.mjs` on every enumerated state; an independent flood-fill re-check of
  Lemma 1 over all reachable states of 7 variants (incl. wall-saturated W=2
  boards) found 0 violations.
- H = 2 negative controls: stalemates found exactly as predicted (first at
  ply 2, witness bit-identical to the construction above), including with
  walls still in stock.
- A four-lens adversarial review (logic, rules fidelity, code audit,
  counterexample hunt) returned no fatal or serious finding; its minor
  remarks are incorporated in this document.

One deliberate strengthening surfaced by review: the proof never uses the
geometric wall-placement rules (no-cross, no-overlap) — only connectivity.
The theorem thus holds even for wall bitmasks that violate placement geometry
but keep both pawns goal-connected; the `frontier_dump --exhaustive` domain
is a subset of the proved domain. Domain equality between `scan-legal` and
the C++ `--exhaustive` enumeration was checked line-by-line against
`reference/frontier_dump.cpp` (config legality, distance-255 semantics,
stock splits, terminal exclusion, turn quantification).
