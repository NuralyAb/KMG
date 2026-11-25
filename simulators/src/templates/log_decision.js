import { THREE, rockMaterial, LEG } from '../core.js';
import { derrick, loggingTruck, loggingTool, cutaway, capShape, grassMat, bar } from '../prefabs.js';
import * as M from '../models/log.js';
import { fbm, clamp } from '../models/util.js';
import { $, fmt, section, prediction, verdict, closing, honesty, canvas } from '../ui.js';

const RES = { oil: ['Чистая нефть', LEG.oil], mix: ['Нефть с водой', '#6fb08d'], water: ['Вода', LEG.water], dry: ['Притока нет', LEG.dense] };
const COST = 1;

export function build(stage, spec, seed, panel) {
  const cs = M.buildCase(spec, seed), cv = M.curves(spec, cs), S = stage.scene, p = spec.params;
  const H = cs.bot - cs.top, yOf = z => cs.top - z;                // глубина вниз
  const half = 17, bore = .85, gap = 7;
  const undul = (x, w, z) => fbm(x * .06, z * .05, w * .06, seed, 3) * 1.1 + x * .02;

  // --- разрез
  const layers = cs.layers.map(l => ({ ...l, src: l, relief: 0,
    material: rockMaterial({ lith: l.lith, fluid: l.fluid, fluid2: l.kind === 'mix' ? 'water' : null, inv: l.collector ? 2.6 : 0, pore: 2.1, reveal: 0, scale: .13 }) }));
  const block = cutaway({ half, bore, layers, yOf, undul }); S.add(block);
  const capM = rockMaterial({ lith: 'shale', reveal: 0, scale: .13 });
  const capG = new THREE.ShapeGeometry(capShape(half, bore), 24); capG.rotateX(-Math.PI / 2);
  // вырез в плоскости XZ: четверть x>0, z>0
  const cap = new THREE.Mesh(capG, capM); cap.receiveShadow = true; S.add(cap);

  // --- поверхность над разрывом
  const top = new THREE.Group(); top.position.y = gap; S.add(top);
  const slabG = new THREE.ExtrudeGeometry(capShape(half, bore), { depth: 3, bevelEnabled: false, curveSegments: 20 }); slabG.rotateX(-Math.PI / 2);
  const soil = rockMaterial({ lith: 'shale', color: '#8a7358', scale: .1 });
  const slab = new THREE.Mesh(slabG, [grassMat(.06), soil]); slab.castShadow = slab.receiveShadow = true; top.add(slab);
  const rig = derrick(27, 7); rig.position.y = 3; top.add(rig);
  const truck = loggingTruck(); truck.position.set(-10, 3, 9); truck.rotation.y = Math.PI + .735; top.add(truck);
  const cableM = new THREE.MeshStandardMaterial({ color: '#15181b', roughness: .6 });
  const topY = gap + 3 + rig.userData.top;
  S.add(new THREE.Mesh(bar([-7.7, gap + 5.9, 6.9], [0, topY, 0], .06), cableM));
  // разрыв: пунктир ствола и подпись
  S.add(stage.label('разрыв ≈ 2 км', [half * .55, gap / 2, 1], 'soft'));
  const casing = new THREE.Mesh(new THREE.CylinderGeometry(bore * .95, bore * .95, gap, 32, 1, true, Math.PI / 2, Math.PI * 1.5), new THREE.MeshStandardMaterial({ color: '#7d858c', metalness: .8, roughness: .4, side: THREE.DoubleSide }));
  casing.position.y = gap / 2; S.add(casing);
  // раствор в стволе
  const mud = new THREE.Mesh(new THREE.CylinderGeometry(bore * .92, bore * .92, H, 40, 1, true, Math.PI / 2, Math.PI * 1.5),
    new THREE.MeshStandardMaterial({ color: LEG.mud, transparent: true, opacity: .4, roughness: .15, side: THREE.DoubleSide, depthWrite: false }));
  mud.position.y = -H / 2; S.add(mud);
  // прибор и кабель
  const tool = loggingTool(6.5, .36); S.add(tool);
  const cable = new THREE.Mesh(new THREE.CylinderGeometry(.06, .06, 1, 8), cableM); S.add(cable);
  // номера интервалов
  const tags = cs.layers.filter(l => l.n).map(l => {
    const o = stage.label(String(l.n), [-.6, yOf((l.top + l.bot) / 2), 1.5], 'num'); o.visible = false; S.add(o);
    o.element.onclick = () => select(l); return { l, o };
  });
  S.add(stage.label('глубина ↓', [0.5, -H - 1.5, half + .6], 'soft'));

  stage.setSun(new THREE.Vector3(34, 46, 40), 48);
  stage.sun.target.position.set(0, -H / 2, 0);
  S.fog = new THREE.Fog('#9fb2c2', 120, 320);
  const mob = stage.low;
  stage.controls.minDistance = 14; stage.controls.maxDistance = 130;
  stage.view(mob ? [56, 40, 72] : [50, 36, 66], [0, 6, 0], 0);

  // --- состояние
  const st = { z: cs.top, zmax: cs.top, play: false, sel: null, tested: {}, started: false, done: false, pick: null };
  const est = new Map(cs.layers.filter(l => l.n).map(l => [l.n, M.estimate(spec, cs, cv, l)]));
  const setZ = z => { st.z = clamp(z, cs.top, cs.bot); st.zmax = Math.max(st.zmax, st.z); };
  stage.cbs.push(dt => {
    if (st.play) { setZ(st.z + dt * (stage.reduced ? 30 : 6.5)); if (st.z >= cs.bot - .01) { st.play = false; ready(); } draw(); }
    const y = yOf(st.z); tool.position.y = y;
    const len = topY - (y + 6.5); cable.scale.y = len; cable.position.y = y + 6.5 + len / 2;
    tool.userData.halo.material.uniforms.t.value += dt;
    if (st.play && !stage.fly) { const t = stage.controls.target, k = Math.min(1, dt * 2.2), d = (y + 2) - t.y; t.y += d * k; stage.camera.position.y += d * k; }
    tags.forEach(t => (t.o.visible = st.zmax >= t.l.bot && st.started));
    for (const l of layers) { const u = l.material.userData.u.uReveal; const target = st.done || (l.n && st.tested[l.n]) ? 1 : 0; u.value += (target - u.value) * Math.min(1, dt * 2.5); }
    capM.userData.u.uReveal.value = layers[0].material.userData.u.uReveal.value;
  });

  const steps = ['Ответьте на вопрос справа', 'Нажмите «Опустить прибор»', 'Прибор пишет кривые — следите за планшетом', 'Выбирайте интервалы 1, 2, 3… и испытайте до трёх', 'Порода вскрыта: сравните со своими решениями'];
  stage.hint(0, steps);
  // --- панель
  const head = section(panel, spec.title, `<p>${spec.intro}</p>`);
  prediction(panel, spec.prediction, i => { st.pick = i; go.disabled = false; go.textContent = 'Опустить прибор'; stage.hint(1, steps); });
  const go = $('<button class="main" disabled>Сначала ответьте</button>'); panel.appendChild(go);
  const logSec = section(panel, 'Планшет', ''); logSec.hidden = true;
  const C = canvas(380); C.className = 'log'; logSec.appendChild(C);
  logSec.appendChild($(`<p class="mut">Тяните по планшету: точка на кривой и прибор в стволе — одна глубина. Обозначения русской школы.</p>`));
  const work = $('<div></div>'); panel.appendChild(work);
  const tail = $('<div></div>'); panel.appendChild(tail);
  honesty(panel, spec);
  go.onclick = () => { stage.hint(2, steps); st.started = true; st.play = true; go.hidden = true; logSec.hidden = false; stage.view(mob ? [24, 9, 30] : [23, 10, 29], [0, 0, 0], 2.2); draw(); logSec.scrollIntoView({ behavior: 'smooth', block: 'nearest' }); };

  const drag = e => { const r = C.getBoundingClientRect(); const y = (e.clientY - r.top - 34) / (r.height - 42); st.play = false; setZ(cs.top + clamp(y, 0, 1) * H); if (st.zmax >= cs.bot - .3) ready(); draw();
    const l = cs.layers.find(l => l.n && st.z >= l.top && st.z <= l.bot); if (l && st.ready && l.bot <= st.zmax) select(l, true); };
  C.style.touchAction = 'none';
  C.onpointerdown = e => { C.setPointerCapture(e.pointerId); drag(e); C.onpointermove = drag; };
  C.onpointerup = () => { C.onpointermove = null; follow(st.z); };
  function follow(z) { const y = yOf(z), c = stage.camera.position, t = stage.controls.target, d = y + 2 - t.y; stage.view([c.x, c.y + d, c.z], [t.x, t.y + d, t.z], .7); }

  function draw() {
    const [g, w, h] = C.fit(), y0 = 34, hh = h - 42, cw = [26, 1, 1, 1, 1], left = 30, tw = (w - left) / 4, Y = z => y0 + (z - cs.top) / H * hh;
    g.fillStyle = LEG.bg; g.fillRect(0, 0, w, h);
    const tr = [
      ['ПС, мВ', cv.SP, LEG.SP, -100, 40, false], ['ГК, усл. ед.', cv.GR, LEG.GR, 10, 130, false],
      ['ρ, Ом·м', cv.RES, LEG.RES, 1, 200, true], ['kп, %', cv.POR.map(x => x * 100), LEG.POR, 40, 0, false]];
    g.font = '12px Segoe UI'; g.textBaseline = 'middle';
    const N = Math.floor((st.zmax - cs.top) / p.dz) + 1;
    cs.layers.forEach(l => { if (!l.n || l.bot > st.zmax + .01) return;
      g.fillStyle = st.sel === l ? 'rgba(236,239,244,.16)' : 'rgba(236,239,244,.05)'; g.fillRect(0, Y(l.top), w, Y(l.bot) - Y(l.top));
      const t = st.tested[l.n]; if (t) { g.fillStyle = RES[t][1]; g.fillRect(0, Y(l.top), 5, Y(l.bot) - Y(l.top)); }
      g.fillStyle = LEG.text; g.font = 'bold 14px Segoe UI'; g.textAlign = 'center'; g.fillText(l.n, 16, (Y(l.top) + Y(l.bot)) / 2); });
    tr.forEach(([name, a, col, lo, hi, lg], i) => {
      const x0 = left + i * tw, X = v => { const k = lg ? Math.log(v / lo) / Math.log(hi / lo) : (v - lo) / (hi - lo); return x0 + 4 + clamp(k, 0, 1) * (tw - 8); };
      g.strokeStyle = '#2b3540'; g.lineWidth = 1; g.strokeRect(x0 + .5, y0, tw, hh);
      g.beginPath(); for (let q = 1; q < 4; q++) { const xx = lg ? X([1, 2, 10, 100][q]) : x0 + tw * q / 4; g.moveTo(xx, y0); g.lineTo(xx, y0 + hh); } g.strokeStyle = '#212a33'; g.stroke();
      g.fillStyle = col; g.font = '12px Segoe UI'; g.textAlign = 'center'; g.fillText(name, x0 + tw / 2, 10);
      g.fillStyle = LEG.muted; g.font = '10px Segoe UI'; g.textAlign = 'left'; g.fillText(lo, x0 + 4, 25); g.textAlign = 'right'; g.fillText(hi, x0 + tw - 4, 25);
      g.beginPath(); for (let j = 0; j < Math.min(N, a.length); j++) { const x = X(a[j]), y = Y(cv.depth[j]); j ? g.lineTo(x, y) : g.moveTo(x, y); }
      g.strokeStyle = col; g.lineWidth = 1.7; g.stroke();
      const j = Math.round((st.z - cs.top) / p.dz); if (j < N && a[j] !== undefined) { g.beginPath(); g.arc(X(a[j]), Y(st.z), 4, 0, 7); g.fillStyle = col; g.fill(); }
    });
    g.strokeStyle = LEG.measure; g.setLineDash([4, 4]); g.beginPath(); g.moveTo(left, Y(st.z)); g.lineTo(w, Y(st.z)); g.stroke(); g.setLineDash([]);
    g.fillStyle = LEG.muted; g.font = '10px Segoe UI'; g.textAlign = 'left'; g.fillText(Math.round(cs.top), 1, y0 - 6);  g.fillText(Math.round(cs.bot), 1, h - 4);
  }

  let box, chips;
  function ready() {
    if (st.ready) return; st.ready = true; stage.hint(3, steps);
    const s = section(work, 'Решение: что испытать?', `<p class="mut">Осталось испытаний: <b class="left">${p.tests}</b>. Выберите интервал и посмотрите оценку.</p><div class="chips"></div><div class="box"></div>`);
    chips = s.querySelector('.chips'); box = s.querySelector('.box');
    cs.layers.filter(l => l.n).forEach(l => { const b = $(`<button class="chip">${l.n}</button>`); b.onclick = () => select(l); l.n && chips.appendChild(b); });
    const fin = $('<button class="main">Завершить и вскрыть породу</button>'); fin.onclick = finish; s.appendChild(fin); st.fin = fin;
    select(cs.layers.find(l => l.n));
    if (!stage.noScroll) s.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }
  function select(l, keep) {
    if (!st.ready) return;
    const same = st.sel === l; st.sel = l; chips.querySelectorAll('.chip').forEach(b => b.classList.toggle('on', +b.textContent === l.n));
    if (!keep) { setZ((l.top + l.bot) / 2); follow(st.z); }
    draw(); if (same && keep) return;
    const e = est.get(l.n), t = st.tested[l.n];
    const th = e.alpha === null ? null : M.thresholds(p.table, e.alpha);
    const out = e.alpha !== null && e.alpha < p.table[p.table.length - 1].alpha - .03;
    box.innerHTML = `<div class="kv">
      <div><span>ρ пласта</span><b>${fmt(e.rho)} Ом·м</b></div><div><span>Пористость</span><b>${fmt(e.kp * 100, 0)} %</b></div>
      <div><span>αсп</span><b>${e.alpha === null ? 'не определить' : fmt(e.alpha, 2)}</b></div>
      <div><span>ρ, если бы вода</span><b>${fmt(e.vp)} Ом·м</b></div></div>
      <p class="pn">Pн = ${fmt(e.rho)} / ${fmt(e.vp)} ≈ <b>${fmt(e.lo)}–${fmt(e.hi)}</b></p>
      <div class="scale"></div>
      <p class="mut">${out ? 'αсп ниже 0,7: таблица автора на такие породы не распространяется. Коллектор ли это вообще?' : th ? `Пороги для этой глинистости: нефть выше ${fmt(th.oil)}, вода ниже ${fmt(th.water)}.` : 'ПС плоская, αсп нет. Порог нефти может быть от 2,1 до 10 — посмотрите на ГК.'}</p>`;
    box.querySelector('.scale').appendChild(scale(e, th, out));
    if (t) box.appendChild($(`<p class="res" style="border-color:${RES[t][1]}"><b>${RES[t][0]}</b> — ${reason(l, t)}</p>`));
    else if (!st.done && Object.keys(st.tested).length < p.tests) {
      const b = $(`<button class="main alt">Испытать интервал ${l.n}</button>`);
      b.onclick = () => { st.tested[l.n] = M.testResult(spec, l); work.querySelector('.left').textContent = p.tests - Object.keys(st.tested).length; st.sel = null; select(l); };
      box.appendChild(b);
    }
  }
  function scale(e, th, out) {
    const c = canvas(54); requestAnimationFrame(() => {
      const [g, w] = c.fit(), X = v => 6 + Math.log(clamp(v, .5, 40) / .5) / Math.log(80) * (w - 12);
      if (th && !out) [[.5, th.water, LEG.water], [th.water, th.oil, LEG.unc], [th.oil, 40, LEG.oil]].forEach(([a, b, col]) => { g.fillStyle = col; g.fillRect(X(a), 12, X(b) - X(a), 16); });
      else { g.fillStyle = '#3a4550'; g.fillRect(X(.5), 12, X(40) - X(.5), 16); }
      g.fillStyle = LEG.text; g.fillRect(X(e.lo), 6, Math.max(3, X(e.hi) - X(e.lo)), 4); g.beginPath(); g.moveTo(X(e.Pn) - 5, 4); g.lineTo(X(e.Pn) + 5, 4); g.lineTo(X(e.Pn), 12); g.fill();
      g.fillStyle = LEG.muted; g.font = '11px Segoe UI'; g.textAlign = 'center'; [1, 2, 5, 10, 20].forEach(v => g.fillText(v, X(v), 44));
    }); return c;
  }
  function reason(l, t) {
    if (l.kind === 'dense') return `плотная порода. Сопротивление высокое, потому что пор ${fmt(l.kp * 100, 0)} %, а не из-за нефти.`;
    if (l.kind === 'oilclay') return `глинистый песчаник: сопротивление всего ${fmt(l.rho, 0)} Ом·м, но Pн ${fmt(l.Pn)} выше порога для его αсп.`;
    if (t === 'oil') return `чистый песчаник, Pн ${fmt(l.Pn)}.`;
    if (t === 'water') return `Pн ${fmt(l.Pn)}: сопротивление почти как с водой.`;
    return `Pн ${fmt(l.Pn)} попал между порогами.`;
  }
  function finish() {
    if (st.done) return; st.done = true; st.fin.remove(); stage.hint(4, steps);
    const all = cs.layers.filter(l => l.n), oil = all.filter(l => M.testResult(spec, l) === 'oil'), got = oil.filter(l => st.tested[l.n]);
    const bad = Object.entries(st.tested).filter(([, t]) => t === 'dry' || t === 'water');
    const miss = oil.filter(l => !st.tested[l.n]);
    stage.view(mob ? [40, 0, 48] : [32, -H / 2 + 12, 40], [0, -H / 2 + 2, 0], 2);
    section(tail, 'Итог', `<div class="score"><div><b>${got.length} из ${oil.length}</b><span>нефтяных пластов найдено</span></div><div><b>${bad.length}</b><span>испытаний впустую</span></div></div>
      ${miss.map(l => `<p class="why"><b>Пропущен ${l.n}.</b> ${reason(l, 'oil')}</p>`).join('')}${bad.map(([n, t]) => `<p class="why"><b>Зря испытан ${n}.</b> ${reason(all.find(l => l.n === +n), t)}</p>`).join('')}
      <p class="leg">${[['sand', 'песчаник'], ['shale', 'глина'], ['dense', 'плотная порода'], ['oil', 'нефть'], ['water', 'вода'], ['filtrate', 'фильтрат раствора']].map(([k, n]) => `<span><i style="background:${LEG[k]}"></i>${n}</span>`).join('')}</p>`);
    verdict(tail, spec.prediction, st.pick);
    closing(tail, spec);
    st.sel && select(st.sel, true); tail.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
  return { st, cs, setZ, ready, finish, select, draw, skip() { st.pick = 0; st.started = true; go.hidden = true; logSec.hidden = false; setZ(cs.bot); ready(); draw(); } };
}
