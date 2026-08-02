#!/usr/bin/env node
/** Hardened in-memory verifier for docs/CERTIFICATE_FORMAT.md (qcert-1). */
import * as fs from 'node:fs';
import { pathToFileURL } from 'node:url';
import { makeEngine } from '../external_reviews/claude_fable_2026-08-01/qref.mjs';

const own = (o, key) => Object.prototype.hasOwnProperty.call(o, key);
const integer = (x) => Number.isSafeInteger(x);
const stateKey = (st) => `${st.hw},${st.vw},${st.p[0]},${st.p[1]},${st.walls[0]},${st.walls[1]},${st.turn}`;
const stateFrom = (o) => ({
  hw: o.hw, vw: o.vw, p: [o.p1, o.p2], walls: [o.r1, o.r2], turn: o.turn
});
// Match Python str.strip()/str.isspace(), deliberately excluding U+FEFF.
// JavaScript trim() includes FEFF and would silently erase an internal BOM.
const PYTHON_EDGE_WHITESPACE = '[\\u0009-\\u000d\\u001c-\\u0020\\u0085\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000]';
const PYTHON_EDGE_LEFT = new RegExp(`^${PYTHON_EDGE_WHITESPACE}+`, 'u');
const PYTHON_EDGE_RIGHT = new RegExp(`${PYTHON_EDGE_WHITESPACE}+$`, 'u');
const pythonStrip = (text) => text.replace(PYTHON_EDGE_LEFT, '').replace(PYTHON_EDGE_RIGHT, '');

function duplicateMemberNames(text) {
  let i = 0;
  const duplicates = [];
  const ws = () => { while (/\s/.test(text[i] || '')) i++; };
  const string = () => {
    const start = i++;
    while (i < text.length) {
      if (text[i] === '\\') { i += 2; continue; }
      if (text[i++] === '"') break;
    }
    return JSON.parse(text.slice(start, i));
  };
  const value = () => {
    ws();
    if (text[i] === '{') { object(); return; }
    if (text[i] === '[') { array(); return; }
    if (text[i] === '"') { string(); return; }
    while (i < text.length && !/[\s,}\]]/.test(text[i])) i++;
  };
  const object = () => {
    i++;
    const names = new Set();
    ws();
    if (text[i] === '}') { i++; return; }
    while (i < text.length) {
      ws();
      const name = string();
      if (names.has(name)) duplicates.push(name); else names.add(name);
      ws(); i++; // colon; JSON.parse has already validated the syntax
      value();
      ws();
      if (text[i++] === '}') return;
    }
  };
  const array = () => {
    i++;
    ws();
    if (text[i] === ']') { i++; return; }
    while (i < text.length) {
      value();
      ws();
      if (text[i++] === ']') return;
    }
  };
  value();
  return duplicates;
}

// JSON.parse deliberately erases the lexical distinction between `3`, `3.0`
// and `3e0`.  Retain every number token together with its object path so the
// qcert integer fields can be checked without imposing a new rule on ignored
// extension fields (the Python verifier likewise validates known fields).
function jsonNumberTokens(text) {
  const found = [];
  let i = 0;
  const ws = () => { while (/\s/.test(text[i] || '')) i++; };
  const string = () => {
    const start = i++;
    while (i < text.length) {
      if (text[i] === '\\') { i += 2; continue; }
      if (text[i++] === '"') break;
    }
    return JSON.parse(text.slice(start, i));
  };
  const value = (path) => {
    ws();
    if (text[i] === '{') { object(path); return; }
    if (text[i] === '[') { array(path); return; }
    if (text[i] === '"') { string(); return; }
    if (text[i] === '-' || /[0-9]/.test(text[i] || '')) {
      const match = text.slice(i).match(/^-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?/);
      if (match) {
        const token = match[0];
        found.push({ path: [...path], token });
        i += token.length;
        return;
      }
    }
    while (i < text.length && !/[\s,}\]]/.test(text[i])) i++;
  };
  const object = (path) => {
    i++;
    ws();
    if (text[i] === '}') { i++; return; }
    while (i < text.length) {
      ws();
      const name = string();
      ws(); i++; // colon; JSON.parse has already validated the syntax
      value([...path, name]);
      ws();
      if (text[i++] === '}') return;
    }
  };
  const array = (path) => {
    i++;
    let index = 0;
    ws();
    if (text[i] === ']') { i++; return; }
    while (i < text.length) {
      value([...path, String(index++)]);
      ws();
      if (text[i++] === ']') return;
    }
  };
  value([]);
  return found;
}

const STATE_INTEGER_FIELDS = ['p1', 'p2', 'r1', 'r2', 'turn', 'hw', 'vw'];
const HEADER_INTEGER_PATHS = new Set([
  ...['width', 'height', 'walls', 'target', 'bound'].map((field) => JSON.stringify([field])),
  ...STATE_INTEGER_FIELDS.map((field) => JSON.stringify(['root', field]))
]);
const NODE_INTEGER_PATHS = new Set(
  [...STATE_INTEGER_FIELDS, 'd'].map((field) => JSON.stringify([field]))
);

function popcount32(value) {
  let x = value >>> 0;
  let n = 0;
  while (x) {
    x = (x & (x - 1)) >>> 0;
    n++;
  }
  return n;
}

function wallGeometryErrors(hw, vw, eng) {
  const errors = [];
  const bit = (mask, i) => (mask >>> i) & 1;
  for (let r = 0; r < eng.R; r++) {
    for (let c = 0; c < eng.C; c++) {
      const i = r * eng.C + c;
      if (bit(hw, i) && bit(vw, i)) errors.push(`crossing walls at ${r},${c}`);
      if (bit(hw, i) && c + 1 < eng.C && bit(hw, i + 1)) {
        errors.push(`overlapping horizontal walls at ${r},${c}`);
      }
      if (bit(vw, i) && r + 1 < eng.R && bit(vw, i + eng.C)) {
        errors.push(`overlapping vertical walls at ${r},${c}`);
      }
    }
  }
  return errors;
}

export function stateLegalityErrors(o, header, eng, { requireBudget = true } = {}) {
  const errors = [];
  const fields = ['p1', 'p2', 'r1', 'r2', 'turn', 'hw', 'vw'];
  for (const field of fields) if (!integer(o[field])) errors.push(`${field} is not an integer`);
  if (requireBudget && (!integer(o.d) || o.d < 1)) errors.push('d is not a positive integer');
  if (errors.length) return errors;

  if (o.p1 < 0 || o.p1 >= eng.N || o.p2 < 0 || o.p2 >= eng.N) errors.push('pawn outside board');
  if (o.p1 === o.p2) errors.push('pawns overlap');
  if (o.turn !== 0 && o.turn !== 1) errors.push('turn is not 0 or 1');
  if (o.r1 < 0 || o.r1 > header.walls || o.r2 < 0 || o.r2 > header.walls) errors.push('wall stock outside range');

  const maskLimit = 2 ** eng.S;
  const masksInRange = o.hw >= 0 && o.hw < maskLimit && o.vw >= 0 && o.vw < maskLimit;
  if (!masksInRange) errors.push('wall mask outside anchor grid');
  if (masksInRange) {
    errors.push(...wallGeometryErrors(o.hw, o.vw, eng));
    const placed = popcount32(o.hw) + popcount32(o.vw);
    if (o.r1 + o.r2 + placed !== 2 * header.walls) errors.push('wall conservation violated');
  }

  const pawnsInRange = o.p1 >= 0 && o.p1 < eng.N && o.p2 >= 0 && o.p2 < eng.N;
  if (masksInRange && pawnsInRange) {
    if (!eng.reaches(o.hw, o.vw, o.p1, 0)) errors.push('Player 1 has no goal path');
    if (!eng.reaches(o.hw, o.vw, o.p2, 1)) errors.push('Player 2 has no goal path');
    if (eng.terminal(stateFrom(o)) !== -1) errors.push('terminal state appears in node index');
  }
  return errors;
}

function headerErrors(o) {
  const errors = [];
  if (o.type !== 'header') errors.push('first record is not a header');
  if (o.format !== 'qcert-1') errors.push(`unsupported format ${o.format}`);
  for (const field of ['width', 'height', 'walls', 'target', 'bound']) {
    if (!integer(o[field])) errors.push(`header ${field} is not an integer`);
  }
  if (errors.length) return errors;
  if (o.width < 2 || o.height < 2 || o.width * o.height > 255) errors.push('unsupported board dimensions');
  const anchors = (o.width - 1) * (o.height - 1);
  if (anchors < 1 || anchors > 31) errors.push('qcert-1 JavaScript verifier supports 1..31 anchors');
  if (o.walls < 0 || o.walls > 255) errors.push('walls outside supported range');
  if (o.target !== 0 && o.target !== 1) errors.push('target is not 0 or 1');
  if (o.bound < 1) errors.push('bound is not positive');
  if (!o.root || typeof o.root !== 'object' || Array.isArray(o.root)) errors.push('root is not an object');
  return errors;
}

export function verifyText(text, file = '<memory>') {
  const started = Date.now();
  const errors = [];
  let errorCount = 0;
  const fail = (message) => {
    errorCount++;
    if (errors.length < 20) errors.push(message);
  };

  if (text.startsWith('\uFEFF')) {
    fail('UTF-8 BOM is forbidden');
    text = text.slice(1);
  }

  let header = null;
  let eng = null;
  const index = new Map();
  // Match Python TextIOWrapper's universal-newline input domain exactly.
  const lines = text.split(/\r\n|\n|\r/);
  for (let lineNo = 1; lineNo <= lines.length; lineNo++) {
    const line = pythonStrip(lines[lineNo - 1]);
    if (!line) continue;
    let o;
    try {
      o = JSON.parse(line);
    } catch (error) {
      fail(`line ${lineNo}: invalid JSON (${error.message})`);
      continue;
    }
    const duplicateNames = duplicateMemberNames(line);
    if (duplicateNames.length) {
      fail(`line ${lineNo}: duplicate member name(s): ${[...new Set(duplicateNames)].join(', ')}`);
      continue;
    }
    if (!o || typeof o !== 'object' || Array.isArray(o)) {
      fail(`line ${lineNo}: record is not an object`);
      continue;
    }
    const integerPaths = o.type === 'header' ? HEADER_INTEGER_PATHS
      : (o.type === 'node' ? NODE_INTEGER_PATHS : new Set());
    const nonIntegerNumbers = jsonNumberTokens(line)
      .filter(({ path, token }) => integerPaths.has(JSON.stringify(path)) && /[.eE]/.test(token));
    if (nonIntegerNumbers.length) {
      fail(`line ${lineNo}: non-integer JSON number spelling(s): ${nonIntegerNumbers.map(({ path, token }) => `${path.join('.')}=${token}`).join(', ')}`);
      continue;
    }
    if (o.type === 'header') {
      if (header) {
        fail(`line ${lineNo}: multiple headers`);
        continue;
      }
      header = o;
      const problems = headerErrors(o);
      for (const problem of problems) fail(`line ${lineNo}: ${problem}`);
      if (!problems.length) eng = makeEngine(o.width, o.height, o.walls);
      continue;
    }
    if (o.type !== 'node') {
      fail(`line ${lineNo}: unknown record type ${o.type}`);
      continue;
    }
    if (!header || !eng) {
      fail(`line ${lineNo}: node before a valid header`);
      continue;
    }

    const problems = stateLegalityErrors(o, header, eng);
    for (const problem of problems) fail(`line ${lineNo}: ${problem}`);
    const hasMove = own(o, 'move');
    if (o.turn === header.target) {
      if (!hasMove || typeof o.move !== 'string' || !o.move) fail(`line ${lineNo}: target node lacks a move`);
    } else if (hasMove) {
      fail(`line ${lineNo}: opponent node contains a move`);
    }
    if (problems.length) continue;
    const st = stateFrom(o);
    const key = stateKey(st);
    if (index.has(key)) {
      fail(`line ${lineNo}: duplicate state ${key}`);
      continue;
    }
    index.set(key, { d: o.d, move: o.move, st });
  }

  if (!header) fail('no header');
  if (!eng) {
    return { ok: false, file, errorCount, errors, nodes: index.size, seconds: (Date.now() - started) / 1000 };
  }

  const target = header.target;
  let edgesChecked = 0;
  let targetNodes = 0;
  let opponentNodes = 0;
  const childOK = (child, parentD, context) => {
    const winner = eng.terminal(child);
    if (winner !== -1) {
      if (winner !== target) fail(`terminal child loses for target (${context})`);
      return;
    }
    const entry = index.get(stateKey(child));
    if (!entry) {
      fail(`non-terminal child is uncovered (${context})`);
      return;
    }
    if (entry.d > parentD - 1) fail(`child budget ${entry.d} exceeds ${parentD - 1} (${context})`);
  };

  for (const [key, entry] of index) {
    const children = eng.children(entry.st);
    if (!children.length) {
      fail(`state has no legal action ${key}`);
      continue;
    }
    if (entry.st.turn === target) {
      targetNodes++;
      const chosen = children.find(([label]) => label === entry.move);
      if (!chosen) {
        fail(`declared move ${entry.move} is illegal at ${key}`);
        continue;
      }
      edgesChecked++;
      childOK(chosen[1], entry.d, `via ${entry.move} from ${key}`);
    } else {
      opponentNodes++;
      for (const [label, child] of children) {
        edgesChecked++;
        childOK(child, entry.d, `via ${label} from ${key}`);
      }
    }
  }

  let rootIsInitialPosition = false;
  if (header.root && typeof header.root === 'object') {
    const rootProblems = stateLegalityErrors({ ...header.root, d: 1 }, header, eng);
    for (const problem of rootProblems) fail(`header root: ${problem}`);
    if (!rootProblems.length) {
      const root = stateFrom(header.root);
      const rootEntry = index.get(stateKey(root));
      if (!rootEntry) fail('root is absent from node index');
      else if (rootEntry.d > header.bound) fail(`root budget ${rootEntry.d} exceeds bound ${header.bound}`);
      rootIsInitialPosition = stateKey(root) === stateKey(eng.initial());
    }
  }

  return {
    ok: errorCount === 0,
    file,
    claim: {
      scope: rootIsInitialPosition ? 'initial-position' : 'branch-position',
      width: header.width, height: header.height, walls: header.walls,
      winner: target + 1, bound: header.bound, root: header.root
    },
    rootIsInitialPosition,
    nodes: index.size,
    targetNodes,
    opponentNodes,
    edgesChecked,
    errorCount,
    errors,
    seconds: +((Date.now() - started) / 1000).toFixed(3)
  };
}

export function verifyFile(file) {
  const artifact = fs.readFileSync(file);
  if (artifact.length >= 3 && artifact[0] === 0xef && artifact[1] === 0xbb && artifact[2] === 0xbf) {
    throw new Error('UTF-8 BOM is forbidden');
  }
  const text = new TextDecoder('utf-8', { fatal: true }).decode(artifact);
  return verifyText(text, file);
}

const isMain = process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href;
if (isMain) {
  const file = process.argv[2];
  if (!file) {
    console.error('usage: node reference/qcert_verify.mjs certificate.jsonl');
    process.exit(2);
  }
  try {
    const result = verifyFile(file);
    console.log(JSON.stringify(result));
    process.exit(result.ok ? 0 : 1);
  } catch (error) {
    console.log(JSON.stringify({ ok: false, file, errorCount: 1, errors: [error.message] }));
    process.exit(1);
  }
}
