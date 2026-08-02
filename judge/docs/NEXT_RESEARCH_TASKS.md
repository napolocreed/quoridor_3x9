# Next research tasks

Priority order after commit `2c2a690` and the lazy-domain branch.

## 2026-08-01 coordination override

The certificate is now a parallel production task owned by Claude: `qcert2`
extracts per-class witnesses and retains the complete state-to-rank map. Sol
must not build a competing production emitter. The independent `qcert-1`
verifier in this tree remains the cross-check for exported parts.

The first real export, branch `H(1,0)`, is accepted independently at rank 31
(9,836,857 nodes and 25,175,363 regenerated edges). Claude subsequently
completed the 18 binary extractions and owns the final portable aggregate.
After its aggregate receipt, the `3x9` validation programme is closed: sol must
not add another verifier, certificate layer or replication pass.  Future work
consumes the publication artifact and returns to the open exact frontier.

The cache-first local touch gate in `LOCAL_CYCLE_GATE_2026-08-01.md` is now
implemented behind its isolated compile-time macro.  Move differentials and all
four exhaustive `3x3x1` K grids pass.  Independent audit caught both a deferred
`--scan-current` root crash and a missing path-flow term in proxy scoring; both
now have regressions.  With the ordering term restored, no partial K beats the
baseline on the required named branch.  This implementation is closed as a
negative result, not a portfolio candidate.

The exact zero-wall retrograde table in `ZERO_WALL_TABLEBASE_2026-08-01.md`
is also closed as a negative result for bounded exact search.  It passed the
complete small proof grid and handles cycles and height-two pats exactly, but
the `4x7` depth-24 calibration reached only 11,148 eligible nodes out of
124.3 million.  Threshold 1 removed 6,803 DFS calls while building 1,163
tables; shorter `4x7` bounds and the certified `3x9x10` branch reached no
double-zero-stock state at all.  Do not add it to the frontier portfolios.

The TT hint-first experiment in `TT_HINT_FIRST_2026-08-02.md` is exact and
more promising, but deliberately remains a candidate rather than a default.
Trying raw TT hints only on opponent-to-target nodes improved local CPU time on
the `P(4,2)` calibration and one certified `3x9` branch, but regressed by 6.8%
on the hard `H(5,2)` depth-24 branch.  Canonically transforming every TT move
made more hints usable but cost more than it saved.  The next gate is the known
40-branch `4x7` family on the quiet gaming PC; judge aggregate throughput and
tail latency, not one friendly position.  A four-branch TT26 pilot exercised the
complete worker path: flow1 won two branches, while baseline and choice40 won
one each; raw hint-first won none.  Hashes were uniform, every verdict was exact
and every stalemate counter was zero.  This authorizes the full gate but offers
no local evidence for promotion; the 40-branch result is the final decision.

The spectral/ZDD/ML/CGT proposals are triaged in
`STRUCTURAL_SHORTCUTS_TRIAGE_2026-08-02.md`.  Spectral connectivity and a Conway
sum are not valid exact reductions for the rule predicate; ML remains an
ordering-only track owned by Claude; a ZDD is an offline representation
experiment at most.  The remaining-wall histogram has now closed the one-wall
tablebase extension: 162,244 TT misses on the hard branch were spread over
12,881 configurations, with a maximum of only 528 for any one configuration.
Do not build the much larger attractor.  The next active gate remains the
40-branch TT hint-first portfolio calibration.

The wall-mask index miss-token experiment in
`MASK_INDEX_PROBE_2026-08-02.md` removes a provably redundant second hash-table
probe for every new configuration except rehash boundaries. It passes the
complete small exact grid and saves about one million hashes on a representative
production branch, but its 1--2% apparent local gain is smaller than laptop
thermal variance. Keep it out of the 40-branch policy race; a short, pinned A/B
on the gaming PC is sufficient to promote or close it.

The TT slot-reuse experiment in `TT_SLOT_REUSE_2026-08-02.md` removes the much
more frequent duplicate TT address calculation between probe and record. It
avoids 56.8 million `mix64` calls on `V(0,0)` depth 24 and improves two long
local regimes by roughly 2%, but a sub-second branch regresses. It is a binary
substitution, not another ordering policy: sample it on a small stratified
subset of the 40 known branches, then either apply it uniformly or close it.

The immediate compute-node order is therefore:

1. do not spend the gaming PC on a wider local-touch K portfolio unless the
   proxy and net-BFS accounting are redesigned;
2. run the full gaming-PC handoff checklist before any long campaign;
3. reproduce the stable-name 40-branch `4x7` family with supported policies,
   and calibrate raw opponent hint-first as an isolated fourth arm;
4. decide the two mechanical microoptimizations (mask-index miss token and TT
   slot reuse) on short quiet-machine A/B samples without multiplying policy
   arms;
5. continue the open Player-1 depth-27 frontier with only policies that earn
   their total process/memory cost.

Keep `reference/qcert_verify_sqlite.py` source-frozen during this production
handoff: its SHA-256 is part of every receipt, including accepted H10. A robust
resume mode is a post-bundle v2 task, not an in-flight patch. Its minimum sound
design seals a complete ingestion before reuse, binds that seal to certificate,
schema, verifier and rules hashes, and checkpoints pass 2 only between complete
`(hw,vw)` configuration groups. Cached JSON reports alone must never bypass
proof obligations. With H10 timings, reusing a sealed index would save 833 of
1,239 seconds after interruption, but changing the verifier now would require a
fresh validation of every production part.

## 1. Re-run the certified `3×9×10` upper-bound family with stable policies

Run `3x9_w10_upper_portfolio.jsonl` across all 18 reply representatives. This
campaign is unusually valuable because every outcome and target depth are already
certified, while the first stable-name seed cut one branch from 79.8M to 37.3M
nodes. It measures whether path-flow ordering accelerates certificate extraction
and independent reproduction across the complete proof family.

Deliverables:

- one atomic race record per representative;
- aggregate policy winners, nodes and wall times;
- comparison against archived dense/core branch counts;
- solver binary hash and machine metadata.

## 2. Reproduce and label the known 40-branch family

Run `4x7_w7_central_reply_portfolio.jsonl` on the gaming PC. The game-theoretic
answers are already known, so any disagreement is a defect. The winning policies and per-branch costs form the first exact dataset for algorithm selection. The campaign now races baseline, immediate path-choice and whole shortest-path-flow orderings.

Deliverables:

- atomic JSON per branch;
- aggregate CSV/JSON;
- CPU, compiler and memory metadata;
- comparison against dense archived nodes and outcomes.

## 3. Attack the open Player-1 depth-27 frontier

Run `4x7_w7_p1_depth27_frontier.jsonl`. A completed `solved=0` task refutes that
opening through total ply 27. A completed Player-1 win would close the frontier in
the opposite direction. Timeouts remain unknown, not losses.

Start with two concurrent portfolios, then increase only if total throughput rises.

## 4. Learn ordering regimes from exact data

Do not train a value function. Train or derive a selector for exact move-ordering
policies using only branch-level features available before full search:

- board geometry and wall counts;
- pawn distances;
- shortest-route choices;
- cut/bridge statistics;
- legal wall count;
- previous-depth proof costs and TT hit rates.

Evaluate selector regret against the full three-policy race. Shallow-depth winner
alone is an invalid label because `P(4,2)` exhibits a horizon reversal.

## 5. Promote or reject the Pareto stock table

Run the same 40-branch suite with and without the compact Pareto table at fixed TT
memory. Promotion requires positive geometric-mean speedup without a damaging tail
and zero proof discrepancies.

## 6. Hot-configuration local retrograde

Measure whether frequently revisited wall masks can be solved as small pawn-state
subgames. Promotion requires lower total work after accounting for table
construction. The previous direct local TT duplicated global information and was
slower.  The exact leaf-DAG special case (both stocks zero) is now also known to
be too rare.  A future design must trigger before stock exhaustion and exploit
wall-mask DAG structure without rebuilding the global TT under another name.

## 7. Independent reproduction

Adapt the public Rust solver or build a small certificate checker for named bounded
positions. Internal variants sharing move generation are not independent evidence.
