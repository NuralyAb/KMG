import { THREE, rockMaterial, LEG, steel } from '../core.js';
import { derrick, shadow } from '../prefabs.js';
import * as M from '../models/reef.js';
import { clamp, fbm } from '../models/util.js';
import { $, fmt, section, prediction, verdict, closing, honesty, canvas, slider } from '../ui.js';

const ramp = (phi, max) => { const k = clamp(phi / max, 0, 1), a = [38, 44, 52], b = [240, 163, 94], c = [255, 240, 205]; const m = (x, y, t) => x + (y - x) * t; return k < .6 ? a.map((v, i) => m(v, b[i], k / .6)) : b.map((v, i) => m(v, c[i], (k - .6) / .4)); };
const css = a => `rgb(${a.map(Math.round).join(',')})`;

// Рябь: тайлящаяся карта нормалей из суммы волн со случайными направлениями.
function waves() {
  const n = 256, c = document.createElement('canvas'); c.width = c.height = n; const g = c.getContext('2d'), im = g.createImageData(n, n), w = [];
  let s = 7; const r = () => (s = (s * 16807) % 2147483647) / 2147483647;
  for (let i = 0; i < 34; i++) { const k = 2 + Math.floor(r() * 13), a = r() * 6.28; w.push([Math.round(Math.cos(a) * k), Math.round(Math.sin(a) * k), r() * 6.28, 1 / (1.5 + k * .55)]); }
  for (let y = 0; y < n; y++) for (let x = 0; x < n; x++) { let dx = 0, dy = 0; for (const [a, b, p, m] of w) { const q = Math.cos((a * x + b * y) / n * 6.2832 + p) * m; dx += a * q; dy += b * q; } const l = Math.hypot(dx * .06, dy * .06, 1), o = (y * n + x) * 4; im.data[o] = 128 + 127 * dx * .06 / l; im.data[o + 1] = 128 + 127 * dy * .06 / l; im.data[o + 2] = 128 + 127 / l; im.data[o + 3] = 255; }
  g.putImageData(im, 0, 0); const t = new THREE.CanvasTexture(c); t.wrapS = t.wrapT = THREE.RepeatWrapping; t.repeat.set(9, 9); return t;
}

export function build(stage, spec, seed, panel) {
  const cs = M.buildCase(spec, seed), S = stage.scene, P = spec.params, L = cs.L, U = L / 130, VE = P.ve;
  const X = v => v / U, Yv = y => y / U * VE, LW = X(L), maxPhi = Math.max(...Object.values(spec.zones).map(z => z.phi[1]));
  const clip = new THREE.Plane(new THREE.Vector3(0, 0, -1), 1e4);

  // --- тело рифа: сетка высот, растёт из той же функции height()
  const N = stage.low ? 130 : 200, g = new THREE.PlaneGeometry(LW, LW, N, N); g.rotateX(-Math.PI / 2);
  const pos = g.attributes.position, full = new Float32Array(pos.count), uv = g.attributes.uv;
  for (let i = 0; i < pos.count; i++) { full[i] = M.height(cs, pos.getX(i) * U, pos.getZ(i) * U); uv.setXY(i, pos.getX(i), pos.getZ(i)); }
  const rm = rockMaterial({ lith: 'reef', scale: .09, extra: { clippingPlanes: [clip] } });
  const old = rm.onBeforeCompile; rm.userData.iso = { value: 0 }; rm.userData.floor = { value: .35 };
  rm.onBeforeCompile = s => { old(s); s.uniforms.uIso = rm.userData.iso; s.uniforms.uBase = { value: new THREE.Color('#8f8468') };
    s.fragmentShader = s.fragmentShader.replace('uniform vec3 uCol', 'uniform float uIso;uniform vec3 uBase;uniform vec3 uCol').replace('diffuseColor.rgb=mix(hid,rk,uReveal);', `
      rk=mix(uBase*tx,rk,smoothstep(.15,1.2,vWP.y));
      float q=vWP.y/2.2; float f=abs(fract(q-.5)-.5)/max(fwidth(q),1e-5); float ln=(1.-smoothstep(.5,1.5,f))*step(.5,vWP.y);
      rk=mix(rk,vec3(.93,.95,.97),ln*.55*uIso);
      diffuseColor.rgb=rk;`); };
  rm.customProgramCacheKey = () => 'reef1';
  const reef = new THREE.Mesh(g, rm); reef.castShadow = reef.receiveShadow = true; S.add(reef);
  const base = new THREE.Mesh(new THREE.BoxGeometry(LW, 8, LW), rockMaterial({ lith: 'shale', color: '#7d755f', scale: 5 })); base.position.y = -4.06; base.receiveShadow = true; S.add(base);
  const hitPlane = reef;
  function shape(k) { for (let i = 0; i < pos.count; i++) pos.setY(i, Yv(full[i] * k)); pos.needsUpdate = true; g.computeVertexNormals(); }

  // --- море
  const water = new THREE.Mesh(new THREE.PlaneGeometry(LW, LW, 1, 1).rotateX(-Math.PI / 2), new THREE.MeshPhysicalMaterial({ color: '#1f7396', transparent: true, opacity: .5, roughness: .12, metalness: 0, clearcoat: .6, clearcoatRoughness: .1, depthWrite: false, normalMap: waves(), normalScale: new THREE.Vector2(.35, .35) }));
  S.add(water);
  const wside = new THREE.Mesh(new THREE.BoxGeometry(LW, 1, LW), new THREE.MeshStandardMaterial({ color: '#2d7fa8', transparent: true, opacity: .24, depthWrite: false })); S.add(wside);
  // --- перекрывающие осадки: полупрозрачный блок, чтобы видеть форму по «сейсмике»
  const shale = new THREE.Mesh(new THREE.BoxGeometry(LW, 1, LW), new THREE.MeshStandardMaterial({ color: LEG.shale, transparent: true, opacity: .2, depthWrite: false, roughness: 1 })); S.add(shale);
  const edges = new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.BoxGeometry(LW, 1, LW)), new THREE.LineBasicMaterial({ color: LEG.shale })); S.add(edges);
  const topY = () => Yv(cs.H * 1.14);

  // --- подвижный разрез: пористость из той же функции porosity()
  const secC = document.createElement('canvas'); secC.width = 150; secC.height = 64;
  const secT = new THREE.CanvasTexture(secC); secT.colorSpace = THREE.SRGBColorSpace; secT.magFilter = THREE.LinearFilter;
  const secH = cs.H * 1.12, sec = new THREE.Mesh(new THREE.PlaneGeometry(LW, Yv(secH)), new THREE.MeshBasicMaterial({ map: secT, transparent: true, side: THREE.DoubleSide, alphaTest: .4, toneMapped: false })); sec.visible = false; S.add(sec);
  function paintSec(z) {
    const c = secC.getContext('2d'), im = c.createImageData(secC.width, secC.height), w = M.owcY(cs);
    for (let j = 0; j < secC.height; j++) for (let i = 0; i < secC.width; i++) {
      const x = ((i + .5) / secC.width - .5) * L, y = (1 - (j + .5) / secC.height) * secH, f = M.porosity(cs, x, y, z), o = (j * secC.width + i) * 4;
      if (f === null) { im.data[o + 3] = 0; continue; }
      let col = ramp(f, maxPhi);
      if (f >= P.cutoff) { const fl = y > w ? [46, 139, 87] : [52, 152, 219]; if ((i + j) % 3 === 0) col = fl; }
      im.data[o] = col[0]; im.data[o + 1] = col[1]; im.data[o + 2] = col[2]; im.data[o + 3] = 255;
    }
    c.putImageData(im, 0, 0); secT.needsUpdate = true;
  }
  function setSection(z) { clip.constant = X(z); sec.position.set(0, Yv(secH) / 2, X(z) + .02); paintSec(z); }

  stage.setSun(new THREE.Vector3(70, 110, 60), 95); S.fog = new THREE.Fog('#9fb2c2', 220, 600);
  stage.controls.minDistance = 40; stage.controls.maxDistance = 260;
  const cam = stage.low ? [80, 90, 190] : [70, 72, 138];
  stage.view(cam, [0, 8, 0], 0);
  S.add(stage.label(`высота ×${VE}`, [-LW / 2, Yv(cs.H) * .6, LW / 2], 'soft'));
  const seaL = stage.label('уровень моря', [-LW * .36, 0, LW / 2], 'soft'); S.add(seaL);

  // --- состояние
  const st = { t: 0.0, play: false, phase: 'history', wells: [], done: false, pick: null, sz: 0 };
  function time(t) {
    st.t = t; const s = M.stage(cs, t); shape(s.grow);
    const sy = Yv(s.sea), burY = Yv(s.bury), wet = t < .985;
    water.visible = wside.visible = seaL.visible = wet; water.position.y = sy; wside.scale.y = Math.max(.1, sy); wside.position.y = sy / 2; seaL.position.y = sy + 1;
    shale.visible = edges.visible = burY > .2; for (const m of [shale, edges]) { m.scale.y = Math.max(.1, burY); m.position.y = burY / 2; }
    const e = cap; e.textContent = s.phase === 'grow' ? 'Море поднимается, риф растёт следом и держится у поверхности' : s.phase === 'drown' ? 'Море поднялось слишком быстро: риф утонул и перестал расти' : 'Глина засыпает риф. Он становится ловушкой под покрышкой';
  }
  stage.cbs.push(dt => {
    if (st.play) { st.t = Math.min(1, st.t + dt / (stage.reduced ? .5 : 9)); time(st.t); ts.set(st.t); if (st.t >= 1) { st.play = false; toDrill(); } }
    if (water.visible && !stage.reduced) { const o = water.material.normalMap.offset; o.x += dt * .03; o.y += dt * .018; }
    for (const w of st.wells) if (w.k < 1) { w.k = Math.min(1, w.k + dt / 1.4); w.anim(w.k); }
  });

  const steps = ['Ответьте на вопрос справа', 'Смотрите историю: риф растёт, тонет, засыпается', `Нажмите на риф: поставьте ${P.wells} скважины`, 'Нажмите «Разрезать риф и узнать»', 'Двигайте разрез и сравните с лучшим планом'];
  stage.hint(0, steps);
  // --- панель
  section(panel, spec.title, `<p>${spec.intro}</p>`);
  prediction(panel, spec.prediction, i => { st.pick = i; hs.hidden = false; st.play = true; stage.hint(1, steps); hs.scrollIntoView({ behavior: 'smooth', block: 'nearest' }); });
  const hs = section(panel, 'История рифа', ''); hs.hidden = true;
  const cap = $('<p class="q"></p>'); hs.appendChild(cap);
  const ts = slider('Геологическое время', 0, 1, .005, 0, v => { st.play = false; time(v); if (v >= .995) toDrill(); }, v => v < .6 ? 'рост' : v < .7 ? 'затопление' : v < .995 ? 'погребение' : 'сегодня'); hs.appendChild(ts);
  const ds = section(panel, 'Бурение', `<p class="q">Линии на теле — равные высоты. Нажмите на риф, чтобы поставить скважину. Осталось: <b class="left">${P.wells}</b></p><div class="wl"></div>`); ds.hidden = true;
  const colC = canvas(210); ds.appendChild(colC);
  ds.appendChild($(`<p class="mut">Столбик — пористость по стволу. Зелёная полоса: пористость не ниже ${P.cutoff} % и выше контакта с водой.</p>`));
  const tail = $('<div></div>'); panel.appendChild(tail);
  honesty(panel, spec);
  time(0);

  function toDrill() {
    if (st.phase !== 'history') return; st.phase = 'drill'; stage.hint(2, steps); ds.hidden = false; ts.querySelector('input').disabled = true; rm.userData.iso.value = 1;
    const ray = new THREE.Raycaster(), el = stage.renderer.domElement; let dn = null;
    el.onpointerdown = e => (dn = [e.clientX, e.clientY]);
    el.onclick = e => {
      if (!dn || Math.hypot(e.clientX - dn[0], e.clientY - dn[1]) > 6) return;
      const b = el.getBoundingClientRect(); ray.setFromCamera(new THREE.Vector2((e.clientX - b.left) / b.width * 2 - 1, 1 - (e.clientY - b.top) / b.height * 2), stage.camera);
      const h = ray.intersectObject(hitPlane)[0]; if (h && st.phase === 'drill') well(h.point.x * U, h.point.z * U);
    };
    drawCols(); ds.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }
  function well(x, z) {
    if (st.wells.length >= P.wells) return;
    if (st.wells.some(w => Math.hypot(w.d.x - x, w.d.z - z) < P.min_dist)) return note(`Слишком близко: между скважинами не меньше ${P.min_dist} м.`);
    const d = M.drill(cs, x, z), G = new THREE.Group(), T = topY(); G.position.set(X(x), 0, X(z)); S.add(G);
    const rig = derrick(11, 3.2); rig.position.y = T; G.add(rig);
    const pipe = new THREE.Mesh(new THREE.CylinderGeometry(.22, .22, 1, 16), steel('#c3cad0', .3)); G.add(pipe);
    const cells = d.col.filter(c => c.phi !== null).map(c => { const m = new THREE.Mesh(new THREE.CylinderGeometry(.95, .95, Yv(d.dy) * 1.01, 24), new THREE.MeshStandardMaterial({ color: css(ramp(c.phi, maxPhi)), roughness: .8 })); m.material.color.setRGB(...ramp(c.phi, maxPhi).map(v => v / 255), THREE.SRGBColorSpace); m.position.y = Yv(c.y); m.visible = false; G.add(m);
      if (c.pay) { const r = new THREE.Mesh(new THREE.TorusGeometry(1.05, .16, 6, 24), new THREE.MeshStandardMaterial({ color: LEG.oil, emissive: LEG.oil, emissiveIntensity: .5 })); r.rotation.x = Math.PI / 2; m.add(r); } return [m, Yv(c.y)]; });
    const n = st.wells.length + 1, lb = stage.label(String(n), [0, T + 13.5, 0], 'num'); G.add(lb);
    const w = { d, k: 0, n, anim: k => { const y = T * (1 - k); pipe.scale.y = T - y; pipe.position.y = (T + y) / 2; cells.forEach(([m, my]) => (m.visible = my >= y)); if (k >= 1) drawCols(); } };
    shadow(G); st.wells.push(w); w.anim(0); ds.querySelector('.left').textContent = P.wells - st.wells.length;
    if (st.wells.length >= P.wells) { const b = $('<button class="main">Разрезать риф и узнать</button>'); b.onclick = () => { b.remove(); finish(); }; ds.appendChild(b); st.btn = b; stage.hint(3, steps); if (!stage.noScroll) b.scrollIntoView({ behavior: 'smooth', block: 'end' }); }
  }
  function note(t) { const e = $(`<p class="why">${t}</p>`); ds.appendChild(e); setTimeout(() => e.remove(), 3500); }
  function drawCols() {
    const [c, w, h] = colC.fit(); c.fillStyle = LEG.bg; c.fillRect(0, 0, w, h); const Y = y => h - 22 - y / (cs.H * 1.12) * (h - 34), cw = (w - 46) / P.wells, oy = Y(M.owcY(cs));
    c.font = '12px Segoe UI'; c.textAlign = 'center';
    for (let i = 0; i < P.wells; i++) { const x0 = 46 + i * cw; c.strokeStyle = '#2b3540'; c.strokeRect(x0 + 4.5, 6.5, cw - 9, h - 28); const wl = st.wells[i]; c.fillStyle = LEG.muted; c.fillText(wl ? 'скв. ' + wl.n : 'свободна', x0 + cw / 2, h - 6);
      if (!wl || wl.k < 1) continue; const dh = wl.d.dy / (cs.H * 1.12) * (h - 34) + .6;
      wl.d.col.forEach(k => { if (k.phi === null) return; c.fillStyle = css(ramp(k.phi, maxPhi)); c.fillRect(x0 + 12, Y(k.y) - dh / 2, k.phi / maxPhi * (cw - 34), dh); if (k.pay) { c.fillStyle = LEG.oil; c.fillRect(x0 + 6, Y(k.y) - dh / 2, 5, dh); } });
      c.fillStyle = LEG.text; c.fillText(`${fmt(wl.d.net, 0)} м`, x0 + cw / 2, 20); }
    c.strokeStyle = LEG.water; c.setLineDash([4, 4]); c.beginPath(); c.moveTo(46, oy); c.lineTo(w, oy); c.stroke(); c.setLineDash([]); c.fillStyle = LEG.water; c.textAlign = 'left'; c.fillText('ВНК', 10, oy + 4);
  }
  function finish() {
    if (st.done) return; st.done = true; st.phase = 'done'; stage.hint(4, steps);
    const got = st.wells.reduce((s, w) => s + w.d.vol, 0), bst = M.best(cs, P.wells, P.min_dist), bv = bst.reduce((s, w) => s + w.vol, 0), pc = Math.min(100, Math.round(got / bv * 100));
    sec.visible = true; shale.visible = false; rm.userData.iso.value = .35;
    stage.view(stage.low ? [40, 60, 190] : [38, 46, 138], [0, 8, 0], 2); setSection(0);
    bst.forEach(b => { const m = new THREE.Mesh(new THREE.TorusGeometry(2.1, .25, 8, 40), new THREE.MeshStandardMaterial({ color: LEG.text, emissive: LEG.text, emissiveIntensity: .7 })); m.rotation.x = Math.PI / 2; m.position.set(X(b.x), topY() + .4, X(b.z)); S.add(m); });
    const zn = st.wells.map(w => `скв. ${w.n} — ${spec.zones[w.d.zone] ? spec.zones[w.d.zone].ru : 'вне рифа'}, ${fmt(w.d.net, 0)} м`).join('; ');
    const r = section(tail, 'Итог', `<div class="score"><div><b>${pc} %</b><span>от лучшего плана теми же скважинами</span></div><div><b>${fmt(st.wells.reduce((s, w) => s + w.d.net, 0), 0)} м</b><span>суммарная эффективная толщина</span></div></div><p>${zn}. Белые кольца — план, который нашёл перебор.</p>`);
    r.appendChild(slider('Двигайте разрез', -.48, .48, .01, 0, v => setSection(v * L), v => fmt(v * L, 0) + ' м'));
    r.appendChild($(`<p class="leg"><span><i style="background:${css(ramp(3, maxPhi))}"></i>плотно</span><span><i style="background:${css(ramp(maxPhi * .6, maxPhi))}"></i>${fmt(maxPhi * .6, 0)} %</span><span><i style="background:${css(ramp(maxPhi, maxPhi))}"></i>${fmt(maxPhi, 0)} % пор</span><span><i style="background:${LEG.oil}"></i>нефть</span><span><i style="background:${LEG.water}"></i>вода</span></p>`));
    section(tail, 'Что сказал автор', `<ul>${Object.values(spec.zones).map(z => `<li>${z.ru}: ${fmt(z.phi[0], z.phi[0] % 1 ? 1 : 0)}–${fmt(z.phi[1], z.phi[1] % 1 ? 1 : 0)} % <span class="pg">стр. ${z.page}</span></li>`).join('')}</ul>`);
    verdict(tail, spec.prediction, st.pick); closing(tail, spec); tail.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
  return { st, cs, time, toDrill, well, finish, setSection, skip() { st.pick = 1; hs.hidden = false; time(1); ts.set(1); toDrill(); } };
}
