// qverify.cpp — vérificateur C++ EXHAUSTIF du certificat 3×9×10.
//
// Port direct de la logique de verify_cert.py (lignée clean-room qref.mjs :
// règles réimplémentées depuis docs/RULES.md). N'inclut volontairement PAS
// qsolve.cpp : le vérificateur ne partage aucun code avec les solveurs qui
// ont produit le certificat.
//
// Vérifie, pour une part (réponse canonique fixée) : depuis l'état après
// P(7,1) + réponse, un DFS exhaustif explore TOUTES les suites de coups de
// J2 ; à chaque état où J1 est au trait, la part doit fournir un coup légal ;
// toute feuille doit être une victoire de J1 (rangée 0) en <= 35 plis au
// total. Mémo : état -> pli maximal auquel la vérification a réussi (gagner
// avec moins de budget implique gagner avec plus).
//
//   qverify --part certparts/H10.bin --reply "H(1,0)" [--mirror] [--memo-bits 26]
//
// --mirror : vérifie la classe JUMELLE : la réponse est le miroir de --reply
// et chaque lookup dans la part applique le miroir gauche-droite à l'état
// (les parts ne couvrent que les 18 réponses canoniques).
//
// Build : g++ -O3 -std=c++20 -o qverify qverify.cpp

#include <cstdint>
#include <cstdio>
#include <cstring>
#include <cstdlib>
#include <string>
#include <vector>
#include <algorithm>
#include <chrono>

using u8 = uint8_t; using u16 = uint16_t; using u32 = uint32_t; using u64 = uint64_t;

static constexpr int W = 3, H = 9, WALLS = 10, BUDGET = 35;
static constexpr int C = W - 1, R = H - 1, S = C * R;   // S = 16 ancres
static constexpr int VW_FIELD = 18;                     // largeur de champ historique du format

struct St { u32 hw, vw; u8 p0, p1, s0, s1, turn; };

static inline int rowOf(int p) { return p / W; }
static inline int colOf(int p) { return p % W; }

static inline bool blocked(u32 hw, u32 vw, int a, int b) {
  if (colOf(a) == colOf(b)) {
    int rr = std::min(rowOf(a), rowOf(b)), c = colOf(a);
    if (c < C && ((hw >> (rr * C + c)) & 1)) return true;
    if (c > 0 && ((hw >> (rr * C + c - 1)) & 1)) return true;
    return false;
  }
  int cc = std::min(colOf(a), colOf(b)), r = rowOf(a);
  if (r < R && ((vw >> (r * C + cc)) & 1)) return true;
  if (r > 0 && ((vw >> ((r - 1) * C + cc)) & 1)) return true;
  return false;
}

static inline int stepTo(u32 hw, u32 vw, int p, int d) {  // 0 haut 1 bas 2 gauche 3 droite
  int r = rowOf(p), c = colOf(p);
  if (d == 0) return (r > 0 && !blocked(hw, vw, p, p - W)) ? p - W : -1;
  if (d == 1) return (r < H - 1 && !blocked(hw, vw, p, p + W)) ? p + W : -1;
  if (d == 2) return (c > 0 && !blocked(hw, vw, p, p - 1)) ? p - 1 : -1;
  return (c < W - 1 && !blocked(hw, vw, p, p + 1)) ? p + 1 : -1;
}

static bool reaches(u32 hw, u32 vw, int p, int goalRow) {
  if (rowOf(p) == goalRow) return true;
  bool seen[W * H] = {};
  int st[W * H], sp = 0;
  seen[p] = true; st[sp++] = p;
  while (sp) {
    int x = st[--sp];
    for (int d = 0; d < 4; d++) {
      int z = stepTo(hw, vw, x, d);
      if (z >= 0 && !seen[z]) {
        if (rowOf(z) == goalRow) return true;
        seen[z] = true; st[sp++] = z;
      }
    }
  }
  return false;
}

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

// coup encodé comme dans le certificat : <256 case pion ; 256 + ori*S + slot
struct MoveList { u16 m[64]; int n = 0; };
static const int PERP[4][2] = { {2,3},{2,3},{0,1},{0,1} };

static void legalMoves(const St& s, MoveList& out) {
  out.n = 0;
  int me = s.turn ? s.p1 : s.p0, op = s.turn ? s.p0 : s.p1;
  for (int d = 0; d < 4; d++) {
    int z = stepTo(s.hw, s.vw, me, d);
    if (z < 0) continue;
    if (z != op) { out.m[out.n++] = (u16)z; continue; }
    int j = stepTo(s.hw, s.vw, op, d);
    if (j >= 0) out.m[out.n++] = (u16)j;
    else for (int k = 0; k < 2; k++) {
      int z2 = stepTo(s.hw, s.vw, op, PERP[d][k]);
      if (z2 >= 0) out.m[out.n++] = (u16)z2;
    }
  }
  int stock = s.turn ? s.s1 : s.s0;
  if (stock > 0) {
    for (int ori = 0; ori < 2; ori++) for (int i = 0; i < S; i++) {
      int r = i / C, c = i % C;
      if (!wallFits(s.hw, s.vw, ori, r, c)) continue;
      u32 nh = s.hw | (ori == 0 ? (1u << i) : 0);
      u32 nv = s.vw | (ori == 1 ? (1u << i) : 0);
      if (!reaches(nh, nv, s.p0, 0) || !reaches(nh, nv, s.p1, H - 1)) continue;
      out.m[out.n++] = (u16)(256 + ori * S + i);
    }
  }
}

static St applyMove(const St& s, u16 mv) {
  St t = s;
  if (mv < 256) { if (s.turn) t.p1 = (u8)mv; else t.p0 = (u8)mv; }
  else {
    int w = mv - 256, ori = w / S, i = w % S;
    if (ori == 0) t.hw |= 1u << i; else t.vw |= 1u << i;
    if (s.turn) t.s1--; else t.s0--;
  }
  t.turn = 1 - s.turn;
  return t;
}

/* clé du certificat (identique à verify_cert.py / qcert2 rawKey - 1) */
static inline u64 keyOf(const St& s) {
  u64 x = s.hw;
  x = (x << VW_FIELD) | s.vw;
  x = (x << 5) | s.p0;
  x = (x << 5) | s.p1;
  x = (x << 4) | s.s0;
  x = (x << 4) | s.s1;
  x = (x << 1) | s.turn;
  x = (x << 1) | 0;
  return x;
}

/* miroir gauche-droite */
static inline int mirSq(int p) { return rowOf(p) * W + (W - 1 - colOf(p)); }
static inline u32 mirMask(u32 m) {
  u32 out = 0;
  for (int i = 0; i < S; i++) if ((m >> i) & 1) out |= 1u << ((i / C) * C + (C - 1 - i % C));
  return out;
}
static inline St mirState(const St& s) {
  St t = s;
  t.hw = mirMask(s.hw); t.vw = mirMask(s.vw);
  t.p0 = (u8)mirSq(s.p0); t.p1 = (u8)mirSq(s.p1);
  return t;
}
static inline u16 mirMove(u16 mv) {
  if (mv < 256) return (u16)mirSq(mv);
  int w = mv - 256, ori = w / S, i = w % S;
  return (u16)(256 + ori * S + (i / C) * C + (C - 1 - i % C));
}

/* part triée + recherche dichotomique */
static std::vector<u64> PART;
static bool USE_MIRROR_LOOKUP = false;
static u64 LOOKUPS = 0;
static int certMove(const St& s) {
  St q = USE_MIRROR_LOOKUP ? mirState(s) : s;
  u64 k = keyOf(q) << 9;
  ++LOOKUPS;
  auto it = std::lower_bound(PART.begin(), PART.end(), k);
  if (it != PART.end() && (*it >> 9) == (k >> 9)) {
    int mv = (int)(*it & 0x1ff);
    return USE_MIRROR_LOOKUP ? mirMove((u16)mv) : mv;
  }
  return -1;
}

/* mémo : état -> pli MAXIMAL auquel la vérification a réussi */
struct Memo {
  std::vector<u64> keys; std::vector<u8> ply;
  u64 mask; u64 count = 0;
  void init(unsigned bits) { keys.assign(1ull << bits, 0); ply.assign(1ull << bits, 0); mask = (1ull << bits) - 1; }
  static inline u64 mix(u64 x) {
    x ^= x >> 33; x *= 0xff51afd7ed558ccdULL; x ^= x >> 33;
    x *= 0xc4ceb9fe1a85ec53ULL; x ^= x >> 33; return x;
  }
  int get(u64 k) const {
    u64 i = mix(k) & mask;
    while (keys[i]) { if (keys[i] == k) return ply[i]; i = (i + 1) & mask; }
    return -1;
  }
  void put(u64 k, int p) {
    u64 i = mix(k) & mask;
    while (keys[i]) { if (keys[i] == k) { if (p > ply[i]) ply[i] = (u8)p; return; } i = (i + 1) & mask; }
    if ((count + 1) * 5 > (mask + 1) * 4) { fprintf(stderr, "mémo pleine — relancer avec --memo-bits plus grand\n"); exit(9); }
    keys[i] = k; ply[i] = (u8)p; ++count;
  }
};
static Memo memo;

static u64 VISITED = 0, MAXSTACK = 0;
static int DEEPEST = 0;

struct Failure { St s; int ply; const char* what; };
static bool FAILED = false; static Failure FAIL;

static bool verifyDFS(const St& s, int ply) {
  if (rowOf(s.p0) == 0) return true;                     // J1 gagne
  if (rowOf(s.p1) == H - 1) { FAILED = true; FAIL = { s, ply, "J2 gagne" }; return false; }
  if (ply >= BUDGET) { FAILED = true; FAIL = { s, ply, "budget épuisé" }; return false; }
  u64 k = keyOf(s);
  int got = memo.get(k);
  if (got >= 0 && ply <= got) return true;               // déjà vérifié avec moins de budget
  ++VISITED;
  MoveList ml; legalMoves(s, ml);
  if (ml.n == 0) { FAILED = true; FAIL = { s, ply, "pat" }; return false; }
  if (s.turn == 0) {
    int mv = certMove(s);
    if (mv < 0) { FAILED = true; FAIL = { s, ply, "entrée manquante" }; return false; }
    bool legal = false;
    for (int i = 0; i < ml.n; i++) if (ml.m[i] == (u16)mv) { legal = true; break; }
    if (!legal) { FAILED = true; FAIL = { s, ply, "coup illégal fourni" }; return false; }
    if (!verifyDFS(applyMove(s, (u16)mv), ply + 1)) return false;
  } else {
    for (int i = 0; i < ml.n; i++)
      if (!verifyDFS(applyMove(s, ml.m[i]), ply + 1)) return false;
  }
  if (ply > DEEPEST) DEEPEST = ply;
  memo.put(k, ply);
  return true;
}

static int parseReply(const std::string& lbl, const St& after1, u16& mv) {
  MoveList ml; legalMoves(after1, ml);
  char buf[24];
  for (int i = 0; i < ml.n; i++) {
    u16 m = ml.m[i];
    if (m < 256) snprintf(buf, 24, "P(%d,%d)", m / W, m % W);
    else { int w = m - 256; snprintf(buf, 24, "%c(%d,%d)", w / S ? 'V' : 'H', (w % S) / C, (w % S) % C); }
    if (lbl == buf) { mv = m; return 0; }
  }
  return -1;
}

int main(int argc, char** argv) {
  std::string part, reply;
  unsigned memoBits = 26;
  bool mirror = false;
  for (int i = 1; i < argc; i++) {
    std::string a = argv[i];
    if (a == "--part") part = argv[++i];
    else if (a == "--reply") reply = argv[++i];
    else if (a == "--memo-bits") memoBits = atoi(argv[++i]);
    else if (a == "--mirror") mirror = true;
    else { fprintf(stderr, "arg inconnu %s\n", a.c_str()); return 2; }
  }
  if (part.empty() || reply.empty()) { fprintf(stderr, "--part et --reply requis\n"); return 2; }

  FILE* fp = fopen(part.c_str(), "rb");
  if (!fp) { fprintf(stderr, "part introuvable\n"); return 1; }
  fseek(fp, 0, SEEK_END); long sz = ftell(fp); fseek(fp, 0, SEEK_SET);
  PART.resize(sz / 8);
  if (fread(PART.data(), 8, PART.size(), fp) != PART.size()) { fclose(fp); return 1; }
  fclose(fp);
  if (!std::is_sorted(PART.begin(), PART.end())) { fprintf(stderr, "part non triée\n"); return 1; }

  memo.init(memoBits);
  USE_MIRROR_LOOKUP = mirror;

  // racine : position initiale, témoin P(7,1), puis la réponse (ou son miroir)
  St root{ 0, 0, (u8)((H - 1) * W + W / 2), (u8)(W / 2), WALLS, WALLS, 0 };
  St after1 = applyMove(root, (u16)(7 * W + 1));
  u16 rmv;
  if (parseReply(reply, after1, rmv) != 0) { fprintf(stderr, "réponse inconnue %s\n", reply.c_str()); return 2; }
  if (mirror) rmv = mirMove(rmv);
  St start = applyMove(after1, rmv);

  auto t0 = std::chrono::steady_clock::now();
  bool ok = verifyDFS(start, 2);
  double el = std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count();

  if (ok) {
    printf("{\"part\":\"%s\",\"reply\":\"%s\",\"mirror\":%s,\"ok\":true,"
           "\"states\":%llu,\"memo\":%llu,\"lookups\":%llu,\"deepest_ply\":%d,\"seconds\":%.1f}\n",
           part.c_str(), reply.c_str(), mirror ? "true" : "false",
           (unsigned long long)VISITED, (unsigned long long)memo.count,
           (unsigned long long)LOOKUPS, DEEPEST, el);
    return 0;
  }
  printf("{\"part\":\"%s\",\"reply\":\"%s\",\"mirror\":%s,\"ok\":false,\"why\":\"%s\","
         "\"ply\":%d,\"hw\":%u,\"vw\":%u,\"p0\":%d,\"p1\":%d,\"s0\":%d,\"s1\":%d,\"turn\":%d,"
         "\"states\":%llu,\"seconds\":%.1f}\n",
         part.c_str(), reply.c_str(), mirror ? "true" : "false", FAIL.what,
         FAIL.ply, FAIL.s.hw, FAIL.s.vw, FAIL.s.p0, FAIL.s.p1, FAIL.s.s0, FAIL.s.s1, FAIL.s.turn,
         (unsigned long long)VISITED, el);
  return 1;
}
