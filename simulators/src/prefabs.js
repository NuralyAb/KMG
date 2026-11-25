// 3D-заготовки: собираются кодом, переиспользуются всеми шаблонами.
import { THREE, steel, paint, tex, rockMaterial, LEG } from './core.js';
import { mergeGeometries } from 'three/examples/jsm/utils/BufferGeometryUtils.js';
import { RoundedBoxGeometry } from 'three/examples/jsm/geometries/RoundedBoxGeometry.js';
import { fbm } from './models/util.js';

function bar(a, b, r) {
  const A = new THREE.Vector3(...a), B = new THREE.Vector3(...b), d = B.clone().sub(A);
  const g = new THREE.CylinderGeometry(r, r, d.length(), 6);
  g.applyQuaternion(new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 1, 0), d.normalize()));
  g.translate((A.x + B.x) / 2, (A.y + B.y) / 2, (A.z + B.z) / 2);
  return g;
}
const shadow = o => { o.traverse(m => { if (m.isMesh) { m.castShadow = m.receiveShadow = true; } }); return o; };

// Буровая вышка: четыре ноги, пояса и раскосы, рабочая площадка, кронблок.
export function derrick(h = 26, w = 6, color = '#c9cdd1') {
  const G = new THREE.Group(), parts = [], n = 8, half = y => w / 2 * (1 - 0.72 * y / h);
  const corner = (i, y) => { const s = half(y); return [[-s, y, -s], [s, y, -s], [s, y, s], [-s, y, s]][i]; };
  const y0 = h * 0.16;
  for (let k = 0; k < n; k++) {
    const a = y0 + (h - y0) * k / n, b = y0 + (h - y0) * (k + 1) / n;
    for (let i = 0; i < 4; i++) {
      const j = (i + 1) % 4;
      parts.push(bar(corner(i, a), corner(i, b), h * 0.0065), bar(corner(i, b), corner(j, b), h * 0.0038));
      parts.push(k % 2 ? bar(corner(i, a), corner(j, b), h * 0.003) : bar(corner(j, a), corner(i, b), h * 0.003));
    }
  }
  G.add(new THREE.Mesh(mergeGeometries(parts), paint(color, 0.45)));
  const sub = [];
  for (const [x, z] of [[-1, -1], [1, -1], [1, 1], [-1, 1]]) sub.push(bar([x * w * .55, 0, z * w * .55], [x * w * .5, y0, z * w * .5], h * 0.01));
  for (const z of [-1, 1]) sub.push(bar([-w * .55, 0, z * w * .55], [w * .5, y0, z * w * .5], h * 0.006), bar([w * .55, 0, z * w * .55], [-w * .5, y0, z * w * .5], h * 0.006));
  G.add(new THREE.Mesh(mergeGeometries(sub), paint('#8d2f25', 0.5)));
  const fl = new THREE.Mesh(new RoundedBoxGeometry(w * 1.35, h * 0.018, w * 1.35, 2, 0.05), steel('#6f767c', 0.6)); fl.position.y = y0; G.add(fl);
  const rail = []; const s = w * .66;
  for (const yy of [0.035, 0.06]) for (const [a, b] of [[[-s, -s], [s, -s]], [[s, -s], [s, s]], [[s, s], [-s, s]], [[-s, s], [-s, -s]]]) rail.push(bar([a[0], y0 + h * yy, a[1]], [b[0], y0 + h * yy, b[1]], h * 0.002));
  G.add(new THREE.Mesh(mergeGeometries(rail), paint('#d8b23a')));
  const crown = new THREE.Mesh(new RoundedBoxGeometry(w * .42, h * .03, w * .42, 2, .05), paint('#8d2f25')); crown.position.y = h; G.add(crown);
  const sheave = new THREE.Mesh(new THREE.TorusGeometry(h * .022, h * .006, 8, 24), steel()); sheave.position.y = h * .965; G.add(sheave);
  G.userData.top = h * .955;
  return shadow(G);
}
// Каротажная станция с лебёдкой.
export function loggingTruck() {
  const G = new THREE.Group(), body = paint('#dfe3e6', .4), dark = paint('#20262c', .6);
  const add = (g, m, p) => { const o = new THREE.Mesh(g, m); o.position.set(...p); G.add(o); return o; };
  add(new RoundedBoxGeometry(9.6, .45, 2.3, 2, .1), dark, [0, 1.05, 0]);
  add(new RoundedBoxGeometry(5.0, 2.5, 2.5, 3, .18), body, [1.0, 2.55, 0]);
  add(new RoundedBoxGeometry(2.1, 2.1, 2.4, 4, .3), paint('#2f5d8c', .3), [4.6, 2.2, 0]);
  add(new RoundedBoxGeometry(.1, .85, 2.0, 2, .04), new THREE.MeshStandardMaterial({ color: '#16222d', roughness: .08, metalness: .4 }), [5.63, 2.65, 0]);
  add(new THREE.BoxGeometry(5.02, .28, 2.52), paint('#2f5d8c'), [1.0, 2.2, 0]);
  for (const x of [-3.4, -2.2, 4.3]) for (const z of [-1.1, 1.1]) {
    const w = add(new THREE.CylinderGeometry(.62, .62, .45, 24), dark, [x, .62, z]); w.rotation.x = Math.PI / 2;
    const r = add(new THREE.CylinderGeometry(.3, .3, .48, 16), steel(), [x, .62, z]); r.rotation.x = Math.PI / 2;
  }
  const drum = add(new THREE.CylinderGeometry(.85, .85, 1.6, 32), steel('#4a4f55', .5), [-3.1, 2.25, 0]); drum.rotation.x = Math.PI / 2;
  for (const z of [-.85, .85]) { const f = add(new THREE.CylinderGeometry(1.15, 1.15, .1, 32), paint('#8d2f25'), [-3.1, 2.25, z]); f.rotation.x = Math.PI / 2; }
  G.userData.drum = drum;
  return shadow(G);
}
// Скважинный прибор: секции, прижимной башмак, светящаяся зона измерения.
export function loggingTool(len = 7, r = .34) {
  const G = new THREE.Group(); const st = steel('#b9c0c6', .22), dk = steel('#3a4046', .4);
  const seg = (y, h, rr, m) => { const o = new THREE.Mesh(new THREE.CylinderGeometry(rr, rr, h, 32), m); o.position.y = y; G.add(o); };
  seg(len * .84, len * .30, r * .9, st); seg(len * .66, len * .07, r * .98, dk);
  seg(len * .50, len * .25, r, st); seg(len * .35, len * .05, r * 1.02, dk); seg(len * .18, len * .30, r * .95, st);
  for (let i = 0; i < 4; i++) seg(len * (.44 + i * .035), len * .009, r * 1.03, dk);
  const head = new THREE.Mesh(new THREE.ConeGeometry(r * .8, len * .1, 32), dk); head.position.y = len * 1.03; G.add(head);
  const nose = new THREE.Mesh(new THREE.SphereGeometry(r * .95, 24, 12, 0, 7, Math.PI / 2, Math.PI / 2), dk); nose.position.y = len * .03; G.add(nose);
  for (const s of [-1, 1]) {
    const arm = new THREE.Mesh(new RoundedBoxGeometry(.08, len * .2, .12, 2, .03), dk); arm.position.set(s * r * 1.5, len * .24, 0); G.add(arm);
    const pad = new THREE.Mesh(new RoundedBoxGeometry(.1, len * .09, .26, 2, .04), steel('#d8b23a', .4)); pad.position.set(s * r * 1.75, len * .24, 0); G.add(pad);
  }
  const ring = new THREE.Mesh(new THREE.TorusGeometry(r * 1.12, .06, 10, 40), new THREE.MeshStandardMaterial({ color: LEG.measure, emissive: LEG.measure, emissiveIntensity: 2.2 }));
  ring.rotation.x = Math.PI / 2; ring.position.y = 0; G.add(ring);
  const halo = new THREE.Mesh(new THREE.SphereGeometry(2.6, 32, 20), new THREE.ShaderMaterial({
    transparent: true, depthWrite: false, side: THREE.DoubleSide, blending: THREE.AdditiveBlending, uniforms: { c: { value: new THREE.Color(LEG.measure) }, t: { value: 0 } },
    vertexShader: 'varying vec3 n,v;void main(){n=normalize(normalMatrix*normal);vec4 p=modelViewMatrix*vec4(position,1.);v=normalize(-p.xyz);gl_Position=projectionMatrix*p;}',
    fragmentShader: 'varying vec3 n,v;uniform vec3 c;uniform float t;void main(){float f=pow(clamp(1.-abs(dot(normalize(n),normalize(v))),0.001,1.),2.2);gl_FragColor=vec4(c,f*(.16+.07*sin(t*5.)));}' }));
  G.add(halo); G.userData.halo = halo;
  return shadow(G);
}
export function derrickSmall(scale) { const d = derrick(26, 6); d.scale.setScalar(scale); return d; }

// Блок недр с вырезанной четвертью и стволом по оси. Границы слоёв — функция top(x,z).
export function cutaway({ half = 16, bore = .8, layers, yOf, undul }) {
  const G = new THREE.Group(), pts = [], N = 22;
  const line = (x0, z0, x1, z1, n) => { for (let i = 0; i < n; i++) pts.push([x0 + (x1 - x0) * i / n, z0 + (z1 - z0) * i / n]); };
  line(half, 0, half, -half, N); line(half, -half, -half, -half, N * 2); line(-half, -half, -half, half, N * 2); line(-half, half, 0, half, N);
  line(0, half, 0, bore, N * 2);
  for (let i = 0; i < 28; i++) { const a = Math.PI / 2 + (Math.PI * 1.5) * i / 28; pts.push([Math.cos(a) * bore, Math.sin(a) * bore]); }
  line(bore, 0, half, 0, N * 2); pts.push([half, 0]);
  const per = [0]; for (let i = 1; i < pts.length; i++) per.push(per[i - 1] + Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]));
  const Y = (z, x, w, edge) => yOf(z) + (edge ? 0 : undul(x, w, z) * Math.min(1, Math.hypot(x, w) / 7));
  layers.forEach((l, li) => {
    const R = Math.max(1, Math.round((l.bot - l.top) / 1.2)), v = [], uv = [], ix = [];
    for (let i = 0; i < pts.length; i++) for (let j = 0; j <= R; j++) {
      const zt = Y(l.top, pts[i][0], pts[i][1], li === 0), zb = Y(l.bot, pts[i][0], pts[i][1], li === layers.length - 1);
      const y = zt + (zb - zt) * j / R;
      // Глина чуть утоплена, плотная порода выступает — как на реальном срезе.
      const q = fbm(pts[i][0] * .8, y * 1.2, pts[i][1] * .8, 5, 3) * .16 * Math.min(1, Math.hypot(...pts[i]) / 3), rr = l.relief || 0;
      const nx = Math.abs(pts[i][1]) < 1e-6 && pts[i][0] > bore ? [0, 1] : Math.abs(pts[i][0]) < 1e-6 && pts[i][1] > bore ? [1, 0] : [0, 0];
      v.push(pts[i][0] + nx[0] * (q + rr), y, pts[i][1] + nx[1] * (q + rr)); uv.push(per[i], y);
    }
    for (let i = 0; i < pts.length - 1; i++) for (let j = 0; j < R; j++) { const a = i * (R + 1) + j, b = a + R + 1; ix.push(a, a + 1, b, b, a + 1, b + 1); }
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.Float32BufferAttribute(v, 3)); g.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2)); g.setIndex(ix); g.computeVertexNormals();
    const m = new THREE.Mesh(g, l.material); m.castShadow = m.receiveShadow = true; m.userData.layer = l; l.mesh = m; G.add(m);
  });
  return G;
}
export function capShape(half, bore) {
  const s = new THREE.Shape(); s.moveTo(half, 0); s.lineTo(half, half); s.lineTo(-half, half); s.lineTo(-half, -half); s.lineTo(0, -half); s.lineTo(0, -bore);
  s.absarc(0, 0, bore, -Math.PI / 2, 0, true); s.lineTo(half, 0); return s;
}
export function grassMat(rep = .05) {
  const t = tex('grass'); for (const k of ['map', 'normalMap']) t[k].repeat.set(rep, rep);
  return new THREE.MeshStandardMaterial({ ...t, roughness: .95 });
}
export { bar, shadow, rockMaterial };
