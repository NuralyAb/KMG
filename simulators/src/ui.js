// Общие кирпичики панели: вопрос, источники, график, ползунок.
export const $ = (h) => { const t = document.createElement('template'); t.innerHTML = h.trim(); return t.content.firstElementChild; };
export const fmt = (x, d = 1) => Number(x).toFixed(d).replace('.', ',');
export function section(root, title, html = '') { const s = $(`<section><h2>${title}</h2>${html}</section>`); root.appendChild(s); return s; }

export function question(root, title, q, done) {
  const s = section(root, title, `<p class="q">${q.q}</p><div class="opts"></div>`);
  q.options.forEach((o, i) => {
    const b = $(`<button class="opt">${o}</button>`);
    b.onclick = () => {
      if (s.dataset.done) return; s.dataset.done = 1;
      s.querySelectorAll('.opt').forEach((x, j) => { x.disabled = true; if (j === q.answer) x.classList.add('ok'); else if (j === i) x.classList.add('no'); });
      s.appendChild($(`<p class="why"><b>${i === q.answer ? 'Верно.' : 'Не так.'}</b> ${q.why}</p>`));
      done && done(i === q.answer);
    };
    s.querySelector('.opts').appendChild(b);
  });
  return s;
}
export function prediction(root, q, done) {
  // Ответ не раскрывается: ученик увидит его на опыте.
  const s = section(root, 'Сначала предположите', `<p class="q">${q.q}</p><div class="opts"></div>`);
  q.options.forEach((o, i) => {
    const b = $(`<button class="opt">${o}</button>`);
    b.onclick = () => { s.querySelectorAll('.opt').forEach(x => (x.disabled = true)); b.classList.add('sel'); done(i); };
    s.querySelector('.opts').appendChild(b);
  });
  return s;
}
export function verdict(root, q, pick) {
  const ok = pick === q.answer;
  return section(root, 'Ваше предположение', `<p class="q">${q.q}</p><p class="why"><b>${ok ? 'Сбылось.' : 'Не сбылось.'}</b> ${q.why}</p>`);
}
export function closing(root, spec) {
  question(root, 'Проверьте перенос', spec.transfer);
  section(root, 'Что это значит для данных', `<p>${spec.data_bridge}</p>${spec.analogy ? `<p><b>Аналогия.</b> ${spec.analogy.text} <span class="mut">Где ломается: ${spec.analogy.breaks_where}</span></p>` : ''}`);
}
export function honesty(root, spec) {
  root.appendChild($(`<details class="hon"><summary>Откуда это и что упрощено</summary>
   <h3>Источники</h3><ul>${spec.sources.map(s => `<li>${s.claim} <span class="pg">стр. ${s.page}</span></li>`).join('')}</ul>
   <h3>Допущения модели</h3><ul>${spec.assumptions.map(a => `<li>${a}</li>`).join('')}</ul>
   <h3>Преувеличено на картинке</h3><ul>${spec.exaggerations.map(a => `<li>${a}</li>`).join('')}</ul>
   <p class="mut">Движение, кривые и итог вычислены из одной модели. Фактура пород — фото CC0 (Poly Haven), это не керн.</p></details>`));
}
export function slider(label, min, max, step, val, on, show = v => fmt(v, 2)) {
  const e = $(`<label class="sl"><span><span>${label}</span><b></b></span><input type="range" min="${min}" max="${max}" step="${step}" value="${val}"></label>`);
  const i = e.querySelector('input'), b = e.querySelector('b');
  const f = () => { b.textContent = show(+i.value); on(+i.value); };
  i.oninput = f; b.textContent = show(+val); e.set = v => { i.value = v; b.textContent = show(+v); };
  return e;
}
export function canvas(h) {
  const c = $(`<canvas style="height:${h}px"></canvas>`);
  c.fit = () => { const d = Math.min(2, devicePixelRatio), w = c.clientWidth || 360; if (c.width !== Math.round(w * d)) { c.width = Math.round(w * d); c.height = h * d; } const g = c.getContext('2d'); g.setTransform(d, 0, 0, d, 0, 0); g.clearRect(0, 0, w, h); return [g, w, h]; };
  return c;
}
export function timeText(s) {
  if (s < 90) return fmt(s, 0) + ' с'; if (s < 5400) return fmt(s / 60, 0) + ' мин'; if (s < 172800) return fmt(s / 3600, 1) + ' ч'; return fmt(s / 86400, 1) + ' сут';
}
