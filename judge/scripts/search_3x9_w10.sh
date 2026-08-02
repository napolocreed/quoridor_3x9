#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$ROOT/runlogs"
/usr/bin/time -v "$ROOT/bin/frontier_solver" \
  --width 3 --height 9 --walls 10 \
  --root-index 0 --target 1 \
  --start-depth "${START_DEPTH:-32}" --max-depth "${MAX_DEPTH:-38}" \
  --seconds "${SECONDS_TOTAL:-1800}" --tt-bits "${TT_BITS:-26}" --order 1 \
  >"$ROOT/runlogs/3x9_w10_root.out" 2>"$ROOT/runlogs/3x9_w10_root.err"
