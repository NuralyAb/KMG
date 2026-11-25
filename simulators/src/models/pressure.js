// Модель «поле давления»: основная формула теории упругого режима (23.52).
import { rng, between } from './util.js';
// E1(x) = −Ei(−x): ряд при x<1, цепная дробь при x≥1.
export function E1(x) {
  if (x <= 0) return Infinity;
  if (x < 1) { let s = -0.5772156649015329 - Math.log(x), t = 1; for (let n = 1; n < 40; n++) { t *= -x / n; s -= t / n; } return s; }
  if (x > 700) return 0;
  let b = x + 1, c = 1e300, d = 1 / b, h = d;
  for (let i = 1; i < 200; i++) { const a = -i * i; b += 2; d = 1 / (a * d + b); c = b + a / c; const q = c * d; h *= q; if (Math.abs(q - 1) < 1e-12) break; }
  return h * Math.exp(-x);
}
// Единицы спецификации: k — мкм² (1e-12 м²), mu — мПа·с, beta — 1e-10 1/Па, Q — м³/сут, h — м, давление — МПа.
export const kappa = p => (p.k * 1e-12) / (p.mu * 1e-3 * p.beta * 1e-10);
export const unitDrop = p => (p.Q / 86400) * p.mu * 1e-3 / (4 * Math.PI * p.k * 1e-12 * p.h) / 1e6;
export const drop = (p, r, t) => t <= 0 ? 0 : unitDrop(p) * E1(r * r / (4 * kappa(p) * t));
export const pressure = (p, r, t) => p.p0 - drop(p, Math.max(r, p.rw), t);
export const front = (p, t) => 2 * Math.sqrt(kappa(p) * t);   // условный радиус возмущения
export const arrival = (p, r) => r * r / (4 * kappa(p));      // момент самого быстрого падения в точке r
export function buildCase(spec, seed) {
  const r = rng(seed), g = spec.generator, p = { ...spec.params };
  for (const k in g.vary) p[k] = +between(r, g.vary[k]).toPrecision(2);
  return { p, seed, obs: Math.round(between(r, g.obs) / 10) * 10 };
}
export const invariants = {
  kappa_in_book_range: (s, c) => { const k = kappa(c.p); return k >= s.limits.kappa[0] && k <= s.limits.kappa[1]; },
  pressure_positive: (s, c) => pressure(c.p, c.p.rw, s.params.t_max) > 0,
  monotone_in_r: (s, c) => { let q = -1; for (let r = 1; r < 2000; r *= 1.5) { const v = pressure(c.p, r, 86400); if (v < q) return false; q = v; } return true; },
  front_sqrt_t: (s, c) => Math.abs(front(c.p, 400) / front(c.p, 100) - 2) < 1e-9,
  log_approx_agrees: () => { const x = 0.01; return Math.abs((Math.log(1 / x) - 0.5772) / E1(x) - 1) < 0.0035; },
};
