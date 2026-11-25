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
test('после сбоя правится прошлый ответ, тип шага в type принимается', () => {
  const g = pk('steps', 'charts'); w('game', { ...g, steps: g.steps.slice(0, 1) });
  const o = run('--from', 'game', '--to', 'game'); assert.match(o, /шаг game не прошёл проверку/); assert.ok(fs.existsSync(D + '/game.failed.json'));
  w('game', { ...g, steps: g.steps.map(({ kind, ...r }) => ({ type: kind, ...r })) });
  const q = run('--to', 'game'); assert.match(q, /✓ game/, q); assert.ok(!fs.existsSync(D + '/game.failed.json')); assert.equal(JSON.parse(fs.readFileSync(D + '/game.json', 'utf8')).steps[0].kind, 'predict');
});
test('флюиды по постоянным глубинам и до ответа не проходят', () => {
  const s = pk('world', 'objects', 'exaggerations'), z = when => ({ ...s, assumptions: [], objects: [...s.objects, { type: 'section', axis: 'z', at: '0', classes: [{ when, color: 'oil', name: 'нефть' }] }] });
  w('scene', z('y < -14 && y > -22')); const o = run('--from', 'scene', '--to', 'scene'); assert.match(o, /по постоянным глубинам/, o);
  w('scene', z('y > 0')); assert.match(run('--from', 'scene', '--to', 'scene'), /торчит стеной/);
  const g = z('0'); g.objects[0] = { ...g.objects[0], opacity: '0.4' }; w('scene', g); assert.match(run('--from', 'scene', '--to', 'scene'), /поправлено кодом: прозрачность тела/);
  w('scene', { ...s, assumptions: [] }); assert.match(run('--from', 'scene', '--to', 'game'), /✓ scene/);
});
test('правка человека проверяется без модели', () => {
  const q = D + '/model.json', m = JSON.parse(fs.readFileSync(q, 'utf8')); m.assumptions.push('правка'); fs.writeFileSync(q, JSON.stringify(m)); const dd = D + '/design.json', dz = JSON.parse(fs.readFileSync(dd, 'utf8')); dz.storyboard = ['другое']; fs.writeFileSync(dd, JSON.stringify(dz)); const p = D + '/scene.json', f = JSON.parse(fs.readFileSync(p, 'utf8')), keep = JSON.stringify(f);
  const o = run('--to', 'game', '--eyes', 'human'); assert.match(o, /= game: правка человека проверена, без модели/, o); assert.doesNotMatch(o, /> game/);
  f.objects[0].type = 'нет'; fs.writeFileSync(p, JSON.stringify(f)); const k = JSON.parse(fs.readFileSync(D + '/state.json', 'utf8')); delete k.steps.scene; fs.writeFileSync(D + '/state.json', JSON.stringify(k));
  assert.match(run('--to', 'game', '--eyes', 'human'), /✗ scene/); fs.writeFileSync(p, keep);
});
test('исправление патчем: остальное не меняется', () => {
  w('scene', { ...pk('world', 'objects', 'exaggerations'), assumptions: [] }); run('--from', 'scene', '--to', 'scene');
  const g = pk('steps', 'charts'), bad = structuredClone(g); bad.steps[4].options[1].correct = '1'; w('game.1', bad); w('game', { patch: { '/steps/4/options/1/correct': 'h<=14' } });
  const st = JSON.parse(fs.readFileSync(D + '/state.json', 'utf8')); st.fake = {}; fs.writeFileSync(D + '/state.json', JSON.stringify(st));
  const o = run('--from', 'game', '--to', 'game'); assert.match(o, /верных ответов/, o); assert.match(o, /✓ game/, o);
  assert.equal(JSON.parse(fs.readFileSync(D + '/game.json', 'utf8')).steps[4].options[1].correct, 'h<=14'); fs.rmSync(path.join(fake, 'game.1.json')); w('game', g);
});
test('сцена и игра идут вместе и сверяются', () => { const o = run('--from', 'scene', '--to', 'game'); assert.ok(o.indexOf('> game') < o.indexOf('✓ scene'), o); assert.match(o, /✓ game/); });
test('лишние ползунки чинит код', () => {
  const g = structuredClone(pk('steps', 'charts')); g.steps[4].use = ['param:h', 'chart:нет']; w('game', g); const o = run('--from', 'game', '--to', 'game'); assert.match(o, /поправлено кодом: use/, o); assert.match(o, /✓ game/); w('game', pk('steps', 'charts'));
});
test('неподвижная сцена и ответ в вариантах не проходят', () => {
  const s = { ...pk('world', 'exaggerations'), assumptions: [], objects: [{ type: 'solid', top: '-10', bottom: '-30', lith: 'sand' }] }; w('scene', s);
  assert.match(run('--from', 'scene', '--to', 'scene'), /до раскрытия ничего не меняется/); w('scene', { ...pk('world', 'objects', 'exaggerations'), assumptions: [] }); run('--from', 'scene', '--to', 'scene');
  const g = structuredClone(pk('steps', 'charts')); g.steps[4].options[0].text = 'Выше {h:m:0} м'; w('game', g); assert.match(run('--from', 'game', '--to', 'game'), /ответ виден без сцены/); w('game', pk('steps', 'charts')); run('--from', 'game', '--to', 'game');
});
test('образец принимается всеми проверками', () => {
  const e = JSON.parse(fs.readFileSync('agent/example.json', 'utf8')), keep = {}; for (const n of ['model', 'scene', 'game']) { keep[n] = fs.readFileSync(path.join(fake, n + '.json')); w(n, e[n]); } fs.renameSync(path.join(fake, 'model.1.json'), path.join(fake, 'm1'));
  const o = run('--from', 'model', '--to', 'game'); assert.match(o, /✓ model/, o); assert.match(o, /✓ scene/, o); assert.match(o, /✓ game/, o); assert.doesNotMatch(o, /исправление/);
  for (const n in keep) fs.writeFileSync(path.join(fake, n + '.json'), keep[n]); fs.renameSync(path.join(fake, 'm1'), path.join(fake, 'model.1.json')); const st = JSON.parse(fs.readFileSync(D + '/state.json', 'utf8')); st.fake = {}; fs.writeFileSync(D + '/state.json', JSON.stringify(st)); run('--from', 'model', '--to', 'game');
});
test('вычитка правит только тексты', { skip: !process.env.FULL }, () => {
  w('proof', { patch: { '/intro': 'Новое вступление.', '/params/h/value': '99', '/steps/0/kind': 'reveal' } }); const o = run('--from', 'look', '--to', 'look'); assert.match(o, /вычитка: исправлено 1/, o);
  const s = JSON.parse(fs.readFileSync(D + '/sim.json', 'utf8')); assert.equal(s.intro, 'Новое вступление.'); assert.equal(s.steps[0].kind, 'predict'); fs.rmSync(path.join(fake, 'proof.json'));
});
test('3D не нужен — конвейер честно останавливается', () => { w('facts', { fit_3d: false, why: 'хватит схемы', claims: cl }); const o = run('--from', 'facts', '--to', 'facts'); assert.match(o, /3D не нужен: хватит схемы/); w('facts', { fit_3d: true, why: 'x', claims: cl }); });
test('до конца: кадры, прохождение, сдача', { skip: !process.env.FULL }, () => { const o = run('--from', 'facts'); assert.match(o, /Готово/, o); fs.rmSync('sims/' + job + '.json', { force: true }); fs.rmSync('sims/' + job + '.webp', { force: true }); spawnSync('node', ['build.mjs']); });

test('по узлу слоя: факты без модели, готовая сцена встаёт на шаг', { skip: !process.env.FULL }, () => {
  const W = path.join('..', 'workspace', 'work', 'zz_test_chapter'); fs.mkdirSync(W, { recursive: true });
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
