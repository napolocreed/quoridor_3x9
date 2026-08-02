# Bounded-proof semantics and soundness argument

This note states the exact question answered by the search. It is not a formal
verification of the C++ implementation. It makes the intended mathematics
explicit so that reviewers can compare code against something less ambiguous
than variable names chosen while a processor was being inconvenienced.

## Predicate

For state `s`, target player `T`, and remaining ply budget `d`, let
`Win(s,T,d)` mean:

> `T` has a strategy that reaches its goal after at most `d` further actions,
> against every legal action of the opponent.

No repetition rule is needed. The horizon is finite, and a positive proof
terminates at a goal state within that horizon.

## Recurrence

1. If `s` is terminal, `Win(s,T,d)` is true exactly when the terminal winner is
   `T`.
2. If `d = 0` and `s` is not terminal, it is false.
3. If `s` is non-terminal and has no legal child, it is false. Reaching the
   goal is the only winning event; a player does not win merely because the
   opponent has no action.
4. If `T` is to move, it is the disjunction over legal children:
   `exists c: Win(c,T,d-1)`.
5. If the opponent is to move, it is the conjunction over the non-empty set of
   legal children:
   `forall c: Win(c,T,d-1)`.

The implementation's `prove` routine is a direct depth-first evaluation of this
recurrence. Move ordering may change cost but not the Boolean expression.

## Empty-child states and the no-stalemate theorem

The explicit third recurrence clause matches the C++ implementation and removes
the former ambiguity between its `false` result and the vacuous-truth convention
for an empty universal quantifier. The choice is semantically relevant on
height-2 boards. It is dead code for every published result here, by the theorem
below.

Call the graph of pawn cells joined by unblocked orthogonal edges the **wall
graph**. Pawns do not remove edges from this graph. Call a state **path-legal**
when the pawns occupy distinct cells and each pawn's wall-graph component meets
that pawn's goal row. This does not assert that the state is reachable from the
initial position, that its wall mask is geometrically constructible, or that its
stocks are historically consistent.

### Path invariant

Every reachable state is path-legal. Initially the wall graph is connected. A
legal wall placement explicitly rechecks both goal paths. A pawn move does not
change the graph and leaves the moving pawn in its component: an ordinary step
traverses one unblocked edge, while a straight jump or diagonal traverses two
unblocked edges through the opponent's cell. The other pawn does not move.

The invariant is needed for **both** pawns. The moving pawn's path alone may run
through the opponent and does not rule out the two-cell prison used below.

### No stalemate for height at least 3

On any board with `height >= 3`, every path-legal non-terminal state grants the
player to move at least one legal pawn move.

Suppose instead that player A, at cell `p`, has no pawn move.

1. Because the state is non-terminal and A's component meets A's goal row, that
   component contains a cell other than `p`. Thus `p` has an unblocked neighbor.
2. An empty unblocked neighbor would be an ordinary move. With only one opposing
   pawn, every such neighbor must therefore be the same cell `n` occupied by B;
   consequently `n` is the unique unblocked neighbor of `p`.
3. If the edge straight beyond `n` were available, A could jump. When it is not,
   either available perpendicular edge at `n` would allow a diagonal. Since no
   move exists, the only unblocked edge at `n` is `n-p`.
4. The shared wall-graph component is therefore exactly `{p,n}`.
5. A is non-terminal, so path-legality for A forces `n` onto A's goal row.
   B is also non-terminal, so path-legality for B forces `p` onto B's opposite
   goal row. The adjacent cells `p` and `n` would have row difference
   `height-1`, which is at most one only when `height <= 2`: a contradiction.

The theorem is stronger than absence of a complete stalemate: a pawn move exists
regardless of wall stocks. It also holds over a strict superset of reachable
states. For example, the exhaustive `4x3x3` grid contains 63,184 path-legal
non-terminal states, while the independent forward scan finds 62,732 reachable
ones; the extra 452 states make the exhaustive test conservative.

### Sharp height-2 counterexample

The height bound cannot be weakened. On `3x2` with at least one wall per player,
the legal line `V(0,0), V(0,1)` seals the central column containing the two
pawns. Player 1 then has no step, straight jump, diagonal, or remaining wall
anchor. Both goal-path checks still pass because each pawn reaches its goal row
through the other pawn's cell. This is a reachable non-terminal state with no
legal action.

Under the explicit recurrence above it is a win for neither target. The former
empty-conjunction reading instead made it a win for the opponent of the player
to move. Independent exhaustive checks find verdict differences on height-2
variants, so any future height-2 claim must state this convention rather than
appeal to the theorem.

Every new top-level and decomposed-branch audit result reports `stalemates_seen`. It
counts executions of the zero-legal-child branch, not unique states or states
lacking only pawn moves; TT hits and early exact shortcuts can affect the count.
New height-at-least-3 audit harnesses require the field to be present and zero.
Historical records that predate the counter remain marked as not recorded. The
theorem closes the semantic question and independent exhaustive scans add
evidence, but they do not retroactively provide the missing runtime tripwire;
absence is never rewritten as zero.

## Depth parity normalization

A player can first become terminal only immediately after its own action. A
budget whose final ply belongs to the other player therefore adds no possible
positive terminal. `target_relevant_depth` removes that unusable final ply.

This preserves `Win` and gives the monotonic relations used by the transposition
table:

- a positive proof at relevant depth `d` remains positive at every larger
  relevant depth;
- a failure at relevant depth `d` remains a failure at every smaller relevant
  depth.

The table stores the smallest positive depth and largest failed depth. Full
packed keys are compared after hashing. The development build also aborts if a
stored positive and negative interval overlap.

## Wall-stock dominance

Fix a path-legal state of height at least 3, including its wall mask, pawn cells,
side to move, target player and remaining ply budget. Let the target's remaining
wall stock be `a` and the opponent's be `b`.

- If `Win(s,T,d)` is true for `(a,b)`, it remains true for every `(a',b')` with
  `a' >= a` and `b' <= b`.
- If `Win(s,T,d)` is false for `(a,b)`, it remains false for every `(a',b')` with
  `a' <= a` and `b' >= b`.

Proof: the no-stalemate theorem guarantees a pawn action at every non-terminal
descendant, for every compared stock pair. Additional walls are optional
actions, never obligations. In the first case the target replays the original
strategy and ignores its additional stock;
the opponent with fewer options cannot introduce a response absent from the
original game. The second statement is the contrapositive under the reversed
resource order, or equivalently the same simulation argument from the
opponent's perspective.

The height/path-legality condition matters under this repository's explicit
`no child => false` convention. On a height-2 two-cell prison, removing an
opponent's last wall action can create an empty move set and change a true
universal node to false. No published result or Pareto-table experiment uses
that domain.

The experimental Pareto table uses only these implications. It does not infer a
value between incomparable stock pairs.

## Symmetry

Horizontal reflection preserves player identities, goals, side to move, wall
stocks, legal pawn transitions, and legal wall placements.

The 180-degree transform additionally swaps player identities, wall stocks,
side to move, and the target player. Under that simultaneous swap it preserves
terminal status and the bounded predicate.

The release contains direct semantic checks on all reachable `3×3×1` states
and sampled `4×3×2` states. A selected full `3×9×10` branch is also rerun with
symmetry disabled.

## Why the positive result is enough to determine the winner

The upper-bound audit proves a finite Player-1 strategy. Infinite cycles or a
choice of draw adjudication cannot defeat a strategy that reaches the goal in a
bounded number of plies against every response.

## Why the lower-bound audit establishes 35 plies

The upper-bound audit supplies a Player-1 strategy within 35 plies. The lower
run fixes every reflection class of legal first moves and exhaustively refutes a
Player-1 force within the next 32 plies, excluding every win of total length at
most 33. Player 1 can only finish on an odd-numbered ply, so 34 is impossible.
Together these facts establish a minimum forcing horizon of exactly 35 plies,
provided both complete audits succeed.

## Remaining trusted computing base

The result still trusts:

- the C++ transition implementation;
- wall-configuration enumeration and lookup;
- packed-state serialization;
- bounded recursion and transposition-table implementation;
- compiler, runtime, and hardware.

Independent Python checks and optimization-removal runs reduce correlated risk,
but do not make this a machine-checked theorem. A separate solver remains the
most valuable replication.
