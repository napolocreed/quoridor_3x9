# qcert-1 : format de certificat de stratégie vérifiable

Objectif : remplacer « notre solveur dit vrai » par un artefact que n'importe
quelle implémentation indépendante peut vérifier **sans refaire la recherche**.
Le solveur émet une stratégie gagnante dédupliquée ; le vérificateur régénère
les coups avec son propre moteur et contrôle des inégalités locales. La borne
globale (p. ex. 35 plis) devient une propriété structurelle du fichier.

## Sémantique certifiée

Le certificat atteste `Win(s0, T, D)` au sens exact de
`docs/PROOF_SEMANTICS.md` : le joueur `T` a une stratégie qui atteint sa
rangée but en au plus `D` actions depuis `s0`, contre toute réponse légale.

## Syntaxe (JSONL)

Une ligne d'en-tête puis une ligne par état certifié, dédupliqué :

```json
{"type":"header","format":"qcert-1","width":W,"height":H,"walls":N,
 "target":T,"bound":D,"root":{"p1":..,"p2":..,"r1":..,"r2":..,"turn":..,"hw":..,"vw":..}}
{"type":"node","p1":..,"p2":..,"r1":..,"r2":..,"turn":..,"hw":..,"vw":..,"d":d,"move":"P:12"}
{"type":"node","p1":..,"p2":..,"r1":..,"r2":..,"turn":..,"hw":..,"vw":..,"d":d}
```

- Champs d'état identiques au format de `frontier_dump` (cases indexées
  `r*W+c`, murs en masques de bits `hw`/`vw` sur les ancres `r*(W-1)+c`).
- `d` : budget certifié — le fichier affirme `Win(état, T, d)`.
- `move` : obligatoire si `turn == T` (le coup de la stratégie, au format
  `P:case`, `H:r:c`, `V:r:c`) ; absent sinon.
- Chaque état apparaît **au plus une fois**. `d` est une fonction de l'état :
  la déduplication entre branches et profondeurs est donc triviale.

## Règles de vérification (aucune recherche)

Le vérificateur construit l'index état → `(d, move)` puis contrôle :

1. **Racine** : `root` est présent dans l'index avec `d ≤ D`.
2. **Nœud à `T` au trait** : `move` est légal selon le moteur du
   vérificateur ; son enfant `c` est soit terminal gagné par `T`, soit
   non terminal, présent dans l'index, avec `d(c) ≤ d − 1`.
3. **Nœud adversaire au trait** : l'ensemble des coups légaux, régénéré par
   le vérificateur, est non vide, et **chaque** enfant est soit terminal
   gagné par `T`, soit non terminal, présent dans l'index, avec
   `d(c) ≤ d − 1`.
4. **Cohérence locale** : tout nœud non terminal a `d ≥ 1` ; aucun nœud
   terminal n'apparaît dans l'index ; les états de l'index sont légaux
   (pions distincts, hors rangée but adverse, stocks dans les bornes,
   conservation `r1 + r2 + murs posés = 2 × dotation`).
5. **Traçabilité de la racine** : le vérificateur signale
   `rootIsInitialPosition` — un certificat de branche est valide, mais le
   consommateur voit explicitement quelle position est certifiée.

## Théorème de correction

*Si le vérificateur accepte, alors `Win(s0, T, D)` est vrai.*

Preuve par récurrence forte sur `d`. Un nœud accepté de budget `d` à `T` au
trait possède un coup vers un enfant gagné immédiatement (base) ou certifié
à `d' ≤ d−1`, donc gagnant en `≤ d−1` par hypothèse de récurrence et
monotonie de `Win` en `d` ; la disjonction existentielle tient. Un nœud
adversaire au trait a tous ses enfants dans le même cas, la conjonction
universelle tient (ensemble non vide contrôlé, donc aucune dépendance à la
convention de pat ; pour H ≥ 3 le cas vide est de toute façon impossible,
cf. `STALEMATE_THEOREM.md`). Comme `d` décroît strictement le long des
arêtes certifiées, le graphe est acyclique et la stratégie termine en `≤ D`
plis : la borne de l'en-tête est vérifiée structurellement, pas déclarée. ∎

Le vérificateur ne fait confiance qu'à : son propre générateur de coups, son
test de terminalité, et l'arithmétique des inégalités. Ni table de
transposition, ni symétrie, ni ordre des coups, ni profondeur relative — les
sources d'erreur classiques du solveur sont hors du périmètre de confiance.

## Émission

Côté solveur, l'extraction est un parcours du sous-graphe de la stratégie :

- à `T` au trait : choisir un enfant `c` minimisant la profondeur de gain
  exacte `dmin(c)` (garantit `d` strictement décroissant et déduplication
  cohérente, `d` étant fonction de l'état) ;
- à l'adversaire au trait : parcourir tous les enfants légaux.

`dmin` s'obtient par requêtes bornées croissantes sur chaque état du
sous-graphe (coût faible : le sous-graphe de stratégie est bien plus petit
que l'espace exploré). Ce choix évite le piège classique : mélanger des
choix prouvés à des profondeurs incohérentes entre branches peut créer un
cycle ; avec `d = dmin` exact, `d` décroît strictement le long de toute
arête, donc aucun cycle n'est possible.

## Implémentations

- `qcert.mjs emit W H walls maxD [fichier]` — émetteur de démonstration
  (petites variantes, solveur de référence JS).
- `qcert.mjs verify fichier` — vérificateur indépendant (moteur clean-room
  de `qref.mjs`).
- Cible réelle : l'émetteur C++ du solveur principal produit le même format ;
  `qcert.mjs verify` reste le juge indépendant.

## Passage à l'échelle (3×9×10 et au-delà)

Le format v1 privilégie l'auditabilité (JSONL lisible, diffable, gzip
efficace). Si le certificat 3×9×10 dépasse la mémoire du vérificateur :
tri externe des lignes par clé d'état, puis vérification en deux passes
(passe 1 : index trié ; passe 2 : jointure triée parent→enfants). Le format
ne change pas ; seule l'implémentation du vérificateur change. Une variante
binaire (`qcert-1b`) n'est justifiée que si la taille devient le facteur
limitant après gzip.
