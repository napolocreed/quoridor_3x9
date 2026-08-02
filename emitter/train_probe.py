#!/usr/bin/env python3
# train_probe.py — sonde de faisabilité : les coups optimaux exacts des mémos
# sont-ils apprenables depuis des traits bon marché ? (idée n°2 d'IDEES.md,
# jugée « plausible » par sol ; verrou de l'ordering appris pour 4×7.)
#
# Dataset : dataset/<TAG>.bin, records 10 octets
#   p0, p1, s0, s1, hw u16LE, vw u16LE, rem, move   (move 0..58)
# Traits (108) : one-hot p0(27) + p1(27) + s0(11) + s1(11) + hw(16) + vw(16).
# Éval : top-1/top-3 in-distribution ET hors-classes (H30, V40 exclues de
# l'entraînement) + base « coup majoritaire par p0 ».
#
#   python train_probe.py

import os
os.environ.setdefault("OMP_NUM_THREADS", "6")
import numpy as np

TAGS = ["P11", "P00", "H00", "H10", "H20", "H30", "H40", "H50", "H60",
        "H70", "V00", "V10", "V20", "V30", "V40", "V50", "V60", "V70"]
HOLDOUT = {"H30", "V40"}
rng = np.random.default_rng(20260802)

def load(tag):
    raw = np.fromfile(f"dataset/{tag}.bin", dtype=np.uint8).reshape(-1, 10)
    p0, p1, s0, s1 = raw[:, 0], raw[:, 1], raw[:, 2], raw[:, 3]
    hw = raw[:, 4].astype(np.uint16) | (raw[:, 5].astype(np.uint16) << 8)
    vw = raw[:, 6].astype(np.uint16) | (raw[:, 7].astype(np.uint16) << 8)
    rem, move = raw[:, 8], raw[:, 9]
    return p0, p1, s0, s1, hw, vw, rem, move

def features(p0, p1, s0, s1, hw, vw):
    n = len(p0)
    X = np.zeros((n, 108), dtype=np.float32)
    X[np.arange(n), p0] = 1
    X[np.arange(n), 27 + p1] = 1
    X[np.arange(n), 54 + s0] = 1
    X[np.arange(n), 65 + s1] = 1
    for b in range(16):
        X[:, 76 + b] = (hw >> b) & 1
        X[:, 92 + b] = (vw >> b) & 1
    return X

train_parts, ho_parts = [], []
for tag in TAGS:
    part = load(tag)
    (ho_parts if tag in HOLDOUT else train_parts).append(part)

def stack(parts):
    return [np.concatenate([p[i] for p in parts]) for i in range(8)]

tr = stack(train_parts)
ho = stack(ho_parts)
n = len(tr[0])
perm = rng.permutation(n)
tr = [a[perm] for a in tr]
n_val = n // 10
va, tr = [a[:n_val] for a in tr], [a[n_val:] for a in tr]
print(f"train {len(tr[0])}, val {len(va[0])}, holdout {len(ho[0])} (H30+V40)")

# ---- base : coup majoritaire par p0 (livre trivial) -------------------------
book = np.zeros(27, dtype=np.int64)
for c in range(27):
    m = tr[0] == c
    if m.any():
        book[c] = np.bincount(tr[7][m], minlength=59).argmax()
for name, d in [("val", va), ("holdout", ho)]:
    acc = (book[d[0]] == d[7]).mean()
    print(f"base majoritaire-par-p0 {name} : top-1 {acc:.4f}")

# ---- modèles ----------------------------------------------------------------
def batches(data, bs, shuffle=True):
    n = len(data[0])
    idx = rng.permutation(n) if shuffle else np.arange(n)
    for i in range(0, n - bs + 1 if shuffle else n, bs):
        j = idx[i:i + bs]
        X = features(data[0][j], data[1][j], data[2][j], data[3][j],
                     data[4][j], data[5][j])
        yield X, data[7][j].astype(np.int64)

def evaluate(Ws, data, bs=8192):
    top1 = top3 = tot = 0
    pk = np.zeros(2); pt = np.zeros(2)              # [pion, mur] corrects/totaux
    w3 = 0                                          # top-3 parmi les vrais murs
    kind_ok = 0                                     # décision pion-vs-mur
    for X, y in batches(data, bs, shuffle=False):
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

def forward(Ws, X):
    acts = [X]
    for i, (W, b) in enumerate(Ws):
        z = acts[-1] @ W + b
        if i < len(Ws) - 1:
            z = np.maximum(z, 0)
        acts.append(z)
    return acts

def train(dims, epochs=4, bs=4096, lr=3e-3, wall_weight=1.0):
    Ws = []
    for i in range(len(dims) - 1):
        Ws.append([rng.normal(0, np.sqrt(2 / dims[i]), (dims[i], dims[i + 1])).astype(np.float32),
                   np.zeros(dims[i + 1], dtype=np.float32)])
    mom = [[np.zeros_like(W), np.zeros_like(b)] for W, b in Ws]
    vel = [[np.zeros_like(W), np.zeros_like(b)] for W, b in Ws]
    t = 0
    for ep in range(epochs):
        loss_sum = cnt = 0
        for X, y in batches(tr, bs):
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
                    mh = mom[i][j] / (1 - 0.9 ** t)
                    vh = vel[i][j] / (1 - 0.999 ** t)
                    Ws[i][j] -= lr * mh / (np.sqrt(vh) + 1e-8)
        va_m = evaluate(Ws, va)
        print(f"  epoch {ep + 1} : loss {loss_sum / cnt:.4f}, val top-1 {va_m[0]:.4f}")
    return Ws

RUNS = [
    ("softmax (linéaire)", [108, 59], dict()),
    ("MLP 108-256-59", [108, 256, 59], dict(epochs=6)),
    ("MLP 108-512-59, murs ×4", [108, 512, 59], dict(epochs=6, wall_weight=4.0)),
]
for name, dims, kw in RUNS:
    print(f"\n=== {name} ===")
    Ws = train(dims, **kw)
    np.savez(f"dataset/probe_{dims[1]}_{kw.get('wall_weight', 1)}.npz",
             *[a for Wb in Ws for a in Wb])
    for dname, d in [("val (in-dist)", va), ("HOLDOUT H30+V40", ho)]:
        t1, t3, pp, pw, w3, kd = evaluate(Ws, d)
        print(f"{dname} : top-1 {t1:.4f}, top-3 {t3:.4f} | pions {pp:.4f}, "
              f"murs {pw:.4f} (top-3 murs {w3:.4f}) | pion-vs-mur {kd:.4f}")
