# Reproducibility

## Fast checks

```bash
make -j2
make test
```

The full local test can use roughly 1 GiB because the `3×9` move-generation checks precompute 2,929,319 wall configurations.

## Conservative `3×9×10` upper bound

```bash
JOBS=1 \
SECONDS_PER_BRANCH=1800 \
TT_BITS=26 \
scripts/verify_3x9_w10_core_only.sh
```

Expected archived summary:

```json
{
  "all_proved": true,
  "forced_win_upper_bound_plies_from_start": 35,
  "no_bounds": true,
  "no_pawn_table": true
}
```

New results are written atomically under
`results/3x9_w10/audit/rerun_core_only/` by default. Set `OUTDIR` to another
fresh directory for a distinct solver or command. The harness refuses to
overwrite a completed record that fails the current audit checks or any record
from another solver/command; it skips a matching completion only when its raw
counter is present and zero. Cache reuse also rereads the adjacent `.out` and
`.err` sidecars and requires byte-for-byte agreement with the copies embedded
in the JSON record; editing only one representation invalidates the cache.

Before launching any branch, the harness asks the exact binary to enumerate the
35 replies, verifies their move labels and the horizontal-reflection partition
into the expected 18 classes, and stores a hash-bound `reply_partition.json`.
Each branch cache is tied to its representative move and aliases. The historical
indices are therefore never reused without first proving what they name for the
current solver hash.

The archived 2026-07 proof binary predates `stalemates_seen`, so the immutable
records above truthfully leave the counter unrecorded. New binaries and harnesses
accept a branch as proved only when `stalemates_seen` is present and zero. The
height-at-least-3 theorem closes the semantic ambiguity and independent scans
add evidence, but neither retroactively supplies the missing runtime tripwire;
the historical field remains explicitly unrecorded rather than rewritten as
zero.

Treat that archived directory as immutable. A current harness deliberately does
not reuse a branch whose raw output lacks the counter; place new runs in a fresh
`OUTDIR` instead of overwriting the 2026-07 evidence. To summarize an untouched
historical copy explicitly, use:

```bash
python3 scripts/summarize_branch_audit.py \
  results/3x9_w10/audit/core_only \
  --counter-policy historical-missing \
  --output /tmp/core-only-historical-summary.json
```

The default `required` policy is for new audits and rejects a missing field.
Neither policy accepts a non-zero or malformed counter.

The exact executable and source are preserved at:

```text
results/3x9_w10/audit/core_only/solver
results/3x9_w10/audit/core_only/solver.cpp
SHA256 ff11c2530a15c534922d4348f7cf0d9e66366f7742951fb38e8550a375e5837c
```

## Exact lower bound through ply 33

```bash
JOBS=1 \
SECONDS_PER_BRANCH=1800 \
TT_BITS=26 \
scripts/verify_3x9_w10_lower_bound.sh
```

Expected archived summary:

```json
{
  "all_refuted": true,
  "first_player_not_forced_within_plies_from_start": 33,
  "no_bounds": true,
  "no_pawn_table": true
}
```

New results are written atomically under
`results/3x9_w10/audit/rerun_lower_bound_33/` by default. The archived
`lower_bound_33/` directory remains immutable and is still the source used by
the final manifest.

The same historical-counter note applies. A new lower-bound record is accepted
as refuted only when its counter is present and zero.

This harness performs the analogous named 35-to-18 preflight on the initial
move list and binds every root cache to `root_partition.json`.

## Final manifest

```bash
python3 scripts/build_final_manifest.py --walls 10
```

This writes `results/3x9_w10/final_result.json` from the archived audit records and exact solver hashes.

After both current reruns finish, build a separate manifest from their raw
records, named partitions and current binary without modifying the archived
claim:

```bash
python3 scripts/build_final_manifest.py --walls 10 \
  --upper-dir results/3x9_w10/audit/rerun_core_only \
  --lower-dir results/3x9_w10/audit/rerun_lower_bound_33 \
  --solver bin/frontier_solver \
  --source src/frontier_solver.cpp \
  --output results/3x9_w10/rerun_final_result.json
```

The builder rereads all 36 branch JSON records **and** their raw `.out`/`.err`
files. It reparses the solver result lines, verifies the exact named move lists
and each invocation's `forcing root/second` line, requires the 35-to-18
partitions and zero counters for a current rerun, and recomputes both aggregate
node totals before emitting the 35-ply claim. The resulting manifest inventories
and SHA-256-binds every consumed summary, branch JSON, raw stdout and raw stderr,
so a later edit to any input cannot silently retain the same evidence bundle.
The immutable historical run is
accepted only under its exact solver-hash whitelist; its absent counter remains
reported as `not_recorded`, never rewritten as zero.

## Disk-backed qcert verification

Use the independent Python verifier when a `qcert-1` part is too large for the
in-memory JavaScript index:

```bash
python3 reference/qcert_verify_sqlite.py part.jsonl.gz \
  --database /path/with/free-space/part.sqlite3 \
  --progress-every 250000 > part.verify.json
```

Input is streamed as plain JSONL or a single gzip member (detected from the file
bytes); trailing data and concatenated members are rejected. Pass 1 rejects
duplicate JSON member names, unsafe or boolean integers, record-local state
errors, stock non-conservation and duplicate raw states while building a unique
SQLite index. The ordered second pass checks configuration-local wall geometry
and both goal paths, independently regenerates the declared target move or every
opponent reply with `reference/quoridor_reference.py`, checks strict rank
decrease or an immediate target terminal, and verifies the root rank, bound and
claim scope.

Pass 2 orders the SQLite scan by wall masks and builds one exact connectivity
profile per configuration. Candidate wall additions are reduced to two goal-row
connectivity masks, so each state needs bit tests rather than fresh path searches.
The JSON result exposes `configProfiles`, `wallCandidateProfiles`,
`profileWallCandidates` and `wallCandidatesChecked` for performance auditing.
It also records SHA-256 hashes of both the verifier and
`reference/quoridor_reference.py`, so an archived exit-0 result binds the exact
checking code as well as the certificate artifact.

Exit code `0` means accepted, `1` means a well-read but invalid certificate and
`2` means invocation, I/O, interruption or SQLite failure. Stdout is one JSON
object in all three cases; progress, when requested, goes to stderr. The SHA-256
and byte count refer to the exact input artifact, including gzip compression.
An explicit database is never overwritten. Omitting `--database` creates and
removes a safe temporary database; `--temp-dir` can choose its parent volume.
Plan disk capacity before a production bundle: the observed H10 index was
313,151,488 bytes for an 881,735,925-byte certificate (about 35.5%), and SQLite
still needs transient WAL/headroom. The aggregate verifier removes each
temporary index after its part, but all certificate artifacts must coexist; use
`--temp-dir` on another volume when the bundle and working extraction caches
approach the free space of the artifact volume.

The small `3x3x0` fixture and its corruption suite remain the fast regression.
The first archived production run is now the `H(1,0)` branch: 881,735,925 input
bytes, 9,836,857 indexed nodes, 25,175,363 checked edges, root rank/bound 31 and
zero errors. Its portable receipt is
`results/validation/qcert/H10_sqlite_verification_2026-08-01.json`; the ignored
313 MB SQLite database was reopened read-only and passed `PRAGMA quick_check`.
The 881,735,925-byte `H10.qcert1.jsonl` artifact is not stored in this
repository. Reproducing the run requires an external copy matching SHA-256
`961df2b3b91ba136404f5a24fd2a98c1ed886a3443ab5cfd71f4abddbaeff1d4`;
the `../claude-help/work/` path in the receipt records only the local location
used for this run. The profile-specific differential receipt is
`results/validation/qcert/H10_profile_move_differential_2026-08-01.json`.
This validates that branch only. Do not describe the initial position as
certificate-verified until every aggregate part has its own accepted report and
`qcert-aggregate-1` accepts their regenerated 35-response composition.

## Reading the coordinates

- cells use `(row,column)`, zero-indexed from the top-left;
- Player 1 starts at `(8,1)` and aims for row 0;
- `P(7,1)` is the central opening advance;
- `H(r,c)` and `V(r,c)` are wall anchors.

## External replication checklist

A strong independent reproduction should vary at least one of:

- rules implementation;
- wall-configuration enumeration;
- symmetry code;
- transposition representation;
- proof-search implementation.

Recompiling the same source on another machine is useful operational validation, but not algorithmic independence. Computers are perfectly capable of repeating the same mistake at impressive speed.

## `4×7×7` central opening through ply 27

```bash
make -j2
SECONDS_PER_BRANCH=300 \
TT_BITS=27 \
scripts/verify_4x7_w7_central_depth27.sh
```

The harness fixes `P(5,2) P(1,2)`, enumerates the 40 legal Player-1 third moves, and asks whether each resulting state permits a Player-1 win within the remaining 24 plies. Each branch receives a fresh transposition table. Completed branch JSON files are written atomically and reused after interruption.

Expected summary fields:

```json
{
  "all_third_moves_refuted": true,
  "first_player_opening_not_forced_within_plies": 27,
  "third_moves": 40,
  "refuted": 40,
  "no_bounds": true,
  "no_pawn_table": true
}
```

Every one of the 40 branch records must contain `stalemates_seen: 0`, and the
summary must report `aggregate_stalemates_seen: 0`.

This proves that the specified Player-2 reply refutes the central opening at the 27-ply horizon. It does not by itself refute every legal Player-1 opening.
