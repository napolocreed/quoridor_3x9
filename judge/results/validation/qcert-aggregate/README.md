# qcert-aggregate-1 validation fixture

This is a deliberately small end-to-end aggregate for `3x4x0`. Player 1 plays
`P:7`; the three regenerated Player-2 replies form two horizontal-reflection
orbits. `branch_left.jsonl` proves the `P:0` representative within three plies
and covers `P:2` by reflection. `branch_center.jsonl` proves the self-mirror
`P:4` response in one ply. Consequently the aggregate certifies Player 1 within
`2 + max(3, 1) = 5` plies from the initial position.

The fixture tests the generic proof-composition rule. It is not evidence for
the production `3x9x10` claim.
