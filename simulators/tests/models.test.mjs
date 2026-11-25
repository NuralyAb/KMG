import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { validate } from '../src/validate.js';
import { resolve } from '../src/extends.js';
import * as log from '../src/models/log.js';
import * as pr from '../src/models/pressure.js';

const raw = Object.fromEntries(fs.readdirSync('scenes').map(f => [f.replace('.json', ''), JSON.parse(fs.readFileSync('scenes/' + f, 'utf8'))]));
const S = Object.fromEntries(Object.keys(raw).map(k => [k, resolve(raw, k)]));
const seeds = n => Array.from({ length: n }, (_, i) => i * 7 + 1);

for (const [n, s] of Object.entries(S)) test('без нарушений на многих случаях: ' + n, () => {
  assert.deepEqual(validate(s, seeds(s.template === 'body_explore' ? 12 : 200)), []);
});
test('E1 совпадает с табличными значениями', () => {
  for (const [x, v] of [[0.01, 4.037929577], [0.1, 1.822923958], [1, 0.219383934], [5, 0.001148295591]]) assert.ok(Math.abs(pr.E1(x) / v - 1) < 1e-6, String(x));
});
test('порог: примеры 50 и 53 книги', () => {
  const t = S['1_log_fresh'].params.table, c = (P, a) => log.classify(t, P, a);
  assert.equal(c(35, 1), 'oil'); assert.equal(c(7, 1), 'mix'); assert.equal(c(2, 1), 'mix'); assert.equal(c(1.3, 1), 'water');
  assert.equal(c(10, 0.9), 'oil'); assert.equal(c(5, 0.8), 'oil'); assert.equal(c(5, 0.95), 'mix'); assert.equal(c(3, 0.9), 'mix');
});
test('оценка по кривым близка к истине у коллекторов', () => {
  const s = S['1_log_fresh']; let n = 0, bad = 0;
  for (const seed of seeds(100)) {
    const c = log.buildCase(s, seed), cv = log.curves(s, c);
    for (const l of c.layers) if (l.collector) { n++; const e = log.estimate(s, c, cv, l); if (Math.abs(Math.log(e.Pn / l.Pn)) > 0.2) bad++; }
  }
  assert.ok(bad / n < 0.03, `${bad}/${n}`);
});
test('в солёном растворе ПС теряет амплитуду', () => {
  const c = log.buildCase(S['2_log_salty'], 1);
  assert.ok(Math.abs(log.curves(S['2_log_salty'], c).ssp) < 5);
});
test('вдвое дальше — вчетверо дольше; дебит на время не влияет', () => {
  const p = S['3_pressure'].params;
  assert.ok(Math.abs(pr.arrival(p, 600) / pr.arrival(p, 300) - 4) < 1e-9);
  assert.equal(pr.arrival({ ...p, Q: 999 }, 300), pr.arrival(p, 300));
});
test('момент arrival — действительно самое быстрое падение', () => {
  const p = S['3_pressure'].params, ta = pr.arrival(p, 400);
  const rate = t => (pr.drop(p, 400, t * 1.001) - pr.drop(p, 400, t * 0.999)) / (0.002 * t);
  assert.ok(rate(ta) > rate(ta * 0.9) && rate(ta) > rate(ta * 1.1));
});
test('неверная физика отвергается', () => {
  const b1 = structuredClone(S['3_pressure']); b1.generator.vary.k = [90, 91];
  assert.ok(validate(b1).some(e => e.includes('kappa')));
  const b2 = structuredClone(S['5_reef_atoll']); b2.zones.lagoon.phi = [20, 30];
  assert.ok(validate(b2).some(e => e.includes('best_zone')));
  const b3 = structuredClone(S['1_log_fresh']); b3.params.kp_dense = [0.2, 0.21];
  assert.ok(validate(b3).some(e => e.includes('dense')));
});
