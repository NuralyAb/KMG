// Модель из спецификации: параметры, таблицы, функции, состояния (ОДУ), переменные. Всё в СИ.
import { parse, names, code, builtinCall, BUILTIN, unit, dims } from '../expr.js';
import { rng, between, lerp } from './util.js';

const ENV = ['t', 'T', 'step', 'revealed', 'picks', 'best_score', 'pick_score', 'seed'];
export function tableFn(rows) { const r = [...rows].sort((a, b) => a[0] - b[0]); return x => { if (x <= r[0][0]) return r[0][1]; for (let i = 1; i < r.length; i++) if (x <= r[i][0]) return lerp(r[i - 1][1], r[i][1], (x - r[i - 1][0]) / (r[i][0] - r[i - 1][0])); return r[r.length - 1][1]; }; }

export class Model {
  constructor(spec, seed) {
    this.spec = spec; this.seed = seed; const r = rng(seed);
    this.P = {}; this.U = {}; this.V = {}; this.F = {}; this.T = {}; this.S = {}; this.E = { t: 0, T: 0, step: 0, revealed: 0, picks: 0, best_score: 0, pick_score: 0, seed };
    for (const [n, p] of Object.entries(spec.params || {})) { this.U[n] = unit(p.unit); const v = p.range ? +between(r, p.range).toPrecision(3) : p.value; this.P[n] = v * this.U[n].k; }
    for (const [n, t] of Object.entries(spec.tables || {})) { const kx = unit(t.x_unit).k, ky = unit(t.y_unit).k; this.T[n] = tableFn(t.rows.map(([a, b]) => [a * kx, b * ky])); }
    for (const s of spec.steps || []) if (s.kind === 'guess') this.E[s.id] = NaN;
    for (const s of spec.steps || []) if (s.kind === 'choose') this.E[s.id] = -1;
    const tm = spec.time; this.tu = unit(tm ? tm.unit : 's');
    this.t0 = tm ? tm.min * this.tu.k : 0; this.t1 = tm ? tm.max * this.tu.k : 1; this.E.t = this.t0;
    this.fsig = Object.create(null); for (const k of Object.keys(spec.functions || {})) { const m = /^\s*([A-Za-z_]\w*)\s*\(([^)]*)\)\s*$/.exec(k); if (!m) throw new Error(`функция должна называться «имя(x,y)»: «${k}»`); this.fsig[m[1]] = { key: k, args: m[2].split(',').map(s => s.trim()).filter(Boolean) }; }
    const taken = new Set(['constructor', '__proto__', 'prototype', 'toString', 'valueOf']); for (const n of [...Object.keys(this.P), ...Object.keys(this.T), ...Object.keys(this.fsig), ...Object.keys(spec.vars || {}), ...Object.keys(spec.states || {})]) { if (taken.has(n) || Object.hasOwn(BUILTIN, n) || ENV.includes(n) || ['x', 'y', 'z', 'i', 'r1', 'r2', 'r3', 'pi'].includes(n)) throw new Error(`имя «${n}» занято`); taken.add(n); }
    for (const [n, s] of Object.entries(this.fsig)) this.F[n] = this.fn(spec.functions[s.key], s.args, 'функция ' + n);
    this.order = []; const vs = Object.keys(spec.vars || {}), mark = {};
    const visit = n => { if (mark[n] === 1) throw new Error(`переменные зависят по кругу: «${n}»`); if (mark[n] === 2) return; mark[n] = 1; this.deps(spec.vars[n].expr).forEach(d => vs.includes(d) && visit(d)); mark[n] = 2; this.order.push(n); };
    vs.forEach(visit); this.vf = {}; vs.forEach(n => (this.vf[n] = this.fn(spec.vars[n].expr, [], 'переменная ' + n)));
    this.sn = Object.keys(spec.states || {}); this.sf = {}; this.sn.forEach(n => (this.sf[n] = { init: this.fn(spec.states[n].init, [], n), rate: this.fn(spec.states[n].rate, [], n) }));
    this.solve(); this.update();
  }
  scope() {
    const s = this.spec;
    return {
      id: n => Object.hasOwn(this.P, n) ? 'P.' + n : Object.hasOwn(s.vars || {}, n) ? 'V.' + n : Object.hasOwn(s.states || {}, n) ? 'S.' + n : Object.hasOwn(this.E, n) ? 'E.' + n : null,
      call: (n, k) => { if (this.fsig[n]) { if (this.fsig[n].args.length !== k) throw new Error(`«${n}» ждёт ${this.fsig[n].args.length} арг., дано ${k}`); return 'F.' + n; } if (Object.hasOwn(this.T, n)) return 'T.' + n; return builtinCall(n, k); },
    };
  }
  fn(src, args = [], where = '') {
    try { const body = code(parse(src), this.scope(), args); return new Function('B', 'P', 'V', 'F', 'T', 'S', 'E', `return function(${args.map(a => '$' + a).join(',')}){return +(${body});}`)(BUILTIN, this.P, this.V, this.F, this.T, this.S, this.E); }
    catch (e) { throw new Error((where ? where + ': ' : '') + e.message); }
  }
  // все имена, от которых зависит формула, включая вложенные функции
  deps(src, seen = new Set()) {
    const { ids, calls } = names(parse(src)), out = new Set(ids);
    calls.forEach(c => { if (this.fsig[c] && !seen.has(c)) { seen.add(c); const a = this.fsig[c].args; this.deps(this.spec.functions[this.fsig[c].key], seen).forEach(d => a.includes(d) || out.add(d)); } });
    for (const d of [...out]) if (Object.hasOwn(this.spec.vars || {}, d) && !seen.has('v:' + d)) { seen.add('v:' + d); this.deps(this.spec.vars[d].expr, seen).forEach(q => out.add(q)); }
    return out;
  }
  // Живые величины: меняются ли они в ходе опыта (время, шаг, ползунки, решения)
  dynamic(src) { const ctl = Object.entries(this.spec.params || {}).filter(([, p]) => p.control).map(([n]) => n); for (const d of this.deps(src)) if (['t', 'T', 'step', 'revealed', 'picks', 'pick_score', 'best_score'].includes(d) || ctl.includes(d) || Object.hasOwn(this.spec.states || {}, d) || (Object.hasOwn(this.E, d) && d !== 'seed')) return true; return false; }
  solve() { // ОДУ: Рунге — Кутта 4, шаг по всему времени опыта
    if (!this.sn.length) return; const N = 600, h = (this.t1 - this.t0) / N, get = v => this.sn.forEach((n, i) => (this.S[n] = v[i]));
    const rate = (t, v) => { get(v); this.E.t = t; this.update(false); return this.sn.map(n => this.sf[n].rate()); };
    const keep = this.E.t; this.E.t = this.t0; this.sn.forEach(n => (this.S[n] = 0)); this.update(false); let v = this.sn.map(n => this.sf[n].init()); this.tr = [v];
    for (let k = 0; k < N; k++) { const t = this.t0 + k * h, a = rate(t, v), b = rate(t + h / 2, v.map((x, i) => x + h / 2 * a[i])), c = rate(t + h / 2, v.map((x, i) => x + h / 2 * b[i])), d = rate(t + h, v.map((x, i) => x + h * c[i])); v = v.map((x, i) => x + h / 6 * (a[i] + 2 * b[i] + 2 * c[i] + d[i])); this.tr.push(v); }
    this.E.t = keep;
  }
  update(states = true) {
    this.E.T = this.t1 > this.t0 ? (this.E.t - this.t0) / (this.t1 - this.t0) : 0;
    if (states && this.sn && this.sn.length) { const q = Math.min(599.999, Math.max(0, this.E.T * 600)), i = Math.floor(q); this.sn.forEach((n, j) => (this.S[n] = lerp(this.tr[i][j], this.tr[i + 1][j], q - i))); }
    for (const n of this.order || []) this.V[n] = this.vf[n]();
  }
  setParam(n, si) { this.P[n] = si; this.solve(); this.update(); }
  // значение формулы при других t/параметрах, с возвратом состояния
  at(over, f) { const kP = { ...this.P }, kE = { ...this.E }; let heavy = false; for (const k in over) if (Object.hasOwn(this.P, k)) { this.P[k] = over[k]; heavy = true; } else this.E[k] = over[k]; if (heavy) this.solve(); this.update(); const v = f(); Object.assign(this.P, kP); Object.assign(this.E, kE); if (heavy) this.solve(); this.update(); return v; }
  text(s) { return String(s).replace(/\{([^{}:]+)(?::([^{}:]*))?(?::(\d+))?\}/g, (_, e, u, d) => { const v = this.fn(e)() / unit(u).k; return Number.isFinite(v) ? v.toFixed(d === undefined ? 1 : +d).replace('.', ',') : '—'; }); }
}
export function buildCase(spec, seed) { return new Model(spec, seed); }

// ---------- проверка спецификации. Каждое замечание — что именно исправить.
const OBJ = {
  solid: { ex: [['top', 'xz'], ['bottom', 'xz']], req: ['top', 'bottom', 'lith'] }, surface: { ex: [['y', 'xz'], ['value', 'xz']], req: ['y'] }, section: { ex: [['value', 'xyz']], req: ['axis', 'at'] },
  water: { ex: [['level', '']], req: ['level'] }, tube: { ex: [], req: ['path', 'radius'] }, prefab: { ex: [], req: ['name', 'at'] }, particles: { ex: [], req: ['velocity', 'box', 'color'] },
  arrows: { ex: [], req: ['vector', 'box', 'color'] }, shape: { ex: [], req: ['shape', 'at', 'size', 'color'] }, scatter: { ex: [], req: ['n', 'at', 'size', 'color'] }, label: { ex: [], req: ['text', 'at'] }, column: { ex: [['value', 'xyz']], req: ['at', 'value', 'top', 'bottom', 'min', 'max'] },
};
export const OBJECT_TYPES = Object.keys(OBJ);
export const COLORS = ['sand', 'shale', 'limestone', 'dolomite', 'dense', 'reef', 'salt', 'anhydrite', 'oil', 'gas', 'water', 'filtrate', 'mud', 'SP', 'GR', 'RES', 'POR', 'PRESSURE', 'measure', 'unc', 'text', 'muted', 'steel'];
const LITH = ['sand', 'shale', 'limestone', 'dolomite', 'dense', 'reef', 'salt', 'anhydrite'];
export const PREFABS = ['derrick', 'truck', 'tool'];
const STEP = { predict: ['q', 'options', 'answer', 'why'], explore: ['text'], guess: ['id', 'text', 'min', 'max', 'unit', 'truth'], pick: ['text', 'n', 'target', 'score'], choose: ['id', 'q', 'options'], reveal: ['text'] };

export function lint(spec, seeds = [1, 2, 3, 4, 5]) {
  const E = [], W = []; const err = s => E.includes(s) || E.push(s), warn = s => W.includes(s) || W.push(s);
  for (const k of ['id', 'title', 'goal', 'node_id', 'difficulty', 'provenance', 'why_3d', 'world', 'objects', 'steps', 'claims', 'assumptions', 'exaggerations', 'transfer', 'data_bridge', 'checks', 'seed', 'misconception']) if (spec[k] === undefined) err(`нет поля «${k}»`);
  if (E.length) return { E, W };
  let M; try { M = new Model(spec, seeds[0]); } catch (e) { err(e.message); return { E, W }; }
  const tryf = (src, args, where) => { if (src === undefined) return null; try { return M.fn(String(src), args, where); } catch (e) { err(e.message); return null; } };
  const arr3 = (a, args, where) => { if (!Array.isArray(a) || a.length !== 3) { err(`${where}: нужен массив из трёх формул`); return []; } return a.map((s, i) => tryf(s, args, `${where}[${'xyz'[i]}]`)); };
  if (!Array.isArray(spec.world.size) || spec.world.size.length !== 3) { err('world.size: [ширина X, высота Y, глубина Z] в метрах'); return { E, W }; }
  const [X, Y, Z] = spec.world.size, [y0, y1] = spec.world.y || [0, Y];
  const grid = []; for (let a = 0; a <= 6; a++) for (let b = 0; b <= 6; b++) grid.push([(a / 6 - .5) * X, (b / 6 - .5) * Z]);
  const times = spec.time ? [0, .03, .25, .5, .75, 1].map(k => M.t0 + (M.t1 - M.t0) * k) : [0];
  const numeric = [];
  const ids = new Set();
  spec.objects.forEach((o, i) => {
    const w = `objects[${i}] ${o.type}${o.id ? ' «' + o.id + '»' : ''}`, d = OBJ[o.type]; if (!d) return err(`${w}: нет такого типа (есть: ${OBJECT_TYPES.join(', ')})`);
    if (o.id) ids.add(o.id); d.req.forEach(k => o[k] === undefined && err(`${w}: нет «${k}»`));
    if (o.lith && !LITH.includes(o.lith)) err(`${w}: lith из ${LITH.join(', ')}`);
    for (const c of ['color', 'fluid', 'fluid2']) if (o[c] && !COLORS.includes(o[c])) err(`${w}: ${c} из единой легенды: ${COLORS.join(', ')}`);
    d.ex.forEach(([k, a]) => { const f = tryf(o[k], a.split(''), `${w}.${k}`); if (f) numeric.push([`${w}.${k}`, f, a]); });
    if (o.show !== undefined) tryf(o.show, [], w + '.show'); if (o.opacity !== undefined) tryf(o.opacity, [], w + '.opacity');
    if (o.type === 'section') { if (!['x', 'z'].includes(o.axis)) err(`${w}: axis — x или z`); tryf(o.at, [], w + '.at'); (o.classes || []).forEach((c, j) => { tryf(c.when, ['x', 'y', 'z'], `${w}.classes[${j}].when`); COLORS.includes(c.color) || err(`${w}.classes[${j}]: color из легенды: ${COLORS.join(', ')}`); if (c.share !== undefined) tryf(c.share, ['x', 'y', 'z'], `${w}.classes[${j}].share`); if (c.mix && !COLORS.includes(c.mix)) err(`${w}.classes[${j}]: mix из легенды`); }); if (!o.value && !o.classes) err(`${w}: нужно value (min,max,color) или classes`); if (o.value && (o.min === undefined || o.max === undefined)) err(`${w}: к value нужны min и max`); }
    if (o.type === 'tube') { (o.path || []).forEach((p, j) => arr3(p, [], `${w}.path[${j}]`)); tryf(o.radius, [], w); }
    if (['prefab', 'shape', 'label'].includes(o.type) && o.at) { if (Array.isArray(o.at)) arr3(o.at, [], w + '.at').forEach(f => f && numeric.push([w + '.at', f, ''])); else err(w + '.at: массив из трёх'); }
    if (o.type === 'prefab' && !PREFABS.includes(o.name)) err(`${w}: name из ${PREFABS.join(', ')}`);
    if (o.type === 'shape') { arr3(o.size, [], w + '.size').forEach(f => f && numeric.push([w + '.size', f, ''])); ['sphere', 'box', 'cylinder', 'ring', 'plane'].includes(o.shape) || err(`${w}: shape — sphere, box, cylinder, ring, plane`); }
    if (['particles', 'arrows'].includes(o.type)) { const v = o.velocity || o.vector; arr3(v, ['x', 'y', 'z'], w + '.velocity'); if (!o.box || o.box.length !== 2) err(`${w}.box: [[x,y,z],[x,y,z]] в метрах`); }
    if (o.type === 'scatter') { const a = ['i', 'r1', 'r2', 'r3']; arr3(o.at, a, w + '.at'); arr3(o.size, a, w + '.size'); if (o.n > 3000) err(w + ': n не больше 3000'); }
    if (o.type === 'column') { tryf(o.top, ['x', 'z'], w + '.top'); tryf(o.bottom, ['x', 'z'], w + '.bottom'); if (o.at !== 'picks') arr3([...(o.at || []), '0'], [], w + '.at'); if (o.good) tryf(o.good, ['x', 'y', 'z', 'v'], w + '.good'); }
    if (o.type === 'label') { try { M.text(o.text); } catch (e) { err(`${w}.text: ${e.message}`); } }
  });
  // --- числа: нет ли NaN, бесконечностей, вылета за мир
  for (const [w, f, a] of numeric) { let bad = null; for (const t of times) M.at({ t }, () => { for (const [x, z] of grid) { for (const y of a.includes('y') ? [y0, (y0 + y1) / 2, y1] : [0]) { const v = a === 'xz' ? f(x, z) : a === 'xyz' ? f(x, y, z) : f(); if (!Number.isFinite(v)) bad = `${w}: не число при x=${x}, z=${z}, t=${t / M.tu.k}`; else if (/\.(top|bottom|y|level)$/.test(w) && (v > y1 + (y1 - y0) * .5 || v < y0 - (y1 - y0) * .5)) bad = `${w}: значение ${v.toPrecision(4)} м вышло за world.y [${y0}, ${y1}]`; } if (!a) break; } }); if (bad) err(bad); }
  // --- единицы
  const dimOf = n => Object.hasOwn(M.U, n) ? M.U[n].dim : n === 't' ? M.tu.dim : spec.vars && spec.vars[n] ? (spec.vars[n].unit !== undefined ? unit(spec.vars[n].unit).dim : null) : spec.states && spec.states[n] ? unit(spec.states[n].unit).dim : ['T', 'step', 'revealed', 'picks'].includes(n) ? [0, 0, 0] : null;
  const L = [1, 0, 0], xyz = { x: L, y: L, z: L };
  for (const [n, v] of Object.entries(spec.vars || {})) { try { const d = dims(parse(v.expr), dimOf, m => err(`единицы в переменной ${n}: ${m}`)); if (v.unit === undefined) err(`переменная ${n}: укажите unit`); else if (d && unit(v.unit).dim.some((q, i) => Math.abs(q - d[i]) > 1e-9)) err(`переменная ${n}: формула даёт размерность м^${d[0]}·кг^${d[1]}·с^${d[2]}, а объявлено «${v.unit}»`); } catch (e) { err(e.message); } }
  for (const [n, s] of Object.entries(M.fsig)) { try { const ad = Object.fromEntries(s.args.map(a => [a, xyz[a] || (a === 't' ? M.tu.dim : null)])); dims(parse(spec.functions[s.key]), dimOf, m => err(`единицы в функции ${n}: ${m}`), ad); } catch (e) { err(e.message); } }
  for (const [n, s] of Object.entries(spec.states || {})) { try { const d = dims(parse(s.rate), dimOf, m => err(`единицы в скорости ${n}: ${m}`)), u = unit(s.unit).dim; if (d && [u[0], u[1], u[2] - 1].some((q, i) => Math.abs(q - d[i]) > 1e-9)) err(`состояние ${n}: rate должен быть «${s.unit} в секунду»`); } catch (e) { err(e.message); } }
  // --- происхождение чисел
  const claims = Object.fromEntries((spec.claims || []).map(c => [c.id, c]));
  for (const [n, p] of Object.entries(spec.params || {})) {
    if (!['book', 'assumption'].includes(p.from)) err(`параметр ${n}: from = book или assumption`);
    if (p.from === 'book') { const c = claims[p.claim]; if (!c) err(`параметр ${n}: from=book, но нет claim`); else { const nums = (c.quote.replace(/(\d),(\d)/g, '$1.$2').match(/\d+(?:\.\d+)?/g) || []).map(Number); const vals = p.range ? p.range : [p.value]; vals.forEach(v => nums.some(q => Math.abs(q - v) < 1e-9 || Math.abs(q * 1e3 - v) < 1e-6 || Math.abs(q / 1e3 - v) < 1e-9) || err(`параметр ${n}: числа ${v} нет в цитате ${p.claim}`)); } }
    if (p.control) { if (p.control.length !== 4) err(`параметр ${n}: control = [мин, макс, шаг, подпись]`); if (p.range && (p.range[0] < p.control[0] || p.range[1] > p.control[1])) err(`параметр ${n}: range шире control`); }
    if (p.value === undefined && !p.range) err(`параметр ${n}: нужно value или range`);
  }
  // --- игра
  const kinds = spec.steps.map(s => s.kind); const guesses = [];
  spec.steps.forEach((s, i) => {
    const w = `steps[${i}] ${s.kind}`, d = STEP[s.kind]; if (!d) return err(`${w}: в поле "kind" нужно одно из ${Object.keys(STEP).join(', ')}`); d.forEach(k => s[k] === undefined && err(`${w}: нет «${k}»`));
    if (s.kind === 'guess') { tryf(s.truth, [], w + '.truth'); guesses.push(s.id); try { unit(s.unit); } catch (e) { err(`${w}: ${e.message}`); } }
    if (s.kind === 'pick') { const f = tryf(s.score, ['x', 'z'], w + '.score'); if (!spec.objects.some(o => o.id === s.target && ['surface', 'solid'].includes(o.type))) err(`${w}: target — id объекта surface или solid`); if (f) { let mx = -1e99, mn = 1e99; grid.forEach(([x, z]) => { const v = f(x, z); mx = Math.max(mx, v); mn = Math.min(mn, v); }); if (mx - mn < 1e-12) err(`${w}: score одинаков везде — решать нечего`); if (mn < 0) err(`${w}: score должен быть ≥ 0`); } }
    if (s.kind === 'choose') { s.options.forEach((o, j) => { if (o.correct === undefined || !o.why) err(`${w}.options[${j}]: нужны text, correct (формула) и why`); else tryf(String(o.correct), [], `${w}.options[${j}].correct`); }); }
    if (s.kind === 'explore' && s.until !== undefined) tryf(s.until, [], w + '.until');
    for (const k of ['text', 'q']) if (s[k]) { try { M.text(s[k]); } catch (e) { err(`${w}: ${e.message}`); } if (s[k].split(/[.!?…]\s/).some(f => f.split(/\s+/).length > 22)) warn(`${w}: фраза длиннее 20 слов`); }
    (s.use || []).forEach(u => { const [a, b] = u.split(':'); if (a === 'time') { spec.time || err(`${w}: use time, но time не задан`); } else if (a === 'param') { (spec.params[b] && spec.params[b].control) || err(`${w}: у параметра «${b}» нет control`); } else if (a === 'chart') { (spec.charts || []).some(c => c.id === b) || err(`${w}: нет графика «${b}»`); } else if (a === 'read') { Object.hasOwn(spec.vars || {}, b) || err(`${w}: нет переменной «${b}»`); } else err(`${w}: use — time, param:имя, chart:id, read:переменная`); });
  });
  if (kinds[0] !== 'predict') err('первый шаг — predict: ученик сначала предполагает');
  if (!kinds.some(k => ['guess', 'pick', 'choose'].includes(k))) err('нет действия ученика: нужен guess, pick или choose');
  if (!kinds.includes('reveal')) err('нет шага reveal: ученик должен увидеть, чем кончилось');
  if (!spec.transfer || !spec.transfer.options || !spec.transfer.why) err('transfer: q, options, answer, why');
  // --- графики
  (spec.charts || []).forEach(c => { const w = `график «${c.id}»`; if (!c.x || c.x.var === undefined) return err(`${w}: x = {var,min,max,unit,label}`); (c.lines || []).forEach((l, j) => { COLORS.includes(l.color) || err(`${w}.lines[${j}]: color из легенды: ${COLORS.join(', ')}`); try { const own = !Object.hasOwn(M.P, c.x.var) && c.x.var !== 't'; M.fn(l.expr, own ? [c.x.var] : [], `${w}.lines[${j}]`); unit(l.unit); } catch (e) { err(e.message); } }); if (c.cursor !== undefined) tryf(c.cursor, [], `${w}.cursor`); try { unit(c.x.unit); } catch (e) { err(`${w}: ${e.message}`); } });
  // --- проверки физики по случайным случаям
  if (!spec.checks.length) err('checks пуст: запишите хотя бы 3 условия, которые обязаны выполняться'); else if (spec.checks.length < 3) err('checks: нужно не меньше 3');
  for (const sd of seeds) { let m; try { m = new Model(spec, sd); } catch (e) { err(e.message); break; }
    for (const c of spec.checks) { try { const vs = Object.keys(c.over || {}), f = m.fn(c.expr, vs.filter(v => v !== 't'), `check «${c.name}»`); let bad = null; const rec = (i, o) => { if (bad) return; if (i === vs.length) { m.at(o.t !== undefined ? { t: o.t } : {}, () => { if (!(f(...vs.filter(v => v !== 't').map(v => o[v])) > 0)) bad = o; }); return; } const [a, b, n = 7] = c.over[vs[i]], k = vs[i] === 't' ? m.tu.k : 1; for (let q = 0; q < n; q++) rec(i + 1, { ...o, [vs[i]]: (a + (b - a) * q / (n - 1)) * k }); }; rec(0, {}); if (bad) err(`нарушено «${c.name}» (случай ${sd}${Object.keys(bad).length ? ', ' + Object.entries(bad).map(([k, v]) => k + '=' + (k === 't' ? v / m.tu.k : v).toPrecision(4)).join(', ') : ''})`); } catch (e) { err(e.message); } }
    for (const x of spec.examples || []) { try { const o = {}; for (const [k, v] of Object.entries(x.at || {})) o[k] = k === 't' ? v * m.tu.k : Object.hasOwn(m.U, k) ? v * m.U[k].k : v; const v = m.at(o, () => m.fn(x.expr)()) / unit(x.unit).k; if (Math.abs(v - x.expect) > Math.abs(x.expect) * (x.tol ?? .05) + 1e-12) err(`пример автора «${x.name}»: модель даёт ${v.toPrecision(4)}, в книге ${x.expect}`); } catch (e) { err(`пример «${x.name}»: ${e.message}`); } }
    for (const s of spec.steps) if (s.kind === 'choose') { try { const ok = s.options.filter(o => m.at({ t: m.t1, revealed: 1 }, () => m.fn(String(o.correct))()) > 0).length; if (ok !== 1) err(`choose «${s.id}»: в случае ${sd} верных ответов ${ok}, должен быть ровно 1`); } catch (e) { err(e.message); } }
    for (const s of spec.steps) if (s.kind === 'guess') { try { const v = m.fn(s.truth)() / unit(s.unit).k; if (!(v >= s.min && v <= s.max)) err(`guess «${s.id}»: в случае ${sd} ответ ${v.toPrecision(3)} вне [${s.min}, ${s.max}]`); } catch (e) { err(e.message); } } }
  // --- мёртвые ползунки: параметр обязан что-то менять на экране
  const probe = () => { const o = []; for (const [, f, a] of numeric) for (const [x, z] of grid.slice(8, 40)) { o.push(a === 'xz' ? f(x, z) : a === 'xyz' ? f(x, (y0 + y1) / 2, z) : f()); if (!a) break; } for (const n in M.V) o.push(M.V[n]); return o.map(v => Number.isFinite(v) ? v.toPrecision(7) : 'x').join(); };
  for (const [n, p] of Object.entries(spec.params || {})) if (p.control) { let same = true; for (const t of times) if (M.at({ t, [n]: p.control[0] * M.U[n].k }, probe) !== M.at({ t, [n]: p.control[1] * M.U[n].k }, probe)) same = false; if (same) err(`ползунок ${n} ни на что не влияет`); }
  if (spec.time) { const a = M.at({ t: M.t0 }, probe), b = M.at({ t: M.t1 }, probe); if (a === b) err('время ни на что не влияет'); }
  if (spec.why_3d.length < 25) err('why_3d: объясните, почему плоской схемы мало; иначе выберите другой формат');
  if (spec.world.ve && spec.world.ve !== 1 && !spec.exaggerations.some(s => s.includes(String(spec.world.ve).replace('.', ',')) || s.includes(String(spec.world.ve)))) err(`вертикальное преувеличение ×${spec.world.ve} не названо в exaggerations`);
  return { E, W };
}
export const invariants = { lint: (s, c) => true };
