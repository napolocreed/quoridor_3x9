/**
 * Quoridor — moteur de règles.
 *
 * Repères (identiques à la notation de l'app) :
 *   - colonnes a..i  -> col 0..8
 *   - rangées 1..9   -> row 0..8  (row 0 = rangée 1, en bas)
 *   - case          -> cell = row * 9 + col
 *   - Joueur 0 (rouge) part de e1 (row 0), doit atteindre row 8
 *   - Joueur 1 (bleu)  part de e9 (row 8), doit atteindre row 0
 *
 * Murs : ancrés sur les 8x8 intersections. slot = wr * 8 + wc, wr/wc dans 0..7.
 *   - "he5" = mur horizontal, wc=4 ('e'), wr=4 (5-1) : bloque le passage
 *     entre les rangées 5 et 6, sur les colonnes e et f.
 *   - "ve5" = mur vertical : bloque entre les colonnes e et f, rangées 5 et 6.
 *
 * Encodage des coups sur un entier (0..208) :
 *   0..80    déplacement du pion vers cette case
 *   81..144  mur horizontal, slot = m - 81
 *   145..208 mur vertical,   slot = m - 145
 *
 * @module engine
 */

export const SIZE = 9;
export const NCELLS = 81;
export const NSLOTS = 64;
export const HORIZ = 0;
export const VERT = 1;
export const WALL_H_BASE = 81;
export const WALL_V_BASE = 145;
export const NMOVES = 209;
export const WALLS_PER_PLAYER = 10;

/* Directions : 0=N(+9) 1=S(-9) 2=E(+1) 3=O(-1) ; bits 1,2,4,8 */
export const DELTA = new Int32Array([9, -9, 1, -1]);
export const BIT = new Int32Array([1, 2, 4, 8]);
/** perpendiculaires utilisées par la règle de saut en diagonale */
export const PERP = [[2, 3], [2, 3], [0, 1], [0, 1]];

/* ─────────── tables précalculées ─────────── */

const BASE_ADJ = new Uint8Array(NCELLS);
for (let r = 0; r < SIZE; r++) {
  for (let c = 0; c < SIZE; c++) {
    let m = 0;
    if (r < 8) m |= 1;
    if (r > 0) m |= 2;
    if (c < 8) m |= 4;
    if (c > 0) m |= 8;
    BASE_ADJ[r * 9 + c] = m;
  }
}

/**
 * Identifiant d'arête (144 arêtes) :
 *   0..71   arêtes nord/sud, id = case inférieure
 *   72..143 arêtes est/ouest, id = 72 + row*8 + col_gauche
 */
export function edgeId(a, b) {
  const m = a < b ? a : b;
  return (b - a === 9 || a - b === 9) ? m : 72 + ((m / 9) | 0) * 8 + (m % 9);
}

/** Les 2 arêtes coupées par chaque mur, indexées par orient*64+slot. */
const WALL_EDGES = new Int32Array(128 * 2);
for (let slot = 0; slot < NSLOTS; slot++) {
  const wr = slot >> 3, wc = slot & 7;
  WALL_EDGES[slot * 2] = wr * 9 + wc;
  WALL_EDGES[slot * 2 + 1] = wr * 9 + wc + 1;
  const v = (64 + slot) * 2;
  WALL_EDGES[v] = 72 + wr * 8 + wc;
  WALL_EDGES[v + 1] = 72 + (wr + 1) * 8 + wc;
}

/**
 * Jonctions du treillis (11 lignes x 11 colonnes -> on n'en utilise que 10x10)
 * touchées par chaque mur. Un mur relie 3 jonctions alignées (ses 2 extrémités
 * et son milieu). Indexé par (orient*64+slot)*3.
 */
const WALL_NODES = new Int32Array(128 * 3);
for (let slot = 0; slot < NSLOTS; slot++) {
  const wr = slot >> 3, wc = slot & 7;
  const h = slot * 3;
  WALL_NODES[h] = (wr + 1) * 10 + wc;
  WALL_NODES[h + 1] = (wr + 1) * 10 + wc + 1;
  WALL_NODES[h + 2] = (wr + 1) * 10 + wc + 2;
  const v = (64 + slot) * 3;
  WALL_NODES[v] = wr * 10 + (wc + 1);
  WALL_NODES[v + 1] = (wr + 1) * 10 + (wc + 1);
  WALL_NODES[v + 2] = (wr + 2) * 10 + (wc + 1);
}

/* ─────────── Zobrist ─────────── */

function mulberry32(a) {
  return function () {
    a |= 0; a = (a + 0x6D2B79F5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0);
  };
}
const _rnd = mulberry32(0x51D0FACE);
const Z_PAWN_LO = new Uint32Array(2 * NCELLS), Z_PAWN_HI = new Uint32Array(2 * NCELLS);
const Z_WALL_LO = new Uint32Array(128), Z_WALL_HI = new Uint32Array(128);
const Z_LEFT_LO = new Uint32Array(2 * (WALLS_PER_PLAYER + 1));
const Z_LEFT_HI = new Uint32Array(2 * (WALLS_PER_PLAYER + 1));
for (let i = 0; i < Z_PAWN_LO.length; i++) { Z_PAWN_LO[i] = _rnd(); Z_PAWN_HI[i] = _rnd(); }
for (let i = 0; i < Z_WALL_LO.length; i++) { Z_WALL_LO[i] = _rnd(); Z_WALL_HI[i] = _rnd(); }
for (let i = 0; i < Z_LEFT_LO.length; i++) { Z_LEFT_LO[i] = _rnd(); Z_LEFT_HI[i] = _rnd(); }
const Z_TURN_LO = _rnd(), Z_TURN_HI = _rnd();

/* ─────────── scratch partagé (aucune allocation en recherche) ─────────── */

const _stamp = new Int32Array(NCELLS);
const _dist = new Int32Array(NCELLS);
const _par = new Int32Array(NCELLS);
const _queue = new Int32Array(NCELLS);
const _cnt = new Float64Array(NCELLS);
let _stampGen = 0;

/* ─────────── helpers de coups ─────────── */

export const isWallMove = (m) => m >= WALL_H_BASE;
export const wallOrient = (m) => (m >= WALL_V_BASE ? VERT : HORIZ);
export const wallSlot = (m) => (m >= WALL_V_BASE ? m - WALL_V_BASE : m - WALL_H_BASE);
export const wallMove = (orient, slot) => (orient === HORIZ ? WALL_H_BASE : WALL_V_BASE) + slot;

const FILES = 'abcdefghi';

/** Coup entier -> notation type "e2" / "he5" / "ve5". */
export function moveToNotation(m) {
  if (!isWallMove(m)) return FILES[m % 9] + (((m / 9) | 0) + 1);
  const slot = wallSlot(m);
  return (wallOrient(m) === HORIZ ? 'h' : 'v') + FILES[slot & 7] + ((slot >> 3) + 1);
}

/** Notation -> coup entier, ou -1 si la chaîne est invalide. */
export function notationToMove(s) {
  s = String(s).trim().toLowerCase();
  if (/^[a-i][1-9]$/.test(s)) return (+s[1] - 1) * 9 + FILES.indexOf(s[0]);
  if (/^[hv][a-h][1-8]$/.test(s)) {
    const slot = (+s[2] - 1) * 8 + FILES.indexOf(s[1]);
    return wallMove(s[0] === 'h' ? HORIZ : VERT, slot);
  }
  return -1;
}

/* ═══════════════════════════ Position ═══════════════════════════ */

export class Position {
  constructor() {
    this.adj = new Uint8Array(NCELLS);
    this.slot = new Int8Array(NSLOTS);       // -1 vide, 0 mur H, 1 mur V
    this.pawn = new Int32Array(2);
    this.left = new Int32Array(2);
    this.turn = 0;
    this.hashLo = 0; this.hashHi = 0;
    this.wallLo = 0; this.wallHi = 0;   // signature des seuls murs posés
    this._sp = 0;
    this._undo = new Int32Array(1024);
    // cache de plus court chemin, invalidé à chaque coup
    this._pathLen = new Int32Array(2);
    this._pathValid = [false, false];
    this._pathEdge = [new Uint8Array(144), new Uint8Array(144)];
    this._pathStamp = new Int32Array(2);
    this._edgeGen = 0;
    this._nearStamp = new Int32Array(NSLOTS);
    this._nearGen = 0;
    // union-find sur les jonctions, avec annulation : sert à savoir si un mur
    // referme un cycle (condition nécessaire pour couper le plateau)
    this._dsuP = new Int32Array(100);
    this._dsuN = new Int32Array(100);
    this._dsuStack = new Int32Array(256);
    this._dsuSp = 0;
    this._undoDsu = new Int32Array(1024);
    this.reset();
  }

  reset() {
    this.adj.set(BASE_ADJ);
    this.slot.fill(-1);
    this.pawn[0] = 4;            // e1
    this.pawn[1] = 76;           // e9
    this.left[0] = WALLS_PER_PLAYER;
    this.left[1] = WALLS_PER_PLAYER;
    this.turn = 0;
    this._sp = 0;
    this._dsuInit();
    this._invalidate();
    this._rehash();
    return this;
  }

  clone() {
    const p = new Position();
    p.adj.set(this.adj); p.slot.set(this.slot);
    p.pawn.set(this.pawn); p.left.set(this.left);
    p.turn = this.turn; p.hashLo = this.hashLo; p.hashHi = this.hashHi;
    p.wallLo = this.wallLo; p.wallHi = this.wallHi;
    p._dsuP.set(this._dsuP); p._dsuN.set(this._dsuN); p._dsuSp = 0;
    p._invalidate();
    return p;
  }

  _invalidate() { this._pathValid[0] = false; this._pathValid[1] = false; }

  _rehash() {
    let lo = 0, hi = 0, wlo = 0, whi = 0;
    for (let p = 0; p < 2; p++) {
      const i = p * NCELLS + this.pawn[p];
      lo ^= Z_PAWN_LO[i]; hi ^= Z_PAWN_HI[i];
      const j = p * (WALLS_PER_PLAYER + 1) + this.left[p];
      lo ^= Z_LEFT_LO[j]; hi ^= Z_LEFT_HI[j];
    }
    for (let s = 0; s < NSLOTS; s++) {
      if (this.slot[s] < 0) continue;
      const i = this.slot[s] * 64 + s;
      lo ^= Z_WALL_LO[i]; hi ^= Z_WALL_HI[i];
      wlo ^= Z_WALL_LO[i]; whi ^= Z_WALL_HI[i];
    }
    if (this.turn) { lo ^= Z_TURN_LO; hi ^= Z_TURN_HI; }
    this.hashLo = lo >>> 0; this.hashHi = hi >>> 0;
    this.wallLo = wlo >>> 0; this.wallHi = whi >>> 0;
  }

  /** -1 si la partie continue, sinon l'indice du gagnant. */
  winner() {
    if (this.pawn[0] >= 72) return 0;
    if (this.pawn[1] <= 8) return 1;
    return -1;
  }

  /* ─────────── murs ─────────── */

  _carve(orient, slot, open) {
    const wr = slot >> 3, wc = slot & 7, a = this.adj;
    if (orient === HORIZ) {
      const t0 = wr * 9 + wc, t1 = t0 + 1;
      if (open) { a[t0] |= 1; a[t1] |= 1; a[t0 + 9] |= 2; a[t1 + 9] |= 2; }
      else { a[t0] &= ~1; a[t1] &= ~1; a[t0 + 9] &= ~2; a[t1 + 9] &= ~2; }
    } else {
      const l0 = wr * 9 + wc, l1 = l0 + 9;
      if (open) { a[l0] |= 4; a[l1] |= 4; a[l0 + 1] |= 8; a[l1 + 1] |= 8; }
      else { a[l0] &= ~4; a[l1] &= ~4; a[l0 + 1] &= ~8; a[l1 + 1] &= ~8; }
    }
  }

  /** Le mur tient-il géométriquement (pas de recouvrement ni de croisement) ? */
  wallFits(orient, slot) {
    if (this.slot[slot] !== -1) return false;
    if (orient === HORIZ) {
      const wc = slot & 7;
      if (wc > 0 && this.slot[slot - 1] === HORIZ) return false;
      if (wc < 7 && this.slot[slot + 1] === HORIZ) return false;
    } else {
      const wr = slot >> 3;
      if (wr > 0 && this.slot[slot - 8] === VERT) return false;
      if (wr < 7 && this.slot[slot + 8] === VERT) return false;
    }
    return true;
  }

  /* ─────────── plus courts chemins ─────────── */

  /**
   * BFS de la case du pion jusqu'à sa rangée d'arrivée.
   * Les pions ne bloquent pas (on peut toujours sauter par-dessus).
   * @returns {number} longueur, ou -1 si aucun chemin
   */
  distance(player) {
    const goalHigh = player === 0;
    const start = this.pawn[player], adj = this.adj;
    if (goalHigh ? start >= 72 : start <= 8) return 0;
    const gen = ++_stampGen;
    _stamp[start] = gen; _dist[start] = 0;
    let qh = 0, qt = 0;
    _queue[qt++] = start;
    while (qh < qt) {
      const c = _queue[qh++], d = _dist[c] + 1, mask = adj[c];
      for (let k = 0; k < 4; k++) {
        if (!(mask & BIT[k])) continue;
        const n = c + DELTA[k];
        if (_stamp[n] === gen) continue;
        if (goalHigh ? n >= 72 : n <= 8) return d;
        _stamp[n] = gen; _dist[n] = d; _queue[qt++] = n;
      }
    }
    return -1;
  }

  /**
   * Fragilité du chemin par coût de détour : de combien s'allonge le trajet
   * si le plus court chemin actuel est coupé ? On relance un BFS en
   * interdisant les arêtes du chemin principal (déjà marquées en cache).
   * Détour nul ou faible = position robuste, un mur adverse ne coûte presque
   * rien ; détour 31 (saturation ou aucune alternative) = chemin unique,
   * fragilité maximale.
   * @returns {number} (len << 5) | min(détour, 31), ou -1 si aucun chemin
   */
  pathFragility(player) {
    const len = this._buildPath(player);
    if (len < 0) return -1;
    if (len === 0) return 0;
    const goalHigh = player === 0;
    const start = this.pawn[player], adj = this.adj;
    const banned = this._pathEdge[player];
    const gen = ++_stampGen;
    _stamp[start] = gen; _dist[start] = 0;
    let qh = 0, qt = 0;
    _queue[qt++] = start;
    let alt = -1;
    outer:
    while (qh < qt) {
      const c = _queue[qh++], d = _dist[c] + 1, mask = adj[c];
      for (let k = 0; k < 4; k++) {
        if (!(mask & BIT[k])) continue;
        const n = c + DELTA[k];
        if (_stamp[n] === gen) continue;
        if (banned[edgeId(c, n)]) continue;          // arête du chemin principal
        if (goalHigh ? n >= 72 : n <= 8) { alt = d; break outer; }
        _stamp[n] = gen; _dist[n] = d; _queue[qt++] = n;
      }
    }
    const detour = alt < 0 ? 31 : Math.min(alt - len, 31);
    return (len << 5) | detour;
  }

  /** Version booléenne, sortie anticipée — utilisée pour la légalité des murs. */
  hasPath(player) {
    const goalHigh = player === 0;
    const start = this.pawn[player], adj = this.adj;
    if (goalHigh ? start >= 72 : start <= 8) return true;
    const gen = ++_stampGen;
    _stamp[start] = gen;
    let qh = 0, qt = 0;
    _queue[qt++] = start;
    while (qh < qt) {
      const c = _queue[qh++], mask = adj[c];
      for (let k = 0; k < 4; k++) {
        if (!(mask & BIT[k])) continue;
        const n = c + DELTA[k];
        if (_stamp[n] === gen) continue;
        if (goalHigh ? n >= 72 : n <= 8) return true;
        _stamp[n] = gen; _queue[qt++] = n;
      }
    }
    return false;
  }

  /**
   * Calcule le plus court chemin et marque ses arêtes, pour pouvoir
   * savoir instantanément si un mur donné peut l'affecter.
   */
  _buildPath(player) {
    if (this._pathValid[player]) return this._pathLen[player];
    const goalHigh = player === 0;
    const start = this.pawn[player], adj = this.adj;
    const mark = this._pathEdge[player];
    const stampVal = ++this._edgeGen;
    this._pathStamp[player] = stampVal;
    let end = -1, len = -1;
    if (goalHigh ? start >= 72 : start <= 8) { len = 0; }
    else {
      const gen = ++_stampGen;
      _stamp[start] = gen; _dist[start] = 0; _par[start] = -1;
      let qh = 0, qt = 0;
      _queue[qt++] = start;
      outer:
      while (qh < qt) {
        const c = _queue[qh++], d = _dist[c] + 1, mask = adj[c];
        for (let k = 0; k < 4; k++) {
          if (!(mask & BIT[k])) continue;
          const n = c + DELTA[k];
          if (_stamp[n] === gen) continue;
          _stamp[n] = gen; _dist[n] = d; _par[n] = c; _queue[qt++] = n;
          if (goalHigh ? n >= 72 : n <= 8) { end = n; len = d; break outer; }
        }
      }
    }
    if (len > 0) {
      mark.fill(0);
      for (let c = end; _par[c] !== -1; c = _par[c]) mark[edgeId(c, _par[c])] = 1;
    } else if (len === 0) {
      mark.fill(0);
    }
    this._pathLen[player] = len;
    this._pathValid[player] = len >= 0;
    return len;
  }

  /** Le mur croise-t-il le plus court chemin mis en cache de ce joueur ? */
  _wallHitsPath(orient, slot, player) {
    const i = (orient * 64 + slot) * 2, mark = this._pathEdge[player];
    return mark[WALL_EDGES[i]] === 1 || mark[WALL_EDGES[i + 1]] === 1;
  }

  /**
   * Légalité complète d'un mur : géométrie + les deux joueurs gardent un chemin.
   * Le BFS n'est relancé que si le mur touche réellement le chemin du joueur.
   */
  wallLegal(orient, slot) {
    if (this.left[this.turn] <= 0) return false;
    if (!this.wallFits(orient, slot)) return false;
    const p0 = this._buildPath(0), p1 = this._buildPath(1);
    if (p0 < 0 || p1 < 0) return false;
    const hit0 = this._wallHitsPath(orient, slot, 0);
    const hit1 = this._wallHitsPath(orient, slot, 1);
    if (!hit0 && !hit1) return true;                 // ne peut rien couper
    if (!this._wouldCycle(orient, slot)) return true; // ne referme aucun cycle
    this._carve(orient, slot, false);
    let ok = true;
    if (hit0 && !this.hasPath(0)) ok = false;
    if (ok && hit1 && !this.hasPath(1)) ok = false;
    this._carve(orient, slot, true);
    return ok;
  }

  /* ─────────── déplacements du pion ─────────── */

  /**
   * Écrit les destinations légales du pion dans `out` à partir de `n`.
   * Applique la règle officielle du saut : saut droit si la case derrière
   * est libre, sinon les deux diagonales.
   * @returns {number} nouvel indice d'écriture
   */
  pawnMoves(out, n) {
    const me = this.pawn[this.turn], opp = this.pawn[1 - this.turn], adj = this.adj;
    const mask = adj[me];
    for (let k = 0; k < 4; k++) {
      if (!(mask & BIT[k])) continue;
      const step = me + DELTA[k];
      if (step !== opp) { out[n++] = step; continue; }
      if (adj[step] & BIT[k]) {            // saut droit possible
        out[n++] = step + DELTA[k];
      } else {                             // mur ou bord derrière -> diagonales
        const pp = PERP[k];
        for (let j = 0; j < 2; j++) {
          const d = pp[j];
          if (adj[step] & BIT[d]) out[n++] = step + DELTA[d];
        }
      }
    }
    return n;
  }

  /* ─────────── génération de coups ─────────── */

  /**
   * @param {Int32Array} out tampon de taille >= 209
   * @param {boolean} [wallsToo=true] inclure les poses de mur
   * @returns {number} nombre de coups écrits
   */
  legalMoves(out, wallsToo = true) {
    let n = this.pawnMoves(out, 0);
    if (!wallsToo || this.left[this.turn] <= 0) return n;
    for (let orient = 0; orient < 2; orient++) {
      for (let slot = 0; slot < NSLOTS; slot++) {
        if (this.wallLegal(orient, slot)) out[n++] = wallMove(orient, slot);
      }
    }
    return n;
  }

  /** Un coup entier est-il légal dans cette position ? */
  isLegal(m) {
    if (m < 0 || m >= NMOVES) return false;
    if (isWallMove(m)) return this.wallLegal(wallOrient(m), wallSlot(m));
    const buf = new Int32Array(5);
    const n = this.pawnMoves(buf, 0);
    for (let i = 0; i < n; i++) if (buf[i] === m) return true;
    return false;
  }

  /* ─────────── application / annulation ─────────── */

  doMove(m) {
    const t = this.turn;
    if (isWallMove(m)) {
      const orient = wallOrient(m), slot = wallSlot(m);
      this._carve(orient, slot, false);
      this.slot[slot] = orient;
      const zi = orient * 64 + slot;
      this.hashLo ^= Z_WALL_LO[zi]; this.hashHi ^= Z_WALL_HI[zi];
      this.wallLo = (this.wallLo ^ Z_WALL_LO[zi]) >>> 0;
      this.wallHi = (this.wallHi ^ Z_WALL_HI[zi]) >>> 0;
      const before = t * (WALLS_PER_PLAYER + 1) + this.left[t];
      this.left[t]--;
      const after = t * (WALLS_PER_PLAYER + 1) + this.left[t];
      this.hashLo ^= Z_LEFT_LO[before] ^ Z_LEFT_LO[after];
      this.hashHi ^= Z_LEFT_HI[before] ^ Z_LEFT_HI[after];
      this._undoDsu[this._sp] = this._dsuSp;
      const ni = (orient * 64 + slot) * 3;
      this._dsuUnion(WALL_NODES[ni], WALL_NODES[ni + 1]);
      this._dsuUnion(WALL_NODES[ni + 1], WALL_NODES[ni + 2]);
      this._undo[this._sp++] = -1;
    } else {
      const from = this.pawn[t];
      const a = t * NCELLS + from, b = t * NCELLS + m;
      this.hashLo ^= Z_PAWN_LO[a] ^ Z_PAWN_LO[b];
      this.hashHi ^= Z_PAWN_HI[a] ^ Z_PAWN_HI[b];
      this.pawn[t] = m;
      this._undo[this._sp++] = from;
    }
    this.turn = 1 - t;
    this.hashLo ^= Z_TURN_LO; this.hashHi ^= Z_TURN_HI;
    this._invalidate();
    this.hashLo >>>= 0; this.hashHi >>>= 0;
  }

  undoMove(m) {
    this.turn = 1 - this.turn;
    const t = this.turn;
    const from = this._undo[--this._sp];
    if (isWallMove(m)) {
      const orient = wallOrient(m), slot = wallSlot(m);
      this._dsuRollback(this._undoDsu[this._sp]);
      this._carve(orient, slot, true);
      this.slot[slot] = -1;
      const zi = orient * 64 + slot;
      this.hashLo ^= Z_WALL_LO[zi]; this.hashHi ^= Z_WALL_HI[zi];
      this.wallLo = (this.wallLo ^ Z_WALL_LO[zi]) >>> 0;
      this.wallHi = (this.wallHi ^ Z_WALL_HI[zi]) >>> 0;
      const before = t * (WALLS_PER_PLAYER + 1) + this.left[t];
      this.left[t]++;
      const after = t * (WALLS_PER_PLAYER + 1) + this.left[t];
      this.hashLo ^= Z_LEFT_LO[before] ^ Z_LEFT_LO[after];
      this.hashHi ^= Z_LEFT_HI[before] ^ Z_LEFT_HI[after];
    } else {
      const a = t * NCELLS + this.pawn[t], b = t * NCELLS + from;
      this.hashLo ^= Z_PAWN_LO[a] ^ Z_PAWN_LO[b];
      this.hashHi ^= Z_PAWN_HI[a] ^ Z_PAWN_HI[b];
      this.pawn[t] = from;
    }
    this.hashLo ^= Z_TURN_LO; this.hashHi ^= Z_TURN_HI;
    this._invalidate();
    this.hashLo >>>= 0; this.hashHi >>>= 0;
  }

  /* ─────────── union-find sur les jonctions ─────────── */

  _dsuInit() {
    const P = this._dsuP, N = this._dsuN;
    for (let i = 0; i < 100; i++) { P[i] = i; N[i] = 1; }
    this._dsuSp = 0;
    // tout le bord extérieur ne forme qu'un seul noeud
    let first = -1;
    for (let i = 0; i < 10; i++) {
      for (let k = 0; k < 10; k++) {
        if (i !== 0 && i !== 9 && k !== 0 && k !== 9) continue;
        const id = i * 10 + k;
        if (first < 0) first = id; else this._dsuUnion(first, id);
      }
    }
    this._dsuSp = 0;   // le bord fait partie de l'état de base, jamais annulé
  }

  _dsuFind(x) {
    const P = this._dsuP;
    while (P[x] !== x) x = P[x];
    return x;
  }

  _dsuUnion(a, b) {
    let ra = this._dsuFind(a), rb = this._dsuFind(b);
    if (ra === rb) return false;
    const N = this._dsuN;
    if (N[ra] < N[rb]) { const t = ra; ra = rb; rb = t; }
    this._dsuP[rb] = ra; N[ra] += N[rb];
    this._dsuStack[this._dsuSp++] = rb;
    return true;
  }

  _dsuRollback(sp) {
    const P = this._dsuP, N = this._dsuN;
    while (this._dsuSp > sp) {
      const rb = this._dsuStack[--this._dsuSp];
      N[P[rb]] -= N[rb];
      P[rb] = rb;
    }
  }

  /**
   * Le mur refermerait-il un cycle dans le treillis (bord compris) ?
   * Théorème (planarité) : sans nouveau cycle, aucune séparation possible —
   * on peut donc sauter entièrement le BFS de légalité.
   */
  _wouldCycle(orient, slot) {
    const i = (orient * 64 + slot) * 3;
    const a = this._dsuFind(WALL_NODES[i]);
    const b = this._dsuFind(WALL_NODES[i + 1]);
    const c = this._dsuFind(WALL_NODES[i + 2]);
    return a === b || b === c || a === c;
  }

  /**
   * Marque, par estampille, les emplacements voisins d'un mur déjà posé.
   * On balaie les murs posés (au plus 20) au lieu de tester les 64 slots.
   */
  _markNear() {
    const gen = ++this._nearGen, stamp = this._nearStamp;
    for (let s = 0; s < NSLOTS; s++) {
      if (this.slot[s] < 0) continue;
      const wr = s >> 3, wc = s & 7;
      for (let dr = -1; dr <= 1; dr++) {
        const r = wr + dr;
        if (r < 0 || r > 7) continue;
        for (let dc = -1; dc <= 1; dc++) {
          const c = wc + dc;
          if (c < 0 || c > 7) continue;
          stamp[r * 8 + c] = gen;
        }
      }
    }
    return gen;
  }

  /**
   * Murs « intéressants » seulement : ceux qui coupent l'un des deux plus
   * courts chemins, plus ceux qui prolongent un mur existant. Fait tomber le
   * facteur de branchement de ~128 à ~25 sans perte de force notable
   * (mesurée en tournoi, cf. arena.js).
   *
   * Légalité inlinée : un mur qui ne touche aucun des deux plus courts
   * chemins ne peut couper personne, on saute donc le BFS.
   * @returns {number} nouvel indice d'écriture
   */
  candidateWalls(out, n, includeAdjacent = true) {
    if (this.left[this.turn] <= 0) return n;
    if (this._buildPath(0) < 0 || this._buildPath(1) < 0) return n;
    const gen = includeAdjacent ? this._markNear() : -1;
    const stamp = this._nearStamp;
    const e0 = this._pathEdge[0], e1 = this._pathEdge[1];
    for (let orient = 0; orient < 2; orient++) {
      const base = orient * 64;
      for (let slot = 0; slot < NSLOTS; slot++) {
        if (!this.wallFits(orient, slot)) continue;
        const i = (base + slot) * 2;
        const eA = WALL_EDGES[i], eB = WALL_EDGES[i + 1];
        const hit0 = e0[eA] === 1 || e0[eB] === 1;
        const hit1 = e1[eA] === 1 || e1[eB] === 1;
        if (!hit0 && !hit1) {
          // ne croise aucun chemin -> ne peut enfermer personne : légal d'office
          if (includeAdjacent && stamp[slot] === gen) out[n++] = wallMove(orient, slot);
          continue;
        }
        if (!this._wouldCycle(orient, slot)) { out[n++] = wallMove(orient, slot); continue; }
        this._carve(orient, slot, false);
        let ok = true;
        if (hit0 && !this.hasPath(0)) ok = false;
        if (ok && hit1 && !this.hasPath(1)) ok = false;
        this._carve(orient, slot, true);
        if (ok) out[n++] = wallMove(orient, slot);
      }
    }
    return n;
  }

  /** Ce mur coupe-t-il le plus court chemin de ce joueur ? (API publique) */
  wallOnPath(orient, slot, player) {
    if (this._buildPath(player) < 0) return false;
    return this._wallHitsPath(orient, slot, player);
  }

  /* ─────────── sérialisation ─────────── */

  toJSON() {
    const walls = [];
    for (let s = 0; s < NSLOTS; s++) {
      if (this.slot[s] >= 0) walls.push(moveToNotation(wallMove(this.slot[s], s)));
    }
    return {
      pawns: [moveToNotation(this.pawn[0]), moveToNotation(this.pawn[1])],
      walls,
      wallsLeft: [this.left[0], this.left[1]],
      turn: this.turn
    };
  }

  /** Reconstruit une position depuis la notation (les murs sont posés en alternance). */
  static fromMoves(list) {
    const p = new Position();
    for (const s of list) {
      const m = typeof s === 'number' ? s : notationToMove(s);
      if (m < 0 || !p.isLegal(m)) throw new Error('coup illégal : ' + s);
      p.doMove(m);
    }
    return p;
  }

  toString() {
    const rows = [];
    for (let r = 8; r >= 0; r--) {
      let line = (r + 1) + ' ';
      for (let c = 0; c < 9; c++) {
        const cell = r * 9 + c;
        line += this.pawn[0] === cell ? ' R' : this.pawn[1] === cell ? ' B' : ' .';
        if (c < 8) line += (this.adj[cell] & 4) ? ' ' : '|';
      }
      rows.push(line);
      if (r > 0) {
        let sep = '  ';
        for (let c = 0; c < 9; c++) {
          sep += (this.adj[r * 9 + c] & 2) ? '  ' : ' ─';
          if (c < 8) sep += ' ';
        }
        rows.push(sep);
      }
    }
    rows.push('   a b c d e f g h i');
    rows.push(`murs R:${this.left[0]} B:${this.left[1]} — trait aux ${this.turn === 0 ? 'rouges' : 'bleus'}`);
    return rows.join('\n');
  }
}
