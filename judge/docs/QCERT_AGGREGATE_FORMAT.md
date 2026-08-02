# qcert-aggregate-1

`qcert-aggregate-1` composes independently verified `qcert-1` branch
certificates into one initial-position upper-bound proof. It is deliberately a
small, closed manifest. A move listing, solver branch index, search log, or
precomputed reflection table is never part of the trusted input.

The production use is the `3x9x10` Player-1 certificate: Player 1 plays `P:22`,
Player 2 has 35 legal replies in 18 horizontal-reflection orbits, and each orbit
is backed by one branch certificate of at most 33 remaining plies. The same
composition rule is usable on smaller odd-width validation boards.

## JSON object

The manifest is one UTF-8 JSON object:

```json
{
  "type": "aggregate",
  "format": "qcert-aggregate-1",
  "claim": {
    "width": 3,
    "height": 9,
    "walls": 10,
    "target": 0,
    "bound": 35,
    "root": {"p1":25,"p2":1,"r1":10,"r2":10,"turn":0,"hw":0,"vw":0},
    "witness": "P:22"
  },
  "parts": [
    {
      "id": "P00",
      "path": "parts/P00.qcert1.jsonl.gz",
      "sha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
      "bound": 33,
      "root": {"p1":22,"p2":0,"r1":10,"r2":10,"turn":0,"hw":0,"vw":0}
    }
  ],
  "replies": [
    {"move":"P:0","part":"P00","transform":"identity"},
    {"move":"P:2","part":"P00","transform":"mirror-columns"}
  ]
}
```

This fragment is illustrative and incomplete: a production manifest contains
all 18 parts and all 35 reply mappings.

Objects are closed. Their exact member sets are:

- aggregate: `type`, `format`, `claim`, `parts`, `replies`;
- claim: `width`, `height`, `walls`, `target`, `bound`, `root`, `witness`;
- part: `id`, `path`, `sha256`, `bound`, `root`;
- reply: `move`, `part`, `transform`;
- state: `p1`, `p2`, `r1`, `r2`, `turn`, `hw`, `vw`.

Missing and additional members are errors. Duplicate member names at any nesting
level are errors. Non-standard JSON values such as `NaN` are errors.

## Numeric and identifier domain

Every number is a JSON safe integer, not a Boolean or floating-point spelling.
The board domain is `width >= 2`, `height >= 3`, at most 255 cells and 1..31
wall anchors. `walls` is in `0..255`, `target` is `0` or `1`, and `bound >= 3`.
State encodings are exactly those of `qcert-1`.

Part IDs match `[A-Za-z0-9][A-Za-z0-9._-]{0,63}` and are unique. SHA-256 values
are exactly 64 lower-case hexadecimal characters. A hash covers the stored
artifact bytes, so for a gzip part it covers the compressed file, not its
decompressed JSONL stream.

Every part path is a normalized POSIX-style relative path interpreted beneath
the verifier's explicit `--artifact-root`. Absolute paths, backslashes, `.` or
`..` components, duplicate paths, aliases resolving to the same file, missing
files, non-regular files, and symlinks escaping the artifact root are rejected.
Distinct path strings that name the same inode/file identity (including hard
links) are also rejected.

## Regenerated decomposition

The verifier constructs `ReferenceGame(width, height, walls)` and requires
`claim.root` to equal its exact initial position. The root must be a
target-to-move position. It regenerates all legal root actions, selects
`claim.witness` by its canonical label, applies it, and rejects a terminal
witness or a witness that does not pass the turn to the opponent. Both the
initial root and post-witness state must be fixed by horizontal reflection;
otherwise mirroring a suffix would prove a different prefix rather than a
second reply to this one.

It then regenerates every legal opponent response. The `replies` array must map
that exact label set: no missing, extra or duplicate response is accepted.
Array order has no meaning.

For each horizontal-reflection orbit, exactly one part is used:

- its one `identity` mapping names the canonical representative (the member
  with the smaller numeric cell/anchor coordinate);
- `part.root` must equal the regenerated child of that response;
- if the child is not self-mirror, exactly one `mirror-columns` mapping must
  name the other regenerated child in its orbit;
- a self-mirror child has no mirror mapping;
- every part must be used, and IDs and paths are unique.

Horizontal reflection maps a cell `(r,c)` to `(r,width-1-c)` and an anchor
`(r,c)` to `(r,width-2-c)`. It preserves wall orientation, stocks, turn and
player identity. The verifier checks involution, winner preservation, legal
move labels and complete child-set equivariance on every aggregate root it
uses. Soundness of applying a verified branch strategy to its mirror ultimately
rests on this rule automorphism; the underlying qcert-1 verifier reports only
the identity transform.

For the published `3x9x10` claim, regeneration must produce 35 replies and 18
orbits. The canonical identity labels are exactly:

- `P:4` and `P:0`;
- `H:0:0` through `H:7:0`;
- `V:0:0` through `V:7:0`.

These are labels, not solver indices. The verifier never reads or trusts a
saved 35-move listing.

## Part verification

Each part is passed independently to
`reference/qcert_verify_sqlite.py::verify_certificate`, using a fresh temporary
SQLite database. Acceptance requires all of the following to match the
manifest, not merely `ok: true`:

- SHA-256 of the exact consumed bytes;
- branch scope, board dimensions, wall count and target;
- qcert header bound and raw root;
- a positive verified root rank no larger than the part bound;
- identity verification by the qcert-1 verifier.

The aggregate process therefore does not load a multi-gigabyte part into RAM,
and no database, report, listing, or successful status from an earlier run is
trusted.

## Bound derivation and soundness

Every part bound is in `1..claim.bound-2`, and the verifier requires

```text
claim.bound = 2 + max(part.bound)
```

The two added plies are the checked target witness and the checked opponent
reply. For an identity mapping, the accepted qcert-1 proves the corresponding
branch. For a mirror mapping, horizontal-reflection equivariance transports the
same strategy and rank bound to the mirrored branch. Exact regenerated response
coverage supplies the universal step at the opponent node; the declared
witness supplies the existential step at the initial target node. Thus the
aggregate proves `Win(initial, target, claim.bound)`.

This is an upper-bound certificate. It does not establish that 35 is minimal;
the independent negative audit through ply 33 remains necessary for that
claim.

## Reference command

```text
python3 reference/qcert_aggregate_verify.py aggregate.json \
  --artifact-root /absolute/path/to/bundle
```

Exit code `0` means accepted, `1` means invalid proof data, and `2` means an
operational, usage, interruption or internal failure. Stdout is one JSON result;
progress is written to stderr. The successful report explicitly states whether
the exact published `3x9x10` profile matched, the regenerated reply/orbit counts,
the derived bound, and that mirror acceptance is based on the rule
automorphism. It also reports the SHA-256 and byte count of the exact manifest
bytes decoded and parsed by that run; semantically equivalent JSON with
different whitespace is therefore a different, visibly bound artifact. The
report additionally binds the aggregate-verifier, qcert-verifier and Python
rules-engine source hashes. Every accepted part must report the same qcert and
rules hashes before it can contribute to the composition.
