# Expérience : les coups optimaux exacts sont-ils apprenables ?

Nuit du 2 au 3 août 2026. Verrou de l'idée « ordering appris » (IDEES.md §2,
jugée « plausible » par sol, écho du point 3 de Gemini). Première sonde de
faisabilité sur le dataset unique au monde issu des mémos certifiés 3×9×10.

## Protocole

- **Données** : `sample_dataset.mjs` — réservoir déterministe (LCG) de
  300 000 états J1 par classe × 18 classes = 5,4 M d'états, chacun étiqueté
  par LE coup optimal exact (celui de la stratégie certifiée, invariant
  min-rem) + le rang. Décodage BigInt strict (clés 2^54). Recoupement :
  `j1_total` de H10 = 6 465 147 = le j1 de qexport, au state près.
- **Découpe** : 16 classes à l'entraînement (10 % réservés en validation),
  2 classes ENTIÈREMENT tenues à l'écart (H30, V40) pour mesurer le
  transfert vers des branches jamais vues.
- **Traits v1 (108)** : one-hot p0/p1 (27+27), stocks (11+11), bits de murs
  (16+16). AUCUN trait calculé — le strict contenu de l'état.
- **Modèles** : softmax linéaire ; MLP 1 couche cachée (numpy pur, Adam,
  4-6 époques, ~10 min CPU). Base de référence : coup majoritaire par p0.
- Métriques : top-1/top-3 globaux, par famille (pions/murs), top-3 parmi
  les états dont le coup optimal est un mur, décision binaire pion-vs-mur.

## Résultats v1 (traits bruts)

| modèle | top-1 val | top-3 val | top-1 HOLDOUT | murs top-1 | murs top-3 |
|---|---|---|---|---|---|
| majoritaire-par-p0 | 0,677 | — | 0,667 | — | — |
| softmax 108 | 0,807 | 0,918 | 0,806 | 0,046 | 0,499 |
| MLP 108-256 | 0,877 | 0,972 | **0,878** | 0,185 | 0,800 |
| MLP 108-512, murs ×4 | 0,826 | 0,973 | 0,820 | **0,452** | **0,858** |

## Lectures

1. **Le transfert est parfait.** Sur les deux classes jamais vues, AUCUNE
   dégradation (0,878 vs 0,877 ; idem top-3). La politique optimale a une
   structure partagée entre les 18 branches — le modèle n'apprend pas des
   classes, il apprend le jeu. C'est LA condition pour qu'un ordering appris
   sur 3×9 ait une chance de guider 4×7 (à re-tester, géométrie différente).
2. **Les pions sont triviaux, les murs sont le signal.** 98 % pion (le
   modèle sait courir), mais le choix du mur optimal est difficile depuis
   les traits bruts. Pondérer les murs ×4 fait passer les murs de 18,5 %
   à 45 % top-1 (86 % top-3) en sacrifiant 10 pts de pions — pour de
   l'ordering c'est le bon échange : quand un mur est le coup, le bon mur
   est dans le top-3 à 86 %.
3. **Un coût dérisoire** : ces chiffres sortent d'un MLP à ~90 k paramètres
   entraîné 10 minutes en numpy sur CPU. L'inférence est de l'ordre de la
   dizaine de µs/état (une couche 180×512) — compatible avec un usage
   d'ordering aux nœuds de mur candidats, PAS aux feuilles.

## Limites honnêtes (avant toute promotion)

- **Distribution on-policy** : les états des mémos sont ceux de la stratégie
  optimale certifiée ; la recherche bornée visite majoritairement des états
  HORS de cette distribution. La fidélité mesurée ici est nécessaire mais
  pas suffisante — le vrai test est le regret à profondeur pleine dans
  qsolve (cf. l'inversion d'horizon documentée : un ordering localement
  meilleur peut coûter des nœuds globalement).
- Un seul coup optimal par état est étiqueté (celui de la CertMap) ; un
  coup prédit « faux » peut être un autre coup optimal équivalent. Les
  chiffres sont donc des BORNES INFÉRIEURES de la vraie fidélité.
- 3×9 seulement ; la généralisation inter-plateaux (3×9 → 4×7) est une
  question ouverte, prometteuse vu le point 1 mais non testée.

## Résultats v2 (traits de chemin BFS, 180 traits)

`augment_dataset.mjs` : + distances d0/d1 one-hot, directions de progrès,
32 bits « ancre adjacente au chemin optimal de J2 ». Auto-test : rem ≥
2·d0 − 3 vérifié sur 5,4 M d'états, zéro violation.

| modèle | top-1 val | top-3 val | murs top-1 | murs top-3 (holdout) |
|---|---|---|---|---|
| softmax 180 | 0,855 | 0,949 | 0,060 | 0,637 |
| MLP 180-512, murs ×4 | 0,835 | 0,977 | 0,457 | **0,870** |

**Lecture v2 — hypothèse réfutée à moitié** : les traits de chemin
transforment le modèle LINÉAIRE (+4,8 pts top-1 : l'information de chemin
est bien le signal manquant à ce niveau) mais n'apportent que ~1 pt au
MLP : le réseau extrayait déjà cette information implicitement des traits
bruts. Le plafond « bon mur dans le top-3 : ~86-87 % » est robuste aux
traits ; le reliquat est vraisemblablement (a) du bruit d'étiquette (un
seul coup optimal étiqueté parmi plusieurs équivalents — les chiffres sont
des bornes inférieures), (b) de la tactique nécessitant de la recherche.

## Conclusion et prochaine étape UNIQUE

La faisabilité est établie : un modèle à ~100 k paramètres, entraînable en
10 min CPU, met le coup optimal dans son top-3 à 97-98 % (86-87 % sur les
murs) et TRANSFÈRE PARFAITEMENT aux branches jamais vues. Itérer davantage
sur les traits/architectures serait de la sur-optimisation hors-cible : le
seul chiffre qui compte désormais est le **regret à profondeur pleine dans
qsolve** (nœuds avec/sans ordering appris sur une branche 3×9 de
référence, puis 4×7 si gain). C'est un chantier d'intégration C++
(inférence 180×512 en int8, ~µs), pas de modélisation. À décider avec sol
(l'ordering 4×7 est dans son périmètre solveur ; le modèle et le dataset
sont dans le mien — livraison possible : poids + spec d'inférence, comme
pour qcert).
