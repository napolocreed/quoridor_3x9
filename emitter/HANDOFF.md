# HANDOFF — Quoridor 3×9×10 : réplication + certificat vérifiable

Passation chat → Claude Code (PC d'Ulysse), 1er août 2026.
Contexte : faire mettre à jour la table publique de Grant Slatton
(https://grantslatton.com/solving-quoridor) — cases 3×9 à 9 et 10 murs,
résolues par GPT 5.6 « Sol » (dépôt `napolocreed/corridor-research`,
**encore privé** : publication = prérequis). Ulysse a écrit à Slatton pour
connaître son format de review préféré (réponse en attente ; screenshot du
mail pas encore transmis à Claude).

## Ce qui est ACQUIS (ne pas refaire)

1. **Review complète du travail de Sol** : `REVIEW-sol.md` (+ `REPRO-log.md`,
   `qref.mjs`). Tout vérifié tient ; 3 classes d'audit reproduites au nœud
   près (79 766 979 / 142 908 257 / 44 048 383).
2. **Réplication indépendante de la borne supérieure — TERMINÉE (18/18)** :
   J1 gagne 3×9×10 en ≤ 35 plis, prouvé par `qsolve` (architecture séparée :
   cache de distances à la demande + porte union-find, PAS d'énumération de
   configs). 16 classes murs + P(0,0) à prof. 31, P(1,1) à 33 — même
   structure fine que l'audit de Sol. Résultats : `replication/*.json`
   (agrégat : `AGGREGATE_upper.json`, ~1,56 G nœuds comptabilisés,
   TT partagée entre classes contrairement à l'audit de Sol).
   Validation de qsolve : 330 k verdicts de légalité sans divergence,
   6 variantes connues à l'horizon exact, 500/500 requêtes bornées
   identiques à `frontier_state_solve`, univers de murs recomptés
   (2 929 319 / 16 368 423), partitions 35→18 retrouvées.
3. **Pipeline certificat conçu, débogué, VALIDÉ sur un exemplaire** :
   part H(0,0) ré-extraite après correctif → **2500/2500 lignes adverses
   aléatoires gagnées en ≤ 33 plis** (`verify_cert.py sample`).

## Le certificat : conception et état

- Un certificat = pour chaque état où J1 est au trait dans la stratégie,
  le coup à jouer. Format : u64 = (clé 51 b) << 9 | coup 9 b, trié.
  Clé (bits bas→haut) : target(=0), turn, st1:4, st0:4, p1:5, p0:5,
  vw:18, hw. Coup : <256 = case pion ; ≥256 : ori=(c−256)/16, slot=(c−256)%16.
- **La revendication se décompose en 18 sous-certificats** (un par classe
  de réponse de J2 après le témoin P(7,1)) — chaque part est
  auto-cohérente. Les 17 réponses jumelles se vérifient via la même part
  avec application du miroir DEPUIS LE PLI 1 (pas de fallback miroir
  intra-part : bug vérifié).
- Le fichier fusionné mono-stratégie (qmerge merge) est une OPTIMISATION :
  la fusion « entrée min par clé » mélange les tempos entre parts →
  violations rares (mesuré ~1/900). Réparation possible en boucle de point
  fixe (vérifier → ré-extraire les états fautifs au rem observé), ou s'en
  passer : les 18 parts suffisent.
- État : parts ré-extraites après correctif : H00 ✓(vérifiée), H10, H20.
  **15 restantes** — relancer simplement `python3 extract_all.py 999999`
  (reprenable ; ordre : murs puis P(0,0) rem 31 puis P(1,1) rem 33).
  Tailles attendues : murs ~2-9 M d'entrées, P(0,0)/P(1,1) 15-40 M
  (le correctif min-rem réduit ~2-3× par rapport aux premiers essais).

## Bugs corrigés — invariants à NE PAS casser

1. **Porte union-find** : un mur = DEUX demi-segments autour de son milieu
   (contacts en T !) ; cycle ssi 2 des 3 nœuds {a,m,b} déjà connectés
   (trois `find`, aucune union). Auto-test : `qsolve --mode selftest`.
2. **`put()` de la CertMap = min-rem SEULEMENT** (bug du cycle
   P(3,2)↔P(4,2) : en post-ordre, la certification externe — budget large,
   coup lent — écrasait la certification interne serrée du même état ; la
   stratégie dépthless bouclait). Reproducteur : `verify_cert.py forensic
   certparts/H00.bin 10 7 "H(0,0)"` sur une part construite SANS le fix.
3. **Deadline murale DANS la recherche** (pas seulement entre profondeurs)
   + **sauvegardes atomiques** (write tmp + rename) : un kill en pleine
   écriture ne doit jamais produire un fichier accepté au rechargement.
4. Ordonnancement : indices TT du grind frontés dans l'ordre des candidats
   (sinon l'oracle réfute les mauvais coups un par un, ~76 s pièce).
5. Références C++ : jamais de `const auto&` sur `DC.get()` si d'autres
   `get()` suivent (réallocation du vector).

## À FAIRE (ordre suggéré)

1. Finir l'extraction (15 parts) puis `qmerge --mode sort` sur chacune.
2. `verify_cert.py sample <part> 3000 <seed> "<réponse>"` sur chaque part
   + `walk` borné ; puis écrire le **vérificateur C++ complet** (porter la
   logique de verify_cert.py, DFS exhaustif par part, mémo (état→remMin) ;
   ~2-4 min/part attendues) — c'est LA pièce pour Slatton : passe
   exhaustive = préuve vérifiée indépendamment.
   Vérif jumelles : rejouer chaque part en miroir (option à ajouter :
   miroir appliqué à la réponse forcée et aux lookups).
3. **Borne inférieure** (réplication de « exactement 35 ») :
   `python3 grind.py lower 999999` — 18 classes, --start-depth 32, attendre
   proved=false timeout=false partout. (La table de Slatton ne stocke que
   le vainqueur : non bloquant pour la mise à jour, mais complète la
   réplication de l'énoncé de Sol.)
4. Rejouer aussi 3×9×9 (moins cher) pour couvrir la 2e case de la table.
5. Selon la réponse de Slatton : préparer le paquet (probablement : repo
   Sol publié + mon dossier réplication + certificat + vérificateurs +
   REVIEW). Compresser les parts en zstd (u64 triés : ratio attendu 3-5×).
6. Dépôt Sol : à rendre public (napolocreed/corridor-research) avant envoi.

## Régénérer l'état de calcul (rien d'irremplaçable ici)

Tout est déterministe. Sur le PC (plus de cœurs = paralléliser par classe) :
    g++ -O3 -std=c++20 -o qsolve qsolve.cpp
    g++ -O3 -std=c++20 -o qcert2 qcert2.cpp     # inclut qsolve.cpp
    g++ -O3 -std=c++20 -o qmerge qmerge.cpp
    python3 grind.py upper 999999               # ~1,5-3 G nœuds, refait tt_cur.bin
    python3 extract_all.py 999999               # les 18 parts
    ./qmerge --mode sort --in certparts/X.bin   # chaque part
    python3 verify_cert.py sample ...           # échantillons
La TT du grind (tt_cur.bin, 805 Mo, non livrée) se refait en ~30-60 min
mono-cœur ; les tranches/reprises (--tt-file, --memo) deviennent inutiles
avec de vraies ressources : tout peut tourner d'un trait.

## Fichiers livrés (outputs/quoridor/)

    REVIEW-sol.md, REPRO-log.md, qref.mjs      — review + vérif clean-room
    replication/*.json                          — les 18 classes + agrégat
    qsolve.cpp, qcert2.cpp, qmerge.cpp          — solveur, extracteur, fusion
    grind.py, extract_all.py, verify_cert.py    — orchestration + vérif
    certparts-H00.bin                           — part exemplaire VÉRIFIÉE
    HANDOFF.md                                  — ce document
    (+ moteur 9×9 : engine.js, ai.js, demo.html… — le projet app d'origine)
