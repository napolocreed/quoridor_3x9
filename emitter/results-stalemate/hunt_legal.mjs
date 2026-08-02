/**
 * Adversarial counterexample hunt over the LEGAL superset, for variants NOT in
 * the main battery: single-column (W=1), two-column (W=2), and wide-short
 * boards. Independent of qscan.mjs: own geometry check, own pawn-move
 * generator written directly from RULES.md, cross-checked against
 * eng.children() on every enumerated state.
 *
 * A "legal non-terminal" state: geometrically legal wall config, pawns on
 * distinct cells, each pawn wall-connected to its own goal row, p1 not on
 * row 0, p2 not on row H-1.  Any such state with zero pawn moves for the
 * player to move refutes the theorem when H >= 3.
 *
 * Usage: node hunt_legal.mjs W H
 */
import { makeEngine } from '../qref.mjs';

const W = +process.argv[2], H = +process.argv[3];
const eng = makeEngine(W, H, 0);
const { C, R, S, N, row, col, blocked, reaches } = eng;
if (2 * S > 26) { console.log(JSON.stringify({ W, H, error: 'too big' })); process.exit(3); }

/* my own geometric legality, from RULES.md:
   - anchors (r,c) in [0,R-1]x[0,C-1] for each orientation
   - same anchor cannot hold two walls (either orientation)  -> no hw&vw, and
     within one orientation a bit is a single wall anyway
   - overlap of parallel neighbours: H(r,c) and H(r,c±1) share a segment;
     V(r,c) and V(r±1,c) share a segment. */
function geomOK(hw, vw) {
  if (hw & vw) return false;
  for (let r = 0; r < R; r++)
    for (let c = 0; c + 1 < C; c++) {
      const i = r * C + c;
      if (((hw >>> i) & 1) && ((hw >>> (i + 1)) & 1)) return false;
    }
  for (let r = 0; r + 1 < R; r++)
    for (let c = 0; c < C; c++) {
      const i = r * C + c;
      if (((vw >>> i) & 1) && ((vw >>> (i + C)) & 1)) return false;
    }
  return true;
}

/* my own pawn-move generator, written from RULES.md sections "Pawn moves". */
function myPawnMoves(hw, vw, me, opp) {
  const out = [];
  const r = row(me), c = col(me);
  const dirs = [];
  if (r > 0) dirs.push(-W);
  if (r < H - 1) dirs.push(W);
  if (c > 0) dirs.push(-1);
  if (c < W - 1) dirs.push(1);
  for (const d of dirs) {
    const n = me + d;
    if (blocked(hw, vw, me, n)) continue;
    if (n !== opp) { out.push(n); continue; }
    // opponent occupies n: try straight jump
    const rn = row(n), cn = col(n);
    const behindIn =
      (d === -W && rn > 0) || (d === W && rn < H - 1) ||
      (d === -1 && cn > 0) || (d === 1 && cn < W - 1);
    if (behindIn && !blocked(hw, vw, n, n + d)) { out.push(n + d); continue; }
    // otherwise diagonals: orthogonal neighbours of opponent, perpendicular
    for (const pd of (d === W || d === -W) ? [1, -1] : [W, -W]) {
      const zin =
        (pd === -W && rn > 0) || (pd === W && rn < H - 1) ||
        (pd === -1 && cn > 0) || (pd === 1 && cn < W - 1);
      if (zin && !blocked(hw, vw, n, n + pd)) out.push(n + pd);
    }
  }
  return out;
}

const t0 = Date.now();
let configs = 0, states = 0, zeroPawn = 0, engineMismatch = 0;
const zeroExamples = [], mismatchExamples = [];
const top = 1 << S;
for (let hw = 0; hw < top; hw++) {
  for (let vw = 0; vw < top; vw++) {
    if (!geomOK(hw, vw)) continue;
    configs++;
    const ok1 = [], ok2 = [];
    for (let p = 0; p < N; p++) {
      ok1.push(reaches(hw, vw, p, 0));
      ok2.push(reaches(hw, vw, p, 1));
    }
    for (let p1 = 0; p1 < N; p1++) {
      if (row(p1) === 0 || !ok1[p1]) continue;
      for (let p2 = 0; p2 < N; p2++) {
        if (p2 === p1 || row(p2) === H - 1 || !ok2[p2]) continue;
        for (let turn = 0; turn < 2; turn++) {
          states++;
          const me = turn === 0 ? p1 : p2, opp = turn === 0 ? p2 : p1;
          const mine = myPawnMoves(hw, vw, me, opp);
          // cross-check against the engine (walls 0 -> pawn moves only)
          const st = { hw, vw, p: [p1, p2], walls: [0, 0], turn };
          const theirs = eng.children(st).map(([l]) => +l.slice(2)).sort((a, b) => a - b);
          const m2 = [...mine].sort((a, b) => a - b);
          if (m2.length !== theirs.length || m2.some((v, i) => v !== theirs[i])) {
            engineMismatch++;
            if (mismatchExamples.length < 3) mismatchExamples.push({ hw, vw, p1, p2, turn, mine: m2, engine: theirs });
          }
          if (mine.length === 0) {
            zeroPawn++;
            if (zeroExamples.length < 5) zeroExamples.push({ hw, vw, p1, p2, turn });
          }
        }
      }
    }
  }
}
console.log(JSON.stringify({
  W, H, configs, legalNonTerminalStates: states,
  zeroPawnMoveStates: zeroPawn, zeroExamples,
  engineMismatch, mismatchExamples,
  seconds: +((Date.now() - t0) / 1000).toFixed(2)
}));
process.exit(zeroPawn && H >= 3 ? 4 : 0);
