#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
python3 "$ROOT/scripts/verify_4x7_w7_central_depth27.py" \
  --solver "${SOLVER:-$ROOT/bin/frontier_solver}" \
  --outdir "${OUTDIR:-$ROOT/results/4x7_w7/audit_central_depth27}" \
  --seconds-per-branch "${SECONDS_PER_BRANCH:-300}" \
  --tt-bits "${TT_BITS:-27}" \
  --chunk-size "${CHUNK_SIZE:-5}"
