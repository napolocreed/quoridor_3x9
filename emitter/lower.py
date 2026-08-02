#!/usr/bin/env python3
# lower.py — réplication de la borne inférieure : « exactement 35 plis ».
#
# Pour chacune des 18 classes de premier coup de J1 (qsolve --mode list),
# on fixe ce coup et on demande si J1 force encore un gain dans les 32 plis
# restants (gain total <= 33). Attendu PARTOUT : proved=false, timeout=false.
# J1 ne conclut que sur un pli impair, donc exclure 33 exclut aussi 34 ;
# avec la borne supérieure 35 (certificats), l'horizon exact est 35.
#
#   python lower.py [--workers 3]

import argparse, json, os, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
QSOLVE = os.path.join(HERE, "qsolve.exe")

ROOTS = ["P(7,1)", "H(0,0)", "H(1,0)", "H(2,0)", "H(3,0)", "H(4,0)", "H(5,0)",
         "H(6,0)", "H(7,0)", "P(8,0)", "V(0,0)", "V(1,0)", "V(2,0)", "V(3,0)",
         "V(4,0)", "V(5,0)", "V(6,0)", "V(7,0)"]

def tag(rep):
    return rep.replace("(", "").replace(")", "").replace(",", "")

LOCK = __import__("threading").Lock()
def log(obj):
    line = json.dumps(obj, ensure_ascii=False)
    with LOCK:
        print(line, flush=True)
        with open(os.path.join(HERE, "replication", "LOWER.log"), "a", encoding="utf-8") as f:
            f.write(line + "\n")

def do_root(rep):
    t = tag(rep)
    out_json = os.path.join(HERE, "replication", f"lower_{t}.json")
    if os.path.exists(out_json):
        log({"root": rep, "skipped": True}); return None
    tt = os.path.join(HERE, "work", f"ttlow_{t}.bin")
    t0 = time.time()
    p = subprocess.run([QSOLVE, "--mode", "branch", "--first", rep, "--target", "1",
                        "--start-depth", "32", "--max-depth", "32",
                        "--tt-bits", "25", "--cache-bits", "22", "--tt-file", tt],
                       capture_output=True, text=True, cwd=HERE)
    el = time.time() - t0
    outline = p.stdout.strip().splitlines()[-1] if p.stdout.strip() else ""
    ok = False
    try:
        j = json.loads(outline)
        # attendu : réfutation propre (proved=false sans timeout) -> rc 1
        ok = (j.get("proved") is False and j.get("timeout") is False)
        if ok:
            with open(out_json, "w", encoding="utf-8") as f: f.write(outline + "\n")
    except json.JSONDecodeError:
        pass
    log({"root": rep, "refuted": ok, "rc": p.returncode, "out": outline, "sec": round(el)})
    return None if ok else f"{rep}: non réfuté (rc={p.returncode})"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=3)
    a = ap.parse_args()
    os.makedirs(os.path.join(HERE, "replication"), exist_ok=True)
    os.makedirs(os.path.join(HERE, "work"), exist_ok=True)
    log({"lower": "start", "roots": len(ROOTS), "workers": a.workers})
    errors = []
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        for e in ex.map(do_root, ROOTS):
            if e: errors.append(e)
    log({"lower": "done", "errors": errors})
    sys.exit(1 if errors else 0)

if __name__ == "__main__":
    main()
