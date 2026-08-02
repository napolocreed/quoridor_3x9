#!/usr/bin/env python3
# allverify.py — passe EXHAUSTIVE finale : qverify sur les 18 parts
# canoniques puis sur les 17 jumelles miroir (P(1,1) est auto-symétrique :
# 18 + 17 = 35 = toutes les réponses légales de J2 après P(7,1)).
#
# Chaque run est un DFS complet sur toutes les suites J2 : accepter les 35
# runs = preuve vérifiée indépendamment que J1 gagne 3×9×10 en <= 35 plis.
#
#   python allverify.py [--start N]

import argparse, json, os, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
QVERIFY = os.path.join(HERE, "qverify.exe")

CLASSES = [
    ("P11", "P(1,1)"), ("P00", "P(0,0)"),
    ("H00", "H(0,0)"), ("H10", "H(1,0)"), ("H20", "H(2,0)"), ("H30", "H(3,0)"),
    ("H40", "H(4,0)"), ("H50", "H(5,0)"), ("H60", "H(6,0)"), ("H70", "H(7,0)"),
    ("V00", "V(0,0)"), ("V10", "V(1,0)"), ("V20", "V(2,0)"), ("V30", "V(3,0)"),
    ("V40", "V(4,0)"), ("V50", "V(5,0)"), ("V60", "V(6,0)"), ("V70", "V(7,0)"),
]
MEMO_BITS = {"P11": 27, "P00": 27}          # classes pion : DFS bien plus large

def part_path(tag):
    root = os.path.join(HERE, "certparts-H00.bin")
    if tag == "H00" and os.path.exists(root): return root
    return os.path.join(HERE, "certparts", f"{tag}.bin")

def log(obj):
    line = json.dumps(obj, ensure_ascii=False)
    print(line, flush=True)
    with open(os.path.join(HERE, "replication", "EXHAUSTIVE.log"), "a", encoding="utf-8") as f:
        f.write(line + "\n")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, default=0)
    a = ap.parse_args()
    runs = []
    for tag, rep in CLASSES:
        runs.append((tag, rep, False))
    for tag, rep in CLASSES:
        if tag != "P11":                     # P(1,1) auto-symétrique
            runs.append((tag, rep, True))
    ok = fail = 0
    for i, (tag, rep, mir) in enumerate(runs):
        if i < a.start: continue
        cmd = [QVERIFY, "--part", part_path(tag), "--reply", rep,
               "--memo-bits", str(MEMO_BITS.get(tag, 25))]
        if mir: cmd.append("--mirror")
        t0 = time.time()
        p = subprocess.run(cmd, capture_output=True, text=True, cwd=HERE)
        out = p.stdout.strip().splitlines()[-1] if p.stdout.strip() else p.stderr.strip()
        log({"i": i, "tag": tag, "mirror": mir, "rc": p.returncode, "out": out,
             "sec": round(time.time() - t0)})
        if p.returncode == 0: ok += 1
        else: fail += 1
    log({"exhaustive": "done", "ok": ok, "fail": fail, "total": len(runs) - a.start})
    sys.exit(1 if fail else 0)

if __name__ == "__main__":
    main()
