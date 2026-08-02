# Le zugzwang de la course : cases correspondantes du Quoridor sans murs

Résultat du balayage exact `racesweep.mjs` sur la table de course `race.js`
(9×9, zéro mur, valeurs exactes par point fixe), 2 août 2026. Conventions
moteur : rangée 0 en bas, J0 vise la rangée 8, J1 la rangée 0 ; d = distance
de rangées à l'arrivée ; « gap » = écart de rangées entre les pions.

## Faits exacts (10 242 états, table point-fixe)

1. **Aucune nulle.** Chaque état de course est décisif (5 760 gains du
   trait, 4 482 pertes, 0 nulle). La course nue n'a pas de forteresse.
2. **Zugzwang mutuel ⇔ symétrie centrale.** Les paires (p0, p1) où le trait
   perd *des deux côtés* sont exactement les 36 états à symétrie centrale :
   p1 = (8 − r0, c0), r0 ∈ {0, 1, 2, 3} — mêmes colonnes, distances égales
   d = 8 − r0 ∈ {5, 6, 7, 8}, gap pair ≥ 2. Les 9 colonnes valent, bords
   compris. La position initiale (r0 = 0, c = 4) en est le cas d = 8.
3. **Perte en exactement 2d plis.** v = −2d sur toute la famille
   (−10, −12, −14, −16 pour d = 5, 6, 7, 8). La défense optimale ne
   gagne RIEN à tergiverser : les pas de côté ne rallongent pas la défaite
   (l'adversaire cesse d'imiter et convertit son tempo), donc les deux
   pions courent droit et le perdant perd sur la longueur exacte de la
   course.
4. **À distances égales, colonnes distinctes : le trait ne perd jamais**
   (0 perte sur toutes les classes d = 1..8, |Δcol| = 1..8). L'alignement
   de colonne est *nécessaire* au zugzwang.

## Esquisse de preuve (stratégie d'imitation au saut volé)

Le second joueur (celui qui ne bouge pas) maintient la symétrie centrale en
répondant au coup m par son image centrale σ(m), σ(r, c) = (8 − r, c).

- *Légalité de l'imitation* : sans murs, σ est un automorphisme du graphe
  des coups qui échange les deux camps ; tant que les pions ne sont pas
  adjacents, σ(m) est légal dès que m l'est (les interactions de saut sont
  les seuls couplages, et elles n'apparaissent qu'au contact).
- *Le contact* : gap pair ⇒ le face-à-face adjacent (gap 1) n'arrive
  jamais AVANT un état gap 2 au trait du perdant. Depuis gap 2 aligné,
  avancer offre le saut : l'adversaire franchit le pion et convertit deux
  rangées en un pli — il mène alors la course d'un tempo entier et gagne
  au décompte. S'écarter (pas de côté) rend la course sans interaction
  avec un tempo de retard : perdu aussi, et plus vite que 2d n'échoit.
- *Terminaison* : l'imitation ne peut durer indéfiniment (le perdant doit
  avancer ou épuiser les colonnes, et chaque pas de côté du perdant est
  puni par conversion immédiate du tempo, point 3).

**Preuve complète : `RACE_ZUGZWANG_PROOF.md`** (rédigée le 3 août —
lemmes de parité de contact, coureur glouton, interception ; auditée
adversarialement, 10 attaques A1-A10, 3 trous mineurs percés puis
réparés, trace d'audit conservée dans le fichier).

## Théorème de dichotomie (vérifié sur 24 plateaux, `race_param.mjs`)

La conjecture de parité est CONFIRMÉE par balayage exact sur W ∈ {2, 3, 5, 9}
× H ∈ {4..9} (table paramétrique auto-contrôlée contre race.js sur 9×9 :
10 242 états, 0 divergence). Énoncé complet, à distances égales d :

> **Sans murs, à distances égales, le trait perd si et seulement si les
> pions sont alignés en colonne, face à face, avec un écart PAIR** (cas
> possible seulement si H est impair — la position est alors à symétrie
> centrale) ; **la perte prend exactement 2d plis. Dans tous les autres
> cas le trait gagne** : alignés à écart impair (H pair — le saut au
> contact sert le trait), colonnes distinctes, ou pions croisés.

Et sur chaque plateau balayé : **zéro nulle** (5 760/4 482/0 sur 9×9, même
décisivité partout). La largeur est totalement indifférente — W = 2, où les
pas de côté sont à l'étroit, obéit à la même loi.

C'est le pendant exact du « avec murs, le trait gagne 24/24 » mesuré en
arène : la parité de la course s'inverse selon que le saut est à prendre
ou à subir.

## Conséquences pratiques

- **Oracle O(1) partiel** : sur la famille caractérisée (et ses voisines à
  un pli), la valeur exacte est une formule — utile aux feuilles de
  recherche avant même la table.
- **Ordering fin de partie** : à stocks épuisés et distances égales,
  l'alignement de colonne est un signal exact de zugzwang — le coup qui
  ALIGNE en passant le trait à l'adversaire est gagnant, celui qui aligne
  en gardant le trait est perdant.
- Pour le sélecteur de politiques de sol : le trait exact « parité de
  course × alignement » coûte 3 comparaisons.

Vérification reproductible : `node racesweep.mjs` (sortie intégrale dans
ce commit ; table indépendamment validée contre l'alpha-bêta, 25/25 en
session précédente).
