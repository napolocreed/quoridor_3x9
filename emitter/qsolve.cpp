// qsolve.cpp — solveur borné indépendant pour variantes étroites de Quoridor.
//
// Réplication structurellement séparée de quoridor-frontier-research :
// règles réimplémentées depuis docs/RULES.md (déjà validées croisées via
// qref.mjs), architecture délibérément différente du solveur de Sol :
//
//   Sol (eager)                    ce solveur
//   ───────────────────────────    ──────────────────────────────────────
//   énumération globale des        aucune énumération : cache de distances
//   2,93 M de configs de murs      construit à la demande, borné
//   légalité par lookup            porte union-find (un mur ne coupe que
//   de reachability précalculée    s'il ferme un cycle du treillis des
//                                  jonctions) + BFS seulement en cas de cycle
//   symétries miroir + 180°/swap   miroir uniquement
//   ordre par éval tactique        ordre statique : pion d'abord,
//   (distances précalculées)       murs par proximité du pion adverse
//
// Sémantique identique (docs/PROOF_SEMANTICS.md) : Win(s,T,d) exact,
// normalisation de parité (re-dérivée : la cible ne peut conclure que sur
// son propre coup), TT à faits monotones (plus petit d prouvé vrai, plus
// grand d prouvé faux), et convention pat = « la cible ne gagne pas »
// (celle du code de Sol ; aucun état pat rencontré empiriquement — un
// compteur l'archive à chaque exécution).
//
// Borne de distance optionnelle (coupe « faux » uniquement), prouvée :
//   Lemme. Soit d0 la distance BFS du pion cible à sa rangée but, murs
//   fixés, pions ignorés. Un coup propre de la cible diminue d0 d'au plus
//   2 (pas simple : ≤1 ; saut droit/diagonal : ≤2 par inégalité
//   triangulaire) ; un coup adverse ne la diminue jamais (un mur ne peut
//   qu'allonger, le pion adverse ne bloque pas le BFS). Donc la cible a
//   besoin d'au moins ⌈d0/2⌉ coups propres.
//
// Build : g++ -O3 -std=c++20 -o qsolve qsolve.cpp

#include <cstdint>
#include <cstring>
#include <cstdio>
#include <cstdlib>
#include <string>
#include <vector>
#include <array>
#include <chrono>
#include <random>
#include <algorithm>

using u8 = uint8_t; using u16 = uint16_t; using u32 = uint32_t; using u64 = uint64_t;
using Clock = std::chrono::steady_clock;

static int W, H, WALLS, N, C, R, S;
static constexpr int NCAP = 32, SCAP = 18;

struct State { u32 hw, vw; u8 p[2]; u8 st[2]; u8 turn; };

/* ───────────────────────── géométrie ───────────────────────── */
static inline int row(int p) { return p / W; }
static inline int col(int p) { return p % W; }

// l'arête entre cases adjacentes a,b est-elle bloquée ?
static inline bool blockedEdge(u32 hw, u32 vw, int a, int b) {
  if (col(a) == col(b)) {                       // verticale -> mur H
    int rr = std::min(row(a), row(b)), c = col(a);
    if (c < C     && ((hw >> (rr * C + c)) & 1)) return true;
    if (c > 0     && ((hw >> (rr * C + c - 1)) & 1)) return true;
  } else {                                      // horizontale -> mur V
    int cc = std::min(col(a), col(b)), r = row(a);
    if (r < R     && ((vw >> (r * C + cc)) & 1)) return true;
    if (r > 0     && ((vw >> ((r - 1) * C + cc)) & 1)) return true;
  }
  return false;
}

static inline int stepOK(u32 hw, u32 vw, int p, int d /*0U 1D 2L 3R*/) {
  int r = row(p), c = col(p);
  if (d == 0) return (r > 0     && !blockedEdge(hw, vw, p, p - W)) ? p - W : -1;
  if (d == 1) return (r < H - 1 && !blockedEdge(hw, vw, p, p + W)) ? p + W : -1;
  if (d == 2) return (c > 0     && !blockedEdge(hw, vw, p, p - 1)) ? p - 1 : -1;
  return          (c < W - 1 && !blockedEdge(hw, vw, p, p + 1)) ? p + 1 : -1;
}

/* ─────────── cache de distances à la demande (mon « lazy ») ───────────
 * clé = hw | vw<<S ; valeur = distances BFS de chaque case vers la rangée
 * but de J1 (rangée 0) et de J2 (rangée H-1), 255 = inatteignable.
 * Table à adressage ouvert, jamais vidée : une branche ne touche qu'une
 * petite fraction de l'univers (mesuré par Sol : 0,3–4,6 %).            */
struct DistCache {
  struct Entry { u64 key; u8 d[2][NCAP]; };
  std::vector<u64> keys; std::vector<u32> vals; std::vector<Entry> data;
  u64 mask = 0; u64 misses = 0, lookups = 0;
  void init(unsigned bits) {
    keys.assign(1ull << bits, ~0ull); vals.resize(1ull << bits);
    mask = (1ull << bits) - 1; data.clear(); data.reserve(1 << 18);
  }
  static inline u64 mix(u64 x) {
    x ^= x >> 33; x *= 0xff51afd7ed558ccdULL; x ^= x >> 33;
    x *= 0xc4ceb9fe1a85ec53ULL; x ^= x >> 33; return x;
  }
  const Entry& get(u32 hw, u32 vw) {
    ++lookups;
    u64 key = (u64)hw | ((u64)vw << SCAP);
    u64 i = mix(key) & mask;
    while (keys[i] != ~0ull) { if (keys[i] == key) return data[vals[i]]; i = (i + 1) & mask; }
    ++misses;
    Entry e; e.key = key;
    for (int g = 0; g < 2; g++) {
      u8* dd = e.d[g]; memset(dd, 255, NCAP);
      int q[NCAP], head = 0, tail = 0;
      int goalRow = g == 0 ? 0 : H - 1;
      for (int c = 0; c < W; c++) { int p = goalRow * W + c; dd[p] = 0; q[tail++] = p; }
      while (head < tail) {
        int p = q[head++];
        for (int d = 0; d < 4; d++) { int z = stepOK(hw, vw, p, d);
          if (z >= 0 && dd[z] == 255) { dd[z] = dd[p] + 1; q[tail++] = z; } }
      }
      // Toujours plein à >75 % ? on refuse d'agrandir en cours de preuve :
      // dimensionner --cache-bits assez grand fait partie du protocole.
    }
    if (data.size() * 4 > (mask + 1) * 3) { fprintf(stderr, "cache distances plein\n"); exit(9); }
    keys[i] = key; vals[i] = (u32)data.size(); data.push_back(e);
    return data.back();
  }
};
static DistCache DC;

/* ───────── porte union-find : un mur ne peut couper que s'il ferme
 *           un cycle dans le treillis des jonctions, bord compris ─────────
 * Jonctions (jr,jc), jr∈[0..H], jc∈[0..W] ; tout le bord est un seul
 * noeud. H(r,c) relie (r+1,c)–(r+1,c+2) ; V(r,c) relie (r,c+1)–(r+2,c+1).
 * Reconstruit à chaque noeud (≤20 unions) : simple et sans annulation.  */
struct DSU {
  int up[(NCAP + 8) * 2]; int n;
  void reset(int nodes) { n = nodes; for (int i = 0; i < n; i++) up[i] = i; }
  int find(int x) { while (up[x] != x) x = up[x] = up[up[x]]; return x; }
  bool uni(int a, int b) { a = find(a); b = find(b); if (a == b) return false; up[a] = b; return true; }
};
static int jid(int jr, int jc) {           // 0 = bord
  if (jr == 0 || jr == H || jc == 0 || jc == W) return 0;
  return 1 + (jr - 1) * (W - 1) + (jc - 1);
}
// un mur = DEUX segments unitaires autour de son milieu : les contacts en T
// (extrémité d'un mur sur le milieu d'un autre) comptent pour l'enclos
static inline void wallEnds(int ori, int r, int c, int& a, int& m, int& b) {
  if (ori == 0) { a = jid(r + 1, c); m = jid(r + 1, c + 1); b = jid(r + 1, c + 2); }
  else          { a = jid(r, c + 1); m = jid(r + 1, c + 1); b = jid(r + 2, c + 1); }
}
static DSU dsu;
static void dsuBuild(u32 hw, u32 vw) {
  dsu.reset(1 + (H - 1) * (W - 1));
  for (int i = 0; i < S; i++) {
    int a, m, b;
    if ((hw >> i) & 1) { wallEnds(0, i / C, i % C, a, m, b); dsu.uni(a, m); dsu.uni(m, b); }
    if ((vw >> i) & 1) { wallEnds(1, i / C, i % C, a, m, b); dsu.uni(a, m); dsu.uni(m, b); }
  }
}

/* ───────────────────── génération de coups ───────────────────── */
static inline bool wallFits(u32 hw, u32 vw, int ori, int r, int c) {
  int i = r * C + c;
  if (((hw >> i) & 1) || ((vw >> i) & 1)) return false;
  if (ori == 0) {
    if (c > 0 && ((hw >> (i - 1)) & 1)) return false;
    if (c < C - 1 && ((hw >> (i + 1)) & 1)) return false;
  } else {
    if (r > 0 && ((vw >> (i - C)) & 1)) return false;
    if (r < R - 1 && ((vw >> (i + C)) & 1)) return false;
  }
  return true;
}

struct Move { u16 id; State s; int ord; };   // id : pion = case ; mur = 256 + ori*S + slot

// gen : pat compté ; ordre = mon heuristique statique (aucune distance requise)
static u64 STALEMATES = 0;
static int gen(const State& s, Move* out, bool useDSU, u64* bfsChecks = nullptr, int target = -1) {
  int n = 0;
  int me = s.turn, op = 1 - me;
  int mp = s.p[me], opp = s.p[op];
  const auto cur = DC.get(s.hw, s.vw);             // COPIE : les get() suivants peuvent réallouer le cache
  auto push = [&](int dest, int prio) {
    Move m; m.id = (u16)dest; m.s = s; m.s.p[me] = (u8)dest; m.s.turn = (u8)op; m.ord = prio;
    out[n++] = m;
  };
  static const int PERP[4][2] = { {2,3},{2,3},{0,1},{0,1} };
  // Ordre eval-complet, schema du solveur de Sol reimplante (sans effet
  // semantique) : score cible-centric de l'ETAT ENFANT = 120*(dO-dT)
  // + 7*(stockT-stockO) + 3*(progT-progO) + urgence +-700/300, puis
  // stocke mover-centric (negatif si le mover n'est pas la cible) pour
  // un tri decroissant unique = leur tri asc aux noeuds adverses.
  int T = target < 0 ? me : target, O = 1 - T;
  auto childScore = [&](const u8* dT_, const u8* dO_, int pT, int pO,
                        int stT, int stO, int childTurn) {
    int dT = dT_[pT], dO = dO_[pO];
    if (dT == 0) return 1000000; if (dO == 0) return -1000000;
    int sc = (dO - dT) * 120 + (stT - stO) * 7;
    int progT = T == 0 ? (H - 1 - row(pT)) : row(pT);
    int progO = O == 0 ? (H - 1 - row(pO)) : row(pO);
    sc += (progT - progO) * 3;
    if (dT == 1) sc += childTurn == T ? 700 : 300;
    if (dO == 1) sc -= childTurn == O ? 700 : 300;
    return sc;
  };
  auto pawnPrio = [&](int dest, int bonus) {
    int pT = me == T ? dest : s.p[T], pO = me == O ? dest : s.p[O];
    int sc = childScore(cur.d[T], cur.d[O], pT, pO, s.st[T], s.st[O], op) + bonus;
    return me == T ? sc : -sc;
  };
  for (int d = 0; d < 4; d++) {
    int z = stepOK(s.hw, s.vw, mp, d);
    if (z < 0) continue;
    if (z != opp) { push(z, pawnPrio(z, 0)); continue; }
    int j = stepOK(s.hw, s.vw, opp, d);
    if (j >= 0) push(j, pawnPrio(j, me == T ? 40 : -40));
    else for (int k = 0; k < 2; k++) {
      int z2 = stepOK(s.hw, s.vw, opp, PERP[d][k]);
      if (z2 >= 0) push(z2, pawnPrio(z2, me == T ? 20 : -20));
    }
  }
  if (s.st[me] > 0) {
    if (useDSU) dsuBuild(s.hw, s.vw);
    for (int ori = 0; ori < 2; ori++) for (int i = 0; i < S; i++) {
      int r = i / C, c = i % C;
      if (!wallFits(s.hw, s.vw, ori, r, c)) continue;
      u32 nh = s.hw | (ori == 0 ? (1u << i) : 0);
      u32 nv = s.vw | (ori == 1 ? (1u << i) : 0);
      if (useDSU) {
        // le chemin a–m–b ferme un cycle ssi deux de ses trois noeuds sont
        // déjà connectés (trois find, aucune union : le DSU reste propre)
        int a, m, b2; wallEnds(ori, r, c, a, m, b2);
        int fa = dsu.find(a), fm = dsu.find(m), fb = dsu.find(b2);
        if (fa == fm || fm == fb || fa == fb) {    // cycle -> vérif BFS
          if (bfsChecks) ++*bfsChecks;
          const auto& e = DC.get(nh, nv);
          if (e.d[0][s.p[0]] == 255 || e.d[1][s.p[1]] == 255) continue;
        }
      } else {
        const auto& e = DC.get(nh, nv);
        if (e.d[0][s.p[0]] == 255 || e.d[1][s.p[1]] == 255) continue;
      }
      Move m; m.id = (u16)(256 + ori * S + i); m.s = s;
      m.s.hw = nh; m.s.vw = nv; m.s.st[me]--; m.s.turn = (u8)op;
      // score cible-centric de l'enfant + tactique murale de Sol
      // (80*allonge_adverse - 55*allonge_propre, signee vers la cible)
      const auto& nxt = DC.get(nh, nv);
      int sc = childScore(nxt.d[T], nxt.d[O], s.p[T], s.p[O],
                          s.st[T] - (me == T), s.st[O] - (me == O), op);
      int dOpp = (int)nxt.d[op][opp] - (int)cur.d[op][opp];
      int dMe  = (int)nxt.d[me][mp]  - (int)cur.d[me][mp];
      int tac = 80 * dOpp - 55 * dMe;
      if (me != T) tac = -tac;
      sc += tac;
      m.ord = me == T ? sc : -sc;
      out[n++] = m;
    }
  }
  if (n == 0) ++STALEMATES;
  std::stable_sort(out, out + n, [](const Move& a, const Move& b) { return a.ord > b.ord; });
  return n;
}

/* ─────────────────────── symétrie miroir ─────────────────────── */
static u8 MIRSQ[NCAP], ROTSQ[NCAP]; static u16 MIRW[2 * SCAP], ROTW[2 * SCAP];
static void buildMirror() {
  for (int p = 0; p < N; p++) {
    MIRSQ[p] = (u8)(row(p) * W + (W - 1 - col(p)));
    ROTSQ[p] = (u8)((H - 1 - row(p)) * W + (W - 1 - col(p)));
  }
  for (int ori = 0; ori < 2; ori++) for (int i = 0; i < S; i++) {
    MIRW[ori * S + i] = (u16)((i / C) * C + (C - 1 - i % C));
    ROTW[ori * S + i] = (u16)((R - 1 - i / C) * C + (C - 1 - i % C));
  }
}
static inline void mirrorMasks(u32 hw, u32 vw, u32& mh, u32& mv) {
  mh = 0; mv = 0;
  for (int i = 0; i < S; i++) {
    if ((hw >> i) & 1) mh |= 1u << MIRW[i];
    if ((vw >> i) & 1) mv |= 1u << MIRW[S + i];
  }
}
// rotation 180 degres : orientation des murs conservee ; joueurs, stocks,
// trait et CIBLE echanges (la rangee but de J1 devient celle de J2)
static inline void rotMasks(u32 hw, u32 vw, u32& rh, u32& rv) {
  rh = 0; rv = 0;
  for (int i = 0; i < S; i++) {
    if ((hw >> i) & 1) rh |= 1u << ROTW[i];
    if ((vw >> i) & 1) rv |= 1u << ROTW[S + i];
  }
}
static inline u64 packKey(u32 hw, u32 vw, u8 p0, u8 p1, u8 s0, u8 s1, u8 turn, u8 target) {
  u64 x = hw; x = (x << SCAP) | vw; x = (x << 5) | p0; x = (x << 5) | p1;
  x = (x << 4) | s0; x = (x << 4) | s1; x = (x << 1) | turn; x = (x << 1) | target;
  return x + 1;
}
static int SYMMODE = 2;
static inline u64 canonKey(const State& s, int target, bool useMirror) {
  u64 a = packKey(s.hw, s.vw, s.p[0], s.p[1], s.st[0], s.st[1], s.turn, (u8)target);
  if (!useMirror || SYMMODE == 0) return a;
  u32 mh, mv; mirrorMasks(s.hw, s.vw, mh, mv);
  u64 b = packKey(mh, mv, MIRSQ[s.p[0]], MIRSQ[s.p[1]], s.st[0], s.st[1], s.turn, (u8)target);
  u64 best = a < b ? a : b;
  if (SYMMODE >= 2) {
    u32 rh, rv; rotMasks(s.hw, s.vw, rh, rv);
    u64 c = packKey(rh, rv, ROTSQ[s.p[1]], ROTSQ[s.p[0]], s.st[1], s.st[0],
                    (u8)(1 - s.turn), (u8)(1 - target));
    u32 rmh, rmv; mirrorMasks(rh, rv, rmh, rmv);
    u64 d = packKey(rmh, rmv, MIRSQ[ROTSQ[s.p[1]]], MIRSQ[ROTSQ[s.p[0]]], s.st[1], s.st[0],
                    (u8)(1 - s.turn), (u8)(1 - target));
    if (c < best) best = c; if (d < best) best = d;
  }
  return best;
}

/* ─────────────── TT à faits monotones (mon implémentation) ───────────────
 * minWin : plus petite profondeur prouvée vraie ; maxFail : plus grande
 * prouvée fausse. Invariant minWin > maxFail vérifié à chaque écriture.  */
struct TT {
  std::vector<u64> key; std::vector<u32> meta;   // meta : minWin | maxFail<<8 | move<<16
  u64 mask = 0; u64 stores = 0, hits = 0;
  void init(unsigned bits) { key.assign(1ull << bits, 0); meta.assign(1ull << bits, 0xff); mask = (1ull << bits) - 1; }
  bool save(const std::string& f) const {
    std::string tmp = f + ".tmp";
    FILE* fp = fopen(tmp.c_str(), "wb"); if (!fp) return false;
    u64 n = mask + 1; fwrite(&n, 8, 1, fp);
    fwrite(key.data(), 8, n, fp); fwrite(meta.data(), 4, n, fp);
    fclose(fp);
    return rename(tmp.c_str(), f.c_str()) == 0;   // atomique : jamais de fichier tronque sous le nom final
  }
  bool load(const std::string& f) {
    FILE* fp = fopen(f.c_str(), "rb"); if (!fp) return false;
    u64 n = 0; if (fread(&n, 8, 1, fp) != 1 || n != mask + 1) { fclose(fp); return false; }
    size_t a = fread(key.data(), 8, n, fp), b = fread(meta.data(), 4, n, fp);
    fclose(fp); return a == n && b == n;
  }
  static inline u64 mix(u64 x) { return DistCache::mix(x); }
  inline void slots(u64 k, u64& a, u64& b) const { u64 h = mix(k); a = h & mask; b = (h >> 21) & mask; if (a == b) b = (b + 1) & mask; }
  bool probe(u64 k, int d, bool& val, u16& mv) const {
    u64 a, b; slots(k, a, b);
    for (u64 i : { a, b }) if (key[i] == k) {
      u32 m = meta[i]; mv = (u16)(m >> 16);
      int mw = m & 0xff, mf = (m >> 8) & 0xff;
      if (mw != 0xff && d >= mw) { val = true; return true; }
      if (d <= mf) { val = false; return true; }
      return false;
    }
    mv = 0xffff; return false;
  }
  void store(u64 k, int d, bool val, u16 mv) {
    u64 a, b; slots(k, a, b);
    u64 i = key[a] == k ? a : key[b] == k ? b : (meta[a] == 0xffu && key[a] == 0 ? a : (key[b] == 0 ? b : ((mix(k) & 1) ? a : b)));
    int mw = 0xff, mf = 0; u16 bm = 0xffff;
    if (key[i] == k) { u32 m = meta[i]; mw = m & 0xff; mf = (m >> 8) & 0xff; bm = (u16)(m >> 16); }
    else key[i] = k;
    if (val) mw = std::min(mw, d); else mf = std::max(mf, d);
    if (mw != 0xff && mf >= mw) { fprintf(stderr, "TT incohérente (mw=%d mf=%d)\n", mw, mf); exit(8); }
    if (mv != 0xffff) bm = mv;
    meta[i] = (u32)mw | ((u32)mf << 8) | ((u32)bm << 16);
    ++stores;
  }
};
static TT tt;

/* ─────────────── amorçage par CertMap certifiée (--tt-seed) ───────────────
 * P2 d'IDEES_SWEEP : les mémos d'extraction (work/memo_*.bin, états certifiés
 * « Win(J1) en <= rem », vérifiés exhaustivement par qverify) servent de
 * tablebase partagée en lecture seule. Fait monotone : au nœud s avec budget
 * normalisé d, un hit rem <= d prouve Win=true sans expansion. Sonde aussi la
 * clé miroir (automorphisme prouvé par les 17 runs qverify miroir). Sans
 * --tt-seed, comportement STRICTEMENT identique (arbre au nœud près).       */
// Table UNIQUE fusionnée : slot u64 = (clé << 6) | rem, vide = 0 (les clés
// packKey sont >= 1 donc tout slot occupé est non nul ; clés <= 2^54, le
// décalage de 6 tient dans u64). Doublons inter-mémos : rem minimal gardé.
// Une sonde = ~1 défaut de cache (la v1 à 16 tables séquentielles coûtait
// 2,4x le temps de recherche — mesuré sur H00).
static std::vector<u64> SEEDS;                 // slots (clé<<6|rem) ; vide si pas de seed
static u64 SEED_MASK = 0, SEED_COUNT = 0;
static u64 SEED_PROBES = 0, SEED_HITS = 0, SEED_LOOSE = 0;
static bool initSeeds(const std::vector<std::string>& files) {
  u64 total = 0;
  for (const auto& f : files) {
    FILE* fp = fopen(f.c_str(), "rb"); if (!fp) return false;
    u64 n = 0, c = 0;
    if (fread(&n, 8, 1, fp) != 1 || fread(&c, 8, 1, fp) != 1) { fclose(fp); return false; }
    fclose(fp); total += c;
  }
  unsigned bits = 20;
  while ((1ull << bits) < total * 5 / 3) bits++;
  SEEDS.assign(1ull << bits, 0); SEED_MASK = (1ull << bits) - 1;
  const u64 CH = 1 << 20;
  std::vector<u64> kb(CH); std::vector<u32> vb(CH);
  for (const auto& f : files) {
    FILE* fp = fopen(f.c_str(), "rb"); if (!fp) return false;
    u64 n = 0, c = 0;
    if (fread(&n, 8, 1, fp) != 1 || fread(&c, 8, 1, fp) != 1 || !n || (n & (n - 1))) { fclose(fp); return false; }
    for (u64 off = 0; off < n; off += CH) {
      u64 m = std::min(CH, n - off);
      _fseeki64(fp, 16 + 8 * (long long)off, SEEK_SET);
      if (fread(kb.data(), 8, m, fp) != m) { fclose(fp); return false; }
      _fseeki64(fp, 16 + 8 * (long long)n + 4 * (long long)off, SEEK_SET);
      if (fread(vb.data(), 4, m, fp) != m) { fclose(fp); return false; }
      for (u64 j = 0; j < m; j++) {
        u64 k = kb[j]; if (!k) continue;
        u64 rem = vb[j] & 63;
        u64 i = TT::mix(k) & SEED_MASK;
        while (SEEDS[i]) {
          if ((SEEDS[i] >> 6) == k) { if (rem < (SEEDS[i] & 63)) SEEDS[i] = (k << 6) | rem; goto next; }
          i = (i + 1) & SEED_MASK;
        }
        SEEDS[i] = (k << 6) | rem; ++SEED_COUNT;
        next:;
      }
    }
    fclose(fp);
  }
  return true;
}
static inline bool seedProbe(u64 k, int& rem) {
  u64 i = TT::mix(k) & SEED_MASK;
  while (SEEDS[i]) {
    if ((SEEDS[i] >> 6) == k) { rem = (int)(SEEDS[i] & 63); return true; }
    i = (i + 1) & SEED_MASK;
  }
  return false;
}

/* ───────────────────────── recherche ─────────────────────────
 * parité (re-dérivée) : la cible ne conclut que juste après son propre
 * coup ; les budgets utiles consomment un nombre impair de plis si c'est
 * son trait, pair sinon.                                                */
static inline int relevantDepth(int turn, int target, int d) {
  if (d <= 0) return d;
  bool odd = d & 1;
  if (turn == target) return odd ? d : d - 1;
  return odd ? d - 1 : d;
}

static u64 NODES = 0, BFS_CHECKS = 0;
static Clock::time_point DEADLINE; static bool HAS_DEADLINE = false;
static bool USE_TT = true, USE_MIRROR = true, USE_DSU = true, USE_DBOUND = true;
static u64 NODE_LIMIT = ~0ull;
struct Abort {};

static bool win(const State& s, int target, int d, std::vector<std::array<Move, 64>>& stk, int ply) {
  if (++NODES > NODE_LIMIT) throw Abort{};
  if (HAS_DEADLINE && (NODES & 16383ULL) == 0 && Clock::now() >= DEADLINE) throw Abort{};
  if (row(s.p[0]) == 0)     return target == 0;
  if (row(s.p[1]) == H - 1) return target == 1;
  d = relevantDepth(s.turn, target, d);
  if (d <= 0) return false;
  if (USE_DBOUND) {
    const auto& e = DC.get(s.hw, s.vw);
    int d0 = e.d[target][s.p[target]];
    int myTurns = (s.turn == target) ? (d + 1) / 2 : d / 2;
    if ((d0 + 1) / 2 > myTurns) return false;      // lemme : ≥ ⌈d0/2⌉ coups propres
  }
  u64 k = 0; bool cached; u16 hint = 0xffff;
  if (USE_TT) {
    k = canonKey(s, target, USE_MIRROR);
    if (tt.probe(k, d, cached, hint)) { ++tt.hits; return cached; }
  }
  if (target == 0 && !SEEDS.empty()) {
    ++SEED_PROBES;
    int srem;
    u64 rk = packKey(s.hw, s.vw, s.p[0], s.p[1], s.st[0], s.st[1], s.turn, 0);
    bool sh = seedProbe(rk, srem);
    if (!sh) {
      u32 mh, mvv; mirrorMasks(s.hw, s.vw, mh, mvv);
      u64 mk = packKey(mh, mvv, MIRSQ[s.p[0]], MIRSQ[s.p[1]], s.st[0], s.st[1], s.turn, 0);
      sh = seedProbe(mk, srem);
    }
    if (sh) {
      if (srem <= d) {
        ++SEED_HITS;
        if (USE_TT) tt.store(k, srem, true, 0xffff);
        return true;
      }
      ++SEED_LOOSE;
    }
  }
  auto& ch = stk[ply];
  int n = gen(s, ch.data(), USE_DSU, &BFS_CHECKS, target);
  if (n == 0) { if (USE_TT) tt.store(k, d, false, 0xffff); return false; }
  if (hint != 0xffff) for (int i = 0; i < n; i++) if (ch[i].id == hint) { std::swap(ch[0], ch[i]); break; }
  bool res; u16 best = 0xffff; u64 hardest = 0;
  if (s.turn == target) {
    res = false;
    for (int i = 0; i < n; i++) {
      u64 b4 = NODES;
      if (win(ch[i].s, target, d - 1, stk, ply + 1)) { res = true; best = ch[i].id; break; }
      u64 c2 = NODES - b4; if (c2 > hardest) { hardest = c2; best = ch[i].id; }
    }
  } else {
    res = true;
    for (int i = 0; i < n; i++) {
      u64 b4 = NODES;
      if (!win(ch[i].s, target, d - 1, stk, ply + 1)) { res = false; best = ch[i].id; break; }
      u64 c2 = NODES - b4; if (c2 > hardest) { hardest = c2; best = ch[i].id; }
    }
  }
  if (USE_TT) tt.store(k, d, res, best);
  return res;
}

/* ───────────────────────── pilotes ───────────────────────── */
static State initial() {
  State s; s.hw = s.vw = 0;
  s.p[0] = (u8)((H - 1) * W + W / 2); s.p[1] = (u8)(W / 2);
  s.st[0] = s.st[1] = (u8)WALLS; s.turn = 0; return s;
}
static std::string mvName(u16 id) {
  char b[24];
  if (id < 256) { snprintf(b, 24, "P(%d,%d)", id / W, id % W); }
  else { int w = id - 256; snprintf(b, 24, "%c(%d,%d)", w / S ? 'V' : 'H', (w % S) / C, (w % S) % C); }
  return b;
}
static int findMove(const State& s, const std::string& name, State& outState) {
  std::array<Move, 64> ch; int n = gen(s, ch.data(), USE_DSU);
  for (int i = 0; i < n; i++) if (mvName(ch[i].id) == name) { outState = ch[i].s; return (int)ch[i].id; }
  return -1;
}

// vérification interne : la porte DSU rend exactement les mêmes verdicts
// de légalité que le BFS pur, sur des états aléatoires saturés en murs
static int selftest(int games, int plies, u64 seed) {
  std::mt19937_64 rng(seed);
  u64 verdicts = 0; int bad = 0;
  for (int g = 0; g < games; g++) {
    State s = initial();
    for (int ply = 0; ply < plies; ply++) {
      if (row(s.p[0]) == 0 || row(s.p[1]) == H - 1) break;
      // compare les deux ensembles de coups
      std::array<Move, 64> a, b; 
      int na = gen(s, a.data(), true), nb = gen(s, b.data(), false);
      std::vector<u16> ia, ib;
      for (int i = 0; i < na; i++) ia.push_back(a[i].id);
      for (int i = 0; i < nb; i++) ib.push_back(b[i].id);
      std::sort(ia.begin(), ia.end()); std::sort(ib.begin(), ib.end());
      verdicts += std::max(na, nb);
      if (ia != ib) { bad++; break; }
      // avance, murs favorisés pour saturer
      std::vector<int> walls;
      for (int i = 0; i < na; i++) if (a[i].id >= 256) walls.push_back(i);
      int pick = (!walls.empty() && (rng() % 10) < 8) ? walls[rng() % walls.size()] : (int)(rng() % na);
      s = a[pick].s;
    }
  }
  printf("{\"selftest\":{\"games\":%d,\"verdicts\":%llu,\"divergences\":%d}}\n",
         games, (unsigned long long)verdicts, bad);
  return bad ? 1 : 0;
}

int main(int argc, char** argv) {
  W = 3; H = 9; WALLS = 10;
  unsigned ttBits = 26, cacheBits = 22;
  int maxDepth = 60, startDepth = 1, target = 0;
  double seconds = 1e9;
  std::string mode = "solve", firstMove, secondMove, ttFile;
  std::vector<std::string> seedFiles;
  int games = 200, plies = 200; u64 seed = 1; u64 nodeLimit = 0;
  bool emitStates = false; (void)emitStates;
  for (int i = 1; i < argc; i++) {
    std::string a = argv[i];
    auto v = [&](auto& x) { std::string s2 = argv[++i]; 
      if constexpr (std::is_same_v<std::decay_t<decltype(x)>, std::string>) x = s2; else x = atoll(s2.c_str()); };
    if (a == "--width") v(W); else if (a == "--height") v(H); else if (a == "--walls") v(WALLS);
    else if (a == "--tt-bits") v(ttBits); else if (a == "--cache-bits") v(cacheBits);
    else if (a == "--max-depth") v(maxDepth); else if (a == "--start-depth") v(startDepth);
    else if (a == "--target") { int t; v(t); target = t - 1; }
    else if (a == "--seconds") { std::string s2 = argv[++i]; seconds = atof(s2.c_str()); }
    else if (a == "--mode") v(mode);
    else if (a == "--first") v(firstMove); else if (a == "--second") v(secondMove);
    else if (a == "--games") v(games); else if (a == "--plies") v(plies); else if (a == "--seed") v(seed);
    else if (a == "--node-limit") v(nodeLimit);
    else if (a == "--tt-file") v(ttFile);
    else if (a == "--tt-seed") { std::string f; v(f); seedFiles.push_back(f); }
    else if (a == "--sym") { int m; v(m); SYMMODE = (int)m; }
    else if (a == "--no-tt") USE_TT = false;
    else if (a == "--no-mirror") USE_MIRROR = false;
    else if (a == "--no-dsu") USE_DSU = false;
    else if (a == "--no-dbound") USE_DBOUND = false;
    else { fprintf(stderr, "argument inconnu : %s\n", a.c_str()); return 2; }
  }
  C = W - 1; R = H - 1; S = C * R; N = W * H;
  if (N > NCAP || S > SCAP) { fprintf(stderr, "dimensions hors capacité\n"); return 2; }
  buildMirror();
  DC.init(cacheBits);
  if (nodeLimit) NODE_LIMIT = nodeLimit;
  if (!seedFiles.empty()) {
    if (!initSeeds(seedFiles)) { fprintf(stderr, "tt-seed illisible\n"); return 2; }
    fprintf(stderr, "tt-seed : %zu fichiers, %llu entrées, %llu slots\n",
            seedFiles.size(), (unsigned long long)SEED_COUNT,
            (unsigned long long)(SEED_MASK + 1));
  }

  if (mode == "selftest") return selftest(games, plies, seed);

  if (mode == "emit") {                       // requêtes aléatoires pour diff croisé
    std::mt19937_64 rng(seed);
    for (int g = 0; g < games; g++) {
      State s2 = initial();
      int stop = 2 + (int)(rng() % plies);
      for (int ply = 0; ply < stop; ply++) {
        if (row(s2.p[0]) == 0 || row(s2.p[1]) == H - 1) break;
        std::array<Move, 64> ch; int n = gen(s2, ch.data(), true);
        if (!n) break;
        std::vector<int> walls2;
        for (int i = 0; i < n; i++) if (ch[i].id >= 256) walls2.push_back(i);
        int pick = (!walls2.empty() && (rng() % 10) < 6) ? walls2[rng() % walls2.size()] : (int)(rng() % n);
        s2 = ch[pick].s;
      }
      if (row(s2.p[0]) == 0 || row(s2.p[1]) == H - 1) { g--; continue; }
      int target2 = (int)(rng() % 2), depth = 1 + (int)(rng() % 13);
      printf("%d %d %d %d %d %u %u %d %d\n", s2.p[0], s2.p[1], s2.st[0], s2.st[1],
             s2.turn, s2.hw, s2.vw, target2, depth);
    }
    return 0;
  }

  if (mode == "query") {                      // répond aux requêtes TSV
    tt.init(ttBits);
    std::vector<std::array<Move, 64>> stk(64);
    int p1, p2, r1, r2, turn, tg, depth; unsigned long long hw2, vw2; size_t idx = 0;
    while (scanf("%d %d %d %d %d %llu %llu %d %d", &p1, &p2, &r1, &r2, &turn, &hw2, &vw2, &tg, &depth) == 9) {
      State s2; s2.hw = (u32)hw2; s2.vw = (u32)vw2; s2.p[0] = (u8)p1; s2.p[1] = (u8)p2;
      s2.st[0] = (u8)r1; s2.st[1] = (u8)r2; s2.turn = (u8)turn;
      bool ok = win(s2, tg, depth, stk, 0);
      printf("%zu %d\n", idx++, ok ? 1 : 0);
    }
    return 0;
  }


  if (mode == "list") {                       // liste les coups + classes miroir
    State s = initial();
    if (!firstMove.empty()) { State t2; if (findMove(s, firstMove, t2) < 0) { fprintf(stderr, "coup inconnu\n"); return 2; } s = t2; }
    std::array<Move, 64> ch; int n = gen(s, ch.data(), USE_DSU);
    std::vector<u16> ids; for (int i = 0; i < n; i++) ids.push_back(ch[i].id);
    std::sort(ids.begin(), ids.end());
    // partition par clé canonique miroir de l'état ENFANT
    std::vector<std::pair<u64, u16>> classes;
    for (int i = 0; i < n; i++) {
      u64 k = canonKey(ch[i].s, target, true);
      bool found = false;
      for (auto& c2 : classes) if (c2.first == k) { found = true; break; }
      if (!found) classes.push_back({ k, ch[i].id });
    }
    printf("{\"moves\":%d,\"classes\":%d,\"reps\":[", n, (int)classes.size());
    for (size_t i = 0; i < classes.size(); i++)
      printf("%s\"%s\"", i ? "," : "", mvName(classes[i].second).c_str());
    printf("]}\n");
    return 0;
  }

  if (mode == "branch" || mode == "solve") {
    tt.init(ttBits);
    if (!ttFile.empty() && tt.load(ttFile)) fprintf(stderr, "TT reprise\n");
    State s = initial();
    std::string fixed;
    if (!firstMove.empty()) { State t2; if (findMove(s, firstMove, t2) < 0) { fprintf(stderr, "coup 1 inconnu\n"); return 2; } s = t2; fixed = firstMove; }
    if (!secondMove.empty()) { State t2; if (findMove(s, secondMove, t2) < 0) { fprintf(stderr, "coup 2 inconnu\n"); return 2; } s = t2; fixed += "," + secondMove; }
    std::vector<std::array<Move, 64>> stk(maxDepth + 4);
    auto t0 = Clock::now();
    if (seconds < 1e8) { DEADLINE = t0 + std::chrono::duration_cast<Clock::duration>(std::chrono::duration<double>(seconds)); HAS_DEADLINE = true; }
    int provedDepth = -1; bool timeout = false;
    for (int d = startDepth; d <= maxDepth; d++) {
      int rd = relevantDepth(s.turn, target, d);
      if (rd < d && d > startDepth) continue;          // profondeur équivalente déjà testée
      bool ok = false;
      try { ok = win(s, target, rd, stk, 0); }
      catch (Abort&) { timeout = true; break; }
      double el = std::chrono::duration<double>(Clock::now() - t0).count();
      fprintf(stderr, "d=%d ok=%d nodes=%llu bfs=%llu cache=%llu el=%.1fs\n",
              rd, ok, (unsigned long long)NODES, (unsigned long long)BFS_CHECKS,
              (unsigned long long)DC.misses, el);
      if (ok) { provedDepth = rd; break; }
      if (el > seconds) { timeout = true; break; }
    }
    double el = std::chrono::duration<double>(Clock::now() - t0).count();
    printf("{\"mode\":\"%s\",\"w\":%d,\"h\":%d,\"walls\":%d,\"fixed\":\"%s\",\"target\":%d,"
           "\"proved\":%s,\"depth\":%d,\"nodes\":%llu,\"tt_stores\":%llu,\"tt_hits\":%llu,"
           "\"dist_configs\":%llu,\"bfs_legality\":%llu,\"stalemates\":%llu,"
           "\"seed_entries\":%llu,\"seed_probes\":%llu,\"seed_hits\":%llu,\"seed_loose\":%llu,"
           "\"timeout\":%s,\"seconds\":%.3f}\n",
           mode.c_str(), W, H, WALLS, fixed.c_str(), target + 1,
           provedDepth >= 0 ? "true" : "false", provedDepth,
           (unsigned long long)NODES, (unsigned long long)tt.stores, (unsigned long long)tt.hits,
           (unsigned long long)DC.misses, (unsigned long long)BFS_CHECKS,
           (unsigned long long)STALEMATES,
           (unsigned long long)SEED_COUNT, (unsigned long long)SEED_PROBES, (unsigned long long)SEED_HITS,
           (unsigned long long)SEED_LOOSE, timeout ? "true" : "false", el);
    if (!ttFile.empty()) tt.save(ttFile);
    return provedDepth >= 0 ? 0 : (timeout ? 3 : 1);
  }

  fprintf(stderr, "mode inconnu : %s\n", mode.c_str());
  return 2;
}
