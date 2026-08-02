# TT hint-first generation experiment — 2026-08-02

## Result

Trying the transposition table's previous best move before generating its
siblings is exact, but not uniformly faster.  The useful version is deliberately
conservative: try raw TT hints only at opponent-to-target nodes, reject hints
that are not legal in the current symmetry frame, and otherwise fall back to the
unchanged complete generator.

This version improved single-run CPU time by 4.5% on the `4x7` pawn-reply
calibration and by 3.3% on a certified `3x9x10` branch.  It was 6.8% slower on
the harder `4x7` wall-reply branch at remaining depth 24.  It is therefore kept
as an experimental portfolio policy, not promoted as the global default.

The implementation is isolated by `QSPEC_TT_HINT_FIRST_EXPERIMENT` and the
supported lazy binary is compiled without it.

## Exact mechanism

An insufficient-depth TT entry may still supply a move hint.  In mode
`opponent`, when the opponent of the proof target is to move:

1. regenerate just that pawn move or wall placement with exact legality checks;
2. if it is illegal in the current state, continue with normal complete
   generation;
3. if it is legal, recurse into it first;
4. return immediately if it refutes the target, without constructing or sorting
   its siblings;
5. otherwise generate every legal move, assert that the hinted child is present,
   skip its duplicate, and continue the ordinary universal recurrence.

No verdict is inferred from the hint.  An invalid hint, a legal non-cutting hint
and a missing TT hint all converge back to the baseline recurrence.  The mode is
therefore an ordering/materialisation change only.

Opponent-only is intentional.  After a failed bounded query, a target-node hint
usually identifies the hardest losing child rather than a winning cutoff.  At an
opponent node it identifies a refuting child, which often cuts immediately at the
next horizon.  On the measured runs, opponent hints cut on 199,145/207,913 legal
attempts (`4x7` pawn reply), 1,331,518/1,798,803 (`3x9`), and
3,365,011/4,241,719 (`4x7` wall reply at depth 24).

## Symmetry experiment

The supported TT key is symmetry-canonical while its old move payload is stored
in the frame of whichever representative wrote the entry.  That is harmless for
correctness: a raw move that is not legal is ignored.  On the `P(4,2)`
calibration, 238,374 of 446,287 raw opponent hints were rejected this way.

The prototype also implements exact move transformations for column reflection,
180-degree rotation with player exchange, and their composition.  This makes all
445,184 opponent hints legal on that branch and reduces the tree from 47,214,750
to 47,003,785 nodes (0.4468%).  It does not improve CPU time: selecting and
carrying the canonical move frame costs more than the smaller tree saves in this
prototype.  `order-only` isolates that effect by transforming/reordering the hint
after full generation without trying it early.

The canonical path is retained as an audited control, not as the recommended
policy.  The candidate command uses:

```text
--tt-hint-first-mode opponent --no-tt-hint-transform
```

## Validation

The independent Python bounded recurrence agreed on:

- 2,000 sampled `3x3x1` requests;
- 2,000 sampled `4x3x2` requests;
- the complete 51,408-request `3x3x1` grid in raw-opponent mode;
- the same complete grid with canonical opponent hints;
- the same complete grid with the mechanism disabled.

A non-`NDEBUG` state-solver build also passed 2,000 requests while checking that
the key returned with a transform is exactly the pre-existing canonical key.
Across every named benchmark, verdicts, timeouts and `stalemates_seen=0` agree.

## Local benchmark summary

These are single runs on the 6-core/12-thread Windows laptop while Claude's
certificate exporter occupied one core.  `TotalProcessorTime` is reported to
reduce scheduler noise, but the timing is still calibration evidence rather
than a promotion benchmark.

| position and bound | mode | nodes | CPU seconds | relative to off |
|---|---|---:|---:|---:|
| `4x7 P(5,2) P(1,2) P(4,2)`, d=18 | off | 47,214,750 | 14.03125 | — |
| same | raw opponent | 47,214,750 | 13.40625 | 4.5% faster |
| same | canonical order-only | 47,003,785 | 14.03125 | tied at timer resolution |
| same | canonical opponent | 47,003,785 | 14.546875 | 3.7% slower |
| `3x9x10 P(7,1) V(1,0)`, d=31 | off | 37,397,601 | 8.609375 | — |
| same | raw opponent | 37,397,601 | 8.328125 | 3.3% faster |
| `4x7 P(5,2) P(1,2) H(5,2)`, d=24 | off | 124,257,426 | 35.4375 | — |
| same | raw opponent | 124,257,426 | 37.84375 | 6.8% slower |

The detailed counters, hashes and exact commands are in
`results/validation/tt_hint_first/benchmark_windows_local.json`.

## Four-branch portfolio pilot

Before handing the full 40-branch gate to the gaming PC, the production worker
ran four deliberately heterogeneous named branches at TT26 on the local laptop.
The unchanged three controls raced the appended `flow1_hint_raw` policy under
one experimental binary.  All four results were exact, all reported
`stalemates_seen=0`, and the solver and worker hashes were uniform.

| branch | winning policy | nodes | solver seconds |
|---|---|---:|---:|
| `H(5,2)` | `choice40` | 15,323,311 | 4.14213 |
| `H(1,2)` | `flow1` | 16,832,741 | 5.26895 |
| `V(0,0)` | `baseline` | 72,550,877 | 17.0189 |
| `P(6,2)` | `flow1` | 89,118,727 | 28.5533 |

The hint arm won none of this final four-task sample.  These single-run timings
are calibration observations, not a rejection benchmark: the sample is small,
and the earlier isolated timings were deliberately bimodal.  The defensible
result is operational: the worker, overlay, campaign identity, co-winner grace
and Windows cancellation path work before the costly campaign.  Only the
pre-registered 40-branch gate may promote or reject the fourth arm.

The atomic records and exact command are archived in
`results/validation/tt_hint_portfolio_pilot/README.md`.

## Decision and next gate

Keep raw opponent hint-first as one experimental portfolio arm.  Do not combine
it with canonical transforms and do not replace the supported solver yet.  Its
promotion gate is the stable-name 40-branch `4x7` family on the quiet gaming PC,
at fixed TT memory, evaluated by total throughput and tail latency.  If it cannot
win enough complementary branches to pay for another process, close it as a
documented negative.
