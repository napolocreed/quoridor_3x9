/**
 * Quoridor — évaluation, recherche et agents.
 *
 * Recherche : negamax fail-soft avec élagage alpha-bêta, approfondissement
 * itératif, table de transposition Zobrist, killer moves, heuristique
 * d'historique, et réduction du facteur de branchement par filtrage des
 * murs candidats.
 *
 * @module ai
 */
import {
  Position, wallOrient, wallSlot, moveToNotation, NMOVES
} from './engine.js';
import { RaceCache } from './race.js';

export const MATE = 1_000_000;
const MAXPLY = 64;
const ABORT = Symbol('abort');

/* ═══════════════ évaluation ═══════════════ */

/** Poids par défaut (affinés par auto-apprentissage, cf. tune.js). */
export const DEFAULT_WEIGHTS = {
  path: 100,    // différence de plus court chemin — terme dominant
  wall: 12,     // murs restants : des munitions
  prog: 3,      // rangées déjà gagnées
  tempo: 8,     // avantage du trait
  hoard: 0,     // valeur croissante des murs quand l'adversaire approche
  frag: 0       // robustesse du chemin : log2(nb de plus courts chemins)
};

/**
 * Score du point de vue du joueur au trait.
 * @param {Position} pos
 * @param {typeof DEFAULT_WEIGHTS} w
 */
export function evaluate(pos, w) {
  const me = pos.turn, opp = 1 - me;
  let dMe, dOpp, fragTerm = 0;
  if (w.frag) {
    // coût de détour : un chemin dont l'alternative est chère se coupe d'un
    // mur ; la fragilité de l'adversaire ne vaut que si l'on a des murs.
    const fMe = pos.pathFragility(me), fOpp = pos.pathFragility(opp);
    dMe = fMe < 0 ? -1 : fMe >> 5;
    dOpp = fOpp < 0 ? -1 : fOpp >> 5;
    if (fMe >= 0 && fOpp >= 0) {
      fragTerm = w.frag * ((pos.left[me] > 0 ? (fOpp & 31) : 0)
                         - (pos.left[opp] > 0 ? (fMe & 31) : 0));
    }
  } else {
    dMe = pos.distance(me);
    dOpp = pos.distance(opp);
  }
  if (dMe < 0) return -MATE / 2;
  if (dOpp < 0) return MATE / 2;
  if (dMe === 0) return MATE / 2;
  if (dOpp === 0) return -MATE / 2;

  const rowMe = me === 0 ? (pos.pawn[0] / 9) | 0 : 8 - (((pos.pawn[1] / 9) | 0));
  const rowOpp = opp === 0 ? (pos.pawn[0] / 9) | 0 : 8 - (((pos.pawn[1] / 9) | 0));

  let s = w.path * (dOpp - dMe)
        + w.wall * (pos.left[me] - pos.left[opp])
        + w.prog * (rowMe - rowOpp)
        + w.tempo
        + fragTerm;

  if (w.hoard) {
    // un mur vaut plus cher quand l'adversaire est près d'arriver
    s += w.hoard * (pos.left[me] / (dOpp + 1) - pos.left[opp] / (dMe + 1));
  }
  return s | 0;
}

/* ═══════════════ table de transposition ═══════════════ */

const TT_BITS = 19;
const TT_SIZE = 1 << TT_BITS;
const TT_MASK = TT_SIZE - 1;
const EXACT = 0, LOWER = 1, UPPER = 2;

/* ═══════════════ moteur de recherche ═══════════════ */

export class SearchEngine {
  /**
   * @param {object} [opts]
   * @param {typeof DEFAULT_WEIGHTS} [opts.weights]
   * @param {boolean} [opts.useTT=true]
   * @param {boolean} [opts.pruneWalls=true] restreindre les murs candidats
   */
  constructor(opts = {}) {
    this.w = { ...DEFAULT_WEIGHTS, ...(opts.weights || {}) };
    this.useTT = opts.useTT !== false;
    this.pruneWalls = opts.pruneWalls !== false;
    // oracle de fin de partie : stocks épuisés -> valeur exacte de la course
    this.race = opts.useRace !== false ? new RaceCache() : null;

    this.ttKeyLo = new Uint32Array(TT_SIZE);
    this.ttKeyHi = new Uint32Array(TT_SIZE);
    this.ttMove = new Int16Array(TT_SIZE);
    this.ttScore = new Int32Array(TT_SIZE);
    this.ttDepth = new Int8Array(TT_SIZE);
    this.ttFlag = new Int8Array(TT_SIZE);
    this.ttAge = new Uint8Array(TT_SIZE);
    this.age = 0;

    this.killer = new Int32Array(MAXPLY * 2).fill(-1);
    this.history = new Int32Array(2 * NMOVES);

    // tampons de coups par profondeur (zéro allocation en recherche)
    this.moveBuf = [];
    this.scoreBuf = [];
    for (let i = 0; i < MAXPLY; i++) {
      this.moveBuf.push(new Int32Array(256));
      this.scoreBuf.push(new Int32Array(256));
    }
    this.nodes = 0;
    this.deadline = Infinity;
    // pile des coups appliqués : quand la limite de temps déclenche une
    // exception au milieu de la récursion, les undoMove en attente sautent.
    // Il faut pouvoir dérouler à la main, sinon la position reste corrompue.
    this.applied = new Int32Array(MAXPLY + 8);
    this.appliedTop = 0;
  }

  clearTables() {
    this.ttKeyLo.fill(0); this.ttKeyHi.fill(0); this.ttDepth.fill(0);
    this.killer.fill(-1); this.history.fill(0);
  }

  /* ─────── génération + tri ─────── */

  _generate(pos, ply, ttMove) {
    const buf = this.moveBuf[ply], sc = this.scoreBuf[ply];
    let n, nPawn;
    if (this.pruneWalls) {
      n = nPawn = pos.pawnMoves(buf, 0);
      n = pos.candidateWalls(buf, n, true);
    } else {
      nPawn = pos.pawnMoves(buf, 0);
      n = pos.legalMoves(buf, true);   // régénère les pions en 0..nPawn-1 puis les murs
    }

    const side = pos.turn;
    const k1 = this.killer[ply * 2], k2 = this.killer[ply * 2 + 1];
    const opp = 1 - side;
    const myDist = pos.distance(side);

    for (let i = 0; i < n; i++) {
      const m = buf[i];
      let s;
      if (m === ttMove) s = 1 << 30;
      else if (m === k1) s = 1 << 29;
      else if (m === k2) s = (1 << 29) - 1;
      else if (i < nPawn) {
        // un pas qui raccourcit notre chemin est presque toujours jouable
        const from = pos.pawn[side];
        pos.pawn[side] = m;
        pos._invalidate();
        const d = pos.distance(side);
        pos.pawn[side] = from;
        pos._invalidate();
        s = (1 << 28) + (myDist - d) * 4096 + this.history[side * NMOVES + m];
      } else {
        // un mur qui coupe le chemin adverse d'abord
        const orient = wallOrient(m), slot = wallSlot(m);
        const hitsOpp = pos.wallOnPath(orient, slot, opp) ? 1 : 0;
        const hitsMe = pos.wallOnPath(orient, slot, side) ? 1 : 0;
        s = hitsOpp * (1 << 27) - hitsMe * (1 << 26) + this.history[side * NMOVES + m];
      }
      sc[i] = s;
    }
    return n;
  }

  /* ─────── negamax ─────── */

  _negamax(pos, depth, alpha, beta, ply) {
    if ((++this.nodes & 1023) === 0 && Date.now() > this.deadline) throw ABORT;

    // stocks épuisés : la course est résolue exactement, ce nœud est une feuille
    if (this.race && pos.left[0] === 0 && pos.left[1] === 0) {
      const v = this.race.get(pos).probe(pos.pawn[0], pos.pawn[1], pos.turn);
      return v > 0 ? MATE - ply - v : v < 0 ? -MATE + ply - v : 0;
    }

    const alphaOrig = alpha;
    let ttMove = -1;

    if (this.useTT) {
      const i = (pos.hashLo & TT_MASK) >>> 0;
      if (this.ttKeyLo[i] === pos.hashLo && this.ttKeyHi[i] === pos.hashHi) {
        ttMove = this.ttMove[i];
        if (this.ttDepth[i] >= depth) {
          const s = this.ttScore[i], f = this.ttFlag[i];
          if (f === EXACT) return s;
          if (f === LOWER && s > alpha) alpha = s;
          else if (f === UPPER && s < beta) beta = s;
          if (alpha >= beta) return s;
        }
      }
    }

    if (depth <= 0) return evaluate(pos, this.w);

    const n = this._generate(pos, ply, ttMove);
    if (n === 0) return evaluate(pos, this.w);

    const buf = this.moveBuf[ply], sc = this.scoreBuf[ply];
    const side = pos.turn;
    let best = -MATE * 2, bestMove = buf[0];

    for (let i = 0; i < n; i++) {
      // tri par sélection : on ne trie que ce qu'on consomme réellement
      let bi = i;
      for (let j = i + 1; j < n; j++) if (sc[j] > sc[bi]) bi = j;
      if (bi !== i) {
        const tm = buf[i]; buf[i] = buf[bi]; buf[bi] = tm;
        const ts = sc[i]; sc[i] = sc[bi]; sc[bi] = ts;
      }
      const m = buf[i];

      this.applied[this.appliedTop++] = m;
      pos.doMove(m);
      let score;
      if (pos.winner() === side) score = MATE - ply;
      else score = -this._negamax(pos, depth - 1, -beta, -alpha, ply + 1);
      pos.undoMove(m);
      this.appliedTop--;

      if (score > best) { best = score; bestMove = m; }
      if (score > alpha) alpha = score;
      if (alpha >= beta) {
        const kk = ply * 2;
        if (this.killer[kk] !== m) { this.killer[kk + 1] = this.killer[kk]; this.killer[kk] = m; }
        this.history[side * NMOVES + m] += depth * depth;
        break;
      }
    }

    if (this.useTT) {
      const i = (pos.hashLo & TT_MASK) >>> 0;
      if (this.ttDepth[i] <= depth || this.ttAge[i] !== this.age) {
        this.ttKeyLo[i] = pos.hashLo; this.ttKeyHi[i] = pos.hashHi;
        this.ttMove[i] = bestMove; this.ttScore[i] = best;
        this.ttDepth[i] = depth; this.ttAge[i] = this.age;
        this.ttFlag[i] = best <= alphaOrig ? UPPER : best >= beta ? LOWER : EXACT;
      }
    }
    return best;
  }

  /**
   * Approfondissement itératif sous contrainte de temps.
   * @param {Position} pos
   * @param {object} [o]
   * @param {number} [o.maxDepth=64]
   * @param {number} [o.maxTimeMs=Infinity]
   * @returns {{move:number, score:number, depth:number, nodes:number, ms:number, pv:string[]}}
   */
  search(pos, o = {}) {
    const maxDepth = o.maxDepth ?? 64;
    const maxTime = o.maxTimeMs ?? Infinity;
    const t0 = Date.now();
    this.deadline = maxTime === Infinity ? Infinity : t0 + maxTime;
    this.nodes = 0;
    this.appliedTop = 0;
    this.age = (this.age + 1) & 255;
    this.killer.fill(-1);

    const root = new Int32Array(256);
    let nRoot = pos.pawnMoves(root, 0);
    nRoot = this.pruneWalls ? pos.candidateWalls(root, nRoot, true) : pos.legalMoves(root, true);
    if (nRoot === 0) return { move: -1, score: 0, depth: 0, nodes: 0, ms: 0, pv: [] };

    let best = root[0], bestScore = 0, reached = 0;

    for (let depth = 1; depth <= maxDepth; depth++) {
      let localBest = -MATE * 2, localMove = best;
      try {
        let alpha = -MATE * 2;
        // le meilleur coup de l'itération précédente en tête
        for (let i = 0; i < nRoot; i++) if (root[i] === best) { const t = root[0]; root[0] = root[i]; root[i] = t; break; }
        for (let i = 0; i < nRoot; i++) {
          const m = root[i];
          this.applied[this.appliedTop++] = m;
          pos.doMove(m);
          let sc;
          if (pos.winner() === 1 - pos.turn) sc = MATE - 0;
          else sc = -this._negamax(pos, depth - 1, -MATE * 2, -alpha, 1);
          pos.undoMove(m);
          this.appliedTop--;
          if (sc > localBest) { localBest = sc; localMove = m; }
          if (sc > alpha) alpha = sc;
        }
      } catch (e) {
        if (e !== ABORT) throw e;
        // dérouler tous les coups restés appliqués avant de rendre la main
        while (this.appliedTop > 0) pos.undoMove(this.applied[--this.appliedTop]);
        break;
      }
      best = localMove; bestScore = localBest; reached = depth;
      if (Math.abs(bestScore) > MATE - 100) break;      // gain forcé trouvé
      if (Date.now() > this.deadline) break;
    }

    return {
      move: best, score: bestScore, depth: reached,
      nodes: this.nodes, ms: Date.now() - t0,
      pv: [moveToNotation(best)]
    };
  }
}

/* ═══════════════ agents ═══════════════ */

/** Générateur pseudo-aléatoire déterministe (parties reproductibles). */
export function rng(seed) {
  let s = seed >>> 0;
  return () => {
    s ^= s << 13; s >>>= 0; s ^= s >> 17; s ^= s << 5; s >>>= 0;
    return s / 4294967296;
  };
}

/**
 * Profils disponibles. `kind` :
 *   'random'  coups légaux au hasard
 *   'greedy'  évaluation à 1 coup, avec un tempérament (goût du mur)
 *   'search'  alpha-bêta complet
 */
export const PROFILES = {
  novice: {
    label: 'Novice', kind: 'random',
    blurb: 'Coups légaux au hasard. Sert de plancher de référence.'
  },
  coureur: {
    label: 'Coureur', kind: 'greedy', wallBias: 0.15, lookahead: false,
    blurb: 'Fonce vers l\'arrivée, ne pose un mur que s\'il est distancé.'
  },
  batisseur: {
    label: 'Bâtisseur', kind: 'greedy', wallBias: 1.6, lookahead: false,
    blurb: 'Aime bloquer : privilégie le mur qui allonge le plus l\'adversaire.'
  },
  tacticien: {
    label: 'Tacticien', kind: 'search', depth: 3, timeMs: 300,
    blurb: 'Alpha-bêta 3 demi-coups. Voit les pièges immédiats.'
  },
  stratege: {
    label: 'Stratège', kind: 'search', depth: 5, timeMs: 1500,
    blurb: 'Alpha-bêta 5 demi-coups avec table de transposition.'
  },
  oracle: {
    label: 'Oracle', kind: 'search', depth: 64, timeMs: 2000,
    blurb: 'Approfondissement itératif sous budget de temps. Le plus fort.'
  }
};

/**
 * Construit un agent jouable.
 * @param {keyof PROFILES|object} profile
 * @param {object} [over] surcharges (depth, timeMs, weights, seed…)
 */
export function createAgent(profile, over = {}) {
  const base = typeof profile === 'string' ? PROFILES[profile] : profile;
  if (!base) throw new Error('profil inconnu : ' + profile);
  const cfg = { ...base, ...over };
  const rand = rng(cfg.seed ?? 0x2F6E2B1 ^ (Date.now() & 0xffff));
  const weights = { ...DEFAULT_WEIGHTS, ...(cfg.weights || {}) };
  const engine = cfg.kind === 'search'
    ? new SearchEngine({
        weights,
        pruneWalls: cfg.pruneWalls !== false,
        useRace: cfg.useRace !== false
      })
    : null;
  const buf = new Int32Array(256);

  const agent = {
    name: cfg.label ?? String(profile),
    kind: cfg.kind,
    blurb: cfg.blurb ?? '',
    config: cfg,
    engine,
    stats: { nodes: 0, ms: 0, moves: 0, depthSum: 0 },

    /**
     * @param {Position} pos
     * @returns {{move:number, info:object}}
     */
    think(pos) {
      const t0 = Date.now();
      let move = -1, info = {};

      if (cfg.kind === 'random') {
        const n = pos.legalMoves(buf);
        move = buf[(rand() * n) | 0];

      } else if (cfg.kind === 'greedy') {
        let n = pos.pawnMoves(buf, 0);
        const nPawn = n;
        n = pos.candidateWalls(buf, n, true);
        const me = pos.turn;
        let bestScore = -Infinity;
        for (let i = 0; i < n; i++) {
          const m = buf[i];
          pos.doMove(m);
          let s;
          if (pos.winner() === me) s = MATE;
          else {
            // évaluer du point de vue de `me` : on inverse après doMove
            s = -evaluate(pos, weights);
            if (i >= nPawn) s += (cfg.wallBias - 1) * weights.path * 0.5;
          }
          pos.undoMove(m);
          s += rand() * 1e-6;
          if (s > bestScore) { bestScore = s; move = m; }
        }
        info = { score: bestScore };

      } else {
        const r = engine.search(pos, { maxDepth: cfg.depth, maxTimeMs: cfg.timeMs });
        move = r.move; info = r;
        agent.stats.nodes += r.nodes;
        agent.stats.depthSum += r.depth;
      }

      agent.stats.ms += Date.now() - t0;
      agent.stats.moves++;
      return { move, info };
    }
  };
  return agent;
}

/* ═══════════════ arbitre ═══════════════ */

/**
 * Fait jouer une partie complète entre deux agents.
 * @returns {{winner:number, plies:number, moves:string[], reason:string}}
 */
export function playGame(agentA, agentB, opts = {}) {
  const maxPlies = opts.maxPlies ?? 300;
  const pos = opts.position ? opts.position : new Position();
  const agents = [agentA, agentB];
  const moves = [];
  const seen = new Map();

  for (let ply = 0; ply < maxPlies; ply++) {
    const { move } = agents[pos.turn].think(pos);
    if (move < 0 || !pos.isLegal(move)) {
      return { winner: 1 - pos.turn, plies: ply, moves, reason: 'coup illégal' };
    }
    pos.doMove(move);
    moves.push(moveToNotation(move));
    const w = pos.winner();
    if (w !== -1) return { winner: w, plies: ply + 1, moves, reason: 'arrivée' };
    const key = pos.hashLo + ':' + pos.hashHi;
    const c = (seen.get(key) ?? 0) + 1;
    seen.set(key, c);
    if (c >= 3) return { winner: -1, plies: ply + 1, moves, reason: 'répétition' };
  }
  // limite atteinte : le plus proche de l'arrivée l'emporte
  const d0 = pos.distance(0), d1 = pos.distance(1);
  return {
    winner: d0 === d1 ? -1 : (d0 < d1 ? 0 : 1),
    plies: maxPlies, moves, reason: 'limite de coups'
  };
}
