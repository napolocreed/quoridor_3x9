/**
 * Worker : la recherche tourne hors du fil principal, l'interface ne gèle
 * jamais. Fonctionne en navigateur et en React Native (via un bundler qui
 * supporte les workers, ou en repliant sur `ai.js` directement).
 *
 * Côté application :
 *
 *   const ia = new Worker(new URL('./worker.js', import.meta.url), { type: 'module' });
 *   ia.onmessage = (e) => {
 *     if (e.data.type === 'move') applique(e.data.notation);
 *   };
 *   ia.postMessage({ type: 'think', moves: ['e2','e8','he5'], profile: 'oracle', timeMs: 800 });
 *
 * Messages entrants :
 *   {type:'think',  moves:string[], profile?, depth?, timeMs?, weights?}
 *   {type:'legal',  moves:string[]}        -> liste des coups légaux
 *   {type:'analyse',moves:string[], timeMs?} -> distances + coup conseillé
 *   {type:'cancel'}
 *
 * Messages sortants :
 *   {type:'move',    notation, score, depth, nodes, ms, mate:boolean}
 *   {type:'legal',   notation:string[]}
 *   {type:'analyse', distances:[number,number], best, score, depth}
 *   {type:'error',   message}
 *
 * @module worker
 */
import { Position, moveToNotation } from './engine.js';
import { SearchEngine, createAgent, PROFILES, MATE } from './ai.js';

/** @type {Map<string, SearchEngine>} un moteur par profil : la table de transposition survit d'un coup à l'autre */
const engines = new Map();

function engineFor(key, weights) {
  let e = engines.get(key);
  if (!e) { e = new SearchEngine({ weights }); engines.set(key, e); }
  return e;
}

function build(moves) {
  return moves && moves.length ? Position.fromMoves(moves) : new Position();
}

self.onmessage = (ev) => {
  const msg = ev.data || {};
  try {
    if (msg.type === 'legal') {
      const pos = build(msg.moves);
      const buf = new Int32Array(256);
      const n = pos.legalMoves(buf);
      const list = [];
      for (let i = 0; i < n; i++) list.push(moveToNotation(buf[i]));
      self.postMessage({ type: 'legal', notation: list });
      return;
    }

    if (msg.type === 'think' || msg.type === 'analyse') {
      const pos = build(msg.moves);
      if (pos.winner() !== -1) {
        self.postMessage({ type: 'error', message: 'la partie est terminée' });
        return;
      }
      const profile = msg.profile ?? 'oracle';
      const preset = PROFILES[profile] ?? PROFILES.oracle;

      // les agents non fondés sur la recherche gardent leur tempérament
      if (preset.kind !== 'search' && msg.type === 'think') {
        const agent = createAgent(profile, { seed: msg.seed });
        const { move } = agent.think(pos);
        self.postMessage({
          type: 'move', notation: moveToNotation(move),
          score: 0, depth: 0, nodes: 0, ms: 0, mate: false
        });
        return;
      }

      const e = engineFor(profile + JSON.stringify(msg.weights ?? {}), msg.weights);
      const r = e.search(pos, {
        maxDepth: msg.depth ?? preset.depth ?? 64,
        maxTimeMs: msg.timeMs ?? preset.timeMs ?? 800
      });

      if (msg.type === 'analyse') {
        self.postMessage({
          type: 'analyse',
          distances: [pos.distance(0), pos.distance(1)],
          best: moveToNotation(r.move),
          score: r.score, depth: r.depth
        });
      } else {
        self.postMessage({
          type: 'move', notation: moveToNotation(r.move),
          score: r.score, depth: r.depth, nodes: r.nodes, ms: r.ms,
          mate: Math.abs(r.score) > MATE - 100
        });
      }
      return;
    }

    if (msg.type === 'cancel') { engines.clear(); return; }

    self.postMessage({ type: 'error', message: 'message inconnu : ' + msg.type });
  } catch (err) {
    self.postMessage({ type: 'error', message: String(err && err.message || err) });
  }
};
