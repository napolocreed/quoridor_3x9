# Quoridor — moteur, IA et recherche exacte

Deux volets dans ce dossier.

**Le programme app 9×9** : moteur de règles complet, recherche alpha-bêta et
famille d'agents. JavaScript ES modules, **zéro dépendance, zéro étape de
build** : ça tourne tel quel dans Node, dans un Web Worker, dans un navigateur
et dans React Native.

**Le programme de recherche exacte** (variantes étroites, réplication du
3×9×10, certificats vérifiables) : voir `STALEMATE_THEOREM.md` (théorème du
pat : vrai pour H ≥ 3, faux pour H = 2, vérifié exhaustivement),
`CERTIFICATE_FORMAT.md` (spec qcert-1), `HANDOFF.md` + `REVIEW-sol.md`
(réplication indépendante du résultat 3×9×10 : J1 gagne en exactement 35
plis), et `NOTE_POUR_SOL.md` (coordination avec le solveur principal).

## Fichiers — app 9×9

| fichier | rôle |
|---|---|
| `engine.js` | règles, génération de coups, légalité des murs (union-find), plus courts chemins, fragilité par coût de détour, Zobrist |
| `ai.js` | évaluation (terme `frag` optionnel), alpha-bêta, oracle de course exacte aux feuilles, agents, arbitre |
| `race.js` | table de course exacte : stocks épuisés ⇒ fin de partie PARFAITE (13 122 états par configuration, point fixe) |
| `racetest.js` | validation croisée de la table (zugzwang initial −16 confirmé par alpha-bêta indépendant) |
| `worker.js` | enveloppe Web Worker : la recherche ne bloque jamais l'interface |
| `arena.js` | tournoi, Elo, ablation, réglage des poids ; `exp_upgrades.js` mesure course+fragilité |
| `test.js` | 33 tests, dont un générateur naïf de référence |
| `demo.html` | démo jouable autonome (double-clic, aucun serveur) |

## Fichiers — recherche exacte

| fichier | rôle |
|---|---|
| `qref.mjs` | moteur clean-room (validé : 0 divergence sur ~65 k états vs C++) + solveur borné |
| `qscan.mjs` | scans exhaustifs du théorème du pat (atteignable, sur-ensemble légal, deux conventions) |
| `qcert.mjs` | émetteur/vérificateur qcert-1 de démonstration (9 variantes certifiées = archives) |
| `qsolve.cpp` | solveur de réplication (architecture séparée : cache paresseux + porte union-find) |
| `qcert2.cpp` | extracteur de certificat par classe de réponse (invariant min-rem) |
| `qmerge.cpp` | tri/contrôle des parts binaires |
| `qverify.cpp` | **vérificateur C++ exhaustif** par part, clean-room, option `--mirror` pour les jumelles |
| `qexport.cpp` | export mémo → qcert-1 JSONL (conforme à la spec durcie de sol) |
| `verify_cert.py` | vérificateur Python indépendant (sample / walk / forensic) |
| `orchestrate.py` | pipeline par classe : preuve → extraction → tri → vérifications |
| `lower.py` | borne inférieure : réfutation des 18 premiers coups J1 à ≤ 33 plis |

```bash
node test.js              # la suite de validation
node arena.js calibrate   # vitesse de recherche
node arena.js tournament  # classement Elo
node arena.js ablation    # ce que rapporte chaque optimisation
node arena.js tune 40     # réglage des poids par SPSA
node build.js             # reconstruit demo.html à partir des modules
```

## Notation

Identique à celle de ton app, sans conversion : `e2` pour un pion, `he5` /
`ve5` pour un mur (`h`/`v`, colonne `a`–`h`, rangée `1`–`8`, ancré au coin
sud-ouest). Joueur 1 part de `e1` et vise la rangée 9, joueur 2 part de `e9`
et vise la rangée 1.

## Intégration

Le plus simple : envoyer la liste des coups déjà joués, récupérer le coup de
l'IA. Aucun état partagé, donc rien à synchroniser.

```js
const ia = new Worker(new URL('./worker.js', import.meta.url), { type: 'module' });

ia.onmessage = (e) => {
  if (e.data.type === 'move') joue(e.data.notation);   // "he5"
};

ia.postMessage({
  type: 'think',
  moves: ['e2', 'e8', 'he5'],   // l'historique que tu affiches déjà
  profile: 'oracle',
  timeMs: 800
});
```

En direct, sans worker :

```js
import { Position } from './engine.js';
import { createAgent } from './ai.js';

const pos = Position.fromMoves(['e2', 'e8', 'he5']);
const ia = createAgent('oracle', { timeMs: 800 });
const { move, info } = ia.think(pos);   // move est un entier
pos.doMove(move);
```

Le moteur sert aussi d'arbitre côté app, si tu veux arrêter de valider les
coups à la main :

```js
pos.isLegal(m)              // un coup est-il jouable ?
pos.legalMoves(buf)         // tous les coups légaux (pions + murs)
pos.wallLegal(orient, slot) // ce mur enfermerait-il quelqu'un ?
pos.distance(0)             // longueur du plus court chemin du joueur 1
pos.winner()                // -1, 0 ou 1
pos.toJSON()                // état sérialisable
```

`worker.js` accepte aussi `{type:'legal'}` pour surligner les coups jouables
et `{type:'analyse'}` pour afficher une barre d'évaluation.

## Les agents

| profil | Elo mesuré | comportement |
|---|---|---|
| `novice` | 0 | coups légaux au hasard — plancher de référence |
| `coureur` | 280 | fonce, ne pose un mur que s'il est distancé |
| `batisseur` | 451 | privilégie le mur qui allonge le plus l'adversaire |
| `tacticien` | 569 | alpha-bêta 3 demi-coups |
| `stratege` | 554 | alpha-bêta 4 demi-coups |
| `oracle` | 561 | approfondissement itératif sous budget de temps |

Elo relatif, Novice ancré à 0, tournoi toutes rondes avec ouvertures
aléatoires appariées. Les trois derniers sont à départager : à 10 parties par
appariement l'incertitude est d'environ ±80 Elo, ils sont statistiquement
indistinguables.

## Ce que les mesures disent

**Le filtrage des murs est l'optimisation qui compte.** Le facteur de
branchement tombe de ~128 à ~25 en ne gardant que les murs qui coupent l'un
des deux plus courts chemins, ou qui prolongent un mur existant.

| variante | temps |
|---|---|
| tout activé | 1,00× |
| sans table de transposition | 1,07× |
| sans filtrage des murs | 6,18× |
| sans rien | 9,21× |

**Le raccourci de légalité vient de la planarité.** Vérifier qu'un mur
n'enferme personne coûte un BFS. Or un mur ne peut couper le plateau que s'il
referme un cycle dans le treillis des jonctions, bord extérieur compris. Un
union-find à annulation répond à cette question en O(α), et le BFS ne tourne
plus que dans les rares cas où un cycle se ferme. C'est là qu'est le gain de
6×. La table de transposition, elle, ne rapporte presque rien : les
transpositions sont rares au Quoridor, un mur posé ne se reprend jamais.

**L'évaluation ne se règle pas.** SPSA sur 40 itérations et 2080 parties
revient aux poids de départ, gain nul. Le diagnostic est net : en changeant
*radicalement* les poids secondaires (murs, progression, tempo), le coup
choisi ne change que dans **5 positions sur 60**. La différence de plus court
chemin écrase tout le reste. Inutile de chercher de la force de ce côté-là.

**Le trait décide la partie initiale.** Depuis la position de départ, rouge
gagne 24/24 entre deux moteurs identiques. Tout banc d'essai doit donc partir
d'ouvertures aléatoires jouées deux fois, une par couleur — sinon chaque match
sort à 50 % exactement et ne mesure rien.

**Où la profondeur sert vraiment.** En milieu de partie la recherche plafonne
vers 4–5 demi-coups. Mais dès que les murs cessent de compter, elle bascule et
résout la course exactement : profondeur 30, « gain forcé en 31 ». Sur une
partie complète, 63 % des coups sont joués avec un gain forcé déjà démontré.
Passer de 30 ms à 200 ms par coup vaut 58 % contre 42 %.

**La table de course exacte vaut +80 à +98 Elo** (mesuré à 80 et 300 ms,
40 parties par appariement) : stocks épuisés ⇒ fin de partie parfaite en
O(1), y compris les nulles de zugzwang que la recherche ratait. Fait notable
prouvé au passage : sans murs, dans la position initiale symétrique, **celui
qui doit jouer perd la course en 16 plis** (zugzwang mutuel — le saut donne
le tempo au second ; confirmé par alpha-bêta indépendant).

**La fragilité par coût de détour est un vrai signal mais un mauvais achat
au temps réel** : +89 Elo à profondeur fixe, −108 Elo à 200 ms/coup — les
4 BFS par évaluation (au lieu de 2 avec sortie anticipée) coûtent plus de
profondeur qu'ils ne rapportent de discernement. `frag` reste donc à 0 par
défaut ; la piste utile est une implémentation bon marché (cache par
configuration de murs, ou tri de coups racine uniquement).

## Performance

378 000 nœuds/s, profondeur 7 en 2 s depuis la position initiale, sur un seul
cœur. Aucune allocation dans la boucle de recherche : tampons de coups
préalloués par profondeur, tableaux typés, estampillage par génération au lieu
de remises à zéro.

## Vérification

`node test.js` — 33 tests. Les trois qui comptent :

- **perft(2) = 16 677**, recoupé trois fois : générateur optimisé,
  décomposition analytique, et générateur naïf indépendant.
- **3581 positions** comparées coup par coup à une implémentation naïve lente
  mais évidemment correcte.
- **115 200 verdicts de légalité de mur** sur 900 plateaux saturés, dont
  **2194 refus d'enfermement**, tous identiques à la référence. C'est ce test
  qui valide le raccourci par union-find.

Deux tests de régression méritent d'être signalés, parce qu'ils viennent de
bugs réels trouvés en route :

- *l'intégrité de la position après recherche* : à l'expiration du budget de
  temps, la recherche lève une exception au milieu de la récursion et tous les
  `undoMove` en attente sautent. La position restait corrompue. Le bug
  invalidait silencieusement toutes les mesures à budget de temps.
- *le test de saturation* : dans sa première version il ne testait rien, parce
  qu'après 40 demi-coups les deux joueurs n'avaient plus de murs et que tous
  les verdicts valaient trivialement « illégal ».

## Pour aller plus loin

Le cœur est isolé derrière une interface étroite (`Position` + `SearchEngine`),
donc remplaçable par un module Rust→WASM sans toucher au reste. Il faut
s'attendre à 5–10× en nœuds/s. Mais au vu des mesures ci-dessus, ce n'est pas
là que se gagne la force : à ce stade le moteur est limité par son évaluation,
pas par sa vitesse. Deux pistes qui rapporteraient davantage :

1. **Un terme d'évaluation qui capture les murs.** Aujourd'hui l'évaluation
   voit la course mais pas la valeur positionnelle d'un mur. Un terme de
   « second plus court chemin » (à quel point le chemin est fragile) est le
   candidat le plus prometteur.
2. **Un livre d'ouvertures.** Les premiers coups sont stéréotypés et la
   recherche y perd du temps.
