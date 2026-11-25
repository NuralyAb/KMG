import { THREE, rockMaterial, LEG, steel, paint } from '../core.js';
import { derrick, bar, shadow } from '../prefabs.js';
import * as M from '../models/pressure.js';
import { clamp, rng } from '../models/util.js';
import { $, fmt, section, prediction, verdict, closing, honesty, canvas, slider, timeText } from '../ui.js';

const U = 10;                                   // 1 единица сцены = 10 м
const logT = k => Math.pow(10, k);              // ползунок времени — логарифмический

function dot() { const c = document.createElement('canvas'); c.width = c.height = 32; const g = c.getContext('2d'); g.fillStyle = '#fff'; g.beginPath(); g.arc(16, 16, 14, 0, 7); g.fill(); return new THREE.CanvasTexture(c); }

export function build(stage, spec, seed, panel) {
  const cs = M.buildCase(spec, seed), p = { ...cs.p }, S = stage.scene, RV = spec.params.r_view, R = RV / U, MP = 24 / (M.unitDrop(p) * M.E1(1 / (4 * M.kappa(p) * spec.params.t_max)));
  const thick = p.h / U * spec.params.h_exag * 3, y0 = thick + 34; // уровень начального давления
  const tmax = Math.log10(spec.params.t_max);

  // --- пласт: диск с глиной снизу
  const rock = rockMaterial({ lith: 'sand', fluid: 'oil', pore: .8, scale: .05 }); rock.userData.u.uHasF.value = 0;
  const disc = new THREE.Mesh(new THREE.CylinderGeometry(R, R, thick, 160, 1), rock); disc.position.y = thick / 2; disc.receiveShadow = disc.castShadow = true; S.add(disc);
  const uvFix = (g, k) => { const pos = g.attributes.position, nor = g.attributes.normal, uv = g.attributes.uv; for (let i = 0; i < pos.count; i++) { if (Math.abs(nor.getY(i)) > .5) uv.setXY(i, pos.getX(i) * k, pos.getZ(i) * k); else uv.setXY(i, Math.atan2(pos.getZ(i), pos.getX(i)) * R * k, pos.getY(i) * k); } };
  uvFix(disc.geometry, 1.2);
  const base = new THREE.Mesh(new THREE.CylinderGeometry(R * 1.0, R * 1.02, 7, 160), rockMaterial({ lith: 'shale', scale: .05 })); base.position.y = -3.5; base.receiveShadow = true; uvFix(base.geometry, 1); S.add(base);

  // --- поверхность давления (полярная сетка, радиусы сгущаются к скважине)
  const NR = 90, NA = 160, rs = Array.from({ length: NR + 1 }, (_, i) => 1 * Math.pow(RV, i / NR));
  const pos = new Float32Array((NR + 1) * (NA + 1) * 3), dropA = new Float32Array((NR + 1) * (NA + 1)), ix = [];
  for (let i = 0; i <= NR; i++) for (let j = 0; j <= NA; j++) { const a = j / NA * Math.PI * 2, o = (i * (NA + 1) + j) * 3; pos[o] = Math.cos(a) * rs[i] / U; pos[o + 2] = Math.sin(a) * rs[i] / U; }
  for (let i = 0; i < NR; i++) for (let j = 0; j < NA; j++) { const a = i * (NA + 1) + j, b = a + NA + 1; ix.push(a, a + 1, b, b, a + 1, b + 1); }
  const sg = new THREE.BufferGeometry(); sg.setAttribute('position', new THREE.BufferAttribute(pos, 3)); sg.setAttribute('aDrop', new THREE.BufferAttribute(dropA, 1)); sg.setIndex(ix);
  const sm = new THREE.MeshPhysicalMaterial({ color: LEG.PRESSURE, roughness: .16, metalness: .05, transparent: true, opacity: .62, side: THREE.DoubleSide, clearcoat: .7, depthWrite: false });
  sm.onBeforeCompile = s => {
    s.uniforms.uStep = { value: 1.2 / MP };
    s.vertexShader = s.vertexShader.replace('#include <common>', '#include <common>\nattribute float aDrop;varying float vD;').replace('#include <begin_vertex>', '#include <begin_vertex>\nvD=aDrop;');
    s.fragmentShader = s.fragmentShader.replace('#include <common>', '#include <common>\nvarying float vD;uniform float uStep;').replace('#include <color_fragment>', `
      float q=vD/uStep; float f=abs(fract(q-.5)-.5)/max(fwidth(q),1e-5); float ln=(1.-smoothstep(.6,1.6,f))*step(uStep*.4,vD);
      diffuseColor.rgb=mix(diffuseColor.rgb*(.55+.45*exp(-vD/uStep*.12)),vec3(.95,1.,1.),ln*.75); diffuseColor.a=mix(diffuseColor.a,.95,ln*.8);
      diffuseColor.a*=mix(.5,1.,smoothstep(.0,uStep*.5,vD));`);
  };
  const surf = new THREE.Mesh(sg, sm); surf.position.y = y0; S.add(surf);
  const rim = new THREE.Mesh(new THREE.TorusGeometry(R, .12, 8, 200), new THREE.MeshBasicMaterial({ color: LEG.muted })); rim.rotation.x = Math.PI / 2; rim.position.y = y0; S.add(rim);

  // --- радиус возмущения и «если бы как звук»
  const ringM = c => new THREE.MeshStandardMaterial({ color: c, emissive: c, emissiveIntensity: .55 });
  const ring = new THREE.Mesh(new THREE.TorusGeometry(1, .012, 8, 160), ringM(LEG.PRESSURE)); ring.rotation.x = Math.PI / 2; ring.position.y = thick + .3; S.add(ring);

  // --- скважины
  const rig = derrick(26, 6.5); rig.position.y = y0 + 6; S.add(rig);
  const pad = new THREE.Mesh(new THREE.CylinderGeometry(7, 7.4, 1, 48), paint('#6b6f66', .9)); pad.position.y = y0 + 5.6; pad.castShadow = pad.receiveShadow = true; S.add(pad);
  const pipe = (x, z, yt, r, c) => { const m = new THREE.Mesh(new THREE.CylinderGeometry(r, r, yt, 24), steel(c, .35)); m.position.set(x, yt / 2, z); m.castShadow = true; S.add(m); return m; };
  pipe(0, 0, y0 + 5.5, .55, '#aab2b9');
  const ang = -.62, ox = Math.cos(ang) * cs.obs / U, oz = Math.sin(ang) * cs.obs / U;
  pipe(ox, oz, y0 + 5, .45, '#d8b23a');
  const head = new THREE.Group(); head.add(new THREE.Mesh(new THREE.CylinderGeometry(1.1, 1.1, 1.2, 24), paint('#8d2f25')), new THREE.Mesh(bar([-1.8, .8, 0], [1.8, .8, 0], .25), steel())); head.position.set(ox, y0 + 5.2, oz); S.add(shadow(head));
  const bead = new THREE.Mesh(new THREE.SphereGeometry(1.1, 32, 20), ringM(LEG.measure)); S.add(bead);
  S.add(stage.label('эксплуатационная скважина', [0, y0 + 38, 0], ''));
  const obsL = stage.label('', [ox, y0 + 10, oz], 'hot'); S.add(obsL);
  const ringL = stage.label('', [0, thick + 1, 0], 'soft'); S.add(ringL);
  S.add(stage.label('начальное давление', [-R * .2, y0 + 2, R * .95], 'soft'));
  S.add(stage.label('нефтяной пласт', [R * .3, thick * .5, R * .97], 'soft'));

  // --- частицы: скорость из той же формулы, u ~ (1/r)·exp(−r²/4κt)
  const NP = stage.low ? 300 : 700, rr = rng(5), pr = new Float32Array(NP), pa = new Float32Array(NP), py = new Float32Array(NP), pp = new Float32Array(NP * 3);
  for (let i = 0; i < NP; i++) { pr[i] = 8 + Math.sqrt(rr()) * RV; pa[i] = rr() * 6.283; py[i] = thick + .25 + rr() * .8; }
  const pg = new THREE.BufferGeometry(); pg.setAttribute('position', new THREE.BufferAttribute(pp, 3));
  const pts = new THREE.Points(pg, new THREE.PointsMaterial({ color: LEG.oil, size: 1.5, sizeAttenuation: true, map: dot(), alphaTest: .5 })); S.add(pts);

  stage.setSun(new THREE.Vector3(120, 190, 90), 150); S.fog = new THREE.Fog('#9fb2c2', 320, 900);
  stage.controls.minDistance = 50; stage.controls.maxDistance = 420;
  const camFar = stage.low ? [150, 120, 250] : [112, 78, 190];
  stage.view(camFar, [0, y0 * .55, 0], 0);

  // --- состояние
  const st = { k: 0, play: false, guess: null, pick: null, done: false, lab: false };
  const T = () => st.k <= 0 ? 0 : logT(st.k);
  const arr = () => M.arrival(p, cs.obs);
  let dirty = true, lastK = -1;
  function update() {
    const t = T(), u = M.unitDrop(p), kap = M.kappa(p);
    for (let i = 0; i <= NR; i++) { const d = t ? u * M.E1(rs[i] * rs[i] / (4 * kap * t)) : 0; for (let j = 0; j <= NA; j++) { const o = i * (NA + 1) + j; pos[o * 3 + 1] = -Math.min(d * MP, y0 - thick - 1.5); dropA[o] = d; } }
    sg.attributes.position.needsUpdate = sg.attributes.aDrop.needsUpdate = true; sg.computeVertexNormals();
    const fr = M.front(p, t) / U; ring.visible = fr > .5 && fr <= R; ring.scale.set(Math.max(fr, .01), Math.max(fr, .01), 12);
    ringL.visible = ring.visible; ringL.position.set(-fr * .35, thick + 1, fr * .93); ringL.element.textContent = `радиус ${fmt(fr * U, 0)} м`;
    const d = M.drop(p, cs.obs, t); bead.position.set(ox, y0 - d * MP, oz);
    obsL.element.innerHTML = `наблюдательная, ${cs.obs} м<br><b>${fmt(p.p0 - d, 2)} МПа</b>`;
    pa.length; draw();
  }
  stage.cbs.push(dt => {
    if (st.play) { st.k = Math.min(tmax, st.k + dt * (stage.reduced ? 4 : .62)); tl.set(st.k); if (st.k >= tmax) { st.play = false; finish(); } dirty = true; }
    if (st.k !== lastK || dirty) { lastK = st.k; dirty = false; update(); }
    const t = T(), kap = M.kappa(p);
    if (t > 0) for (let i = 0; i < NP; i++) { const r = pr[i]; pr[i] -= dt * Math.min(140, 4200 / r * Math.exp(-r * r / (4 * kap * t))) * (p.Q / 60); if (pr[i] < 6) { pr[i] = RV * (.6 + .4 * Math.random()); } }
    for (let i = 0; i < NP; i++) { pp[i * 3] = Math.cos(pa[i]) * pr[i] / U; pp[i * 3 + 1] = py[i]; pp[i * 3 + 2] = Math.sin(pa[i]) * pr[i] / U; }
    pg.attributes.position.needsUpdate = true;
  });

  const steps = ['Ответьте на вопрос справа', 'Поставьте прогноз и нажмите «Пустить скважину»', 'Смотрите, как расходится воронка', 'Сравните прогноз и покрутите параметры в лаборатории'];
  stage.hint(0, steps);
  // --- панель
  section(panel, spec.title, `<p>${spec.intro}</p>`);
  prediction(panel, spec.prediction, i => { st.pick = i; gs.hidden = false; stage.hint(1, steps); gs.scrollIntoView({ behavior: 'smooth', block: 'nearest' }); });
  const gs = section(panel, 'Ваш прогноз', `<div class="kv"><div><span>Расстояние</span><b>${cs.obs} м</b></div><div><span>k</span><b>${fmt(p.k, 2)} мкм²</b></div><div><span>μ</span><b>${fmt(p.mu)} мПа·с</b></div><div><span>β*</span><b>${fmt(p.beta)}·10⁻¹⁰ 1/Па</b></div></div><p class="mut">κ = k/(μβ*), а время считается как r²/(4κ). Можно посчитать, можно угадать.</p>`); gs.hidden = true;
  let gk = 3.2; gs.appendChild(slider('Падение дойдёт через', 1, tmax, .01, gk, v => (gk = v), v => timeText(logT(v))));
  const go = $('<button class="main">Пустить скважину</button>'); gs.appendChild(go);
  const run = section(panel, 'Опыт', ''); run.hidden = true;
  const tl = slider('Время после пуска', 0, tmax, .005, 0, v => { st.play = false; st.k = v; if (v >= tmax - .01) finish(); }, v => timeText(v <= 0 ? 0 : logT(v))); run.appendChild(tl);
  const C1 = canvas(150), C2 = canvas(150);
  run.appendChild($('<h3>Давление в наблюдательной скважине</h3>')); run.appendChild(C1);
  run.appendChild($('<h3>Радиус возмущения: расчёт и «как звук»</h3>')); run.appendChild(C2);
  const tail = $('<div></div>'); panel.appendChild(tail);
  honesty(panel, { ...spec, exaggerations: [`глубина воронки: 1 МПа = ${fmt(MP * U, 0)} м рисунка; слишком глубокая воронка обрезана у пласта`, `линии на воронке — через ${fmt(1.2 / MP, 3)} МПа`, ...spec.exaggerations] });
  go.onclick = () => { stage.hint(2, steps); st.guess = logT(gk); go.remove(); gs.querySelector('input').disabled = true; run.hidden = false; st.play = true; stage.view(stage.low ? [110, 95, 190] : [82, 62, 132], [0, y0 * .5, 0], 3); run.scrollIntoView({ behavior: 'smooth', block: 'nearest' }); };

  function axes(g, w, h, xs) {
    g.fillStyle = LEG.bg; g.fillRect(0, 0, w, h); g.strokeStyle = '#2b3540'; g.strokeRect(44.5, 8.5, w - 54, h - 34);
    g.fillStyle = LEG.muted; g.font = '11px Segoe UI'; g.textAlign = 'center'; xs.forEach(([x, t]) => g.fillText(t, x, h - 8)); g.textAlign = 'right';
  }
  function draw() {
    if (run.hidden) return;
    const X = (k, w) => 44 + (k - 1) / (tmax - 1) * (w - 54), tick = w => [[60, 'мин'], [3600, 'час'], [86400, 'сутки'], [864000, '10 сут']].map(([s, n]) => [X(Math.log10(s), w), n]);
    { const [g, w, h] = C1.fit(); axes(g, w, h, tick(w)); const dm = Math.max(.05, M.drop(p, cs.obs, spec.params.t_max)), Y = d => 12 + d / dm * (h - 46);
      g.fillText(fmt(p.p0, 2), 40, 16); g.fillText(fmt(p.p0 - dm, 2), 40, h - 30);
      const mark = (t, col, name, dy) => { const x = X(Math.log10(t), w); g.strokeStyle = col; g.setLineDash([3, 4]); g.beginPath(); g.moveTo(x, 9); g.lineTo(x, h - 26); g.stroke(); g.setLineDash([]); g.fillStyle = col; g.textAlign = x > w * .6 ? 'right' : 'left'; g.fillText(name, x + (x > w * .6 ? -5 : 5), dy); };
      if (st.guess) mark(st.guess, LEG.text, 'ваш прогноз', h - 46);
      if (st.k >= Math.log10(arr())) mark(arr(), LEG.measure, 'самое быстрое падение', h - 32);
      g.beginPath(); for (let k = 1; k <= st.k; k += .03) { const x = X(k, w), y = Y(M.drop(p, cs.obs, logT(k))); k === 1 ? g.moveTo(x, y) : g.lineTo(x, y); } g.strokeStyle = LEG.PRESSURE; g.lineWidth = 2.2; g.stroke(); }
    { const [g, w, h] = C2.fit(); axes(g, w, h, [[44, '0'], [(w + 34) / 2, '5 сут'], [w - 22, '10 сут']]); const TM = 864000, rm = M.front(p, TM) * 1.1, Xl = t => 44 + t / TM * (w - 54), Y = r => h - 26 - Math.min(1, r / rm) * (h - 40);
      g.fillText(fmt(rm, 0) + ' м', 40, 16); const t1 = 3600 * 6, v = M.front(p, t1) / t1, cur = Math.min(TM, T());
      g.save(); g.beginPath(); g.rect(44, 8, w - 54, h - 34); g.clip();
      g.setLineDash([5, 5]); g.strokeStyle = LEG.unc; g.lineWidth = 1.6; g.beginPath(); g.moveTo(Xl(0), Y(0)); const te = Math.min(cur, rm / v); g.lineTo(Xl(te), Y(v * te)); g.stroke(); g.setLineDash([]);
      g.beginPath(); for (let i = 0; i <= 100; i++) { const t = cur * i / 100; i ? g.lineTo(Xl(t), Y(M.front(p, t))) : g.moveTo(Xl(0), Y(0)); } g.strokeStyle = LEG.PRESSURE; g.lineWidth = 2.2; g.stroke(); g.restore();
      g.textAlign = 'left'; g.fillStyle = LEG.PRESSURE; g.fillText('расчёт, √t', w * .55, Y(M.front(p, TM * .52)) + 22); g.fillStyle = LEG.unc; g.fillText('если бы как звук', 70, 20); }
  }
  function finish() {
    if (st.done) return; st.done = true; st.play = false; stage.hint(3, steps);
    const a = arr(), q = st.guess ? Math.max(st.guess / a, a / st.guess) : null;
    section(tail, 'Итог', `<div class="score"><div><b>${timeText(a)}</b><span>дошло по расчёту</span></div><div><b>${st.guess ? timeText(st.guess) : '—'}</b><span>ваш прогноз</span></div></div>
      <p class="why">${!q ? '' : q < 1.3 ? '<b>Отлично:</b> ошибка меньше 30 %.' : q < 3 ? '<b>Верный порядок.</b> Промах в ' + fmt(q) + ' раза.' : '<b>Промах в ' + fmt(q, 0) + ' раз.</b> Интуиция про «скорость волны» здесь не работает.'} При вдвое большем расстоянии ждать пришлось бы ${timeText(a * 4)}.</p>`);
    verdict(tail, spec.prediction, st.pick);
    const lab = section(tail, 'Лаборатория', `<p class="mut">Меняйте параметры: воронка и графики пересчитываются. <span class="kap"></span></p>`);
    const kap = lab.querySelector('.kap'), show = () => { const k = M.kappa(p), [a1, b1] = spec.limits.kappa; kap.innerHTML = `κ = <b>${fmt(k, 2)} м²/с</b>${k < a1 || k > b1 ? ' — вне пределов, названных автором' : ''}`; };
    for (const key in spec.controls) { const [a0, b0, s0, n] = spec.controls[key]; lab.insertBefore(slider(n, a0, b0, s0, clamp(p[key], a0, b0), v => { p[key] = v; dirty = true; show(); }), null); }
    show(); closing(tail, spec); tail.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
  return { st, cs, p, finish, skip(k = 5.2) { st.pick = 0; st.guess = 3600; gs.hidden = false; run.hidden = false; st.k = k; tl.set(k); dirty = true; } };
}
