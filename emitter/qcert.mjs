/**
 * qcert — certificats de stratégie vérifiables (format qcert-1).
 *
 * `emit`   : résout une petite variante depuis la position initiale, extrait
 *            la stratégie gagnante dédupliquée avec budgets exacts `dmin`,
 *            écrit le certificat JSONL (spec : CERTIFICATE_FORMAT.md).
 * `verify` : vérifie un certificat SANS recherche — régénère les coups avec
 *            le moteur clean-room de qref.mjs et contrôle les inégalités
 *            locales. Accepter ⇒ Win(root, T, bound) (théorème de correction
 *            dans CERTIFICATE_FORMAT.md).
 *
 * Usage :
 *   node qcert.mjs emit W H walls maxDepth [fichier.jsonl] [étatRacineJSON]
 *   node qcert.mjs verify fichier.jsonl
 *
 * L'état racine optionnel ({"p1":..,"p2":..,"r1":..,"r2":..,"turn":..,
 * "hw":..,"vw":..}, format du dump) permet de certifier une branche —
 * exactement ce qu'exige la décomposition par classes de réponses du
 * solveur principal.
 */
import * as fs from 'node:fs';
import * as readline from 'node:readline';
import { makeEngine, makeSolver } from './qref.mjs';

const [, , cmd, ...args] = process.argv;

const stKey = (st) => `${st.hw},${st.vw},${st.p[0]},${st.p[1]},${st.walls[0]},${st.walls[1]},${st.turn}`;
const stJson = (st) => ({
  p1: st.p[0], p2: st.p[1], r1: st.walls[0], r2: st.walls[1],
  turn: st.turn, hw: st.hw, vw: st.vw
});

if (cmd === 'emit') {
  const [W, H, walls, maxD] = args.slice(0, 4).map(Number);
  const outPath = args[4] || `cert_${W}x${H}x${walls}.jsonl`;
  const eng = makeEngine(W, H, walls);
  const sol = makeSolver(eng, 'code');
  let root = eng.initial();
  if (args[5]) {
    const o = JSON.parse(args[5]);
    root = { hw: o.hw, vw: o.vw, p: [o.p1, o.p2], walls: [o.r1, o.r2], turn: o.turn };
    if (eng.terminal(root) !== -1) { console.error('{"error":"racine terminale"}'); process.exit(2); }
  }
  const t0 = Date.now();

  // 1. vainqueur et profondeur minimale à la racine
  let T = -1, rootD = -1;
  outer:
  for (let d = 1; d <= maxD; d++) {
    for (const cand of [0, 1]) {
      if (sol.win(root, cand, d)) { T = cand; rootD = d; break outer; }
    }
  }
  if (T < 0) {
    console.error(JSON.stringify({ error: 'non résolu', maxDepth: maxD, nodes: sol.stats().nodes }));
    process.exit(1);
  }

  // 2. dmin exact par état (les longueurs de gain ont une parité fixe par trait)
  const dminMemo = new Map();
  function dmin(st) {
    const t = eng.terminal(st);
    if (t !== -1) return t === T ? 0 : Infinity;
    const k = stKey(st);
    let v = dminMemo.get(k);
    if (v !== undefined) return v;
    const start = st.turn === T ? 1 : 2;
    v = Infinity;
    for (let d = start; d <= maxD; d += 2) {
      if (sol.win(st, T, d)) { v = d; break; }
    }
    dminMemo.set(k, v);
    return v;
  }

  // 3. extraction du sous-graphe de stratégie, dédupliqué
  const out = fs.createWriteStream(outPath);
  out.write(JSON.stringify({
    type: 'header', format: 'qcert-1', width: W, height: H, walls,
    target: T, bound: rootD, root: stJson(root)
  }) + '\n');

  const emitted = new Set();
  let nNodes = 0, nTNodes = 0, maxDepthSeen = 0;
  function emitNode(st) {
    const k = stKey(st);
    if (emitted.has(k)) return;
    emitted.add(k);
    const d = dmin(st);
    if (!Number.isFinite(d)) throw new Error('état non gagnant dans la stratégie : ' + k);
    maxDepthSeen = Math.max(maxDepthSeen, d);
    nNodes++;
    const kids = eng.children(st);
    if (kids.length === 0) throw new Error('pat rencontré (impossible pour H>=3) : ' + k);
    if (st.turn === T) {
      nTNodes++;
      // enfant réalisant dmin - 1 (0 = gain immédiat)
      let best = null;
      for (const [label, c] of kids) {
        const t = eng.terminal(c);
        const dc = t !== -1 ? (t === T ? 0 : Infinity) : dmin(c);
        if (dc === d - 1) { best = [label, c, dc]; break; }
      }
      if (!best) throw new Error(`aucun enfant à dmin-1 (d=${d}) : ` + k);
      out.write(JSON.stringify({ type: 'node', ...stJson(st), d, move: best[0] }) + '\n');
      if (best[2] > 0) emitNode(best[1]);
    } else {
      out.write(JSON.stringify({ type: 'node', ...stJson(st), d }) + '\n');
      for (const [, c] of kids) {
        const t = eng.terminal(c);
        if (t !== -1) {
          if (t !== T) throw new Error('enfant terminal perdant sous stratégie : ' + k);
          continue;
        }
        emitNode(c);
      }
    }
  }
  emitNode(root);
  out.end(() => {
    console.log(JSON.stringify({
      file: outPath, width: W, height: H, walls,
      winner: T + 1, bound: rootD, nodes: nNodes, targetNodes: nTNodes,
      maxCertifiedDepth: maxDepthSeen,
      solverNodes: sol.stats().nodes,
      seconds: +((Date.now() - t0) / 1000).toFixed(2)
    }));
  });

} else if (cmd === 'verify') {
  const file = args[0];
  const t0 = Date.now();
  const rl = readline.createInterface({ input: fs.createReadStream(file) });
  let header = null, eng = null;
  const index = new Map();  // clé état -> {d, move, st}
  const errors = [];
  const fail = (msg) => { if (errors.length < 10) errors.push(msg); };

  rl.on('line', (line) => {
    line = line.trim();
    if (!line) return;
    const o = JSON.parse(line);
    if (o.type === 'header') {
      if (header) fail('en-têtes multiples');
      if (o.format !== 'qcert-1') fail('format inconnu : ' + o.format);
      for (const f of ['width', 'height', 'walls', 'target', 'bound'])
        if (!Number.isSafeInteger(o[f])) fail('en-tête : entier non sûr ' + f);
      if ((o.width - 1) * (o.height - 1) > 31)
        fail('plus de 31 ancres : hors domaine du moteur 32 bits');
      header = o;
      eng = makeEngine(o.width, o.height, o.walls);
      return;
    }
    if (o.type !== 'node') { fail('type de ligne inconnu : ' + o.type); return; }
    if (!header) { fail('nœud avant en-tête'); return; }
    // entiers sûrs obligatoires : avec 2^54, d-1 === d et la décroissance
    // stricte devient invérifiable (durcissement repris de la revue de sol)
    for (const f of ['p1', 'p2', 'r1', 'r2', 'turn', 'hw', 'vw', 'd'])
      if (!Number.isSafeInteger(o[f])) { fail('entier non sûr ' + f + ' : ' + o[f]); return; }
    const nAnchors = (header.width - 1) * (header.height - 1);
    if (o.hw < 0 || o.vw < 0 || o.hw >= 2 ** nAnchors || o.vw >= 2 ** nAnchors)
      fail('masque de murs hors domaine');
    const st = { hw: o.hw, vw: o.vw, p: [o.p1, o.p2], walls: [o.r1, o.r2], turn: o.turn };
    const k = stKey(st);
    if (index.has(k)) { fail('état dupliqué : ' + k); return; }
    // légalité structurelle
    if (o.p1 === o.p2) fail('pions superposés : ' + k);
    if (o.r1 < 0 || o.r1 > header.walls || o.r2 < 0 || o.r2 > header.walls) fail('stock hors bornes : ' + k);
    // conservation : stocks restants + murs posés = dotation totale
    let placed = 0;
    for (let x = o.hw; x; x &= x - 1) placed++;
    for (let x = o.vw; x; x &= x - 1) placed++;
    if (o.r1 + o.r2 + placed !== 2 * header.walls) fail('conservation des murs violée : ' + k);
    if (eng.terminal(st) !== -1) fail('état terminal dans l’index : ' + k);
    if (!(o.d >= 1)) fail('budget < 1 sur état non terminal : ' + k);
    if (o.turn === header.target && !o.move) fail('coup manquant à T au trait : ' + k);
    if (o.turn !== header.target && o.move) fail('coup déclaré à l’adversaire au trait : ' + k);
    index.set(k, { d: o.d, move: o.move, st });
  });

  rl.on('close', () => {
    if (!header) { console.log(JSON.stringify({ ok: false, errors: ['aucun en-tête'] })); process.exit(1); }
    const T = header.target;
    let edges = 0, tNodes = 0, oppNodes = 0;

    // enfant admissible : terminal gagné par T, ou indexé avec d' <= d-1
    function childOK(c, d, ctx) {
      const t = eng.terminal(c);
      if (t !== -1) {
        if (t !== T) fail(`enfant terminal perdu par T (${ctx})`);
        return;
      }
      const e = index.get(stKey(c));
      if (!e) { fail(`enfant non couvert (${ctx})`); return; }
      if (!(e.d <= d - 1)) fail(`budget enfant ${e.d} > ${d - 1} (${ctx})`);
    }

    for (const [k, { d, move, st }] of index) {
      const kids = eng.children(st);
      if (kids.length === 0) { fail('état sans coup légal : ' + k); continue; }
      if (st.turn === T) {
        tNodes++;
        const hit = kids.find(([label]) => label === move);
        if (!hit) { fail(`coup déclaré illégal ${move} : ` + k); continue; }
        edges++;
        childOK(hit[1], d, `via ${move} depuis ${k}`);
      } else {
        oppNodes++;
        for (const [label, c] of kids) {
          edges++;
          childOK(c, d, `via ${label} depuis ${k}`);
        }
      }
    }

    // racine
    const rootSt = {
      hw: header.root.hw, vw: header.root.vw,
      p: [header.root.p1, header.root.p2],
      walls: [header.root.r1, header.root.r2], turn: header.root.turn
    };
    const re = index.get(stKey(rootSt));
    if (!re) fail('racine absente de l’index');
    else if (!(re.d <= header.bound)) fail(`budget racine ${re.d} > borne annoncée ${header.bound}`);

    // la racine est-elle la position initiale de la variante ? (informatif :
    // un certificat de branche est valide, mais le consommateur doit savoir
    // quelle position est réellement certifiée)
    const ini = eng.initial();
    const rootIsInitial = stKey(rootSt) === stKey(ini);

    const ok = errors.length === 0;
    console.log(JSON.stringify({
      ok, file,
      claim: { width: header.width, height: header.height, walls: header.walls, winner: T + 1, bound: header.bound },
      rootIsInitialPosition: rootIsInitial,
      nodes: index.size, targetNodes: tNodes, opponentNodes: oppNodes, edgesChecked: edges,
      errors, seconds: +((Date.now() - t0) / 1000).toFixed(2)
    }));
    process.exit(ok ? 0 : 1);
  });

} else {
  console.log('commandes : emit | verify');
  process.exit(2);
}
