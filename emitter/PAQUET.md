# Paquet de réplication 3×9 — inventaire et revendications

Assemblé dans la nuit du 1er au 2 août 2026 sur le PC 12 cœurs (Windows 11,
MSYS2 g++ 16.1). Destination : mise à jour de la table publique de Grant
Slatton (grantslatton.com/solving-quoridor), cases 3×9 à 9 et 10 murs.
Prérequis restant : publication du dépôt de sol (`napolocreed/
corridor-research`) ; réponse de Slatton sur le format de review attendue.

## Revendications et niveaux de preuve

### 3×9, 10 murs : J1 gagne en EXACTEMENT 35 plis

1. **Résultat original** (sol, dépôt principal) : preuve monolithique +
   décomposée, audits archivés.
2. **Review externe** (REVIEW-sol.md) : 3 classes d'audit reproduites au
   nœud près sur binaire recompilé (79 766 979 / 142 908 257 / 44 048 383).
3. **Réplication indépendante** (qsolve, architecture séparée : cache
   paresseux + porte union-find, PAS d'énumération globale) :
   - borne sup : 18/18 classes après le témoin P(7,1) — ce PC, TT par
     classe : 5 402 042 173 nœuds (`replication/AGGREGATE_upper_pc.json`) ;
   - borne inf : 18/18 premiers coups J1 réfutés à ≤ 33 plis, sans timeout,
     2 505 091 973 nœuds (`replication/AGGREGATE_lower.json`). Parité
     impaire des gains J1 ⇒ 34 exclu ⇒ horizon exact 35.
4. **Certificat vérifiable** (la pièce maîtresse) : 18 parts binaires
   (`certparts/`, 191 173 124 couples état-J1/coup au total ; les CertMap
   mémos `work/memo_*.bin` contiennent en sus les nœuds J2, soit
   287 795 827 états certifiés — 284 207 012 sur les 17 mémos d'origine
   + 3 588 815 pour H00 régénérée ; invariant min-rem), chacune :
   - vérifiée par échantillon : 3 000 parties adverses aléatoires ;
   - vérifiée par DFS borné : 200 000 états ;
   - **vérifiée EXHAUSTIVEMENT** par `qverify` (C++ clean-room, port de
     verify_cert.py, zéro code commun avec les solveurs) : les 18 réponses
     canoniques + 17 jumelles miroir = les 35 réponses légales de J2,
     **612 890 536 expansions DFS de vérification, zéro violation**
     (ce cardinal compte les expansions sur les 35 branches, pas des
     positions uniques ; `replication/AGGREGATE_exhaustive.json`).
   Le vérificateur ne fait confiance qu'à ses propres règles (RULES.md),
   sa recherche dichotomique, et l'arithmétique des plis.

### 3×9, 9 murs : J1 gagne en ≤ 35 plis

Réplication indépendante : 18/18 classes prouvées (P(1,1) à 33, les autres
à 31 — même structure fine que le 10 murs), 6 577 365 458 nœuds
(`replication9/AGGREGATE_upper9.json`). Suffisant pour la table (vainqueur).

### Théorème du pat (question de sémantique fermée)

`STALEMATE_THEOREM.md` : pour H ≥ 3, tout état légal non terminal offre un
coup de pion — la divergence doc/code sur la conjonction vide est du code
mort prouvé (pas seulement sondé) ; contre-exemple H = 2 atteignable en
2 plis ; vérification exhaustive multi-topologies (~23 M d'états) + panel
adversarial. `stalemates:0` archivé dans chaque run de la réplication.

## Artefacts

    certparts/*.bin, certparts-H00.bin   18 parts triées (u64), ~1,1 Go
    work/memo_*.bin                      CertMaps complètes (export qcert-1)
    replication/AGGREGATE_*.json         agrégats sup / inf / exhaustif
    replication/{PIPELINE,LOWER,EXHAUSTIVE}.log   journaux pas à pas
    replication9/AGGREGATE_upper9.json   3×9×9
    qsolve.cpp qcert2.cpp qmerge.cpp qverify.cpp qexport.cpp
    verify_cert.py orchestrate.py lower.py allverify.py orchestrate9.py
    qref.mjs qscan.mjs qcert.mjs         lignée clean-room JS + petites variantes
    REVIEW-sol.md REPRO-log.md HANDOFF.md STALEMATE_THEOREM.md
    CERTIFICATE_FORMAT.md NOTE_POUR_SOL.md

## Reproduire (tout est déterministe)

    g++ -O3 -std=c++20 -o qsolve.exe  qsolve.cpp
    g++ -O3 -std=c++20 -o qcert2.exe  qcert2.cpp
    g++ -O3 -std=c++20 -o qmerge.exe  qmerge.cpp
    g++ -O3 -std=c++20 -o qverify.exe qverify.cpp
    python orchestrate.py            # 18 parts (preuve+extraction+tri+vérifs)
    python lower.py                  # 18 réfutations
    python allverify.py              # la passe exhaustive 35/35
    python orchestrate9.py           # 3×9×9

Coûts mesurés ici : ~40 min (parts, 3 travailleurs), ~20 min (borne inf),
~21 min (exhaustif), ~25 min (3×9×9, 2 travailleurs). RAM : 2,3 Go pour les
classes pion (CertMap 2^27).

## Ce qui n'est PAS revendiqué

- Vérificateur externe trié pour les exports qcert-1 des classes pion
  (dépassent la heap JS) — livrable futur, conformément à la revue de sol.
- Fichier fusionné mono-stratégie (les 18 parts suffisent ; la fusion
  min-par-clé mélange les tempos, cf. HANDOFF).
- Toute revendication 4×7 (frontière ouverte, hors périmètre du paquet).
