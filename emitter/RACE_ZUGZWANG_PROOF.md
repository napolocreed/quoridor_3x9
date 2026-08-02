# Théorème de dichotomie de la course au Quoridor sans murs — preuve formelle

Grille W×H, W ≥ 2, H ≥ 4, deux pions, zéro mur. Ce document prouve les
énoncés (a), (b), (c) de `RACE_ZUGZWANG.md`, avec la sémantique de coups
EXACTE de `race_param.mjs` (fonction `moves()`). Les balayages exacts sur
24 plateaux servent de garde-fou, pas d'argument.

## 1. Définitions

**Cases et joueurs.** Une case est un couple (r, c), 0 ≤ r < H, 0 ≤ c < W.
Deux cases sont *adjacentes* si leur distance de Manhattan vaut 1. J0
occupe p0 = (r0, c0) et vise la rangée H−1 (« monte ») ; J1 occupe
p1 = (r1, c1) et vise la rangée 0 (« descend »). Les pions n'occupent
jamais la même case. Une *position* est (p0, p1, t) avec t ∈ {0, 1} le
trait. J_t doit jouer (pas de passe). J_t gagne dès que son pion ARRIVE
sur sa rangée but (test après le coup, cf. `goal(t, z)` appliqué à la
case d'arrivée) ; la partie s'arrête alors.

**Coups (sémantique exacte de `moves(me, opp)`).** Soit X au trait en
case m, l'adversaire en case o. Pour chaque voisin s de m :

- si s ≠ o : *pas ordinaire* vers s ;
- si s = o : soit δ = s − m la direction du contact et b = s + δ la case
  « derrière » l'adversaire dans cette direction.
  - si b est dans la grille (i.e. b est voisin de s dans la direction δ) :
    l'unique coup à travers o est le *saut droit* vers b ;
  - sinon : les coups à travers o sont les *pas de côté* : tout voisin z
    de o dans la grille avec z ≠ m et z pas dans la direction δ depuis o.
    (Comme b est hors grille, la contrainte active est z ≠ m.)

Remarques immédiates, lues sur le code : (i) `b` hors grille en vertical
signifie que o est sur la rangée 0 ou H−1 ; en horizontal, que o est sur
la colonne 0 ou W−1 (l'expression `s + d` ne « déborde » jamais sur la
rangée voisine grâce au test `neigh(step).includes(behind)`). (ii) Les
pas de côté d'un contact vertical mènent en (ligne de o, c o ± 1) ; ceux
d'un contact horizontal en (r o ± 1, colonne de o). (iii) W ≥ 2 et
H ≥ 4 garantissent qu'un joueur au trait a toujours au moins un coup
(le pion a ≥ 2 voisins, au plus un est bloqué-avec-issues).

**Distances et vocabulaire.** d0 = H−1−r0, d1 = r1 (distances de rangées
au but). *Avancer* = jouer un coup qui diminue sa distance. Le *gap* est
g = r1 − r0. La paire est *face à face* si c0 = c1 et g ≥ 1 (chaque pion
est entre l'autre et son but) ; *croisée* si g ≤ 0 (pour c0 = c1, g = 0
est impossible). *Alignés* = c0 = c1.

**Plis.** Les coups sont numérotés 1, 2, 3, … (plis). Si X a le trait
dans la position de référence, son n-ième coup propre est le pli 2n−1 ;
celui de son adversaire, le pli 2n. Une partie « dure k plis » si le
k-ième coup est le coup gagnant.

## 2. Géométrie élémentaire des coups

**Lemme 1 (déplacement par coup).** Pour le joueur qui joue, en notant
δr le déplacement signé de SA ligne vers SON but et δc celui de colonne :

1. pas ordinaire : |δr| + |δc| = 1 ;
2. saut droit vertical : δr = ±2, δc = 0 (le +2 exige l'adversaire
   adjacent dans la direction du but, même colonne, case derrière dans
   la grille) ; saut droit horizontal : δr = 0, |δc| = 2 ;
3. pas de côté d'un contact vertical : |δr| = 1, |δc| = 1 (diagonal) ;
   d'un contact horizontal : |δr| = 1, |δc| = 1 également (on part de
   (r, c'±… ) vers (r±1, colonne de o)). Dans tous les cas |δr| ≤ 1.

Donc : **le seul coup qui gagne 2 rangées est le saut droit vertical
vers son but** (« saut avant »). Aucun coup ne gagne plus d'une rangée
autrement. *Preuve : lecture directe de la définition des coups.* ∎

**Lemme 2 (parité de contact).** Posons p = (r0 + c0 + r1 + c1) mod 2.

1. Les pions sont adjacents ⇒ p = 1 (Manhattan 1 est impair ; la
   réciproque est fausse — p = 1 signifie seulement distance de
   Manhattan impaire — et n'est utilisée nulle part).
2. Un pas ordinaire inverse p (déplacement Manhattan 1) ; tout coup à
   travers l'adversaire (saut ou pas de côté) préserve p (déplacement
   Manhattan 2, cf. Lemme 1).
3. Par conséquent, tant qu'aucun coup à travers l'adversaire n'a été
   joué, p après k plis vaut p_init + k (mod 2) ; l'ensemble des plis où
   une adjacence peut exister au trait d'un joueur donné est donc figé
   par p_init : si p_init = 0 avec X au trait, toute adjacence au moment
   de jouer survient au trait de l'ADVERSAIRE de X ; si p_init = 1, au
   trait de X. (Après un coup de contact, la parité des rôles se décale
   d'un cran ; les preuves traiteront ce cas localement.)

*Preuve : (1) et (2) sont immédiats ; (3) : au trait de X on est après un
nombre pair de plis depuis la référence, donc p y vaut p_init ; une
adjacence exige p = 1.* ∎

**Corollaire 2.1 (qui peut être bloqué / sauter).** Sauter ou faire un
pas de côté exige l'adjacence À SON TRAIT ; être « bloqué » (case devant
occupée) aussi. Donc dans une phase sans coups de contact, un seul des
deux joueurs — déterminé par p_init et le trait — peut être bloqué ou
bénéficier d'un saut ; l'autre avance sans jamais rencontrer l'adversaire
sur sa case cible. On appellera *joueur de contact* celui qui peut
rencontrer l'adjacence à son trait, et *coureur* l'autre.

## 3. Le coureur glouton et le budget de coups

**Définition (coureur glouton).** À partir d'un état de référence, X joue
*glouton* dans sa colonne γ : à chaque trait, (i) si la case devant (une
rangée vers son but, colonne γ) est libre, il y avance ; (ii) si elle est
occupée par l'adversaire et que la case derrière est dans la grille, il
saute droit (gain de 2 rangées) ; (iii) sinon — la case derrière est hors
grille, donc l'adversaire est SUR la rangée but de X — il fait un pas de
côté vers (rangée but, γ ± 1) : une telle case existe (W ≥ 2), est libre
(l'unique autre pion est celui qu'on contourne), et c'est la rangée but :
X gagne sur ce coup.

**Lemme 3 (le glouton n'est jamais retardé).** Un coureur glouton de
distance initiale d gagne en au plus d coups propres, exactement d si le
cas (ii) ne se produit jamais ; chacun de ses coups diminue sa distance
d'au moins 1 ; il ne quitte jamais la colonne γ sauf par le pas de côté
final gagnant du cas (iii). *Preuve : chaque branche de la définition
diminue la distance de 1 ou 2 et est toujours légale (énumération
ci-dessus) ; il n'a jamais d'autre interaction, car toute interaction
exigerait l'adjacence à son trait, et les trois branches la traitent.* ∎

**Lemme 4 (budget de coups propres).** Dans toute partie, si un joueur X
de distance initiale d gagne en N coups propres dont j sauts avant, alors

1. N ≥ d − j (Lemme 1 : somme des δr = d, chaque coup apporte ≤ 1 sauf
   les sauts avant qui apportent 2 ; les sauts ARRIÈRE, δr = −2,
   n'apportent que du négatif et ne peuvent qu'augmenter N) ;
2. si l'adversaire est un COUREUR GLOUTON (Lemme 3), alors j ≤ 1 :
   après le premier saut avant de X, plus aucun saut de X (avant OU
   arrière) n'est jamais légal ;
3. donc, face à un coureur glouton, N ≥ d − 1, avec égalité seulement si
   j = 1 et si TOUS les autres coups de X sont des avancées strictes
   (δr = +1 vers son but — ce qui exclut en particulier tout saut
   arrière, δr = −2).

*Preuve de (2) (invariant q ≥ 2).* Soit q = (rangée de X) − (rangée de
l'adversaire), comptée positivement dans la direction du but de X. Au
trait de X : un saut AVANT exige q = −1 (adversaire juste devant, même
colonne) ; un saut ARRIÈRE exige q = +1 (adversaire juste derrière). Le
saut avant fait passer q de −1 à +1. C'est alors le trait du glouton R,
dont chaque coup avance vers SON propre but, c'est-à-dire s'écarte de X :
δq = +1 (Lemme 3 : R n'a que des coups qui diminuent SA distance, tous
avec δq = +1 relativement à X). Donc au trait suivant de X, q ≥ 2.
Ensuite, invariant : tout coup de X vérifie δq ≥ −1 (Lemme 1 : |δr| ≤ 1
hors sauts, et un saut exigerait q ∈ {−1, +1}, faux sous l'invariant),
et tout coup de R vérifie δq = +1 ; par récurrence sur les rondes,
**q ≥ 2 à chaque trait de X après son premier saut avant**. Or tout saut
(avant ou arrière) exige |q| = 1 au trait de X : aucun second saut
n'est jamais légal. j ≤ 1. ∎

> Portée : (2) et donc (3) sont établis **face à un coureur glouton** ;
> c'est le seul contexte où on les utilise. (1) est inconditionnel.
> (Sans l'hypothèse gloutonne, une comptabilité brute donnerait
> N ≥ d + 2j − 3, insuffisante et inutilisée ici.)

**Lemme 5 (interception d'un coureur glouton).** Soit R un coureur
glouton (colonne γ, distance dR) à partir d'un état de référence, et C
l'autre joueur (colonne initiale cC, distance dC). Alors le nombre de
coups propres de C pour gagner vérifie N ≥ dC − 1, et N = dC − 1 est
possible seulement si, dans l'état de référence :

- cC = γ (alignés), R est entre C et le but de C (face à face), et
- le gap |q| initial a la parité qui place l'adjacence au trait de C :
  impair si C a le trait dans l'état de référence, pair sinon ;

et alors l'unique trajectoire à dC − 1 coups est : avancées strictes dans
la colonne γ jusqu'au contact, puis saut avant, puis avancées strictes.

*Preuve.* Par le Lemme 4(3) (valide face au glouton), N = dC − 1 exige
j = 1 et tous les autres coups en δr = +1. Les coups à δr = +1 sont : le
pas ordinaire d'avancée (colonne fixe) et le pas de côté « diagonal
avançant ». Examinons les diagonales possibles ; tout pas de côté exige
le contact avec R, qui reste en colonne γ (Lemme 3) :

- *Contact latéral* (C en (ρ, γ±1), R en (ρ, γ)) : le saut droit
  horizontal existe sauf si γ est une colonne de bord ; les pas de côté,
  quand ils existent, mènent en (ρ±1, γ). La variante avançante mène C
  en colonne γ, une rangée PLUS PRÈS de son but que R : C a alors
  DÉPASSÉ R (R est derrière lui et s'éloigne, puisque R avance vers le
  but opposé et que q ne peut plus revenir à −1 : chaque coup des deux
  joueurs donne désormais δq ≥ 0 côté utile). Plus aucun saut avant de C
  n'est possible ensuite — contradiction avec j = 1 encore à réaliser.
  Si le saut C a DÉJÀ eu lieu, C est également passé de l'autre côté de
  R et aucun contact facial ne peut renaître (même argument sur q).
  La variante reculante est un recul (exclue). Le saut horizontal a
  δr = 0 (exclu).
- *Contact vertical avec R sur la rangée but de C* : le pas de côté
  atterrit sur la rangée but = coup GAGNANT à δr = +1 et δc = ±1 ; c'est
  le dernier coup, il ne précède aucun saut ; s'il est le coup n° dC − 1
  d'une trajectoire avec j = 1, le saut a eu lieu avant, dans la colonne
  où C a toujours été. Ce cas ne fait donc pas sortir C de γ avant le
  saut.

Conclusion : avant son saut, C n'a joué que des avancées à colonne
constante, donc cC = γ et le face-à-face initial est nécessaire (le saut
avant exige R devant C). Enfin la parité : dans la phase d'avancées
mutuelles, tous les coups sont ordinaires ; par le Lemme 2(3),
l'adjacence au trait de C exige que |q| initial soit impair si C a le
trait (l'adjacence survient après un nombre pair de plis) et pair sinon.
Réciproquement, il faut aussi que R n'atteigne PAS l'adjacence à SON
trait avant (sinon R saute par-dessus C, les pions se croisent et le saut
de C devient impossible) : les deux avancent d'une rangée par pli, le gap
diminue de 1 par pli, et le premier à voir gap 1 à son trait est
déterminé par la même parité — c'est C exactement dans les cas énoncés. ∎

**Fait 6 (décompte des plis).** Si X gagne à son n-ième coup propre, la
partie dure 2n − 1 plis si X avait le trait dans l'état de référence,
2n plis sinon. Deux joueurs ne finissent jamais au même pli. ∎

## 4. Lemme du tempo

**Lemme 7 (course sans interaction utile).** Soit M au trait (distance
dm), O l'adversaire (distance do).

1. Si dm ≤ do − 1, M gagne : M joue glouton, gagne au plus tard au pli
   2dm − 1 (Lemme 3, Fait 6) ; O, même avec un saut avant, totalise
   ≥ do − 1 ≥ dm coups propres (Lemme 5 face au glouton M), donc finirait
   au plus tôt au pli 2dm > 2dm − 1.
2. Si dm = do = d et que O ne peut pas réaliser N = d − 1 (conditions du
   Lemme 5 non réunies), M gagne : glouton, pli 2d − 1, contre ≥ 2d.
3. Symétriquement, si do ≤ dm − 2, O gagne : O joue glouton dès son
   premier coup (pli 2), gagne au pli ≤ 2do ; M totalise ≥ dm − 1 ≥
   do + 1 coups, pli ≥ 2do + 1.

∎ (Les décomptes utilisent que le glouton n'est jamais retardé, et que
toute tentative de saut de l'autre camp est bornée par le Lemme 5.)

## 5. Cas (b) : alignés, face à face, gap pair — le trait perd en 2d plis

Position B : distances égales d0 = d1 = d, c0 = c1 = c, face à face,
g = r1 − r0 pair. Comme d0 = d1 force r1 = H−1−r0, on a g = H−1−2r0 :
g pair ⇔ **H impair**, et la position est à symétrie centrale
σ(r, x) = (H−1−r, x) : p1 = σ(p0). Face à face avec g pair donne g ≥ 2,
donc r0 < (H−1)/2 =: μ (rangée médiane, H impair). Ici p_init =
r0 + r1 = H−1 pair : par le Corollaire 2.1, **J1 (le non-trait) est le
joueur de contact, J0 le coureur** tant qu'aucun contact n'a eu lieu.
Sans perte de généralité J0 a le trait (σ échange les rôles).

### 5.1 Stratégie de J1 (miroir + conversion) et borne supérieure ≤ 2d

Stratégie τ de J1 :

- **(M)** tant que la position à son trait est « symétrique + J0 vient
  d'avancer » : si J0 vient de jouer (r, c) → (r+1, c) avec r+1 < μ,
  répondre le miroir σ : (H−1−r, c) → (H−2−r, c) ; si r+1 = μ (J0 vient
  d'entrer sur la rangée médiane depuis le gap 2), **sauter** : J1 est en
  (μ+1, c), J0 en (μ, c), la case derrière (μ−1, c) est dans la grille
  (μ ≥ 2 car H ≥ 5) et libre : saut avant vers (μ−1, c) ;
- **(C)** au premier coup de J0 qui n'est pas une avancée (pas de côté ou
  recul), *convertir* : avancer glouton dans la colonne c jusqu'au gain,
  en ignorant J0.

*Légalité du miroir.* Après le coup ordinaire de J0 (aucun contact n'a
encore eu lieu en phase (M) : à son trait p = 0, pas d'adjacence, donc
tous ses coups sont ordinaires), la cible σ-miroir est adjacente à la
case de J1 (σ est un automorphisme du graphe-grille) ; elle n'est ni la
case de J0 (σ(x) = x exigerait x sur la rangée μ, cas traité par le
saut) ni sa propre case. Le coup miroir est un pas ordinaire (les pions
sont à gap ≥ 3 avant lui… en fait ≥ 2 : la cible n'est jamais adjacente
au moment critique car le cas gap 2 → adjacence est précisément le cas
du saut). Après lui, la position est de nouveau symétrique, gap pair,
J0 au trait : l'invariant est maintenu.

*Décomptes.*

- **Ligne « J0 avance toujours ».** Après k rondes miroir la position est
  symétrique de distances d−k. Au gap 2 (k = d − (H+1)/2… peu importe
  k : notons simplement le moment), J0 avance sur (μ, c) au pli 2k+1,
  J1 saute au pli 2k+2 vers (μ−1, c) : J1 a alors distance μ−1 et a joué
  k+1 coups ; il lui reste μ−1 avancées, toutes libres : après le saut,
  J1 est PASSÉ sous J0, J0 monte, J1 descend, plus aucun contact facial
  (l'argument q du Lemme 4 : q ne revient jamais à −1) ; J1 gagne au pli
  2(k + 1 + μ − 1) = 2(k + μ). Avec d = k + μ + … vérifions : au moment
  du saut r0 = μ−1 + … plus simplement, J1 totalise 1 saut et d−2
  avancées = d−1 coups propres, donc gagne au pli 2(d−1) = **2d − 2**.
  J0, jamais retardé, aurait fini au pli 2d − 1 : trop tard. J0 perd.
- **Ligne « J0 dévie à la ronde k » (pas de côté ou recul, pli 2k+1).**
  J1 convertit : il avance en (H−2−r, c) — case libre : J0 est en rangée
  r (pas de côté) ou r−1 (recul) avec H−2−r − r = g_k − 1 ≥ 1 où g_k ≥ 2
  est le gap courant, donc rangées distinctes ; colonnes : si pas de
  côté, colonnes distinctes aussi. Puis J1 joue glouton (colonne c).
  Distances au pli 2k+2 : J1 : d−k−1 ; J0 : d−k (pas de côté) ou d−k+1
  (recul). J1 gagne au pli 2k+2 + 2(d−k−1) − … : ses d−k−1 avancées
  restantes occupent les plis 2k+4, …, 2k+2+2(d−k−1) = **2d**, sauf
  accélération (si J0 vient se mettre devant lui, J1 saute ou fait le
  pas de côté but : plus tôt encore ; cf. Lemme 3). J0, lui : (i) après
  un pas de côté, ses colonnes diffèrent de celle du glouton J1 ; par le
  Lemme 5 son budget est ≥ d0_courant = d−k, plus le coup déjà gaspillé :
  total ≥ d+1, pli ≥ 2(d+1)−1 = 2d+1 > 2d ; (ii) après un recul, il est
  aligné face à J1 avec gap impair et LE TRAIT : le Lemme 5 l'autorise à
  un budget d+1−1 = d (recul compté, saut possible), pli ≥ 2d−1… mais le
  décompte fin donne : distance d−k+1, budget ≥ (d−k+1) − 1 = d−k coups
  À PARTIR du pli 2k+3, soit un gain au plus tôt au pli 2k+1+2(d−k) =
  **2d+1** > 2d. Dans les deux cas J1 gagne d'abord, au pli ≤ 2d.

Toute stratégie de J0 est l'une de ces lignes (à chaque trait il avance
ou dévie), donc **J1 gagne en au plus 2d plis contre toute défense**, et
en 2d−2 exactement si J0 ne dévie jamais.

### 5.2 Borne inférieure : la défense atteint exactement 2d plis

Défense de J0 : au pli 1, pas de côté (r0, c) → (r0, c′), c′ = c ± 1
dans la grille (W ≥ 2 ; case libre car g ≥ 2) ; ensuite, glouton dans la
colonne c′. À partir du pli 2, J0 est un coureur glouton de colonne
c′ ≠ c. Par le Lemme 5 (appliqué à l'état après le pli 1), J1 ne peut
pas économiser de coup : colonnes distinctes ⇒ budget ≥ d, gain au pli
≥ 2d. Donc la valeur est **exactement −2d** : J1 gagne, en 2d plis
précisément, et les pas de côté supplémentaires de J0 ne rallongent rien
(chaque déviation après conversion laisse l'horloge de J1 inchangée,
Lemme 3). ∎ (b)

## 6. Cas (c) : tous les autres cas à distances égales — le trait gagne

Distances égales d, M = le trait, O = l'autre. Stratégie de M : glouton
dans sa colonne. Par le Lemme 3, M gagne au pli 2d − 1 sauf si O gagne
avant, ce qui exige (Fait 6) un budget O ≤ d − 1 : par le Lemme 5, ce
n'est possible que si, dès la position initiale, les pions sont ALIGNÉS,
FACE À FACE, et le gap a la parité « adjacence au trait de O », c'est-à-
dire PAIRE (O n'a pas le trait). C'est exactement le cas (b), exclu ici.
Détail des trois sous-cas :

- **(c1) colonnes distinctes.** Lemme 5 : budget de O ≥ d ⇒ pli ≥ 2d.
  M gagne au pli 2d − 1. (La largeur ne joue aucun rôle : la preuve du
  Lemme 5 montre que les entrées « gratuites » dans la colonne de M —
  diagonales de bord — croisent les pions ou reculent, et ne créent
  jamais de saut.)
- **(c2) alignés croisés (g ≤ 0, donc g ≤ −1).** Le face-à-face fait
  défaut : le saut avant de O exigerait M entre O et la rangée 0, i.e.
  r0 < r1, faux initialement ; et q = r1 − r0 ≤ −1 ne peut atteindre +1
  face au glouton M (tous les coups de M donnent δ(r0) = +1… par le
  Lemme 3, et O ne gagne q qu'en reculant, ce qui coûte plus qu'un saut
  ne rapporte, Lemme 4). Budget O ≥ d ⇒ M gagne. Idem colonnes
  distinctes croisées (couvert par (c1)).
- **(c3) alignés face à face, gap IMPAIR (H pair).** Ici p_init =
  g mod 2 = 1 : par le Corollaire 2.1, c'est M, le trait, qui est le
  joueur de contact. O ne peut jamais sauter ni bloquer utilement
  (budget ≥ d, pli 2d), tandis que le glouton M ne peut être que servi
  par le contact : les deux avancent, gap 1 survient au trait de M, qui
  saute (case derrière libre ; si elle est hors grille, O est sur la
  rangée but de M et le pas de côté de M gagne sur-le-champ). M gagne au
  pli ≤ 2d − 1, et même 2d − 3 si O court droit. Si O dévie pour esquiver
  le contact, chaque déviation ajoute 1 à son budget (≥ d + 1, pli
  ≥ 2d + 2) sans retarder M (Lemme 3) : M gagne au pli 2d − 1. ∎ (c)

## 7. Énoncé (a) : aucune position de course n'est nulle

On donne la carte complète des vainqueurs ; chaque case fournit une
stratégie gagnante à horizon borné pour un des deux joueurs, ce qui
exclut la nulle (et les parties infinies). M = trait (distance dm),
O = l'autre (distance do).

| Situation | Vainqueur | Argument |
|---|---|---|
| dm ≤ do − 1 | M | Lemme 7(1) : glouton, pli 2dm − 1 < 2(do−1) ≤ O |
| dm = do, cas (b) | O | §5, en exactement 2d plis |
| dm = do, sinon | M | §6, pli ≤ 2d − 1 |
| dm = do + 1, alignés face à face gap impair | M | ci-dessous |
| dm = do + 1, sinon | O | ci-dessous |
| dm ≥ do + 2 | O | Lemme 7(3) : glouton, pli 2do ; M ≥ do + 1 coups |

*Cas dm = do + 1.* O mène d'un tempo : glouton, il gagne au pli 2do ; M
doit finir au pli ≤ 2do − 1, i.e. en ≤ do = dm − 1 coups : par le
Lemme 5 (O glouton), possible seulement si alignés, face à face, avec le
gap plaçant l'adjacence au trait de M — gap IMPAIR (M a le trait). Dans
ce cas M joue glouton : si O court droit, M obtient le saut au contact
(gap impair ⇒ gap 1 à son trait) et gagne au pli 2(dm−1) − 1 = 2do − 1 ;
si O dévie ne serait-ce qu'une fois, budget O ≥ do + 1 ⇒ pli ≥ 2do + 2,
tandis que M court en 2dm − 1 = 2do + 1 : M gagne encore. Sinon (pas
alignés-face-à-face-impair), O gagne : il faut exclure N(M) ≤ do, en
réappliquant explicitement le Lemme 5.

- *M sans déviation* (que des coups δr = +1, plus au plus un saut) : le
  Lemme 5, appliqué à l'état initial avec O glouton, n'autorise
  N = dm − 1 = do que dans le cas alignés-face-à-face-gap-impair, exclu
  ici ; donc N ≥ dm = do + 1, pli ≥ 2do + 1 > 2do.
- *M avec au moins une déviation* (premier coup à δr ≤ 0 au pli 2k+1) :
  on réapplique le Lemme 5 à l'état POST-déviation (O y est toujours un
  coureur glouton dans sa colonne, état de référence = après le pli
  2k+1) : le budget restant de M y est ≥ d′M − 1 où d′M ≥ dm est sa
  distance courante (la déviation n'a pas diminué sa distance). Total :
  N ≥ (k + 1) + (d′M − 1) ≥ (coups déjà joués) + dm − 1 ≥ dm = do + 1,
  la déviation elle-même payant le −1 éventuel du saut. Pli
  ≥ 2(do + 1) − 1 = 2do + 1 > 2do.

Dans tous les cas O, glouton et jamais retardé (Lemme 3), gagne au pli
2do. ∎ (a)

Remarque : la table redonne le résultat mesuré « 5 760 gains du trait /
4 482 pertes / 0 nulle » sur 9×9 comme simple recomptage des classes.

## 8. Cas limites

- **W = 2.** Tous les lemmes n'utilisent qu'UN voisin latéral : le pas
  de côté but du glouton (Lemme 3(iii)) et la déviation défensive de
  §5.2 existent dès W ≥ 2. Les diagonales de bord (colonnes 0 et W−1
  partout) sont exactement celles analysées au Lemme 5 : elles croisent
  ou reculent, jamais elles n'offrent de saut — d'où l'indifférence à W
  observée dans le balayage.
- **Pions au bord (colonnes 0/W−1).** Seul effet : le saut droit
  HORIZONTAL peut être remplacé par des pas de côté verticaux (contact
  latéral en colonne de bord). Ces coups ont |δr| = 1 (Lemme 1) : ils ne
  changent aucun budget ; leur seul rôle fin (entrée diagonale dans la
  colonne du coureur) est traité au Lemme 5.
- **Saut vers la rangée but.** `goal` est testé sur la case d'arrivée :
  un saut ou un pas de côté qui ATTERRIT sur la rangée but gagne. Le cas
  « derrière hors grille » en direction du but signifie adversaire SUR
  la rangée but ; le pas de côté atterrit alors lui-même sur la rangée
  but : aucun blocage terminal n'existe (Lemme 3(iii)).
- **Adjacence initiale (gap 1).** Cas (c3) de base : le trait saute (ou
  pas de côté but) immédiatement ; cohérent avec g impair ⇒ gain.
- **Positions croisées.** L'argument q (Lemme 4/5) montre qu'un
  croisement est irréversible face à un glouton : aucun face-à-face ne
  renaît, donc aucun saut ; c'est ce qui clôt (c2) et l'unicité du saut.
- **H pair / H impair.** À distances égales, g = H−1−2r0 : la parité du
  gap est un invariant du plateau, d'où « (b) possible seulement si H
  impair » ; pour H ∈ {4, 6, 8} la famille (b) est vide et le trait
  gagne toute position à distances égales — conforme aux balayages.

## 9. Conclusion

(a), (b), (c) sont démontrés : (b) par miroir + conversion avec bornes
2d exactes (§5), (c) par glouton + Lemme d'interception (§6), (a) par la
carte exhaustive (§7). Les seuls points d'appui non triviaux sont les
Lemmes 4(2) (pénalité des sauts multiples, prouvé face à un glouton — le
seul cas utilisé) et 5 (interception), dont la preuve épuise les coups
diagonaux de bord. Aucun TROU restant identifié ; les faits calculés des
24 plateaux (0 nulle, familles −2d, indifférence à W) coïncident avec
chaque décompte.

## Audit adversarial

Audit indépendant (2026-08-02), sémantique vérifiée ligne à ligne contre
`moves()` de `race_param.mjs` (saut droit ssi `neigh(step).includes(behind)`,
sinon pas de côté = voisins de o sauf `me` et la direction δ). Chaque attaque
est déroulée à la main.

### A1 — Lemme 1 (géométrie des coups) : TIENT
Énumération conforme au code. Vérifié en particulier que le pas de côté
d'un contact horizontal (colonne de bord) a bien |δr| = 1, |δc| = 1, et que
`neigh` empêche tout débordement de colonne (`p % W`). Aucun coup à δr = +2
hors saut avant vertical.

### A2 — Lemme 2(1) : PERCE (cosmétique)
« Adjacents ⇔ p = 1 » est faux dans le sens ⇐ : p = 1 signifie distance de
Manhattan IMPAIRE (1, 3, 5, …), pas nécessairement 1. Seul le sens ⇒
(adjacence ⇒ p = 1) est vrai — et c'est le seul utilisé dans (3), le
Corollaire 2.1 et le Lemme 5. Réparation : remplacer ⇔ par ⇒. Aucune
conséquence en aval.

**RÉPARÉ (2026-08-02)** : Lemme 2(1) reformulé en « ⇒ », avec mention
explicite que la réciproque est fausse et inutilisée.

### A3 — Lemme 3 (glouton) : TIENT
Cas (iii) vérifié contre le code : o sur la rangée but de X, `behind` hors
grille, les pas de côté sont exactement (rangée but, γ ± 1) — la case
`z − step = d` exclue est `behind` (hors grille de toute façon), la case
z = me est le voisin intérieur. Le coup atterrit sur la rangée but et
`goal` est testé sur la case d'arrivée : gain immédiat, y compris en
colonne de bord (W ≥ 2 donne l'autre côté). Le blocage latéral n'empêche
jamais l'avancée frontale. Jamais retardé : confirmé.

### A4 — Lemme 4(2), attaque prioritaire : PERCE (mineur, réparable)
Le décompte omet les coups de X à δr = −2 (saut ARRIÈRE : R adjacent côté
départ de X, case derrière dans la grille). Un tel coup donne δq = −2 en
UN coup ; avec u2 sauts arrière l'algèbre donne N ≥ d + 2j − 3, pas
d + 3j − 4 (pour j = 2 : d + 1, pas d + 2). MAIS le trou ne perce pas la
conclusion : simulation face au glouton — après le premier saut avant de
X (q : −1 → +1), c'est le trait de R, qui s'éloigne (face-à-face : R
descend vers la rangée départ de X… non : R avance vers SON but, donc
s'écarte de X), d'où q = +2 au trait suivant de X ; ensuite chaque recul
de X (−1) est compensé par l'avancée de R (+1) : q ≥ 2 à CHAQUE trait de
X après le premier saut. Donc ni deuxième saut avant (q = −1 requis) ni
saut arrière (q = +1 requis au trait de X) n'est jamais légal face au
glouton : j ≤ 1 toujours, et 4(3) tient trivialement. Réparation
suggérée : remplacer la comptabilité de fenêtres par cet invariant
« q ≥ 2 après le premier saut », plus court et qui couvre δr = −2.

**RÉPARÉ (2026-08-02)** : Lemme 4(2) réécrit — la constante d + 3j − 4
est supprimée ; face au glouton, l'invariant « q ≥ 2 à chaque trait de X
après son premier saut avant » interdit tout second saut (avant comme
arrière, qui exigent |q| = 1), d'où j ≤ 1 et 4(3) inchangé.

### A5 — Lemme 5, épuisement des diagonales, attaque prioritaire : TIENT
Contre-exemple candidat : W = 3, C en (ρ, 1) montant, R glouton en (ρ, 0)
(colonne de bord γ = 0). `behind` = (ρ, −1) hors grille : pas de côté
diagonaux (ρ ± 1, 0) disponibles — c'est le seul contact latéral offrant
un δr = +1 hors colonne (si γ intérieure, seul le saut droit horizontal
existe, δr = 0, exclu : conforme au code). La variante avançante met C en
(ρ+1, 0) : C est alors devant R qui recule relativement à lui à chaque
pli (q passe à +1 puis croît, cf. A4) — le saut avant (q = −1) devient
inatteignable sans reculs, exclus par « tous les autres coups à
δr = +1 ». Si le saut a déjà eu lieu, revenir à q = 0 pour recréer le
contact latéral exigerait δq < 0, même exclusion. Le contact vertical
arrière (R sur la rangée DÉPART de C) ne produit que des diagonales à
δr = −1. L'épuisement est complet. La parité (qui saute le premier au
gap 1) est correcte : gap décroissant de 1 par pli en phase d'avancées
mutuelles, premier gap 1 au trait fixé par la parité initiale.

### A6 — Cas (b), §5.1 : TIENT (décomptes revérifiés)
H impair ⇒ μ = (H−1)/2 ≥ 2 dès H ≥ 5 (H = 5 : saut vers (1, c), dans la
grille) ; le cas (b) exige H impair donc H ≥ 5, cohérent avec H ≥ 4
global. Ligne droite : k = μ−1−r0 rondes miroir, saut au pli 2k+2,
total J1 = k + μ = d − 1 coups, gain au pli 2d−2 < 2d−1 (J0). Déviation
à la ronde k : conversion, J1 gagne au pli 2d ; J0 : pas de côté ⇒
budget ≥ (k+1) + (d−k) = d+1 (Lemme 5, colonnes distinctes), pli
≥ 2d+1 ; recul ⇒ gap impair au trait de J0, le Lemme 5 l'autorise au
saut, mais d−k coups à partir du pli 2k+3 finissent au pli 2d+1 : exact.
Retour de J0 dans la colonne c pour bloquer le glouton J1 : traité par
le Lemme 3 (saut ou pas de côté but, jamais retardé).

### A7 — Cas (b), §5.2, exactitude v = −2d : TIENT
La défense (pas de côté pli 1, W ≥ 2 garantit c′, case libre car g ≥ 2,
puis glouton en c′) force J1 à budget ≥ d (Lemme 5, colonnes distinctes
dans l'état de référence après le pli 1), pli ≥ 2d ; §5.1 donne ≤ 2d
contre TOUTE défense. Valeur = −2d exactement, partie bornée ⇒ pas de
nulle. Cohérent avec la table (−10/−12/−14/−16).

### A8 — §7, ligne dm = do + 1, déviation de M : PERCE (mineur, réparable)
La justification « budget O(=M) ≥ do + 1 ⇒ pli ≥ 2do + 2 » est
sous-argumentée : après UNE déviation (δr = 0), M pourrait viser
j = 1 et N = dm − 1 = do (bilan de rangées A + 2 = dm, N = A + 1 + 1),
soit le pli 2do < 2do + 1 — la phrase du texte ne l'exclut pas
explicitement. L'exclusion est vraie mais demande l'argument A5 : le
glouton O reste dans sa colonne ; pour sauter, M doit y revenir, soit
par un second coup à δr = 0 (N ≥ do + 1), soit par la diagonale de bord
avançante qui le fait PASSER O (q = +1, saut mort, j = 0, N ≥ do + 1) ;
un recul de M laisse la parité d'adjacence au trait de M mais coûte
u ≥ 1 avec j alors ≤ 1 et N ≥ dm = do + 1. Dans tous les cas pli
≥ 2(do+1) = 2do + 2 > 2do + 1 = course droite de M. Réparation : citer
explicitement le Lemme 5 appliqué à l'état POST-déviation, comme le
fait §5.1(i).

**RÉPARÉ (2026-08-02)** : §7, cas dm = do + 1 « sinon », scindé en deux
sous-cas avec réapplication explicite du Lemme 5 : sans déviation (état
initial, conditions d'égalité exclues ⇒ N ≥ dm) et post-déviation (état
de référence après le pli déviant, O toujours glouton, N ≥ (k+1) +
(d′M − 1) ≥ do + 1) ; conclusion pli ≥ 2do + 1 > 2do inchangée.

### A9 — Cas limites : TIENT
- W = 2 : la déviation §5.2 et le pas de côté but existent (une seule
  colonne latérale suffit) ; contact latéral toujours en colonne de
  bord ⇒ diagonales analysées en A5.
- Saut débouchant sur la rangée but : `goal` testé sur la case
  d'arrivée, gain immédiat ; « behind hors grille vers le but » ⇒
  adversaire SUR la rangée but ⇒ pas de côté gagnant : aucun blocage
  terminal.
- Croisés (c2) : q ≤ −1 et tous les coups du glouton M donnent
  δq ≤ 0 côté O ; revenir à q = +1 coûte ≥ 2 reculs à O ⇒ budget > d :
  confirmé par l'invariant de A4.
- Gap 1 initial, H pair/impair, adjacence à distances égales : décomptes
  refaits, conformes (2d−3 pour (c3) course droite).

### A10 — Circularité et terminaison : TIENT
Ordre : L1, L2 → L3 → L4(2) (utilise L3) → L5 (utilise L2, L3, L4(3)) →
L7, §5, §6, §7. Aucun cycle. Toutes les stratégies exhibées sont à
horizon borné explicite (2d, 2d−1, 2do…) : la terminaison et l'absence
de nulle en découlent, cohérent avec « 0 nulle » sur les 24 plateaux.

### Verdict global
**Preuve solide, deux trous mineurs réparables** (A4 : constante de
L4(2) fausse telle qu'écrite, l'invariant q ≥ 2 la remplace ; A8 :
justification elliptique d'une ligne de §7) et une coquille (A2 : ⇔ → ⇒).
Aucun contre-exemple concret ne perce les conclusions (a), (b), (c) ni
l'exactitude v = −2d.
