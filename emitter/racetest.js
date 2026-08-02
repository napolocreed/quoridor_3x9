/**
 * Validation de la table de course exacte (race.js).
 *
 *   node racetest.js
 *
 * 1. position initiale sans murs : le trait gagne la course symétrique ;
 * 2. cohérence interne : depuis des états 0-0 aléatoires, si la table annonce
 *    « gain en v », une partie jouée par bestMove des DEUX côtés dure
 *    exactement v plis et le bon joueur gagne ; une nulle annoncée cycle ;
 * 3. validation croisée contre l'alpha-bêta SANS table (implémentation
 *    antérieure, indépendante de race.js) : accord de signe et de distance
 *    de mat sur les états où la recherche peut conclure ;
 * 4. fragilité : le comptage de chemins réagit comme attendu aux murs.
 */
import { Position, moveToNotation, notationToMove } from './engine.js';
import { SearchEngine, MATE } from './ai.js';
import { RaceTable } from './race.js';
import { rng } from './ai.js';

let failures = 0;
function check(label, cond, detail = '') {
  if (cond) console.log(`  ok  ${label}`);
  else { failures++; console.log(`  ÉCHEC  ${label}  ${detail}`); }
}

/* position 0-0 aléatoire : murs légaux posés via Position, stocks vidés */
function randomEndgame(seed, nWalls) {
  const r = rng(seed);
  const pos = new Position();
  const buf = new Int32Array(256);
  // pose de murs légaux au hasard (en alternance, comme une vraie partie)
  for (let i = 0; i < nWalls * 4 && pos.left[0] + pos.left[1] > 20 - nWalls; i++) {
    const n = pos.legalMoves(buf, true);
    const walls = [];
    for (let j = 0; j < n; j++) if (buf[j] >= 81) walls.push(buf[j]);
    if (!walls.length) break;
    pos.doMove(walls[(r() * walls.length) | 0]);
  }
  // pions au hasard (non terminaux, non superposés)
  let p0, p1;
  do { p0 = (r() * 72) | 0; } while (false);            // < 72 : jamais arrivé
  do { p1 = 9 + ((r() * 72) | 0); } while (p1 === p0);  // > 8  : jamais arrivé
  pos.pawn[0] = p0; pos.pawn[1] = p1;
  pos.left[0] = 0; pos.left[1] = 0;
  pos.turn = (r() * 2) | 0;
  pos._invalidate(); pos._rehash();
  return pos;
}

console.log('— 1. course symétrique initiale : zugzwang mutuel —');
{
  // Résultat contre-intuitif mais réel : sans murs, dans la position de départ
  // symétrique, CELUI QUI DOIT JOUER PERD la course. C'est celui qui approche
  // le premier qui se fait sauter par-dessus, et le saut donne le tempo.
  const pos = new Position();
  pos.left[0] = 0; pos.left[1] = 0;
  pos._invalidate(); pos._rehash();
  const rt = new RaceTable(pos.adj);
  const v = rt.probe(4, 76, 0);
  const v2 = rt.probe(4, 76, 1);
  check(`zugzwang mutuel (v=${v}, v2=${v2})`, v < 0 && v2 === v);
  check('parité paire de la défaite', v % 2 === 0);
  // confirmation par l'alpha-bêta SANS table : défaite en 16 -> score -MATE+15
  const eng = new SearchEngine({ useRace: false });
  const r = eng.search(pos.clone(), { maxDepth: -v + 2, maxTimeMs: 120000 });
  check(`alpha-bêta indépendant d'accord (score=${r.score}, attendu ${-(MATE - (-v - 1))})`,
    r.score === -(MATE - (-v - 1)));
}

console.log('— 2. cohérence interne : bestMove réalise exactement la valeur —');
{
  let done = 0;
  const failBefore = failures;
  for (let seed = 1; done < 40; seed++) {
    const pos = randomEndgame(seed * 7919, 3 + (seed % 5));
    if (pos.distance(0) < 0 || pos.distance(1) < 0) continue;
    const rt = new RaceTable(pos.adj);
    const v0 = rt.probe(pos.pawn[0], pos.pawn[1], pos.turn);
    let p = [pos.pawn[0], pos.pawn[1]], turn = pos.turn, plies = 0, winner = -1;
    while (plies < 400) {
      const z = rt.bestMove(p[0], p[1], turn);
      p = turn === 0 ? [z, p[1]] : [p[0], z];
      plies++;
      if (turn === 0 && z >= 72) { winner = 0; break; }
      if (turn === 1 && z <= 8) { winner = 1; break; }
      turn = 1 - turn;
    }
    if (v0 > 0) {
      const expWinner = pos.turn;
      if (!(winner === expWinner && plies === v0)) {
        failures++;
        console.log(`  ÉCHEC  seed ${seed} : annoncé v=${v0}, joué ${plies} plis, vainqueur ${winner} (attendu ${expWinner})`);
      }
    } else if (v0 < 0) {
      const expWinner = 1 - pos.turn;
      if (!(winner === expWinner && plies === -v0)) {
        failures++;
        console.log(`  ÉCHEC  seed ${seed} : annoncé v=${v0}, joué ${plies} plis, vainqueur ${winner} (attendu ${expWinner})`);
      }
    } else if (winner !== -1) {
      failures++;
      console.log(`  ÉCHEC  seed ${seed} : nulle annoncée mais vainqueur ${winner} en ${plies} plis`);
    }
    done++;
  }
  check(`40 fins de partie rejouées à la valeur exacte`, failures === failBefore);
}

console.log('— 3. validation croisée contre l\'alpha-bêta sans table —');
{
  let checked = 0, agreed = 0;
  const details = [];
  for (let seed = 100; checked < 25; seed++) {
    const pos = randomEndgame(seed * 104729, 4 + (seed % 4));
    if (pos.distance(0) < 0 || pos.distance(1) < 0) continue;
    const rt = new RaceTable(pos.adj);
    const v = rt.probe(pos.pawn[0], pos.pawn[1], pos.turn);
    if (v === 0 || Math.abs(v) > 13) continue;   // hors de portée d'une recherche exacte courte
    const eng = new SearchEngine({ useRace: false, useTT: true });
    const r = eng.search(pos.clone(), { maxDepth: Math.abs(v) + 2, maxTimeMs: 30000 });
    checked++;
    const sSign = r.score > MATE / 2 ? 1 : r.score < -MATE / 2 ? -1 : 0;
    const vSign = Math.sign(v);
    const sDist = r.score > MATE / 2 ? MATE - r.score : r.score < -MATE / 2 ? MATE + r.score : -1;
    // la recherche marque le mat au pli où le coup gagnant est JOUÉ :
    // gain en v plis -> score = MATE - (v-1) ; défaite en k -> -MATE + (k-1)
    const expDist = Math.abs(v) - 1;
    if (sSign === vSign && sDist === expDist) agreed++;
    else details.push({ seed, v, score: r.score, sDist, expDist });
  }
  check(`25 états 0-0 : accord signe + distance de mat (${agreed}/${checked})`,
    agreed === checked, JSON.stringify(details.slice(0, 3)));
}

console.log('— 4. fragilité par coût de détour —');
{
  const pos = new Position();
  const f0 = pos.pathFragility(0);
  check(`longueur initiale 8 (f=${f0 >> 5})`, (f0 >> 5) === 8);
  // le but est une rangée : l'alternative optimale est un pas de côté puis
  // la colonne voisine, soit +1 seulement
  check(`plateau vide robuste : détour 1 (mesuré ${f0 & 31})`, (f0 & 31) === 1);
  // rangée 1 presque scellée : seul le couloir i1-i2 reste ouvert ->
  // le chemin est unique, aucune alternative arête-disjointe : détour saturé
  for (const w of ['ha1', 'hc1', 'he1', 'hg1']) pos.doMove(notationToMove(w));
  const f1 = pos.pathFragility(0);
  check(`couloir unique : détour saturé (mesuré ${f1 & 31})`, (f1 & 31) === 31);
}

console.log(failures === 0 ? '\ntout est vert' : `\n${failures} échec(s)`);
process.exit(failures ? 1 : 0);
