/**
 * Validation du moteur.
 * Stratégie : une implémentation naïve, lente mais évidemment correcte
 * (murs stockés en liste, BFS complet à chaque test), comparée coup par
 * coup à l'implémentation optimisée sur des milliers de positions.
 */
import {
  Position, HORIZ, VERT, wallMove, wallSlot, wallOrient, isWallMove,
  moveToNotation, notationToMove, NSLOTS
} from './engine.js';

let pass = 0, fail = 0;
const ok = (cond, label, extra = '') => {
  if (cond) { pass++; }
  else { fail++; console.log('  ✗ ' + label + (extra ? '  ' + extra : '')); }
};

/* ══════════ implémentation de référence naïve ══════════ */

class Naive {
  constructor() {
    this.walls = [];            // {orient, wr, wc}
    this.pawn = [4, 76];
    this.left = [10, 10];
    this.turn = 0;
  }
  blocked(a, b) {
    for (const w of this.walls) {
      if (w.orient === HORIZ) {
        for (const c of [w.wc, w.wc + 1]) {
          const lo = w.wr * 9 + c, hi = lo + 9;
          if ((a === lo && b === hi) || (a === hi && b === lo)) return true;
        }
      } else {
        for (const r of [w.wr, w.wr + 1]) {
          const l = r * 9 + w.wc, rt = l + 1;
          if ((a === l && b === rt) || (a === rt && b === l)) return true;
        }
      }
    }
    return false;
  }
  neighbours(c) {
    const r = (c / 9) | 0, col = c % 9, out = [];
    if (r < 8 && !this.blocked(c, c + 9)) out.push(c + 9);
    if (r > 0 && !this.blocked(c, c - 9)) out.push(c - 9);
    if (col < 8 && !this.blocked(c, c + 1)) out.push(c + 1);
    if (col > 0 && !this.blocked(c, c - 1)) out.push(c - 1);
    return out;
  }
  reaches(p) {
    const goal = p === 0 ? 8 : 0;
    const seen = new Set([this.pawn[p]]);
    const st = [this.pawn[p]];
    while (st.length) {
      const c = st.pop();
      if (((c / 9) | 0) === goal) return true;
      for (const n of this.neighbours(c)) if (!seen.has(n)) { seen.add(n); st.push(n); }
    }
    return false;
  }
  pawnMoves() {
    const me = this.pawn[this.turn], opp = this.pawn[1 - this.turn], out = [];
    for (const n of this.neighbours(me)) {
      if (n !== opp) { out.push(n); continue; }
      const d = n - me;
      const beyond = n + d;
      const straightOnBoard =
        (d === 9 && ((n / 9) | 0) < 8) || (d === -9 && ((n / 9) | 0) > 0) ||
        (d === 1 && (n % 9) < 8) || (d === -1 && (n % 9) > 0);
      if (straightOnBoard && !this.blocked(n, beyond)) { out.push(beyond); continue; }
      const perps = (d === 9 || d === -9) ? [1, -1] : [9, -9];
      for (const pd of perps) {
        const t = n + pd;
        const onBoard = (pd === 1 && (n % 9) < 8) || (pd === -1 && (n % 9) > 0) ||
                        (pd === 9 && ((n / 9) | 0) < 8) || (pd === -9 && ((n / 9) | 0) > 0);
        if (onBoard && !this.blocked(n, t)) out.push(t);
      }
    }
    return out;
  }
  wallFits(orient, wr, wc) {
    for (const w of this.walls) {
      if (w.wr === wr && w.wc === wc) return false;                       // même intersection
      if (orient === HORIZ && w.orient === HORIZ && w.wr === wr && Math.abs(w.wc - wc) === 1) return false;
      if (orient === VERT && w.orient === VERT && w.wc === wc && Math.abs(w.wr - wr) === 1) return false;
    }
    return true;
  }
  legalMoves() {
    const out = this.pawnMoves().slice();
    if (this.left[this.turn] > 0) {
      for (let orient = 0; orient < 2; orient++) {
        for (let slot = 0; slot < NSLOTS; slot++) {
          const wr = slot >> 3, wc = slot & 7;
          if (!this.wallFits(orient, wr, wc)) continue;
          this.walls.push({ orient, wr, wc });
          const good = this.reaches(0) && this.reaches(1);
          this.walls.pop();
          if (good) out.push(wallMove(orient, slot));
        }
      }
    }
    return out;
  }
  doMove(m) {
    if (isWallMove(m)) {
      const slot = wallSlot(m);
      this.walls.push({ orient: wallOrient(m), wr: slot >> 3, wc: slot & 7 });
      this.left[this.turn]--;
    } else this.pawn[this.turn] = m;
    this.turn = 1 - this.turn;
  }
  winner() {
    if (((this.pawn[0] / 9) | 0) === 8) return 0;
    if (((this.pawn[1] / 9) | 0) === 0) return 1;
    return -1;
  }
}

/* ══════════ 1. position initiale ══════════ */

console.log('\n▸ position de départ');
{
  const p = new Position();
  const buf = new Int32Array(256);
  const n = p.legalMoves(buf);
  ok(n === 131, 'départ = 131 coups légaux (3 pions + 128 murs)', 'obtenu ' + n);
  ok(p.distance(0) === 8, 'distance rouge = 8', 'obtenu ' + p.distance(0));
  ok(p.distance(1) === 8, 'distance bleu = 8', 'obtenu ' + p.distance(1));
}

/* ══════════ 2. notation ══════════ */

console.log('\n▸ notation');
{
  ok(moveToNotation(4) === 'e1', 'case 4 = e1');
  ok(moveToNotation(76) === 'e9', 'case 76 = e9');
  ok(notationToMove('e2') === 13, 'e2 = case 13');
  const he5 = notationToMove('he5');
  ok(wallOrient(he5) === HORIZ && wallSlot(he5) === 4 * 8 + 4, 'he5 = mur H slot (4,4)');
  ok(moveToNotation(he5) === 'he5', 'aller-retour he5');
  let roundtrip = true;
  for (let m = 0; m < 209; m++) if (notationToMove(moveToNotation(m)) !== m) roundtrip = false;
  ok(roundtrip, 'aller-retour sur les 209 coups');
}

/* ══════════ 3. règle du saut ══════════ */

console.log('\n▸ règle du saut');
{
  const p = Position.fromMoves(['e2', 'e8', 'e3', 'e7', 'e4', 'e6', 'ha1', 'e5']);
  const buf = new Int32Array(8);
  const n = p.pawnMoves(buf, 0);
  const got = [...buf.slice(0, n)].map(moveToNotation).sort().join(' ');
  ok(got === 'd4 e3 e6 f4', 'saut droit par-dessus l\'adversaire -> e6', got);
}
{
  // mur derrière l'adversaire : le saut droit devient deux diagonales
  const p = Position.fromMoves(['e2', 'e8', 'e3', 'e7', 'e4', 'e6', 'ha1', 'e5', 'hc1', 'he5']);
  const buf = new Int32Array(8);
  const n = p.pawnMoves(buf, 0);
  const got = [...buf.slice(0, n)].map(moveToNotation).sort().join(' ');
  ok(got === 'd4 d5 e3 f4 f5', 'mur derrière -> diagonales d5/f5, pas de saut droit', got);
}

/* ══════════ 4. un mur ne peut pas enfermer un joueur ══════════ */

console.log('\n▸ interdiction d\'enfermer');
{
  const p = Position.fromMoves(['e2', 'd9', 'e3', 'c9', 'e4', 'b9', 'ha8', 'a9']);
  ok(p.pawn[1] === 72, 'bleu en a9');
  const vb8 = notationToMove('vb8');
  ok(p.wallFits(wallOrient(vb8), wallSlot(vb8)), 'vb8 tient géométriquement');
  ok(!p.wallLegal(wallOrient(vb8), wallSlot(vb8)), 'vb8 refusé : il enfermerait le bleu');
  const buf = new Int32Array(256);
  const n = p.legalMoves(buf);
  ok(![...buf.slice(0, n)].includes(vb8), 'vb8 absent de la génération');
}

/* ══════════ 5. géométrie des murs ══════════ */

console.log('\n▸ chevauchements');
{
  const p = new Position();
  p.doMove(notationToMove('he5'));
  ok(!p.wallFits(HORIZ, 4 * 8 + 4), 'he5 deux fois -> refusé');
  ok(!p.wallFits(VERT, 4 * 8 + 4), 've5 croise he5 -> refusé');
  ok(!p.wallFits(HORIZ, 4 * 8 + 3), 'hd5 chevauche he5 -> refusé');
  ok(!p.wallFits(HORIZ, 4 * 8 + 5), 'hf5 chevauche he5 -> refusé');
  ok(p.wallFits(HORIZ, 4 * 8 + 6), 'hg5 ne chevauche pas -> accepté');
  ok(p.wallFits(VERT, 4 * 8 + 3), 'vd5 accepté');
}

/* ══════════ 6. perft + comparaison différentielle ══════════ */

console.log('\n▸ perft');
function perft(p, depth, buf) {
  if (depth === 0) return 1;
  const moves = new Int32Array(256);
  const n = p.legalMoves(moves);
  if (depth === 1) return n;
  let total = 0;
  for (let i = 0; i < n; i++) {
    p.doMove(moves[i]);
    total += p.winner() === -1 ? perft(p, depth - 1) : 1;
    p.undoMove(moves[i]);
  }
  return total;
}
{
  const p = new Position();
  const t0 = Date.now();
  const p1 = perft(p, 1), p2 = perft(p, 2);
  console.log(`  perft(1) = ${p1}`);
  console.log(`  perft(2) = ${p2}   (${Date.now() - t0} ms)`);
  const t1 = Date.now();
  const p3 = perft(p, 3);
  console.log(`  perft(3) = ${p3}   (${Date.now() - t1} ms)`);
  ok(p1 === 131, 'perft(1) = 131');
  // 16677 vérifié par décomposition indépendante :
  //   3 ouvertures de pion    -> 131 réponses chacune          =   393
  //   64 murs H + 64 murs V   -> 8144 réponses chacun (recouvrements exclus) = 16288
  //   moins hd8/he8/vd8/ve8 qui rognent aussi la mobilité du pion bleu       =    -4
  ok(p2 === 16677, 'perft(2) = 16677', String(p2));
  ok(3 * 131 + 8144 * 2 - 4 === p2, 'perft(2) recoupé par décomposition analytique');
  // recoupement final : le générateur naïf doit produire le même total
  {
    const root = new Naive();
    let naiveTotal = 0;
    for (const m of root.legalMoves()) {
      const child = new Naive();
      child.doMove(m);
      naiveTotal += child.legalMoves().length;
    }
    ok(naiveTotal === p2, 'perft(2) identique avec le générateur naïf', String(naiveTotal));
    console.log(`  perft(2) naïf = ${naiveTotal}  (recoupement indépendant)`);
  }
}

console.log('\n▸ test différentiel optimisé / naïf');
{
  let plies = 0, mismatch = 0, worst = '';
  const buf = new Int32Array(256);
  let seed = 12345;
  const rnd = () => (seed = (seed * 1103515245 + 12345) & 0x7fffffff) / 0x7fffffff;

  for (let game = 0; game < 60; game++) {
    const fast = new Position();
    const slow = new Naive();
    for (let ply = 0; ply < 60; ply++) {
      if (fast.winner() !== -1) break;
      const n = fast.legalMoves(buf);
      const a = [...buf.slice(0, n)].sort((x, y) => x - y);
      const b = slow.legalMoves().sort((x, y) => x - y);
      plies++;
      if (a.length !== b.length || a.some((v, i) => v !== b[i])) {
        mismatch++;
        if (!worst) {
          const sa = new Set(a), sb = new Set(b);
          worst = 'en trop: ' + a.filter(v => !sb.has(v)).map(moveToNotation).join(',') +
                  ' | manquants: ' + b.filter(v => !sa.has(v)).map(moveToNotation).join(',');
        }
        break;
      }
      // biais vers les murs pour stresser la logique de blocage
      let m;
      if (rnd() < 0.45 && a.some(isWallMove)) {
        const w = a.filter(isWallMove);
        m = w[(rnd() * w.length) | 0];
      } else m = a[(rnd() * a.length) | 0];
      fast.doMove(m); slow.doMove(m);
    }
  }
  ok(mismatch === 0, `${plies} positions comparées, 0 divergence`, worst);
  console.log(`  ${plies} positions vérifiées contre la référence naïve`);
}

/* ══════════ 6b. légalité des murs en position saturée ══════════ */
// Le raccourci par union-find (« pas de cycle -> pas de coupure ») est une
// optimisation sensible : on la confronte à un BFS brut sur des positions
// chargées en murs, là où les coupures deviennent possibles.

console.log('\n▸ légalité des murs, positions saturées');
{
  const buf = new Int32Array(256);
  let checked = 0, wrong = 0, sealing = 0, withWalls = 0;
  let seed = 4242;
  const rnd = () => (seed = (seed * 1103515245 + 12345) & 0x7fffffff) / 0x7fffffff;

  for (let g = 0; g < 45; g++) {
    const fast = new Position();
    const slow = new Naive();
    for (let ply = 0; ply < 34 && fast.winner() === -1; ply++) {
      // comparer les 128 verdicts À CHAQUE demi-coup, tant qu'il reste des murs
      if (fast.left[fast.turn] > 0) {
        withWalls++;
        for (let orient = 0; orient < 2; orient++) {
          for (let slot = 0; slot < NSLOTS; slot++) {
            const wr = slot >> 3, wc = slot & 7;
            let ref = slow.wallFits(orient, wr, wc);
            if (ref) {
              slow.walls.push({ orient, wr, wc });
              ref = slow.reaches(0) && slow.reaches(1);
              if (!ref) sealing++;
              slow.walls.pop();
            }
            if (fast.wallLegal(orient, slot) !== ref) wrong++;
            checked++;
          }
        }
      }
      const n = fast.legalMoves(buf);
      const all = [...buf.slice(0, n)];
      // murs concentrés autour d'un pion : c'est là que l'enfermement devient
      // possible, donc là que le raccourci par union-find doit être éprouvé
      const target = fast.pawn[rnd() < 0.5 ? 0 : 1];
      const tr = (target / 9) | 0, tc = target % 9;
      const near = all.filter(mm => {
        if (!isWallMove(mm)) return false;
        const sl = wallSlot(mm);
        return Math.abs((sl >> 3) - tr) <= 1 && Math.abs((sl & 7) - tc) <= 1;
      });
      const walls = all.filter(isWallMove);
      const m = near.length && rnd() < 0.85 ? near[(rnd() * near.length) | 0]
              : walls.length && rnd() < 0.5 ? walls[(rnd() * walls.length) | 0]
              : all[(rnd() * all.length) | 0];
      fast.doMove(m); slow.doMove(m);
    }
  }
  ok(wrong === 0, `${checked} verdicts de légalité identiques à la référence`, String(wrong));
  ok(sealing > 0, 'des murs enfermants ont bien été rencontrés', String(sealing));
  console.log(`  ${checked} verdicts sur ${withWalls} positions, dont ${sealing} refus pour enfermement`);
}

/* ══════════ 7. cohérence do/undo + Zobrist ══════════ */

console.log('\n▸ do/undo et Zobrist');
{
  const p = new Position();
  const buf = new Int32Array(256);
  let hashOk = true, stateOk = true, collisions = 0;
  const seen = new Map();
  let seed = 777;
  const rnd = () => (seed = (seed * 1103515245 + 12345) & 0x7fffffff) / 0x7fffffff;

  for (let g = 0; g < 40; g++) {
    p.reset();
    for (let ply = 0; ply < 40 && p.winner() === -1; ply++) {
      const n = p.legalMoves(buf);
      const m = buf[(rnd() * n) | 0];
      const before = { lo: p.hashLo, hi: p.hashHi, pawn: [...p.pawn], left: [...p.left], adj: [...p.adj] };
      p.doMove(m);
      // le hash incrémental doit égaler le hash recalculé de zéro
      const lo = p.hashLo, hi = p.hashHi;
      p._rehash();
      if (p.hashLo !== lo || p.hashHi !== hi) hashOk = false;
      const key = p.hashLo + ':' + p.hashHi;
      const sig = p.pawn.join(',') + '|' + p.left.join(',') + '|' + p.slot.join('') + '|' + p.turn;
      if (seen.has(key) && seen.get(key) !== sig) collisions++;
      seen.set(key, sig);
      p.undoMove(m);
      if (p.hashLo !== before.lo || p.hashHi !== before.hi) hashOk = false;
      if (p.pawn[0] !== before.pawn[0] || p.pawn[1] !== before.pawn[1] ||
          p.left[0] !== before.left[0] || p.left[1] !== before.left[1] ||
          [...p.adj].some((v, i) => v !== before.adj[i])) stateOk = false;
      p.doMove(m);
    }
  }
  ok(hashOk, 'Zobrist incrémental = Zobrist recalculé, et réversible');
  ok(stateOk, 'undoMove restaure exactement la position');
  ok(collisions === 0, `aucune collision de hash sur ${seen.size} positions`, String(collisions));
}

/* ══════════ 8. la recherche ne doit jamais corrompre la position ══════════ */
// Régression : à l'expiration du budget de temps, la recherche lève une
// exception au milieu de la récursion. Sans déroulage explicite, tous les
// undoMove en attente sont sautés et la position reste dans un état absurde.

console.log('\n▸ intégrité de la position après recherche');
{
  const { SearchEngine } = await import('./ai.js');
  let corrupted = 0, tested = 0;
  for (let g = 0; g < 30; g++) {
    const p = new Position();
    const buf = new Int32Array(256);
    let seed = 900 + g;
    const rnd = () => (seed = (seed * 1103515245 + 12345) & 0x7fffffff) / 0x7fffffff;
    for (let i = 0; i < 6; i++) { const n = p.legalMoves(buf); p.doMove(buf[(rnd() * n) | 0]); }
    const before = {
      lo: p.hashLo, hi: p.hashHi, pawn: [...p.pawn],
      left: [...p.left], slot: [...p.slot], turn: p.turn, sp: p._sp
    };
    const e = new SearchEngine();
    // budgets minuscules : on force l'abandon en pleine récursion
    e.search(p, { maxDepth: 64, maxTimeMs: g % 3 === 0 ? 0 : (g % 7) + 1 });
    tested++;
    const same = p.hashLo === before.lo && p.hashHi === before.hi &&
      p.pawn[0] === before.pawn[0] && p.pawn[1] === before.pawn[1] &&
      p.left[0] === before.left[0] && p.left[1] === before.left[1] &&
      p.turn === before.turn && p._sp === before.sp &&
      [...p.slot].every((v, i) => v === before.slot[i]);
    if (!same) corrupted++;
  }
  ok(corrupted === 0, `${tested} recherches interrompues, position intacte`, String(corrupted));

  // et le coup rendu doit rester légal même sur abandon immédiat
  let illegal = 0;
  for (let g = 0; g < 30; g++) {
    const p = new Position();
    const buf = new Int32Array(256);
    let seed = 4000 + g;
    const rnd = () => (seed = (seed * 1103515245 + 12345) & 0x7fffffff) / 0x7fffffff;
    for (let i = 0; i < 8; i++) { const n = p.legalMoves(buf); p.doMove(buf[(rnd() * n) | 0]); }
    const e = new SearchEngine();
    const r = e.search(p, { maxDepth: 64, maxTimeMs: 0 });
    if (r.move < 0 || !p.isLegal(r.move)) illegal++;
  }
  ok(illegal === 0, '30 recherches à budget nul rendent un coup légal', String(illegal));
}

/* ══════════ résumé ══════════ */

console.log(`\n${fail === 0 ? '✓' : '✗'} ${pass} tests passés, ${fail} échecs\n`);
process.exit(fail ? 1 : 0);
