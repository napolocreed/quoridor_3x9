# Journal de reproduction — 2026-08-01, Ubuntu 24, g++ 13.3, 1 cœur

## Suite du dépôt
    make -j2 && make test        # tout passe (smoke, known_outcomes ×5, diff ×3, proof-diff, symétrie)

## Vérificateur indépendant (qref.mjs, clean-room depuis docs/RULES.md)
    ./bin/frontier_dump --width 3 --height 9 --walls 10 --samples 2000 --seed 777 | node qref.mjs check-dump 3 9 10
    → {"checked":2000,"divergences":0}
    ./bin/frontier_dump --width 4 --height 3 --walls 3 --exhaustive | node qref.mjs check-dump 4 3 3
    → {"checked":63184,"divergences":0}
    ./bin/lazy_frontier_dump --width 4 --height 7 --walls 7 --samples 1500 --seed 888 | node qref.mjs check-dump 4 7 7
    → {"checked":1500,"divergences":0}

    node qref.mjs solve 3 3 0 6   → J2 en 4    node qref.mjs solve 4 3 3 15  → J1 en 13
    node qref.mjs solve 3 3 1 10  → J2 en 8    node qref.mjs solve 3 5 3 21  → J1 en 19
    node qref.mjs solve 4 3 2 12  → J2 en 10   node qref.mjs solve 3 5 4 24  → J2 en 22

    node qref.mjs count-configs 3 9 20  → 2 929 319   (= revendication)
    node qref.mjs count-configs 4 7 14  → 16 368 423  (= revendication)
    node qref.mjs probe-stalemate 3 9 10 4000 200 42  → 0 état sans coup légal / 513 459
    node qref.mjs probe-stalemate 4 7 7 3000 200 43   → 0 / 288 934

## Reproduction au nœud près (binaire recompilé ici)
    frontier_solver --width 3 --height 9 --walls 10 --root-index 0 --root-index2 19 --target 1 \
      --start-depth 31 --max-depth 35 --tt-bits 26 --order 1 --no-bounds --no-pawn-table
    → solved=1 winner=1 depth=31 nodes=79766979        (archive : 79 766 979 ✓)
    … --root-index2 27 → nodes=142908257               (archive : 142 908 257 ✓)
    frontier_solver … --root-index 31 --target 1 --start-depth 32 --max-depth 32 …
    → solved=0 nodes=44048383                          (archive : 44 048 383 ✓)
