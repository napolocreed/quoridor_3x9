# Independent review by Claude Fable

Received 2026-08-01 from an independent Anthropic model working from commit
`1fe68fb` and the published rules/proof-semantics documents.

Contents:

- `REVIEW.md`: research review, reproduced results, reservations and proposals;
- `REPRODUCTION_LOG.md`: commands and outputs from Ubuntu 24 / g++ 13.3;
- `qref.mjs`: clean-room Node.js move generator and small bounded solver;
- `STALEMATE_THEOREM.md`: the reviewer's proof for height at least 3 and sharp
  reachable height-2 counterexample;
- `qscan.mjs`: independent reachable/path-legal state scanner and convention
  differential;
- `results-stalemate/`: selected compact scan outputs, hashes and reproduction
  commands.

`qref.mjs` includes the reviewer's later five-line library-compatibility update
(`pathToFileURL` main-module guard) so certificate verifiers can import the same
clean-room engine without executing its CLI. No game-rule code was changed.

Its optional `doc` stalemate mode preserves the literal empty-conjunction
semantics of the document reviewed at that time. The current
`docs/PROOF_SEMANTICS.md` now defines a no-action state as false for both targets;
`qref.mjs`'s default `code` mode matches that current convention. The historical
mode is retained to reproduce the sharp height-2 divergence, not as the current
published semantics.

The reviewer states that `qref.mjs` was written from `docs/RULES.md` and
`docs/PROOF_SEMANTICS.md` without reading or reusing the C++ solver or the Python
reference implementation. The files are preserved verbatim except for their
repository paths and filenames.

These materials are independent evidence, not code authored by this repository's
primary implementation. Their inclusion does not imply that the full 3×9×10
proof has been independently recomputed; the reproduction log covers selected
large branches and complete smaller variants.
