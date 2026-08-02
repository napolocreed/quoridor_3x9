# Idées pour la suite — notes de fin de session, 2 août 2026

Écrites avec tout le projet en tête, avant compaction de contexte. Par ordre
de conviction décroissante.

## 1. Certificat de survie : rendre « exactement 35 » entièrement vérifiable

La borne inférieure repose encore sur la confiance dans la recherche (18
réfutations « proved=false »). Or le même mécanisme qcert-1 peut certifier le
négatif : définir `Survive(s, J2, k)` = « J2 a une stratégie qui évite toute
victoire de J1 pendant ≥ k plis ». Un certificat de survie donne, à chaque
nœud J2, le coup de survie ; le vérificateur contrôle TOUS les coups J1 et la
décroissance des budgets — exactement la machinerie de qverify avec les rôles
échangés. Un certificat de survie à 33 plis depuis la racine transformerait
la minimalité en artefact vérifiable sans recherche. Risque : la taille (le
DAG branche maintenant côté J1) — à estimer sur 3×3/3×5 d'abord avec qcert.mjs
avant d'attaquer 3×9.

## 2. Les mémos comme jeu d'entraînement : la voie AlphaZero est déjà pavée

**Premier pas fait (2 août)** : `memostats.mjs` décode les mémos (BigInt
OBLIGATOIRE — clés jusqu'à 2^54, une conversion float64 corrompt le bit de
trait ; validé exactement contre qexport : j1 = 6 465 147 sur H10, zéro
anomalie). Faits H10 : 221 621 configs de murs distinctes, stratégie
optimale = 87 % pion / 8 % mur H / 4 % mur V, histogramme des rangs en
dents de scie de parité. Entrée réseau minuscule confirmée : 16+16 bits
d'ancres + 2 cases + 2 stocks.

Les 17 `memo_*.bin` contiennent **284 207 012 états exactement étiquetés**
(coup optimal + rang de gain) sur 3×9×10, et le format est trivial à décoder
(qexport.cpp). C'est un dataset d'imitation parfaite qu'aucun projet Quoridor
n'a jamais eu : distiller un petit réseau politique/valeur dessus, mesurer sa
fidélité hors échantillon, puis le brancher comme heuristique d'ordering dans
qsolve (les régimes d'ordering sont LE goulot mesuré — cf. horizon reversal
de P(4,2)). Si ça marche sur 3×9, la même recette s'applique à 4×7 en
auto-génération (le solveur étiquette ses propres sous-problèmes résolus).
NNUE avant AlphaZero : l'entrée est minuscule (masques de murs + 2 cases).

## 3. Fins de partie exactes stratifiées par stocks — l'arme pour 4×7×7

La table de course (race.js) résout (0,0) murs en 13 122 états. Stratifier :
à (s1,s2) stocks totaux ≤ 2, le sous-jeu « murs restants × course » reste
minuscule PAR configuration de murs atteinte. Dans qsolve, remplacer la
feuille « d ≤ 0 → false » par un oracle exact quand les stocks sont épuisés
(et borner par ⌈d0/2⌉ raffiné par la parité de course quand stocks faibles).
Sur 4×7 la course nue fait 28×28×2 = 1 568 états par config — gratuit. Le
zugzwang mutuel (−16 sur 9×9 symétrique) montre que la parité de course
n'est PAS celle que l'intuition donne : un trait exact bon marché pour le
sélecteur de politiques de sol, et peut-être des coupes franches en fin de
recherche 4×7. C'est mon meilleur candidat pour repousser la frontière.

## 4. Théorème du zugzwang de course — FAIT le 2 août (balayages exacts)

Voir `RACE_ZUGZWANG.md` + `racesweep.mjs` + `race_param.mjs`. Dichotomie
complète vérifiée sur 24 plateaux (W ∈ {2,3,5,9} × H ∈ {4..9}) : à
distances égales, le trait perd ssi pions alignés face-à-face à écart pair
(H impair — position à symétrie centrale), en exactement 2d plis ; il gagne
partout ailleurs ; zéro nulle sur tous les plateaux. RESTE : la rédaction
formelle de la preuve par imitation (lemme du tempo du saut + 4 cas de
contact, ~une page) — éventuellement pour l'agent rédacteur LaTeX.

## 5. Agent 9×9 : la fragilité au bon prix

Le signal détour vaut +89 Elo à profondeur fixe mais coûte −108 au temps
réel (4 BFS/éval). Deux implémentations bon marché à essayer :
- cache (wallLo, wallHi, cellule) → détour, invalidé par coup de mur
  seulement — dans un sous-arbre sans pose de mur, le détour de chaque camp
  ne change que par le déplacement du pion (recalcul rare) ;
- fragilité au TRI seulement : calculée une fois par nœud pour ordonner les
  murs candidats (pas dans l'éval des feuilles).
Autres chantiers 9×9 : livre d'ouvertures (les 24/24 du trait le crient),
Rust→WASM si l'app en a besoin, et brancher `worker.js` sur la démo.

## 6. Divers consignés

- qverify imprime les chemins Windows avec antislashs bruts dans son JSON de
  sortie (invalide) — sanitisé à l'agrégation, à corriger dans la source.
- L'export qcert-1 des classes pion (~6-9 Go JSONL) attend le vérificateur
  externe trié de sol ; gzipper à l'émission (ratio 7×).
- Les TT par classe coûtent ~3,5× plus de nœuds que la TT partagée mais
  parallélisent parfaitement — le bon compromis dépend de la RAM libre,
  qui fluctue quand sol travaille sur la même machine.
- H2 : la convention de pat est sémantiquement vivante (7-42 verdicts
  divergents mesurés par variante) — ne jamais publier de résultat H=2 sans
  fixer la convention explicitement.
