# Computationally resolving two narrow Quoridor frontier cases

## Abstract

We report computational first-player wins for Quoridor on a board of width 3 and height 9 with 9 and 10 walls per player. Both configurations were unresolved in the public results table consulted before the experiments. For the 10-wall case, a central first move is followed by 35 legal opponent replies, partitioned into 18 horizontal-reflection classes. Separate bounded proof searches establish a win for every representative. A conservative rerun disabling the distance bound and pawn-only endgame table visits 9.309 billion nodes. A complementary exhaustive audit fixes every first-move reflection class and refutes a forced win within 33 plies, visiting 3.553 billion nodes. Since a first-player win can occur only on an odd ply, these audits establish an exact minimax forcing horizon of 35 plies. Legal move generation and bounded-search semantics are differentially tested against simple reference implementations. The result remains software-based and awaits external reproduction by a structurally separate solver.

## 1. Problem

A Quoridor position is a deterministic, perfect-information game state. On each turn a player moves a pawn or places a wall, while preserving a path to the goal for both pawns. The combination of many candidate wall placements, path-legality constraints, pawn jumps and cycles makes exact search expensive.

The public table at `https://grantslatton.com/solving-quoridor` listed the `3×9` cases with 9 and 10 walls per player as unknown at the time of this work.

## 2. Results

### 2.1 `3×9×9`

The first player wins after the central pawn advance. A monolithic proof and a decomposed 18-class verification both produce a 35-ply upper bound.

### 2.2 `3×9×10`

The first player wins in exactly 35 plies after the central pawn advance `(8,1) -> (7,1)`.

#### Upper bound

After this opening, the opponent has 35 legal replies. Exact horizontal reflection reduces them to 18 classes. Every representative is proved winning for Player 1 in a fresh process and fresh transposition table.

The strongest archived run disables the distance bound and pawn-only endgame table:

- representative searches: 18
- covered legal replies: 35/35
- total representative nodes: 9,309,248,724
- sum of reported search time: 1,805.5593 s
- upper bound from the initial position: 35 plies
- solver executable SHA-256: `ff11c2530a15c534922d4348f7cf0d9e66366f7742951fb38e8550a375e5837c`

#### Lower bound

A separate audit considers all 18 reflection classes of legal first moves. Each first move is fixed, then a bounded search tests whether Player 1 can force a win within the remaining 32 plies. All searches terminate without proving a win and without timeout.

- classes refuted: 18/18
- total nodes: 3,553,060,577
- sum of reported search time: 716.47244 s
- conclusion: no first-player win exists in 33 plies or fewer

Player 1 moves on odd plies, so a first-player terminal win cannot first occur on ply 34. The forcing horizon is therefore exactly 35.

## 3. Solver

The engine pre-enumerates wall configurations and stores, per configuration, goal reachability, distances, movement edges, legal wall additions and symmetry transforms. The proof search is existential on the target player's turns and universal on the opponent's turns. Iterative depth limits are memoized with monotone transposition semantics.

The conservative exact-horizon audits use:

- exact packed state keys;
- horizontal and player-swapping rotational symmetry;
- a two-slot transposition table with full-key equality checks;
- move ordering only for performance;
- no distance bound;
- no pawn-only endgame table;
- one fresh process and table for each decomposed class.

## 4. Validation

### 4.1 Differential move generation

The optimized C++ engine and a structurally different Python rules engine produce identical complete legal move sets on an exhaustive grid of 63,184 path-, structure- and stock-legal non-terminal `4×3×3` states. This is a conservative superset of the 62,732 reachable non-terminal states found by an independent forward scan. Additional deterministic random tests cover `3×5` and `3×9` states.

### 4.2 Differential proof semantics

A simple reference solver and the optimized engine agree on 51,408 bounded target/depth queries over the complete reachable `3×3×1` state set, including a run with transpositions and symmetries disabled. A further 5,000 sampled queries on `4×3×2` agree.

### 4.3 Exact regression cases

The solver reproduces known small-board winners, including both first-player and second-player cases.

### 4.4 Symmetry and precompute audits

Independent scripts verify the 35-to-18 root and reply partitions. A separate enumerator independently obtains 2,929,319 wall configurations and 24,832,956 one-wall transitions for `3×9×10`, matching the optimized engine.

### 4.5 Toolchain checks

AddressSanitizer and UndefinedBehaviorSanitizer report no diagnostic on tractable regression workloads. Selected branches are reproduced with Clang rather than the GCC build used for the main logs.

### 4.6 Strategy-certificate status

The repository specifies the independent `qcert-1` strategy-DAG format and
contains both in-memory JavaScript and disk-backed Python/SQLite verifiers. The
first production branch, after canonical moves `P:22,H:1:0`, has been accepted
by the disk-backed verifier: 9,836,857 distinct nodes, 25,175,363 regenerated
edges, rank and branch bound 31, and zero errors. A separate deterministic
comparison on 1,500 wall configurations from that accepted index finds no move
divergence from the naive rules engine and no divergence in 706,806 all-cell
goal-connectivity checks against fresh BFS. This establishes only that branch;
certificate verification of the initial position still requires all 18 reply
classes and successful `qcert-aggregate-1` composition.

## 5. Limitations

This is not a formally verified proof. A correlated defect in state transitions, proof recursion, state canonicalization or wall-configuration preprocessing could invalidate the claim. The lower- and upper-bound audits remove specialized pruning but share the same full C++ implementation. External reproduction should vary the rules engine, state representation or proof algorithm.

## 6. Reproduction

See `docs/REPRODUCIBILITY.md`. The archive includes source, exact executables, raw logs, parsed records, environment data and SHA-256 hashes.
