/* Слепая скважина: планшет из настоящих кривых, ответы с уверенностью, роботы с порогом. */
(() => {
  const core = window.LabCore;
  const PX_PER_M = 7;
  const HEAD = 54;
  const DEPTH = 52;
  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const ru = (n, digits = 1) => (n === null || n === undefined ? '—' : Number(n).toLocaleString('ru-RU', { maximumFractionDigits: digits }));

  const metres = (z) => String(z).replace('.', ',');

  const position = (c, value) => {
    const f = c.log ? Math.log : (x) => x;
    const t = (f(Math.max(value, c.log ? 1e-3 : -1e9)) - f(c.min)) / (f(c.max) - f(c.min));
    return Math.min(1, Math.max(0, t));
  };

  /** Глубина растёт вниз; кривая рвётся там, где отсчёта нет. Выход за шкалу прижимается к краю, это сказано под планшетом. */
  const log = (practice, well, state) => {
    const tracks = practice.curves;
    const narrow = matchMedia('(max-width: 600px)').matches;
    const width = narrow ? 76 : 120;
    const [big, small] = narrow ? [13, 11] : [14, 12];
    const total = DEPTH + tracks.length * width;
    const top = well.depth[0];
    const y = (z) => 8 + (z - top) * PX_PER_M;
    const height = y(well.depth[well.depth.length - 1]) + 12;
    const path = (c, k) => {
      let pen = 'M';
      let d = '';
      well.curves[c.id].forEach((v, i) => {
        if (v === null) { pen = 'M'; return; }
        d += `${pen}${(DEPTH + k * width + 4 + position(c, v) * (width - 8)).toFixed(1)},${y(well.depth[i]).toFixed(1)}`;
        pen = 'L';
      });
      return `<path d="${d}" fill="none" stroke="${c.color}" stroke-width="1.6"/>`;
    };
    const head = (c, k) => {
      const x = DEPTH + k * width;
      return `<rect x="${x + 1}" y="1" width="${width - 2}" height="${HEAD - 6}" rx="6" fill="#1A2129"/>
        <text x="${x + width / 2}" y="20" text-anchor="middle" fill="${c.color}" font-size="${big}" font-weight="600">${esc(narrow ? c.short || c.name : c.name)}</text>
        <text x="${x + 4}" y="40" fill="#ECEFF4" font-size="${small}">${ru(c.min, 2)}</text><text x="${x + width - 4}" y="40" text-anchor="end" fill="#ECEFF4" font-size="${small}">${ru(c.max, 2)}</text>
        <text x="${x + width / 2}" y="40" text-anchor="middle" fill="#B8C2CC" font-size="${small}">${narrow ? "" : esc(c.unit)}</text>`;
    };
    const grid = [];
    for (let z = Math.ceil(top / 10) * 10; y(z) < height; z += 10) grid.push(`<line x1="${DEPTH}" x2="${total}" y1="${y(z)}" y2="${y(z)}" stroke="#2A333D"/><text x="${DEPTH - 6}" y="${y(z) + 4}" text-anchor="end" fill="#B8C2CC" font-size="12">${z}</text>`);
    const bands = well.intervals.map((i) => {
      const answer = state.answers[i.id];
      const cls = practice.classes.find((c) => c.id === (state.revealed ? i.truth : answer && answer.choice));
      const on = state.current === i.id;
      return `<g data-interval="${i.id}" style="cursor:pointer"><rect x="${DEPTH}" y="${y(i.top)}" width="${total - DEPTH}" height="${(i.base - i.top) * PX_PER_M}" fill="${cls ? cls.color : '#F1C40F'}" fill-opacity="${on ? 0.36 : 0.2}" stroke="${on ? '#ffffff' : 'none'}" stroke-width="2"/>
        <text x="${DEPTH + 6}" y="${y((i.top + i.base) / 2) + 5}" fill="#ffffff" font-size="15" font-weight="700" paint-order="stroke" stroke="#0F1419" stroke-width="4">${esc(state.numbers[i.id])}</text></g>`;
    });
    // шапка — отдельный рисунок: она остаётся на месте, пока планшет прокручивается
    return `<svg class="log-head" viewBox="0 0 ${total} ${HEAD}" width="${total}" height="${HEAD}" aria-hidden="true"><rect width="${total}" height="${HEAD}" fill="#0F1419"/>${tracks.map(head).join('')}
      <text x="${DEPTH - 6}" y="20" text-anchor="end" fill="#B8C2CC" font-size="${small}">глуб.</text><text x="${DEPTH - 6}" y="36" text-anchor="end" fill="#B8C2CC" font-size="${small}">м</text></svg>
      <svg class="log-body" viewBox="0 0 ${total} ${height}" width="${total}" height="${height}" role="img" aria-label="Каротаж: ${esc(well.name)}, глубина ${top}–${well.depth[well.depth.length - 1]} м">
      <rect width="${total}" height="${height}" fill="#0F1419"/>${grid.join('')}${bands.join('')}${tracks.map(path).join('')}</svg>`;
  };

  const readings = (practice, interval) => `<dl class="readings">${practice.curves.map((c) => `<div><dt><i style="background:${c.color}"></i>${esc(c.name)}</dt><dd>${ru(interval.medians[c.id], 2)} ${esc(c.unit)}</dd></div>`).join('')}</dl>`;

  const question = (practice, interval, state, draft) => {
    const choice = (c) => `<label class="choice"><input type="radio" name="class" value="${c.id}" ${draft.choice === c.id ? 'checked' : ''}><i style="background:${c.color}"></i>${esc(c.name)}</label>`;
    const sure = (p) => `<label class="choice sure"><input type="radio" name="sure" value="${p}" ${draft.confidence === p ? 'checked' : ''}>${p} %</label>`;
    return `<h2 tabindex="-1">Интервал ${esc(state.numbers[interval.id])}: ${metres(interval.top)}–${metres(interval.base)} м</h2>
      <p class="muted">Медианы по интервалу. Форму смотрите на планшете.</p>${readings(practice, interval)}
      <fieldset><legend>Что это?</legend><div class="choices">${practice.classes.map(choice).join('')}</div></fieldset>
      <fieldset><legend>Насколько уверены?</legend><div class="choices row">${practice.confidence.map(sure).join('')}</div></fieldset>
      <p class="muted">Уверенная ошибка стоит дороже, чем честное «не уверен».</p>
      <button class="btn main" data-answer ${draft.choice && draft.confidence ? '' : 'disabled'}>${state.answers[interval.id] ? 'Изменить ответ' : 'Ответить'}</button>`;
  };

  const robotCard = (practice, robot, threshold) => {
    const score = core.robotScore(practice, robot, threshold);
    const best = core.bestThreshold(practice, robot);
    const marks = core.intervalsOf(practice).filter((i) => core.isScored(practice, i)).map((i) => {
      const said = core.robotAnswer(robot, i, threshold);
      const ok = said === i.truth;
      const name = (id) => practice.classes.find((c) => c.id === id).name.toLowerCase();
      return `<li class="${ok ? 'ok' : 'no'}"><b>${ok ? '✓' : '✗'}</b><span>${i.label}: ${name(said)}${ok ? '' : `, а это ${name(i.truth)}`}</span></li>`;
    }).join('');
    return `<section class="card"><h3>${esc(robot.name)}</h3><p>${esc(robot.rule)}</p>
      <label class="slider">Порог ${robot.param === 'pn' ? 'Pн' : 'сопротивления, Ом·м'}: <output>${ru(threshold, 1)}</output>
        <input type="range" min="0" max="200" value="${Math.round(200 * Math.log(threshold / robot.min) / Math.log(robot.max / robot.min))}" data-robot="${robot.id}"></label>
      <p class="score"><strong>${score.right} из ${score.total}</strong> <span class="muted">лучшее, что даёт любой порог: ${best.right} из ${best.total}</span></p>
      <details><summary>Ответы по интервалам</summary><ul class="marks">${marks}</ul></details>${robot.note ? `<p class="muted">${esc(robot.note)}</p>` : ''}</section>`;
  };

  const verdictRow = (practice, i, state) => {
    const answer = state.answers[i.id];
    const scored = core.isScored(practice, i);
    const right = answer.choice === i.truth;
    const name = (id) => (practice.classes.find((c) => c.id === id) || { name: (practice.truth_names || {})[id] || id }).name;
    return `<li class="card ${scored ? (right ? 'ok' : 'no') : ''}"><h3>${i.label}: ${esc(name(i.truth))}</h3>
      <p>Ваш ответ: ${esc(name(answer.choice).toLowerCase())}, уверенность ${answer.confidence} %.${scored ? ` ${right ? 'Верно' : 'Неверно'}, ${core.points(right, answer.confidence)} баллов.` : ''}</p>
      <p>${esc(practice.reasons[i.id] || '')}</p>${scored ? '' : `<p>${esc(practice.unscored[i.truth])}</p>`}
      <p class="muted num">Оператор: VSH ${ru(i.medians.VSH, 2)}, PHIF ${ru(i.medians.PHIF, 2)}, SW ${ru(i.medians.SW, 2)}. Наш расчёт: kп ${ru(i.porosity_density, 2)}, Pн ${i.pn === null ? 'не считается, пор нет' : ru(i.pn, 1)}.</p></li>`;
  };

  const mount = (root, practice, course, store) => {
    const numbers = {};
    practice.wells.forEach((w, k) => w.intervals.forEach((i, n) => { numbers[i.id] = `${k + 1}${'абвгдежз'[n]}`; i.label = numbers[i.id]; }));
    const all = core.intervalsOf(practice);
    const saved = store.get('well', { answers: {}, revealed: false });
    const known = new Set(all.map((i) => i.id));
    const state = { numbers, answers: Object.fromEntries(Object.entries(saved.answers || {}).filter(([k]) => known.has(k))), revealed: Boolean(saved.revealed), current: null };
    if (Object.keys(state.answers).length < all.length) state.revealed = false;
    state.current = (all.find((i) => !state.answers[i.id]) || all[0]).id;
    const thresholds = Object.fromEntries(practice.robots.map((r) => [r.id, r.threshold]));
    let draft = {};
    const keep = () => store.set('well', { answers: state.answers, revealed: state.revealed });
    const wellOf = (id) => practice.wells.find((w) => w.intervals.some((i) => i.id === id));

    const results = () => {
      const s = core.summary(practice, state.answers);
      const gap = s.confidence - s.accuracy;
      const steps = (practice.steps || []).map((id) => course.steps.find((x) => x.id === id)).filter(Boolean);
      return `<section class="results"><h2 tabindex="-1">Результат: ${s.right} из ${s.total}, ${s.points} баллов из 100</h2>
        <p>Средняя уверенность ${s.confidence} %, верных ответов ${s.accuracy} %. ${gap > 12 ? 'Вы увереннее, чем точны: так же ошибается модель с высокой вероятностью класса.' : gap < -12 ? 'Вы точнее, чем думаете.' : 'Уверенность близка к точности.'}</p>
        <h2>Что показало заключение</h2><p class="muted">${esc(practice.truth_note)}</p>
        <ul class="verdicts">${all.map((i) => verdictRow(practice, i, state)).join('')}</ul>
        <h2>Сможет ли правило заменить вас</h2><div class="robots">${practice.robots.map((r) => robotCard(practice, r, thresholds[r.id])).join('')}</div>
        <p class="lesson">${esc(practice.data_lesson)}</p>
        ${steps.length ? `<p>Разобрать в курсе: ${steps.map((x) => `<a href="index.html#/step/${x.order}">шаг ${x.order}, ${esc(x.short_title)}</a>`).join('; ')}.</p>` : ''}
        <button class="btn" data-reset>Пройти заново</button></section>`;
    };

    const render = (focus) => {
      const well = wellOf(state.current);
      const interval = well.intervals.find((i) => i.id === state.current);
      const done = Object.keys(state.answers).length;
      if (!draft.id || draft.id !== interval.id) draft = { id: interval.id, ...(state.answers[interval.id] || {}) };
      const scroll = root.querySelector('.log') ? root.querySelector('.log').scrollTop : null;
      const sameWell = root.dataset.shown === well.id;
      root.dataset.shown = well.id;
      root.innerHTML = `<div class="intro"><p class="badge">${esc(practice.label)}</p><h1>${esc(practice.title)}</h1><p>${esc(practice.lead)}</p></div>
        <div class="wells" role="group" aria-label="Скважина">${practice.wells.map((w) => `<button class="btn ${w.id === well.id ? 'on' : ''}" aria-pressed="${w.id === well.id}" data-well="${w.id}">${esc(w.name)}${state.revealed ? ` (${esc(w.real_name)})` : ''}</button>`).join('')}<span class="muted">Отвечено ${done} из ${all.length}</span></div>
        <div class="bench"><div class="log" tabindex="0" role="region" aria-label="Планшет, прокручивается вниз">${log(practice, well, state)}</div>
        <div class="side"><div class="dots" role="group" aria-label="Интервалы">${well.intervals.map((i) => `<button data-go="${i.id}" aria-pressed="${i.id === state.current}" class="dot ${i.id === state.current ? 'on' : ''} ${state.answers[i.id] ? 'done' : ''}">${numbers[i.id]}</button>`).join('')}</div>
        ${state.revealed ? `<p>Ответы открыты. Интервалы окрашены по заключению оператора.</p>${readings(practice, interval)}` : question(practice, interval, state, draft)}
        ${!state.revealed && done === all.length ? '<button class="btn main" data-reveal>Открыть заключение</button>' : ''}
        <details><summary>Как читать кривые</summary><ul>${practice.curves.map((c) => `<li><b>${esc(c.name)}.</b> ${esc(c.hint)}</li>`).join('')}</ul></details>
        <p class="muted">${esc(practice.source)} Значения за пределами шкалы прижаты к её краю. Названия скважин скрыты до ответа.</p></div></div>
        ${state.revealed ? results() : ''}`;
      const box = root.querySelector('.log');
      const y = 8 + ((interval.top + interval.base) / 2 - well.depth[0]) * PX_PER_M;
      const body = box.querySelector('.log-body');
      const scale = body.getBoundingClientRect().height / body.viewBox.baseVal.height;
      if (sameWell && scroll !== null && focus === 'stay') box.scrollTop = scroll;
      else box.scrollTop = Math.max(0, y * scale - box.clientHeight / 3);
      if (focus === 'question') root.querySelector('.side h2')?.focus({ preventScroll: true });
      if (focus === 'results') { const h = root.querySelector('.results h2'); h.focus({ preventScroll: true }); h.scrollIntoView(); }
    };

    root.onclick = (e) => {
      const at = (name) => e.target.closest(`[data-${name}]`)?.dataset[name];
      if (at('well')) { state.current = practice.wells.find((w) => w.id === at('well')).intervals[0].id; render('question'); }
      else if (at('go')) { state.current = at('go'); render('question'); }
      else if (at('interval')) { state.current = at('interval'); render('question'); }
      else if (at('answer') !== undefined) {
        state.answers = { ...state.answers, [state.current]: { choice: draft.choice, confidence: draft.confidence } };
        const next = all.find((i) => !state.answers[i.id]);
        if (next) state.current = next.id;
        keep();
        render('question');
      } else if (at('reveal') !== undefined) { state.revealed = true; keep(); render('results'); }
      else if (at('reset') !== undefined) { state.answers = {}; state.revealed = false; state.current = all[0].id; draft = {}; keep(); render('question'); window.scrollTo(0, 0); }
    };
    root.onchange = (e) => {
      if (e.target.name === 'class') draft = { ...draft, choice: e.target.value };
      if (e.target.name === 'sure') draft = { ...draft, confidence: Number(e.target.value) };
      const button = root.querySelector('[data-answer]');
      if (button) button.disabled = !(draft.choice && draft.confidence);
    };
    root.oninput = (e) => {
      const id = e.target.dataset.robot;
      if (!id) return;
      const robot = practice.robots.find((r) => r.id === id);
      thresholds[id] = robot.min * (robot.max / robot.min) ** (Number(e.target.value) / 200);
      const open = e.target.closest('.card').querySelector('details').open;
      const card = document.createElement('div');
      card.innerHTML = robotCard(practice, robot, thresholds[id]);
      const fresh = card.firstElementChild;
      fresh.querySelector('details').open = open;
      // ползунок остаётся тем же узлом: иначе перетаскивание оборвётся
      const old = e.target.closest('.card');
      ['output', '.score', '.marks'].forEach((s) => old.querySelector(s).replaceWith(fresh.querySelector(s)));
    };
    render();
  };

  window.LabWell = { mount, esc, ru };
})();
