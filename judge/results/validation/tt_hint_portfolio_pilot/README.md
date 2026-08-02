# TT hint-first four-branch portfolio pilot

This local pilot validates the four-policy orchestration path before the full
40-branch `4x7x7` campaign.  It is not a promotion benchmark.

## Reproduction

From the repository root, with the MSYS2 UCRT64 runtime on `PATH`:

```powershell
$env:Path = 'C:\msys64\ucrt64\bin;' + $env:Path
python scripts/codex_portfolio_worker.py `
  --solver bin/lazy_tt_hint_first_solver.exe `
  --manifest experiments/manifests/4x7_w7_central_reply_portfolio.jsonl `
  --outdir results/validation/tt_hint_portfolio_pilot `
  --jobs 1 `
  --append-policy-file experiments/policies/flow1_hint_raw.json `
  --task-id 4x7w7-central-reply-third-01-H5_2 `
  --task-id 4x7w7-central-reply-third-04-H1_2 `
  --task-id 4x7w7-central-reply-third-19-V0_0 `
  --task-id 4x7w7-central-reply-third-37-P6_2
python scripts/summarize_portfolios.py `
  results/validation/tt_hint_portfolio_pilot
```

## Bound provenance

- Solver SHA-256:
  `2575b3ad10ae5ecb51ccaf709333e483ecbee3f53b79809761d5c5cca7dde090`
- Portfolio worker SHA-256:
  `6baa3cd23e300a2e6beb97980f1c6d9ec3093946be905947c02c239834a33613`
- Solver-output parser SHA-256:
  `5d4492114c4dc7ec8b0cfa3270b695cf3ddb40a0a3e798c038255fe20ccc32d3`
- Worker bundle SHA-256:
  `ee6caf7ef8679de65226b61b2d0e43ecb6f3672ea0fd7e2d06e178444420efa4`
- Portfolio summarizer SHA-256:
  `1a3b17c21db8d3c3e82685413318a3f6215d0aacbc4d1f15ad0ec2a8771208fe`
- Solver implementation SHA-256:
  `fd190aeaf55f5f5523472024647a41aa712a3f273e693facf7e0d488ef358d57`
- Experimental wrapper SHA-256:
  `9bc234d2fc491def30c3a5941fe412c7419c6225b29c869d8d7252f42afce343`
- Compiler: MSYS2 UCRT64 GCC 16.1.0, with the Makefile flags including
  `-Wl,--no-insert-timestamp`.  A second independent build produced the same
  solver SHA-256.
- Every winner is parseable, exact (`timeout=0`) and reports
  `stalemates_seen=0`.
- All four records use the same normalized policies and TT26 manifest tasks.

## Result

| task suffix | winner | nodes | solver seconds |
|---|---|---:|---:|
| `H5_2` | `choice40` | 15,323,311 | 4.14213 |
| `H1_2` | `flow1` | 16,832,741 | 5.26895 |
| `V0_0` | `baseline` | 72,550,877 | 17.0189 |
| `P6_2` | `flow1` | 89,118,727 | 28.5533 |

The hint arm won none of this final four-task sample.  The defensible conclusion
is operational rather than promotional: the fourth arm, policy whitelist,
campaign binding, co-winner handling and Windows cancellation all work end to
end.  The earlier isolated benchmarks were bimodal and four tasks are too few
to reject a complementary arm, so the pre-registered 40-branch gate on the quiet
gaming PC remains the final promotion-or-rejection test.
