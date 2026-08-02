#!/usr/bin/env python3
# orchestrate9.py — réplication 3×9 à 9 murs (2e case de la table Slatton).
#
# Borne supérieure seulement : témoin P(7,1), 18 classes de réponses J2,
# preuve de branche par classe (start-depth 31, max 33). La table publique
# ne stocke que le vainqueur ; « proved=true » partout suffit.
#
#   python orchestrate9.py [--workers 2]

import argparse, json, os, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
QSOLVE = os.path.join(HERE, "qsolve.exe")

CLASSES = [
    ("P11", "P(1,1)"), ("P00", "P(0,0)"),
    ("H00", "H(0,0)"), ("H10", "H(1,0)"), ("H20", "H(2,0)"), ("H30", "H(3,0)"),
    ("H40", "H(4,0)"), ("H50", "H(5,0)"), ("H60", "H(6,0)"), ("H70", "H(7,0)"),
    ("V00", "V(0,0)"), ("V10", "V(1,0)"), ("V20", "V(2,0)"), ("V30", "V(3,0)"),
    ("V40", "V(4,0)"), ("V50", "V(5,0)"), ("V60", "V(6,0)"), ("V70", "V(7,0)"),
]

LOCK = __import__("threading").Lock()
def log(obj):
    line = json.dumps(obj, ensure_ascii=False)
    with LOCK:
        print(line, flush=True)
        with open(os.path.join(HERE, "replication9", "PIPELINE9.log"), "a", encoding="utf-8") as f:
            f.write(line + "\n")

def do_class(args):
    tag, rep = args
    out_json = os.path.join(HERE, "replication9", f"upper9_{tag}.json")
    if os.path.exists(out_json):
        log({"tag": tag, "skipped": True}); return None
    tt = os.path.join(HERE, "work", f"tt9_{tag}.bin")
    t0 = time.time()
    p = subprocess.run([QSOLVE, "--walls", "9", "--mode", "branch",
                        "--first", "P(7,1)", "--second", rep, "--target", "1",
                        "--start-depth", "31", "--max-depth", "33",
                        "--tt-bits", "25", "--cache-bits", "22", "--tt-file", tt],
                       capture_output=True, text=True, cwd=HERE)
    el = time.time() - t0
    outline = p.stdout.strip().splitlines()[-1] if p.stdout.strip() else ""
    ok = False
    try:
        j = json.loads(outline)
        ok = (j.get("proved") is True and j.get("timeout") is False)
        if ok:
            with open(out_json, "w", encoding="utf-8") as f: f.write(outline + "\n")
    except json.JSONDecodeError:
        pass
    log({"tag": tag, "proved": ok, "rc": p.returncode, "out": outline, "sec": round(el)})
    return None if ok else f"{tag}: non prouvé (rc={p.returncode})"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=2)
    a = ap.parse_args()
    os.makedirs(os.path.join(HERE, "replication9"), exist_ok=True)
    os.makedirs(os.path.join(HERE, "work"), exist_ok=True)
    log({"w9": "start", "classes": len(CLASSES), "workers": a.workers})
    errors = []
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        for e in ex.map(do_class, CLASSES):
            if e: errors.append(e)
    log({"w9": "done", "errors": errors})
    sys.exit(1 if errors else 0)

if __name__ == "__main__":
    main()
