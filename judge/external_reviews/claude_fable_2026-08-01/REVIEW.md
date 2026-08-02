# Review — `quoridor-frontier-research` (GPT 5.6 « Sol »)

Reviewer : Claude (Anthropic) — 1er août 2026.
Objet : commit `1fe68fb`, revendication principale : **3×9 à 10 murs = victoire du
premier joueur en exactement 35 plis** ; travail en cours sur 4×7 à 7 murs.

---

## 1. Verdict

Travail de **qualité recherche**, sur un angle complémentaire au mien : Sol ne
construit pas un moteur pour jouer au 9×9, il **résout exactement** des
variantes étroites — et il attaque précisément les deux cases encore ouvertes
de la table de référence publique. La discipline d'audit est le point le plus
remarquable : sémantique de preuve écrite avant le code, reruns conservateurs
avec les optimisations suspectes désactivées, TT fraîche par branche, commandes
et SHA archivés, artefacts reproductibles au nœud près.

J'ai soumis le dépôt à une validation indépendante (détail en §2). **Tout ce
que j'ai testé tient.** Je n'ai trouvé aucune erreur de règles, aucune
divergence de génération, aucune incohérence de preuve. Je relève une
divergence spec/code sur un cas limite (§4a), très probablement sans effet mais
qui mérite d'être fermée, et quelques points mineurs.

La revendication reste, comme Sol le dit lui-même, « un résultat computationnel
reproductible, pas un théorème vérifié machine ». Ma contribution la plus utile
ici : j'ai écrit le début du vérificateur structurellement indépendant qu'ils
réclament (§2, `qref.mjs`).

---

## 2. Ce que j'ai vérifié moi-même

Environnement : Ubuntu 24, g++ 13.3, 1 cœur, 4 Go — binaires **recompilés
depuis les sources** (donc SHA différent de l'archive : la reproduction au nœud
près ci-dessous traverse aussi le changement de toolchain).

### 2.1 Leur propre suite

`make -j2 && make test` : **tout passe** — smoke, 5 issues connues, 2 500
comparaisons différentielles de coups contre leur référence Python, 500
comparaisons de preuves bornées, vérification sémantique des symétries.

### 2.2 Vérificateur clean-room (troisième implémentation)

J'ai écrit `qref.mjs` (Node, ~330 lignes) **à partir de `docs/RULES.md` et
`docs/PROOF_SEMANTICS.md` uniquement** — sans lire leur C++ ni leur référence
Python pendant l'écriture. Résultats :

| test | résultat |
|---|---|
| 2 000 états aléatoires 3×9×10 (leur `frontier_dump`) | **0 divergence** de coups |
| 63 184 états exhaustifs 4×3×3 | **0 divergence** |
| 1 500 états aléatoires 4×7×7 (moteur lazy) | **0 divergence** |
| 3×3×0 résolu indépendamment | J2 en 4 ✓ |
| 3×3×1 | J2 en 8 ✓ |
| 4×3×2 | J2 en 10 ✓ |
| 4×3×3 | J1 en 13 ✓ |
| 3×5×3 | J1 en 19 ✓ |
| 3×5×4 | J2 en 22 ✓ |
| univers de murs 3×9 (mon DP par matrice de transfert) | **2 929 319** — identique |
| univers de murs 4×7 | **16 368 423** — identique |
| états sans coup légal (sondage, ~800 k états saturés en murs) | **0** rencontré |

Les six variantes coïncident aussi avec la table publique de Slatton (§3), qui
constitue une quatrième source indépendante pour ces valeurs.

### 2.3 Reproduction du résultat phare, au nœud près

Trois classes d'audit 3×9×10 rejouées avec les commandes archivées exactes
(`--no-bounds --no-pawn-table`, TT 2²⁶, ordre 1) :

| classe | attendu (archive) | obtenu ici | verdict |
|---|---|---|---|
| borne sup, `reply_19` | 79 766 979 nœuds, prouvée prof. 31 | **79 766 979**, prouvée prof. 31 | identique |
| borne sup, `reply_27` | 142 908 257 nœuds, prouvée prof. 31 | **142 908 257**, prouvée prof. 31 | identique |
| borne inf, `root_31` | 44 048 383 nœuds, réfutée | **44 048 383**, réfutée | identique |

Machine différente, compilateur différent, binaire recompilé : la recherche est
**parfaitement déterministe et portable**. C'est une propriété rare et
précieuse pour un résultat de ce type.

### 2.4 Limites de ma vérification

Je n'ai **pas** refait l'intégralité des 12,9 milliards de nœuds des deux
audits (~42 min sur leur machine, faisable mais hors du budget de cette
review) ; j'ai rejoué ~267 M de nœuds (≈2 %) plus la totalité des petites
variantes. Mon `qref.mjs` peut résoudre 3×5×4 en 39 s ; un re-solve indépendant
complet de 3×9×10 avec lui demanderait de l'optimiser sérieusement (il est
naïf par construction) — c'est l'étape de réplication externe qui manque
encore, et Sol le dit explicitement.

---

## 3. Nouveauté et état de l'art

### 3.1 Résolution de variantes

La référence est **Grant Slatton, « Solving the board game Quoridor »
(25 mai 2026)** — la « public frontier table » que cite le PAPER.md. Sa table :
ligne 3×9 résolue de 0 à 8 murs (J2×5 puis J1×4), **« ? » à 9 et 10 murs** ;
ligne 4×7 résolue de 0 à 6, ouverte de 7 à 10. Travaux antérieurs (analyse
rétrograde japonaise sur petits plateaux, thèses MCTS/GA) plus loin derrière.

Donc : **Sol attaque exactement les deux premières cases ouvertes de l'état de
l'art, et les comble** (3×9×9 et 3×9×10 = J1, la seconde avec horizon exact),
sous réserve de la réplication externe complète. Le résultat est par ailleurs
cohérent avec la structure de la table (bascule vers J1 à partir de 5 murs sur
cette géométrie — l'avantage de tempo finit par dominer la parité de saut). Sur
4×7×7, les bornes partielles (aucun gain forcé ≤ 26 plis pour les deux camps,
ouverture centrale réfutée à 27) sont une vraie avancée incrémentale sur une
case ouverte.

Convergence méthodologique frappante et indépendante avec Slatton :
énumération des configurations de murs + masques de reachability précalculés +
TT + symétrie miroir + recherche « proof-search-like ». Sol ajoute par-dessus :
la **symétrie 180° avec échange des joueurs**, la **normalisation de parité de
profondeur**, la **TT à faits monotones** (avec abort sur incohérence), la
**table de finale pions-seuls** (rétrograde, DTM exact, par configuration), le
**moteur lazy** (configs à la demande — leur profil montre qu'une branche ne
touche que 0,3–4,6 % de l'univers), et surtout **l'appareil d'audit**. La
différence philosophique : Slatton optimise pour résoudre vite ; Sol optimise
pour qu'on puisse le croire. Les deux sont complémentaires — et le cas 8×3×3
= **nulle forcée** découvert par Slatton valide au passage le choix sémantique
de Sol (preuve de forçage bornée, aucune convention de nulle nécessaire pour
un résultat positif).

### 3.2 Jeu 9×9

Aucun moteur public fort et établi : prototypes AlphaZero/MuZero académiques à
tout petit budget (20 itérations, 25 simulations, règles restreintes),
dépôts hobby, thèses. Slatton juge le negamax classique plafonner vers
profondeur ~6 et **propose de financer** une tentative AlphaZero sérieuse. Mon
moteur de la semaine dernière (α-β 378 k nœuds/s, filtrage de murs, union-find)
est donc dans le peloton de ce qui existe, et le plafond que j'avais mesuré
(« la force vient de la profondeur, l'éval linéaire ne se règle pas ») est le
même mur que Slatton décrit (« very few quiet positions », éval difficile).

---

## 4. Réserves et correctifs proposés

**a. Spec/code : la conjonction vide.** `PROOF_SEMANTICS.md` définit
`Win` par « conjonction sur les enfants légaux » — mathématiquement, une
conjonction vide est **vraie** (adversaire pat ⇒ cible gagne). Le code fait
autre chose : `prove()` retourne `false` dès que `n==0`, **quel que soit le
camp au trait**. Divergence de convention sur le pat, non tranchée dans
`RULES.md`. Conséquence théorique : la borne *supérieure* (35) est
conservatrice sous les deux conventions, mais la borne *inférieure* (aucun
gain ≤ 33) pourrait en dépendre si un état sans coup légal était atteignable.
Empiriquement : 0 état de ce type sur ~800 k états sondés et dans mes six
résolutions complètes — la clause est très probablement vacue. Correctif
minimal : (1) trancher la convention dans `RULES.md` ; (2) compter les
`n==0` rencontrés dans les audits et l'archiver — « zéro état pat rencontré »
devient alors un fait d'audit qui rend la question sans objet par construction.

**b. Schéma des artefacts.** Les `reply_XX.json` n'exposent les compteurs que
sous `parsed` (en chaînes). Aplatir `nodes`/`depth`/`status` au premier niveau
en numérique simplifierait l'outillage aval (je suis tombé dessus en scriptant).

**c. `throw 1` / `catch(int)`** pour le timeout : fonctionne, mais une
exception dédiée serait plus robuste à la maintenance.

**d. Lemme de dominance Pareto.** La table Pareto sur les stocks de murs
(moteur lazy) repose sur la monotonie de `Win` dans les stocks (plus de murs
pour soi n'est jamais pire, plus pour l'adversaire jamais mieux). C'est vrai —
un mur en stock est une option, jamais une obligation, preuve en trois lignes
par simulation de stratégie — mais le lemme n'est écrit nulle part. Il devrait
rejoindre `PROOF_SEMANTICS.md` puisqu'un module « exact » s'y adosse.

**e. Nit.** `AGENTS.md`/`README` : quelques chiffres de RSS donnés « roughly » —
préciser la méthode de mesure (VmHWM ?) pour la reproductibilité mémoire.

Rien de tout cela ne remet en cause le résultat ; a. est le seul point qui
touche à la sémantique, et il est fermable en une heure de travail.

---

## 5. Croisement avec mes trouvailles (moteur 9×9, semaine dernière)

| sujet | moi (9×9, jeu) | Sol (étroit, exact) | lecture |
|---|---|---|---|
| Légalité des murs | critère exact par cycle : **union-find à annulation** sur le treillis des jonctions, O(α), zéro précalcul | lookup dans des reachability **précalculées par configuration** (exact, mémoire-lourde, impossible en 9×9) | + l'heuristique de « contact » de Slatton = version informelle de mon critère. Trois solutions au même goulot ; la mienne est la seule sans précalcul → portable chez Sol (§6.3) |
| Multiplicité des plus courts chemins | proposée comme **terme d'évaluation** (« fragilité du chemin »), pas encore implémentée | implémentée comme **ordre de coups** (`path_choice_weight`) : 47,3 s → 3,7 s sur une branche 4×7 (~13×) | convergence indépendante → le signal structurel est réel ; à porter dans mon éval (§6.7) |
| Finale sans murs | proposée (« solveur de course exact ») | **réalisée** : table rétrograde DTM par config, pions seuls | à rapatrier telle quelle côté 9×9 (§6.8) |
| Table de transposition | +7 % seulement en jeu 9×9 | **décisive** en preuve (reply_00 : 727 M hits / 1,5 G nœuds) | les deux mesures sont justes : en preuve bornée avec parité normalisée et deepening, les retranspositions abondent ; en jeu α-β peu profond, non |
| Méthodologie de mesure | « la parité 3-vs-4 à 25 % » était du **bruit d'échantillon** ; ouvertures appariées obligatoires | « les pilotes superficiels choisissent le **mauvais** ordonnancement » ; portefeuilles exacts obligatoires | même leçon, apprise des deux côtés indépendamment |
| Déterminisme | parties reproductibles par graines | reproduction **au nœud près** à travers machines et compilateurs | leur barre est plus haute ; à imiter |

---

## 6. Nouveaux angles d'optimisation

Classés par rapport gain attendu / coût. 1–6 : pour le solveur de Sol.
7–10 : pour notre moteur 9×9.

**1. Certificat de preuve vérifiable (impact : crédibilité, le chaînon
manquant).** Faire émettre par le solveur la **stratégie gagnante** de J1
(un DAG : à chaque état où J1 joue, le coup ; à chaque état adverse, tous les
enfants), puis la faire vérifier par un programme indépendant qui ne fait que :
générer les coups, vérifier la couverture, vérifier les terminaux et le budget
de plis. Mon `qref.mjs` est à 80 % de ce vérificateur. Taille attendue :
sous-arbre dédupliqué ≪ nœuds de recherche (les 727 M de TT hits le suggèrent).
Ça transforme « calcul reproductible » en « **preuve vérifiable
indépendamment** » — exactement la réponse à leur propre section « correctness
boundary », et la condition pour faire mettre à jour la table publique.

**2. DF-PN borné (déjà dans leur plan — à endosser).** Leurs faits monotones
(minWin/maxFail par état) sont précisément la structure dont df-pn a besoin.
Deux précautions : garder la profondeur restante dans l'état (c'est ce qui les
immunise contre le problème graph-history-interaction, qu'un df-pn non borné
réintroduirait), et le trick 1+ε pour limiter les re-expansions.

**3. Porte union-find dans le moteur lazy (mon apport direct).** Aujourd'hui,
chaque placement candidat peut déclencher la construction d'une config (2 BFS +
tables). Or mon critère de cycle répond en O(α) « ce mur ne peut déconnecter
personne » **sans rien construire** : si aucun cycle ne se ferme dans le
treillis des jonctions (bord compris), la légalité est acquise et la
construction peut être différée jusqu'à la visite effective de l'enfant. Leur
profil attribue 21 % du temps à la génération de successeurs ; sur mon moteur
9×9 le même critère a divisé la génération par ~4. Implémentation : DSU à
annulation par pile, ~80 lignes, je peux fournir le patch.

**4. Généraliser la dominance Pareto à la TT.** Au probe, si (stock cible
supérieur, stock adverse inférieur ou égal) d'un fait `Win=vrai` archivé
domine l'état courant, conclure sans chercher (et symétriquement pour
`false`). Le lemme de §4d le justifie. Coût : une indexation secondaire par
(cfg, pions, trait).

**5. Parallélisme par vol de travail.** Le découpage actuel par classe racine
marche mais laisse la classe la plus dure (reply_15 : 2,8 G nœuds, 30 % du
total) sur un seul cœur. Un split au 2e niveau (les ~35 réponses de chaque
classe) avec files de vol équilibrerait ; TT par worker, pas partagée
(leurs runs montrent que la fraîcheur par branche n'est pas chère).

**6. Frontière suivante.** Après 4×7×7 : 4×7×{8,9,10}, puis Slatton lui-même
désigne 7×5 comme la prochaine géométrie intéressante hors de sa table. Le
moteur lazy est le bon véhicule (l'univers 7×5 explose en énumération eager).
Publier 3×9×{9,10} d'abord — contacter Slatton, qui maintient la table et
finance ce champ.

**7. [9×9] Terme d'évaluation « fragilité de chemin ».** Le résultat le plus
transférable de leur travail. Concrètement : double BFS (depuis le pion et
depuis la rangée but), une arête est « sur un plus court chemin » ssi
`d_pion(u) + 1 + d_but(v) == d_total` ; compter ces arêtes (ou les coupes de
largeur 1) donne en O(N) une mesure de la robustesse du chemin. Mon SPSA
montrait que les poids **linéaires existants** ne se règlent pas ; il ne disait
rien d'une **feature manquante** — et leurs mesures d'ordering (13×) montrent
que c'est LA feature manquante.

**8. [9×9] Table de course exacte en finale.** Quand les murs restants ne
peuvent plus affecter les chemins (ou stocks à zéro) : rétrograde DTM sur
81×81×2 états, ~30 ms, remplace mes recherches profondeur 30 par un lookup —
leur `build_pawn_table` se transpose presque tel quel (une seule config).

**9. [9×9] « Mat en N » exact dans l'app.** Leur code démontre qu'un solveur
borné devient tractable dès que le jeu se rétrécit ; en fin de partie 9×9
(≤ 2-3 murs en stock), l'annonce exacte « gain forcé en N » est à portée — et
c'est une feature produit différenciante pour ton app.

**10. [9×9] AlphaZero/NNUE.** L'état de l'art est vide de tentatives sérieuses
et Slatton offre de financer. Mon moteur JS fournit déjà le générateur de
self-play et l'arbitre ; un NNUE léger (features : cases pions, bitmask murs,
stocks) attaquerait exactement le plafond d'évaluation que nous avons mesuré
tous les deux.

---

## 7. Recommandation

1. Fermer §4a (convention de pat + compteur d'audit) et §4d (lemme Pareto) —
   une demi-journée, et la revendication devient inattaquable sur sa sémantique.
2. Produire le **certificat vérifiable** pour 3×9×10 (§6.1) ; je fournis le
   vérificateur indépendant. Publier, faire mettre à jour la table de Slatton.
3. Poursuivre 4×7×7 avec lazy + DF-PN + porte union-find (§6.2-3) plutôt que
   plus de profondeur brute — leur propre redirection va déjà dans ce sens.
4. Côté app 9×9 : porter §6.7-8 dans mon moteur (je peux le faire dès
   maintenant), garder §6.9-10 comme itérations suivantes.

Fichiers joints : `qref.mjs` (vérificateur indépendant), ce document.
