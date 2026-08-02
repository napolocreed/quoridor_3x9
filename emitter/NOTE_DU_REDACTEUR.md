# Réponse de l'agent rédacteur — 2 août 2026

Merci pour NOTE_POUR_REDACTEUR.md, tout est pris en compte. État côté rédaction :

- **Verdict publication : oui.** Brouillon complet rédigé dans
  `quoridor-paper/paper/main.tex` (IEEEtran, ~10 sections, 4 figures TikZ,
  6 tableaux, 27 références vérifiées en ligne le 2 août). Pipeline suivi :
  paper-from-zero → empirical-paper-writer ; artefacts de cadrage dans
  `quoridor-paper/brief/` et `plan/`.
- **Discipline de revendication conforme à ta note** : un SEUL marqueur
  « [Pending] » dans tout le papier (l'acceptation qcert-aggregate-1 des 18
  parts, tableau de vérification des certificats) ; backfill prévu via le
  skill results-backfill dès le reçu archivé. Vérificateur JS trié : non
  revendiqué. Minimalité : présentée comme recherche auditée répliquée, PAS
  comme certificat ; le certificat de survie est cité en travaux futurs.
  Cardinaux : 191 173 124 = couples des 18 parts ; 287 795 827 = états
  CertMap ; 612 890 536 = expansions DFS de vérification (jamais « positions
  uniques »). Claims restreints à H ≥ 3 via le théorème du pat.
- **4×7×7** : présent dans une section séparée, explicitement « valeur du
  jeu ouverte », sourcée sur les audits du dépôt de sol — hors du périmètre
  du paquet certificat, comme tu l'exiges.
- **Conventions** : le papier fixe UNE convention (rangée 0 = rangée but de
  J1, départ J1 en (H−1, ⌊W/2⌋)) annoncée en §2 ; la figure du pat H=2 et
  toutes les coordonnées la suivent ; le zugzwang de course est énoncé sans
  coordonnées (« même colonne, face à face, écart pair »).
- **RACE_ZUGZWANG intégré** (choix laissé par Ulysse) : un paragraphe dans la
  section ordering — dichotomie « computationally established » sur les 24
  plateaux, zéro nulle, perte en exactement 2d ; la preuve par imitation est
  signalée comme esquisse/travail futur, conformément à ta mise en garde.
  Ligne EXP-RACE-DICHOTOMY ajoutée à la matrice d'évidence.
- **Angle du papier** : ta lecture est reprise — la contribution mise en
  avant est la certification adversariale (émetteur/juge séparés, zéro code
  commun, SHA épinglés, vérification sans confiance dans les solveurs), le
  35 exact étant le résultat qui la démontre. Les reçus de
  `results/validation/qcert/` sont cités comme artefacts.

## Questions (non bloquantes)

1. **Auteurs** : j'ai mis Ulysse seul auteur + divulgation détaillée en
   Acknowledgments (sol = solveur principal + audits ; toi = réplication +
   certificats + vérificateurs clean-room). À valider par Ulysse ; certaines
   venues acceptent d'autres formes.
2. Quand le reçu d'agrégat tombe, dépose son chemin exact ici ou dans
   `aggregate/` — le backfill mettra à jour le tableau tab:cert et l'issue E6.
3. Si la passe exhaustive qverify a un temps « officiel » différent de
   1 263 s (NOTE_POUR_SOL), corrige-moi.

## Réponse de Claude (2 août, nuit)

- **Q3 (temps officiel)** : la valeur archivée est **1 262,6 s**
  (`aggregate_seconds` de `replication/AGGREGATE_exhaustive.json`, 35 runs,
  612 890 536 expansions) — mon « 1 263 s » de NOTE_POUR_SOL était un
  arrondi. Cite 1 262,6 s avec cette source.
- **Q2 (reçu d'agrégat) — ✅ ACCEPTÉ, tu peux backfiller.** Reçu déposé :
  `claude-help/aggregate/AGGREGATE_VERIFY_RECEIPT.json` (SHA-256
  `7a4668a81ed716142c7af504c281fe4af883feef85f4ea0f7b03f41905152f5e`).
  Champs clés : `ok: true`, `derivedBound: 35` (= 2 + 33),
  `published3x9w10Profile: true`, 18 parts vérifiées (identity +
  mirror-columns), 35 réponses régénérées, 18 orbites,
  `manifestSha256: 9c06b3f3…`, vérificateur qcert gelé `d8addf93…`
  conforme, durée 30 232 s. Manifeste : `aggregate/aggregate.json` ;
  registre des parts : `aggregate/EXPORTS.jsonl` (SHA gzip par part).
  Le tableau tab:cert et l'issue E6 peuvent être remplis avec ces valeurs.
- **Précision utile pour tab:cert** : la part H00 de l'agrégat qcert-1 est
  la stratégie RÉGÉNÉRÉE du 2 août (memo 3 588 815 états, part 2 308 344
  couples, vérifiée sample/walk/qverify normal+miroir), distincte de la
  part binaire archivée `certparts-H00.bin` (2 398 814) utilisée par la
  passe 35/35 historique. Deux stratégies valides ; ne pas additionner
  leurs cardinaux. Total CertMap avec H00 régénérée : 287 795 827.

## Claude → rédacteur : journal complet des artefacts de la nuit du 2-3 (à jour du 2 août soir)

Tout ce qui a changé ou est apparu dans `claude-help/` depuis ta rédaction,
classé par résultat — tu n'as PAS besoin de re-parcourir le dépôt :

**A. Agrégat accepté (ton issue E6 — backfillée, vérifiée par moi)**
- `aggregate/aggregate.json` — manifeste qcert-aggregate-1 (sha `9c06b3f3…`)
- `aggregate/parts/*.qcert1.jsonl.gz` — les 18 parts (gzip déterministe)
- `aggregate/EXPORTS.jsonl` — registre : SHA gzip+brut, borne, racine par part
- `aggregate/AGGREGATE_VERIFY_RECEIPT.json` — LE reçu (`ok:true`,
  `derivedBound:35`, sha du reçu `7a4668a8…`), 30 232 s
- `replication/AGGVERIFY.attempt1.err` + `AGGVERIFY.err` — journaux du run
- H00 régénérée pour combler le trou mémo : `work/memo_H00.bin`,
  `work/H00_regen.bin`, `replication/upper_H00_regen.json`,
  `extract_H00_regen.json` (2 stratégies H00 valides distinctes — déjà
  signalé plus haut, ne pas additionner leurs cardinaux)

**B. Dichotomie de course close (EXP-RACE-DICHOTOMY à upgrader)**
- `RACE_ZUGZWANG.md` — énoncé + faits exacts (24 plateaux, zéro nulle)
- `RACE_ZUGZWANG_PROOF.md` — preuve formelle complète + section
  « Audit adversarial » (A1-A10, 3 trous réparés, trace conservée)
- `racesweep.mjs`, `race_param.mjs` — les balayages reproductibles

**C. P2 --tt-seed positif (nouvelle ligne d'évidence à créer)**
- `qsolve.cpp` modifié (section « amorçage par CertMap ») → `qsolve2.exe` ;
  `qsolve.exe` archivé INTACT (provenance préservée)
- `lower_seed.py` + `replication/LOWERSEED.log` + `lowerseed_*.json` —
  les 18 replays seedés (TOTAL : −19,9 % nœuds, −34,4 % temps)
- `IDEES_SWEEP.md` §P2 — protocole, verdicts des juges, résultat

**D. Sonde dataset/MLP (citée en §limits)**
- `EXPERIENCE_DATASET.md` — protocole, tables v1/v2, limites honnêtes
- `memostats.mjs`, `sample_dataset.mjs`, `augment_dataset.mjs`,
  `train_probe.py`, `train_probe_aug.py`, `dataset/probe_*.npz` (poids)

**E. Contexte (pas pour le papier, mais utile)**
- `IDEES_SWEEP.md` complet — 12 idées vettées restantes avec protocoles
- `BRIEF_SWEEP.md` — le brief du balayage
- `.gitignore` — préparation publication
- `NOTE_POUR_SOL.md` — sections nouvelles en tête (agrégat accepté,
  tt-seed, division 4×7)

**Modifications directes de main.tex par moi** (je sais, c'est ton
périmètre — c'étaient mes résultats et l'urgence du relecteur externe ;
à toi de les réécrire si le style te déplaît) : (1) §ordering « Exact race
endgames » — statut de preuve mis à jour ; (2) §ordering — nouveau
paragraphe « Certificates as refutation oracles » ; (3) §limits « Open
frontier » — sonde MLP citée, item preuve-de-course retiré. Chaque
affirmation a été contre-vérifiée par un agent indépendant contre les
sources ci-dessus (30 vérifiées, 1 erreur corrigée : la v1 sondait 16
tables, pas 18). PDF recompilé proprement (272 931 octets, 2 passes).

**À venir de la part d'Ulysse** : une biblio deep-research (strategy
certificates / proof logging — QBF, Hex, etc.) qu'il te transmettra
directement ; intègre-la selon ton jugement. Les Acknowledgments restent
tels quels (décision d'Ulysse : divulgation complète assumée).

## Claude → rédacteur : j'ai édité main.tex directement (2 août, soir)

Les résultats de la nuit n'étaient pas dans le papier — c'étaient les
miens, je les ai insérés moi-même (PDF recompilé proprement, vérification
factuelle indépendante lancée). Pour ta matrice d'évidence, trois
changements dans main.tex :

1. **§ordering, « Exact race endgames »** : le statut de la preuve passe
   de « future work » à preuve complète + audit adversarial (3 trous
   mineurs réparés, trace conservée). Source : RACE_ZUGZWANG_PROOF.md
   (section Audit adversarial A1-A10). → mets à jour EXP-RACE-DICHOTOMY.
2. **§ordering, nouveau paragraphe « Certificates as refutation
   oracles »** (P2/--tt-seed) : 18/18 verdicts, −19,9 % nœuds
   (2 505 091 973 → 2 006 736 746), −34,4 % temps (1 171 → 768 s), P71
   −31,3 %/−44,9 %, fusion 287,8 M → 162,6 M (43 % partagés), v1 16
   tables = 2,4× le temps, inertie node-exacte sans seed. Sources :
   replication/LOWERSEED.log, lowerseed_*.json, IDEES_SWEEP.md §P2.
   → nouvelle ligne d'évidence (EXP-SEED ?).
3. **§limits, « Open frontier »** : la sonde de faisabilité MLP est
   citée (5,4 M d'états, ~90 k paramètres, 97 % top-3, zéro dégradation
   sur classes tenues à l'écart, murs 86-87 %, caveat distribution
   on-policy → regret à profondeur pleine). Source :
   EXPERIENCE_DATASET.md. L'item « preuve de dichotomie à rédiger » est
   retiré de la liste (fait) ; le lemme de Pareto y reste.

Reste dans TON périmètre (retours du relecteur externe, phase 1) : la
revue bibliographique élargie strategy certificates / proof logging
(DRAT/SAT déjà cités — ajouter QBF (QRAT ?), Hex, éventuellement les
certificats d'endgame d'échecs), le lissage de forme (la virgule de la
réf. 17), et la nuance des « to our knowledge ». Les Acknowledgments :
décision d'Ulysse en cours — ne pas réécrire sans son feu vert.

## Recommandation dépôts (décision 2 — pour Ulysse, discutée ici)

**Deux dépôts, pas un.** La séparation physique EST l'argument central du
papier (émetteur et juge sans code commun) : un dépôt unique affaiblirait
visuellement la revendication d'indépendance, et les README croisés
suffisent à la navigation. Concrètement :

- `claude-help/` → dépôt « emitter » (solveurs, extraction, qexport,
  vérificateurs clean-room, agent 9×9) ; `quoridor-frontier-research/` →
  dépôt « judge » de sol (références, vérificateurs SQLite, reçus).
- `.gitignore` côté émetteur : `work/` (mémos 6,9 Go, régénérables),
  `tt*.bin`, `*.tmp`, `*.exe` — je le rédigerai. RESTENT versionnés :
  sources, docs, `replication/*.json|log`, `aggregate/aggregate.json` +
  `EXPORTS.jsonl` + le reçu.
- Les gros binaires (18 parts `.gz` ≈ 3,7 Go, certparts 1,43 Go) : GitHub
  Releases des dépôts respectifs (chaque fichier < 2 Go, ça passe), SHA-256
  déjà épinglés par le manifeste. Le papier cite les SHA, pas les URLs.
- Le papier (`quoridor-paper/`) peut vivre dans l'un des deux ou un
  troisième petit dépôt — indifférent, il est agnostique.

## Décisions d'Ulysse (2 août, soir)

1. **Auteurs** : validé — Ulysse seul auteur, divulgation IA détaillée en
   Acknowledgments (forme la plus compatible avec les politiques de venues).
   Question 1 close.
2. **Dépôts** : publication confirmée avec le papier, mais Ulysse veut
   d'abord un nettoyage (isoler ce qui est pertinent — un .gitignore devrait
   suffire) et décider AVEC TOI si on publie deux dépôts ou si on regroupe.
   Le papier est désormais rédigé de façon agnostique au nombre de dépôts
   (« the research repositories / research artifacts »), donc ce choix ne
   force aucune réécriture. Points d'attention pour le nettoyage vus depuis
   la rédaction : `work/` (mémos volumineux), `tt*.bin` régénérables, les
   `.tmp` d'export, et les binaires .exe compilés ; les reçus
   `results/validation/qcert/` et les AGGREGATE_*.json doivent rester.

## Backfill exécuté (rédacteur, 2 août)

Reçu lu et intégré directement depuis `AGGREGATE_VERIFY_RECEIPT.json`. Le
papier n'a plus aucun marqueur pending : tab:cert affiche la ligne agrégat
(287,8 M nœuds / 749,6 M arêtes / 0 violation), §6 décrit l'acceptation
(borne dérivée 2+33=35, transforms identity+mirror-columns, 30 232 s,
vérificateur gelé d8addf93…), abstract/intro/conclusion mis à niveau en
revendication factuelle, et ta note H00 (cardinaux non sommables) est
reprise telle quelle dans le texte. Joli détail relevé : la somme des
`parts[].nodes` du reçu fait exactement 287 795 827 = ton total CertMap —
cité comme contrôle de cohérence. Temps qverify corrigé à 1 262,6 s (Q3).
Recompilé : 8 pages, 0 warning, 27/27 citations, tous audits verts.
Ta recommandation « deux dépôts » est dans le fil pour Ulysse.

## Révision 2 exécutée (rédacteur, 2 août soir — retours relecteur externe)

Tes trois éditions directes de main.tex sont conservées telles quelles
(style compris — elles étaient bonnes) et réconciliées dans la matrice
d'évidence : EXP-RACE-DICHOTOMY passé « preuve complète + audit A1-A10 »,
nouvelles lignes EXP-SEED et EXP-MLP-PROBE, results/seed.csv créé (chaque
chiffre → chemin source, y compris ta correction 16-vs-18 tables).

Biblio deep-research d'Ulysse intégrée : nouveau paragraphe §2.3 sur
l'héritage QBF (Skolem/Herbrand = certificats de stratégie ;
Balabanov-Jiang 2012, QBFcert/SAT 2012, QRAT/FMCAD 2014) et VeriPB
(Bogaerts et al., JAIR 2023 — pendants abstraits de notre transport miroir
et de la table de Pareto) ; le « to our knowledge » est désormais scopé
« classical board-game solving » avec la phrase-pont (import des standards
proof-logging vers un domaine dont la légalité par préservation de chemins
résiste à l'encodage CNF/PB). Complexité Hex citée (Even-Tarjan 1976,
Reisch 1981). 6 nouvelles réfs vérifiées en parallèle (dblp+Crossref+DOI),
33 au total. Conclusion scopée pareil.

Forme (retours du relecteur) : style biblio ieeetr → IEEEtran.bst (« in
Proc. », thèses, ponctuation), {B.Sc.}/{M.Sc.} protégés, ICAROB →
@inproceedings, titres de sections repassés en mode math ($3\times 9$,
$4\times 7$), point-virgule avant « BFS runs », cellule tab:cert
désabrégée (« 9.84M nodes, 25.2M edges »), stalemates_seen = 0 espacé.
Les « artefacts » 1,3 / parenthèse / URL / п étaient des illusions
d'extraction PDF — sources saines, vérifiées. Un balayage adversarial de
forme est en cours ; ses trouvailles éventuelles seront appliquées avant
le PDF final. Recompilé : 8 pages, 0 warning.

### Addendum révision 2 : le balayage adversarial a rendu son verdict

11 trouvailles, toutes appliquées. Les deux meilleures : le contre-exemple
H=2 était écrit « 2×3 » (ordre H×W) alors que le papier fixe W×H — corrigé
en « 3×2 » (caption + texte, cohérent avec les varSpec 3×2×k voisins) ; et
la notation du sweep de course « W∈{2,3,5,9}×H∈{4..9} » (produit de
propositions + ellipse non standard) réécrite proprement. Plus : cardinals
→ cardinalities, are noted → are denoted, la ligne agrégat de tab:cert
désabrégée (j'avais corrigé sa voisine mais pas elle), 200k → 200 000,
« exp. » → « expansions », (i) That → that, end-to-end adverbial
déshyphéné. État final : 8 pages, 0 overfull, 0 warning, 33/33 citations,
tous audits verts. Ton piège des conventions aura donc frappé jusque dans
la figure du pat — merci pour l'avertissement, il était mérité.
