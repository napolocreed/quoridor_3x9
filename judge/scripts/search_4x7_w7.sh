#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUTDIR="${OUTDIR:-$ROOT/runlogs/4x7_w7}"
mkdir -p "$OUTDIR"

TARGET="${TARGET:-1}"
START_DEPTH="${START_DEPTH:-1}"
MAX_DEPTH="${MAX_DEPTH:-45}"
SECONDS_TOTAL="${SECONDS_TOTAL:-900}"
TT_BITS="${TT_BITS:-25}"
STAMP="${STAMP:-target${TARGET}_d${START_DEPTH}_tt${TT_BITS}}"

set +e
/usr/bin/time -v "$ROOT/bin/frontier_solver" \
  --width 4 --height 7 --walls 7 \
  --target "$TARGET" \
  --start-depth "$START_DEPTH" --max-depth "$MAX_DEPTH" \
  --seconds "$SECONDS_TOTAL" --tt-bits "$TT_BITS" --order 1 \
  --no-bounds --no-pawn-table \
  >"$OUTDIR/${STAMP}.out.tmp" 2>"$OUTDIR/${STAMP}.err.tmp"
rc=$?
set -e
mv "$OUTDIR/${STAMP}.out.tmp" "$OUTDIR/${STAMP}.out"
mv "$OUTDIR/${STAMP}.err.tmp" "$OUTDIR/${STAMP}.err"
printf '%s\n' "$rc" > "$OUTDIR/${STAMP}.rc"
