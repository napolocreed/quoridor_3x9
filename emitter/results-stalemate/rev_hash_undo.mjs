/**
 * rev_hash_undo.mjs — adversarial check of wallLo/wallHi (and hashLo/hashHi)
 * maintenance across doMove/undoMove/clone/reset/_rehash.
 *
 * Plays random legal move sequences, at every step asserts that the
 * incrementally-maintained signatures match a from-scratch _rehash()
 * recomputation (done on an isolated copy so the original's fields are
 * untouched), then unwinds in reverse and asserts the position returns
 * bit-for-bit to its initial state.
 */
import { Position, isWallMove } from '../engine.js';

function rng(seed) {
  let s = seed >>> 0;
  return () => {
    s ^= s << 13; s >>>= 0; s ^= s >> 17; s ^= s << 5; s >>>= 0;
    return s / 4294967296;
  };
}

let fails = 0;
function check(cond, label) {
  if (!cond) { fails++; console.log('FAIL: ' + label); }
}

function snapshot(p) {
  return {
    hashLo: p.hashLo, hashHi: p.hashHi, wallLo: p.wallLo, wallHi: p.wallHi,
    adj: Array.from(p.adj).join(','), slot: Array.from(p.slot).join(','),
    pawn: [p.pawn[0], p.pawn[1]], left: [p.left[0], p.left[1]], turn: p.turn,
    dsuP: Array.from(p._dsuP).join(','), dsuN: Array.from(p._dsuN).join(','),
  };
}

// recompute signatures from scratch without touching p: use a scratch Position,
// overwrite its state, call _rehash, read fields.
const scratch = new Position();
function rehashed(p) {
  scratch.adj.set(p.adj); scratch.slot.set(p.slot);
  scratch.pawn.set(p.pawn); scratch.left.set(p.left);
  scratch.turn = p.turn;
  scratch._rehash();
  return { hashLo: scratch.hashLo, hashHi: scratch.hashHi, wallLo: scratch.wallLo, wallHi: scratch.wallHi };
}

const buf = new Int32Array(256);
const N_GAMES = 300;
for (let g = 0; g < N_GAMES; g++) {
  const rand = rng(g * 2654435761 + 12345);
  const pos = new Position();
  const init = snapshot(pos);
  const played = [];
  const maxLen = 40 + ((rand() * 60) | 0);
  for (let step = 0; step < maxLen; step++) {
    if (pos.winner() !== -1) break;
    const n = pos.legalMoves(buf, true);
    if (n === 0) break;
    // bias towards walls so signatures actually move
    let m = -1;
    if (rand() < 0.6) {
      const wallIdx = [];
      for (let i = 0; i < n; i++) if (isWallMove(buf[i])) wallIdx.push(buf[i]);
      if (wallIdx.length) m = wallIdx[(rand() * wallIdx.length) | 0];
    }
    if (m < 0) m = buf[(rand() * n) | 0];
    pos.doMove(m);
    played.push(m);

    const r = rehashed(pos);
    check(pos.hashLo === r.hashLo && pos.hashHi === r.hashHi,
      `g${g} step${step}: hash mismatch inc=(${pos.hashLo},${pos.hashHi}) rehash=(${r.hashLo},${r.hashHi})`);
    check(pos.wallLo === r.wallLo && pos.wallHi === r.wallHi,
      `g${g} step${step}: wall sig mismatch inc=(${pos.wallLo},${pos.wallHi}) rehash=(${r.wallLo},${r.wallHi})`);

    // clone must carry identical signatures and state
    const c = pos.clone();
    check(c.hashLo === pos.hashLo && c.hashHi === pos.hashHi &&
          c.wallLo === pos.wallLo && c.wallHi === pos.wallHi,
      `g${g} step${step}: clone signature mismatch`);
    const rc = rehashed(c);
    check(c.wallLo === rc.wallLo && c.wallHi === rc.wallHi,
      `g${g} step${step}: clone wall sig vs rehash mismatch`);
  }
  // unwind everything, checking signatures at each undo
  for (let i = played.length - 1; i >= 0; i--) {
    pos.undoMove(played[i]);
    const r = rehashed(pos);
    check(pos.hashLo === r.hashLo && pos.hashHi === r.hashHi,
      `g${g} undo@${i}: hash mismatch after undo`);
    check(pos.wallLo === r.wallLo && pos.wallHi === r.wallHi,
      `g${g} undo@${i}: wall sig mismatch after undo`);
  }
  const fin = snapshot(pos);
  for (const k of Object.keys(init)) {
    check(JSON.stringify(init[k]) === JSON.stringify(fin[k]),
      `g${g}: field ${k} not restored after full unwind`);
  }
  // reset must return to pristine
  pos.reset();
  const rst = snapshot(pos);
  const pristine = snapshot(new Position());
  for (const k of Object.keys(pristine)) {
    check(JSON.stringify(pristine[k]) === JSON.stringify(rst[k]),
      `g${g}: reset field ${k} differs from fresh Position`);
  }
}
console.log(fails === 0 ? `OK — ${N_GAMES} random games, all signature invariants held` : `${fails} FAILURES`);
process.exit(fails ? 1 : 0);
