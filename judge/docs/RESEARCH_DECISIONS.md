# Research decisions

## Chosen question

The project switched from building a strong heuristic agent to resolving exact
unknown entries on the narrow-board Quoridor frontier. This was chosen because it
admits a falsifiable output: either every adversarial branch is proved or it is
not. Elo improvements are useful, but they are easier to manufacture accidentally
with a friendly benchmark.

## Current target

For `3×9` with 10 walls per player:

1. prove a finite Player-1 win after a concrete opening;
2. remove specialized pruning from a full replication;
3. test whether the 35-ply upper bound is also a lower bound;
4. preserve exact binaries, source, raw logs and resumable branch records;
5. seek reproduction by an implementation that does not share this engine.

## Validation ladder

The repository treats the following as progressively stronger evidence:

1. regression against known small-board winners;
2. legal-move differential testing against a simple Python engine;
3. exhaustive small-board comparison of bounded proof truth values;
4. independent audits of symmetry classes and wall-configuration counts;
5. full proof reruns with optional optimizations disabled;
6. compiler/toolchain variation and selected no-symmetry runs;
7. external reproduction by another solver.

Only the final item would turn the present internally replicated computational
claim into a result that should be treated as established rather than merely very
well annoyed by testing.

## Stop criteria

The exact-search line remains worthwhile while it either:

- resolves a public `?` entry;
- strengthens a result from winner-only to exact forcing horizon;
- materially reduces the trusted computing base; or
- produces a reusable verification artifact.

Increasing node counts without one of those outcomes is not progress. It is a
space heater with logging.
