/**
 * Vérificateur indépendant pour quoridor-frontier-research.
 *
 * Implémentation « clean-room » : écrite d'après docs/RULES.md et
 * docs/PROOF_SEMANTICS.md uniquement, sans lire ni réutiliser le code C++
 * du solveur ni sa référence Python. Sert de troisième implémentation,
 * structurellement séparée, pour valider :
 *   1. la génération de coups (via la sortie de frontier_dump / lazy_frontier_dump),
 *   2. les valeurs exactes (vainqueur + horizon minimal) sur petites variantes,
 *   3. l'accessibilité d'états sans coup légal (question pat/stalemate),
 *   4. le comptage des configurations de murs.
 *
 * Conventions (docs/RULES.md) :
 *   - cases (r,c), r=0 en haut ; J1 part de (H-1, ⌊W/2⌋) et vise r=0 ;
 *     J2 part de (0, ⌊W/2⌋) et vise r=H-1 ; J1 commence.
 *   - ancres de mur (r,c) ∈ [0,H-2]×[0,W-2] ; H(r,c) bloque les arêtes
 *     verticales (r,c)-(r+1,c) et (r,c+1)-(r+1,c+1) ; V(r,c) bloque
 *     (r,c)-(r,c+1) et (r+1,c)-(r+1,c+1).
 *   - un pat (aucun coup légal) est résolu selon `stalemate` :
 *       'code'  -> Win=false quel que soit le camp au trait (comportement du C++)
 *       'doc'   -> ∀ sur ensemble vide = vrai (sémantique littérale du doc)
 *
 * Usage :
 *   node qref.mjs check-dump                        < dump.jsonl
 *   node qref.mjs solve W H walls maxDepth [stalemate]
 *   node qref.mjs probe-stalemate W H walls nGames nPlies seed
 *   node qref.mjs count-configs W H cap
 */
import * as readline from 'node:readline';
import { pathToFileURL } from 'node:url';

/* ═══════════════ moteur de règles ═══════════════ */

export function makeEngine(W, H, wallsEach) {
  const N = W * H, C = W - 1, R = H - 1, S = C * R;
  const sq = (r, c) => r * W + c;
  const row = (p) => (p / W) | 0, col = (p) => p % W;

  // arête bloquée entre deux cases adjacentes a,b sous (hw,vw) ?
  function blocked(hw, vw, a, b) {
    const ra = row(a), ca = col(a), rb = row(b), cb = col(b);
    if (ca === cb) {                     // arête verticale : bloquée par un mur H
      const rr = Math.min(ra, rb);
      // H(rr,c) couvre les colonnes c et c+1 : l'arête en colonne ca est
      // bloquée par H(rr, ca) ou H(rr, ca-1)
      if (ca < C && ((hw >>> (rr * C + ca)) & 1)) return true;
      if (ca > 0 && ((hw >>> (rr * C + ca - 1)) & 1)) return true;
      return false;
    } else {                             // arête horizontale, mur V à droite/gauche
      const cc = Math.min(ca, cb);
      if (ra < R && ((vw >>> (ra * C + cc)) & 1)) return true;
      if (ra > 0 && ((vw >>> ((ra - 1) * C + cc)) & 1)) return true;
      return false;
    }
  }

  function neighbours(hw, vw, p) {
    const out = [];
    const r = row(p), c = col(p);
    if (r > 0 && !blocked(hw, vw, p, p - W)) out.push(p - W);
    if (r < H - 1 && !blocked(hw, vw, p, p + W)) out.push(p + W);
    if (c > 0 && !blocked(hw, vw, p, p - 1)) out.push(p - 1);
    if (c < W - 1 && !blocked(hw, vw, p, p + 1)) out.push(p + 1);
    return out;
  }

  /** BFS : le pion de `player` atteint-il sa rangée d'arrivée ? (les pions ne bloquent pas) */
  function reaches(hw, vw, p, player) {
    const goal = player === 0 ? 0 : H - 1;
    if (row(p) === goal) return true;
    const seen = new Set([p]);
    const st = [p];
    while (st.length) {
      const x = st.pop();
      for (const n of neighbours(hw, vw, x)) {
        if (seen.has(n)) continue;
        if (row(n) === goal) return true;
        seen.add(n); st.push(n);
      }
    }
    return false;
  }

  /** géométrie seule : l'ancre est-elle libre de recouvrement/croisement ? */
  function fits(hw, vw, ori, r, c) {
    const i = r * C + c;
    if (((hw >>> i) & 1) || ((vw >>> i) & 1)) return false;   // même ancre
    if (ori === 0) {
      if (c > 0 && ((hw >>> (i - 1)) & 1)) return false;
      if (c < C - 1 && ((hw >>> (i + 1)) & 1)) return false;
    } else {
      if (r > 0 && ((vw >>> (i - C)) & 1)) return false;
      if (r < R - 1 && ((vw >>> (i + C)) & 1)) return false;
    }
    return true;
  }

  /** tous les coups légaux, étiquetés au format du dump : P:sq, H:r:c, V:r:c */
  function children(st) {
    const { hw, vw, p, walls, turn } = st;
    const me = p[turn], opp = p[1 - turn];
    const out = [];
    // ── pion ──
    for (const n of neighbours(hw, vw, me)) {
      if (n !== opp) { out.push(['P:' + n, { ...st, p: turn ? [p[0], n] : [n, p[1]], turn: 1 - turn }]); continue; }
      const d = n - me;
      const behindOk = (() => {
        const r = row(n), c = col(n);
        if (d === -W) return r > 0 && !blocked(hw, vw, n, n - W);
        if (d === W) return r < H - 1 && !blocked(hw, vw, n, n + W);
        if (d === -1) return c > 0 && !blocked(hw, vw, n, n - 1);
        return c < W - 1 && !blocked(hw, vw, n, n + 1);
      })();
      if (behindOk) {
        const z = n + d;
        out.push(['P:' + z, { ...st, p: turn ? [p[0], z] : [z, p[1]], turn: 1 - turn }]);
      } else {
        const perp = (d === W || d === -W) ? [1, -1] : [W, -W];
        for (const pd of perp) {
          const r = row(n), c = col(n);
          const on = (pd === 1 && c < W - 1) || (pd === -1 && c > 0) ||
                     (pd === W && r < H - 1) || (pd === -W && r > 0);
          if (on && !blocked(hw, vw, n, n + pd)) {
            const z = n + pd;
            out.push(['P:' + z, { ...st, p: turn ? [p[0], z] : [z, p[1]], turn: 1 - turn }]);
          }
        }
      }
    }
    // ── murs ──
    if (walls[turn] > 0) {
      for (let ori = 0; ori < 2; ori++) {
        for (let r = 0; r < R; r++) for (let c = 0; c < C; c++) {
          if (!fits(hw, vw, ori, r, c)) continue;
          const nh = ori === 0 ? (hw | (1 << (r * C + c))) >>> 0 : hw;
          const nv = ori === 1 ? (vw | (1 << (r * C + c))) >>> 0 : vw;
          if (!reaches(nh, nv, p[0], 0) || !reaches(nh, nv, p[1], 1)) continue;
          const nw = turn ? [walls[0], walls[1] - 1] : [walls[0] - 1, walls[1]];
          out.push([(ori ? 'V:' : 'H:') + r + ':' + c,
                    { hw: nh, vw: nv, p: [...p], walls: nw, turn: 1 - turn }]);
        }
      }
    }
    return out;
  }

  const initial = () => ({
    hw: 0, vw: 0,
    p: [sq(H - 1, (W / 2) | 0), sq(0, (W / 2) | 0)],
    walls: [wallsEach, wallsEach], turn: 0
  });
  const terminal = (st) => row(st.p[0]) === 0 ? 0 : row(st.p[1]) === H - 1 ? 1 : -1;

  return { W, H, N, C, R, S, sq, row, col, children, initial, terminal, reaches, neighbours, blocked };
}

/* ═══════════════ solveur borné indépendant ═══════════════ */
/*
 * Win(s,T,d) littéral, sans symétrie ni normalisation de parité — le but est
 * l'indépendance structurelle, pas la vitesse. Mémo par faits monotones :
 * minWin[s,T] (plus petit d prouvé vrai) et maxFail[s,T] (plus grand d prouvé faux).
 */
export function makeSolver(eng, stalemate = 'code') {
  const minWin = new Map(), maxFail = new Map();
  let nodes = 0, stalemates = 0;

  // clé compacte : suppose S<=12 (petites variantes) -> hw,vw sur 12 bits chacun
  const key = (st, T) =>
    `${st.hw},${st.vw},${st.p[0]},${st.p[1]},${st.walls[0]},${st.walls[1]},${st.turn},${T}`;

  function win(st, T, d) {
    nodes++;
    const t = eng.terminal(st);
    if (t !== -1) return t === T;
    if (d <= 0) return false;
    const k = key(st, T);
    const mw = minWin.get(k);
    if (mw !== undefined && d >= mw) return true;
    const mf = maxFail.get(k);
    if (mf !== undefined && d <= mf) return false;
    const kids = eng.children(st);
    let res;
    if (kids.length === 0) { stalemates++; res = stalemate === 'doc' ? st.turn !== T : false; }
    else if (st.turn === T) {
      res = false;
      for (const [, c] of kids) if (win(c, T, d - 1)) { res = true; break; }
    } else {
      res = true;
      for (const [, c] of kids) if (!win(c, T, d - 1)) { res = false; break; }
    }
    if (res) { if (mw === undefined || d < mw) minWin.set(k, d); }
    else { if (mf === undefined || d > mf) maxFail.set(k, d); }
    return res;
  }
  return { win, stats: () => ({ nodes, states: minWin.size + maxFail.size, stalemates }) };
}

/* ═══════════════ commandes ═══════════════ */

const isMain = process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href;
const [, , cmd, ...args] = process.argv;

if (!isMain) {
  /* importé comme bibliothèque : ne pas exécuter la CLI */
} else if (cmd === 'check-dump') {
  // lit le JSONL de frontier_dump / lazy_frontier_dump et recompare les coups
  const rl = readline.createInterface({ input: process.stdin });
  let engines = new Map(), checked = 0, bad = 0, firstBad = null;
  const W = +args[0], H = +args[1], walls = +args[2];
  const eng = makeEngine(W, H, walls);
  rl.on('line', (line) => {
    line = line.trim();
    if (!line.startsWith('{')) return;
    const d = JSON.parse(line);
    const st = { hw: Number(d.hw), vw: Number(d.vw), p: [d.p1, d.p2], walls: [d.r1, d.r2], turn: d.turn };
    const mine = eng.children(st).map(([l]) => l).sort();
    const theirs = [...d.moves].sort();
    checked++;
    if (mine.length !== theirs.length || mine.some((v, i) => v !== theirs[i])) {
      bad++;
      if (!firstBad) firstBad = { state: d, mine, theirs };
    }
  });
  rl.on('close', () => {
    console.log(JSON.stringify({ checked, divergences: bad, firstBad }, null, bad ? 1 : 0));
    process.exit(bad ? 1 : 0);
  });

} else if (cmd === 'solve') {
  const [W, H, walls, maxD, mode] = [+args[0], +args[1], +args[2], +args[3], args[4] || 'code'];
  const eng = makeEngine(W, H, walls);
  const sol = makeSolver(eng, mode);
  const root = eng.initial();
  const t0 = Date.now();
  let out = null;
  outer:
  for (let d = 1; d <= maxD; d++) {
    for (const T of [0, 1]) {
      if (sol.win(root, T, d)) { out = { winner: T + 1, depth: d }; break outer; }
    }
  }
  const st = sol.stats();
  console.log(JSON.stringify({
    width: W, height: H, walls, stalemateMode: mode,
    ...(out ?? { winner: 0, depth: -1, note: 'non résolu à cette profondeur' }),
    nodes: st.nodes, memo: st.states, stalematesSeen: st.stalemates,
    seconds: +((Date.now() - t0) / 1000).toFixed(2)
  }));

} else if (cmd === 'probe-stalemate') {
  // parties aléatoires profondes : rencontre-t-on des états sans coup légal ?
  const [W, H, walls, games, plies, seed] = args.map(Number);
  const eng = makeEngine(W, H, walls);
  let s = (seed >>> 0) || 1;
  const rnd = () => { s ^= s << 13; s >>>= 0; s ^= s >> 17; s ^= s << 5; s >>>= 0; return s / 4294967296; };
  let zero = 0, visited = 0, examples = [];
  for (let g = 0; g < games; g++) {
    let st = eng.initial();
    for (let ply = 0; ply < plies; ply++) {
      if (eng.terminal(st) !== -1) break;
      const kids = eng.children(st);
      visited++;
      if (kids.length === 0) {
        zero++;
        if (examples.length < 3) examples.push({ ply, ...st });
        break;
      }
      // biais mur pour saturer le plateau (c'est là que le pat peut naître)
      const wallKids = kids.filter(([l]) => l[0] !== 'P');
      const pick = wallKids.length && rnd() < 0.8 ? wallKids : kids;
      st = pick[(rnd() * pick.length) | 0][1];
    }
  }
  console.log(JSON.stringify({ width: W, height: H, walls, games, statesVisited: visited, zeroMoveStates: zero, examples }));

} else if (cmd === 'count-configs') {
  // comptage indépendant des configurations géométriques de murs, par
  // programmation dynamique ligne à ligne (états d'une ligne d'ancres ×
  // contrainte V-V verticale × plafond de murs)
  const [W, H, cap] = args.map(Number);
  const C = W - 1, R = H - 1;
  const rowStates = [];
  const total = 3 ** C;
  for (let x = 0; x < total; x++) {
    let y = x; const a = [];
    for (let c = 0; c < C; c++) { a.push(y % 3); y = (y / 3) | 0; }
    let ok = true;
    for (let c = 0; c + 1 < C; c++) if (a[c] === 1 && a[c + 1] === 1) ok = false;   // H-H adjacents
    if (!ok) continue;
    let vmask = 0, count = 0;
    for (let c = 0; c < C; c++) { if (a[c]) count++; if (a[c] === 2) vmask |= 1 << c; }
    rowStates.push({ vmask, count });
  }
  // dp[vmaskPrécédent][nbMursPosés] -> nombre de préfixes
  let dp = new Map([[0, new Map([[0, 1n]])]]);
  for (let r = 0; r < R; r++) {
    const nx = new Map();
    for (const [pv, byCount] of dp) {
      for (const st of rowStates) {
        if (pv & st.vmask) continue;                    // V au-dessus de V
        for (const [k, v] of byCount) {
          const nk = k + st.count;
          if (nk > cap) continue;
          if (!nx.has(st.vmask)) nx.set(st.vmask, new Map());
          const m = nx.get(st.vmask);
          m.set(nk, (m.get(nk) ?? 0n) + v);
        }
      }
    }
    dp = nx;
  }
  let sum = 0n;
  for (const [, byCount] of dp) for (const [, v] of byCount) sum += v;
  console.log(JSON.stringify({ width: W, height: H, cap, configs: sum.toString() }));

} else {
  console.log('commandes : check-dump | solve | probe-stalemate | count-configs');
  process.exit(2);
}
