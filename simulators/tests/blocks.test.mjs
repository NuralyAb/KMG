// Крупные блоки: каждый разворачивается в сцену, которая проходит полную проверку.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { lint } from '../src/models/compose.js';
import { expand, BLOCKS } from '../src/models/blocks.js';
const D = JSON.parse(fs.readFileSync('tests/blocks.demo.json', 'utf8'));
const spec = k => { const x = expand(D[k]), m = D.model; return { ...D.base, id: 'demo_' + k, ...m, params: { ...m.params, ...x.params }, functions: { ...m.functions, ...x.functions }, world: x.world, objects: x.objects, assumptions: ['условно', ...x.assumptions], exaggerations: x.exaggerations }; };
const KEYS = Object.keys(D).filter(k => !['base', 'model'].includes(k));
for (const k of KEYS) test('блоки: ' + k, () => assert.deepEqual(lint(spec(k)).E.filter(e => !/^время ни на что/.test(e)), []));
test('показан каждый блок', () => { const used = new Set(KEYS.flatMap(k => D[k].blocks.map(b => b.block))); assert.deepEqual(BLOCKS.filter(b => !used.has(b)), []); });
test('ошибки названы', () => {
  assert.throws(() => expand({ blocks: [{ block: 'нет' }] }), /нет блока/); assert.throws(() => expand({ blocks: [{ block: 'log' }] }), /нет «value»/);
  assert.throws(() => expand({ blocks: [{ block: 'layers' }, { block: 'stack', beds: [] }] }), /один на сцену/); assert.throws(() => expand({ blocks: [{ block: 'layers', shape: 'шар' }] }), /shape/);
  assert.throws(() => expand({ blocks: [{ block: 'layers', zones: [{ fill: [{ fluid: 'mud' }] }] }] }), /fluid/);
});
test('сцена без блоков не меняется', () => { const s = { objects: [1] }; assert.equal(expand(s), s); });
if (process.argv[2] === '--specs') fs.writeFileSync(process.argv[3], JSON.stringify(Object.fromEntries(KEYS.map(k => [k, spec(k)]))));
