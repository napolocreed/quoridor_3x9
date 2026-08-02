#!/usr/bin/env python3
# orchestrate.py — pipeline complet par classe de réponse (reconstruit pour
# le PC 12 cœurs ; remplace grind.py + extract_all.py de la passation).
#
# Par classe : preuve de branche (TT par classe) -> extraction -> tri ->
# vérification échantillon + DFS borné. Reprenable : chaque étape saute si
# son artefact existe déjà. Sortie : une ligne JSON par étape dans
# replication/PIPELINE.log, artefacts dans work/, certparts/, replication/.
#
#   python orchestrate.py [--workers 3] [--only TAG,TAG] [--skip-verify]

import argparse, json, os, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
QSOLVE = os.path.join(HERE, "qsolve.exe")
QCERT2 = os.path.join(HERE, "qcert2.exe")
QMERGE = os.path.join(HERE, "qmerge.exe")
VERIFY = os.path.join(HERE, "verify_cert.py")

# les 18 classes canoniques (qsolve --mode list --first "P(7,1)"),
# lourdes d'abord ; H(0,0) déjà livrée et vérifiée -> reprise seulement si absente
CLASSES = [
    ("P11", "P(1,1)", 33),
    ("P00", "P(0,0)", 31),
    ("H00", "H(0,0)", 31),
    ("H10", "H(1,0)", 31), ("H20", "H(2,0)", 31), ("H30", "H(3,0)", 31),
    ("H40", "H(4,0)", 31), ("H50", "H(5,0)", 31), ("H60", "H(6,0)", 31),
    ("H70", "H(7,0)", 31),
    ("V00", "V(0,0)", 31), ("V10", "V(1,0)", 31), ("V20", "V(2,0)", 31),
    ("V30", "V(3,0)", 31), ("V40", "V(4,0)", 31), ("V50", "V(5,0)", 31),
    ("V60", "V(6,0)", 31), ("V70", "V(7,0)", 31),
]

TT_BITS, CACHE_BITS, CM_BITS = 25, 22, 24
# les classes pion sont 5-10x plus grosses que les classes mur (HANDOFF :
# 15-40 M d'entrées) ; V70 déborde aussi les 2^24 slots (rempli à 80 %)
CM_OVERRIDE = {"P11": 27, "P00": 27, "V70": 25}

LOG_LOCK = __import__("threading").Lock()
def log(obj):
    line = json.dumps(obj, ensure_ascii=False)
    with LOG_LOCK:
        print(line, flush=True)
        with open(os.path.join(HERE, "replication", "PIPELINE.log"), "a", encoding="utf-8") as f:
            f.write(line + "\n")

def run(cmd, out_json=None, timeout=None):
    t0 = time.time()
    p = subprocess.run(cmd, capture_output=True, text=True, cwd=HERE, timeout=timeout)
    if out_json and p.returncode in (0,) and p.stdout.strip():
        with open(out_json, "w", encoding="utf-8") as f:
            f.write(p.stdout)
    return p.returncode, p.stdout.strip().splitlines()[-1] if p.stdout.strip() else "", \
           p.stderr.strip().splitlines()[-1] if p.stderr.strip() else "", time.time() - t0

def do_class(tag, rep, rem, skip_verify):
    work = os.path.join(HERE, "work")
    parts = os.path.join(HERE, "certparts")
    repl = os.path.join(HERE, "replication")
    tt = os.path.join(work, f"tt_{tag}.bin")
    memo = os.path.join(work, f"memo_{tag}.bin")
    part = (os.path.join(HERE, "certparts-H00.bin") if tag == "H00"
            and os.path.exists(os.path.join(HERE, "certparts-H00.bin"))
            else os.path.join(parts, f"{tag}.bin"))
    upper_json = os.path.join(repl, f"upper_{tag}.json")
    extract_json = os.path.join(repl, f"extract_{tag}.json")

    # 1. preuve de branche (peuple la TT de classe)
    if os.path.exists(upper_json):
        log({"tag": tag, "step": "branch", "skipped": True})
    elif not os.path.exists(part):
        rc, out, err, el = run([QSOLVE, "--mode", "branch", "--first", "P(7,1)",
            "--second", rep, "--target", "1",
            "--start-depth", str(rem), "--max-depth", str(rem),
            "--tt-bits", str(TT_BITS), "--cache-bits", str(CACHE_BITS),
            "--tt-file", tt], out_json=upper_json)
        log({"tag": tag, "step": "branch", "rc": rc, "out": out, "err": err, "sec": round(el)})
        if rc != 0: return f"{tag}: branch rc={rc}"

    # 2. extraction
    if os.path.exists(part):
        log({"tag": tag, "step": "extract", "skipped": True})
        # reprise : une part dumpée juste avant une coupure peut ne pas être
        # triée — contrôler, et trier si nécessaire
        rc, out, err, el = run([QMERGE, "--mode", "check", "--in", part])
        if rc != 0:
            rc, out, err, el = run([QMERGE, "--mode", "sort", "--in", part])
            log({"tag": tag, "step": "sort(reprise)", "rc": rc, "out": out, "sec": round(el)})
            if rc not in (0, 4): return f"{tag}: sort reprise rc={rc}"
    else:
        rc, out, err, el = run([QCERT2, "--mode", "extract", "--reply", rep,
            "--rem", str(rem), "--tt-bits", str(TT_BITS),
            "--cache-bits", str(CACHE_BITS),
            "--cm-bits", str(CM_OVERRIDE.get(tag, CM_BITS)),
            "--tt-file", tt, "--memo", memo, "--out", part], out_json=extract_json)
        log({"tag": tag, "step": "extract", "rc": rc, "out": out, "err": err, "sec": round(el)})
        if rc != 0: return f"{tag}: extract rc={rc}"
        # 3. tri
        rc, out, err, el = run([QMERGE, "--mode", "sort", "--in", part])
        log({"tag": tag, "step": "sort", "rc": rc, "out": out, "sec": round(el)})
        if rc not in (0, 4): return f"{tag}: sort rc={rc}"

    if skip_verify: return None

    # 4. vérifications indépendantes (Python, règles clean-room)
    seed = 100003 * (1 + sum(ord(c) for c in tag))
    rc, out, err, el = run([sys.executable, VERIFY, "sample", part, "3000", str(seed), rep])
    log({"tag": tag, "step": "verify-sample", "rc": rc, "out": out, "sec": round(el)})
    if rc != 0: return f"{tag}: verify-sample rc={rc}"
    rc, out, err, el = run([sys.executable, VERIFY, "walk", part, rep, "200000"])
    log({"tag": tag, "step": "verify-walk", "rc": rc, "out": out, "sec": round(el)})
    if rc != 0: return f"{tag}: verify-walk rc={rc}"
    # GARDER les mémos : la CertMap contient (état -> rem, coup) pour TOUS les
    # nœuds, J2 compris — c'est la matière première d'un export qcert-1 JSONL
    # conforme à docs/CERTIFICATE_FORMAT.md (rangs = rem, décroissance stricte).
    return None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--only", type=str, default="")
    ap.add_argument("--skip-verify", action="store_true")
    a = ap.parse_args()
    for d in ("work", "certparts", "replication"):
        os.makedirs(os.path.join(HERE, d), exist_ok=True)
    todo = [c for c in CLASSES if not a.only or c[0] in a.only.split(",")]
    log({"pipeline": "start", "classes": [c[0] for c in todo], "workers": a.workers})
    errors = []
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        futs = {ex.submit(do_class, t, r, m, a.skip_verify): t for t, r, m in todo}
        for f in futs:
            e = f.result()
            if e: errors.append(e)
    log({"pipeline": "done", "errors": errors})
    sys.exit(1 if errors else 0)

if __name__ == "__main__":
    main()
