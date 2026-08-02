// memostats.mjs — décode une CertMap mémo (work/memo_*.bin) et imprime les
// statistiques utiles au dataset d'apprentissage (idée n°2 d'IDEES.md) :
// volumes J1/J2, histogramme des rangs, familles de coups, nombre de
// configurations de murs distinctes.
//
// Les clés (packKey+1) occupent jusqu'à 2^54 bits : TOUT le décodage reste
// en BigInt — une conversion float64 arrondirait le bit de poids faible,
// qui porte target/turn (la leçon Number.isSafeInteger de sol, encore).
// Layout après -1 : bit0 target, bit1 turn, s1 (4b), s0 (4b), p1 (5b),
// p0 (5b), vw (18b), hw (reste). val u32 = rem (6b) | move (9b, 0x1ff = J2).
//
//   node memostats.mjs work/memo_H10.bin

import { readFileSync } from 'node:fs';

const path = process.argv[2] ?? 'work/memo_H10.bin';
const buf = readFileSync(path);
const n = Number(buf.readBigUInt64LE(0)), count = Number(buf.readBigUInt64LE(8));
const kv = new BigUint64Array(buf.buffer, buf.byteOffset + 16, n);
const vals = new Uint32Array(buf.buffer, buf.byteOffset + 16 + 8 * n, n);

const S = 16;                               // (W-1)*(H-1) = 2*8 ancres par orientation
let j1 = 0, j2 = 0, anomalies = 0;
const remHist = new Map(), mvKind = { pawn: 0, hwall: 0, vwall: 0 };
const wallCfg = new Set();
let stockSum = 0;
for (let i = 0; i < n; i++) {
  const k = kv[i];
  if (k === 0n) continue;
  let x = (k - 1n) >> 1n;                   // target (toujours 0 dans les parts)
  const turn = Number(x & 1n); x >>= 1n;
  const s1 = Number(x & 15n); x >>= 4n;
  const s0 = Number(x & 15n); x >>= 4n;
  x >>= 10n;                                // p1 (5b) puis p0 (5b), inutiles ici
  const vw = Number(x & 0x3ffffn); x >>= 18n;
  const hw = Number(x);
  const v = vals[i];
  const rem = v & 63, mv = (v >> 6) & 0x1ff;
  if ((turn === 0) !== (mv !== 0x1ff)) { anomalies++; continue; }
  remHist.set(rem, (remHist.get(rem) || 0) + 1);
  wallCfg.add(hw * 2 ** 18 + vw);
  stockSum += s0 + s1;
  if (turn === 0) {
    j1++;
    if (mv < 256) mvKind.pawn++;
    else if (mv < 256 + S) mvKind.hwall++;
    else mvKind.vwall++;
  } else j2++;
}
const hist = [...remHist.entries()].sort((a, b) => a[0] - b[0])
  .map(([r, c]) => `${r}:${c}`).join(' ');
console.log(JSON.stringify({
  file: path.replace(/\\/g, '/'), slots: n, count, j1, j2, anomalies,
  distinctWallConfigs: wallCfg.size,
  avgStocks: +(stockSum / (j1 + j2)).toFixed(2),
  moveKinds: mvKind,
}));
console.log(`rem histogramme : ${hist}`);
