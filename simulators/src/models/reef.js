// Модель «тело и зоны»: форма рифа, зоны пористости, рост во времени, скважины.
import { rng, between, fbm, clamp, smooth, lerp } from './util.js';
export function buildCase(spec, seed) {
  const r = rng(seed), p = spec.params;
  return { seed, type: spec.reef_type, R: between(r, p.R), H: between(r, p.H), ell: between(r, p.ellipse), rot: r() * Math.PI,
    owc: between(r, p.owc_frac), L: p.domain, spec };
}
// q — нормированный радиус: 0 центр, 1 край тела.
export function polar(c, x, z) {
  const ca = Math.cos(c.rot), sa = Math.sin(c.rot), u = (x * ca + z * sa) / c.ell, v = (-x * sa + z * ca) * c.ell;
  return { q: Math.hypot(u, v) / c.R * (1 + 0.13 * fbm(u / c.R * 1.6, v / c.R * 1.6, 3.1, c.seed, 3)), u, v };
}
function profile(type, q) {
  if (type === 'dome') return Math.pow(Math.max(0, Math.cos(Math.min(q, 1) * Math.PI / 2)), 1.15);
  const rim = Math.exp(-Math.pow((q - 0.72) / 0.13, 2)), plat = 1 - smooth(0.78, 1.14, q);
  return clamp(0.74 * plat + 0.27 * rim, 0, 1);
}
export function height(c, x, z) {
  const { q } = polar(c, x, z);
  const k = profile(c.type, q);
  return c.H * Math.max(0, k + smooth(0, 0.12, k) * 0.05 * fbm(x / 150, z / 150, 0, c.seed + 9, 4));
}
export function zone(c, x, z) {
  const { q } = polar(c, x, z);
  if (c.type === 'dome') return q < 0.45 ? 'core' : q < 1.0 ? 'wing' : 'off';
  return q < 0.55 ? 'lagoon' : q < 0.86 ? 'crest' : q < 1.12 ? 'slope' : 'off';
}
// Пористость, %: зона задаёт диапазон автора, слои и линзы — положение внутри диапазона.
export function porosity(c, x, y, z) {
  const top = height(c, x, z); if (y > top || y < 0) return null;
  const { q } = polar(c, x, z), Z = c.spec.zones;
  const lens = clamp(0.5 + 0.8 * fbm(x / 260, y / (c.H * 0.11), z / 260, c.seed + 30, 3), 0, 1);
  const val = n => lerp(Z[n].phi[0], Z[n].phi[1], lens);
  if (c.type === 'dome') return lerp(val('core'), val('wing'), smooth(0.38, 0.52, q));
  const a = lerp(val('lagoon'), val('crest'), smooth(0.50, 0.60, q));
  return lerp(a, val('slope'), smooth(0.82, 0.90, q));
}
export const owcY = c => c.H * c.owc;
export function drill(c, x, z, n = 64) {
  const top = height(c, x, z), w = owcY(c), dy = c.H * 1.05 / n, col = [];
  let net = 0, vol = 0;
  for (let i = 0; i < n; i++) {
    const y = (i + 0.5) * dy, phi = porosity(c, x, y, z), pay = phi !== null && y > w && phi >= c.spec.params.cutoff;
    col.push({ y, phi, pay }); if (pay) { net += dy; vol += dy * phi / 100; }
  }
  return { x, z, top, zone: zone(c, x, z), net, vol, col, dy };
}
// Лучший достижимый результат тем же числом скважин (жадный поиск по сетке).
export function best(c, wells, minDist) {
  const pts = [];
  for (let i = -22; i <= 22; i++) for (let j = -22; j <= 22; j++) { const d = drill(c, i / 22 * c.L / 2, j / 22 * c.L / 2, 28); if (d.vol > 0) pts.push(d); }
  pts.sort((a, b) => b.vol - a.vol);
  const out = [];
  for (const p of pts) { if (out.length >= wells) break; if (out.every(o => Math.hypot(o.x - p.x, o.z - p.z) >= minDist)) out.push(p); }
  return out;
}
// Рост: вершина догоняет поднимающийся уровень моря, затем тело перекрывают осадки.
export function stage(c, t) {
  const g = smooth(0, 0.6, t), sea = c.H * lerp(0.12, 1.06, g), bury = smooth(0.68, 1, t);
  return { grow: lerp(0.06, 1, g), sea: lerp(sea, c.H * 1.45, smooth(0.62, 0.75, t)), bury: bury * c.H * 1.14, phase: t < 0.6 ? 'grow' : t < 0.7 ? 'drown' : 'bury' };
}
export const invariants = {
  reef_below_sea: (s, c) => [0.2, 0.4, 0.6].every(t => stage(c, t).grow * c.H <= stage(c, t).sea + 0.12 * c.H),
  phi_in_author_range: (s, c) => {
    const all = Object.values(s.zones).map(z => z.phi), lo = Math.min(...all.map(a => a[0])), hi = Math.max(...all.map(a => a[1]));
    for (let i = 0; i < 400; i++) { const x = (i % 20 - 10) * c.L / 22, z = (Math.floor(i / 20) - 10) * c.L / 22, v = porosity(c, x, c.H * 0.3, z); if (v !== null && (v < lo - 1e-9 || v > hi + 1e-9)) return false; }
    return true;
  },
  best_zone_matches_book: (s, c) => { const b = best(c, 3, 100); return b.length > 0 && b.every(w => s.best_zones.includes(w.zone)); },
  has_seal: (s, c) => stage(c, 1).bury > c.H,
  oil_above_water: (s, c) => owcY(c) > 0 && owcY(c) < c.H,
};
