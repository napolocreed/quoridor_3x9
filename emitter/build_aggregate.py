#!/usr/bin/env python3
# build_aggregate.py — construit aggregate/aggregate.json au format
# qcert-aggregate-1 (spec sol : quoridor-frontier-research/docs/
# QCERT_AGGREGATE_FORMAT.md) depuis le registre aggregate/EXPORTS.jsonl
# produit par export_all.py.
#
# Objets fermés, chemins relatifs POSIX, SHA-256 des octets stockés (.gz),
# une liaison identity par part + mirror-columns sauf P:4 auto-miroir,
# borne du claim = 2 + max(borne de part) = 35.

import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
AGG = os.path.join(HERE, "aggregate")
LEDGER = os.path.join(AGG, "EXPORTS.jsonl")
OUT = os.path.join(AGG, "aggregate.json")

# tag -> (label identité canonique, label miroir ou None si auto-miroir)
# réflexion horizontale : cellule (r,c) -> (r, 2-c), ancre (r,c) -> (r, 1-c)
REPLIES = {"P11": ("P:4", None), "P00": ("P:0", "P:2")}
for r in range(8):
    REPLIES[f"H{r}0"] = (f"H:{r}:0", f"H:{r}:1")
    REPLIES[f"V{r}0"] = (f"V:{r}:0", f"V:{r}:1")

def main():
    recs = {}
    with open(LEDGER, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                r = json.loads(line)
                recs[r["tag"]] = r
    missing = sorted(set(REPLIES) - set(recs))
    if missing:
        sys.exit(f"parts manquantes dans le registre : {missing}")

    parts, replies = [], []
    for tag in sorted(REPLIES):
        r = recs[tag]
        if not (1 <= r["bound"] <= 33):
            sys.exit(f"{tag} : borne {r['bound']} hors 1..33")
        parts.append({
            "id": tag,
            "path": r["path"],
            "sha256": r["sha256_gz"],
            "bound": r["bound"],
            "root": r["root"],
        })
        ident, mirror = REPLIES[tag]
        replies.append({"move": ident, "part": tag, "transform": "identity"})
        if mirror is not None:
            replies.append({"move": mirror, "part": tag, "transform": "mirror-columns"})

    bound = 2 + max(p["bound"] for p in parts)
    if bound != 35:
        sys.exit(f"borne dérivée {bound} != 35")
    if len(replies) != 35:
        sys.exit(f"{len(replies)} replies != 35")

    manifest = {
        "type": "aggregate",
        "format": "qcert-aggregate-1",
        "claim": {
            "width": 3, "height": 9, "walls": 10, "target": 0,
            "bound": bound,
            "root": {"p1": 25, "p2": 1, "r1": 10, "r2": 10,
                     "turn": 0, "hw": 0, "vw": 0},
            "witness": "P:22",
        },
        "parts": parts,
        "replies": replies,
    }
    tmp = OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(manifest, f, ensure_ascii=True, indent=1)
        f.write("\n")
    os.replace(tmp, OUT)
    print(json.dumps({"out": OUT, "parts": len(parts), "replies": len(replies),
                      "bound": bound}))

if __name__ == "__main__":
    main()
