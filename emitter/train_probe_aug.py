#!/usr/bin/env python3
# train_probe_aug.py — sonde AUGMENTÉE : mêmes protocoles que train_probe.py
# mais sur dataset/<TAG>.aug.bin (records 20 octets) avec traits de chemin :
#   108 de base + d0 one-hot(16) + d1 one-hot(16) + dir0(4) + dir1(4)
#   + 32 bits « ancre adjacente au chemin optimal de J2 » = 180 traits.
# Question : les traits de chemin débloquent-ils la prédiction des MURS ?
#
#   python train_probe_aug.py

import os
os.environ.setdefault("OMP_NUM_THREADS", "6")
import numpy as np

TAGS = ["P11", "P00", "H00", "H10", "H20", "H30", "H40", "H50", "H60",
        "H70", "V00", "V10", "V20", "V30", "V40", "V50", "V60", "V70"]
HOLDOUT = {"H30", "V40"}
rng = np.random.default_rng(20260803)
NF = 180

def load(tag):
    raw = np.fromfile(f"dataset/{tag}.aug.bin", dtype=np.uint8).reshape(-1, 20)
    return raw

def features(raw):
    n = len(raw)
    X = np.zeros((n, NF), dtype=np.float32)
    ar = np.arange(n)
    X[ar, raw[:, 0]] = 1                                  # p0
    X[ar, 27 + raw[:, 1]] = 1                             # p1
    X[ar, 54 + raw[:, 2]] = 1                             # s0
    X[ar, 65 + raw[:, 3]] = 1                             # s1
    hw = raw[:, 4].astype(np.uint16) | (raw[:, 5].astype(np.uint16) << 8)
    vw = raw[:, 6].astype(np.uint16) | (raw[:, 7].astype(np.uint16) << 8)
    for b in range(16):
        X[:, 76 + b] = (hw >> b) & 1
        X[:, 92 + b] = (vw >> b) & 1
    X[ar, 108 + np.minimum(raw[:, 10], 15)] = 1           # d0
    X[ar, 124 + np.minimum(raw[:, 11], 15)] = 1           # d1
    for b in range(4):
        X[:, 140 + b] = (raw[:, 12] >> b) & 1             # dir0
        X[:, 144 + b] = (raw[:, 13] >> b) & 1             # dir1
    pm = (raw[:, 14].astype(np.uint32) | (raw[:, 15].astype(np.uint32) << 8) |
          (raw[:, 16].astype(np.uint32) << 16) | (raw[:, 17].astype(np.uint32) << 24))
    for b in range(32):
        X[:, 148 + b] = (pm >> b) & 1                     # ancres près chemin J2
    return X

train_parts, ho_parts = [], []
for tag in TAGS:
    (ho_parts if tag in HOLDOUT else train_parts).append(load(tag))
tr_raw = np.concatenate(train_parts)
ho_raw = np.concatenate(ho_parts)
perm = rng.permutation(len(tr_raw))
tr_raw = tr_raw[perm]
n_val = len(tr_raw) // 10
va_raw, tr_raw = tr_raw[:n_val], tr_raw[n_val:]
print(f"train {len(tr_raw)}, val {len(va_raw)}, holdout {len(ho_raw)} (H30+V40)")

def batches(raw, bs, shuffle=True):
    n = len(raw)
    idx = rng.permutation(n) if shuffle else np.arange(n)
    for i in range(0, n - bs + 1 if shuffle else n, bs):
        j = idx[i:i + bs]
        yield features(raw[j]), raw[j, 9].astype(np.int64)

def forward(Ws, X):
    acts = [X]
    for i, (W, b) in enumerate(Ws):
        z = acts[-1] @ W + b
        if i < len(Ws) - 1:
            z = np.maximum(z, 0)
        acts.append(z)
    return acts

def evaluate(Ws, raw, bs=8192):
    top1 = top3 = tot = 0
    pk = np.zeros(2); pt = np.zeros(2)
    w3 = 0; kind_ok = 0
    for X, y in batches(raw, bs, shuffle=False):
        z = forward(Ws, X)[-1]
        pred = z.argmax(1)
        top1 += (pred == y).sum()
        t3 = np.argpartition(-z, 3, axis=1)[:, :3]
        hit3 = (t3 == y[:, None]).any(1)
        top3 += hit3.sum()
        wall = y >= 27
        kind_ok += ((pred >= 27) == wall).sum()
        w3 += hit3[wall].sum()
        for k, m in [(0, ~wall), (1, wall)]:
            pk[k] += (pred[m] == y[m]).sum(); pt[k] += m.sum()
        tot += len(y)
    return (top1 / tot, top3 / tot, pk[0] / max(pt[0], 1), pk[1] / max(pt[1], 1),
            w3 / max(pt[1], 1), kind_ok / tot)

def train(dims, epochs=6, bs=4096, lr=3e-3, wall_weight=1.0):
    Ws = []
    for i in range(len(dims) - 1):
        Ws.append([rng.normal(0, np.sqrt(2 / dims[i]), (dims[i], dims[i + 1])).astype(np.float32),
                   np.zeros(dims[i + 1], dtype=np.float32)])
    mom = [[np.zeros_like(W), np.zeros_like(b)] for W, b in Ws]
    vel = [[np.zeros_like(W), np.zeros_like(b)] for W, b in Ws]
    t = 0
    for ep in range(epochs):
        loss_sum = cnt = 0
        for X, y in batches(tr_raw, bs):
            acts = forward(Ws, X)
            z = acts[-1]
            z -= z.max(1, keepdims=True)
            e = np.exp(z); p = e / e.sum(1, keepdims=True)
            loss_sum += -np.log(p[np.arange(len(y)), y] + 1e-12).sum(); cnt += len(y)
            sw = np.where(y >= 27, wall_weight, 1.0).astype(np.float32)
            g = p; g[np.arange(len(y)), y] -= 1
            g *= (sw / sw.sum())[:, None]
            grads = []
            for i in range(len(Ws) - 1, -1, -1):
                gW = acts[i].T @ g; gb = g.sum(0)
                grads.append((gW, gb))
                if i > 0:
                    g = (g @ Ws[i][0].T) * (acts[i] > 0)
            grads.reverse()
            t += 1
            for i, (gW, gb) in enumerate(grads):
                for j, gr in enumerate((gW, gb)):
                    mom[i][j] = 0.9 * mom[i][j] + 0.1 * gr
                    vel[i][j] = 0.999 * vel[i][j] + 0.001 * gr * gr
                    Ws[i][j] -= lr * (mom[i][j] / (1 - 0.9 ** t)) / (np.sqrt(vel[i][j] / (1 - 0.999 ** t)) + 1e-8)
        va_m = evaluate(Ws, va_raw)
        print(f"  epoch {ep + 1} : loss {loss_sum / cnt:.4f}, val top-1 {va_m[0]:.4f}", flush=True)
    return Ws

RUNS = [
    ("softmax-180", [NF, 59], dict(epochs=4)),
    ("MLP 180-512-59, murs ×4", [NF, 512, 59], dict(epochs=6, wall_weight=4.0)),
]
for name, dims, kw in RUNS:
    print(f"\n=== {name} ===", flush=True)
    Ws = train(dims, **kw)
    np.savez(f"dataset/probe_aug_{dims[1] if len(dims) > 2 else 'lin'}.npz",
             *[a for Wb in Ws for a in Wb])
    for dname, d in [("val (in-dist)", va_raw), ("HOLDOUT H30+V40", ho_raw)]:
        t1, t3, pp, pw, w3, kd = evaluate(Ws, d)
        print(f"{dname} : top-1 {t1:.4f}, top-3 {t3:.4f} | pions {pp:.4f}, "
              f"murs {pw:.4f} (top-3 murs {w3:.4f}) | pion-vs-mur {kd:.4f}")
