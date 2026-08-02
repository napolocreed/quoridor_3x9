/**
 * Table de course exacte.
 *
 * Quand plus aucun mur n'est en stock, le graphe est figé : le jeu restant
 * est une course pure entre les deux pions, interactions de saut comprises.
 * L'espace d'états est minuscule (81 × 81 × 2 = 13 122) : on le résout
 * exactement par induction arrière itérée jusqu'au point fixe.
 *
 * Valeur d'un état, du point de vue du joueur au trait :
 *   +k : gain forcé en k plis (k ≥ 1)
 *   -k : défaite forcée en k plis, quoi qu'il joue
 *    0 : nulle (cycle sous jeu optimal des deux côtés)
 *
 * La table rend le jeu de fin de partie PARFAIT (mat le plus court, défense
 * la plus longue) et transforme les feuilles de recherche en oracles exacts.
 *
 * @module race
 */
import { NCELLS, DELTA, BIT, PERP } from './engine.js';

const IDX = (p0, p1, turn) => (p0 * NCELLS + p1) * 2 + turn;

export class RaceTable {
  /**
   * @param {Uint8Array} adj masques d'adjacence figés (copiés)
   */
  constructor(adj) {
    this.adj = new Uint8Array(adj);
    this.val = new Int16Array(NCELLS * NCELLS * 2);
    this._solve();
  }

  /** Destinations légales du pion `me` (l'adversaire en `opp`), règle complète du saut. */
  _moves(me, opp, out) {
    const adj = this.adj;
    let n = 0;
    const mask = adj[me];
    for (let k = 0; k < 4; k++) {
      if (!(mask & BIT[k])) continue;
      const step = me + DELTA[k];
      if (step !== opp) { out[n++] = step; continue; }
      if (adj[step] & BIT[k]) out[n++] = step + DELTA[k];
      else {
        const pp = PERP[k];
        for (let j = 0; j < 2; j++) {
          const d = pp[j];
          if (adj[step] & BIT[d]) out[n++] = step + DELTA[d];
        }
      }
    }
    return n;
  }

  _solve() {
    const val = this.val;
    const buf = new Int32Array(5);
    // balayages jusqu'au point fixe : les distances de gain convergent en
    // décroissant, les distances de perte ne se posent que sur successeurs
    // tous connus gagnants pour l'adversaire.
    for (let changed = true; changed;) {
      changed = false;
      for (let p0 = 0; p0 < NCELLS; p0++) {
        if (p0 >= 72) continue;                    // J0 arrivé : terminal
        for (let p1 = 0; p1 < NCELLS; p1++) {
          if (p1 === p0 || p1 <= 8) continue;      // superposé / J1 arrivé
          for (let turn = 0; turn < 2; turn++) {
            const s = IDX(p0, p1, turn);
            const me = turn === 0 ? p0 : p1;
            const op = turn === 0 ? p1 : p0;
            const goalWin = turn === 0 ? (z) => z >= 72 : (z) => z <= 8;
            const n = this._moves(me, op, buf);
            let bestWin = 0x7fff, allLose = true, maxLose = -1;
            for (let i = 0; i < n; i++) {
              const z = buf[i];
              if (goalWin(z)) { bestWin = 1; allLose = false; continue; }
              const t = turn === 0 ? IDX(z, p1, 1) : IDX(p0, z, 0);
              const v = val[t];
              if (v < 0) { const w = 1 - v; if (w < bestWin) bestWin = w; allLose = false; }
              else if (v > 0) { const l = v + 1; if (l > maxLose) maxLose = l; }
              else allLose = false;                // successeur nul/inconnu
            }
            let nv;
            if (bestWin < 0x7fff) nv = bestWin;
            else if (allLose && n > 0) nv = -maxLose;
            else nv = 0;
            if (nv !== val[s]) { val[s] = nv; changed = true; }
          }
        }
      }
    }
  }

  /**
   * Valeur exacte, du point de vue du joueur au trait.
   * Ne pas interroger un état terminal ni superposé.
   */
  probe(p0, p1, turn) { return this.val[IDX(p0, p1, turn)]; }

  /** Meilleur coup exact : mat le plus court, sinon nulle, sinon défense la plus longue. */
  bestMove(p0, p1, turn) {
    const me = turn === 0 ? p0 : p1;
    const op = turn === 0 ? p1 : p0;
    const goalWin = turn === 0 ? (z) => z >= 72 : (z) => z <= 8;
    const buf = new Int32Array(5);
    const n = this._moves(me, op, buf);
    let best = -1, bestV = -0x7fff;
    for (let i = 0; i < n; i++) {
      const z = buf[i];
      // valeur du coup pour moi : gain immédiat, sinon -valeur de l'état suivant
      let v;
      if (goalWin(z)) v = 0x7fff;
      else {
        const t = turn === 0 ? IDX(z, p1, 1) : IDX(p0, z, 0);
        const w = this.val[t];
        v = w === 0 ? 0 : (w > 0 ? -(0x4000 - w) : 0x4000 - (-w));
        // perdant -w : préférer -w grand (défense longue) ; gagnant w : w petit
      }
      if (v > bestV) { bestV = v; best = z; }
    }
    return best;
  }
}

/**
 * Cache de tables par configuration de murs (signature Zobrist des murs).
 * Une recherche visite peu de configurations distinctes à stocks épuisés.
 */
export class RaceCache {
  constructor(cap = 64) { this.cap = cap; this.size = 0; this.map = new Map(); }
  /** @param {import('./engine.js').Position} pos */
  get(pos) {
    // deux niveaux : (wallLo * 2^32 + wallHi) déborderait la précision
    // entière du float64 et pourrait faire collisionner deux configurations
    let inner = this.map.get(pos.wallLo);
    if (!inner) { inner = new Map(); this.map.set(pos.wallLo, inner); }
    let t = inner.get(pos.wallHi);
    if (!t) {
      if (this.size >= this.cap) { this.map.clear(); this.map.set(pos.wallLo, inner = new Map()); this.size = 0; }
      t = new RaceTable(pos.adj);
      inner.set(pos.wallHi, t);
      this.size++;
    }
    return t;
  }
}
