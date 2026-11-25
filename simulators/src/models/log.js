// Модель «прибор и кривая»: породы → отклики приборов → оценка → итог испытания.
// Кривые, картинка и итог испытания вычисляются из одного массива layers.
import { rng, between, gauss, clamp, lerp } from './util.js';

const KINDS = ['shale', 'oil', 'oilclay', 'water', 'mix', 'dense'];
export const LITH = { shale: 'shale', oil: 'sand', oilclay: 'sand', water: 'sand', mix: 'sand', dense: 'dense' };
export const FLUID = { oil: 'oil', oilclay: 'oil', water: 'water', mix: 'oil' };

// Пороги по αсп — таблица 22 (интерполяция между строками, за пределы не выходим).
export function thresholds(table, alpha) {
  const t = [...table].sort((a, b) => a.alpha - b.alpha);
  const a = clamp(alpha, t[0].alpha, t[t.length - 1].alpha);
  for (let i = 0; i < t.length - 1; i++) if (a <= t[i + 1].alpha) {
    const k = (a - t[i].alpha) / (t[i + 1].alpha - t[i].alpha);
    return { oil: lerp(t[i].oil, t[i + 1].oil, k), water: lerp(t[i].water, t[i + 1].water, k) };
  }
  return t[t.length - 1];
}
export function classify(table, Pn, alpha) {
  const th = thresholds(table, alpha);
  return Pn > th.oil ? 'oil' : Pn < th.water ? 'water' : 'mix';
}
export const formationFactor = (kp, m) => Math.pow(kp, -m);

export function buildCase(spec, seed) {
  const r = rng(seed), p = spec.params, layers = [];
  // Обязательный набор ловушек + случайные добавки; порядок перемешан.
  const bag = [...spec.generator.must];
  while (bag.length < spec.generator.targets) bag.push(spec.generator.extra[Math.floor(r() * spec.generator.extra.length)]);
  for (let i = bag.length - 1; i > 0; i--) { const j = Math.floor(r() * (i + 1)); [bag[i], bag[j]] = [bag[j], bag[i]]; }
  let z = p.top;
  const push = (kind, h) => {
    let alpha, kp, Pn, rho;
    if (kind === 'shale') { alpha = 0.02 + 0.06 * r(); kp = 0.10 + 0.04 * r(); Pn = 1; rho = between(r, p.rho_shale); }
    else if (kind === 'dense') { alpha = 0.05 + 0.08 * r(); kp = between(r, p.kp_dense); Pn = 1; rho = formationFactor(kp, p.m) * p.rho_w; }
    else {
      alpha = kind === 'oilclay' ? between(r, [0.71, 0.76]) : kind === 'oil' ? between(r, [0.95, 1]) : between(r, [0.9, 1]);
      kp = kind === 'oilclay' ? between(r, [0.17, 0.2]) : between(r, [0.18, 0.24]);
      const th = thresholds(p.table, alpha);
      Pn = kind === 'oil' ? th.oil * between(r, [1.25, 1.7])
        : kind === 'oilclay' ? th.oil * between(r, [1.25, 1.5])
        : kind === 'water' ? between(r, [1.0, 1.2])
        : Math.sqrt(th.oil * th.water) * between(r, [0.95, 1.15]);
      rho = Pn * formationFactor(kp, p.m) * p.rho_w;
    }
    layers.push({ kind, lith: LITH[kind], fluid: FLUID[kind] || null, collector: !!FLUID[kind], alpha, kp, Pn, rho, top: z, bot: z + h });
    z += h;
  };
  push('shale', 5 + 2 * r());
  bag.forEach(k => { push(k, between(r, p.h_target)); push('shale', between(r, p.h_shale)); });
  let n = 0;
  layers.forEach(l => { if (l.kind !== 'shale') l.n = ++n; });
  return { layers, top: p.top, bot: z, seed };
}

// Прибор усредняет по окну ~ своей вертикальной разрешённости и шумит.
export function curves(spec, cs) {
  const p = spec.params, dz = p.dz, N = Math.floor((cs.bot - cs.top) / dz) + 1, r = rng(cs.seed ^ 0x9e37);
  const at = z => cs.layers.find(l => z < l.bot) || cs.layers[cs.layers.length - 1];
  // Амплитуда ПС зависит от соотношения сопротивлений фильтрата и пластовой воды.
  const ssp = -p.sp_k * Math.log10(p.rho_f / p.rho_w);
  const raw = { SP: [], GR: [], RES: [], POR: [] }, depth = [];
  for (let i = 0; i < N; i++) {
    const z = cs.top + i * dz, l = at(z); depth.push(z);
    raw.SP.push(l.alpha * ssp);
    raw.GR.push(p.gr_sand + (p.gr_shale - p.gr_sand) * (1 - (l.kind === 'dense' ? 0.95 : l.alpha)));
    raw.RES.push(Math.log10(l.rho));
    raw.POR.push(l.kind === 'shale' ? l.kp + p.clay_por : l.kp);
  }
  const out = { depth };
  const sm = { SP: 0.8, GR: 0.5, RES: 0.5, POR: 0.4 }, nz = { SP: 0.8, GR: 2, RES: 0.01, POR: 0.003 };
  for (const k in raw) {
    const s = sm[k] / dz, R = Math.ceil(3 * s);
    out[k] = raw[k].map((_, i) => {
      let a = 0, w = 0;
      for (let j = -R; j <= R; j++) { const q = clamp(i + j, 0, N - 1), g = Math.exp(-j * j / (2 * s * s)); a += g * raw[k][q]; w += g; }
      return a / w + nz[k] * gauss(r);
    });
  }
  out.RES = out.RES.map(x => Math.pow(10, x));
  out.ssp = ssp;
  return out;
}

// Оценка по кривым: так же, как сделал бы интерпретатор, без доступа к layers.kind.
export function estimate(spec, cs, cv, l) {
  const p = spec.params, mid = (l.top + l.bot) / 2, half = Math.max(0.3, (l.bot - l.top) * 0.22);
  const idx = [];
  cv.depth.forEach((z, i) => { if (Math.abs(z - mid) <= half) idx.push(i); });
  const mean = a => idx.reduce((s, i) => s + a[i], 0) / idx.length;
  const rho = Math.pow(10, mean(cv.RES.map(Math.log10)));
  const kp = mean(cv.POR);
  const spOk = Math.abs(cv.ssp) > 15;
  const alpha = spOk ? clamp(mean(cv.SP) / cv.ssp, 0, 1) : null;
  const vp = formationFactor(kp, p.m) * p.rho_w;
  // Диапазон, а не число: ошибка ρв и ошибка kп.
  const lo = rho / (formationFactor(kp * (1 - p.err_kp), p.m) * p.rho_w * (1 + p.err_rw));
  const hi = rho / (formationFactor(kp * (1 + p.err_kp), p.m) * p.rho_w * (1 - p.err_rw));
  return { rho, kp, alpha, Pn: rho / vp, lo, hi, vp };
}
// Истинный итог испытания.
export function testResult(spec, l) {
  if (!l.collector) return 'dry';
  return classify(spec.params.table, l.Pn, l.alpha);
}
export const invariants = {
  layers_contiguous: (s, c) => c.layers.every((l, i) => !i || Math.abs(l.top - c.layers[i - 1].bot) < 1e-9),
  depth_down: (s, c) => c.layers.every(l => l.bot > l.top),
  pn_ge_1: (s, c) => c.layers.every(l => l.Pn >= 1),
  sp_sign_matches_mud: (s, c) => { const x = curves(s, c).ssp, k = s.params.rho_f / s.params.rho_w; return k > 1 ? x < 0 : k < 1 ? x > 0 : true; },
  trap_present: (s, c) => c.layers.some(l => l.kind === 'dense') && c.layers.some(l => l.kind === 'oilclay'),
  dense_looks_like_oil: (s, c) => { const d = c.layers.filter(l => l.kind === 'dense'), o = c.layers.filter(l => l.kind === 'oilclay'); return d.every(a => o.every(b => a.rho > b.rho)); },
  kinds_known: s => [...s.generator.must, ...s.generator.extra].every(k => KINDS.includes(k)),
};
