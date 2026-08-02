#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
python3 "$ROOT/scripts/verify_root_lower_bound.py" \
  --solver "${SOLVER:-$ROOT/bin/frontier_solver}" --width 3 --height 9 --walls 10 \
  --remaining-depth 32 --seconds "${SECONDS_PER_BRANCH:-1800}" \
  --tt-bits "${TT_BITS:-26}" --jobs "${JOBS:-1}" \
  --outdir "${OUTDIR:-$ROOT/results/3x9_w10/audit/rerun_lower_bound_33}"
