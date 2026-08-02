# Draft upstream report

Subject: computational results for the unresolved 3×9 Quoridor frontier

I reproduced the public `3×9×8` first-player result and then obtained first-player proofs for `3×9×9` and `3×9×10` under the same standard movement and wall-legality rules.

For `3×9×10`, the witness opening is the central pawn advance. The 35 legal replies are reduced by horizontal reflection to 18 classes, and each representative is proved independently with a fresh process and transposition table.

Key figures:

- 18/18 reply classes proved;
- 4,260,347,144 aggregate representative nodes;
- 960.084 seconds summed search time;
- 35-ply upper bound from the initial position;
- zero legal-move divergences against a simple Python reference on 2,500 deterministic random positions;
- clean sanitizer run on small exact cases;
- one branch reproduced under Clang 17;
- full no-pawn-endgame-table audit included.

The result remains a computational claim pending independent reproduction. The bundle contains the exact executable, source, raw logs, hashes and resumable scripts.
