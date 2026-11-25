import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { lint, Model } from '../src/models/compose.js';
import { parse, unit, unitRu } from '../src/expr.js';
const base = JSON.parse(fs.readFileSync('tests/smoke.json', 'utf8')), mut = f => { const s = structuredClone(base); f(s); return lint(s).E.join('\n'); };

test('верная сцена проходит', () => assert.deepEqual(lint(base).E, []));
const BAD = {
  'неизвестное имя': [s => (s.vars.xf.expr = 'qq*t'), /неизвестное имя «qq»/],
  'чужой код': [s => (s.vars.xf.expr = 'process.exit(1)'), /непонятный символ|неизвестн/],
  'доступ к прототипу': [s => (s.vars.xf.expr = 'constructor(1)'), /неизвестная функция/],
  'разные единицы складываются': [s => (s.vars.xf.expr = 'q+R'), /между разными размерностями/],
  'объявлена не та единица': [s => (s.vars.xf.expr = 'q'), /размерность/],
  'экспонента от метров': [s => (s.vars.xf.expr = 'R*exp(R)'), /безразмерным/],
  'деление на ноль': [s => (s.objects[0].top = 'h/(t-t)'), /не число/],
  'тело вне мира': [s => (s.objects[0].top = 'h*100'), /вышло за world/],
  'нарушена физика': [s => (s.checks[0].expr = '-h'), /нарушено/],
  'мёртвый ползунок': [s => (s.params.k9 = { value: 1, unit: '1', from: 'assumption', control: [0, 2, 1, 'x'] }), /ни на что не влияет/],
  'число не из цитаты': [s => (s.params.R = { value: 80, unit: 'm', from: 'book', claim: 'c1' }), /нет в цитате/],
  'прогноз вне шкалы': [s => (s.steps[2].max = 50), /вне \[/],
  'два верных ответа': [s => (s.steps[4].options[1].correct = '1'), /верных ответов/],
  'нет предположения': [s => s.steps.shift(), /первый шаг — predict/],
  'нет решения ученика': [s => (s.steps = s.steps.filter(x => !['guess', 'pick', 'choose'].includes(x.kind))), /нет действия/],
  'чужой цвет': [s => (s.objects[8].color = 'purple'), /легенды/],
  'преувеличение не названо': [s => (s.exaggerations = ['поры увеличены']), /не названо/],
  'пример автора не сходится': [s => (s.examples = [{ name: 'п', at: { t: 2 }, expr: 'xf', unit: 'm', expect: 500 }]), /в книге 500/],
  'круг в переменных': [s => (s.vars.a1 = { expr: 'a1+R', unit: 'm' }), /по кругу/],
  'выбирать нечего': [s => (s.steps[3].score = '5'), /одинаков везде/],
};
for (const [n, [f, re]] of Object.entries(BAD)) test('ловит: ' + n, () => assert.match(mut(f), re));
test('ОДУ совпадает с точным решением', () => { const m = new Model(base, 1); const v = m.at({ t: 4 * m.tu.k }, () => m.fn('V')()); assert.ok(Math.abs(v - 100 * (1 - Math.exp(-0.05 * 4))) < 1e-3); });
test('единицы переводятся', () => { assert.equal(unit('m3/d').k, 1 / 86400); assert.equal(unit('km').k, 1000); assert.equal(unitRu('m3/d'), 'м³/сут'); });
test('приоритет операций', () => { const m = new Model(base, 1); assert.equal(m.fn('-2^2+2*3')(), 2); assert.equal(m.fn('1<2 && 2<1 ? 5 : 7')(), 7); assert.throws(() => parse('1+')); });
