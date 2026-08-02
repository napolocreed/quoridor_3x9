/**
 * Énumération exhaustive des états atteignables — vérification mécanique du
 * théorème de pat (STALEMATE_THEOREM.md).
 *
 * Réutilise le moteur clean-room de qref.mjs. Pour chaque état atteignable
 * depuis la position initiale (BFS avant, plis minimaux) :
 *   - vérifie l'invariant du Lemme 1 (chaque pion connecté à sa rangée but) ;
 *   - compte les coups de pion légaux ; signale tout état non terminal à
 *     zéro coup de pion, et tout état à zéro coup légal (pat complet) ;
 *   - conserve les premiers exemples de pat au pli minimal.
 *
 * Usage :
 *   node qscan.mjs scan W H walls [capStates]
 *   node qscan.mjs solve-both W H walls maxDepth     # H=2 : les deux conventions
 */
import { makeEngine, makeSolver } from './qref.mjs';

const [, , cmd, ...args] = process.argv;

function stKey(st) {
  return `${st.hw},${st.vw},${st.p[0]},${st.p[1]},${st.walls[0]},${st.walls[1]},${st.turn}`;
}

if (cmd === 'scan') {
  const [W, H, walls] = args.map(Number);
  const cap = args[3] ? Number(args[3]) : 30_000_000;
  const eng = makeEngine(W, H, walls);
  const t0 = Date.now();

  let frontier = [eng.initial()];
  const seen = new Set([stKey(frontier[0])]);
  let ply = 0;
  let total = 0, terminals = 0;
  let zeroPawnMove = 0, fullStalemate = 0, invariantViolations = 0;
  const stalemateExamples = [];
  let firstStalematePly = -1;

  while (frontier.length) {
    const next = [];
    for (const st of frontier) {
      total++;
      // Lemme 1 : les deux pions atteignent leur rangée but (les pions ne
      // bloquent pas) — vérifié sur TOUS les états atteignables, terminaux compris
      if (!eng.reaches(st.hw, st.vw, st.p[0], 0) || !eng.reaches(st.hw, st.vw, st.p[1], 1)) {
        invariantViolations++;
      }
      const t = eng.terminal(st);
      if (t !== -1) { terminals++; continue; }

      const kids = eng.children(st);
      const pawnMoves = kids.filter(([l]) => l[0] === 'P').length;
      if (pawnMoves === 0) {
        zeroPawnMove++;
        if (kids.length === 0) {
          fullStalemate++;
          if (firstStalematePly < 0) firstStalematePly = ply;
          if (stalemateExamples.length < 3) stalemateExamples.push({ ply, ...st });
        }
      }
      for (const [, c] of kids) {
        const k = stKey(c);
        if (!seen.has(k)) {
          seen.add(k);
          if (seen.size > cap) {
            console.log(JSON.stringify({ error: 'cap exceeded', cap }));
            process.exit(3);
          }
          next.push(c);
        }
      }
    }
    frontier = next;
    ply++;
  }

  console.log(JSON.stringify({
    width: W, height: H, walls,
    reachableStates: total,
    terminalStates: terminals,
    invariantViolations,
    zeroPawnMoveNonTerminal: zeroPawnMove,
    fullStalemates: fullStalemate,
    firstStalematePly,
    stalemateExamples,
    maxPlyDepth: ply - 1,
    seconds: +((Date.now() - t0) / 1000).toFixed(2)
  }));
  // codes de sortie : 4 = invariant violé ; 5 = pat trouvé alors que H>=3
  // (contredirait le théorème) ; pour H=2 trouver des pats est attendu -> 0
  if (invariantViolations) process.exit(4);
  process.exit(H >= 3 && (zeroPawnMove || fullStalemate) ? 5 : 0);

} else if (cmd === 'scan-legal') {
  /*
   * Sur-ensemble légal, même définition que frontier_dump --exhaustive :
   * toute configuration de murs géométriquement légale avec ≤ 2·walls murs
   * posés × toute paire de pions (cases distinctes, chacun connecté à sa
   * rangée but, non terminal) × toute répartition de stock cohérente × trait.
   * La reachability n'est PAS exigée : le théorème couvre ce sur-ensemble.
   */
  const [W, H, walls] = args.map(Number);
  const eng = makeEngine(W, H, walls);
  const { C, R, S, N, row } = eng;
  const t0 = Date.now();
  if (2 * S > 30) { console.log(JSON.stringify({ error: 'variante trop grande' })); process.exit(3); }

  const popcount = (x) => { let n = 0; while (x) { x &= x - 1; n++; } return n; };
  function geomOK(hw, vw) {
    if (hw & vw) return false;                                  // croisement même ancre
    for (let r = 0; r < R; r++)
      for (let c = 0; c + 1 < C; c++) {
        const i = r * C + c;
        if (((hw >>> i) & 1) && ((hw >>> (i + 1)) & 1)) return false;  // H-H adjacents
      }
    for (let r = 0; r + 1 < R; r++)
      for (let c = 0; c < C; c++) {
        const i = r * C + c;
        if (((vw >>> i) & 1) && ((vw >>> (i + C)) & 1)) return false;  // V-V adjacents
      }
    return true;
  }

  let legalStates = 0, zeroPawnMove = 0, configs = 0;
  const examples = [];
  for (let hw = 0; hw < (1 << S); hw++) {
    for (let vw = 0; vw < (1 << S); vw++) {
      if (!geomOK(hw, vw)) continue;
      const placed = popcount(hw) + popcount(vw);
      if (placed > 2 * walls) continue;
      configs++;
      const remain = 2 * walls - placed;
      const splits = Math.min(walls, remain) - Math.max(0, remain - walls) + 1;
      if (splits <= 0) continue;
      // cellules connectées à chaque rangée but
      const ok1 = [], ok2 = [];
      for (let p = 0; p < N; p++) {
        ok1.push(eng.reaches(hw, vw, p, 0));
        ok2.push(eng.reaches(hw, vw, p, 1));
      }
      for (let p1 = 0; p1 < N; p1++) {
        if (!ok1[p1] || row(p1) === 0) continue;
        for (let p2 = 0; p2 < N; p2++) {
          if (p2 === p1 || !ok2[p2] || row(p2) === H - 1) continue;
          for (let turn = 0; turn < 2; turn++) {
            legalStates += splits;
            // les coups de pion ne dépendent pas des stocks
            const st = { hw, vw, p: [p1, p2], walls: [0, 0], turn };
            const pawnMoves = eng.children(st).length;
            if (pawnMoves === 0) {
              zeroPawnMove += splits;
              if (examples.length < 3) examples.push({ hw, vw, p1, p2, turn });
            }
          }
        }
      }
    }
  }
  console.log(JSON.stringify({
    width: W, height: H, walls,
    legalConfigs: configs,
    legalNonTerminalStates: legalStates,
    zeroPawnMoveStates: zeroPawnMove,
    examples,
    seconds: +((Date.now() - t0) / 1000).toFixed(2)
  }));
  process.exit(H >= 3 && zeroPawnMove ? 5 : 0);

} else if (cmd === 'diff-states') {
  /*
   * H=2 : la convention de pat est-elle sémantiquement visible ? Pour CHAQUE
   * état atteignable et chaque cible T, compare Win(s,T,d) sous les deux
   * conventions au budget d fixé. Compte et exhibe les divergences.
   */
  const [W, H, walls, d] = args.map(Number);
  const eng = makeEngine(W, H, walls);
  const solC = makeSolver(eng, 'code');
  const solD = makeSolver(eng, 'doc');
  const t0 = Date.now();
  let frontier = [eng.initial()];
  const seen = new Set([stKey(frontier[0])]);
  const all = [frontier[0]];
  while (frontier.length) {
    const next = [];
    for (const st of frontier) {
      if (eng.terminal(st) !== -1) continue;
      for (const [, c] of eng.children(st)) {
        const k = stKey(c);
        if (!seen.has(k)) { seen.add(k); all.push(c); next.push(c); }
      }
    }
    frontier = next;
  }
  let checked = 0, diverging = 0;
  const examples = [];
  for (const st of all) {
    if (eng.terminal(st) !== -1) continue;
    for (const T of [0, 1]) {
      checked++;
      const a = solC.win(st, T, d), b = solD.win(st, T, d);
      if (a !== b) {
        diverging++;
        if (examples.length < 3) examples.push({ ...st, target: T, code: a, doc: b });
      }
    }
  }
  console.log(JSON.stringify({
    width: W, height: H, walls, depth: d,
    reachableStates: all.length, queriesChecked: checked,
    divergingVerdicts: diverging, examples,
    stalematesSeenCode: solC.stats().stalemates, stalematesSeenDoc: solD.stats().stalemates,
    seconds: +((Date.now() - t0) / 1000).toFixed(2)
  }));

} else if (cmd === 'solve-both') {
  const [W, H, walls, maxD] = args.map(Number);
  const eng = makeEngine(W, H, walls);
  const out = {};
  for (const mode of ['code', 'doc']) {
    const sol = makeSolver(eng, mode);
    const root = eng.initial();
    let res = null;
    outer:
    for (let d = 1; d <= maxD; d++) {
      for (const T of [0, 1]) {
        if (sol.win(root, T, d)) { res = { winner: T + 1, depth: d }; break outer; }
      }
    }
    const st = sol.stats();
    out[mode] = { ...(res ?? { winner: 0, depth: -1 }), nodes: st.nodes, stalematesSeen: st.stalemates };
  }
  out.rootVerdictsAgree = out.code.winner === out.doc.winner && out.code.depth === out.doc.depth;
  console.log(JSON.stringify({ width: W, height: H, walls, maxDepth: maxD, ...out }));

} else {
  console.log('commandes : scan | solve-both');
  process.exit(2);
}
