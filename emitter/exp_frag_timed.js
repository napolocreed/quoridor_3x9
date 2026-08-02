/** Appariement 4 seul (interrompu deux fois) : fragilité au temps réel. */
import { match } from './arena.js';
import { createAgent } from './ai.js';

const pairs = +(process.argv[2] || 20);
const t0 = Date.now();
const r = match(
  g => createAgent('oracle', { timeMs: 200, weights: { frag: 8 }, seed: g * 13 + 7 }),
  g => createAgent('oracle', { timeMs: 200, seed: g * 17 + 8 }),
  pairs, { openingSeed: 44000, openingPlies: 3 });
const pct = r.scoreA / r.games;
const elo = pct <= 0 ? -Infinity : pct >= 1 ? Infinity : Math.round(-400 * Math.log10(1 / pct - 1));
console.log(JSON.stringify({
  label: 'frag8 vs frag0 @ oracle 200ms', a: r.a, b: r.b, draws: r.draw,
  games: r.games, pctA: +(100 * pct).toFixed(1), eloA: elo,
  avgPlies: +r.plies.toFixed(1), seconds: +((Date.now() - t0) / 1000).toFixed(0)
}));
