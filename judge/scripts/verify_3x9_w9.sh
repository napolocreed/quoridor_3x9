#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$ROOT/runlogs"
/usr/bin/time -v "$ROOT/bin/frontier_solver" \
  --width 3 --height 9 --walls 9 \
  --root-index 0 --target 1 \
  --parallel-second --jobs "${JOBS:-3}" --child-depth 33 \
  --seconds "${SECONDS_PER_BRANCH:-900}" --tt-bits "${TT_BITS:-24}" --order 1 \
  >"$ROOT/runlogs/3x9_w9_verify.out" 2>"$ROOT/runlogs/3x9_w9_verify.err"
grep -Eq '^parallel_result proven=1 .*stalemates_seen=0 ' "$ROOT/runlogs/3x9_w9_verify.out"
