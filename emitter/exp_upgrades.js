/**
 * Mesure des deux améliorations (table de course exacte, fragilité par détour).
 *
 *   node exp_upgrades.js [pairs]
 *
 * Chaque appariement : `pairs` ouvertures aléatoires jouées deux fois (une par
 * couleur). Sortie JSONL, un objet par appariement.
 */
import { match } from './arena.js';
import { createAgent } from './ai.js';

const pairs = +(process.argv[2] || 20);

function run(label, mkA, mkB, seedBase) {
  const t0 = Date.now();
  const r = match(mkA, mkB, pairs, { openingSeed: seedBase, openingPlies: 3 });
  const pct = r.scoreA / r.games;
  const elo = pct <= 0 ? -Infinity : pct >= 1 ? Infinity :
    Math.round(-400 * Math.log10(1 / pct - 1));
  console.log(JSON.stringify({
    label, a: r.a, b: r.b, draws: r.draw, games: r.games,
    scoreA: r.scoreA, pctA: +(100 * pct).toFixed(1), eloA: elo,
    avgPlies: +r.plies.toFixed(1), seconds: +((Date.now() - t0) / 1000).toFixed(0)
  }));
}

// 1. table de course, budget court : là où la recherche ne résout pas la course
run('race-on vs race-off @ oracle 80ms',
  g => createAgent('oracle', { timeMs: 80, seed: g * 13 + 1 }),
  g => createAgent('oracle', { timeMs: 80, seed: g * 17 + 2, useRace: false }),
  11000);

// 2. table de course, budget moyen
run('race-on vs race-off @ oracle 300ms',
  g => createAgent('oracle', { timeMs: 300, seed: g * 13 + 3 }),
  g => createAgent('oracle', { timeMs: 300, seed: g * 17 + 4, useRace: false }),
  22000);

// 3. fragilité, profondeur fixe : le signal aide-t-il, coût mis à part ?
run('frag8 vs frag0 @ tacticien d3',
  g => createAgent('tacticien', { depth: 3, weights: { frag: 8 }, seed: g * 13 + 5 }),
  g => createAgent('tacticien', { depth: 3, seed: g * 17 + 6 }),
  33000);

// 4. fragilité au temps : le signal vaut-il son coût de calcul ?
run('frag8 vs frag0 @ oracle 200ms',
  g => createAgent('oracle', { timeMs: 200, weights: { frag: 8 }, seed: g * 13 + 7 }),
  g => createAgent('oracle', { timeMs: 200, seed: g * 17 + 8 }),
  44000);
