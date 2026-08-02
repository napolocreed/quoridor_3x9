#!/usr/bin/env python3
"""Reproduce the compact clean-room stalemate regression values."""
from __future__ import annotations

import json
import hashlib
import subprocess
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REVIEW = ROOT / "external_reviews" / "claude_fable_2026-08-01"
EXPECTED_HASHES = {
    "qref.mjs": "146e60808c83d45c46ca052fffab320956e0111f9f2eb97e5b759ec8dab551b1",
    "qscan.mjs": "0a9116a63d9898a46a852c6a55aee3b6f7edb705ef7e9f17c488aae4dce667e0",
    "STALEMATE_THEOREM.md": "ab8e1de7277984b2ab4c5db02c3b3ec0b5065dc6810c6e0ce2041b81fea575f8",
    "results-stalemate/scan_h2.jsonl": "9abc63a71bd11e01d2b0169565216b49f5b59f734a2126f48db66193c2323557",
    "results-stalemate/scan_h3_small.jsonl": "b7e6feefe2495bf2abfc223d8e0a51568cdd54dc321b53f98642a91d64b60d56",
    "results-stalemate/scan_legal.jsonl": "e5fbb976d65c39256d0e3dec0df41efb9d7c7e37fca6a3d6f707f033177ca752",
    "results-stalemate/diff_states_3x2x1.json": "634ea92b575cc4b3a98d65b04425fde897997e8a9fa89081f6f7e954fabb2fc3",
}


def verify_hashes() -> None:
    for relative, expected in EXPECTED_HASHES.items():
        path = REVIEW / relative
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected:
            raise AssertionError(f"external artifact hash mismatch for {relative}: {actual}")


def run(arguments: list[str], expected: dict[str, Any]) -> dict[str, Any]:
    completed = subprocess.run(
        ["node", "qscan.mjs", *arguments],
        cwd=REVIEW,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise AssertionError(
            f"qscan {' '.join(arguments)} failed with {completed.returncode}: "
            f"{completed.stderr.strip()}"
        )
    lines = [line for line in completed.stdout.splitlines() if line.strip()]
    if len(lines) != 1:
        raise AssertionError(f"qscan {' '.join(arguments)} emitted {len(lines)} result lines")
    result = json.loads(lines[0])
    mismatches = {
        key: {"expected": value, "actual": result.get(key)}
        for key, value in expected.items()
        if result.get(key) != value
    }
    if mismatches:
        raise AssertionError(f"qscan {' '.join(arguments)} mismatch: {mismatches}")
    return result


def main() -> int:
    verify_hashes()
    cases = [
        run(["scan", "3", "2", "1"], {
            "reachableStates": 142,
            "invariantViolations": 0,
            "fullStalemates": 5,
            "firstStalematePly": 2,
        }),
        run(["scan", "3", "3", "1"], {
            "reachableStates": 2856,
            "invariantViolations": 0,
            "zeroPawnMoveNonTerminal": 0,
            "fullStalemates": 0,
        }),
        run(["scan-legal", "4", "3", "3"], {
            "legalConfigs": 301,
            "legalNonTerminalStates": 63184,
            "zeroPawnMoveStates": 0,
        }),
        run(["diff-states", "3", "2", "1", "12"], {
            "reachableStates": 142,
            "queriesChecked": 172,
            "divergingVerdicts": 7,
        }),
    ]
    print(json.dumps({
        "status": "ok",
        "clean_room_files_verified": len(EXPECTED_HASHES),
        "clean_room_stalemate_cases": len(cases),
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
