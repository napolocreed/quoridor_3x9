/**
 * rev_retro.mjs — adversarial cross-check of race.js RaceTable._solve.
 *
 * Independent exact solver: classic level-order retrograde analysis
 * (predecessor counters, strictly increasing distance levels) — a totally
 * different algorithm from race.js's Gauss-Seidel sweep — and using
 * Position.pawnMoves() from engine.js as the move generator (different code
 * path from RaceTable._moves). Compares the FULL value table on each config.
 *
 * Configs: empty board, serpentine corridors, jump traps, random legal walls.
 */
import { Position, notationToMove, NCELLS } from '../engine.js';
import { RaceTable } from '../race.js';
import { rng } from '../ai.js';

const IDX = (p0, p1, t) => (p0 * NCELLS + p1) * 2 + t;

/** Independent exact solve. Returns Int32Array val[] with race.js conventions. */
function solveRetro(pos) {
  const S = NCELLS * NCELLS * 2;
  const val = new Int32Array(S);          // 0 = unknown/draw
  const valid = new Uint8Array(S);
  const succ = new Array(S);              // successor state indices (non-winning moves)
  const winMove = new Uint8Array(S);      // mover has an immediate winning move
  const nMoves = new Int32Array(S);
  const buf = new Int32Array(8);

  const savedP0 = pos.pawn[0], savedP1 = pos.pawn[1], savedTurn = pos.turn;

  for (let p0 = 0; p0 < 72; p0++) {
    for (let p1 = 9; p1 < NCELLS; p1++) {
      if (p1 === p0) continue;
      for (let t = 0; t < 2; t++) {
        const s = IDX(p0, p1, t);
        valid[s] = 1;
        pos.pawn[0] = p0; pos.pawn[1] = p1; pos.turn = t; pos._invalidate();
        const n = pos.pawnMoves(buf, 0);
        nMoves[s] = n;
        const arr = [];
        for (let i = 0; i < n; i++) {
          const z = buf[i];
          if (t === 0 ? z >= 72 : z <= 8) { winMove[s] = 1; continue; }
          arr.push(t === 0 ? IDX(z, p1, 1) : IDX(p0, z, 0));
        }
        succ[s] = arr;
      }
    }
  }
  pos.pawn[0] = savedP0; pos.pawn[1] = savedP1; pos.turn = savedTurn; pos._invalidate();

  // predecessors
  const preds = new Array(S);
  for (let s = 0; s < S; s++) if (valid[s]) {
    for (const z of succ[s]) {
      if (!preds[z]) preds[z] = [];
      preds[z].push(s);
    }
  }

  const cntUnres = new Int32Array(S);   // successors not yet labeled WIN
  for (let s = 0; s < S; s++) if (valid[s]) cntUnres[s] = succ[s].length;

  // level d=1: immediate wins
  let frontierWin = [], frontierLoss = [];
  for (let s = 0; s < S; s++) if (valid[s] && winMove[s]) { val[s] = 1; frontierWin.push(s); }

  let d = 1;
  while (frontierWin.length || frontierLoss.length) {
    const nextWin = [], nextLoss = [];
    // predecessors of newly-labeled LOSS states become WIN at d+1 (min dist:
    // levels are processed in strictly increasing order)
    for (const l of frontierLoss) {
      const ps = preds[l];
      if (!ps) continue;
      for (const p of ps) {
        if (val[p] !== 0) continue;          // already labeled
        val[p] = d + 1;                       // win in d+1 (l is loss in d)
        nextWin.push(p);
      }
    }
    // wait — frontierLoss states carry dist d, frontierWin dist d.
    // predecessors of newly WIN states: decrement counters; when all succ are
    // wins (and no immediate winMove, which would have labeled it already,
    // and it is still unlabeled) -> LOSS at 1 + max succ dist = d + 1.
    for (const w of frontierWin) {
      const ps = preds[w];
      if (!ps) continue;
      for (const p of ps) {
        cntUnres[p]--;
        if (cntUnres[p] === 0 && val[p] === 0 && !winMove[p] && nMoves[p] > 0) {
          val[p] = -(d + 1);
          nextLoss.push(p);
        }
      }
    }
    frontierWin = nextWin; frontierLoss = nextLoss;
    d++;
    if (d > 20000) throw new Error('retro runaway');
  }
  return { val, valid };
}

function compare(label, pos) {
  const rt = new RaceTable(pos.adj);
  const { val, valid } = solveRetro(pos);
  let bad = 0;
  for (let p0 = 0; p0 < 72; p0++) {
    for (let p1 = 9; p1 < NCELLS; p1++) {
      if (p1 === p0) continue;
      for (let t = 0; t < 2; t++) {
        const s = IDX(p0, p1, t);
        if (!valid[s]) continue;
        if (rt.val[s] !== val[s]) {
          if (bad < 10) console.log(`  MISMATCH ${label}: p0=${p0} p1=${p1} turn=${t}  race=${rt.val[s]} retro=${val[s]}`);
          bad++;
        }
      }
    }
  }
  console.log(`${bad === 0 ? 'ok ' : 'FAIL'}  ${label}: ${bad} mismatches over all valid states`);
  return bad;
}

let totalBad = 0;

// 1. empty board
{
  const pos = new Position();
  totalBad += compare('empty board', pos);
}

// 2. serpentine corridor: rows sealed alternately left/right -> one long snake
{
  const pos = new Position();
  for (const w of ['ha1','hc1','he1','hg1']) pos.doMove(notationToMove(w));   // rows 1-2 sealed except col i
  for (const w of ['hb2','hd2','hf2','hh2']) pos.doMove(notationToMove(w));   // rows 2-3 sealed except col a
  for (const w of ['ha3','hc3','he3','hg3']) pos.doMove(notationToMove(w));   // rows 3-4 sealed except col i
  for (const w of ['hb4','hd4','hf4','hh4']) pos.doMove(notationToMove(w));   // rows 4-5 sealed except col a
  totalBad += compare('serpentine 4 levels', pos);
}

// 3. narrow vertical corridors (width-1 lanes) — head-on pawn meetings, jumps blocked sideways
{
  const pos = new Position();
  for (const w of ['va1','va3','va5','va7']) pos.doMove(notationToMove(w));
  for (const w of ['vb2','vb4','vb6','vb8']) pos.doMove(notationToMove(w));
  for (const w of ['vc1','vc3','vc5','vc7']) pos.doMove(notationToMove(w));
  totalBad += compare('vertical lanes', pos);
}

// 4. jump-trap: walls that force diagonal jumps near the goal rows
{
  const pos = new Position();
  for (const w of ['hd8','hf8','vd7','ve8']) pos.doMove(notationToMove(w));
  for (const w of ['hd1','hf1','vd1','ve1']) pos.doMove(notationToMove(w));
  totalBad += compare('jump traps near goals', pos);
}

// 5. random legal wall configs (same generator style as racetest, more seeds)
function randomWalls(seed, nWalls) {
  const r = rng(seed);
  const pos = new Position();
  const buf = new Int32Array(256);
  for (let placed = 0; placed < nWalls; ) {
    const n = pos.legalMoves(buf, true);
    const walls = [];
    for (let j = 0; j < n; j++) if (buf[j] >= 81) walls.push(buf[j]);
    if (!walls.length) break;
    pos.doMove(walls[(r() * walls.length) | 0]);
    placed++;
  }
  return pos;
}
for (let seed = 1; seed <= 12; seed++) {
  const pos = randomWalls(seed * 2654435761 >>> 0 || seed, 4 + (seed % 6));
  totalBad += compare(`random walls seed=${seed}`, pos);
}

console.log(totalBad === 0 ? '\nALL TABLES AGREE with independent retrograde solver' : `\n${totalBad} TOTAL MISMATCHES`);
process.exit(totalBad ? 1 : 0);
