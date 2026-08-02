// qmerge.cpp — post-traitement des parts de certificat (reconstruit : la
// version du chat n'a pas survécu à la passation ; rôle identique).
//
//   qmerge --mode sort --in part.bin        trie les u64 en place (atomique)
//   qmerge --mode check --in part.bin       vérifie tri strict + unicité des clés
//
// Une part brute sort de qcert2 dans l'ordre de la table de hachage ; le
// vérificateur (bisect) exige des entrées triées par u64 croissant.
// Build : g++ -O3 -std=c++20 -o qmerge qmerge.cpp

#include <cstdint>
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>
#include <algorithm>

using u64 = uint64_t;

int main(int argc, char** argv) {
  std::string mode = "sort", in;
  for (int i = 1; i < argc; i++) {
    std::string a = argv[i];
    if (a == "--mode") mode = argv[++i];
    else if (a == "--in") in = argv[++i];
    else { fprintf(stderr, "arg inconnu %s\n", a.c_str()); return 2; }
  }
  if (in.empty()) { fprintf(stderr, "--in requis\n"); return 2; }

  FILE* fp = fopen(in.c_str(), "rb");
  if (!fp) { fprintf(stderr, "introuvable : %s\n", in.c_str()); return 1; }
  fseek(fp, 0, SEEK_END); long sz = ftell(fp); fseek(fp, 0, SEEK_SET);
  if (sz % 8) { fprintf(stderr, "taille non multiple de 8\n"); fclose(fp); return 1; }
  std::vector<u64> v(sz / 8);
  if (fread(v.data(), 8, v.size(), fp) != v.size()) { fclose(fp); return 1; }
  fclose(fp);

  if (mode == "sort") {
    std::sort(v.begin(), v.end());
    u64 dupKeys = 0;
    for (size_t i = 1; i < v.size(); i++) if ((v[i] >> 9) == (v[i - 1] >> 9)) ++dupKeys;
    std::string tmp = in + ".tmp";
    FILE* fo = fopen(tmp.c_str(), "wb");
    if (!fo || fwrite(v.data(), 8, v.size(), fo) != v.size()) { fprintf(stderr, "écriture\n"); return 1; }
    fclose(fo);
    remove(in.c_str());
    if (rename(tmp.c_str(), in.c_str()) != 0) { fprintf(stderr, "rename\n"); return 1; }
    printf("{\"sorted\":\"%s\",\"entries\":%zu,\"dup_keys\":%llu}\n",
           in.c_str(), v.size(), (unsigned long long)dupKeys);
    return dupKeys ? 4 : 0;
  }
  if (mode == "check") {
    u64 bad = 0, dupKeys = 0;
    for (size_t i = 1; i < v.size(); i++) {
      if (v[i] < v[i - 1]) ++bad;
      if ((v[i] >> 9) == (v[i - 1] >> 9)) ++dupKeys;
    }
    printf("{\"file\":\"%s\",\"entries\":%zu,\"order_violations\":%llu,\"dup_keys\":%llu}\n",
           in.c_str(), v.size(), (unsigned long long)bad, (unsigned long long)dupKeys);
    return (bad || dupKeys) ? 1 : 0;
  }
  fprintf(stderr, "mode inconnu\n"); return 2;
}
