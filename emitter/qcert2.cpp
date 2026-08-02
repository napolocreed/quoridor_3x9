// qcert2.cpp — extracteur de certificat, v2 (par réponse canonique).
//
// Changements vs v1 : mémo réinitialisée PAR réponse (RAM bornée), dump
// partiel certparts/<tag>.bin à la complétion, budget = profondeur minimale
// prouvée de la classe (31, ou 33 pour P(1,1)), sélection du fils gagnant
// au minWin le plus petit (stratégie la plus courte => DAG plus petit).
// Le certificat final ne couvre que les 18 réponses canoniques ; le
// vérificateur applique la symétrie miroir pour les 17 jumelles.
//
// Build : g++ -O3 -std=c++20 -o qcert2 qcert2.cpp

#define main qsolve_embedded_main
#include "qsolve.cpp"
#undef main

struct CertMap {
  std::vector<u64> keys; std::vector<u32> vals;   // val = rem 6b | move 9b << 6
  u64 mask = 0; u64 count = 0;
  void init(unsigned bits) { keys.assign(1ull << bits, 0); vals.assign(1ull << bits, 0); mask = (1ull << bits) - 1; count = 0; }
  bool get(u64 k, int& mv, int& rem) const {
    u64 i = TT::mix(k) & mask;
    while (keys[i]) { if (keys[i] == k) { mv = (vals[i] >> 6) & 0x1ff; rem = vals[i] & 63; return true; } i = (i + 1) & mask; }
    return false;
  }
  void put(u64 k, int mv, int rem) {
    u64 i = TT::mix(k) & mask;
    // ne garder que la certification la plus SERRÉE : en post-ordre, la
    // visite externe (budget large) écrit après la visite interne (budget
    // petit) du même état ; écraser vers le haut réintroduit des coups
    // lents qui peuvent boucler (bug du cycle P(3,2)<->P(4,2))
    while (keys[i]) { if (keys[i] == k) { if (rem < (int)(vals[i] & 63)) vals[i] = (u32)((rem & 63) | ((mv & 0x1ff) << 6)); return; } i = (i + 1) & mask; }
    if ((count + 1) * 5 > (mask + 1) * 4) { fprintf(stderr, "CertMap pleine\n"); exit(9); }
    keys[i] = k; vals[i] = (u32)((rem & 63) | ((mv & 0x1ff) << 6)); ++count;
  }
  bool save(const std::string& f) const {
    std::string tmp = f + ".tmp"; FILE* fp = fopen(tmp.c_str(), "wb"); if (!fp) return false;
    u64 n = mask + 1; fwrite(&n, 8, 1, fp); fwrite(&count, 8, 1, fp);
    fwrite(keys.data(), 8, n, fp); fwrite(vals.data(), 4, n, fp); fclose(fp);
    return rename(tmp.c_str(), f.c_str()) == 0;
  }
  bool load(const std::string& f) {
    FILE* fp = fopen(f.c_str(), "rb"); if (!fp) return false;
    u64 n = 0, c = 0;
    if (fread(&n, 8, 1, fp) != 1 || n != mask + 1 || fread(&c, 8, 1, fp) != 1) { fclose(fp); return false; }
    size_t a = fread(keys.data(), 8, n, fp), b = fread(vals.data(), 4, n, fp); fclose(fp);
    if (a != n || b != n) return false; count = c; return true;
  }
};
static CertMap cm;

static inline u64 rawKey(const State& s) {
  return packKey(s.hw, s.vw, s.p[0], s.p[1], s.st[0], s.st[1], s.turn, 0);
}

static u64 CVISITED = 0, ORACLE_CALLS = 0;
static std::vector<std::array<Move, 64>> OSTK(48);

static bool extract(const State& s, int rem) {
  if (row(s.p[0]) == 0) return true;
  if (row(s.p[1]) == H - 1) return false;
  int rn = relevantDepth(s.turn, 0, rem);
  if (rn <= 0) return false;
  u64 k = rawKey(s);
  int mv0 = -1, r0 = 99;
  bool have = cm.get(k, mv0, r0);
  if (have && rn >= r0) return true;
  if ((++CVISITED & 0x3FFF) == 0 && HAS_DEADLINE && Clock::now() >= DEADLINE) throw Abort{};
  Move ch[64]; int n = gen(s, ch, true, nullptr, 0);
  if (n == 0) return false;
  if (s.turn == 0) {
    for (int i = 0; i < n; i++) if (row(ch[i].s.p[0]) == 0) { cm.put(k, ch[i].id, rn); return true; }
    // ordre : coup mémoïsé d'abord (s'il existe), puis ordre de génération ;
    // chaque candidat est VÉRIFIÉ (probe TT puis oracle) avant la descente
    int order[64]; int no = 0;
    // devant : le coup mémoïsé, puis l'indice de la TT du grind (si lisible
    // dans cette orientation), puis l'ordre de génération
    bool pv; u16 phint = 0xffff;
    tt.probe(canonKey(s, 0, true), rn, pv, phint);
    auto front = [&](int id) {
      for (int i = 0; i < n; i++) if (ch[i].id == id) {
        for (int j = 0; j < no; j++) if (order[j] == i) return;
        order[no++] = i; return;
      }
    };
    if (have) front(mv0);
    if (phint != 0xffff) front((int)phint);
    for (int i = 0; i < n; i++) { bool dup = false; for (int j = 0; j < no; j++) if (order[j] == i) { dup = true; break; } if (!dup) order[no++] = i; }
    for (int pass = 0; pass < 2; pass++) {
      for (int oi = 0; oi < no; oi++) {
        const Move& m = ch[order[oi]];
        int cd = relevantDepth(m.s.turn, 0, rn - 1);
        if (cd <= 0) continue;
        bool val; u16 hint;
        bool known = tt.probe(canonKey(m.s, 0, true), cd, val, hint);
        if (pass == 0) { if (!(known && val)) continue; }
        else {
          if (known && !val) continue;
          ++ORACLE_CALLS;
          if (!win(m.s, 0, cd, OSTK, 0)) continue;
        }
        if (extract(m.s, rn - 1)) { cm.put(k, m.id, rn); return true; }
        fprintf(stderr, "INCOHERENCE passe %d coup %s rn=%d\n", pass, mvName(m.id).c_str(), rn);
        exit(7);
      }
    }
    return false;
  } else {
    for (int i = 0; i < n; i++) if (!extract(ch[i].s, rn - 1)) return false;
    cm.put(k, 0x1ff, rn);
    return true;
  }
}

static void dumpP1(const std::string& out) {
  FILE* fp = fopen((out + ".tmp").c_str(), "wb");
  u64 written = 0;
  for (u64 i = 0; i <= cm.mask; i++) {
    if (!cm.keys[i]) continue;
    u64 k = cm.keys[i]; int mv = (cm.vals[i] >> 6) & 0x1ff;
    if ((((k - 1) >> 1) & 1) != 0) continue;      // trait J2 : pas dans le fichier
    u64 e = ((k - 1) << 9) | (u64)mv;
    fwrite(&e, 8, 1, fp); ++written;
  }
  fclose(fp); rename((out + ".tmp").c_str(), out.c_str());
  fprintf(stderr, "dump %s : %llu entrées J1\n", out.c_str(), (unsigned long long)written);
}

int main(int argc, char** argv) {
  W = 3; H = 9; WALLS = 10;
  unsigned ttBits = 26, cacheBits = 23, cmBits = 24;
  double budget = 1e9; int rem = 31;
  std::string mode = "extract", reply, ttFile = "tt_cur.bin", memoFile, out;
  for (int i = 1; i < argc; i++) {
    std::string a = argv[i];
    if (a == "--mode") mode = argv[++i];
    else if (a == "--reply") reply = argv[++i];
    else if (a == "--budget") budget = atof(argv[++i]);
    else if (a == "--rem") rem = atoi(argv[++i]);
    else if (a == "--tt-bits") ttBits = atoi(argv[++i]);
    else if (a == "--cm-bits") cmBits = atoi(argv[++i]);
    else if (a == "--cache-bits") cacheBits = atoi(argv[++i]);
    else if (a == "--memo") memoFile = argv[++i];
    else if (a == "--tt-file") ttFile = argv[++i];
    else if (a == "--out") out = argv[++i];
    else { fprintf(stderr, "arg inconnu %s\n", a.c_str()); return 2; }
  }
  C = W - 1; R = H - 1; S = C * R; N = W * H;
  if (mode == "merge") { ttBits = 4; cacheBits = 10; cmBits = 4; }
  buildMirror(); DC.init(cacheBits); tt.init(ttBits); cm.init(cmBits);
  bool ttOK = mode == "merge" ? false : tt.load(ttFile);
  bool cmOK = !memoFile.empty() && cm.load(memoFile);
  fprintf(stderr, "TT %s, mémo %s (%llu)\n", ttOK ? "ok" : "vide", cmOK ? "reprise" : "vide", (unsigned long long)cm.count);

  State root = initial();
  State after1; findMove(root, "P(7,1)", after1);

  if (mode == "extract") {
    State s2; if (findMove(after1, reply, s2) < 0) { fprintf(stderr, "réponse inconnue\n"); return 2; }
    auto t0 = Clock::now();
    if (budget < 1e8) { DEADLINE = t0 + std::chrono::duration_cast<Clock::duration>(std::chrono::duration<double>(budget)); HAS_DEADLINE = true; }
    bool done = false, aborted = false;
    try { done = extract(s2, rem); }
    catch (Abort&) { aborted = true; }
    if (!memoFile.empty()) cm.save(memoFile);
    tt.save(ttFile);
    if (done && !out.empty()) dumpP1(out);
    double el = std::chrono::duration<double>(Clock::now() - t0).count();
    printf("{\"reply\":\"%s\",\"rem\":%d,\"done\":%s,\"aborted\":%s,\"visited\":%llu,\"oracle_calls\":%llu,"
           "\"memo\":%llu,\"stalemates\":%llu,\"seconds\":%.1f}\n",
           reply.c_str(), rem, done ? "true" : "false", aborted ? "true" : "false",
           (unsigned long long)CVISITED, (unsigned long long)ORACLE_CALLS,
           (unsigned long long)cm.count, (unsigned long long)STALEMATES, el);
    return done ? 0 : (aborted ? 3 : 1);
  }

  if (mode == "merge") {
    // charge toutes les parts, ajoute la racine, TRIE, unique par clé, écrit.
    std::vector<u64> all; all.reserve(150000000);
    State a1; int idFirst = findMove(root, "P(7,1)", a1);
    all.push_back(((rawKey(root) - 1) << 9) | (u64)idFirst);
    std::string list = reply; size_t pos = 0;
    while (pos < list.size()) {
      size_t c2 = list.find(',', pos);
      std::string f = list.substr(pos, c2 == std::string::npos ? std::string::npos : c2 - pos);
      pos = c2 == std::string::npos ? list.size() : c2 + 1;
      FILE* fi = fopen(f.c_str(), "rb");
      if (!fi) { fprintf(stderr, "part manquante %s\n", f.c_str()); return 1; }
      u64 e; while (fread(&e, 8, 1, fi) == 1) all.push_back(e);
      fclose(fi);
    }
    fprintf(stderr, "lu %zu entrées, tri...\n", all.size());
    std::sort(all.begin(), all.end());
    u64 total = 0, dup = 0, conflits = 0;
    FILE* fo = fopen((out + ".tmp").c_str(), "wb");
    u64 hdr[4] = { 0x54524351ull, (u64)W | ((u64)H << 8) | ((u64)WALLS << 16), 35, 0 };
    fwrite(hdr, 8, 4, fo);
    for (size_t i = 0; i < all.size(); i++) {
      if (i && (all[i] >> 9) == (all[i-1] >> 9)) { ++dup; if (all[i] != all[i-1]) ++conflits; continue; }
      fwrite(&all[i], 8, 1, fo); ++total;
    }
    fclose(fo); rename((out + ".tmp").c_str(), out.c_str());
    printf("{\"cert\":\"%s\",\"entrees\":%llu,\"doublons\":%llu,\"conflits_de_coup\":%llu}\n",
           out.c_str(), (unsigned long long)total, (unsigned long long)dup, (unsigned long long)conflits);
    return 0;
  }
  fprintf(stderr, "mode inconnu\n"); return 2;
}
