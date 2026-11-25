import * as log from './models/log.js';
import * as pressure from './models/pressure.js';
import * as reef from './models/reef.js';
import * as compose from './models/compose.js';
export const MODELS = { log_decision: log, pressure_field: pressure, body_explore: reef };
export const lint = compose.lint;
const REQ = ['id', 'template', 'title', 'difficulty', 'node_id', 'provenance', 'params', 'generator', 'assumptions', 'exaggerations', 'sources', 'prediction', 'transfer', 'data_bridge', 'invariants', 'seed'];
// Спецификацию, нарушающую физику, движок не собирает.
export function validate(spec, seeds = [spec.seed]) {
  if (spec.template === 'compose') return compose.lint(spec, seeds).E;
  const err = [];
  for (const k of REQ) if (spec[k] === undefined) err.push(`нет поля «${k}»`);
  const M = MODELS[spec.template];
  if (!M) return [...err, `неизвестный шаблон «${spec.template}»`];
  if (err.length) return err;
  if (!['реальные данные', 'симуляция', 'схема'].includes(spec.provenance)) err.push('метка происхождения не из списка');
  for (const s of spec.sources) if (!s.claim || !s.page) err.push('источник без утверждения или страницы');
  for (const seed of seeds) {
    let c;
    try { c = M.buildCase(spec, seed); } catch (e) { err.push('случай не строится: ' + e.message); break; }
    for (const n of spec.invariants) {
      const f = M.invariants[n];
      try { if (!f) err.push(`неизвестный инвариант «${n}»`); else if (!f(spec, c)) err.push(`нарушен инвариант «${n}»`); }
      catch (e) { err.push(`инвариант «${n}»: ${e.message}`); }
    }
  }
  return [...new Set(err)];
}
