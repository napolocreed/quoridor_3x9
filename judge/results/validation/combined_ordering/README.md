# Combined path-choice + path-flow pilot

Position: `4×7×7 P(5,2) P(1,2) H(5,2)`, target Player 1, remaining depth 24.

Policy: `--path-choice-weight 40 --path-flow-weight 1`.

The process was manually terminated after roughly 40 seconds without a result.
The standalone `path_choice_weight=40` policy completes this position in roughly
four seconds. The linear combination is therefore rejected as a portfolio member;
individually useful ordering signals do not add linearly in an AND/OR search tree.
