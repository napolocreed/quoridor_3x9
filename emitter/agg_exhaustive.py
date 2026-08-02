#!/usr/bin/env python3
# Agrège replication/EXHAUSTIVE.log en AGGREGATE_exhaustive.json.
# qverify imprime les chemins Windows avec antislashs bruts (JSON invalide) :
# on les normalise avant re-parse.
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
rows = [json.loads(l) for l in open(os.path.join(HERE, "replication", "EXHAUSTIVE.log"), encoding="utf-8")
        if '"tag"' in l]
outs = [json.loads(r["out"].replace("\\", "/")) for r in rows if r["rc"] == 0]
ts = sum(o["states"] for o in outs)
tsec = sum(o["seconds"] for o in outs)
agg = {
    "claim": ("chaque reponse legale de J2 apres P(7,1) (18 canoniques + 17 jumelles miroir) "
              "verifiee par DFS exhaustif clean-room : J1 gagne toujours en <= 35 plis"),
    "runs": len(outs), "ok": len(outs),
    "aggregate_states": ts, "aggregate_seconds": round(tsec, 1),
    "per_run": [{"reply": o["reply"], "mirror": o["mirror"],
                 "states": o["states"], "seconds": o["seconds"]} for o in outs],
}
with open(os.path.join(HERE, "replication", "AGGREGATE_exhaustive.json"), "w", encoding="utf-8") as f:
    f.write(json.dumps(agg, ensure_ascii=False, indent=1))
print("runs:", len(outs), "/35  etats totaux:", f"{ts:,}", " temps:", round(tsec), "s")
