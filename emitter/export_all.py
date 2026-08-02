#!/usr/bin/env python3
# export_all.py — exporte les 18 mémos CertMap en parts qcert-1 gzippées
# déterministes pour l'agrégat qcert-aggregate-1 (docs/QCERT_AGGREGATE_FORMAT.md
# côté sol). Séquentiel (RAM), reprenable (saute une part déjà consignée).
#
# Par classe : qexport (JSONL brut, en-tête = racine+borne) -> gzip -n -9
# (octets déterministes, pas de nom/mtime) -> renommage atomique -> SHA-256
# du flux gzip -> ligne dans aggregate/EXPORTS.jsonl -> suppression du brut.
# Exception H10 : le brut épinglé work/H10.qcert1.jsonl (reçu sol
# 961df2b3...) est réutilisé tel quel et JAMAIS supprimé.

import gzip as gzmod
import hashlib, json, os, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
QEXPORT = os.path.join(HERE, "qexport.exe")
WORK = os.path.join(HERE, "work")
AGG = os.path.join(HERE, "aggregate")
PARTS = os.path.join(AGG, "parts")
LEDGER = os.path.join(AGG, "EXPORTS.jsonl")

CLASSES = [
    ("P11", "P(1,1)"), ("P00", "P(0,0)"),
    ("H00", "H(0,0)"), ("H10", "H(1,0)"), ("H20", "H(2,0)"), ("H30", "H(3,0)"),
    ("H40", "H(4,0)"), ("H50", "H(5,0)"), ("H60", "H(6,0)"), ("H70", "H(7,0)"),
    ("V00", "V(0,0)"), ("V10", "V(1,0)"), ("V20", "V(2,0)"), ("V30", "V(3,0)"),
    ("V40", "V(4,0)"), ("V50", "V(5,0)"), ("V60", "V(6,0)"), ("V70", "V(7,0)"),
]

PINNED_H10 = os.path.join(WORK, "H10.qcert1.jsonl")

def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

def done_tags():
    tags = set()
    if os.path.exists(LEDGER):
        with open(LEDGER, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    tags.add(json.loads(line)["tag"])
    return tags

def main():
    os.makedirs(PARTS, exist_ok=True)
    already = done_tags()
    for tag, rep in CLASSES:
        gz = os.path.join(PARTS, f"{tag}.qcert1.jsonl.gz")
        if tag in already and os.path.exists(gz):
            print(json.dumps({"tag": tag, "skipped": True}), flush=True)
            continue
        t0 = time.time()
        # 1. JSONL brut (H10 : réutilise l'export épinglé, déterminisme déjà prouvé)
        if tag == "H10" and os.path.exists(PINNED_H10):
            raw, keep_raw = PINNED_H10, True
            summary = None
        else:
            raw, keep_raw = os.path.join(PARTS, f"{tag}.qcert1.jsonl.tmp"), False
            # chemins RELATIFS à barres obliques : qexport recopie --out tel
            # quel dans son JSON de résumé, et des antislashs Windows y font
            # un échappement invalide (bug consigné, IDEES.md §6)
            raw_rel = f"aggregate/parts/{tag}.qcert1.jsonl.tmp"
            memo_rel = f"work/memo_{tag}.bin"
            p = subprocess.run([QEXPORT, "--memo", memo_rel, "--reply", rep,
                                "--out", raw_rel],
                               capture_output=True, text=True, cwd=HERE)
            if p.returncode != 0:
                print(json.dumps({"tag": tag, "step": "export", "rc": p.returncode,
                                  "err": p.stderr.strip()}), flush=True)
                sys.exit(1)
            last = p.stdout.strip().splitlines()[-1].replace("\\", "/")
            summary = json.loads(last)
        # 2. en-tête (racine + borne pour le manifeste)
        with open(raw, encoding="utf-8") as f:
            header = json.loads(f.readline())
        # 3. gzip déterministe (module Python : pas de nom, mtime=0, niveau 9 ;
        # indépendant du PATH — le gzip MSYS2 est invisible en détaché)
        gz_tmp = gz + ".tmp"
        with open(raw, "rb") as fi, open(gz_tmp, "wb") as fo:
            with gzmod.GzipFile(filename="", mode="wb", fileobj=fo,
                                compresslevel=9, mtime=0) as zo:
                for chunk in iter(lambda: fi.read(1 << 20), b""):
                    zo.write(chunk)
        os.replace(gz_tmp, gz)
        # 4. empreintes + registre
        rec = {
            "tag": tag, "reply": rep,
            "path": f"parts/{tag}.qcert1.jsonl.gz",
            "bound": header["bound"], "root": header["root"],
            "sha256_gz": sha256_file(gz), "bytes_gz": os.path.getsize(gz),
            "sha256_raw": sha256_file(raw), "bytes_raw": os.path.getsize(raw),
            "summary": summary, "seconds": round(time.time() - t0, 1),
        }
        with open(LEDGER, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")
        if not keep_raw:
            os.remove(raw)
        print(json.dumps({"tag": tag, "ok": True, "bound": rec["bound"],
                          "bytes_gz": rec["bytes_gz"],
                          "sec": rec["seconds"]}), flush=True)
    print(json.dumps({"exports": "done"}), flush=True)

if __name__ == "__main__":
    main()
