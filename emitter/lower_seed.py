#!/usr/bin/env python3
# lower_seed.py — rejoue les 18 réfutations de la borne inférieure avec
# --tt-seed (P2 d'IDEES_SWEEP) et compare aux archives lower_*.json.
# SÉQUENTIEL : chaque processus charge la table fusionnée (~4,3 Go).
#
#   python lower_seed.py

import json, os, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
QSOLVE2 = os.path.join(HERE, "qsolve2.exe")
ROOTS = ["P(7,1)", "H(0,0)", "H(1,0)", "H(2,0)", "H(3,0)", "H(4,0)", "H(5,0)",
         "H(6,0)", "H(7,0)", "P(8,0)", "V(0,0)", "V(1,0)", "V(2,0)", "V(3,0)",
         "V(4,0)", "V(5,0)", "V(6,0)", "V(7,0)"]
TAGS = ["P11", "P00", "H00", "H10", "H20", "H30", "H40", "H50", "H60", "H70",
        "V00", "V10", "V20", "V30", "V40", "V50", "V60", "V70"]
SEED_ARGS = []
for t in TAGS:
    SEED_ARGS += ["--tt-seed", os.path.join("work", f"memo_{t}.bin")]

def tag(rep):
    return rep.replace("(", "").replace(")", "").replace(",", "")

def log(obj):
    line = json.dumps(obj, ensure_ascii=False)
    print(line, flush=True)
    with open(os.path.join(HERE, "replication", "LOWERSEED.log"), "a", encoding="utf-8") as f:
        f.write(line + "\n")

tot_nodes = tot_base = tot_sec = tot_base_sec = 0
errors = []
for rep in ROOTS:
    t = tag(rep)
    out_json = os.path.join(HERE, "replication", f"lowerseed_{t}.json")
    base = json.load(open(os.path.join(HERE, "replication", f"lower_{t}.json"), encoding="utf-8"))
    if os.path.exists(out_json):
        j = json.load(open(out_json, encoding="utf-8"))
    else:
        p = subprocess.run([QSOLVE2, "--mode", "branch", "--first", rep, "--target", "1",
                            "--start-depth", "32", "--max-depth", "32",
                            "--tt-bits", "25", "--cache-bits", "22"] + SEED_ARGS,
                           capture_output=True, text=True, cwd=HERE)
        outline = p.stdout.strip().splitlines()[-1] if p.stdout.strip() else ""
        try:
            j = json.loads(outline)
        except json.JSONDecodeError:
            errors.append(f"{rep}: sortie illisible rc={p.returncode}")
            log({"root": rep, "rc": p.returncode, "err": p.stderr.strip()[-200:]})
            continue
        ok = (j.get("proved") is False and j.get("timeout") is False)
        if not ok:
            errors.append(f"{rep}: verdict inattendu {j.get('proved')}")
            log({"root": rep, "UNEXPECTED": j}); continue
        with open(out_json, "w", encoding="utf-8") as f:
            f.write(outline + "\n")
    dn = 100.0 * (1 - j["nodes"] / base["nodes"])
    ds = 100.0 * (1 - j["seconds"] / base["seconds"])
    tot_nodes += j["nodes"]; tot_base += base["nodes"]
    tot_sec += j["seconds"]; tot_base_sec += base["seconds"]
    log({"root": rep, "nodes": j["nodes"], "base": base["nodes"],
         "dnodes_pct": round(dn, 1), "dsec_pct": round(ds, 1),
         "seed_hits": j.get("seed_hits"), "seed_loose": j.get("seed_loose")})

log({"TOTAL": {"nodes": tot_nodes, "base": tot_base,
               "dnodes_pct": round(100.0 * (1 - tot_nodes / tot_base), 1),
               "sec": round(tot_sec, 1), "base_sec": round(tot_base_sec, 1),
               "errors": errors}})
sys.exit(1 if errors else 0)
