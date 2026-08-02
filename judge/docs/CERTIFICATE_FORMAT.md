# qcert-1 strategy certificate

This format turns a bounded positive search result into a strategy DAG that an
independent rules engine can check without repeating the search. It is based on
Claude Fable's clean-room certificate proposal, with two hardenings made during
integration: all promised state-legality checks are normative, and node budgets
are ranks rather than claims of per-state optimality.

## Claim

A certificate proves `Win(root, target, bound)` under
`docs/PROOF_SEMANTICS.md`. It proves an upper bound only. Establishing that 35
plies is minimal still requires the independent negative audit through ply 33.

## Supported numeric domain

In `qcert-1`:

- `width`, `height`, `walls`, `bound`, state fields and node budgets are JSON
  safe integers (absolute value at most `2^53 - 1`, so adjacent ranks remain
  distinguishable under `d - 1`) encoded with JSON's integer lexical grammar;
  decimal-point and exponent spellings such as `3.0` and `3e0` are forbidden
  even when a generic JSON parser would produce an integral numeric value;
- players and `turn` use zero-based values: Player 1 is `0`, Player 2 is `1`;
- cells use `row * width + column`;
- an anchor uses bit `row * (width - 1) + column` in separate `hw` and `vw`
  masks;
- the reference JavaScript verifier supports at most 31 anchors, because its
  clean-room engine deliberately uses 32-bit bitwise operations.
- the same verifier requires `width,height >= 2`, `width * height <= 255`, and
  `0 <= walls <= 255`.

Every JSON object must contain each member name at most once. This is normative
even though JavaScript's built-in `JSON.parse` keeps the last occurrence; it
prevents independent parsers from assigning different meanings to one file.
Unknown extension members are currently permitted and ignored. Their presence
does not alter the claim, state key, rank or move obligation; future closed
schemas require a new format identifier rather than silently changing qcert-1.

The current research boards have 16 anchors (`3x9`) or 18 anchors (`4x7`) and
are inside this domain.

## JSONL syntax

The byte encoding is strict UTF-8 without a byte-order mark. Invalid UTF-8 is
rejected rather than replaced. The reference verifiers accept LF, CRLF and
legacy CR record separators; this is the shared universal-newline domain, not
permission for raw control characters inside a JSON record.

The first non-empty line is the only header:

```json
{"type":"header","format":"qcert-1","width":3,"height":9,"walls":10,"target":0,"bound":35,"root":{"p1":25,"p2":1,"r1":10,"r2":10,"turn":0,"hw":0,"vw":0}}
```

Every later line is one distinct non-terminal state:

```json
{"type":"node","p1":25,"p2":1,"r1":10,"r2":10,"turn":0,"hw":0,"vw":0,"d":35,"move":"P:22"}
{"type":"node","p1":22,"p2":1,"r1":10,"r2":10,"turn":1,"hw":0,"vw":0,"d":34}
```

`move` is required exactly when `turn == target`. Labels are `P:cell`,
`H:row:column`, or `V:row:column`. A raw state appears at most once. Cache-local
configuration IDs and symmetry-canonical keys never appear.

## State legality

The verifier rejects a node unless:

- both pawn cells and `turn` are in range and the pawns are distinct;
- both stocks are integers in `0..walls`;
- masks are non-negative integers with no bit outside the anchor grid;
- existing walls neither cross nor overlap;
- both pawns retain a wall-graph path to their own goal row;
- `r1 + r2 + popcount(hw) + popcount(vw) == 2 * walls`;
- the state is non-terminal and `d >= 1`.

Reachability from the initial position is not required. This deliberately allows
certificates rooted at named decomposed branches, while path and structural
legality prevent an arbitrary malformed root from becoming an axiom.

## Local verification

After indexing all nodes by raw state, the verifier checks:

1. the header root is indexed with `d <= bound`;
2. at a target node, the declared move is legal and its child is either an
   immediate target win or an indexed node with `d(child) <= d(parent) - 1`;
3. at an opponent node, the regenerated legal-move set is non-empty and every
   child satisfies the same terminal-or-indexed condition;
4. no indexed state is terminal or duplicated.

The verifier reports `scope: initial-position` or `scope: branch-position` and
includes the raw root in its claim. A branch certificate is valid, but it is
never silently presented as a root certificate. The certificate alone does not
prove that a stated move prefix reaches an arbitrary branch root.

For a branch certificate, `bound` is measured from that branch root. Prefix
plies are not subtracted by the emitter and must not be silently folded into the
claim. Any aggregate that reconstructs an initial-position bound must verify the
prefix moves, cover every opponent reply (including reflected classes), bind
each part by hash and add the prefix length explicitly. The closed composition
format and independent verifier are specified in
[`QCERT_AGGREGATE_FORMAT.md`](QCERT_AGGREGATE_FORMAT.md).

## Why acceptance is sound

Use strong induction on `d`. At a target node, one legal declared move reaches a
target terminal or a smaller accepted rank. At an opponent node, every legal
move does. Thus the existential or universal recurrence holds. Strict rank
decrease makes a cycle impossible and forces a target terminal within the header
bound. The check trusts only the independent move generator, terminal test,
state-legality checks and integer comparisons.

## Emission policies

The field `d` is a certified remaining budget and ranking function. It need not
equal the minimum forcing depth `dmin(state)`; minimality is neither necessary
for the proof above nor verifiable without search.

Two emitter policies are useful:

- `rank` (production): start from the known root bound, propagate `parent - 1`,
  and re-expand a state whenever a second incoming edge lowers its rank. At
  convergence every stored edge satisfies the local inequality. Each rank can
  decrease only finitely many times.
- `exact-dmin` (small-board validation): find the first true relevant-parity
  bounded query for every indexed state. This produces a canonical tight rank
  but may require many negative searches and is not the production requirement.

At target nodes the emitter must regenerate moves and ask the proof oracle which
child is winning; it must not serialize a TT hint. At opponent nodes it must
cover every regenerated child.

## Atomicity and scale

An emitter writes a sibling partial file, flushes and closes it, then installs it
atomically without overwriting an existing certificate. Interrupted files are
never valid certificates. The production handoff is not complete until an
orchestration wrapper records the emitter binary hash, command, node/edge counts,
raw file hash and independent verifier result; the prototype emitter does not
yet create that summary.

The in-memory JavaScript verifier is intended for early certificates.
`reference/qcert_verify_sqlite.py` is the disk-backed verifier for larger
artifacts. It streams plain or gzip JSONL into a SQLite table whose raw-state
columns form a unique primary key, then performs a second pass that regenerates
all legal obligations with `reference/quoridor_reference.py` and resolves their
children through that table. Its memory use is therefore independent of the
number of certificate nodes, apart from SQLite's bounded page cache.

The second pass scans the primary key in `(hw,vw,...)` order. Once per wall
configuration it computes the components connected to each goal row after every
geometrically possible wall addition. Wall legality at a concrete state then
reduces exactly to two pawn-membership bit tests. Opponent nodes still enumerate
every pawn and wall action; target nodes validate only their one declared action,
which is the complete existential obligation. The optimized generator agrees
with `ReferenceGame.legal_moves` on all 2,078 reachable non-terminal `3x3x1`
states and its declared-move path on all 6,910 legal moves there, plus 300
deterministic `3x9x10` samples exercising the production board dimensions.

Gzip input must contain exactly one member and no trailing bytes; concatenated
members are rejected even when their decompressed concatenation would be valid
JSONL. By default the SQLite database lives in a safely created temporary
directory and is removed at exit. `--database PATH` preserves it for inspection
and refuses to run if the database or a SQLite sidecar already exists.

For an accepted file, the reported SHA-256 and byte count are accumulated by the
same physical stream that feeds JSON parsing (the compressed bytes for gzip),
while `verifierSha256` and `rulesSha256` bind the two Python sources trusted by
the run. The claim reports the raw root, root rank, bound and initial/branch
scope. In verifier reports, `claim.winner` is a one-based display field (`1`
means Player 1); qcert headers and state fields remain zero-based (`target: 0`
means Player 1). This implementation has passed the small external fixture and adversarial
corruption suite. On 2026-08-01 it also accepted the real `H(1,0)` production
branch: 9,836,857 nodes and 25,175,363 regenerated edges with root rank 31 and
zero errors. The hash-bound receipt is
`results/validation/qcert/H10_sqlite_verification_2026-08-01.json`. This is one
branch certificate, not the complete 18-part initial-position aggregate.

A separate deterministic differential samples 1,500 distinct wall
configurations directly from that accepted SQLite index. It finds exact
agreement with the naive reference generator on 10,024 moves, validates 1,208
real declared target moves and rejects 3,000 invalid labels. It additionally
checks every one of the 27 cells against a fresh goal-path BFS for each sampled
base configuration and 11,589 candidate wall additions: 706,806 connectivity
mask comparisons with no divergence. This tests the profile optimization only;
it performs no proof search and does not broaden the branch claim.
