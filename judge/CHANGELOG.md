# Changelog

## 2026-08-02 — TT hint-first portfolio experiment

- Added an isolated exact path that tries an insufficient-depth TT move before
  full successor generation and returns early only after recursively proving the
  ordinary cutoff condition.
- Added opponent/target, pawn/wall and canonical-order controls plus exact
  symmetry transforms for diagnostic comparison.
- Passed sampled `3x3x1`/`4x3x2`, three complete 51,408-request `3x3x1`
  grids, and a debug canonical-key tripwire with zero verdict divergences.
- Kept raw opponent hint-first as an experimental portfolio candidate: local
  CPU time improved on two named regimes and regressed on the hard `4x7`
  wall-reply regime.  Canonical transforms are not recommended.  See
  `docs/TT_HINT_FIRST_2026-08-02.md`.
- Profiled exact-search calls at total remaining wall stocks `0/1/2` and closed
  the proposed one-wall tablebase before implementation: its TT misses are too
  diffuse across configurations to amortize a full attractor construction.
- Made the experimental hint binary inert unless flags explicitly enable it,
  added versioned policy overlays and stable task subsets to the portfolio
  worker, restricted policies to ordering-only options, and bound campaigns to
  the solver, normalized task universe and worker/parser bundle hashes.
- Hardened cross-platform races: Windows cancellation is explicit, naturally
  completed co-winners are retained, and completions inside a 20 ms grace use a
  deterministic solver-time tie break.
- Completed a four-branch TT26 pilot with exact results and zero stalemates;
  flow1 won two branches, baseline and choice40 one each, and raw TT hint-first
  won none.  The full 40-branch gaming-PC gate is therefore the final
  promotion-or-rejection test.
- Added an exact miss-token path for the lazy wall-configuration hash table. It
  removes one hash and the repeated probe chain for virtually every new
  configuration while preserving rehash behavior and physical table layout.
- Passed a stale-token debug test, forced-rehash differentials and the complete
  51,408-request small grid. Local timing remained below thermal noise, so the
  path stays experimental pending a quiet gaming-PC A/B.
- Added an exact TT address token that reuses the immutable candidate slots
  computed before recursion while reloading keys, metadata and replacement
  quality afterward. It passed two-way/four-way replacement stress, sampled
  differentials and the complete 51,408-request grid. Two long `4x7` regimes
  improved by about 2% locally, but a sub-second branch regressed, so it remains
  experimental pending a small quiet-machine branch sample.

## 2026-08-01 — exact zero-wall tablebase experiment

- Added an isolated, exact retrograde table for fixed configurations after both
  wall stocks reach zero.  Its target-specific least-attractor ranks handle
  cycles, draws and height-two stalemates without a no-cycle assumption.
- Passed sampled `3x3x1`/`4x3x2`, the full 51,408-request `3x3x1` proof grid in
  two cache regimes, and the reachable `3x2x1` stalemate grid with zero verdict
  divergences.
- Closed the mechanism as a negative exact-search result: on the named `4x7`
  depth-24 branch it removed only 0.005475% of DFS calls and did not improve
  time; shallower `4x7` bounds and the certified `3x9x10` branch never reached
  double-zero stock.  See `docs/ZERO_WALL_TABLEBASE_2026-08-01.md`.

## Unreleased

- reduced `4×7×7` precompute memory by storing a single goal-distance table and deriving the opponent table through exact rotation;
- added resumable third-ply branch scans and a dedicated central-opening verification harness;
- refuted the central `4×7×7` opening through ply 27 after 3.591 billion branch nodes;
- preserved the conservative no-distance-bound and no-pawn-table audit mode;
- integrated an external clean-room review and deterministic cross-toolchain reproductions;
- formalized the no-stalemate and wall-stock Pareto lemmas and added explicit audit counters;
- specified the `qcert-1` strategy-DAG format and added an independent verifier
  with adversarial corruption tests;
- added a streaming Python/SQLite `qcert-1` verifier for artifacts that exceed
  the in-memory verifier, including gzip, exact artifact hashes and no-overwrite
  persistent indexes, with exact per-wall-configuration connectivity profiles;
- aligned the JavaScript and SQLite verifiers on strict UTF-8 without BOM,
  universal JSONL line separators and the integer lexical grammar, with a
  shared byte-level adversarial corpus while retaining documented extension
  members;
- accepted the first production-scale qcert branch (`H(1,0)`): 9,836,857
  nodes, 25,175,363 regenerated edges, rank/bound 31, zero errors, with a
  hash-bound receipt and independently checked persistent index;
- specified `qcert-aggregate-1` and added an independent aggregate verifier
  that regenerates the opening and all reply orbits, binds every part by its
  stored-byte hash, records the aggregate/qcert/rules source hashes, and
  can compose identity/mirror branch proofs into the 35-ply initial-position
  bound; no production 18-part aggregate has yet been accepted;
- differential-checked the production profile reduction on 1,500 distinct
  wall configurations sampled from the accepted H10 index, with 10,024 exact
  legal moves, 1,208 declared moves, 3,000 rejected labels and 706,806
  all-cell connectivity-mask comparisons agreeing;
- hardened resumable audit and portfolio caches against stale commands, solver
  hashes, partial coverage, malformed counters and forged aggregate statuses;
- rebound all 36 archived `3x9x10` branches to their raw solver lines and named
  `forcing` diagnostics, and hash-inventoried every consumed audit file, before
  the final manifest may retain the 35-ply claim;
- made the dense sequential modes build under MinGW while rejecting only the
  POSIX-only `--parallel-second` launcher explicitly on Windows;
- replaced integer timeout exceptions with the dedicated `SearchTimeout` type;
- validated a topological cycle gate but rejected naive DFS deferral after a negative benchmark;
- implemented the isolated cache-first local-touch gate with pending transition
  handles, incremental resolution, K=0/2/4/all refinement and explicit savings
  counters; all four K values passed the exhaustive `3x3x1` proof grid;
- fixed an audit-found deferred-root crash in `--scan-current`, added its named
  three-wall regression, and restored the exact path-flow term in deferred proxy
  scoring; the corrected named benchmark makes the current gate a negative
  result (no partial K beats baseline), superseding the apparent K=2 gain;
- implemented and benchmarked a bounded DF-PN prototype, retained as experimental because mature DFS remains faster;
- rejected decremental shortest-distance repair after it tripled runtime despite identical nodes;
- promoted whole-shortest-path-flow impact as an optional exact ordering policy and cut two certified `3×9×10` branches from 79.8M to 37.3M and 142.9M to 50.6M nodes;
- generalized compute-node portfolios from scalar weights to named policy argument sets and prepared an 18-class stable-name `3×9×10` campaign.
- closed the height-2 stalemate convention, repaired the height-at-least-3 proof,
  and made a present zero `stalemates_seen` field mandatory in every new audit.

## v0.3.0 - 2026-07-27

- established an exact 35-ply minimax forcing horizon for `3×9×10`;
- completed the conservative 18-class upper-bound audit with bounds and pawn table disabled;
- completed the exhaustive 18-class lower-bound audit through ply 33;
- accumulated 12.862 billion audited search nodes across the matching bounds;
- expanded differential proof, symmetry and precompute validation;
- added a final machine-readable result manifest and updated research paper draft.

## v0.2.0 - 2026-07-27

- proved all 18 reply classes after the central opening for `3×9×10`;
- added machine-readable branch artifacts and exact proof binary;
- repaired and expanded differential testing;
- added a conservative no-pawn-table audit mode;
- added resumable verification scripts and reproducibility documentation.

## v0.1.0 - 2026-07-26

- initial `3×9×9` computational result and reproducible solver package.
