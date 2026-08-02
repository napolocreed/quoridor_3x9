# Experimental solvers

These variants document falsified or not-yet-promoted ideas. They are kept for
reproducibility rather than presented as supported binaries.

- `lazy_transition_solver.cpp`: isolates adaptive transition caching.
- `lazy_symcache_solver.cpp`: canonical configuration-payload cache; lower RSS,
  slower on the hard reference branch.
- `lazy_dominance_solver.cpp`: repeated neighbouring-TT probes for exact stock
  dominance; fewer nodes but worse wall time.
- `lazy_pareto_solver.cpp`: compact auxiliary Pareto-bound TT prototype. It
  passes the exhaustive `3x3x1` proof differential, but suite-wide promotion is
  pending.

The supported experimental candidate is `src/lazy_specialized_solver.cpp`.
- `lazy_pathshape_solver.cpp`: shortest-route choice-count ordering. It is
  spectacular on some corridor branches and pathological on others.
- `lazy_domain_solver.cpp`: combines path-choice ordering with the exact Pareto
  wall-stock table for interaction benchmarks.
- `lazy_pns_solver.cpp`: basic graph Proof-Number Search. It is compact on tiny
  boards and unusably slow on the first meaningful `4x7` benchmark; retained as
  a negative result before a possible memory-bounded DF-PN redesign.
- `lazy_tt_slot_reuse_solver.cpp`: retains immutable TT candidate addresses
  between probe and record while rereading replacement state after recursion.
  It is exact and favorable on long local branches, but remains unpromoted
  because a sub-second branch regressed.

Manifests under `experiments/manifests/` use stable move labels. The central-reply
portfolio reproduces known branches and yields data about ordering regimes. The
Player-1 depth-27 manifest is the next actual frontier campaign.
