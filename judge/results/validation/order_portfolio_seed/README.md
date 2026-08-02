# Ordering portfolio seed results

Stable named positions only. The records are intended as seed data for the larger
compute-node campaign, not as a universal policy ranking.

- `4×7×7`, `P(5,2) P(1,2) H(5,1)`, depth 24: `choice40` wins the exact race.
- `3×9×10`, `P(7,1) V(1,0)`, depth 31: `flow1` reduces the search from
  79,800,528 baseline nodes to 37,279,448 and wins the race.
- `3×9×10`, `P(7,1) H(1,0)`, depth 31: `flow1` completes in 89,887,471
  nodes and 23.235 seconds. Interrupted exploratory baseline runs are deliberately
  not treated as benchmark measurements.

- `3×9×10`, `P(7,1) V(5,0)`, depth 31: `flow1` reduces 142,948,371
  baseline nodes to 50,633,369, with 29.857 seconds falling to 13.173.

See `summary.json` and the per-race JSON records for commands and solver hashes.
