// augment_dataset.mjs — enrichit dataset/<TAG>.bin avec des traits de chemin
// calculés par BFS (convention qsolve : (0,0) en haut à gauche, J1 = p0 vise
// la rangée 0, J2 = p1 vise la rangée 8 ; W=3, H=9, ancres 8×2 par
// orientation, index i = r*2 + c).
//
// Record de sortie (dataset/<TAG>.aug.bin, 20 octets) :
//   les 10 octets d'origine, puis
//   d0 u8, d1 u8 (distances BFS vers les rangées but, pion adverse ignoré)
//   dir0 u8, dir1 u8 (bitmask des directions qui décroissent la distance :
//                     1=haut, 2=bas, 4=gauche, 8=droite)
//   path1 u32LE (bits 0..15 : ancres H adjacentes à un chemin optimal de J2,
//                bits 16..31 : idem ancres V) — « où murer pour gêner J2 »
//   auto-test : compte les records où rem < 2*d0 - 3 (géométrie fausse si >0)
//
//   node augment_dataset.mjs

import { readFileSync, writeFileSync } from 'node:fs';

const W = 3, H = 9, C = 2;                      // C = W-1 anchors par rangée
const TAGS = ['P11', 'P00', 'H00', 'H10', 'H20', 'H30', 'H40', 'H50', 'H60',
  'H70', 'V00', 'V10', 'V20', 'V30', 'V40', 'V50', 'V60', 'V70'];

// arêtes bloquées par les masques hw/vw
// verticale (r,c)-(r+1,c) : bloquée si ancre H (r, c-1) ou (r, c)  (c-1>=0, c<=1)
// horizontale (r,c)-(r,c+1) : bloquée si ancre V (r-1, c) ou (r, c)
function blockedV(hw, r, c) {
  if (c >= 1 && (hw >> (r * C + c - 1)) & 1) return true;
  if (c <= C - 1 && (hw >> (r * C + c)) & 1) return true;
  return false;
}
function blockedH(vw, r, c) {
  if (r >= 1 && (vw >> ((r - 1) * C + c)) & 1) return true;
  if (r <= H - 2 && (vw >> (r * C + c)) & 1) return true;
  return false;
}

// distances de TOUTES les cases vers la rangée but (BFS multi-source arrière)
function distToRow(hw, vw, goalRow) {
  const dist = new Int8Array(27).fill(-1);
  const q = [];
  for (let c = 0; c < W; c++) { dist[goalRow * W + c] = 0; q.push(goalRow * W + c); }
  for (let h = 0; h < q.length; h++) {
    const p = q[h], r = Math.floor(p / W), c = p % W, d = dist[p];
    if (r > 0 && !blockedV(hw, r - 1, c) && dist[p - W] < 0) { dist[p - W] = d + 1; q.push(p - W); }
    if (r < H - 1 && !blockedV(hw, r, c) && dist[p + W] < 0) { dist[p + W] = d + 1; q.push(p + W); }
    if (c > 0 && !blockedH(vw, r, c - 1) && dist[p - 1] < 0) { dist[p - 1] = d + 1; q.push(p - 1); }
    if (c < W - 1 && !blockedH(vw, r, c) && dist[p + 1] < 0) { dist[p + 1] = d + 1; q.push(p + 1); }
  }
  return dist;
}

// directions décroissantes + cellules d'UN chemin optimal (suivi glouton)
function pathInfo(dist, p, hw, vw) {
  let dirs = 0;
  const r = Math.floor(p / W), c = p % W, d = dist[p];
  if (r > 0 && !blockedV(hw, r - 1, c) && dist[p - W] === d - 1) dirs |= 1;
  if (r < H - 1 && !blockedV(hw, r, c) && dist[p + W] === d - 1) dirs |= 2;
  if (c > 0 && !blockedH(vw, r, c - 1) && dist[p - 1] === d - 1) dirs |= 4;
  if (c < W - 1 && !blockedH(vw, r, c) && dist[p + 1] === d - 1) dirs |= 8;
  // chemin glouton (préfère vertical) pour le marquage d'ancres
  const cells = [p];
  let cur = p;
  while (dist[cur] > 0) {
    const r2 = Math.floor(cur / W), c2 = cur % W, d2 = dist[cur];
    let next = -1;
    if (r2 > 0 && !blockedV(hw, r2 - 1, c2) && dist[cur - W] === d2 - 1) next = cur - W;
    else if (r2 < H - 1 && !blockedV(hw, r2, c2) && dist[cur + W] === d2 - 1) next = cur + W;
    else if (c2 > 0 && !blockedH(vw, r2, c2 - 1) && dist[cur - 1] === d2 - 1) next = cur - 1;
    else if (c2 < W - 1 && !blockedH(vw, r2, c2) && dist[cur + 1] === d2 - 1) next = cur + 1;
    if (next < 0) break;
    cells.push(next); cur = next;
  }
  return { dirs, cells };
}

// ancres adjacentes aux cellules d'un chemin : une ancre H (r,c) touche les
// cases (r,c),(r,c+1),(r+1,c),(r+1,c+1) ; idem V.
function anchorsNear(cells) {
  let mask = 0;
  const seen = new Uint8Array(27);
  for (const p of cells) seen[p] = 1;
  for (let r = 0; r < H - 1; r++)
    for (let c = 0; c < C; c++) {
      const touch = seen[r * W + c] || seen[r * W + c + 1] ||
                    seen[(r + 1) * W + c] || seen[(r + 1) * W + c + 1];
      if (touch) mask |= (1 << (r * C + c)) | (1 << (16 + r * C + c));
    }
  return mask >>> 0;
}

let badGeom = 0;
for (const tag of TAGS) {
  const raw = readFileSync(`dataset/${tag}.bin`);
  const nrec = raw.length / 10;
  const out = Buffer.alloc(nrec * 20);
  // cache par configuration de murs (les BFS ne dépendent que de hw/vw)
  const cache = new Map();
  for (let i = 0; i < nrec; i++) {
    const o = i * 10, q = i * 20;
    raw.copy(out, q, o, o + 10);
    const p0 = raw[o], p1 = raw[o + 1], rem = raw[o + 8];
    const hw = raw.readUInt16LE(o + 4), vw = raw.readUInt16LE(o + 6);
    const ck = hw * 65536 + vw;
    let e = cache.get(ck);
    if (!e) {
      const dist0 = distToRow(hw, vw, 0);        // J1 vise la rangée 0
      const dist1 = distToRow(hw, vw, H - 1);    // J2 vise la rangée 8
      e = { dist0, dist1 };
      cache.set(ck, e);
    }
    const d0 = e.dist0[p0], d1 = e.dist1[p1];
    const i0 = pathInfo(e.dist0, p0, hw, vw);
    const i1 = pathInfo(e.dist1, p1, hw, vw);
    if (rem < 2 * d0 - 3) badGeom++;
    out[q + 10] = d0; out[q + 11] = d1;
    out[q + 12] = i0.dirs; out[q + 13] = i1.dirs;
    out.writeUInt32LE(anchorsNear(i1.cells), q + 14);
    // 2 octets de réserve (q+18, q+19) à zéro
  }
  writeFileSync(`dataset/${tag}.aug.bin`, out);
  console.log(JSON.stringify({ tag, records: nrec, wallCfgCached: cache.size }));
}
console.log(JSON.stringify({ geom_violations: badGeom }));
