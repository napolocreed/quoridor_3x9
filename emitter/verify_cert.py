#!/usr/bin/env python3
# verify_cert.py — vérificateur indépendant du certificat cert_3x9x10.bin.
#
# But : contrôler la revendication « J1 gagne au Quoridor 3x9 (10 murs) en
# <= 35 plis » SANS faire confiance aux solveurs. Le certificat donne, pour
# des états où J1 est au trait, le coup à jouer. Ce script rejoue la
# stratégie contre les coups adverses et vérifie : légalité du coup fourni,
# présence d'une entrée à chaque état J1 rencontré (directement ou via le
# miroir gauche-droite), et victoire de J1 (rangée 0) en <= 35 plis.
#
# Règles réimplémentées ici depuis docs/RULES.md (lignée clean-room qref.mjs),
# indépendamment du solveur qui a produit le certificat.
#
# Modes :
#   python3 verify_cert.py sample cert.bin N seed     # N parties aléatoires
#   python3 verify_cert.py walk cert.bin REPLY M      # DFS borné à M états sous une réponse
#
# Format du certificat : 4 u64 d'en-tête ("QCRT", W|H<<8|murs<<16, budget, 0)
# puis des u64 : (clé 51b) << 9 | coup 9b, TRIÉS sauf la 1re entrée (racine).
# Clé (bits, du bas vers le haut) : target1, turn1, st1:4, st0:4, p1:5, p0:5,
# vw:18, hw:reste. Coup : <256 = case d'arrivée du pion ; >=256 : mur,
# ori=(c-256)//S (0=H,1=V), slot=(c-256)%S, r=slot//C, c=slot%C.

import sys, random
from array import array
from bisect import bisect_left

W, H, WALLS, BUDGET = 3, 9, 10, 35
C, R = W - 1, H - 1
S = C * R

# ── règles (depuis RULES.md) ──────────────────────────────────────────────
def row(p): return p // W
def col(p): return p % W

def blocked(hw, vw, a, b):
    if col(a) == col(b):
        rr, c = min(row(a), row(b)), col(a)
        if c < C and (hw >> (rr * C + c)) & 1: return True
        if c > 0 and (hw >> (rr * C + c - 1)) & 1: return True
        return False
    cc, r = min(col(a), col(b)), row(a)
    if r < R and (vw >> (r * C + cc)) & 1: return True
    if r > 0 and (vw >> ((r - 1) * C + cc)) & 1: return True
    return False

def step(hw, vw, p, d):                      # 0 haut, 1 bas, 2 gauche, 3 droite
    r, c = row(p), col(p)
    if d == 0: return p - W if r > 0 and not blocked(hw, vw, p, p - W) else -1
    if d == 1: return p + W if r < H - 1 and not blocked(hw, vw, p, p + W) else -1
    if d == 2: return p - 1 if c > 0 and not blocked(hw, vw, p, p - 1) else -1
    return p + 1 if c < W - 1 and not blocked(hw, vw, p, p + 1) else -1

def reaches(hw, vw, p, goal_row):
    if row(p) == goal_row: return True
    seen, st = {p}, [p]
    while st:
        x = st.pop()
        for d in range(4):
            z = step(hw, vw, x, d)
            if z >= 0 and z not in seen:
                if row(z) == goal_row: return True
                seen.add(z); st.append(z)
    return False

def wall_fits(hw, vw, ori, r, c):
    i = r * C + c
    if (hw >> i) & 1 or (vw >> i) & 1: return False
    if ori == 0:
        if c > 0 and (hw >> (i - 1)) & 1: return False
        if c < C - 1 and (hw >> (i + 1)) & 1: return False
    else:
        if r > 0 and (vw >> (i - C)) & 1: return False
        if r < R - 1 and (vw >> (i + C)) & 1: return False
    return True

PERP = {0: (2, 3), 1: (2, 3), 2: (0, 1), 3: (0, 1)}

def legal_moves(st):
    hw, vw, p, stock, turn = st
    me, op = p[turn], p[1 - turn]
    out = []
    for d in range(4):
        z = step(hw, vw, me, d)
        if z < 0: continue
        if z != op:
            out.append(("P", z)); continue
        j = step(hw, vw, op, d)
        if j >= 0: out.append(("P", j))
        else:
            for pd in PERP[d]:
                z2 = step(hw, vw, op, pd)
                if z2 >= 0: out.append(("P", z2))
    if stock[turn] > 0:
        for ori in range(2):
            for i in range(S):
                r, c = i // C, i % C
                if not wall_fits(hw, vw, ori, r, c): continue
                nh = hw | (1 << i) if ori == 0 else hw
                nv = vw | (1 << i) if ori == 1 else vw
                if not reaches(nh, nv, p[0], 0) or not reaches(nh, nv, p[1], H - 1): continue
                out.append(("W", ori, r, c))
    return out

def apply_move(st, mv):
    hw, vw, p, stock, turn = st
    if mv[0] == "P":
        np_ = list(p); np_[turn] = mv[1]
        return (hw, vw, tuple(np_), stock, 1 - turn)
    _, ori, r, c = mv
    i = r * C + c
    nh = hw | (1 << i) if ori == 0 else hw
    nv = vw | (1 << i) if ori == 1 else vw
    ns = list(stock); ns[turn] -= 1
    return (nh, nv, p, tuple(ns), 1 - turn)

# ── certificat ────────────────────────────────────────────────────────────
def key_of(st):
    hw, vw, p, stock, turn = st
    x = hw
    x = (x << 18) | vw
    x = (x << 5) | p[0]
    x = (x << 5) | p[1]
    x = (x << 4) | stock[0]
    x = (x << 4) | stock[1]
    x = (x << 1) | turn
    x = (x << 1) | 0
    return x

def decode_move(mid):
    if mid < 256: return ("P", mid)
    w = mid - 256
    return ("W", w // S, (w % S) // C, (w % S) % C)

def mirror_state(st):
    hw, vw, p, stock, turn = st
    mh = mv_ = 0
    for i in range(S):
        r, c = i // C, i % C
        if (hw >> i) & 1: mh |= 1 << (r * C + (C - 1 - c))
        if (vw >> i) & 1: mv_ |= 1 << (r * C + (C - 1 - c))
    mp = tuple(q // W * W + (W - 1 - q % W) for q in p)
    return (mh, mv_, mp, stock, turn)

def mirror_move(mv):
    if mv[0] == "P":
        q = mv[1]; return ("P", q // W * W + (W - 1 - q % W))
    _, ori, r, c = mv
    return ("W", ori, r, C - 1 - c)

class Cert:
    def __init__(self, path):
        raw = open(path, "rb").read()
        a = array("Q"); a.frombytes(raw)
        if a[0] == 0x54524351:                 # fichier fusionné avec en-tête
            self.budget = a[2]; self.root = a[4]; self.body = a[5:]
        else:                                  # part brute triée, sans en-tête
            self.budget = BUDGET; self.root = 0; self.body = a
        print(f"certificat : {len(self.body):,} entrées, budget {self.budget}")
    def lookup_raw(self, k):
        if (self.root >> 9) == k: return self.root & 0x1ff
        i = bisect_left(self.body, k << 9)
        if i < len(self.body) and (self.body[i] >> 9) == k: return self.body[i] & 0x1ff
        return -1
    use_mirror = True
    def lookup(self, st):
        m = self.lookup_raw(key_of(st))
        if m >= 0: return decode_move(m), False
        if self.use_mirror:
            m = self.lookup_raw(key_of(mirror_state(st)))
            if m >= 0: return mirror_move(decode_move(m)), True
        return None, False

def initial():
    return (0, 0, ((H - 1) * W + W // 2, W // 2), (WALLS, WALLS), 0)

# ── vérifications ─────────────────────────────────────────────────────────
def check_line(cert, rng, forced_reply=None):
    """une partie : J1 suit le certificat, J2 joue au hasard ; retourne (ok, plis)"""
    st, ply = initial(), 0
    while ply < cert.budget:
        if row(st[2][0]) == 0: return True, ply
        if row(st[2][1]) == H - 1: return False, ply           # J2 gagne : contradiction
        moves = legal_moves(st)
        if not moves: return False, ply                        # pat : contradiction
        if st[4] == 0:
            if ply == 0:
                mv = ("P", 7 * W + 1)                          # témoin public : P(7,1)
            else:
                mv, _ = cert.lookup(st)
                if mv is None: return False, ply               # entrée manquante
            if mv not in moves: return False, ply              # coup illégal fourni
        else:
            if ply == 1 and forced_reply is not None:
                mv = forced_reply
            else:
                mv = moves[rng.randrange(len(moves))]
        st = apply_move(st, mv); ply += 1
    return row(st[2][0]) == 0, ply

def parse_reply(lbl):
    if lbl.startswith("P("):
        r, c = map(int, lbl[2:-1].split(",")); return ("P", r * W + c)
    ori = 0 if lbl[0] == "H" else 1
    r, c = map(int, lbl[2:-1].split(",")); return ("W", ori, r, c)

def mode_forensic(cert_path, game_idx, seed, reply):
    """rejoue les parties jusqu'à game_idx et imprime la ligne fautive en détail"""
    cert = Cert(cert_path); cert.use_mirror = False
    rng = random.Random(seed)
    forced = parse_reply(reply)
    for g in range(game_idx):
        check_line(cert, rng, forced)
    # partie fautive, tracée
    st, ply, line = initial(), 0, []
    while ply < cert.budget:
        if row(st[2][0]) == 0:
            print("gagnée ?!"); return 0
        moves = legal_moves(st)
        if st[4] == 0:
            mv = ("P", 7 * W + 1) if ply == 0 else cert.lookup(st)[0]
            src = "cert"
        else:
            mv = forced if ply == 1 else moves[rng.randrange(len(moves))]
            src = "rand"
        lbl = (f"P({mv[1]//W},{mv[1]%W})" if mv[0] == "P" else f"{'HV'[mv[1]]}({mv[2]},{mv[3]})")
        line.append(lbl)
        k = key_of(st)
        print(f"pli {ply:2d} [{src}] {lbl:8s} reste={cert.budget-ply:2d} "
              f"cle={k} hw={st[0]} vw={st[1]} p={st[2]} st={st[3]}")
        st = apply_move(st, mv); ply += 1
    print("LIGNE:", ",".join(line))
    print(f"final : p1 rangée {row(st[2][0])} (pas 0) — budget épuisé")
    return 1

def mode_sample(cert_path, n, seed, reply=None):
    cert = Cert(cert_path)
    if reply: cert.use_mirror = False          # une part brute : clés brutes uniquement
    rng = random.Random(seed)
    forced = parse_reply(reply) if reply else None
    plies = []
    for g in range(n):
        ok, ply = check_line(cert, rng, forced)
        if not ok:
            print(f"ECHEC à la partie {g} (pli {ply})"); return 1
        plies.append(ply)
        if (g + 1) % 500 == 0: print(f"  {g + 1}/{n} ok…")
    print(f"OK : {n} parties, J1 gagne toujours en <= {max(plies)} plis "
          f"(min {min(plies)}, moy {sum(plies)/len(plies):.1f})")
    return 0

def mode_walk(cert_path, reply, max_states):
    """DFS borné : TOUTES les réponses de J2 explorées, jusqu'à max_states états"""
    cert = Cert(cert_path)
    st = initial()
    if cert.root:
        mv, _ = cert.lookup(st)                                # fichier fusionné
    else:
        mv, cert.use_mirror = ("P", 7 * W + 1), False          # part brute : témoin forcé, clés brutes
    st = apply_move(st, mv)                                    # P(7,1)
    target = None
    for m in legal_moves(st):
        lbl = (f"P({m[1]//W},{m[1]%W})" if m[0] == "P" else
               f"{'HV'[m[1]]}({m[2]},{m[3]})")
        if lbl == reply: target = m
    if target is None: print("réponse inconnue"); return 2
    st = apply_move(st, target)
    seen, stack, states, deepest = set(), [(st, 2)], 0, 0
    while stack and states < max_states:
        s, ply = stack.pop()
        if row(s[2][0]) == 0: continue
        if ply >= cert.budget or row(s[2][1]) == H - 1:
            print(f"ECHEC (pli {ply})"); return 1
        k = key_of(s)
        if k in seen: continue
        seen.add(k); states += 1; deepest = max(deepest, ply)
        moves = legal_moves(s)
        if not moves: print("pat rencontré ?!"); return 1
        if s[4] == 0:
            mv, _ = cert.lookup(s)
            if mv is None or mv not in moves:
                print(f"ECHEC entrée (pli {ply})"); return 1
            stack.append((apply_move(s, mv), ply + 1))
        else:
            for m in moves: stack.append((apply_move(s, m), ply + 1))
    print(f"OK : {states:,} états contrôlés sous {reply} (pli max {deepest}), aucune violation")
    return 0

if __name__ == "__main__":
    m = sys.argv[1]
    if m == "forensic": sys.exit(mode_forensic(sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), sys.argv[5]))
    if m == "sample": sys.exit(mode_sample(sys.argv[2], int(sys.argv[3]), int(sys.argv[4]),
                                            sys.argv[5] if len(sys.argv) > 5 else None))
    if m == "walk":   sys.exit(mode_walk(sys.argv[2], sys.argv[3], int(sys.argv[4])))
    print("modes : sample | walk"); sys.exit(2)
