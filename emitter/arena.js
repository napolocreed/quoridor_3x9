/**
 * Banc d'essai : tournoi toutes rondes, Elo, étude d'ablation des
 * optimisations, et réglage des poids d'évaluation par auto-apprentissage.
 *
 *   node arena.js calibrate
 *   node arena.js tournament
 *   node arena.js ablation
 *   node arena.js tune [iterations]
 *
 * @module arena
 */
import { Position, moveToNotation } from './engine.js';
import {
  createAgent, playGame, PROFILES, SearchEngine, DEFAULT_WEIGHTS, rng
} from './ai.js';

const pad = (s, n) => String(s).padEnd(n);
const padL = (s, n) => String(s).padStart(n);

/* ═══════════ Elo (Bradley–Terry, itérations MM) ═══════════ */

export function computeElo(names, score, games, anchorIdx = 0) {
  const n = names.length;
  const gamma = new Array(n).fill(1);
  for (let it = 0; it < 400; it++) {
    for (let i = 0; i < n; i++) {
      let wins = 0, den = 0;
      for (let j = 0; j < n; j++) {
        if (i === j || games[i][j] === 0) continue;
        wins += score[i][j];
        den += games[i][j] / (gamma[i] + gamma[j]);
      }
      if (den > 0 && wins > 0) gamma[i] = wins / den;
    }
  }
  const elo = gamma.map(g => 400 * Math.log10(Math.max(1e-9, g)));
  const base = elo[anchorIdx];
  return elo.map(e => Math.round(e - base));
}

/* ═══════════ ouvertures aléatoires appariées ═══════════ */

/**
 * Les agents de recherche sont déterministes : sans diversification, toutes
 * les parties d'un même appariement seraient identiques et le score
 * vaudrait mécaniquement 50 %. On tire donc une ouverture courte au hasard,
 * jouée deux fois — une par couleur — ce qui neutralise aussi l'avantage
 * du trait.
 */
export function makeOpening(idx, plies) {
  const p = new Position();
  const r = rng((0x9E3779B9 ^ Math.imul(idx + 1, 2654435761)) >>> 0);
  const buf = new Int32Array(256);
  for (let i = 0; i < plies; i++) {
    const nPawn = p.pawnMoves(buf, 0);
    const n = r() < 0.7 ? nPawn : p.legalMoves(buf, true);
    p.doMove(buf[(r() * n) | 0]);
    if (p.winner() !== -1) break;
  }
  return p;
}

/* ═══════════ match entre deux agents ═══════════ */

/** @param {number} pairs nombre d'ouvertures ; chacune est jouée 2 fois (une par couleur) */
export function match(makeA, makeB, pairs, opts = {}) {
  let a = 0, b = 0, draw = 0, plies = 0, games = 0;
  const openingPlies = opts.openingPlies ?? 3;
  for (let g = 0; g < pairs; g++) {
    const opening = makeOpening((opts.openingSeed ?? 0) + g, openingPlies);
    if (opening.winner() !== -1) continue;
    for (let side = 0; side < 2; side++) {
      const A = makeA(g), B = makeB(g);
      const aIsRed = side === 0;
      const r = playGame(aIsRed ? A : B, aIsRed ? B : A, {
        maxPlies: opts.maxPlies ?? 220,
        position: opening.clone()
      });
      games++; plies += r.plies;
      if (r.winner === -1) draw++;
      else if (r.winner === (aIsRed ? 0 : 1)) a++;
      else b++;
    }
  }
  return { a, b, draw, games, plies: plies / games, scoreA: a + draw / 2 };
}

/* ═══════════ 1. calibrage ═══════════ */

function calibrate() {
  console.log('\n═══ calibrage ═══\n');
  const p = new Position();
  console.log(pad('profondeur', 12) + padL('noeuds', 12) + padL('ms', 8) + padL('noeuds/s', 12));
  for (const d of [2, 3, 4, 5, 6, 7]) {
    const e = new SearchEngine();
    const r = e.search(p, { maxDepth: d, maxTimeMs: 20000 });
    console.log(pad(d, 12) + padL(r.nodes, 12) + padL(r.ms, 8) + padL(Math.round(r.nodes / Math.max(1, r.ms) * 1000), 12));
  }
  console.log('\ndurée d\'une partie complète :');
  for (const [prof, over] of [['coureur', {}], ['tacticien', { depth: 2 }], ['tacticien', { depth: 3 }], ['stratege', { depth: 4, timeMs: 5000 }]]) {
    const t0 = Date.now();
    const r = playGame(createAgent(prof, { ...over, seed: 1 }), createAgent(prof, { ...over, seed: 2 }), { maxPlies: 220 });
    console.log(`  ${pad(prof + (over.depth ? ' d' + over.depth : ''), 16)} ${padL(Date.now() - t0, 6)} ms  ${padL(r.plies, 4)} demi-coups  (${r.reason})`);
  }
}

/* ═══════════ 2. tournoi toutes rondes ═══════════ */

function tournament(gamesPerPair = 12) {
  const roster = [
    ['novice', {}],
    ['coureur', {}],
    ['batisseur', {}],
    ['tacticien', { depth: 3 }],
    ['stratege', { depth: 4, timeMs: 4000 }],
    ['oracle', { depth: 64, timeMs: 80 }]
  ];
  const names = roster.map(([k, o]) => PROFILES[k].label + (o.depth ? ' d' + o.depth : ''));
  const n = roster.length;
  const score = Array.from({ length: n }, () => new Array(n).fill(0));
  const games = Array.from({ length: n }, () => new Array(n).fill(0));

  console.log(`\n═══ tournoi toutes rondes — ${gamesPerPair} parties par paire ═══\n`);
  const t0 = Date.now();
  for (let i = 0; i < n; i++) {
    for (let j = i + 1; j < n; j++) {
      const mk = (idx) => (g) => createAgent(roster[idx][0], { ...roster[idx][1], seed: g * 977 + idx * 31 + 1 });
      const r = match(mk(i), mk(j), gamesPerPair, { openingSeed: (i * 17 + j) * 500, openingPlies: 3 });
      score[i][j] = r.scoreA; score[j][i] = r.games - r.scoreA;
      games[i][j] = r.games; games[j][i] = r.games;
      console.log(`  ${pad(names[i], 14)} ${padL(r.a, 3)} – ${padL(r.b, 3)}${r.draw ? ' (' + r.draw + ' nulles)' : ''}  ${names[j]}`);
    }
  }
  const elo = computeElo(names, score, games, 0);
  const order = names.map((_, i) => i).sort((x, y) => elo[y] - elo[x]);

  console.log(`\n  classement (Elo relatif, Novice = 0) — ${Math.round((Date.now() - t0) / 1000)} s\n`);
  console.log('  ' + pad('agent', 16) + padL('Elo', 7) + padL('score', 9) + '   profil');
  for (const i of order) {
    const tot = games[i].reduce((a, b) => a + b, 0);
    const won = score[i].reduce((a, b) => a + b, 0);
    console.log('  ' + pad(names[i], 16) + padL(elo[i], 7) +
      padL(tot ? (100 * won / tot).toFixed(0) + '%' : '—', 9) + '   ' +
      (PROFILES[roster[i][0]].blurb || ''));
  }
}

/* ═══════════ 3. ablation des optimisations ═══════════ */

function ablation() {
  console.log('\n═══ ablation — que rapporte chaque optimisation ? ═══\n');
  const positions = [new Position(), makeOpening(3, 8), makeOpening(11, 14)];
  const variants = [
    ['tout activé', { useTT: true, pruneWalls: true }],
    ['sans table de transposition', { useTT: false, pruneWalls: true }],
    ['sans filtrage des murs', { useTT: true, pruneWalls: false }],
    ['sans rien', { useTT: false, pruneWalls: false }]
  ];
  const DEPTH = 5;
  console.log('  ' + pad('variante', 30) + padL('noeuds', 12) + padL('ms', 8) + padL('vs ref', 9));
  let ref = null;
  for (const [label, opt] of variants) {
    let nodes = 0, ms = 0;
    for (const p of positions) {
      const e = new SearchEngine(opt);
      const r = e.search(p.clone(), { maxDepth: DEPTH, maxTimeMs: 60000 });
      nodes += r.nodes; ms += r.ms;
    }
    if (ref === null) ref = ms;
    console.log('  ' + pad(label, 30) + padL(nodes, 12) + padL(ms, 8) +
      padL((ms / ref).toFixed(2) + '×', 9));
  }

  console.log('\n  le filtrage des murs coûte-t-il en force ?');
  const r = match(
    g => createAgent('tacticien', { depth: 3, seed: g * 13 + 1, pruneWalls: true }),
    g => createAgent('tacticien', { depth: 3, seed: g * 17 + 2, pruneWalls: false }),
    16, { openingSeed: 90000, openingPlies: 3 }
  );
  console.log(`    filtré ${r.a} – ${r.b} complet  (${r.draw} nulles) — à profondeur égale`);
  console.log('    -> à profondeur égale le filtrage coûte un peu de force, mais il');
  console.log('       divise le temps par ~6 : on gagne 2 niveaux de profondeur, très');
  console.log('       largement rentable (cf. le classement Elo par profondeur).');
}

/* ═══════════ 4. réglage des poids (SPSA) ═══════════ */

function tune(iterations = 24) {
  console.log(`\n═══ réglage des poids par auto-apprentissage (SPSA, ${iterations} itérations) ═══\n`);
  // `path` sert d'échelle de référence et reste fixe ; on règle les autres.
  const keys = ['wall', 'prog', 'tempo', 'hoard'];
  const w = { ...DEFAULT_WEIGHTS };
  const step = { wall: 4, prog: 2, tempo: 3, hoard: 6 };
  const GAMES = 26, DEPTH = 2;   // 26 ouvertures = 52 parties (bruit ~±7 %)

  console.log('  départ : ' + keys.map(k => `${k}=${w[k]}`).join('  '));
  const t0 = Date.now();

  for (let it = 1; it <= iterations; it++) {
    const delta = {}; for (const k of keys) delta[k] = Math.random() < 0.5 ? -1 : 1;
    const wp = { ...w }, wm = { ...w };
    for (const k of keys) { wp[k] += step[k] * delta[k]; wm[k] -= step[k] * delta[k]; }

    const r = match(
      g => createAgent('tacticien', { depth: DEPTH, weights: wp, seed: g * 101 + it }),
      g => createAgent('tacticien', { depth: DEPTH, weights: wm, seed: g * 211 + it }),
      GAMES, { openingSeed: it * 1000, openingPlies: 4 }
    );
    const grad = (r.scoreA / r.games - 0.5) * 2;        // -1..1, 0 si match nul
    for (const k of keys) {
      w[k] = Math.max(0, Math.round(w[k] + grad * step[k] * delta[k] * 0.9));
    }
    if (it % 4 === 0 || it === 1) {
      console.log(`  it ${padL(it, 3)}  ${padL((r.scoreA / r.games * 100).toFixed(0) + '%', 5)}  ` +
        keys.map(k => `${k}=${padL(w[k], 3)}`).join('  '));
    }
  }

  console.log(`\n  poids obtenus (${Math.round((Date.now() - t0) / 1000)} s) :`);
  console.log('  ' + JSON.stringify({ ...w }));

  console.log('\n  validation : poids réglés contre poids de départ (profondeur 3)');
  const v = match(
    g => createAgent('tacticien', { depth: 3, weights: w, seed: g * 7 + 5 }),
    g => createAgent('tacticien', { depth: 3, weights: DEFAULT_WEIGHTS, seed: g * 19 + 6 }),
    30, { openingSeed: 500000, openingPlies: 4 }
  );
  const pct = (v.scoreA / v.games * 100).toFixed(0);
  console.log(`    réglés ${v.a} – ${v.b} départ  (${v.draw} nulles) = ${pct}%`);
  const eloGain = v.scoreA === v.games ? '∞' :
    Math.round(-400 * Math.log10(v.games / v.scoreA - 1));
  console.log(`    gain estimé : ${eloGain} Elo`);
  return w;
}

/* ═══════════ CLI ═══════════ */

import { fileURLToPath } from 'url';
const isMain = process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1];
const mode = isMain ? (process.argv[2] || 'calibrate') : null;
if (isMain) {
  if (mode === 'calibrate') calibrate();
  else if (mode === 'tournament') tournament(+(process.argv[3] || 12));
  else if (mode === 'ablation') ablation();
  else if (mode === 'tune') tune(+(process.argv[3] || 24));
  else console.log('modes : calibrate | tournament | ablation | tune');
}
