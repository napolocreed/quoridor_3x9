# Research log: lazy domain engine

## Question

Can exact reduced-Quoridor proofs avoid global wall-configuration enumeration and
exploit corridor geometry without weakening correctness?

## Answer so far

Yes, for isolated branches. A lazy exact engine with incremental configurations and
transition caching cuts the isolated `4x7x7` precompute tax and more than halves
memory. A shortest-route choice ordering reduces one difficult same-position branch
from 223,188,594 to 15,323,311 nodes. The effect reverses on other branches, so it
is deployed as an exact full-depth portfolio rather than a global default.

An exact Pareto table over remaining wall stocks passes exhaustive small-board proof
differentials and further improves two representative branches. It remains
experimental until the 40-branch suite measures its tail behaviour.

## Protocol correction

Sorted child indices are not stable across ordering policies. The supported solver
now accepts named moves and portfolio tooling refuses index-based tasks. Earlier
same-index comparisons that denoted different moves were discarded.

## Next computational experiment

1. reproduce the 40 known central-reply branches with weights 0 and 40;
2. measure per-branch winner policies and regret;
3. attack all 39 first moves at total Player-1 horizon 27;
4. validate the Pareto table on the same family;
5. use the resulting exact dataset to study algorithm selection and corridor
   regimes, not value prediction.
