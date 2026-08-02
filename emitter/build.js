import { readFileSync, writeFileSync } from 'fs';
// Le navigateur ouvert en file:// refuse les imports de modules :
// on inline engine.js + ai.js dans la démo pour qu'elle marche par double-clic.
const strip = (src) => src
  .replace(/^import\s+[\s\S]*?from\s+'[^']*';\s*$/gm, '')
  .replace(/^import\s+\{[\s\S]*?\}\s+from\s+'[^']*';/gm, '')
  .replace(/^export\s+/gm, '');
const bundle = [
  '/* ─── engine.js ─── */', strip(readFileSync('engine.js', 'utf8')),
  '/* ─── race.js ─── */', strip(readFileSync('race.js', 'utf8')),
  '/* ─── ai.js ─── */', strip(readFileSync('ai.js', 'utf8'))
].join('\n');
const html = readFileSync('demo.template.html', 'utf8').replace('/*__ENGINE__*/', bundle);
writeFileSync('demo.html', html);
console.log('demo.html construit :', (html.length / 1024).toFixed(0), 'ko');
