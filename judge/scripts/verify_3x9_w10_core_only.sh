#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
python3 "$ROOT/scripts/verify_replies.py" \
  --solver "$ROOT/bin/frontier_solver" \
  --width 3 --height 9 --walls 10 \
  --root-index 0 --target 1 \
  --start-depth 31 --max-depth 35 \
  --seconds "${SECONDS_PER_BRANCH:-1800}" \
  --tt-bits "${TT_BITS:-26}" --order 1 \
  --no-bounds --no-pawn-table \
  --jobs "${JOBS:-1}" \
  --outdir "${OUTDIR:-$ROOT/results/3x9_w10/audit/rerun_core_only}"
