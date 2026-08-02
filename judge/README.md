# Quoridor frontier research

Exact-search experiments for narrow Quoridor variants, focused on the unresolved `3×9` frontier.

## Current computational result

Under the rules implemented and tested here, the starting position of `3×9` Quoridor with **10 walls per player** is a **first-player win in exactly 35 plies**.

A witness opening is the central pawn advance from `(8,1)` to `(7,1)`.

### Upper bound

After that move:

- Player 2 has 35 legal replies;
- horizontal reflection reduces them to 18 exact state classes;
- every representative class is proved winning for Player 1 in a separate process with a fresh transposition table;
- the conservative audit disables both the distance bound and the pawn-only endgame table;
- this audit visits **9,309,248,724 nodes** and reports **1,805.559 seconds** of sequential search time;
- the largest child proof depth yields a 35-ply win from the initial position.

### Matching lower bound

A separate audit fixes each of the 18 reflection classes of Player 1's possible first moves and asks whether Player 1 can force a win within the remaining 32 plies. All 18 searches terminate negatively with no timeout, while also disabling the distance bound and pawn-only endgame table.

- classes refuted: 18/18;
- nodes: **3,553,060,577**;
- sequential search time: **716.472 seconds**;
- conclusion: no first-player win exists in 33 plies or fewer.

Player 1 can only complete a win on an odd-numbered ply. Therefore the 35-ply upper bound and 33-ply lower bound establish an **exact minimax forcing horizon of 35 plies**.

The public frontier table consulted before the run listed `3×9` with 9 and 10 walls as unresolved. This repository also contains the preceding `3×9×9` result.

This is a reproducible computational result, not a machine-checked theorem. An
external clean-room Node.js engine agrees on move generation and six complete
small variants. Separately, recompilation of the C++ solver with another
toolchain reproduced selected large archived branches at the same node counts.
Production extraction of a compact independently checkable strategy certificate
is now in progress; this tree already contains the `qcert-1` format and an
independent verifier for cross-checking its exported parts. The first real part,
`H(1,0)` after the canonical opening, has been accepted independently at rank
31 with 9,836,857 certificate nodes and zero errors. Seventeen representative
parts and the final aggregate verification still remain; this is not yet a
certificate of the initial position.

## Frontier continuation

The next unresolved case under study is `4×7` with 7 walls per player. The current exact partial result is that Player 1 has no forced win within 25 plies and Player 2 has no forced win within 26 plies. All 39 legal first moves were refuted independently for Player 1 at the remaining 24-ply bound, using 4,888,712,130 nodes in aggregate with both specialized pruning modules disabled. A separate Player-2 audit reaches depth 26 with 901,837,164 cumulative nodes. Therefore neither player can force a win within the first 26 plies. The game-theoretic outcome remains unresolved.

The most plausible Player-1 opening, the central pawn advance `P(5,2)`, is now also refuted at the next relevant horizon of 27 plies. Player 2's central reply `P(1,2)` leaves 40 legal Player-1 third moves; all 40 were searched with fresh transposition tables and none forces a Player-1 win by ply 27. The decomposed audit used 3,591,324,070 nodes and 920.522 seconds of sequential search. This eliminates the central opening as a 27-ply witness, but does not yet establish the full Player-1 lower bound through ply 27 because the other 38 first moves remain to be treated.

## Build and validation

```bash
make -j2
make test
```

Validation artifacts include:

- exhaustive legal-move comparison against a deliberately simple Python engine
  on 63,184 path-, structure- and stock-legal non-terminal `4×3×3` states (a
  conservative superset of the 62,732 reachable non-terminal states);
- exhaustive bounded-proof comparison on 51,408 `3×3×1` queries;
- sampled proof comparisons on larger states;
- independent symmetry-class checks;
- independent wall-configuration and transition counts;
- GCC, Clang, AddressSanitizer and UndefinedBehaviorSanitizer runs on tractable workloads.
- compact one-goal distance storage validated against the independent move generator and an archived `3×9×10` branch; the symmetric table derivation reduces `4×7×7` precompute RSS from roughly 2.95 GiB to 2.15 GiB.
- an explicit no-stalemate theorem for height at least 3, a sharp reachable
  height-2 counterexample, exhaustive small-board regression checks and a
  mandatory zero `stalemates_seen` field in every new audit result;
- Claude Fable's independent review, clean-room verifier and reproduction log
  under `external_reviews/claude_fable_2026-08-01/`.
- disk-backed verification of the first production qcert branch, plus a
  zero-divergence profile check over 1,500 distinct configurations drawn from
  its accepted 9,836,857-node index.

## Reproduce `3×9×10`

Upper-bound audit:

```bash
JOBS=1 scripts/verify_3x9_w10_core_only.sh
```

Lower-bound audit:

```bash
JOBS=1 scripts/verify_3x9_w10_lower_bound.sh
```

Both harnesses write one atomic JSON record per class and skip matching completed branches on restart.

## Reproduce the `4×7×7` central-opening depth-27 refutation

```bash
make -j2
SECONDS_PER_BRANCH=300 TT_BITS=27 scripts/verify_4x7_w7_central_depth27.sh
```

The verifier writes one atomic record per Player-1 third move and resumes from completed records. It deliberately disables the distance bound and pawn-only table. A full run needs several gigabytes of memory and roughly twenty minutes of sequential search on the reference environment, because computers remain stubbornly literal about the phrase “all branches”.


## Lazy exact engine and compute-node campaigns

The supported lazy solver constructs only wall configurations reached by the
current proof obligation and accepts stable named moves so ordering experiments
cannot silently change the tested position:

```bash
make lazy lazy-smoke lazy-differential
./bin/lazy_specialized_solver \
  --width 4 --height 7 --walls 7 \
  --root-move 'P(5,2)' --second-move 'P(1,2)' --third-move 'H(5,2)' \
  --target 1 --start-depth 24 --max-depth 24 \
  --tt-bits 26 --transition-cache-threshold 1 \
  --path-flow-weight 1 --path-flow-cache-bits 18
```

See:

- `docs/LAZY_ENGINE_RESULTS_2026-07-31.md` for validation and benchmarks;
- `docs/ORDERING_PORTFOLIO.md` for exact three-policy ordering races;
- `docs/SHORTEST_PATH_FLOW_ORDERING_2026-08-01.md` for the full shortest-path-DAG signal;
- `docs/BOUNDED_DFPN_PROTOTYPE_2026-08-01.md` and `docs/DECREMENTAL_DISTANCE_NEGATIVE_2026-08-01.md` for experiments retained as negative results;
- `docs/CODEX_GAMING_PC.md` for the reproducible compute-node setup.

The current frontier manifest attacks every `4x7x7` first move at total ply 27:
`experiments/manifests/4x7_w7_p1_depth27_frontier.jsonl`. Each task now races
baseline, immediate path-choice and whole shortest-path-flow policies. On the
archived `P(4,2)` branch, path flow reduces the proof from 119,898,717 to
47,214,748 nodes while preserving the exact verdict. On the certified
`3×9×10` reply `P(7,1) V(1,0)`, stable named moves reveal a second substantial
gain: 79,800,528 baseline nodes fall to 37,279,448, with wall time dropping from
15.996 to 9.493 seconds. On `P(7,1) V(5,0)`, it cuts 142,948,371 nodes to
50,633,369 and 29.857 seconds to 13.173. The earlier index-based negative
diagnosis was invalid because changing move ordering also changed the indexed
position.

The full 18-class upper-bound portfolio is prepared at
`experiments/manifests/3x9_w10_upper_portfolio.jsonl` for the compute node.

## Artifacts

- `results/3x9_w10/final_result.json`: compact machine-readable claim and audit manifest;
- `results/3x9_w10/audit/core_only/`: conservative 35-ply upper-bound proof;
- `results/3x9_w10/audit/lower_bound_33/`: exhaustive refutation of every win within 33 plies;
- `results/3x9_w10/BRANCHES.md`: human-readable primary branch table;
- `results/validation/`: differential and toolchain validation;
- `docs/PROOF_SEMANTICS.md`: exact bounded-search semantics;
- `docs/CERTIFICATE_FORMAT.md`: independently checkable `qcert-1` strategy-DAG format;
- `docs/RULES.md`: implemented rule specification;
- `docs/REPRODUCIBILITY.md`: commands and audit boundaries.
- `docs/TOPOLOGICAL_CYCLE_GATE_2026-08-01.md`: validation and rejection of the
  naive DFS form of the proposed union-find/no-cycle gate;
- `docs/SHORTEST_PATH_FLOW_ORDERING_2026-08-01.md`: an optional path-flow ordering
  that exactly reproduces archived node counts and wins a distinct corridor regime;
- `docs/BOUNDED_DFPN_PROTOTYPE_2026-08-01.md`: a correct bounded DF-PN prototype
  that remains slower than the mature DFS solver on current frontier branches.
- `external_reviews/claude_fable_2026-08-01/`: independent review materials.
- `reference/qcert_verify.mjs`: hardened verifier using the external clean-room
  move generator, with no search or C++ transition code.
- `reference/qcert_verify_sqlite.py`: streaming two-pass verifier using the
  independent Python rules engine and a unique disk-backed raw-state index.

## Correctness boundary

The claim depends on legal move generation, path-preserving wall placement, state packing, symmetry transforms, bounded existential/universal proof semantics and transposition-table depth semantics.

The strongest archived audits remove the two specialized pruning modules most likely to deserve suspicion. They still share the same underlying C++ rules and search implementation. Software remains software, which is merely mathematics after being given several opportunities to lie.

## License

MIT. See `CITATION.cff` for attribution metadata.
