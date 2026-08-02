// sample_dataset.mjs — échantillonne les mémos CertMap en dataset
// d'apprentissage (états J1 exactement étiquetés : coup optimal + rang).
//
// Réservoir de K états J1 par classe (LCG déterministe), un fichier binaire
// par classe : records de 10 octets
//   p0 u8, p1 u8, s0 u8, s1 u8, hw u16LE, vw u16LE, rem u8, move u8
// move : 0..26 = P:cell ; 27..42 = H:anchor ; 43..58 = V:anchor.
// Décodage clé STRICTEMENT en BigInt (clés jusqu'à 2^54, cf. memostats.mjs).
//
//   node sample_dataset.mjs [K]        (défaut 300000)

import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';

const K = Number(process.argv[2] ?? 300000);
const TAGS = ['P11', 'P00', 'H00', 'H10', 'H20', 'H30', 'H40', 'H50', 'H60',
  'H70', 'V00', 'V10', 'V20', 'V30', 'V40', 'V50', 'V60', 'V70'];
mkdirSync('dataset', { recursive: true });

// LCG 64 bits (Knuth) — reproductible, indépendant de Math.random
function lcg(seed) {
  let s = BigInt(seed);
  const A = 6364136223846793005n, C = 1442695040888963407n, M = 1n << 64n;
  return () => { s = (s * A + C) % M; return Number(s >> 11n) / 2 ** 53; };
}

for (const tag of TAGS) {
  const buf = readFileSync(`work/memo_${tag}.bin`);
  const n = Number(buf.readBigUInt64LE(0));
  const kv = new BigUint64Array(buf.buffer, buf.byteOffset + 16, n);
  const vals = new Uint32Array(buf.buffer, buf.byteOffset + 16 + 8 * n, n);
  const rnd = lcg(1000003 + TAGS.indexOf(tag));
  const res = Buffer.alloc(K * 10);
  let seen = 0, kept = 0;
  for (let i = 0; i < n; i++) {
    const k = kv[i];
    if (k === 0n) continue;
    let x = (k - 1n) >> 1n;
    const turn = Number(x & 1n); x >>= 1n;
    if (turn !== 0) continue;                      // états J1 seulement
    const v = vals[i];
    const rem = v & 63, mv = (v >> 6) & 0x1ff;
    if (mv === 0x1ff) continue;                    // anomalie théorique
    seen++;
    let slot;
    if (kept < K) slot = kept++;
    else {
      const j = Math.floor(rnd() * seen);
      if (j >= K) continue;
      slot = j;
    }
    const s1 = Number(x & 15n); x >>= 4n;
    const s0 = Number(x & 15n); x >>= 4n;
    const p1 = Number(x & 31n); x >>= 5n;
    const p0 = Number(x & 31n); x >>= 5n;
    const vw = Number(x & 0x3ffffn); x >>= 18n;
    const hw = Number(x);
    const move = mv < 256 ? mv : (mv < 272 ? 27 + (mv - 256) : 43 + (mv - 272));
    const o = slot * 10;
    res[o] = p0; res[o + 1] = p1; res[o + 2] = s0; res[o + 3] = s1;
    res.writeUInt16LE(hw, o + 4); res.writeUInt16LE(vw, o + 6);
    res[o + 8] = rem; res[o + 9] = move;
  }
  writeFileSync(`dataset/${tag}.bin`, res.subarray(0, kept * 10));
  console.log(JSON.stringify({ tag, j1_total: seen, sampled: kept }));
}
