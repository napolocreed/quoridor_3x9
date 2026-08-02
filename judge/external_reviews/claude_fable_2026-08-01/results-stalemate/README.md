# Clean-room stalemate artifacts

These files were authored by the independent Claude Fable review on
2026-08-01 and imported from the sibling `claude-help` worktree. The theorem,
scanner, and selected compact result files are preserved verbatim. In
particular, no game-rule or search logic was changed during integration.

Editorial scope note: the imported theorem sometimes calls the path-only
domain "exactly" the C++ exhaustive domain. The C++ enumeration additionally
requires geometric wall legality and historically consistent stocks, so it is
a subset of the theorem's path-legal domain. This wording does not weaken the
theorem or its application to the 63,184 enumerated states; the hashed external
artifact is left unchanged.

`../qscan.mjs` imports `../qref.mjs`, the reviewer's clean-room rules engine
already archived in this directory. The relative import required no adaptation.
The `doc` mode name in those external programs denotes the former
empty-conjunction reading discussed in `../STALEMATE_THEOREM.md`; the
repository's current proof semantics explicitly returns false at a
non-terminal state with no legal child.

## Representative regression commands

Run from `external_reviews/claude_fable_2026-08-01/`:

```bash
node qscan.mjs scan 3 2 1
node qscan.mjs scan 3 3 1
node qscan.mjs scan-legal 4 3 3
node qscan.mjs diff-states 3 2 1 12
```

The substantive expected values are respectively:

- 142 reachable states, five full stalemates, first at ply 2;
- 2,856 reachable states, no invariant violation and no pawn-move-less state;
- 63,184 path-legal non-terminal states and no pawn-move-less state;
- 172 bounded queries and seven verdict differences between the two
  height-2 stalemate conventions.

Runtime fields are informational and may vary.

From the repository root, `make external-stalemate-smoke` parses all four
outputs and rejects any substantive value that differs from this table.

## Imported SHA-256 hashes

| File | SHA-256 |
| --- | --- |
| `../qref.mjs` | `146e60808c83d45c46ca052fffab320956e0111f9f2eb97e5b759ec8dab551b1` |
| `../qscan.mjs` | `0a9116a63d9898a46a852c6a55aee3b6f7edb705ef7e9f17c488aae4dce667e0` |
| `../STALEMATE_THEOREM.md` | `ab8e1de7277984b2ab4c5db02c3b3ec0b5065dc6810c6e0ce2041b81fea575f8` |
| `scan_h2.jsonl` | `9abc63a71bd11e01d2b0169565216b49f5b59f734a2126f48db66193c2323557` |
| `scan_h3_small.jsonl` | `b7e6feefe2495bf2abfc223d8e0a51568cdd54dc321b53f98642a91d64b60d56` |
| `scan_legal.jsonl` | `e5fbb976d65c39256d0e3dec0df41efb9d7c7e37fca6a3d6f707f033177ca752` |
| `diff_states_3x2x1.json` | `634ea92b575cc4b3a98d65b04425fde897997e8a9fa89081f6f7e954fabb2fc3` |
