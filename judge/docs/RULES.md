# Rules and coordinate convention

This repository studies the two-player Quoridor rules below. The specification is
included because “standard rules” is not a serialization format, however often
software projects pretend otherwise.

## Board and goals

- The board contains `height × width` pawn cells.
- Coordinates are zero-indexed `(row, column)` from the top-left.
- Player 1 starts at `(height-1, floor(width/2))` and wins upon reaching row `0`.
- Player 2 starts at `(0, floor(width/2))` and wins upon reaching row `height-1`.
- Player 1 moves first.

The experiments reported here use width `3`, height `9`, and either `9` or `10`
walls per player.

## Pawn moves

A pawn may move to an orthogonally adjacent cell when the shared edge is not
blocked by a wall and the destination does not contain the opposing pawn.

When the opposing pawn occupies that adjacent cell:

1. if the cell immediately behind the opponent in the same direction exists and
   its connecting edge is clear, the moving pawn jumps straight over the opponent;
2. otherwise, the moving pawn may move diagonally to either orthogonal neighbor of
   the opponent whose connecting edge is clear.

A pawn never shares a cell with the opponent.

For every reported board (`height >= 3`), the path-preservation rule implies
that a path-legal non-terminal state always has at least one legal pawn move. A
state is path-legal when the pawns are distinct and each remains connected in
the wall graph to its own goal row. The proof and the sharp `height = 2`
counterexample are recorded in `docs/PROOF_SEMANTICS.md`.

On a non-terminal state with no legal action, the implemented bounded predicate
returns `false` for both target players: only reaching a goal is a win. Such
states are reachable on height-2 boards, so future work there must state this
convention explicitly. Solver outputs include a `stalemates_seen` counter; new
reported audits require the field to be present and zero.

## Walls

There are `(height-1) × (width-1)` anchors for each orientation.

- `H(r,c)` blocks the two vertical cell edges immediately above/below the
  horizontal wall anchored at `(r,c)`.
- `V(r,c)` blocks the two horizontal cell edges immediately left/right of the
  vertical wall anchored at `(r,c)`.

A wall placement is geometrically illegal when it:

- occupies an already occupied wall anchor in either orientation;
- crosses a wall of the opposite orientation at the same anchor;
- overlaps one segment of a neighboring parallel wall.

It is also illegal unless, after placement, each pawn still has at least one path
through unblocked orthogonal cell edges to its own goal row. The check starts from
the pawns' current cells.

A placed wall is permanent. Each placement consumes one wall from the moving
player's stock.

## Cycles and proof meaning

No artificial repetition, move-count, or adjudication rule is added. Pawn cycles
are legal. The reported positive result is a bounded forcing result: Player 1 has
a strategy that reaches its goal within the stated number of plies against every
legal response, including delaying cycles. Consequently, the positive claim does
not depend on selecting a particular draw convention for infinite play.

A **ply** is one action by one player, whether a pawn move or a wall placement.
