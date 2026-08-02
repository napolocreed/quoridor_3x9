// race_param.mjs — table de course exacte PARAMÉTRIQUE (W×H sans murs) pour
// tester la conjecture de parité de RACE_ZUGZWANG.md :
//
//   pions alignés en colonne, distances égales d, face-à-face (gap >= 1) :
//     gap PAIR  (H impair) => le trait PERD en exactement 2d plis ;
//     gap IMPAIR (H pair)  => le trait GAGNE (le saut au contact le sert).
//   partout ailleurs (croisés ou colonnes distinctes, distances égales) :
//     le trait gagne. Et : aucune nulle nulle part.
//
// Auto-contrôle : sur 9×9 la table doit coïncider avec race.js (13 122 états).
//
//   node race_param.mjs

class Race {
  constructor(W, H) {
    this.W = W; this.H = H; this.N = W * H;
    // adjacence pleine grille ; DELTA : +W (haut), -W (bas), +1, -1
    this.val = new Int16Array(this.N * this.N * 2);
    this._solve();
  }
  idx(p0, p1, t) { return (p0 * this.N + p1) * 2 + t; }
  neigh(p) {
    const { W, N } = this, out = [];
    if (p + W < N) out.push(p + W);
    if (p - W >= 0) out.push(p - W);
    if (p % W < W - 1) out.push(p + 1);
    if (p % W > 0) out.push(p - 1);
    return out;
  }
  moves(me, opp) {
    const out = [];
    for (const step of this.neigh(me)) {
      if (step !== opp) { out.push(step); continue; }
      const d = step - me;                       // saut en ligne si case derrière
      const behind = step + d;
      const straightOk = this.neigh(step).includes(behind);
      if (straightOk) out.push(behind);
      else for (const z of this.neigh(step))     // sinon pas de côté du saut
        if (z !== me && z - step !== d) out.push(z);
    }
    return out;
  }
  goal(t, z) { return t === 0 ? z >= this.N - this.W : z < this.W; }
  done(p, t) { return this.goal(t, p); }
  _solve() {
    const { N, val } = this;
    for (let changed = true; changed;) {
      changed = false;
      for (let p0 = 0; p0 < N; p0++) {
        if (this.goal(0, p0)) continue;
        for (let p1 = 0; p1 < N; p1++) {
          if (p1 === p0 || this.goal(1, p1)) continue;
          for (let t = 0; t < 2; t++) {
            const me = t === 0 ? p0 : p1, op = t === 0 ? p1 : p0;
            let bestWin = 0x7fff, allLose = true, maxLose = -1;
            for (const z of this.moves(me, op)) {
              if (this.goal(t, z)) { bestWin = 1; allLose = false; continue; }
              const v = val[t === 0 ? this.idx(z, p1, 1) : this.idx(p0, z, 0)];
              if (v < 0) { const w = 1 - v; if (w < bestWin) bestWin = w; allLose = false; }
              else if (v > 0) { const l = v + 1; if (l > maxLose) maxLose = l; }
              else allLose = false;
            }
            const s = this.idx(p0, p1, t);
            let nv;
            if (bestWin < 0x7fff) nv = bestWin;
            else if (allLose && maxLose > 0) nv = -maxLose;
            else nv = 0;
            if (nv !== val[s]) { val[s] = nv; changed = true; }
          }
        }
      }
    }
  }
  probe(p0, p1, t) { return this.val[this.idx(p0, p1, t)]; }
}

// ---- auto-contrôle 9×9 contre race.js --------------------------------------
{
  const { Position } = await import('./engine.js');
  const { RaceTable } = await import('./race.js');
  const pos = new Position(); pos.reset();
  const ref = new RaceTable(pos.adj);
  const par = new Race(9, 9);
  let diff = 0, checked = 0;
  for (let p0 = 0; p0 < 72; p0++)
    for (let p1 = 9; p1 < 81; p1++) {
      if (p1 === p0) continue;
      for (let t = 0; t < 2; t++) {
        checked++;
        if (ref.probe(p0, p1, t) !== par.probe(p0, p1, t)) diff++;
      }
    }
  console.log(JSON.stringify({ selftest: '9x9 vs race.js', checked, diff }));
  if (diff) process.exit(5);
}

// ---- balayage de la conjecture sur une grille de plateaux ------------------
const results = [];
for (let H = 4; H <= 9; H++) {
  for (const W of [2, 3, 5, 9]) {
    const g = new Race(W, H);
    const row = (p) => Math.floor(p / W), col = (p) => p % W;
    let draws = 0, states = 0;
    let alignedFacing = 0, afMoverLose = 0, afBad = [];
    let elseLose = 0;                      // distances égales, pas aligné-face
    for (let p0 = 0; p0 < g.N; p0++) {
      if (g.goal(0, p0)) continue;
      for (let p1 = 0; p1 < g.N; p1++) {
        if (p1 === p0 || g.goal(1, p1)) continue;
        const v0 = g.probe(p0, p1, 0), v1 = g.probe(p0, p1, 1);
        states += 2;
        if (v0 === 0) draws++;
        if (v1 === 0) draws++;
        const d0 = H - 1 - row(p0), d1 = row(p1);
        if (d0 !== d1) continue;
        const gap = row(p1) - row(p0);
        const aligned = col(p0) === col(p1) && gap >= 1;
        for (const [t, v] of [[0, v0], [1, v1]]) {
          if (aligned) {
            alignedFacing++;
            const expectLose = gap % 2 === 0;      // conjecture
            if (v < 0) afMoverLose++;
            const loseExact = v === -2 * d0;
            if (expectLose !== (v < 0) || (expectLose && !loseExact))
              afBad.push({ W, H, p0, p1, t, v, d: d0, gap });
          } else if (v < 0) elseLose++;
        }
      }
    }
    results.push({ W, H, states, draws, alignedFacing, afMoverLose,
                   conjectureViolations: afBad.length, elseLose,
                   sample: afBad.slice(0, 3) });
  }
}
for (const r of results) console.log(JSON.stringify(r));
const bad = results.filter(r => r.conjectureViolations || r.draws || r.elseLose);
console.log(bad.length ? `CONJECTURE FAUSSE sur ${bad.length} plateaux` : 'CONJECTURE TIENT sur tous les plateaux balayés');
