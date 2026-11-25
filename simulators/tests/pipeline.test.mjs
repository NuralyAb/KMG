// Конвейер на подставных ответах: модель не вызывается, лимит не тратится.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
const S = JSON.parse(fs.readFileSync('tests/smoke.json', 'utf8')), T = fs.mkdtempSync(path.join(os.tmpdir(), 'pl-')), fake = path.join(T, 'f'), job = 'testpipe', D = path.join('jobs', job);
fs.mkdirSync(fake); fs.rmSync(D, { recursive: true, force: true, maxRetries: 3 }); fs.rmSync('sims/' + job + '.json', { force: true });
const book = path.join(T, 'b.md'); fs.writeFileSync(book, '<!-- page 34 -->\nнет\n<!-- page 35 -->\nразрезы с постепенным увеличением размера зерен кверху. Бар продвигается к морю. Рукав врезан в подошву.\n');
const w = (n, o) => fs.writeFileSync(path.join(fake, n + '.json'), JSON.stringify(o)), pk = (...k) => Object.fromEntries(k.filter(x => S[x] !== undefined).map(x => [x, S[x]]));
const cl = [['c1', 'постепенным увеличением размера'], ['c2', 'Бар продвигается к морю'], ['c3', 'Рукав врезан в подошву']].map(([id, quote]) => ({ id, text: quote, quote, page: 35 }));
w('facts.1', { fit_3d: true, why: 'x', claims: [{ ...cl[0], quote: 'такой цитаты здесь нет' }, cl[1], cl[2]] }); w('facts', { fit_3d: true, why: 'x', claims: cl });
w('design', { ...pk('title', 'goal', 'difficulty', 'misconception', 'why_3d', 'transfer', 'data_bridge', 'node_id'), intro: 'i', decision: 'd', varies: ['h'], storyboard: ['a'], analogy: { text: 'a', breaks_where: 'b' } });
const model = { ...pk('params', 'tables', 'functions', 'states', 'vars', 'time', 'checks'), assumptions: ['всё условно'] };
w('model.1', { ...model, vars: { ...model.vars, bad: { expr: 'q+R', unit: 'm' } } }); w('model', model);
w('scene', { ...pk('world', 'objects', 'exaggerations'), assumptions: [] }); w('game', pk('steps', 'charts')); w('look', { ok: true });
const run = (...a) => { const r = spawnSync('node', ['agent/pipeline.mjs', job, '--fake', fake, ...a], { encoding: 'utf8', timeout: 400000 }); return r.stdout + r.stderr; };

test('ошибочные ответы не проходят и исправляются', () => {
  const o = run('--book', book, '--pages', '34-35', '--to', 'game');
  assert.match(o, /цитаты нет дословно/); assert.match(o, /между разными размерностями/); assert.match(o, /✓ game/); assert.match(o, /Остановлено после game/);
});
test('повторный запуск не вызывает модель', () => { const o = run('--to', 'game'); assert.equal((o.match(/пропуск/g) || []).length, 5); });
test('правка факта пересчитывает только зависимые шаги', () => {
  const f = JSON.parse(fs.readFileSync(D + '/design.json', 'utf8')); f.storyboard = ['новое']; fs.writeFileSync(D + '/design.json', JSON.stringify(f));
  const o = run('--to', 'game'); assert.match(o, /= facts/); assert.match(o, /= design/); assert.match(o, /✓ model/); assert.match(o, /✓ scene/);
});
test('в запросы попадает каталог', () => { const o = run('--plan'); for (const n of ['model', 'scene', 'game']) assert.ok(+new RegExp(n + '\\s+≈(\\d+)').exec(o)[1] > 900, o); });
test('3D не нужен — конвейер честно останавливается', () => { w('facts', { fit_3d: false, why: 'хватит схемы', claims: cl }); const o = run('--from', 'facts', '--to', 'facts'); assert.match(o, /3D не нужен: хватит схемы/); w('facts', { fit_3d: true, why: 'x', claims: cl }); });
test('до конца: кадры, прохождение, сдача', { skip: !process.env.FULL }, () => { const o = run('--from', 'facts'); assert.match(o, /Готово/, o); fs.rmSync('sims/' + job + '.json', { force: true }); fs.rmSync('sims/' + job + '.webp', { force: true }); spawnSync('node', ['build.mjs']); });

test('по узлу слоя: факты без модели, готовая сцена встаёт на шаг', { skip: !process.env.FULL }, () => {
  const W = path.join('..', 'work', 'zz_test_chapter'); fs.mkdirSync(W, { recursive: true });
  try {
    const cl2 = cl.map(c => ({ ...c, id: 'zz.node#' + c.id, page_pdf: 35, source_kind: 'text' }));
    fs.writeFileSync(W + '/layer.json', JSON.stringify({ title: 'Глава', nodes: [{ id: 'zz.node', title: 'Узел', claims: cl2, layers: { main: { text: 'м' }, mechanism: { text: 'м' } } }] }));
    const r = spawnSync('node', ['agent/pipeline.mjs', 'zz_node', '--chapter', 'zz_test_chapter', '--node', 'zz.node', '--fake', fake], { encoding: 'utf8', timeout: 400000 }), o = r.stdout + r.stderr;
    assert.match(o, /утверждений из слоя, без модели/, o); assert.match(o, /привязано к шагу zz.node/, o);
    const c = JSON.parse(fs.readFileSync(W + '/simulations.json', 'utf8')).steps['zz.node'][0];
    assert.equal(c.origin, 'agent'); assert.deepEqual(c.claims, cl2.map(x => x.id)); assert.ok(fs.existsSync(W + '/simulations/zz_node.json'));
  } finally { for (const d of [W, 'jobs/zz_node', 'sims/zz_node.json', 'sims/zz_node.webp']) fs.rmSync(d, { recursive: true, force: true, maxRetries: 5 }); }
});
test('узла нет в слое — отказ до траты', () => { const r = spawnSync('node', ['agent/pipeline.mjs', 'zz_no', '--chapter', 'zz_absent', '--node', 'zz.no'], { encoding: 'utf8' }); assert.notEqual(r.status, 0); fs.rmSync('jobs/zz_no', { recursive: true, force: true }); });
