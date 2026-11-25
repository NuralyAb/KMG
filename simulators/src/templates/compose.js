// Универсальный шаблон: собирает сцену и игру из спецификации агента.
import { THREE, rockMaterial, LEG, steel, paint, tex } from '../core.js';
import { derrick, loggingTruck, loggingTool, shadow } from '../prefabs.js';
import { Model } from '../models/compose.js';
import { unit, unitRu } from '../expr.js';
import { rng, clamp } from '../models/util.js';
import { $, fmt, section, prediction, verdict, closing, honesty, canvas, slider, question } from '../ui.js';

const COL = { ...LEG, dolomite: '#A98FD1', salt: '#C9D6DF', anhydrite: '#D98CB3', steel: '#aab2b9' };
const TEXOF = { sand: 'sand', shale: 'shale', limestone: 'limestone', dolomite: 'limestone', dense: 'dense', reef: 'reef', salt: 'limestone', anhydrite: 'limestone' };
const rgb = h => { const c = new THREE.Color(h); return [c.r, c.g, c.b]; };
function ramp(k, colr) { k = clamp(k, 0, 1); const lo = [.03, .04, .055], hi = [1, .97, .88], m = (a, b, t) => a + (b - a) * t; return k < .65 ? lo.map((v, i) => m(v, colr[i], k / .65)) : colr.map((v, i) => m(v, hi[i], (k - .65) / .35)); }

// Срез породы: зёрна и флюид в порах, а не ровная заливка
const FLUIDS = ['oil', 'gas', 'water', 'filtrate'], hash = (a, b, k) => { const v = Math.sin(a * 127.1 + b * 311.7 + k * 74.7) * 43758.5453; return v - Math.floor(v); };
function grain(d, w, h, id, sh) {
  const G = 6, srgb = n => { const c = new THREE.Color(COL[n]); return [c.r, c.g, c.b].map(v => 255 * (v <= .0031308 ? v * 12.92 : 1.055 * v ** (1 / 2.4) - .055)); }, memo = {}, col = n => (memo[n] = memo[n] || srgb(n)), sand = col('sand');
  for (let j = 0; j < h; j++) for (let i = 0; i < w; i++) {
    const c = id[j * w + i]; if (!c) continue; const k = (j * w + i) * 4, fl = FLUIDS.includes(c.color), gi = Math.floor(i / G), gj = Math.floor(j / G); let m = 9, t = 0;
    for (let a = -1; a <= 1; a++) for (let b = -1; b <= 1; b++) { const q = Math.hypot(gi + a + hash(gi + a, gj + b, 1) - i / G, gj + b + hash(gi + a, gj + b, 2) - j / G); if (q < m) { m = q; t = hash(gi + a, gj + b, 3); } }
    const pore = fl && m > .27 + .12 * t, f = c.mix && hash(Math.floor(i / 22 + hash(gi, gj, 5)), Math.floor(j / 14 + hash(gi, gj, 6)), 4) < (sh ? sh[j * w + i] : .5) ? c.mix : c.color, base = fl ? (pore ? col(f) : sand) : [d[k], d[k + 1], d[k + 2]], s = (pore ? .96 : fl ? .78 + .2 * t - .18 * m : .84 + .22 * t - .1 * m);
    for (let q = 0; q < 3; q++) d[k + q] = base[q] * s;
    const up = j > 0 ? id[(j - 1) * w + i] : c; if (up && up !== c) for (let q = 0; q < 3; q++) d[k + q] *= .45;
  }
}

export function build(stage, spec, seed, panel) {
  const M = new Model(spec, seed), S = stage.scene, [X, , Z] = spec.world.size, [y0, y1] = spec.world.y || [0, spec.world.size[1]], ve = spec.world.ve || 1;
  const U = Math.max(X, Z) / 100, sx = v => v / U, sy = y => (y - (y0 + y1) / 2) / U * ve, sv = v => v / U * ve, H = sv(y1 - y0);
  const labels = []; // подписи: важные видны всегда, остальные прячутся, если налезают
  const ups = [], frames = [], pickables = {}, clipP = new THREE.Plane(new THREE.Vector3(0, 0, -1), 1e6); let useClip = false;
  const f = (s, a = []) => M.fn(String(s), a), f3 = (a, args = []) => a.map(s => f(s, args));
  const dynAny = list => list.some(s => s !== undefined && M.dynamic(String(s)));
  const secO = spec.objects.find(o => o.type === 'section' && o.cut !== false);
  if (secO) { useClip = true; clipP.normal.set(secO.axis === 'x' ? -1 : 0, 0, secO.axis === 'z' ? -1 : 0); const at = f(secO.at); ups.push({ d: dynAny([secO.at]), u: () => { clipP.constant = sx(at()); } }); }
  const clipOpt = o => (useClip && o.clip !== false ? { clippingPlanes: [clipP] } : {});
  // величины, от которых зависят формулы: не изменились — объект не пересчитывается
  const watch = list => { const ns = new Set(); list.forEach(s => s !== undefined && M.deps(String(s)).forEach(n => ns.add(n))); const a = [...ns]; return () => a.map(n => M.P[n] ?? M.V[n] ?? M.S[n] ?? M.E[n]).join(); };
  const common = (o, mesh, list, u) => {
    S.add(mesh); const show = o.show !== undefined ? f(o.show) : null, op = o.opacity !== undefined ? f(o.opacity) : null, key = watch(list); let last = null;
    ups.push({ d: true, u: () => { if (show) { mesh.visible = show() > 0; if (!mesh.visible) return; } const k = key(); if (k !== last) { last = k; u(); } if (mesh.userData.off) mesh.visible = false; if (op && mesh.material) { mesh.material.opacity = clamp(op(), 0, 1); mesh.material.transparent = true; mesh.material.depthWrite = mesh.material.opacity > .9; } } });
    if (o.id) pickables[o.id] = mesh;
  };
  const mat = (o, extra = {}) => o.lith ? rockMaterial({ lith: TEXOF[o.lith], color: COL[o.lith], fluid: o.fluid && LEG[o.fluid] ? o.fluid : null, fluid2: o.fluid2 && LEG[o.fluid2] ? o.fluid2 : null, pore: o.pore || 1.1, scale: .1, extra: { ...clipOpt(o), ...extra } })
    : new THREE.MeshStandardMaterial({ color: COL[o.color] || '#9aa6b3', roughness: .6, side: THREE.DoubleSide, ...clipOpt(o), ...extra });

  const T = {
    solid(o) {
      const n = Math.min(96, o.res || 56), ft = f(o.top, ['x', 'z']), fb = f(o.bottom, ['x', 'z']), N = n + 1, vs = new Float32Array(N * N * 2 * 3 + 4 * N * 2 * 3), uv = new Float32Array(vs.length / 3 * 2), ix = [];
      const q = (a, b, c, d) => ix.push(a, b, c, c, b, d);
      for (let k = 0; k < 2; k++) for (let i = 0; i < n; i++) for (let j = 0; j < n; j++) { const a = k * N * N + i * N + j; k ? q(a, a + N, a + 1, a + N + 1) : q(a, a + 1, a + N, a + N + 1); }
      const off = 2 * N * N; for (let s = 0; s < 4; s++) for (let i = 0; i < n; i++) { const a = off + s * N * 2 + i * 2; q(a, a + 1, a + 2, a + 3); }
      const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.BufferAttribute(vs, 3)); g.setAttribute('uv', new THREE.BufferAttribute(uv, 2)); g.setIndex(ix);
      const set = (p, x, y, z, u, v) => { vs[p * 3] = sx(x); vs[p * 3 + 1] = sy(y); vs[p * 3 + 2] = sx(z); uv[p * 2] = u; uv[p * 2 + 1] = v; };
      const m = new THREE.Mesh(g, mat(o)); m.castShadow = m.receiveShadow = true;
      common(o, m, [o.top, o.bottom], () => {
        for (let i = 0; i < N; i++) for (let j = 0; j < N; j++) { const x = (i / n - .5) * X, z = (j / n - .5) * Z, t = ft(x, z), b = Math.min(t, fb(x, z)); set(i * N + j, x, t, z, sx(x), sx(z)); set(N * N + i * N + j, x, b, z, sx(x), sx(z)); }
        for (let s = 0; s < 4; s++) for (let i = 0; i < N; i++) { const k = (i / n - .5), x = s === 0 ? k * X : s === 1 ? -k * X : s === 2 ? X / 2 : -X / 2, z = s === 0 ? Z / 2 : s === 1 ? -Z / 2 : s === 2 ? -k * Z : k * Z, t = ft(x, z), b = Math.min(t, fb(x, z)), p = off + s * N * 2 + i * 2, w = sx(k * (s < 2 ? X : Z)); set(p, x, t, z, w, sv(t)); set(p + 1, x, b, z, w, sv(b)); }
        g.attributes.position.needsUpdate = g.attributes.uv.needsUpdate = true; g.computeVertexNormals(); g.computeBoundingSphere();
      });
    },
    surface(o) {
      const n = Math.min(160, o.res || 100), fy = f(o.y, ['x', 'z']), fv = o.value ? f(o.value, ['x', 'z']) : null, g = new THREE.PlaneGeometry(sx(X), sx(Z), n, n).rotateX(-Math.PI / 2), p = g.attributes.position, uv = g.attributes.uv, base = rgb(COL[o.color || 'reef']);
      for (let i = 0; i < p.count; i++) uv.setXY(i, p.getX(i), p.getZ(i)); let c = null; if (fv) { c = new THREE.BufferAttribute(new Float32Array(p.count * 3), 3); g.setAttribute('color', c); }
      const ex = { ...clipOpt(o) }; const m = new THREE.Mesh(g, fv ? new THREE.MeshStandardMaterial({ vertexColors: true, roughness: .7, side: THREE.DoubleSide, ...ex }) : mat(o));
      if (o.contour) { const mm = m.material, old = mm.onBeforeCompile; mm.onBeforeCompile = s => { old && old(s); s.uniforms.uC = { value: sv(o.contour) }; if (!s.vertexShader.includes('vWP')) s.vertexShader = s.vertexShader.replace('#include <common>', '#include <common>\nvarying vec3 vWP;').replace('#include <project_vertex>', '#include <project_vertex>\nvWP=(modelMatrix*vec4(transformed,1.)).xyz;'); const decl = s.fragmentShader.includes('varying vec3 vWP') ? '' : 'varying vec3 vWP;'; s.fragmentShader = s.fragmentShader.replace('#include <common>', `#include <common>\n${decl}uniform float uC;`).replace('#include <roughnessmap_fragment>', `float qq=vWP.y/uC; float ff=abs(fract(qq-.5)-.5)/max(fwidth(qq),1e-5); diffuseColor.rgb=mix(diffuseColor.rgb,vec3(.95),.55*(1.-smoothstep(.5,1.5,ff)));\n#include <roughnessmap_fragment>`); }; mm.customProgramCacheKey = () => 'ct' + (o.lith || '') + !!fv; }
      m.castShadow = m.receiveShadow = true;
      common(o, m, [o.y, o.value], () => { for (let i = 0; i < p.count; i++) { const x = p.getX(i) * U, z = p.getZ(i) * U; p.setY(i, sy(fy(x, z))); if (c) c.setXYZ(i, ...ramp((fv(x, z) - o.min) / (o.max - o.min), base)); } p.needsUpdate = true; if (c) c.needsUpdate = true; g.computeVertexNormals(); g.computeBoundingSphere(); });
    },
    section(o) {
      const W = o.axis === 'z' ? X : Z, flat = !o.value, cw = flat ? 480 : 200, ch = Math.round(clamp(cw * (y1 - y0) * ve / W, 60, flat ? 384 : 160)), cv = document.createElement('canvas'); cv.width = cw; cv.height = ch; const cx = cv.getContext('2d'), tx = new THREE.CanvasTexture(cv); tx.colorSpace = THREE.SRGBColorSpace;
      const m = new THREE.Mesh(new THREE.PlaneGeometry(sx(W), H), new THREE.MeshBasicMaterial({ map: tx, transparent: true, side: THREE.DoubleSide, alphaTest: .3, toneMapped: false })); if (o.axis === 'x') m.rotation.y = Math.PI / 2;
      const at = f(o.at), fv = o.value ? f(o.value, ['x', 'y', 'z']) : null, cl = (o.classes || []).map(c => [f(c.when, ['x', 'y', 'z']), new THREE.Color(COL[c.color]), c, c.share !== undefined ? f(c.share, ['x', 'y', 'z']) : null]), ms = o.mask ? f(o.mask, ['x', 'y', 'z']) : null, base = rgb(COL[o.color || 'reef']), tc = new THREE.Color();
      common(o, m, [o.at, o.value, o.mask, ...(o.classes || []).map(c => c.when)], () => {
        const a = at(), im = cx.createImageData(cw, ch), id = flat ? new Array(cw * ch) : null, sh = flat && cl.some(q => q[3]) ? new Float32Array(cw * ch).fill(.5) : null; m.position.set(o.axis === 'x' ? sx(a) + .03 : 0, 0, o.axis === 'z' ? sx(a) + .03 : 0);
        for (let j = 0; j < ch; j++) for (let i = 0; i < cw; i++) {
          const h = ((i + .5) / cw - .5) * W, y = y1 - (j + .5) / ch * (y1 - y0), x = o.axis === 'z' ? h : a, z = o.axis === 'z' ? a : -h, k = (j * cw + i) * 4; let c = null;
          if (ms && !(ms(x, y, z) > 0)) continue;
          for (const q of cl) if (q[0](x, y, z) > 0) { c = q[1]; if (id) id[j * cw + i] = q[2]; if (sh && q[3]) sh[j * cw + i] = q[3](x, y, z); break; }
          if (!c && fv) { const v = fv(x, y, z); if (Number.isFinite(v)) c = tc.setRGB(...ramp((v - o.min) / (o.max - o.min), base)); }
          if (!c) continue; const s = c.clone().convertLinearToSRGB(); im.data[k] = s.r * 255; im.data[k + 1] = s.g * 255; im.data[k + 2] = s.b * 255; im.data[k + 3] = 255;
        }
        if (flat) grain(im.data, cw, ch, id, sh);
        cx.putImageData(im, 0, 0); tx.needsUpdate = true;
      });
    },
    water(o) { const lv = f(o.level), m = new THREE.Mesh(new THREE.BoxGeometry(sx(X) * .999, 1, sx(Z) * .999), new THREE.MeshPhysicalMaterial({ color: '#1f7396', transparent: true, opacity: .42, roughness: .1, depthWrite: false, ...clipOpt(o) })); const b = f(o.bottom === undefined ? String(y0) : o.bottom); common({ ...o, opacity: undefined }, m, [o.level, o.bottom], () => { const a = sy(lv()), c = sy(b()); m.scale.y = Math.max(.05, a - c); m.position.y = (a + c) / 2; m.userData.off = !(a > c); m.visible = a > c; }); },
    tube(o) { const ps = o.path.map(p => f3(p)), r = f(o.radius), m = new THREE.Mesh(new THREE.BufferGeometry(), o.color && o.color !== 'steel' ? new THREE.MeshStandardMaterial({ color: COL[o.color], roughness: .5 }) : steel('#aab2b9', .35)); m.castShadow = true; common(o, m, [...o.path.flat(), o.radius], () => { const v = ps.map(p => new THREE.Vector3(sx(p[0]()), sy(p[1]()), sx(p[2]()))); m.geometry.dispose(); m.geometry = new THREE.TubeGeometry(v.length > 2 && o.smooth ? new THREE.CatmullRomCurve3(v) : (() => { const c = new THREE.CurvePath(); for (let i = 1; i < v.length; i++) c.add(new THREE.LineCurve3(v[i - 1], v[i])); return c; })(), Math.max(8, v.length * 10), Math.max(.12, sx(r())), 12); }); },
    prefab(o) { const at = f3(o.at), g = o.name === 'derrick' ? derrick(26, 6.5) : o.name === 'truck' ? loggingTruck() : loggingTool(6.5, .36); const base = { derrick: 13 / 26, truck: 7 / 9.6, tool: 7 / 6.5 }[o.name] * (o.scale || 1); g.scale.setScalar(base); g.rotation.y = (o.rot || 0) * Math.PI / 180; common(o, g, o.at, () => g.position.set(sx(at[0]()), sy(at[1]()), sx(at[2]()))); },
    shape(o) {
      const at = f3(o.at), sz = f3(o.size), G = { sphere: () => new THREE.SphereGeometry(.5, 40, 24), box: () => new THREE.BoxGeometry(1, 1, 1), cylinder: () => new THREE.CylinderGeometry(.5, .5, 1, 48), ring: () => new THREE.TorusGeometry(.5, .012, 10, 120).rotateX(Math.PI / 2), plane: () => new THREE.PlaneGeometry(1, 1).rotateX(-Math.PI / 2) }[o.shape]();
      const m = new THREE.Mesh(G, o.lith ? mat(o) : new THREE.MeshStandardMaterial({ color: COL[o.color], roughness: .45, side: THREE.DoubleSide, emissive: o.glow ? COL[o.color] : '#000', emissiveIntensity: o.glow ? .7 : 0, ...(o.clip ? clipOpt(o) : {}) })); m.castShadow = true;
      common(o, m, [...o.at, ...o.size], () => { m.position.set(sx(at[0]()), sy(at[1]()), sx(at[2]())); m.scale.set(Math.max(1e-3, sx(sz[0]())), o.shape === 'sphere' && o.round ? Math.max(1e-3, sx(sz[1]())) : Math.max(1e-3, sv(sz[1]())), Math.max(1e-3, sx(sz[2]()))); });
    },
    scatter(o) {
      const A = ['i', 'r1', 'r2', 'r3'], at = f3(o.at, A), sz = f3(o.size, A), r = rng(seed + 17), R = Array.from({ length: o.n }, () => [r(), r(), r()]), g = o.shape === 'box' ? new THREE.BoxGeometry(1, 1, 1) : new THREE.IcosahedronGeometry(.5, 2);
      const m = new THREE.InstancedMesh(g, o.lith ? mat(o) : new THREE.MeshStandardMaterial({ color: COL[o.color], roughness: .7 }), o.n), d = new THREE.Object3D(); m.castShadow = m.receiveShadow = true; m.frustumCulled = false;
      common(o, m, [...o.at, ...o.size], () => { for (let i = 0; i < o.n; i++) { const a = [i, ...R[i]]; d.position.set(sx(at[0](...a)), sy(at[1](...a)), sx(at[2](...a))); const k = sz.map(q => Math.max(0, sx(q(...a)))); d.scale.set(k[0], o.round === false ? k[1] * ve : k[1], k[2]); d.rotation.set(0, R[i][0] * 6.28, 0); d.updateMatrix(); m.setMatrixAt(i, d.matrix); } m.instanceMatrix.needsUpdate = true; });
    },
    particles(o) {
      const n = Math.min(o.n || 400, stage.low ? 400 : 1500), v = f3(o.velocity, ['x', 'y', 'z']), r = rng(seed + 5), [a, b] = o.box, P = Array.from({ length: n }, () => [0, 1, 2].map(k => a[k] + (b[k] - a[k]) * r())), arr = new Float32Array(n * 3), g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.BufferAttribute(arr, 3));
      const c = document.createElement('canvas'); c.width = c.height = 32; const q = c.getContext('2d'); q.fillStyle = '#fff'; q.beginPath(); q.arc(16, 16, 14, 0, 7); q.fill();
      const m = new THREE.Points(g, new THREE.PointsMaterial({ color: COL[o.color], size: o.size || .9, map: new THREE.CanvasTexture(c), alphaTest: .5, ...(clipOpt(o)) })); m.frustumCulled = false; const on = o.where ? f(o.where, ['x', 'y', 'z']) : null; common(o, m, [], () => {});
      frames.push(dt => { if (!m.visible) return; const k = dt * (o.speed || 1); for (let i = 0; i < n; i++) { const p = P[i]; if (!stage.reduced) for (let d = 0; d < 3; d++) { const s = v[d](...p) * k; if (Number.isFinite(s)) p[d] += clamp(s, -(b[d] - a[d]) * .1, (b[d] - a[d]) * .1); } if (p.some((q, d) => q < Math.min(a[d], b[d]) || q > Math.max(a[d], b[d])) || (on && !(on(...p) > 0)) || Math.random() < dt * .08) for (let d = 0; d < 3; d++) p[d] = a[d] + (b[d] - a[d]) * Math.random(); const hid = on && !(on(...p) > 0); arr[i * 3] = sx(p[0]); arr[i * 3 + 1] = hid ? -1e4 : sy(p[1]); arr[i * 3 + 2] = sx(p[2]); } g.attributes.position.needsUpdate = true; });
    },
    arrows(o) {
      const n = o.grid || [8, 1, 8], v = f3(o.vector, ['x', 'y', 'z']), [a, b] = o.box, tot = n[0] * n[1] * n[2], cone = new THREE.ConeGeometry(.5, 1.2, 10).translate(0, 1.2, 0), shaft = new THREE.CylinderGeometry(.16, .16, 1, 8).translate(0, .4, 0), mm = new THREE.MeshStandardMaterial({ color: COL[o.color], roughness: .4 }), m1 = new THREE.InstancedMesh(cone, mm, tot), m2 = new THREE.InstancedMesh(shaft, mm, tot), G = new THREE.Group(); G.add(m1, m2); m1.frustumCulled = m2.frustumCulled = false; const d = new THREE.Object3D(), up = new THREE.Vector3(0, 1, 0);
      common(o, G, o.vector, () => { let k = 0, mx = 1e-30; const L = []; for (let i = 0; i < n[0]; i++) for (let j = 0; j < n[1]; j++) for (let l = 0; l < n[2]; l++) { const p = [i, j, l].map((q, c) => a[c] + (b[c] - a[c]) * (n[c] > 1 ? q / (n[c] - 1) : .5)), w = v.map(q => q(...p)), len = Math.hypot(...w); mx = Math.max(mx, len || 0); L.push([p, w, len]); }
        for (const [p, w, len] of L) { const s = (o.scale || 3) * Math.sqrt((len || 0) / mx); d.position.set(sx(p[0]), sy(p[1]), sx(p[2])); const dir = new THREE.Vector3(...w); dir.lengthSq() > 0 && d.quaternion.setFromUnitVectors(up, dir.normalize()); d.scale.setScalar(len > 0 ? Math.max(.001, s) : .001); d.updateMatrix(); m1.setMatrixAt(k, d.matrix); m2.setMatrixAt(k++, d.matrix); } m1.instanceMatrix.needsUpdate = m2.instanceMatrix.needsUpdate = true; });
    },
    label(o) { const at = f3(o.at), l = stage.label('', [0, 0, 0], o.hot ? 'hot' : 'soft'); labels.push([l, o.hot ? 0 : 1]); common(o, l, [...o.at], () => { l.position.set(sx(at[0]()), sy(at[1]()), sx(at[2]())); }); ups.push({ d: true, u: () => { const t = M.text(o.text); if (l.element.textContent !== t) l.element.textContent = t; } }); },
    column(o) { // столбик керна/скважины: в точке или в местах, выбранных учеником
      const fv = f(o.value, ['x', 'y', 'z']), ft = f(o.top, ['x', 'z']), fb = f(o.bottom, ['x', 'z']), gd = o.good ? f(o.good, ['x', 'y', 'z', 'v']) : null, base = rgb(COL[o.color || 'reef']);
      const make = (x, z) => { const G = new THREE.Group(), t = ft(x, z), b = fb(x, z), n = 40, h = (t - b) / n; for (let i = 0; i < n && h > 0; i++) { const y = b + (i + .5) * h, v = fv(x, y, z); const mm = new THREE.MeshStandardMaterial({ roughness: .8 }); mm.color.setRGB(...ramp((v - o.min) / (o.max - o.min), base)); const m = new THREE.Mesh(new THREE.CylinderGeometry(.8, .8, sv(h) * 1.02, 20), mm); m.position.y = sy(y); G.add(m); if (gd && gd(x, y, z, v) > 0) { const r = new THREE.Mesh(new THREE.TorusGeometry(.95, .13, 6, 20).rotateX(Math.PI / 2), new THREE.MeshStandardMaterial({ color: COL[o.good_color || 'oil'], emissive: COL[o.good_color || 'oil'], emissiveIntensity: .4 })); r.position.y = sy(y); G.add(r); } } G.position.set(sx(x), 0, sx(z)); S.add(shadow(G)); return G; };
      if (o.at === 'picks') (st.onPick = st.onPick || []).push((x, z) => make(x, z)); else { const a = f3([...o.at, '0']); const g = make(a[0](), a[1]()); if (o.show !== undefined) { const s = f(o.show); ups.push({ d: true, u: () => (g.visible = s() > 0) }); } }
    },
  };
  const st = { i: 0, done: false, play: false, picks: [], preds: [], wells: [] };
  // основание сцены
  const pl = new THREE.Mesh(new THREE.BoxGeometry(sx(X) + 3, 1.6, sx(Z) + 3), paint('#39434d', .9)); pl.position.y = -H / 2 - .9; pl.receiveShadow = true; S.add(pl);
  spec.objects.forEach(o => T[o.type](o));
  const apply = all => { M.update(); for (const u of ups) if (all || u.d) u.u(); };
  apply(true);
  { const fill = new THREE.DirectionalLight('#dbe6f0', 1.5); fill.position.set(-80, 45, -50); S.add(fill); } // подсветка теневых сторон
  stage.setSun(new THREE.Vector3(60, 95, 70), 85); S.fog = new THREE.Fog('#9fb2c2', 260, 700);
  stage.controls.minDistance = 25; stage.controls.maxDistance = 330;
  const look = (c = {}, dur = 1.6) => { const k = stage.low ? 1.55 : 1, R = (c.zoom ? 1 / c.zoom : 1) * 128 * k, a = (c.yaw ?? 30) * Math.PI / 180, b = (c.pitch ?? 24) * Math.PI / 180, t = c.target ? [sx(c.target[0]), sy(c.target[1]), sx(c.target[2])] : [0, 0, 0]; stage.view([t[0] + Math.sin(a) * Math.cos(b) * R, t[1] + Math.sin(b) * R, t[2] + Math.cos(a) * Math.cos(b) * R], t, dur); };
  look(spec.world.camera, 0);
  let tick = 0; frames.push(() => {
    if (labels.length < 2 || tick++ % 8) return; const kept = [];
    for (const [l] of [...labels].sort((a, b) => a[1] - b[1])) { const e = l.element, r = e.getBoundingClientRect(); if (!l.visible || !r.width) continue; const hit = kept.some(q => r.left < q.right - 4 && r.right > q.left + 4 && r.top < q.bottom - 3 && r.bottom > q.top + 3); e.style.visibility = hit ? 'hidden' : ''; if (!hit) kept.push(r); }
  });
  let dirty = true, redraw = [];
  const tm = spec.time, k2t = k => tm && tm.log ? Math.exp(Math.log(Math.max(M.t0, 1e-12)) + (Math.log(M.t1) - Math.log(Math.max(M.t0, 1e-12))) * k) : M.t0 + (M.t1 - M.t0) * k;
  let tk = 0, tsl = null; const setK = k => { tk = clamp(k, 0, 1); M.E.t = k2t(tk); dirty = true; tsl && tsl.set(tk); };
  stage.cbs.push(dt => {
    if (st.play && tm) { setK(tk + dt / (stage.reduced ? 1 : tm.duration || 9)); tsl && tsl.set(tk); if (tk >= 1) { st.play = false; redraw.forEach(r => r.btn && r.btn()); } }
    if (dirty) { dirty = false; apply(false); redraw.forEach(r => r.draw && r.draw()); redraw.forEach(r => r.gate && r.gate()); }
    frames.forEach(q => q(dt));
  });
  // ---------- панель
  section(panel, spec.title, `<p>${spec.intro || spec.goal}</p>`);
  const names = { predict: 'Ответьте на вопрос справа', explore: 'Исследуйте', guess: 'Поставьте прогноз', pick: 'Выберите места на сцене', choose: 'Примите решение', reveal: 'Посмотрите, что вышло' };
  const hints = spec.steps.map(s => s.hint || names[s.kind]);
  const body = $('<div></div>'); panel.appendChild(body);
  const used = new Set();
  function tools(sec, s) {
    const row = $('<div></div>');
    for (const u of s.use || []) { const [a, b] = u.split(':'); if (a !== 'read' && used.has(u)) continue; used.add(u);
      if (a === 'time') { const w = $('<div></div>'); tsl = slider(tm.label || 'Время', 0, 1, .002, tk, v => { st.play = false; setK(v); }, v => { const q = k2t(v) / M.tu.k; return fmt(q, Math.abs(q) < 10 ? 1 : 0) + ' ' + unitRu(tm.unit); }); const p = $('<button class="main alt">Запустить</button>'); p.onclick = () => { if (tk >= .999) setK(0); st.play = true; }; const cap = $('<p class="q"></p>'); w.append(tsl, p, cap); redraw.push({ draw: () => { const g = (tm.stages || []).find(x => tk <= x.until + 1e-9); cap.textContent = g ? M.text(g.text) : ''; cap.hidden = !g; } }); row.appendChild(w); }
      if (a === 'param') { const p = spec.params[b], k = M.U[b].k; row.appendChild(slider(p.control[3], p.control[0], p.control[1], p.control[2], clamp(M.P[b] / k, p.control[0], p.control[1]), v => { M.setParam(b, v * k); dirty = true; }, v => fmt(p.unit === 'm' && p.control[1] <= 0 ? -v : v, p.control[2] < .1 ? 2 : p.control[2] < 1 ? 1 : 0) + ' ' + unitRu(p.unit))); }
      if (a === 'chart') row.appendChild(chart(spec.charts.find(c => c.id === b)));
      if (a === 'read') { let kv = row.lastElementChild; if (!kv || !kv.classList.contains('kv')) { kv = $('<div class="kv"></div>'); row.appendChild(kv); } const v = spec.vars[b], e = $(`<div><span>${v.label || b}</span><b></b></div>`); kv.appendChild(e); redraw.push({ draw: () => { const q = M.V[b] / unit(v.unit).k; e.querySelector('b').textContent = (Number.isFinite(q) ? fmt(q, v.digits ?? (Math.abs(q) < 10 ? 2 : 0)) : '—') + ' ' + unitRu(v.unit); } }); } }
    sec.appendChild(row); dirty = true;
  }
  function chart(c) {
    const box = $(`<div><h3>${c.title}</h3></div>`), cv = canvas(c.height || 170); box.appendChild(cv); const kx = unit(c.x.unit).k, own = !Object.hasOwn(M.P, c.x.var) && c.x.var !== 't', fs = c.lines.map(l => M.fn(l.expr, own ? [c.x.var] : [])), ku = c.lines.map(l => unit(l.unit).k), dep = c.kind === 'depth', N = 80;
    const draw = () => {
      const [g, w, h] = cv.fit(); g.fillStyle = LEG.bg; g.fillRect(0, 0, w, h); const xs = Array.from({ length: N + 1 }, (_, i) => c.x.min + (c.x.max - c.x.min) * i / N);
      const ys = fs.map((fn, li) => xs.map(x => { const v = own ? fn(x * kx) : M.at({ [c.x.var]: x * kx }, fn); return v / ku[li]; })); const all = ys.flat().filter(Number.isFinite); let lo = c.y && c.y.min !== undefined ? c.y.min : Math.min(...all), hi = c.y && c.y.max !== undefined ? c.y.max : Math.max(...all); if (!(hi > lo)) { hi = lo + 1; } const pad = c.y && c.y.max !== undefined ? 0 : (hi - lo) * .08; lo -= c.y && c.y.min !== undefined ? 0 : pad; hi += pad;
      const L = 54, B = 26, Tt = 10 + 16 * Math.ceil(c.lines.length / 2), pw = w - L - 12, ph = h - B - Tt, PX = (x, y) => dep ? [L + (y - lo) / (hi - lo) * pw, Tt + (c.x.var === 'y' ? (c.x.max - x) : (x - c.x.min)) / (c.x.max - c.x.min) * ph] : [L + (x - c.x.min) / (c.x.max - c.x.min) * pw, Tt + ph - (y - lo) / (hi - lo) * ph];
      g.strokeStyle = '#2b3540'; g.lineWidth = 1; g.strokeRect(L + .5, Tt + .5, pw, ph); g.font = '11px Segoe UI'; g.fillStyle = LEG.muted; const ff = v => fmt(v, Math.abs(hi - lo) < 2 ? 2 : Math.abs(v) < 10 ? 1 : 0), fx = v => fmt(v, Math.abs(c.x.max - c.x.min) < 10 ? 1 : 0);
      if (dep) { g.textAlign = 'right'; g.fillText(fx(c.x.var === 'y' ? c.x.max : c.x.min), L - 4, Tt + 10); g.fillText(fx(c.x.var === 'y' ? c.x.min : c.x.max), L - 4, Tt + ph); g.textAlign = 'left'; g.fillText(ff(lo), L, h - 10); g.textAlign = 'right'; g.fillText(ff(hi), L + pw, h - 10); g.textAlign = 'center'; g.fillText(`${(c.y && c.y.label) || ''} ${unitRu(c.lines[0].unit)}`, L + pw / 2, h - 10); }
      else { g.textAlign = 'right'; g.fillText(ff(hi), L - 4, Tt + 10); g.fillText(ff(lo), L - 4, Tt + ph); g.textAlign = 'left'; g.fillText(fx(c.x.min), L, h - 8); g.textAlign = 'right'; g.fillText(fx(c.x.max), L + pw, h - 8); g.textAlign = 'center'; g.fillText(`${c.x.label || ''}${c.x.unit ? ', ' + unitRu(c.x.unit) : ''}`, L + pw / 2, h - 8); }
      const cur = c.x.var === 't' ? M.E.t / kx : Object.hasOwn(M.P, c.x.var) ? M.P[c.x.var] / kx : c.cursor ? M.fn(c.cursor)() / kx : null;
      c.lines.forEach((l, li) => { g.beginPath(); let on = false; xs.forEach((x, i) => { if (c.reveal !== false && c.x.var === 't' && x > cur + 1e-9) return; const y = ys[li][i]; if (!Number.isFinite(y)) { on = false; return; } const [a, b] = PX(x, clamp(y, lo, hi)); on ? g.lineTo(a, b) : g.moveTo(a, b); on = true; }); g.strokeStyle = COL[l.color]; g.lineWidth = 2; g.setLineDash(l.dash ? [5, 4] : []); g.stroke(); g.setLineDash([]); g.fillStyle = COL[l.color]; g.textAlign = 'left'; g.fillText((l.dash ? '┄ ' : '━ ') + (l.label || '') + (li === 0 && !dep && l.unit ? ', ' + unitRu(l.unit) : ''), L + (li % 2) * pw / 2, 14 + 16 * Math.floor(li / 2)); if (cur !== null) { const y = own ? fs[li](cur * kx) / ku[li] : fs[li]() / ku[li]; if (Number.isFinite(y)) { const [a, b] = PX(clamp(cur, c.x.min, c.x.max), clamp(y, lo, hi)); g.beginPath(); g.arc(a, b, 4, 0, 7); g.fill(); } } });
    };
    redraw.push({ draw }); return box;
  }
  const el = stage.renderer.domElement;
  function next() { st.i++; run(); }
  function run() {
    if (st.i >= spec.steps.length) return finish();
    const s = spec.steps[st.i]; M.E.step = st.i; stage.hint(st.i, hints); if (s.camera) look(s.camera); if (s.reveal) M.E.revealed = 1; dirty = true; let sec;
    const cont = (t = 'Дальше') => { const b = $(`<button class="main next">${t}</button>`); b.onclick = () => { b.remove(); next(); }; sec.appendChild(b); return b; };
    if (s.kind === 'predict') { sec = prediction(body, s, i => { st.preds.push([s, i]); next(); }); }
    if (s.kind === 'explore') { sec = section(body, s.title || 'Опыт', `<p>${M.text(s.text)}</p>`); tools(sec, s); const b = cont(s.button || 'Дальше'); if (s.until !== undefined) { const u = f(s.until); b.disabled = true; const r = { gate: () => { if (u() > 0) { b.disabled = false; redraw = redraw.filter(q => q !== r); } } }; redraw.push(r); } }
    if (s.kind === 'guess') { sec = section(body, s.title || 'Ваш прогноз', `<p>${M.text(s.text)}</p>`); tools(sec, s); const ku = unit(s.unit).k, lg = s.log, from = k => lg ? Math.exp(Math.log(s.min) + (Math.log(s.max) - Math.log(s.min)) * k) : s.min + (s.max - s.min) * k; let k = .5; const sl = slider(s.label || 'Прогноз', 0, 1, .005, k, v => (k = v), v => { const q = from(v); return fmt(q, Math.abs(q) < 10 ? 1 : 0) + ' ' + unitRu(s.unit); }); sec.appendChild(sl); const b = $('<button class="main next">Зафиксировать</button>'); b.onclick = () => { b.remove(); sl.querySelector('input').disabled = true; M.E[s.id] = from(k) * ku; next(); }; sec.appendChild(b); }
    if (s.kind === 'choose') { sec = section(body, s.title || 'Решение', `<p class="q">${M.text(s.q)}</p>`); tools(sec, s); const ops = $('<div class="opts"></div>'); s.options.forEach((o, j) => { const b = $(`<button class="opt">${M.text(o.text)}</button>`); b.onclick = () => { if (ops.dataset.d) return; ops.dataset.d = 1; M.E[s.id] = j; ops.querySelectorAll('.opt').forEach(q => (q.disabled = true)); b.classList.add('sel'); st['ch_' + s.id] = [s, j, ops]; next(); }; ops.appendChild(b); }); sec.appendChild(ops); }
    if (s.kind === 'pick') {
      sec = section(body, s.title || 'Выберите места', `<p>${M.text(s.text)}</p><p class="q">Осталось: <b class="left">${s.n}</b></p>`); tools(sec, s); const sc = f(s.score, ['x', 'z']), ray = new THREE.Raycaster(); let dn = null; const md = s.min_dist || 0; st.pick = (x, z) => {
        if (st.picks.length >= s.n) return; if (st.picks.some(p => Math.hypot(p.x - x, p.z - z) < md)) { const e = $(`<p class="why">Слишком близко: не меньше ${fmt(md, 0)} м.</p>`); sec.appendChild(e); setTimeout(() => e.remove(), 3000); return; }
        const v = sc(x, z); st.picks.push({ x, z, v }); M.E.picks = st.picks.length; M.E.pick_score += v; const top = y1, rg = derrick(26, 6.5); rg.scale.setScalar(.32); rg.position.set(sx(x), sy(top), sx(z)); S.add(rg); const pp = new THREE.Mesh(new THREE.CylinderGeometry(.18, .18, H, 12), steel('#c3cad0', .3)); pp.position.set(sx(x), 0, sx(z)); S.add(pp); S.add(stage.label(String(st.picks.length), [sx(x), sy(top) + 10.5, sx(z)], 'num')); (st.onPick || []).forEach(q => q(x, z)); sec.querySelector('.left').textContent = s.n - st.picks.length; dirty = true;
        if (st.picks.length >= s.n) { el.onclick = null; const pts = []; for (let i = -20; i <= 20; i++) for (let j = -20; j <= 20; j++) { const x = i / 40 * X, z = j / 40 * Z; pts.push({ x, z, v: sc(x, z) }); } pts.sort((a, b) => b.v - a.v); const out = []; for (const p of pts) { if (out.length >= s.n) break; if (out.every(o => Math.hypot(o.x - p.x, o.z - p.z) >= md)) out.push(p); } M.E.best_score = out.reduce((q, p) => q + p.v, 0); st.best = out; const pc = Math.round(Math.min(1, M.E.pick_score / (M.E.best_score || 1)) * 100); sec.appendChild($(`<div class="score"><div><b>${pc} %</b><span>от лучшего плана теми же точками</span></div></div>`)); out.forEach(b => { const r = new THREE.Mesh(new THREE.TorusGeometry(2, .22, 8, 40).rotateX(Math.PI / 2), new THREE.MeshStandardMaterial({ color: LEG.text, emissive: LEG.text, emissiveIntensity: .6 })); r.position.set(sx(b.x), sy(y1) + .5, sx(b.z)); S.add(r); }); cont(); sec.lastElementChild.scrollIntoView({ block: 'end', behavior: 'smooth' }); } };
      el.onpointerdown = e => (dn = [e.clientX, e.clientY]); el.onclick = e => { if (!dn || Math.hypot(e.clientX - dn[0], e.clientY - dn[1]) > 6) return; const b = el.getBoundingClientRect(); ray.setFromCamera(new THREE.Vector2((e.clientX - b.left) / b.width * 2 - 1, 1 - (e.clientY - b.top) / b.height * 2), stage.camera); const h = ray.intersectObject(pickables[s.target])[0]; h && st.pick(h.point.x * U, h.point.z * U); };
    }
    if (s.kind === 'reveal') {
      M.E.revealed = 1; apply(true); sec = section(body, s.title || 'Что вышло', ''); const gs = spec.steps.filter(q => q.kind === 'guess' && Number.isFinite(M.E[q.id]));
      gs.forEach(q => { const ku = unit(q.unit).k, a = M.fn(q.truth)() / ku, v = M.E[q.id] / ku, d = x => fmt(x, Math.abs(x) < 10 ? 1 : 0) + ' ' + unitRu(q.unit); sec.appendChild($(`<div class="score"><div><b>${d(a)}</b><span>по расчёту</span></div><div><b>${d(v)}</b><span>ваш прогноз</span></div></div>`)); });
      for (const k in st) if (k.startsWith('ch_')) { const [q, j, ops] = st[k]; q.options.forEach((o, n) => { const ok = M.fn(String(o.correct))() > 0; if (ok) ops.children[n].classList.add('ok'); else if (n === j) ops.children[n].classList.add('no'); }); const o = q.options[j], ok = M.fn(String(o.correct))() > 0; sec.appendChild($(`<p class="why"><b>${ok ? 'Верно.' : 'Не так.'}</b> ${M.text(o.why)}</p>`)); delete st[k]; }
      sec.appendChild($(`<p>${M.text(s.text)}</p>`)); tools(sec, s); cont(st.i === spec.steps.length - 1 ? 'К выводам' : 'Дальше');
    }
    sec && st.i > 0 && sec.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
  function finish() { if (st.done) return; st.done = true; st.preds.forEach(([s, i]) => verdict(body, s, i)); closing(body, spec); body.lastElementChild.previousElementSibling.scrollIntoView({ behavior: 'smooth' }); }
  const lg = new Map(); spec.objects.forEach(o => { if (o.name_ru && (o.color || o.lith)) lg.set(o.name_ru, COL[o.color || o.lith]); (o.classes || []).forEach(c => c.name && lg.set(c.name, c.mix ? `linear-gradient(90deg,${COL[c.color]} 50%,${COL[c.mix]} 50%)` : COL[c.color])); });
  if (lg.size) panel.appendChild($(`<p class="leg">${[...lg].map(([n, c]) => `<span><i style="background:${c}"></i>${n}</span>`).join('')}</p>`));
  honesty(panel, { ...spec, sources: spec.claims.map(c => ({ claim: c.text, page: c.page })) });
  run();
  return { st, M, setK, look, next, get step() { return st.i; }, refresh: () => { dirty = true; },
    info: () => ({ step: st.i, steps: spec.steps.length, kind: (spec.steps[st.i] || {}).kind, done: st.done, t: M.E.t / M.tu.k, vars: { ...M.V } }) };
}
