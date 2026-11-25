// Детерминированный генератор: один seed — один и тот же случай у всех.
export function rng(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
export const between = (r, [a, b]) => a + (b - a) * r();
export const clamp = (x, a, b) => Math.min(b, Math.max(a, x));
export const lerp = (a, b, t) => a + (b - a) * t;
export const smooth = (a, b, x) => { const t = clamp((x - a) / (b - a), 0, 1); return t * t * (3 - 2 * t); };
export function gauss(r) { return Math.sqrt(-2 * Math.log(1 - r())) * Math.cos(2 * Math.PI * r()); }

function hash3(x, y, z, s) {
  let h = Math.imul(x, 374761393) ^ Math.imul(y, 668265263) ^ Math.imul(z, 1103515245) ^ Math.imul(s, 1274126177);
  h = Math.imul(h ^ (h >>> 13), 1274126177);
  h = Math.imul(h ^ (h >>> 15), 0x2c1b3c6d);
  return ((h ^ (h >>> 16)) >>> 0) / 4294967296;
}
export function noise3(x, y, z, s = 0) {
  const xi = Math.floor(x), yi = Math.floor(y), zi = Math.floor(z);
  const f = t => t * t * (3 - 2 * t);
  const u = f(x - xi), v = f(y - yi), w = f(z - zi);
  const c = (i, j, k) => hash3(xi + i, yi + j, zi + k, s);
  return lerp(
    lerp(lerp(c(0, 0, 0), c(1, 0, 0), u), lerp(c(0, 1, 0), c(1, 1, 0), u), v),
    lerp(lerp(c(0, 0, 1), c(1, 0, 1), u), lerp(c(0, 1, 1), c(1, 1, 1), u), v), w) * 2 - 1;
}
export function fbm(x, y, z, s = 0, oct = 4) {
  let a = 0.5, sum = 0;
  for (let i = 0; i < oct; i++) { sum += a * noise3(x, y, z, s + i); x *= 2.03; y *= 2.03; z *= 2.03; a *= 0.5; }
  return sum;
}
