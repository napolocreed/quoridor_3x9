# Structural shortcut triage — 2026-08-02

This note evaluates four proposed shortcuts for the exact `4x7x7` frontier.
The standard is not whether an idea sounds asymptotically attractive, but whether
it preserves the bounded proof recurrence and attacks measured work.

## 1. Spectral connectivity: reject for the exact rule engine

The relevant wall-legality predicate is not connectivity of the whole cell
graph.  It is the conjunction of two terminal-set reachability predicates: each
pawn must remain connected to at least one cell of its own goal row.  A legal
position may contain an irrelevant disconnected region, so testing
`lambda_2(L) > 0` would reject valid wall configurations.

A wall also deletes two cell-graph edges, hence changes the Laplacian by two
positive rank-one edge terms rather than one.  Maintaining an eigensystem after
each candidate deletion is substantially more work than bit-parallel reachability
on a 28-cell board.  Floating comparison against zero would additionally insert
a numerical predicate into an exact proof.

Spectral values could only be heuristic ordering features.  The existing exact
shortest-path-flow feature is cheaper, directly related to both goal sets, and
already has named-position evidence.  No spectral prototype is justified.

## 2. ZDD wall families: valid representation research, low search priority

Wall sets are a plausible ZDD domain: they are sparse, and both structural
conflicts and monotone path preservation may compress.  The claimed constant
time pruning does not follow, however.  ZDD membership and restriction traverse
diagram nodes, while the solver still needs child identifiers, pawn-to-goal
distances and ordering metadata for every configuration it actually reaches.

The lazy engine visits about 1.4 million configurations on the hard depth-24
calibration, rather than eagerly consuming all 16.37 million.  A global diagram
must therefore beat both the lazy subset and its transition cache, including the
cost of extracting per-child metadata.

A future ZDD experiment should be offline first: build the exact legal family,
record diagram nodes/bytes, and benchmark batched successor restriction against
the existing flat mask cache.  Do not connect it to proof search unless it wins
that representation benchmark by enough to cover metadata extraction.

## 3. Learned proof priors: potentially useful, but ordering only

Of the two alternatives posed in the proposal, ML is the more plausible one.
It can preserve exactness when it chooses move order, a DFS/DF-PN portfolio, or
initial expansion priorities; every returned verdict must still be established
by the ordinary recurrence.  A prediction must never become a cutoff.

There are two practical cautions.  First, labels from `3x9` strategy maps are
not automatically calibrated proof-mass labels for `4x7`; geometry and branch
regimes differ.  Second, per-node inference must save more generation/search
than it costs.  A cheap selector over exact features may be more useful than a
large model evaluated at every node.

Claude owns the memo-to-NNUE and `9x9` programme, so sol will not duplicate it.
The exact `4x7` solver will later consume a frozen model only as an optional
ordering policy with deterministic fallback and full differential tests.

## 4. CGT disjunctive sums: reject; retain exact separator analysis

A geometric separation does not create a Conway disjunctive sum.  The players
share one alternating clock, victory is a first-arrival race rather than normal
play on the sum, and either player may spend a turn placing a wall in the other
component.  Interleavings therefore remain strategically coupled even when the
pawns cannot meet.

Separators may still support exact reductions, but they require a different
theorem: a regional signature must prove that all future legal moves outside the
signature are irrelevant to both goal reachability, wall-anchor conflicts,
stocks and race timing.  Without that future-independence proof, component
caching is only an unsound quotient.  At zero stock the coupling reduces to a
pawn race; that case is already covered exactly by the zero-wall tablebase and
was empirically too rare to accelerate bounded search.

## Selected next exact experiment

The next structural test should extend the useful part of the zero-wall idea by
one wall-DAG layer, but instrumentation comes first:

1. count proof nodes, TT misses and distinct configurations for total remaining
   wall stock `0`, `1` and `2` on the stable 40-branch family;
2. if the one-wall layer is materially populated, prototype an exact
   one-remaining-wall tablebase for a hot base configuration;
3. solve the base pawn graph plus every legal one-wall child configuration as a
   single finite attractor, preserving which player owns the last wall;
4. account separately for graph construction, table hits, bytes and saved DFS
   calls, and close the idea immediately if the layer is as sparse as zero stock.

For `4x7`, such a table has roughly `(1 + legal additions) * 2 * 28 * 27`
valid pawn/turn states before stock-owner and target bookkeeping: tens of
thousands rather than the 1,568 raw zero-wall indices.  It is therefore not
automatically cheap.  The histogram is the decision gate.

The immediate compute priority remains the already prepared 40-branch campaign
for the raw opponent TT hint-first arm.  That experiment has measured mixed
performance and can be accepted or rejected without introducing a new proof
inference.

## Measurement result: one-wall extension closed

The proposed histogram was run immediately.  The hard
`P(5,2) P(1,2) H(5,2)` depth-24 proof reached 375,925 positive-depth calls with
one remaining wall, including 162,244 unresolved TT probes across 12,881 wall
configurations.  The distribution is too diffuse: the hottest configuration had
only 528 misses; 512 configurations reached 64 misses, 31 reached 256, and none
reached 1,024.

The shallower `P(4,2)` calibration contained only 756 one-wall TT misses across
286 configurations.  The measured `3x9x10` branch never reached total stock two
or below.

A complete one-wall attractor must construct at least the base pawn graph and
normally many one-wall child graphs—thousands to tens of thousands of states per
configuration.  It cannot amortize against a maximum of 528 unresolved probes.
The one-wall tablebase is therefore closed before implementation.  Raw counters
and hashes are in
`results/validation/endgame_layers/benchmark_windows_local.json`.
