/**
 * Adversarial attack on Lemma 1: forward BFS over all REACHABLE states of
 * small variants (including W=1/W=2 topologies with wall stock), checking with
 * an INDEPENDENT flood-fill that each pawn's wall-connectivity component
 * contains a cell of its own goal row. Any violation is fatal for Lemma 1.
 * Also counts non-terminal reachable states with zero pawn moves (fatal for
 * the theorem when H >= 3) and full stalemates.
 *
 * Usage: node hunt_reach.mjs W H walls
 */
import { makeEngine } from '../qref.mjs';

const [W, H, walls] = process.argv.slice(2).map(Number);
const eng = makeEngine(W, H, walls);
const { N, row, blocked } = eng;

/* independent connectivity: flood fill over unblocked orthogonal edges */
function componentHasRow(hw, vw, start, goalRow) {
  const seen = new Uint8Array(N);
  const stack = [start];
  seen[start] = 1;
  while (stack.length) {
    const x = stack.pop();
    if (row(x) === goalRow) return true;
    const r = row(x), c = x % W;
    const nbrs = [];
    if (r > 0) nbrs.push(x - W);
    if (r < H - 1) nbrs.push(x + W);
    if (c > 0) nbrs.push(x - 1);
    if (c < W - 1) nbrs.push(x + 1);
    for (const n of nbrs) {
      if (!seen[n] && !blocked(hw, vw, x, n)) { seen[n] = 1; stack.push(n); }
    }
  }
  return false;
}

const key = (s) => `${s.hw},${s.vw},${s.p[0]},${s.p[1]},${s.walls[0]},${s.walls[1]},${s.turn}`;
const t0 = Date.now();
let frontier = [eng.initial()];
const seen = new Set([key(frontier[0])]);
let ply = 0, total = 0, terminals = 0, lemma1Violations = 0, zeroPawn = 0, fullStale = 0;
const violExamples = [], staleExamples = [];
while (frontier.length) {
  const next = [];
  for (const st of frontier) {
    total++;
    if (eng.terminal(st) !== -1) { terminals++; continue; }
    if (!componentHasRow(st.hw, st.vw, st.p[0], 0) ||
        !componentHasRow(st.hw, st.vw, st.p[1], H - 1)) {
      lemma1Violations++;
      if (violExamples.length < 3) violExamples.push({ ply, ...st });
    }
    const kids = eng.children(st);
    if (!kids.some(([l]) => l[0] === 'P')) {
      zeroPawn++;
      if (kids.length === 0) {
        fullStale++;
        if (staleExamples.length < 3) staleExamples.push({ ply, ...st });
      }
    }
    for (const [, c] of kids) {
      const k = key(c);
      if (!seen.has(k)) { seen.add(k); next.push(c); }
    }
  }
  frontier = next;
  ply++;
}
console.log(JSON.stringify({
  W, H, walls, reachable: total, terminals,
  lemma1Violations, violExamples,
  zeroPawnMoveNonTerminal: zeroPawn, fullStalemates: fullStale, staleExamples,
  maxPly: ply - 1, seconds: +((Date.now() - t0) / 1000).toFixed(2)
}));
process.exit(lemma1Violations || (zeroPawn && H >= 3) ? 4 : 0);
