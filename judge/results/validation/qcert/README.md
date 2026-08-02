# qcert validation fixture

`cert_3x3x0.jsonl` was emitted by Claude Fable's clean-room `qcert.mjs` on
2026-08-01 and copied unchanged into this repository. It is a Player-2 strategy
certificate for the initial `3x3` board with zero walls and bound 4.

SHA-256:

```text
7f36036cce38918425b9bfb320224f5fd94a7a4ae1c513c700a7d50702842aae
```

Validate it with:

```text
node reference/qcert_verify.mjs results/validation/qcert/cert_3x3x0.jsonl
node reference/qcert_verify_check.mjs
python3 reference/qcert_verify_sqlite.py results/validation/qcert/cert_3x3x0.jsonl
python3 reference/qcert_verify_sqlite_check.py
```

The fixture is intentionally small enough for line-by-line inspection. It is
external validation material, not output from the experimental C++ emitter.
The Python smoke also exercises gzip input, the persistent-database no-overwrite
rule, strict gzip framing, exit codes 0/1/2 and twenty-three malformed-certificate
families. Passing this fixture is not evidence that a large production
certificate has been checked.

The configuration-profile reduction is exhaustively differential-tested against
the baseline Python `legal_moves` on 2,078 reachable non-terminal `3x3x1` states
and all 6,910 legal declared moves across 29 wall configurations, plus 300
deterministic `3x9x10` samples.

The height-2 two-wall stalemate is rejected as a no-action certificate node,
matching `qcert_verify.mjs` and the `qcert-1` non-empty-obligation rule.

## First production-scale branch verification

`H10_sqlite_verification_2026-08-01.json` is the compact receipt for the first
production-scale run of the disk-backed verifier. It accepted Claude Fable's
`H10.qcert1.jsonl` export, SHA-256
`961df2b3b91ba136404f5a24fd2a98c1ed886a3443ab5cfd71f4abddbaeff1d4`:

- 881,735,925 input bytes and 9,836,857 distinct non-terminal nodes;
- 25,175,363 regenerated certificate edges;
- root rank 31 under a branch header bound of 31;
- zero verification errors;
- 833.402 seconds to ingest and 405.834 seconds to check obligations.

The persistent SQLite index was independently reopened read-only, contained
9,836,857 rows, returned `PRAGMA quick_check = ok`, and matched the certificate,
verifier and rules hashes stored in its metadata. Its byte hash is recorded in
the receipt; the 313 MB database itself remains in ignored `build/` storage.

This is a certificate for the branch after canonical moves `P:22,H:1:0`, not an
initial-position proof. The qcert verifier deliberately does not trust or check
that prefix. The separate `qcert-aggregate-1` verifier must regenerate the
prefix, cover all 35 replies and accept all 18 branch parts before the complete
3x9x10 upper-bound certificate can be claimed.

The 881,735,925-byte certificate itself is not stored in this repository.
Reproduction requires an external copy matching SHA-256
`961df2b3b91ba136404f5a24fd2a98c1ed886a3443ab5cfd71f4abddbaeff1d4`;
the sibling `../claude-help/work/` path in the receipt is only the path used by
the archived local run.

`H10_profile_move_differential_2026-08-01.json` records a second, narrower
check of the verifier's configuration-profile optimization against the naive
Python generator on 1,500 distinct configurations drawn from the accepted
index. It compares 10,024 legal moves, validates 1,208 actual declared moves,
rejects 3,000 invalid labels and performs 706,806 all-cell connectivity-mask
comparisons against fresh BFS, all with zero divergence. It is move-generation
assurance, not another strategy proof.
