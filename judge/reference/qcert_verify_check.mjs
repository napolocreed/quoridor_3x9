#!/usr/bin/env node
/** Self-contained acceptance/rejection checks for the hardened qcert verifier. */
import * as fs from 'node:fs';
import * as os from 'node:os';
import * as path from 'node:path';
import { makeEngine } from '../external_reviews/claude_fable_2026-08-01/qref.mjs';
import { stateLegalityErrors, verifyFile, verifyText } from './qcert_verify.mjs';

const file = new URL('../results/validation/qcert/cert_3x3x0.jsonl', import.meta.url);
const valid = fs.readFileSync(file, 'utf8');
const lines = valid.trimEnd().split(/\r?\n/);

const accepted = verifyText(valid, 'cert_3x3x0.jsonl');
if (!accepted.ok) throw new Error(`valid certificate rejected: ${accepted.errors.join('; ')}`);

const corruptions = {
  badBudget: valid.replace('"d":4', '"d":0'),
  nonDecreasingBudget: valid.replace('"d":3,"move":"P:4"', '"d":4,"move":"P:4"'),
  badMove: valid.replace('"move":"P:7"', '"move":"H:0:0"'),
  legalButFalseMove: valid.replace('"move":"P:4"', '"move":"P:0"'),
  coverageHole: lines.slice(0, -1).join('\n') + '\n',
  rootOverBound: valid.replace('"bound":4', '"bound":3'),
  duplicate: `${valid}${lines[1]}\n`,
  duplicateMember: valid.replace('"bound":4', '"bound":4,"bound":5'),
  floatingInteger: valid.replace('"height":3', '"height":3.0'),
  exponentInteger: valid.replace('"bound":4', '"bound":4e0'),
  badTarget: valid.replace('"target":1', '"target":2'),
  unsafeInteger: lines.map((line) => {
    const record = JSON.parse(line);
    if (record.type === 'header') record.bound = 18014398509481984;
    else record.d = 18014398509481984;
    return JSON.stringify(record);
  }).join('\n') + '\n'
};
for (const [name, text] of Object.entries(corruptions)) {
  const result = verifyText(text, name);
  if (result.ok) throw new Error(`${name} corruption was accepted`);
}

const header = { walls: 2 };
const engine = makeEngine(3, 3, 2);
const crossing = { p1: 7, p2: 1, r1: 1, r2: 1, turn: 0, hw: 1, vw: 1, d: 1 };
const crossingErrors = stateLegalityErrors(crossing, header, engine);
if (!crossingErrors.some((error) => error.includes('crossing walls'))) {
  throw new Error(`crossing state was not rejected: ${crossingErrors.join('; ')}`);
}
const overlap = { p1: 7, p2: 1, r1: 1, r2: 1, turn: 0, hw: 3, vw: 0, d: 1 };
const overlapErrors = stateLegalityErrors(overlap, header, engine);
if (!overlapErrors.some((error) => error.includes('overlapping horizontal'))) {
  throw new Error(`overlapping state was not rejected: ${overlapErrors.join('; ')}`);
}
const conservation = { ...crossing, hw: 0, vw: 0 };
const conservationErrors = stateLegalityErrors(conservation, header, engine);
if (!conservationErrors.some((error) => error.includes('conservation'))) {
  throw new Error(`stock conservation error was not rejected: ${conservationErrors.join('; ')}`);
}

const maxSafeBound = verifyText(valid.replace('"bound":4', `"bound":${Number.MAX_SAFE_INTEGER}`), 'maxSafeBound');
if (!maxSafeBound.ok) throw new Error(`MAX_SAFE_INTEGER bound was rejected: ${maxSafeBound.errors.join('; ')}`);

const extensionFloat = verifyText(
  valid.replace('"format":"qcert-1"', '"format":"qcert-1","extra":1.5'),
  'extensionFloat'
);
if (!extensionFloat.ok) {
  throw new Error(`ignored numeric extension diverged from Python: ${extensionFloat.errors.join('; ')}`);
}
const dottedExtensionFloat = verifyText(
  valid.replace('"format":"qcert-1"', '"format":"qcert-1","root.p1":1.5'),
  'dottedExtensionFloat'
);
if (!dottedExtensionFloat.ok) {
  throw new Error(`dotted extension collided with a known path: ${dottedExtensionFloat.errors.join('; ')}`);
}
const nullRecord = verifyText(`${valid}null\n`, 'nullRecord');
if (nullRecord.ok || !nullRecord.errors.some((error) => error.includes('record is not an object'))) {
  throw new Error(`null record was not rejected structurally: ${nullRecord.errors.join('; ')}`);
}

const crOnly = verifyText(valid.replaceAll('\n', '\r'), 'crOnly');
if (!crOnly.ok) throw new Error(`universal-newline certificate rejected: ${crOnly.errors.join('; ')}`);
const bom = verifyText(`\uFEFF${valid}`, 'bom');
if (bom.ok) throw new Error('UTF-8 BOM was accepted');
const spacedBom = verifyText(` \uFEFF${valid}`, 'spacedBom');
if (spacedBom.ok) throw new Error('BOM after leading spaces was accepted');
const internalBom = verifyText(valid.replace('\n', '\n\uFEFF'), 'internalBom');
if (internalBom.ok) throw new Error('BOM at a later record was accepted');

const byteFixtures = fs.mkdtempSync(path.join(os.tmpdir(), 'qcert-byte-check-'));
try {
  const validBytes = Buffer.from(valid, 'utf8');
  const marker = Buffer.from('"format":"qcert-1"', 'utf8');
  const markerAt = validBytes.indexOf(marker);
  if (markerAt < 0) throw new Error('test fixture format marker is absent');
  const insertion = markerAt + marker.length;
  const invalidUtf8 = Buffer.concat([
    validBytes.subarray(0, insertion),
    Buffer.from(',"extra":"', 'utf8'),
    Buffer.from([0xff]),
    Buffer.from('"', 'utf8'),
    validBytes.subarray(insertion)
  ]);
  const invalidPath = path.join(byteFixtures, 'invalid-utf8.jsonl');
  fs.writeFileSync(invalidPath, invalidUtf8);
  let invalidRejected = false;
  try { verifyFile(invalidPath); } catch { invalidRejected = true; }
  if (!invalidRejected) throw new Error('invalid UTF-8 bytes were replaced and accepted');

  const bomPath = path.join(byteFixtures, 'bom.jsonl');
  fs.writeFileSync(bomPath, Buffer.concat([Buffer.from([0xef, 0xbb, 0xbf]), validBytes]));
  let byteBomRejected = false;
  try { verifyFile(bomPath); } catch (error) {
    byteBomRejected = error.message.includes('BOM');
  }
  if (!byteBomRejected) throw new Error('byte-level UTF-8 BOM was not rejected explicitly');
} finally {
  fs.rmSync(byteFixtures, { recursive: true, force: true });
}

console.log(JSON.stringify({
  status: 'ok', acceptedNodes: accepted.nodes,
  corruptionsRejected: Object.keys(corruptions).length,
  illegalGeometryRejected: true,
  stockConservationRejected: true,
  maxSafeIntegerAccepted: true,
  ignoredFloatExtensionAccepted: true,
  dottedFloatExtensionAccepted: true,
  nullRecordRejected: true,
  universalNewlinesAccepted: true,
  bomRejected: true,
  displacedBomRejected: true,
  invalidUtf8Rejected: true
}));
