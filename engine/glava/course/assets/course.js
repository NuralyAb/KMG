/* Курс целиком строится из window.COURSE (data.js). Без сервера, без сети. */
(() => {
  'use strict';
  const C = window.COURSE;
  const app = document.getElementById('app');
  const KEY = `glava.${C.id}`;
  const KIND = { observation: 'наблюдение', inference: 'вывод', assumption: 'допущение' };

  // ---------- состояние в браузере ----------
  const load = () => { try { return JSON.parse(localStorage.getItem(KEY)) || {}; } catch { return {}; } };
  let state = { done: [], solved: {}, cards: {}, last: null, theme: 'auto', ...load() };
  const set = (patch) => { state = { ...state, ...patch }; try { localStorage.setItem(KEY, JSON.stringify(state)); } catch { /* приватное окно */ } };
  const applyTheme = () => { document.documentElement.dataset.theme = state.theme; };

  // ---------- текст: экранирование и формулы ----------
  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const tex = (code, display) => { try { return katex.renderToString(code, { displayMode: display, throwOnError: false, strict: 'ignore' }); } catch { return esc(code); } };
  const rich = (s) => String(s ?? '').split(/(\$\$[\s\S]+?\$\$|\\\[[\s\S]+?\\\]|\$[^$\n]+?\$|\\\([\s\S]+?\\\))/).map((part) => {
    if (/^(\$\$|\\\[)/.test(part)) return tex(part.slice(2, -2), true);
    if (/^\\\(/.test(part)) return tex(part.slice(2, -2), false);
    if (/^\$/.test(part)) return tex(part.slice(1, -1), false);
    return esc(part);
  }).join('');
  const pages = (list) => (list?.length ? ` <span class="page">стр. ${list.join(', ')}</span>` : '');
  const block = (title, body, id = '') => (body ? `<section class="block"${id ? ` id="${id}"` : ''}><h2>${title}</h2>${body}</section>` : '');
  const stepUrl = (s) => `#/step/${s.order}`;
  const stepById = (id) => C.steps.find((s) => s.id === id);

  // ---------- страница шага ----------
  const picture = (p) => `<figure>${p.svg || `<img src="${esc(p.file)}" alt="${esc(p.alt)}" loading="lazy">`}<figcaption>${rich(p.caption)} <span class="chip">${esc(p.label)}</span>${p.source ? ` ${esc(p.source)}` : ''}</figcaption></figure>`;
  const how = (s) => s.how.map((b) => `<h3>${b.title}</h3>${b.paragraphs.map((p) => `<p>${rich(p.text)}${pages(p.pages)}</p>`).join('')}`).join('') + '<p class="by">Изложено моделью по утверждениям автора, они перечислены ниже с цитатами.</p>';
  const claims = (s) => `<ul class="claims">${s.claims.map((c) => `<li>${rich(c.text)}${pages([c.page_pdf])} <span class="chip">${KIND[c.kind]}</span>${c.source_kind === 'figure_description_model' ? ' <span class="chip">описание рисунка моделью</span>' : ''}<details><summary>Цитата автора</summary><blockquote>${rich(c.quote)}</blockquote></details></li>`).join('')}</ul>`;
  const example = (e) => `<div class="card"><p><strong>Условие.</strong> ${rich(e.condition)}</p><ol>${e.steps.map((x) => `<li>${rich(x)}</li>`).join('')}</ol><p><strong>Итог.</strong> ${rich(e.result)}${pages([e.page_pdf])}</p>${e.figure ? `<p class="muted">Нужен рисунок: ${esc(e.figure)}</p>` : ''}</div>`;
  const bookTask = (t) => `<div class="card"><p><strong>Задача ${esc(t.number)}.</strong> ${rich(t.text)}${pages([t.page_pdf])}</p>${t.figure ? `<p class="muted">Нужен рисунок: ${esc(t.figure)}</p>` : ''}</div>`;
  const dataBlock = (s) => { const d = s.data_meaning; return `<p>${rich(d.from_chapter.text)}</p><p><strong>Где ломается.</strong> ${rich(d.breaks.text)}</p>${d.hypotheses.map((h) => `<div class="note warn"><strong>Гипотеза, не из главы</strong><p>${rich(h.text)}</p></div>`).join('')}`; };
  const lens = (l) => (l ? `<dl><div><dt>Входные данные</dt><dd>${rich(l.inputs)}</dd></div><div><dt>Ручные шаги</dt><dd>${rich(l.manual_steps)}</dd></div><div><dt>Точки суждения</dt><dd>${rich(l.judgment_points)}</dd></div><div><dt>Время</dt><dd>${rich(l.time)}</dd></div><div><dt>Типичные ошибки</dt><dd>${rich(l.typical_errors)}</dd></div></dl>` : '');
  const decision = (d) => (d ? `<ol>${d.features.map((f) => `<li>${rich(f)}</li>`).join('')}</ol><p><strong>Правило.</strong> ${rich(d.rule)}</p><p><strong>Вывод.</strong> ${rich(d.conclusion)}</p>${d.counterexample ? `<div class="note warn"><strong>Контрпример</strong><p>${rich(d.counterexample)}</p></div>` : ''}` : '');

  const stepPage = (s) => {
    const i = C.steps.indexOf(s);
    const [prev, next] = [C.steps[i - 1], C.steps[i + 1]];
    set({ last: s.order });
    return `<article class="column">
      <header class="block"><p class="muted">Шаг ${s.order} из ${C.steps.length} · ${s.minutes} мин${s.threshold ? ' · пороговая идея' : ''}</p><h1 tabindex="-1">${esc(s.short_title || s.title)}</h1><p class="muted">В книге: ${esc(s.title)}${pages(s.pages)}</p></header>
      <p class="lead">${rich(s.essence)}${pages(s.pages)}</p>
      ${s.pictures.map(picture).join('')}
      ${block('Как это работает', how(s), 'how')}
      ${block('Решение на данных', decision(s.decision_on_data))}
      ${block('Разбор примеров из главы', s.worked_examples?.map(example).join(''))}
      ${block('Все мысли автора', claims(s), 'claims')}
      ${block('Глубже', s.deeper.map((d) => `<p>${rich(d.text)}${pages(d.pages)}</p>`).join(''))}
      ${block('Новые понятия', s.glossary.length ? `<dl>${s.glossary.map((g) => `<div><dt>${rich(g.term)}</dt><dd>${rich(g.definition)}</dd></div>`).join('')}</dl>` : '')}
      ${s.misconception ? `<section class="note bad"><h2>Частая ошибка</h2><p>${rich(s.misconception.text)}</p></section>` : ''}
      ${block('Что это значит для данных', dataBlock(s), 'data')}
      <section class="note brand"><h2>Аналогия из ИТ</h2><p>${rich(s.it_analogy.text)}</p><p><strong>Где перестаёт работать.</strong> ${rich(s.it_analogy.breaks_where)}</p></section>
      ${block('Ручной труд специалиста', lens(s.inefficiency_lens))}
      ${s.now_practice ? `<section class="note warn"><h2>Как это делают сейчас</h2><p>${rich(s.now_practice.text)}</p><p class="by">Написано моделью, не из книги.</p></section>` : ''}
      ${block('Задачи из книги', s.book_tasks?.map(bookTask).join(''))}
      ${s.tasks.length ? `<section class="block" id="tasks"><h2>Проверьте себя</h2>${s.tasks.map((t) => `<div class="card task" data-task="${esc(t.id)}"></div>`).join('')}</section>` : ''}
      <footer class="row noprint">${prev ? `<a class="btn" href="${stepUrl(prev)}">Назад</a>` : '<span></span>'}<button class="btn main" data-done="${esc(s.id)}">${next ? 'Понятно, дальше' : 'Завершить курс'}</button></footer>
      <p class="muted">Почему этот шаг здесь: ${rich(s.why_here.text)}</p>
    </article>`;
  };

  // ---------- задания ----------
  const norm = (v) => String(v ?? '').trim().toLowerCase().replace(/ё/g, 'е').replace(',', '.').replace(/\s+/g, ' ');
  const shuffled = (list, seed) => list.map((o, i) => [((i + 1) * 7919 + seed.length * 104729) % 1009, o]).sort((a, b) => a[0] - b[0]).map((x) => x[1]);

  function mountTask(root, task) {
    let picked = task.type === 'order' ? (task.options || []).map((o) => o.id) : [];
    let verdict = null;
    let shown = false;
    const options = shuffled(task.options || [], task.id);
    const values = () => [...root.querySelectorAll('input')].map((x) => x.value);
    const correct = () => {
      const a = task.answer;
      if (task.type === 'single') return picked[0] === a;
      if (task.type === 'multiple') return picked.length === a.length && a.every((x) => picked.includes(x));
      if (task.type === 'order') return picked.join() === a.join();
      if (task.type === 'gap') return a.every((x, i) => norm(values()[i]) === norm(x));
      return values()[0].trim() !== '' && Math.abs(Number(norm(values()[0])) - a) <= (task.tolerance || 0);
    };
    const answerText = () => {
      const label = (id) => rich(task.options.find((o) => o.id === id)?.text ?? id);
      if (task.type === 'single') return label(task.answer);
      if (task.type === 'multiple') return task.answer.map(label).join('; ');
      if (task.type === 'order') return task.answer.map(label).join(' → ');
      if (task.type === 'gap') return task.answer.map(esc).join('; ');
      return `${esc(task.answer)} ${esc(task.unit || '')}`;
    };
    const cls = (id) => {
      if (!shown) return picked.includes(id) ? ' on' : '';
      if ([].concat(task.answer).includes(id)) return ' right';
      return picked.includes(id) ? ' wrong' : '';
    };
    const lock = () => (shown ? 'disabled' : '');
    const body = () => {
      if (task.type === 'gap') return `<p>${rich(task.prompt).replace(/\{\{(\d+)\}\}/g, (_, n) => `<input class="gap-input" type="text" aria-label="Пропуск ${n}" ${lock()}>`)}</p>`;
      if (task.type === 'calc') return `<label>Ответ, ${esc(task.unit || '')}<br><input type="text" inputmode="decimal" ${lock()}></label>`;
      if (task.type === 'order') {
        return `<div class="options" role="group" aria-label="Порядок">${picked.map((id) => task.options.find((o) => o.id === id)).map((o, i) => `<div class="option drag" data-id="${esc(o.id)}"><span class="num">${i + 1}.</span><span>${rich(o.text)}</span><span class="move"><button data-move="-1" aria-label="Выше" ${lock()}>↑</button><button data-move="1" aria-label="Ниже" ${lock()}>↓</button></span></div>`).join('')}</div>`;
      }
      return `<div class="options" role="group" aria-label="Варианты">${options.map((o) => `<button class="option${cls(o.id)}" data-id="${esc(o.id)}" aria-pressed="${picked.includes(o.id)}" ${lock()}>${rich(o.text)}</button>`).join('')}</div>`;
    };
    const result = () => {
      const claim = C.steps.flatMap((s) => s.claims).find((c) => c.id === task.claim_ids[0]);
      return `<div class="verdict ${verdict ? 'good' : 'bad'}" role="status"><strong>${verdict ? 'Верно' : 'Пока нет'}</strong><p>Верный ответ: ${answerText()}</p><p>${rich(task.explanation)}${claim ? pages([claim.page_pdf]) : ''}</p></div><button class="btn" data-again>Ещё раз</button>`;
    };
    const draw = () => {
      root.innerHTML = `${task.type === 'gap' ? '' : `<h3>${rich(task.prompt)}</h3>`}${task.type === 'multiple' ? '<p class="muted">Несколько верных ответов</p>' : ''}${body()}${shown ? result() : '<button class="btn main" data-check>Проверить</button>'}`;
    };
    const check = () => {
      const typed = values();
      verdict = correct();
      shown = true;
      set({ solved: { ...state.solved, [task.id]: verdict } });
      draw();
      root.querySelectorAll('input').forEach((x, i) => { x.value = typed[i]; });
    };
    const move = (id, shift) => {
      const i = picked.indexOf(id);
      const j = i + shift;
      if (j < 0 || j >= picked.length) return;
      const next = [...picked];
      [next[i], next[j]] = [next[j], next[i]];
      picked = next;
      draw();
      root.querySelector(`[data-id="${CSS.escape(id)}"] [data-move="${shift}"]`)?.focus();
    };
    const choose = (id) => {
      if (task.type === 'single') picked = [id];
      else picked = picked.includes(id) ? picked.filter((x) => x !== id) : [...picked, id];
      draw();
      root.querySelector(`[data-id="${CSS.escape(id)}"]`)?.focus();
    };
    root.addEventListener('click', (e) => {
      const button = e.target.closest('button');
      if (!button) return;
      const id = button.closest('[data-id]')?.dataset.id;
      if ('check' in button.dataset) check();
      else if ('again' in button.dataset) { shown = false; picked = task.type === 'order' ? picked : []; draw(); }
      else if (button.dataset.move) move(id, Number(button.dataset.move));
      else if (id) choose(id);
    });
    root.addEventListener('pointerdown', (e) => {
      const item = e.target.closest('.drag');
      if (!item || shown || e.target.closest('button')) return;
      e.preventDefault();
      item.classList.add('lift');
      const drag = (ev) => {
        const over = document.elementFromPoint(ev.clientX, ev.clientY)?.closest('.drag');
        if (!over || over === item || !root.contains(over)) return;
        const box = over.getBoundingClientRect();
        over.parentNode.insertBefore(item, ev.clientY > box.top + box.height / 2 ? over.nextSibling : over);
      };
      const drop = () => {
        ['pointermove', 'pointerup', 'pointercancel'].forEach((n) => document.removeEventListener(n, n === 'pointermove' ? drag : drop));
        picked = [...root.querySelectorAll('.drag')].map((x) => x.dataset.id);
        draw();
      };
      document.addEventListener('pointermove', drag);
      document.addEventListener('pointerup', drop);
      document.addEventListener('pointercancel', drop);
    });
    draw();
  }

  // ---------- остальные разделы ----------
  const total = C.steps.reduce((a, s) => a + s.minutes, 0);
  const home = () => {
    const resume = C.steps.find((s) => s.order === state.last) || C.steps[0];
    return `<div class="column"><header class="block"><h1 tabindex="-1">${esc(C.title)}</h1><p class="muted">${esc(C.book)}</p></header>
      <p class="lead">Шагов: ${C.steps.length}, около ${total} минут, заданий: ${C.steps.reduce((a, s) => a + s.tasks.length, 0)}. Каждый абзац ведёт на страницу книги.</p>
      <div><a class="btn main" href="${stepUrl(resume)}">${state.last ? `Продолжить: шаг ${resume.order}` : 'Начать'}</a></div>
      ${C.parts.map((p) => block(esc(p.title), `<ol>${p.nodes.map(stepById).filter(Boolean).map((s) => `<li value="${s.order}"><a href="${stepUrl(s)}">${esc(s.short_title)}</a> <span class="muted">${s.minutes} мин</span></li>`).join('')}</ol>`)).join('')}
      <p class="muted">Учебный слой собран моделью ${esc(C.generated_by)}; цитаты и числа проверены кодом по страницам главы.</p></div>`;
  };
  const cards = () => {
    const fresh = C.steps.filter((s) => !state.cards[s.id]);
    const again = C.steps.filter((s) => state.cards[s.id] === 'again');
    const s = fresh[0] || again[0];
    if (!s) return '<div class="column"><h1 tabindex="-1">Карточки</h1><p class="lead">Все карточки отмечены «знаю».</p><div><button class="btn" data-cards-reset>Повторить все</button></div></div>';
    return `<div class="column"><h1 tabindex="-1">Карточки</h1><p class="muted">Осталось ${fresh.length + again.length} из ${C.steps.length}, из них на повтор: ${again.length}</p>
      <button class="flash" data-flip><h2>${esc(s.short_title)}</h2><p class="muted">Вспомните суть и нажмите</p></button>
      <div class="row" hidden data-rate="${esc(s.id)}"><button class="btn" data-know="again">Повторить</button><button class="btn main" data-know="know">Знаю</button></div></div>`;
  };
  const summary = () => `<div class="column"><div class="row"><h1 tabindex="-1">Конспект</h1><button class="btn noprint" data-print>Печать в PDF</button></div>${C.steps.map((s) => `<div class="card"><h3>${s.order}. ${esc(s.short_title)}</h3><p>${rich(s.essence)}${pages(s.pages)}</p><p class="muted"><strong>Для данных.</strong> ${rich(s.data_meaning.from_chapter.text)}</p></div>`).join('')}</div>`;
  const map = () => {
    const rowH = 44, pad = 16, x = 60;
    const y = (s) => pad + (s.order - 1) * rowH + 22;
    const links = C.steps.flatMap((s) => (s.links || []).filter((l) => l.type === 'prerequisite').map((l) => [stepById(l.target), s])).filter(([a]) => a);
    const bend = (a, b) => x - Math.min(56, 10 + (b.order - a.order) * 4);
    return `<div class="column wide"><h1 tabindex="-1">Карта связей</h1><p class="muted">Дуга ведёт от шага-опоры к шагу, который на него опирается.</p><div class="scroll"><svg class="map" viewBox="0 0 620 ${pad * 2 + C.steps.length * rowH}" role="img" aria-label="Связи шагов">${links.map(([a, b]) => `<path d="M${x},${y(a)} C${bend(a, b)},${y(a)} ${bend(a, b)},${y(b)} ${x},${y(b)}"/>`).join('')}${C.steps.map((s) => `<a href="${stepUrl(s)}"><circle cx="${x}" cy="${y(s)}" r="7"/><text x="${x + 18}" y="${y(s) + 5}">${s.order}. ${esc(s.short_title)}</text></a>`).join('')}</svg></div></div>`;
  };
  const TABS = [['#/', 'Курс', home], ['#/cards', 'Карточки', cards], ['#/summary', 'Конспект', summary], ['#/map', 'Карта связей', map]];

  // ---------- каркас ----------
  const current = () => {
    const m = location.hash.match(/^#\/step\/(\d+)/);
    return m ? C.steps.find((s) => s.order === Number(m[1])) : null;
  };
  const pathLink = (x, s) => `<a href="${stepUrl(x)}" ${x === s ? 'aria-current="page"' : ''}><span class="mark ${state.done.includes(x.id) ? 'done' : ''}">${state.done.includes(x.id) ? '✓' : x.order}</span><span>${esc(x.short_title)}</span></a>`;
  const side = (s) => {
    const hash = location.hash || '#/';
    const done = state.done.filter((id) => stepById(id)).length / C.steps.length;
    return `<a class="brand" href="#/"><svg width="28" height="28" viewBox="0 0 512 512" aria-hidden="true"><rect width="512" height="512" rx="112" fill="#0B6E8F"/><path d="M148 330h72v-72h72v-72h72" fill="none" stroke="#fff" stroke-width="44" stroke-linecap="round" stroke-linejoin="round"/><circle cx="364" cy="186" r="30" fill="#FFB547"/></svg>Глава → курс</a>
      <div class="progress" role="progressbar" aria-valuenow="${Math.round(done * 100)}" aria-valuemin="0" aria-valuemax="100" aria-label="Пройдено"><i style="width:${done * 100}%"></i></div>
      <nav class="tabs" aria-label="Разделы">${TABS.map(([url, label]) => `<a href="${url}" ${hash === url ? 'aria-current="page"' : ''}>${label}</a>`).join('')}</nav>
      <nav class="path" aria-label="Путь по главе">${C.parts.map((p) => `<h3>${esc(p.title)}</h3>${p.nodes.map(stepById).filter(Boolean).map((x) => pathLink(x, s)).join('')}`).join('')}</nav>
      <button class="btn" data-theme-toggle style="margin:16px 10px">Сменить тему</button>`;
  };
  let first = true;
  const render = () => {
    const s = current();
    const page = s ? stepPage(s) : (TABS.find(([u]) => u === location.hash) || TABS[0])[2]();
    app.innerHTML = `<div class="bar"><button class="btn" data-menu aria-expanded="false">Путь</button><strong>${esc(s ? s.short_title : C.title)}</strong></div><div class="shell"><aside class="side">${side(s)}</aside><main class="sheet" id="main" tabindex="-1">${page}</main></div>`;
    app.querySelectorAll('[data-task]').forEach((el) => mountTask(el, s.tasks.find((t) => t.id === el.dataset.task)));
    app.querySelector('.path [aria-current]')?.scrollIntoView({ block: 'nearest' });
    if (!first) { scrollTo(0, 0); app.querySelector('h1')?.focus({ preventScroll: true }); }
    first = false;
  };
  const finish = (id) => {
    const next = C.steps[C.steps.findIndex((s) => s.id === id) + 1];
    set({ done: [...new Set([...state.done, id])] });
    location.hash = next ? stepUrl(next) : '#/';
  };
  const flip = (el) => {
    const rate = app.querySelector('[data-rate]');
    const s = stepById(rate.dataset.rate);
    el.innerHTML = `<p class="lead">${rich(s.essence)}${pages(s.pages)}</p>`;
    rate.hidden = false;
  };
  const toggleTheme = () => {
    const dark = state.theme === 'dark' || (state.theme === 'auto' && matchMedia('(prefers-color-scheme: dark)').matches);
    set({ theme: dark ? 'light' : 'dark' });
    applyTheme();
  };
  app.addEventListener('click', (e) => {
    const el = e.target.closest('button');
    if (!el) return;
    const d = el.dataset;
    if (d.done) finish(d.done);
    else if ('menu' in d) el.setAttribute('aria-expanded', app.querySelector('.side').classList.toggle('open'));
    else if ('themeToggle' in d) toggleTheme();
    else if ('print' in d) window.print();
    else if ('flip' in d) flip(el);
    else if (d.know) { set({ cards: { ...state.cards, [el.closest('[data-rate]').dataset.rate]: d.know } }); render(); }
    else if ('cardsReset' in d) { set({ cards: {} }); render(); }
  });
  // ссылка «К содержанию» не должна менять адрес шага
  document.querySelector('.skip').addEventListener('click', (e) => { e.preventDefault(); document.getElementById('main').focus(); });
  addEventListener('hashchange', render);
  applyTheme();
  render();
})();
