# IDEES_SWEEP — synthèse du balayage d'intuitions (2026-08-02)

Source : 16 propositions issues de 8 personas × 2, jugées par un juge règles/exactitude
et un juge coût/bénéfice. Brief : `claude-help/BRIEF_SWEEP.md`.
Convention : shortlist = gardées par les DEUX juges (keep+keep ou keep+maybe), classées
par espérance de gain / coût. Les fusions décidées par les juges sont appliquées.

---

## Shortlist classée

### 1. P2 — Amorçage de la réfutation par les mémos de la borne sup (`--tt-seed`) 【règles : keep · coût : keep】 — ✅ FAIT (nuit du 2-3), POSITIF
**Résultat** : qsolve2.exe (archivé intact), inertie node-exacte sans seed ;
table unique fusionnée (162,6 M d'entrées — 43 % de doublons inter-branches,
découverte en soi) ; **18/18 réfutations : verdicts identiques, −19,9 % de
nœuds, −34,4 % de temps** (P71 : −31,3 %/−44,9 %). La v1 à 16 tables
séquentielles coûtait 2,4× le temps : la fusion était indispensable.
Journaux : replication/LOWERSEED.log. Transfert 4×7 proposé à sol.
**Idée.** Les CertMaps `memo_*.bin` (287,8 M d'états « Win=true en ≤ r », certifiés qverify)
sont des faits monotones en budget : au nœud s d'une réfutation avec budget b, si le mémo
donne r ≤ b, la branche est Win=true sans expansion. Option `--tt-seed <memo.bin>` dans
qsolve : CertMap chargée en lecture seule (mmap partagé), consultée avant expansion, jamais
écrite. Zéro contention, parallélisme intact — c'est la « base de finales partagée » de
checkers. Attaque les goulots 4 (borne inf aussi chère que la sup), 1 (la chaleur de TT vaut
4,5× mesurés : 129 M/582 M) et 3 (regagne une part du 3,5× perdu par les TT par classe).
**Protocole.** (1) Implémenter `--tt-seed` en réutilisant le décodeur CertMap de
qexport/qverify (~1 jour). (2) Rejouer lower.py sur 2-3 classes 3×9×10 (dont P(1,1), 33 plis)
avec seed + compteur seed_hits/expansions ventilé hits_utiles / hits_budget_insuffisant ;
comparer nœud à nœud avec `replication/AGGREGATE_lower.json` (<1 h). (3) Si positif : sur 4×7,
conserver les CertMaps partiels de la borne sup et seeder les 38 réfutations du pli 27.
**Critère.** ≥ 30 % de nœuds en moins sur les classes testées (référence 2 505 091 973 au
total), verdicts identiques, RAM ≤ 2,5 Go, seed_hits ≥ 5 % des expansions ; < 10 % = négatif
à archiver.
**Réserves des juges.** Vérifier que la clé mémo inclut trait/stocks et que le rang min-rem a
la même normalisation de parité que relevantDepth ; imposer le mmap PARTAGÉ (2,3 Go × 12
workers ne tient pas en copies privées sur 16 Go). Risque principal : disjonction des
distributions (l'oracle juste consulté dans un régime jamais atteint) — tranché par le
compteur en <1 h.

### 2. P4 ⊕ P1 ⊕ P12-phase-1 — Filtre témoin exact de légalité (fusion) 【règles : keep×3 · coût : keep (P4 représentant, P1 et P12-ph1 absorbés)】
**Idée.** Un chemin-témoin par pion, extrait par descente gloutonne du champ BFS déjà payé
(dist_configs), stocké en bitmask d'arêtes dans le cadre de pile DFS. Un mur bloque 2 arêtes
précises (table précalculée slot→masque, apport de P1) : s'il ne coupe aucun témoin, il est
légal ET la distance du pion s'hérite sans BFS (argument P12 : le chemin survivant témoigne
dist inchangée) ; BFS seulement pour le pion effectivement coupé. Filtre EXACT, unilatéral,
composé avec la porte union-find : arbre et verdicts inchangés au nœud près = harnais de
correction gratuit. Attaque le goulot 2 (~2,3 BFS/nœud, 1,33 G d'appels sur une branche 3×9).
**Prérequis obligatoire (hérité de P5, exigé par le juge coût).** Profil Very Sleepy/gprof
½ journée sur `qsolve --mode branch` classe P(7,1) : part de temps mur réellement en
BFS+dist_configs. Si < 25 %, tout le cluster légalité est plafonné — abandon avant d'écrire
une ligne.
**Protocole.** Compteurs BFS-appelés / candidats-court-circuités ; rejouer la branche 3×9 de
référence : nœuds et verdicts STRICTEMENT identiques (toute déviation = bug), seuls appels
BFS et chrono changent ; puis une réfutation 4×7 à profondeur 25. Échelle d'abandon la moins
chère du lot : ratio mesurable dès 3×7, < 30 % = archive sans toucher 3×9. ~1 jour + <1 h.
**Critère.** ≥ 60 % des appels BFS de légalité éliminés sur la branche 3×9 (1,33 G → ≤ 530 M),
chrono ≥ −10 %, confirmé sur 4×7 (cible : ≥ 60 % des candidats passés porte union-find
tranchés sans BFS). Bonus aval : réactiver la fragilité-au-tri dans arena.js.

### 3. P7 — Certificat d'arête serrée : héritage de φ et coupe admissible 【règles : keep · coût : keep】
**Idée.** Mémoïser les potentiels φᵢ(v)=dist(v, rangée but de i) (déjà calculés par
dist_configs, mémoire marginale quasi nulle). Si aucune des 2 arêtes d'un mur n'est serrée
(φ(u)=φ(v)+1) pour aucun des deux champs, les distances sont EXACTEMENT inchangées : légalité
héritée + partage du champ par pointeur (memo hit garanti pour la config fille — strictement
plus fort que le témoin sur le volet distance). Bonus : φ monotone sous ajout de murs ⇒ borne
inférieure admissible héritée, coupe les réfutations quand φ dépasse le budget (goulot 4), en
gardant la convention ⌈d/2⌉ / marge de saut du code (qsolve.cpp l. 384-388).
**Protocole.** Phase 1 (1 h, éliminatoire) : compter la fraction des appels de légalité où
les 8 tests d'extrémités passent. Phase 2 : skip + partage par pointeur, même classe, nœuds
IDENTIQUES exigés, temps mur mesuré. Phase 3 : réfutation 4×7 pli 27 avec coupe φ-héritée.
À instrumenter dans la MÊME après-midi que P4 (mêmes compteurs).
**Critère.** Phase 1 ≥ 50 % de BFS éliminables sinon abandon ; phase 2 ≥ −15 % temps mur à
nœuds identiques ; phase 3 ≥ −10 % nœuds. Risque (trafic mémoire > BFS économisés, le mode
d'échec du cache-first archivé) isolé par construction en phase 2.

### 4. P8 — Tri tropical des murs : arêtes serrées pondérées par largeur de niveau 【règles : keep · coût : keep】
**Idée.** Pendant le BFS déjà payé, précalculer le masque des arêtes serrées Tᵢ et les
largeurs cnt_i[k] par niveau (proxy min-coupe de Menger). Score O(1) d'un mur candidat :
Σ 1/cnt_adv[k] sur les arêtes coupées de T_adverse − idem côté propre. Clé de TRI uniquement
(jamais dans l'éval) : régression bornée par construction, aucune atteinte à l'exactitude.
Seule attaque du goulot dominant (n°1, ordering : 129 M → 582 M) à coût quasi nul
(popcount + 2 lookups).
**Protocole.** (A) 3 classes 3×9 en paires TT chaude/froide, ordering actuel vs + départage
tropical. (B) 2 des 38 réfutations 4×7 pli 27. (C) arena.js 9×9, 200 parties temps réel.
Recommandation du juge coût : passer d'abord le score par la sonde offline MRR de P9 (1 h sur
memostats) pour un kill encore moins cher.
**Critère.** A/B : ≥ 5 % de nœuds, MÊME SIGNE sur les 5 mesures (signe instable = négatif à
archiver, pas un réglage à sauver). C : ≥ +30 Elo temps réel.

### 5. P11 — Tri σ-d'abord : imitation centrale aux nœuds J2 des réfutations 【règles : keep · coût : keep】
**Idée.** Aux nœuds J2 (existentiels : UN coup de survie suffit), si la position est à un pli
de la symétrie centrale σ, essayer σ(dernier coup J1) EN PREMIER (O(1), légalité par le
movegen existant). Si l'imitation survit souvent, l'arbre de réfutation s'effondre vers le
seul branchement J1. Réutilise la stratégie prouvée du zugzwang de course (24 plateaux) ;
s'applique telle quelle à 4×7 (H=7 impair, départ auto-symétrique). Correction gratuite :
pure permutation d'ordre, aucun élagage nouveau (sûr même en zone de zugzwang).
**Protocole.** Compteurs sigma_candidat / sigma_legal / sigma_survit_premier ; rerun des 18
réfutations 3×9×10 (~20 min, vérité terrain certifiée) ; puis bras 4×7 apparié à budget fixe.
**Critère.** ≥ 15 % de nœuds sur l'agrégat des 18 réfutations (rejet < 5 %), verdicts 18/18 ;
sigma_survit_premier ≥ 60 % aux nœuds quasi-symétriques → portage 4×7 avec cible ≥ 8 %
(au-dessus du bruit 3-7 %). Résultat nul = ½ journée perdue, le meilleur risque/coût du lot
ordering-J2.

### 6. P14 — Certificat de survie par automate : la politique en Ko, la clôture énumérée 【règles : maybe · coût : keep】
**Idée.** Certifier Survive(s, J2, 33) non par la table état→coup (6-9 Go) mais par la
POLITIQUE : automate ~3 états (mur max-retard sur la géodésique J1 ; sinon coup de course par
dichotomie ; sinon pas de côté canonique). Le vérificateur (qverify aux rôles échangés)
énumère la clôture (tous coups J1 × réponse unique de π) sans la stocker : certificat en Ko,
lève le blocage heap JS de qcert-1. La survie certifiée n'exige PAS l'optimalité de π.
Rendrait « exactement 35 » vérifiable sans confiance dans la recherche (goulot 4, axe
« certificat moins cher » explicitement demandé).
**Clarifications EXIGÉES par le juge règles avant tout code.** (1) Ψ = 2·d1−1+2·retards viole
la marge de saut telle qu'écrite : Ψ doit être DÉCORATIF (jamais utilisé pour élaguer ou
certifier sans énumérer jusqu'au budget), sinon unsound ; « retards garantis restants »
présuppose un théorème de disponibilité non fourni. (2) « clôture jamais stockée » : un cache
de dédup (état, plis restants) est sound et probablement indispensable — assumer la RAM.
**Protocole.** Une soirée JS : π + clôture sur 3×3 puis 3×5 (valeurs connues), mesurer
k_π = plis réellement survécus. Si k_π = v−2 : une branche 3×9, extrapoler. Repli gradué :
table d'exceptions minée des mémos (viable si < 1 % de la clôture).
**Critère.** 3×5 : k_π = v−2 exactement, clôture < 1 min ; échec net si k_π ≤ v−4. Branche
3×9 : clôture ≤ 5× les expansions de la passe exhaustive, RAM ≤ 3 Go, certificat ≤ 100 Ko.

### 7. P16 — Régression de masse de réfutation (strong branching imité) 【règles : keep · coût : maybe】
**Idée.** Pendant lower.py, journaliser (état J2, coup, log₂ du sous-arbre de réfutation) —
le solveur s'auto-étiquette. Régresseur minuscule prédisant le coût de disproof ; aux nœuds
J2 des réfutations, trier par coût prédit CROISSANT (nœud ET : le moins cher d'abord = le
gain du strong branching). Distinct du DF-PN archivé : aucun PN/DN au runtime, O(1) prédit.
Le coût-de-preuve n'est pas la valeur : signal réellement nouveau. Goulot 4 frontal.
**Protocole.** Logging TT froide (1 nœud sur k) ; entraîner, holdout par classe de premier
coup (12 train / 6 test) ; rerun lower.py froid sur les 6 classes de test vs
AGGREGATE_lower.json, verdicts 18/18. Une seule relance dagger autorisée.
**Critère.** Spearman ≥ 0,6 et moins-cher-premier ≥ 50 % sur classes jamais vues ; puis
≥ 25 % de nœuds en moins bout-en-bout, temps ≤ baseline. Coût honnête 3-4 jours (encodeur de
features partagé avec P15) — premier pari ML à tenter, AVANT P15.

### 8. P13 — Mur max-retard sur la géodésique de J1 aux nœuds J2 【règles : keep · coût : maybe】
**Idée.** Dans les réfutations, essayer d'abord le mur retardateur w* maximisant Δd1 sur la
géodésique de J1 (candidats ≤ 2·d1, filtrés union-find, un BFS chacun) : si le retard suffit,
le sous-arbre tombe par la coupe de distance DÉJÀ prouvée en un pli. Permutation pure,
correction gratuite. Attention (juge règles) : la coupe réelle est ⌈d1/2⌉ coups propres avec
marge de saut, pas « 2·d1−1 > r−1 » — effondrements plus rares qu'annoncé.
**Protocole/critère.** selftest, puis classe de réfutation la plus chère : nœuds ET temps ET
appels BFS vs baseline ; ≥ 15 % de nœuds sur l'agrégat des 18 sans régression temps > 5 % ni
BFS > +10 % ; sonde 4×7 ≥ 20 %. Risque assumé : nœuds ↓ mais temps ↑ (le scoring aggrave le
goulot 2) — replis définis (profondeurs faibles, 2 premiers candidats). **Séquencement : après
P11 (surcoût nul) et idéalement après P4/P7 (qui rendent le scoring moins cher).**

### 9. P12-phase-2 — Tri murs-chauds-d'abord (add-on du témoin) 【règles : keep · coût : maybe (ph. 1 fusionnée dans P4)】
**Idée.** Une fois l'infrastructure témoin de P4 en place : trier en premier les murs qui
touchent le chemin adverse (« chauds »), les murs froids (température nulle sur la distance)
en dernier. Quasi gratuit, ordering pur.
**Protocole/critère.** Flag dans le même run apparié que P8 (TT froide, graine fixe) ;
≥ −8 % de nœuds sur le bras 4×7 ; si échec, l'héritage phase 1 (dans P4) reste acquis.
Valeur entièrement conditionnée au sort de P4/P7.

### 10. P9 — Ordering électrique (Laplacien) : ÉTAPE 0 SEULE autorisée 【règles : keep · coût : maybe】
**Idée.** Un solve Laplacien par pion (super-puits = SA rangée but — échappe réellement au
négatif λ₂) note tous les murs d'un coup via l'énergie coupée (φa−φb)²+(φc−φd)². Nuance du
juge règles : c'est une MINORATION de ΔR, pas le ΔR exact — acceptable pour un tri.
**Protocole/critère.** UNIQUEMENT l'étape 0 offline (1 h, memostats, 100 k états à
coup-mur-optimal) : top-3 ≥ 55 % ET MRR > ordering actuel rejoué, sinon poubelle. Étapes 1-3
(intégration qsolve, arène) GELÉES tant que la sonde n'a pas strictement battu la baseline.
Risque nommé : sur W=3/4 le courant se concentre sur la quasi-géodésique et le signal
dégénère en information déjà présente.

### 11. P15 — NNUE d'ordering distillé des mémos 【règles : keep · coût : maybe】
**Idée.** Distiller les 284 M d'états exactement étiquetés en NNUE int16 incrémental, injecté
comme clé de tri (zéro risque de soundness). Atout unique au monde : regret EXACT mesurable
(rang prédit − rang optimal, à profondeur pleine). Substitut de chaleur de TT → attaque
l'écart 129 M/582 M et le goulot 3 (parallèle par classe).
**Protocole/critère.** Étape 1 offline autonome (~2 jours réels, pas « 1 jour ») : holdout
PAR config de murs, regret ≤ 1 pli et top-1 ≥ 90 % sinon stop. Étape 3 : classe volatile en
TT froide 582 M → ≤ 300 M (stretch 150 M = parité chaude), temps mur ≤ 1,1× ; 3 coups 4×7
≥ −20 %. Ajouter le TRAIT aux features (oubli relevé). **Gated derrière P16** (encodeur/
inférence partagés, P16 vise le chemin critique pour moins cher). Coût honnête : ~1 semaine.

### 12. P6 — Détour exact O(W³) par matrices de bord préfixe/suffixe 【règles : keep · coût : maybe】
**Idée.** Matrices min-plus L_r/U_r cachées le long de la ligne de recherche → détour EXACT
de chaque mur candidat par clôture locale, sans BFS ; clé d'ordering principielle (goulots 1
et 4). Distinction valide du négatif archivé : tri seulement, jamais aux feuilles.
**Mais** : l'infrastructure est celle de P5 (tuée), coût réel 4-6 jours, sous-estimé.
**Protocole/critère.** Préalable obligatoire : sonde offline gratuite (~1 h, méthodologie
étape 0 de P9) — le signal détour-exact évalué par BFS brut échantillonné contre les coups
optimaux des mémos ; si le MRR ne bat pas l'ordering actuel, tout tombe. Le volet 9×9
(729 ops vs BFS 81 cases, cible ≥ +30 Elo temps réel vs −108/+89 encadrants) peut vivre
seul et est le seul où l'algèbre paie clairement. Attention à la fenêtre de 2 rangées pour
les murs verticaux.

---

## Tuées et pourquoi

- **P1 (témoin bitmask, lentille tablebases)** : tuée pour REDONDANCE seulement — mécanisme
  identique à P4/P12-ph1 ; ses deux apports (table slot→masque, test décisif 4×7) sont
  absorbés dans P4. Aucun défaut de fond.
- **P3 (canonisation duale, groupe d'ordre 4)** : DÉJÀ implémentée (canonKey, qsolve.cpp
  l. 292-309, SYMMODE=2 par défaut — les baselines incluent ce quotient) ; et la
  mutualisation attaque/défense promise est structurellement inaccessible par quotient de
  clé (target transformé conjointement, toutes les requêtes d'un run fixent le même target
  ⇒ zéro hit dual possible).
- **P5 (automate de frontière min-plus)** : dominée dans toutes les branches du futur — si
  les filtres exacts à 1 jour (P4/P7) réussissent, gain résiduel laminé ; s'ils échouent
  (part de temps faible), elle échoue pour la même raison, à 4-5× le coût. **À sauver : son
  étape 0 (profil ½ journée), devenue prérequis obligatoire de P4/P7.**
- **P10 (légalité algébrique L⁺/Woodbury)** : un déterminant FLOTTANT (erreur Woodbury
  accumulée, écarts au singulier ~1/T² sous l'epsilon des doubles) DÉCIDE un verdict de
  légalité sans critère de détection certifié — heuristique numérique dans une preuve ;
  l'exactifier tue le gain ; dominée par P4/P7 exacts au même goulot.

---

## Recommandation — les deux actions immédiates

**Action 1 : P2 (`--tt-seed`).** Meilleur rapport gain/coût du lot, unanimité des juges.
Tout est déjà sur disque (CertMaps certifiés, baseline au nœud près), ~1 jour
d'implémentation en réutilisant le décodeur qexport/qverify, verdict en <1 h de machine avec
compteurs qui tranchent aussi le risque (disjonction des distributions). Attaque
simultanément les goulots 4, 1 et 3, et définit directement le protocole 4×7 (seeder les 38
réfutations avec les CertMaps partiels de la borne sup). Deux points d'exécution : cohérence
clé mémo ↔ états de réfutation (trait/stocks, normalisation de parité), et mmap partagé.

**Action 2 : le paquet légalité exacte — profil d'abord, puis P4⊕P7 ensemble.**
½ journée de profil (étape 0 héritée de P5, ÉLIMINATOIRE : si BFS+dist_configs < 25 % du
temps mur, tout le cluster est plafonné et on économise 2 jours) ; puis une seule après-midi
d'instrumentation commune (compteurs partagés) et ~1 jour d'implémentation pour le témoin
(P4, légalité) + l'arête serrée (P7, héritage de distance et coupe admissible φ). Filtres
EXACTS : arbre inchangé au nœud près = validation gratuite contre les agrégats archivés ;
échelles d'abandon à 1 h (comptage P7 < 50 %, ratio P4 < 30 % dès 3×7). Si succès, débloque
en cascade P12-ph2 et réduit le coût de P13.

*Ensuite, dans l'ordre : P11 (½ journée, verdict en 20 min) et P8 (précédé de la sonde MRR
offline), puis P14 (une soirée JS après clarification du rôle de Ψ), P16 comme premier pari
ML. P9 et P6 n'existent que sous forme de sondes offline à 1 h tant qu'elles n'ont pas battu
l'ordering actuel sur les mémos.*
