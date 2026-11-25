import DATA from 'scenes';
import { Stage } from './core.js';
import { resolve } from './extends.js';
import { validate } from './validate.js';
import * as log_decision from './templates/log_decision.js';
import * as pressure_field from './templates/pressure_field.js';
import * as body_explore from './templates/body_explore.js';
import * as compose from './templates/compose.js';
import { $ } from './ui.js';

import t1 from '../tex/thumb_1_log_fresh.webp';
import t2 from '../tex/thumb_2_log_salty.webp';
import t3 from '../tex/thumb_3_pressure.webp';
import t4 from '../tex/thumb_4_reef_dome.webp';
import t5 from '../tex/thumb_5_reef_atoll.webp';

const RAW = DATA.scenes;
const THUMB = { ...DATA.thumbs,  '1_log_fresh': t1, '2_log_salty': t2, '3_pressure': t3, '4_reef_dome': t4, '5_reef_atoll': t5 };
const TPL = { log_decision, pressure_field, body_explore, compose };
const SC = Object.fromEntries(Object.keys(RAW).map(k => [k, resolve(RAW, k)]));
const q = s => document.querySelector(s);
let stage, cur, spec, seed;
try { stage = new Stage(q('#view')); } catch (e) { q('#view').innerHTML = '<p class="fail">Браузер не смог открыть 3D (нужен WebGL 2).</p>'; throw e; }

const sel = q('#scene');
Object.entries(SC).forEach(([k, s]) => sel.appendChild($(`<option value="${k}">${s.title}</option>`)));

function load(s, sd) {
  const err = validate(s, [sd]);
  if (err.length) return err;
  spec = s; seed = sd;
  stage.reset();
  stage.renderer.domElement.onpointerdown = null;
  const panel = q('#panel'); panel.innerHTML = ''; panel.scrollTop = 0;
  q('#sub').textContent = s.subtitle || ''; q('#prov').textContent = s.provenance; q('#case').textContent = 'случай № ' + sd;
  q('#all').hidden = false; cur = TPL[s.template].build(stage, s, sd, panel);
  return [];
}
sel.onchange = () => { location.hash = sel.value; };
const home = q('#home');
home.querySelector('.cards').append(...Object.entries(SC).map(([k, s]) => $(`<a class="card" href="#${k}">${THUMB[k] ? `<img src="${THUMB[k]}" alt="">` : ''}<b>${s.title}</b><span>${s.goal || s.intro}</span><small>${s.template === 'compose' ? 'Собрал агент. ' : ''}${s.subtitle || ''}</small></a>`)));
q('#all').onclick = () => { location.hash = ''; };
const EMBED = document.body.classList.contains('embed');
const fromHash = () => { const k = decodeURIComponent(location.hash.slice(1)); home.hidden = EMBED || !!SC[k]; const n = SC[k] ? k : Object.keys(SC)[0]; sel.value = n; load(SC[n], SC[n].seed); };
addEventListener('hashchange', fromHash);
q('#next').onclick = () => load(spec, 1 + Math.floor(Math.random() * 9000));

// --- живая спецификация: правка → проверка физики → пересборка сцены
const dlg = q('#spec'), ta = q('#json'), msg = q('#msg');
q('#edit').onclick = () => { ta.value = JSON.stringify(spec, null, 1); msg.textContent = ''; dlg.showModal(); };
q('#apply').onclick = () => {
  let s; try { s = JSON.parse(ta.value); } catch (e) { msg.className = 'bad'; msg.textContent = 'Ошибка в JSON: ' + e.message; return; }
  const err = load(s, s.seed);
  msg.className = err.length ? 'bad' : ''; msg.textContent = err.length ? 'Сцена не собрана. ' + err.join('; ') : '';
  if (!err.length) dlg.close();
};
q('#close').onclick = () => dlg.close();

fromHash();
window.__t = { get cur() { return cur; }, get stage() { return stage; }, load, SC, validate };
