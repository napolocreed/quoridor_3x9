/**
 * rev_frag.mjs — adversarial check of Position.pathFragility().
 *
 * 1. Reference implementation (plain JS, no shared scratch, mirrors the same
 *    BFS neighbour order and insertion-time goal detection so tie-breaking is
 *    identical) compared on thousands of random positions.
 * 2. Staleness attacks: pathFragility called mid "search-like" activity —
 *    after doMove/undoMove churn, after wallLegal/candidateWalls (which build
 *    and cache paths), after the _generate-style pawn mutation hack, and
 *    back-to-back for both players — always compared against a cold clone.
 */
import { Position, isWallMove, DELTA, BIT, edgeId } from '../engine.js';

function rng(seed) {
  let s = seed >>> 0;
  return () => {
    s ^= s << 13; s >>>= 0; s ^= s >> 17; s ^= s << 5; s >>>= 0;
    return s / 4294967296;
  };
}
let fails = 0;
function check(cond, label) { if (!cond) { fails++; console.log('FAIL: ' + label); } }

/** Reference pathFragility mirroring engine BFS order exactly. */
function refFrag(pos, player) {
  const goalHigh = player === 0;
  const start = pos.pawn[player], adj = pos.adj;
  const atGoal = goalHigh ? start >= 72 : start <= 8;
  if (atGoal) return 0;
  // BFS with parent, goal detected at insertion time, neighbour order k=0..3
  let dist = new Map([[start, 0]]), par = new Map([[start, -1]]);
  let q = [start], end = -1, len = -1;
  outer:
  for (let qh = 0; qh < q.length; qh++) {
    const c = q[qh], d = dist.get(c) + 1, mask = adj[c];
    for (let k = 0; k < 4; k++) {
      if (!(mask & BIT[k])) continue;
      const n = c + DELTA[k];
      if (dist.has(n)) continue;
      dist.set(n, d); par.set(n, c); q.push(n);
      if (goalHigh ? n >= 72 : n <= 8) { end = n; len = d; break outer; }
    }
  }
  if (len < 0) return -1;
  const banned = new Set();
  for (let c = end; par.get(c) !== -1; c = par.get(c)) banned.add(edgeId(c, par.get(c)));
  // second BFS avoiding banned edges, goal at generation before stamping
  dist = new Map([[start, 0]]); q = [start];
  let alt = -1;
  outer2:
  for (let qh = 0; qh < q.length; qh++) {
    const c = q[qh], d = dist.get(c) + 1, mask = adj[c];
    for (let k = 0; k < 4; k++) {
      if (!(mask & BIT[k])) continue;
      const n = c + DELTA[k];
      if (dist.has(n)) continue;
      if (banned.has(edgeId(c, n))) continue;
      if (goalHigh ? n >= 72 : n <= 8) { alt = d; break outer2; }
      dist.set(n, d); q.push(n);
    }
  }
  const detour = alt < 0 ? 31 : Math.min(alt - len, 31);
  return (len << 5) | detour;
}

const buf = new Int32Array(256);
const N_GAMES = 250;
for (let g = 0; g < N_GAMES; g++) {
  const rand = rng(g * 977 + 31);
  const pos = new Position();
  const maxLen = 20 + ((rand() * 80) | 0);
  for (let step = 0; step < maxLen; step++) {
    if (pos.winner() !== -1) break;
    const n = pos.legalMoves(buf, true);
    if (n === 0) break;
    let m = -1;
    if (rand() < 0.55) {
      const walls = [];
      for (let i = 0; i < n; i++) if (isWallMove(buf[i])) walls.push(buf[i]);
      if (walls.length) m = walls[(rand() * walls.length) | 0];
    }
    if (m < 0) m = buf[(rand() * n) | 0];
    pos.doMove(m);

    // ---- scenario A: cold position vs reference implementation ----
    const cold = pos.clone();
    for (let p = 0; p < 2; p++) {
      const eng = cold.pathFragility(p);
      const ref = refFrag(cold, p);
      check(eng === ref,
        `g${g} s${step} A: player ${p} engine=${eng} (len=${eng >> 5},det=${eng & 31}) ref=${ref} (len=${ref >> 5},det=${ref & 31})`);
    }

    // ---- scenario B: warm caches + churn, then fragility, vs cold clone ----
    // warm the path caches the way search does
    pos.candidateWalls(buf, 0, true);
    // do/undo a random legal move (invalidation must be sufficient)
    const n2 = pos.legalMoves(buf, true);
    if (n2 > 0) {
      const m2 = buf[(rand() * n2) | 0];
      pos.doMove(m2);
      pos.pathFragility(0); pos.pathFragility(1);  // fill caches at child
      pos.undoMove(m2);
    }
    // _generate-style pawn hack (mutate pawn directly, invalidate, restore)
    const side = pos.turn;
    const from = pos.pawn[side];
    const pm = new Int32Array(8);
    const npm = pos.pawnMoves(pm, 0);
    if (npm > 0) {
      pos.pawn[side] = pm[0];
      pos._invalidate();
      pos.distance(side);
      pos.pawn[side] = from;
      pos._invalidate();
    }
    // back-to-back both players, twice, must be stable and equal cold values
    const cold2 = pos.clone();
    const f0a = pos.pathFragility(0), f1a = pos.pathFragility(1);
    const f0b = pos.pathFragility(0), f1b = pos.pathFragility(1);
    check(f0a === f0b && f1a === f1b, `g${g} s${step} B: fragility not idempotent (${f0a},${f0b}) (${f1a},${f1b})`);
    check(f0a === cold2.pathFragility(0), `g${g} s${step} B: warm f0=${f0a} != cold=${cold2.pathFragility(0)}`);
    check(f1a === cold2.pathFragility(1), `g${g} s${step} B: warm f1=${f1a} != cold=${cold2.pathFragility(1)}`);
    // and against the reference
    check(f0a === refFrag(pos, 0), `g${g} s${step} B: warm f0=${f0a} != ref=${refFrag(pos, 0)}`);
    check(f1a === refFrag(pos, 1), `g${g} s${step} B: warm f1=${f1a} != ref=${refFrag(pos, 1)}`);

    // ---- scenario C: interleave wallLegal (temporary carve) then fragility ----
    for (let orient = 0; orient < 2; orient++)
      for (let slot = 0; slot < 64; slot += 7) pos.wallLegal(orient, slot);
    check(pos.pathFragility(0) === refFrag(pos, 0), `g${g} s${step} C: f0 after wallLegal churn`);
    check(pos.pathFragility(1) === refFrag(pos, 1), `g${g} s${step} C: f1 after wallLegal churn`);
  }
}
console.log(fails === 0 ? `OK — ${N_GAMES} games, pathFragility matches reference under all scenarios` : `${fails} FAILURES`);
process.exit(fails ? 1 : 0);
