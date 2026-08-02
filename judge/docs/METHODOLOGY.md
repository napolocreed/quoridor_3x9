# Methodology

## State model

The solver pre-enumerates every geometrically non-overlapping wall configuration reachable within the total wall budget. For each configuration it stores:

- legal cell-to-cell directions;
- distance-to-goal tables;
- goal-reachability masks;
- legal one-wall transitions;
- horizontal-reflection and 180-degree player-swapping transforms.

A position consists of a wall-configuration index, both pawn squares, remaining wall counts and side to move.

## Bounded proof search

For a selected target player, a node is:

- existential when the target moves;
- universal when the opponent moves.

Terminal wins are exact. The search asks whether the target can force a win within the remaining number of plies. Transposition entries store the smallest depth with a positive proof and the largest depth with a failed proof. Full packed state keys are stored in every entry; hashing selects candidate slots but never substitutes for equality.

The conservative final audits disable the optional distance bound and pawn-only table. Their result therefore rests on terminal checks, complete legal child generation, existential/universal recursion and exact transposition reuse.

## `3×9×10` upper-bound decomposition

1. Fix Player 1's central pawn advance.
2. Generate all 35 legal Player-2 replies.
3. Pack each post-reply state and its horizontal mirror exactly.
4. Group identical canonical keys into 18 classes.
5. Solve every representative in a fresh operating-system process with a fresh transposition table.
6. Accept the opening only when all 18 representatives return a positive Player-1 proof without timeout.

No proof information is shared between reply classes. Shared precomputed board tables are immutable.

## `3×9×10` lower-bound decomposition

1. Generate all legal Player-1 first moves.
2. Group the 35 moves into 18 exact horizontal-reflection classes.
3. For each representative, fix the first move.
4. Ask whether Player 1 can force a win in the remaining 32 plies.
5. Run with distance bounds and pawn-only tables disabled.
6. Require a complete negative result without timeout for every class.

This proves that no first-player strategy wins in 33 plies or fewer. Since Player 1 can only make the terminal move on an odd ply, the next possible horizon is 35.

## Independent checks

The Python reference engine implements wall geometry, path legality, pawn jumps and diagonal moves without using the C++ precomputed tables. Separate reference programs test bounded proof semantics on complete small state spaces. Independent scripts audit symmetry partitions and wall-configuration counts.

These checks do not constitute formal verification. External reproduction remains the most valuable next step.
