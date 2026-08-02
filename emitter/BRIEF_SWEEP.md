# Brief pour le balayage d'intuitions — état exact du projet Quoridor (2 août 2026)

Lis ce brief EN ENTIER avant de proposer. Ta proposition doit être concrète,
falsifiable, et testable sur l'outillage existant. Les généralités sont sans
valeur ; les idées déjà réfutées ci-dessous sont éliminatoires.

## Le jeu et l'état de l'art interne

Quoridor W×H×murs : chaque joueur court vers sa rangée but ; un mur (2 cases
de long) est légal ssi APRÈS pose, chacun des deux pions garde un chemin vers
sa propre rangée but (pas la connexité globale). Saut : pion adjacent en face
→ saut par-dessus ; si bloqué derrière, pas de côté perpendiculaire.

Résolu exactement ici : 3×9×10 = 35 plis (certifié, 18 parts, vérification
exhaustive) ; 3×9×9 ≤ 35. Cible ouverte : **4×7×7** (aucun gain forcé ≤ 26
plis ; 38 premiers coups à réfuter au pli 27 ; ~16,3 M de configs de murs
légales). Machine : PC 12 cœurs, 16 Go RAM, C++/Node/Python.

## Architecture des solveurs (2 indépendants, verdicts identiques au nœud)

- A (« chat ») : énumération globale des configs de murs + TT partagée.
- B (qsolve) : construction paresseuse + porte union-find sur le treillis des
  jonctions (un mur ne peut couper que s'il ferme un cycle), distances par
  BFS memoïsées par config (dist_configs ~600 k par branche 3×9).
- Prédicat borné Win(s,T,d) avec parité (gains J1 impairs) ; réfutations
  = recherche bornée sans gain.

## GOULOTS MESURÉS (c'est ça qu'il faut attaquer)

1. **L'ordering des coups domine tout** : inversions d'horizon mesurées
   (une classe 3×9 passe de 129 M à 582 M de nœuds selon la chaleur de la
   TT). Sur 4×7, les bras de portefeuille de sol gagnent/perdent 3-7 %.
2. BFS de légalité : ~2,3 appels par nœud (1,33 G sur une branche 3×9).
3. TT par classe ~3,5× plus de nœuds que TT partagée (prix du parallèle).
4. La borne inférieure (réfutations) coûte autant que la borne sup.

## NÉGATIFS DÉJÀ AUDITÉS (proposer ça = rejet immédiat)

- Spectral / λ₂ du Laplacien : teste la mauvaise propriété (connexité
  globale vs chemin de CHAQUE pion vers SA rangée) — rejeté.
- Somme disjonctive CGT naïve : tours/stocks/course restent couplés à
  travers la séparation géométrique — rejeté.
- DF-PN avec PN/DN naïfs : thrashing, battu par DFS — négatif archivé.
- Porte topologique cache-first (K=0/2/4/all) : négatif audité en temps.
- Oracle exact à stocks nuls dans la recherche bornée : régime trop rare
  (0,005 % des nœuds à profondeur 24 sur 4×7) — négatif archivé par sol.
- Fragilité par coût de détour dans l'éval : −108 Elo au temps réel.
- ZDD pour la légalité en bloc : jugé priorité basse (ni intersection ni
  successeurs O(1) réels).

## POSITIFS ÉTABLIS (à exploiter, pas à redécouvrir)

- Porte union-find : un mur ne coupe que s'il ferme un cycle du treillis
  (contacts en T = deux demi-segments).
- Dichotomie de course exacte (RACE_ZUGZWANG.md) : sans murs, à distances
  égales, le trait perd ssi alignement face-à-face à écart pair (H impair),
  en exactement 2d plis ; zéro nulle. Vérifiée sur 24 plateaux.
- Dominance de Pareto sur les stocks ; borne ⌈d0/2⌉.
- 287,8 M d'états EXACTEMENT étiquetés (coup optimal + rang) décodables
  (memostats.mjs) — dataset d'imitation parfait, unique au monde.
- Théorème du pat (H ≥ 3) ; symétrie miroir (18 orbites sur 35 réponses).

## Ce qu'on attend de toi

1 à 2 propositions MAX, chacune avec : (a) l'idée en 5 lignes, ancrée dans
ton domaine ; (b) pourquoi elle attaque un goulot MESURÉ ci-dessus ;
(c) un protocole de test bon marché sur l'outillage existant (qsolve
--mode selftest/branch, race_param.mjs, mémos, arène arena.js) avec
critère de succès chiffré ; (d) le risque principal et comment le test le
tranche. Pense « réduction de nœuds sur 4×7×7 » ou « certificat moins
cher » ou « Elo 9×9 » — pas « élégance ».
