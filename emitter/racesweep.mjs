// racesweep.mjs — balayage de la conjecture du zugzwang de course.
//
// Plateau 9×9 SANS murs : la RaceTable donne la valeur exacte de chaque
// (p0, p1, trait). On cherche une caractérisation des états où le trait
// PERD (zugzwang), en particulier sur les états symétriques (p1 = miroir
// central de p0) où la position initiale donne le −16 mesuré.
//
// Convention engine : rangée 0 en bas, J0 vise la rangée 8 (z >= 72),
// J1 vise la rangée 0 (z <= 8). d0 = 8 − r0, d1 = r1.
//
//   node racesweep.mjs

import { Position, NCELLS } from './engine.js';
import { RaceTable } from './race.js';

const pos = new Position();
pos.reset();
const rt = new RaceTable(pos.adj);

const row = (p) => Math.floor(p / 9), col = (p) => p % 9;

// ---- 1. inventaire global --------------------------------------------------
let states = 0, moverWins = 0, moverLoses = 0, draws = 0;
let mutual = 0; // paires (p0,p1) où le trait perd DES DEUX côtés
const loseByKey = new Map(); // caractérisation des pertes du trait
for (let p0 = 0; p0 < 72; p0++) {
  for (let p1 = 9; p1 < NCELLS; p1++) {
    if (p1 === p0) continue;
    const v0 = rt.probe(p0, p1, 0), v1 = rt.probe(p0, p1, 1);
    for (const v of [v0, v1]) {
      states++;
      if (v > 0) moverWins++;
      else if (v < 0) moverLoses++;
      else draws++;
    }
    if (v0 < 0 && v1 < 0) mutual++;
    // caractérisation : le trait perd
    const d0 = 8 - row(p0), d1 = row(p1), dc = Math.abs(col(p0) - col(p1));
    if (v0 < 0) {
      const k = `dd=${d0 - d1} dc=${dc}`;
      loseByKey.set(k, (loseByKey.get(k) || 0) + 1);
    }
    if (v1 < 0) {
      const k = `dd=${d1 - d0} dc=${dc}`;
      loseByKey.set(k, (loseByKey.get(k) || 0) + 1);
    }
  }
}
console.log(JSON.stringify({ states, moverWins, moverLoses, draws, mutual }));

// ---- 2. la perte du trait : signature (écart de distance, écart de colonne)
const sig = [...loseByKey.entries()].sort((a, b) => b[1] - a[1]);
console.log('pertes du trait par (d_moi − d_lui, |Δcol|), top 12 :');
for (const [k, n] of sig.slice(0, 12)) console.log(`  ${k}  ×${n}`);
const ddSet = new Set(sig.map(([k]) => k.match(/dd=(-?\d+)/)[1]));
console.log(`valeurs de (d_moi − d_lui) présentes dans les pertes : ${[...ddSet].sort((a,b)=>a-b).join(', ')}`);

// ---- 3. états symétriques (p1 = miroir central de p0) ----------------------
console.log('\nétats symétriques p1 = (8−r0, c0) — v identique des deux traits :');
const bycol = [];
for (let r0 = 0; r0 <= 3; r0++) {           // r0 < 4 : au-delà, superposition/croisement
  const line = [];
  for (let c = 0; c < 9; c++) {
    const p0 = r0 * 9 + c, p1 = (8 - r0) * 9 + c;
    const v0 = rt.probe(p0, p1, 0), v1 = rt.probe(p0, p1, 1);
    line.push(`c${c}:${v0}${v0 !== v1 ? '/' + v1 : ''}`);
  }
  bycol.push(`r0=${r0} (gap ${8 - 2 * r0}) : ${line.join(' ')}`);
}
console.log(bycol.join('\n'));

// ---- 4. même colonne, distances égales, gap variable -----------------------
console.log('\nmême colonne c=4, d0 = d1 = d, tous les faces-à-face (r0, r1 = r0+gap) :');
for (let gap = 2; gap <= 8; gap++) {
  const line = [];
  for (let r0 = 0; r0 + gap <= 8; r0++) {
    const r1 = r0 + gap;
    const d0 = 8 - r0, d1 = r1;
    if (d0 !== d1) continue;                 // distances égales seulement
    const p0 = r0 * 9 + 4, p1 = r1 * 9 + 4;
    line.push(`r0=${r0}: v=${rt.probe(p0, p1, 0)}/${rt.probe(p0, p1, 1)}`);
  }
  if (line.length) console.log(`  gap=${gap} : ${line.join('  ')}`);
}

// ---- 5. distances égales, colonnes distinctes : le trait perd-il encore ? --
console.log('\ndistances égales d0=d1=d, écart de colonne dc, % de pertes du trait :');
const agg = new Map();
for (let p0 = 0; p0 < 72; p0++) {
  for (let p1 = 9; p1 < NCELLS; p1++) {
    if (p1 === p0) continue;
    const d0 = 8 - row(p0), d1 = row(p1);
    if (d0 !== d1) continue;
    const dc = Math.abs(col(p0) - col(p1));
    const k = `d=${d0} dc=${dc}`;
    const e = agg.get(k) || { n: 0, lose: 0 };
    e.n += 2;
    if (rt.probe(p0, p1, 0) < 0) e.lose++;
    if (rt.probe(p0, p1, 1) < 0) e.lose++;
    agg.set(k, e);
  }
}
const rows = [...agg.entries()].sort();
for (const [k, e] of rows) {
  if (e.lose > 0) console.log(`  ${k} : ${e.lose}/${e.n} pertes du trait`);
}
const zeroLoss = rows.filter(([, e]) => e.lose === 0).map(([k]) => k);
console.log(`combinaisons (d, dc) SANS perte du trait : ${zeroLoss.length ? zeroLoss.join(' | ') : 'aucune'}`);
