// qexport.cpp — export d'une mémo d'extraction (CertMap) vers un certificat
// qcert-1 JSONL conforme à quoridor-frontier-research/docs/CERTIFICATE_FORMAT.md.
//
// La CertMap contient TOUS les nœuds certifiés de la part (J1 et J2) avec
// leur rem minimal — l'invariant min-rem garantit la décroissance stricte
// des rangs le long des arêtes, exigée par la spec. `d` exporté = rem.
// Correspondance de champs : JSON p1/p2/r1/r2 = état p0/p1/s0/s1 (la spec
// indexe les joueurs à partir de 1 dans les NOMS, à partir de 0 dans turn).
//
//   qexport --memo work/memo_H10.bin --reply "H(1,0)" --out H10.qcert1.jsonl
//
// Build : g++ -O3 -std=c++20 -o qexport qexport.cpp

#include <cstdint>
#include <cstdio>
#include <cstring>
#include <cstdlib>
#include <string>
#include <vector>

using u8 = uint8_t; using u16 = uint16_t; using u32 = uint32_t; using u64 = uint64_t;

static constexpr int W = 3, H = 9, WALLS = 10;
static constexpr int C = W - 1, R = H - 1, S = C * R;
static constexpr int VW_FIELD = 18;

struct St { u32 hw, vw; int p0, p1, s0, s1, turn; };

static St decodeKey(u64 rawKeyPlus1) {
  u64 x = rawKeyPlus1 - 1;
  St s;
  x >>= 1;                       // target (toujours 0 dans les parts)
  s.turn = (int)(x & 1); x >>= 1;
  s.s1 = (int)(x & 15); x >>= 4;
  s.s0 = (int)(x & 15); x >>= 4;
  s.p1 = (int)(x & 31); x >>= 5;
  s.p0 = (int)(x & 31); x >>= 5;
  s.vw = (u32)(x & ((1u << VW_FIELD) - 1)); x >>= VW_FIELD;
  s.hw = (u32)x;
  return s;
}

static u64 encodeKey(const St& s) {
  u64 x = s.hw;
  x = (x << VW_FIELD) | s.vw;
  x = (x << 5) | (u32)s.p0;
  x = (x << 5) | (u32)s.p1;
  x = (x << 4) | (u32)s.s0;
  x = (x << 4) | (u32)s.s1;
  x = (x << 1) | (u32)s.turn;
  x = (x << 1);
  return x + 1;
}

static std::string moveLabel(int mv) {
  char b[24];
  if (mv < 256) snprintf(b, 24, "P:%d", mv);
  else {
    int w = mv - 256, ori = w / S, i = w % S;
    snprintf(b, 24, "%c:%d:%d", ori ? 'V' : 'H', i / C, i % C);
  }
  return b;
}

int main(int argc, char** argv) {
  std::string memoPath, reply, outPath;
  for (int i = 1; i < argc; i++) {
    std::string a = argv[i];
    if (a == "--memo") memoPath = argv[++i];
    else if (a == "--reply") reply = argv[++i];
    else if (a == "--out") outPath = argv[++i];
    else { fprintf(stderr, "arg inconnu %s\n", a.c_str()); return 2; }
  }
  if (memoPath.empty() || reply.empty() || outPath.empty()) {
    fprintf(stderr, "--memo, --reply et --out requis\n"); return 2;
  }

  FILE* fp = fopen(memoPath.c_str(), "rb");
  if (!fp) { fprintf(stderr, "mémo introuvable\n"); return 1; }
  u64 n = 0, count = 0;
  if (fread(&n, 8, 1, fp) != 1 || fread(&count, 8, 1, fp) != 1) { fclose(fp); return 1; }
  std::vector<u64> keys(n); std::vector<u32> vals(n);
  if (fread(keys.data(), 8, n, fp) != n || fread(vals.data(), 4, n, fp) != n) { fclose(fp); return 1; }
  fclose(fp);

  // racine de la part : position initiale -> P(7,1) -> réponse
  St root{ 0, 0, (H - 1) * W + W / 2, W / 2, WALLS, WALLS, 0 };
  root.p0 = 7 * W + 1; root.turn = 1;              // après le témoin P(7,1)
  // applique la réponse (P(r,c) / H(r,c) / V(r,c))
  if (reply[0] == 'P') {
    int r, c; if (sscanf(reply.c_str(), "P(%d,%d)", &r, &c) != 2) { fprintf(stderr, "réponse invalide\n"); return 2; }
    root.p1 = r * W + c;
  } else {
    int r, c; char o = reply[0];
    if (sscanf(reply.c_str() + 1, "(%d,%d)", &r, &c) != 2) { fprintf(stderr, "réponse invalide\n"); return 2; }
    int i = r * C + c;
    if (o == 'H') root.hw |= 1u << i; else root.vw |= 1u << i;
    root.s1--;
  }
  root.turn = 0;

  u64 rootKey = encodeKey(root);
  int rootRem = -1;
  for (u64 i = 0; i < n; i++) if (keys[i] == rootKey) { rootRem = (int)(vals[i] & 63); break; }
  if (rootRem < 0) { fprintf(stderr, "racine absente de la mémo\n"); return 1; }

  FILE* fo = fopen(outPath.c_str(), "wb");
  if (!fo) { fprintf(stderr, "sortie\n"); return 1; }
  fprintf(fo, "{\"type\":\"header\",\"format\":\"qcert-1\",\"width\":%d,\"height\":%d,\"walls\":%d,"
              "\"target\":0,\"bound\":%d,\"root\":{\"p1\":%d,\"p2\":%d,\"r1\":%d,\"r2\":%d,"
              "\"turn\":%d,\"hw\":%u,\"vw\":%u}}\n",
          W, H, WALLS, rootRem, root.p0, root.p1, root.s0, root.s1, root.turn, root.hw, root.vw);

  u64 written = 0, j1 = 0, j2 = 0, anomalies = 0;
  for (u64 i = 0; i < n; i++) {
    if (!keys[i]) continue;
    St s = decodeKey(keys[i]);
    int rem = (int)(vals[i] & 63), mv = (int)((vals[i] >> 6) & 0x1ff);
    // invariant CertMap : nœud J1 <=> coup stocké ; toute violation est un
    // bug d'extraction et doit invalider l'export, pas produire du JSONL faux
    if ((s.turn == 0) != (mv != 0x1ff)) { ++anomalies; continue; }
    if (s.turn == 0) {
      fprintf(fo, "{\"type\":\"node\",\"p1\":%d,\"p2\":%d,\"r1\":%d,\"r2\":%d,\"turn\":0,"
                  "\"hw\":%u,\"vw\":%u,\"d\":%d,\"move\":\"%s\"}\n",
              s.p0, s.p1, s.s0, s.s1, s.hw, s.vw, rem, moveLabel(mv).c_str());
      ++j1;
    } else {
      fprintf(fo, "{\"type\":\"node\",\"p1\":%d,\"p2\":%d,\"r1\":%d,\"r2\":%d,\"turn\":1,"
                  "\"hw\":%u,\"vw\":%u,\"d\":%d}\n",
              s.p0, s.p1, s.s0, s.s1, s.hw, s.vw, rem);
      ++j2;
    }
    ++written;
  }
  fclose(fo);
  if (anomalies) {
    fprintf(stderr, "%llu anomalies coup/trait — export invalide\n", (unsigned long long)anomalies);
    remove(outPath.c_str());
    return 1;
  }
  printf("{\"out\":\"%s\",\"nodes\":%llu,\"j1\":%llu,\"j2\":%llu,\"bound\":%d}\n",
         outPath.c_str(), (unsigned long long)written, (unsigned long long)j1,
         (unsigned long long)j2, rootRem);
  return 0;
}
