// Язык формул для сцен. Разбирается в дерево, чужой код не исполняется: только имена из белого списка.
import { fbm, noise3, clamp, lerp, smooth } from './models/util.js';
import { E1 } from './models/pressure.js';

export const BUILTIN = {
  sin: Math.sin, cos: Math.cos, tan: Math.tan, exp: Math.exp, ln: Math.log, log10: Math.log10, sqrt: Math.sqrt, abs: Math.abs,
  min: Math.min, max: Math.max, pow: Math.pow, floor: Math.floor, sign: Math.sign, atan2: Math.atan2, hypot: Math.hypot,
  mod: (a, b) => a - b * Math.floor(a / b), clamp, lerp, smooth, step: (a, x) => (x >= a ? 1 : 0), gauss: x => Math.exp(-x * x),
  erf: x => { const s = Math.sign(x), a = Math.abs(x), t = 1 / (1 + 0.3275911 * a); return s * (1 - (((((1.061405429 * t - 1.453152027) * t) + 1.421413741) * t - 0.284496736) * t + 0.254829592) * t * Math.exp(-a * a)); },
  E1, noise: noise3, fbm, if: (c, a, b) => (c ? a : b),
};
const NARGS = { sin: 1, cos: 1, tan: 1, exp: 1, ln: 1, log10: 1, sqrt: 1, abs: 1, pow: 2, floor: 1, sign: 1, atan2: 2, mod: 2, clamp: 3, lerp: 3, smooth: 3, step: 2, gauss: 1, erf: 1, E1: 1, if: 3 };

// ---------- разбор
export function parse(src) {
  const toks = []; const re = /\s*(?:(\d+\.?\d*(?:[eE][+-]?\d+)?|\.\d+)|([A-Za-z_][A-Za-z_0-9]*)|(<=|>=|==|!=|&&|\|\||[-+*/^()<>,?:!]))/y;
  let m; re.lastIndex = 0; const s = String(src);
  while (re.lastIndex < s.length) { const i = re.lastIndex; m = re.exec(s); if (!m) { if (/^\s*$/.test(s.slice(i))) break; throw new Error(`непонятный символ «${s.slice(i).trim()[0]}» в «${s}»`); } toks.push(m[1] !== undefined ? { n: +m[1] } : m[2] ? { id: m[2] } : { op: m[3] }); }
  let p = 0; const is = o => toks[p] && toks[p].op === o, eat = o => { if (!is(o)) throw new Error(`ожидалось «${o}» в «${s}»`); p++; };
  const bin = (next, ops) => () => { let a = next(); while (toks[p] && ops.includes(toks[p].op)) { const op = toks[p++].op; a = { op, a, b: next() }; } return a; };
  function prim() {
    const t = toks[p]; if (!t) throw new Error(`формула оборвана: «${s}»`);
    if (t.n !== undefined) { p++; return { n: t.n }; }
    if (t.id) { p++; if (is('(')) { p++; const args = []; if (!is(')')) do { args.push(tern()); } while (is(',') && ++p); eat(')'); return { call: t.id, args }; } return { id: t.id }; }
    if (is('(')) { p++; const e = tern(); eat(')'); return e; }
    throw new Error(`неожиданно «${t.op}» в «${s}»`);
  }
  function pow() { const a = prim(); if (is('^')) { p++; return { op: '^', a, b: unary() }; } return a; }
  function unary() { if (is('-')) { p++; return { neg: unary() }; } if (is('+')) { p++; return unary(); } if (is('!')) { p++; return { not: unary() }; } return pow(); }
  const mul = bin(unary, ['*', '/']), add = bin(mul, ['+', '-']), cmp = bin(add, ['<', '>', '<=', '>=', '==', '!=']), and = bin(cmp, ['&&']), or = bin(and, ['||']);
  function tern() { const c = or(); if (is('?')) { p++; const a = tern(); eat(':'); return { c, a, b: tern() }; } return c; }
  const r = tern(); if (p < toks.length) throw new Error(`лишнее после формулы: «${s}»`); return r;
}
export function names(ast, ids = new Set(), calls = new Set()) {
  if (ast.id) ids.add(ast.id); if (ast.call) { calls.add(ast.call); ast.args.forEach(a => names(a, ids, calls)); }
  for (const k of ['a', 'b', 'c', 'neg', 'not']) if (ast[k]) names(ast[k], ids, calls);
  return { ids, calls };
}
// ---------- сборка в функцию (текст строится только из проверенного дерева)
export function code(ast, scope, args) {
  const g = a => {
    if (a.n !== undefined) return String(a.n);
    if (a.id) { if (a.id === 'pi') return 'Math.PI'; if (args.includes(a.id)) return '$' + a.id; const s = /^(constructor|prototype|__proto__)$/.test(a.id) ? null : scope.id(a.id); if (!s) throw new Error(`неизвестное имя «${a.id}»`); return s; }
    if (a.call) { const s = scope.call(a.call, a.args.length); if (!s) throw new Error(`неизвестная функция «${a.call}»`); return `${s}(${a.args.map(g).join(',')})`; }
    if (a.neg) return `(-${g(a.neg)})`; if (a.not) return `(${g(a.not)}?0:1)`;
    if (a.c) return `(${g(a.c)}?${g(a.a)}:${g(a.b)})`;
    if (a.op === '^') return `Math.pow(${g(a.a)},${g(a.b)})`;
    if (['<', '>', '<=', '>=', '==', '!='].includes(a.op)) return `(${g(a.a)}${a.op}${g(a.b)}?1:0)`;
    if (a.op === '&&' || a.op === '||') return `((${g(a.a)})${a.op}(${g(a.b)})?1:0)`;
    return `(${g(a.a)}${a.op}${g(a.b)})`;
  };
  return g(ast);
}
export const builtinCall = (n, k) => { if (!Object.hasOwn(BUILTIN, n)) return null; if (NARGS[n] !== undefined && NARGS[n] !== k) throw new Error(`«${n}» ждёт ${NARGS[n]} арг., дано ${k}`); return 'B.' + n; };

// ---------- единицы: всё считается в СИ, размерность [м, кг, с]
const Uu = { m: [1, 1, 0, 0], cm: [.01, 1, 0, 0], mm: [.001, 1, 0, 0], um: [1e-6, 1, 0, 0], km: [1e3, 1, 0, 0], kg: [1, 0, 1, 0], g: [1e-3, 0, 1, 0], t: [1e3, 0, 1, 0],
  s: [1, 0, 0, 1], min: [60, 0, 0, 1], h: [3600, 0, 0, 1], d: [86400, 0, 0, 1], yr: [31557600, 0, 0, 1], kyr: [31557600e3, 0, 0, 1], Myr: [31557600e6, 0, 0, 1],
  Pa: [1, -1, 1, -2], kPa: [1e3, -1, 1, -2], MPa: [1e6, -1, 1, -2], bar: [1e5, -1, 1, -2], atm: [101325, -1, 1, -2], N: [1, 1, 1, -2], mPas: [1e-3, -1, 1, -1], D: [9.869e-13, 2, 0, 0], mD: [9.869e-16, 2, 0, 0], '%': [.01, 0, 0, 0], deg: [Math.PI / 180, 0, 0, 0], rad: [1, 0, 0, 0], C: [1, 0, 0, 0], ohm: [1, 0, 0, 0], ppt: [1, 0, 0, 0] };
export const UNIT_NAMES = Object.keys(Uu);
const RU = { m: 'м', cm: 'см', mm: 'мм', um: 'мкм', km: 'км', kg: 'кг', g: 'г', t: 'т', s: 'с', min: 'мин', h: 'ч', d: 'сут', yr: 'лет', kyr: 'тыс. лет', Myr: 'млн лет', Pa: 'Па', kPa: 'кПа', MPa: 'МПа', bar: 'бар', atm: 'атм', N: 'Н', mPas: 'мПа·с', D: 'Д', mD: 'мД', deg: '°', rad: 'рад', C: '°C', ohm: 'Ом', ppt: 'г/л' };
const RU_UNIT = { м: 'm', см: 'cm', мм: 'mm', км: 'km', кг: 'kg', г: 'g', т: 't', с: 's', мин: 'min', ч: 'h', сут: 'd', год: 'yr', лет: 'yr', Па: 'Pa', кПа: 'kPa', МПа: 'MPa', бар: 'bar', атм: 'atm', Н: 'N', Д: 'D', мД: 'mD', Ом: 'ohm', град: 'deg' };
export function unit(u) {
  let k = 1, dim = [0, 0, 0]; if (!u || u === '1') return { k, dim }; u = String(u).replace(/[·⋅]/g, '*').replace(/[А-Яа-яЁё]+/g, w => RU_UNIT[w] || w);
  let sg = 1; for (const part of u.split(/([*/])/)) {
    if (part === '*') { sg = 1; continue; } if (part === '/') { sg = -1; continue; } if (part === '1') continue;
    const m = /^([A-Za-z%]+)\^?(-?\d+)?$/.exec(part.trim()); if (!m || !Object.hasOwn(Uu, m[1])) throw new Error(`неизвестная единица «${part}» (есть: ${UNIT_NAMES.join(' ')})`);
    const e = sg * (m[2] ? +m[2] : 1), q = Uu[m[1]]; k *= Math.pow(q[0], e); dim = dim.map((d, i) => d + e * q[i + 1]);
  }
  return { k, dim };
}
const SUP = { '-': '⁻', 0: '⁰', 1: '¹', 2: '²', 3: '³', 4: '⁴', 5: '⁵', 6: '⁶', 7: '⁷', 8: '⁸', 9: '⁹' };
export const unitRu = u => (!u || u === '1') ? '' : u.replace(/([A-Za-z]+)\^?(-?\d+)?/g, (_, n, e) => (RU[n] || n) + (e ? [...e].map(c => SUP[c]).join('') : '')).replace(/\*/g, '·');

// Размерность выражения. null — неизвестна (не проверяем). Возвращает список несоответствий.
export function dims(ast, dimOf, warn, argDim = {}) {
  const same = (a, b) => a.every((v, i) => Math.abs(v - b[i]) < 1e-9), zero = d => d.every(v => Math.abs(v) < 1e-9);
  const f = a => {
    if (a.n !== undefined) return { lit: a.n, d: [0, 0, 0] };
    if (a.id) { const d = a.id === 'pi' ? [0, 0, 0] : argDim[a.id] !== undefined ? argDim[a.id] : dimOf(a.id); return { d }; }
    if (a.neg) return f(a.neg); if (a.not) { f(a.not); return { d: [0, 0, 0] }; }
    if (a.c) { f(a.c); const x = f(a.a), y = f(a.b); return x.lit !== undefined ? y : x; }
    if (a.call) {
      const xs = a.args.map(f), n = a.call;
      if (['sin', 'cos', 'tan', 'exp', 'ln', 'log10', 'erf', 'E1', 'gauss'].includes(n)) { if (xs[0].d && !zero(xs[0].d)) warn(`аргумент ${n}() должен быть безразмерным: делите на параметр с той же единицей, а не на число`); return { d: [0, 0, 0] }; }
      if (n === 'sqrt') return { d: xs[0].d && xs[0].d.map(v => v / 2) };
      if (['abs', 'floor'].includes(n)) return xs[0]; if (['min', 'max', 'hypot', 'mod'].includes(n)) return xs.find(x => x.lit === undefined) || xs[0];
      if (n === 'clamp') return xs[0]; if (n === 'lerp') return xs[0].lit !== undefined ? xs[1] : xs[0]; if (n === 'if') return xs[1].lit !== undefined ? xs[2] : xs[1];
      if (['smooth', 'step', 'sign', 'noise', 'fbm', 'atan2'].includes(n)) return { d: [0, 0, 0] };
      if (n === 'pow' && xs[1].lit !== undefined) return { d: xs[0].d && xs[0].d.map(v => v * xs[1].lit) };
      return { d: null };
    }
    const x = f(a.a), y = f(a.b);
    // число × безразмерное (амплитуда шума и т. п.) может стать любой величиной
    const soft = (x.lit !== undefined || x.soft) && y.d && zero(y.d) || (y.lit !== undefined || y.soft) && x.d && zero(x.d);
    if (a.op === '*') return { soft, d: x.d && y.d ? x.d.map((v, i) => v + y.d[i]) : null };
    if (a.op === '/') return { d: x.d && y.d ? x.d.map((v, i) => v - y.d[i]) : null };
    if (a.op === '^') return { d: x.d && y.lit !== undefined ? x.d.map(v => v * y.lit) : x.d && zero(x.d) ? [0, 0, 0] : null };
    if (['&&', '||'].includes(a.op)) return { d: [0, 0, 0] };
    if (x.lit === undefined && y.lit === undefined && !x.soft && !y.soft && x.d && y.d && !same(x.d, y.d)) warn(`«${a.op}» между разными размерностями`);
    if (['<', '>', '<=', '>=', '==', '!='].includes(a.op)) return { d: [0, 0, 0] };
    return x.lit !== undefined || (x.soft && y.lit === undefined) ? y : x;
  };
  const r = f(ast); return r.soft || r.lit !== undefined ? null : r.d;
}
