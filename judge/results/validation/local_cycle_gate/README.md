# Local cycle-gate validation

`exhaustive.jsonl` records direct runs of
`reference/local_cycle_gate_check.py` on 2026-08-01. Reproduce the main rows
with `make local-gate-check`; the two additional geometry checks use:

```text
python3 reference/local_cycle_gate_check.py --width 5 --height 3 --walls 3
python3 reference/local_cycle_gate_check.py --width 2 --height 2 --walls 1
```

These are exhaustive classification/soundness checks, not search-speed
benchmarks. See `docs/LOCAL_CYCLE_GATE_2026-08-01.md` for scope.
