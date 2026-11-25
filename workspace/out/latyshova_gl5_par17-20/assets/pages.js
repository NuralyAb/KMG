/* Разметка страниц курса: шаг, разделы, боковой путь, карта. Данные — только из window.COURSE. */
(() => {
  'use strict';
  const core = window.GlavaCore;
  const { esc } = core;
  const rich = core.makeRich(window.katex);
  const KIND = { observation: 'наблюдение', inference: 'вывод', assumption: 'допущение' };
  const WHO = { author: 'автор', model: 'модель' };
  const ADVICE = { 'карточки': ['#/cards', 'Этот шаг удобно закрепить карточками'], 'практикум на данных': ['decision', 'Главное в этом шаге — решение на данных'] };
  const LEGEND = `<details class="legend"><summary>Кто это написал и что значат пометки</summary><dl>
    <div><dt><span class="chip who author">автор</span></dt><dd>Мысль, число или пример из книги; у каждой мысли раскрывается дословная цитата.</dd></div>
    <div><dt><span class="chip who model">модель</span></dt><dd>Пересказ, пояснение или аналогия, написанные моделью по мыслям автора. Если они расходятся с цитатой, верьте цитате.</dd></div>
    <div><dt><span class="chip">наблюдение</span></dt><dd>Автор сообщает факт или правило измерения.</dd></div>
    <div><dt><span class="chip">вывод</span></dt><dd>Автор выводит это из других фактов.</dd></div>
    <div><dt><span class="chip">допущение</span></dt><dd>Верно только при названном условии или принято для задачи.</dd></div>
    <div><dt><span class="chip">сверить со сканом</span></dt><dd>Текст страницы распознан с потерями или описан по рисунку, поэтому деталь стоит проверить по книге.</dd></div>
    <div><dt>стр. N</dt><dd>Страница книги по файлу PDF, с которой взят абзац.</dd></div></dl></details>`;

  const pages = (list) => (list?.length ? ` <span class="page">стр.&nbsp;${list.map(esc).join(', ')}</span>` : '');
  const chip = (text) => ` <span class="chip">${text}</span>`;
  const who = (key) => (key ? `<span class="chip who ${key}">${WHO[key]}</span>` : '');
  const byModel = (field) => (field?.by_model === false ? 'author' : 'model');
  const stepUrl = (s, section = '') => `#/step/${s.order}${section ? `/${section}` : ''}`;

  // ---------- блоки шага ----------
  const size = (p) => (p.width ? ` width="${Number(p.width)}" height="${Number(p.height)}"` : '');
  const picture = (p) => `<figure><img src="${esc(p.file)}" alt="${esc(p.alt)}"${size(p)} loading="lazy"><figcaption>${rich(p.caption)}${chip(esc(p.label))}${p.source ? ` ${esc(p.source)}` : ''}</figcaption></figure>`;
  const video = (v) => `<figure class="video${v.format === '9:16' ? ' tall' : ''}"><video controls preload="metadata" playsinline src="${esc(v.src)}" aria-label="${esc(v.title)}" data-vtt="${esc(v.vtt || '')}" data-subtitles="${esc(v.subtitles || '')}"></video><figcaption>${esc(v.title)}${v.label ? chip(esc(v.label)) : ''}</figcaption></figure>`;
  const interactive = (i) => (i ? `<div data-interactive="${esc(i.kind)}" data-params="${esc(JSON.stringify(i.params ?? {}))}"></div>` : '');
  const essence = (s) => {
    const [first, rest] = core.splitLead(s.essence);
    return `<section class="block" id="essence"><h2 class="sr" tabindex="-1">Суть</h2><p class="lead"><strong>${rich(first)}</strong> ${rich(rest)}${pages(s.pages)} ${who('model')}</p></section>`;
  };
  const how = (s) => {
    const marked = core.markTerms(s.how.flatMap((b) => b.paragraphs.map((p) => p.text)), s.glossary);
    const start = s.how.map((_, i) => s.how.slice(0, i).reduce((n, b) => n + b.paragraphs.length, 0));
    return s.how.map((b, i) => `<h3>${esc(b.title)}</h3>${b.paragraphs.map((p, k) => `<p>${rich(marked[start[i] + k])}${pages(p.pages)}</p>`).join('')}`).join('');
  };
  const list = (items, tag, html) => (items?.length ? `<${tag}>${items.map(html).join('')}</${tag}>` : '');
  const procedure = (s) => list(s.procedure, 'ol', (x) => `<li>${rich(x.text)}${pages(x.pages)}</li>`);
  const numbers = (s) => (s.numbers?.length ? `<ul class="facts">${s.numbers.map((x) => `<li>${rich(x.text)}${pages([x.page])}</li>`).join('')}</ul>` : '');
  const formula = (f) => `<div class="card"><div class="formula">${core.texOnly(f.tex, rich)}${pages([f.page])}</div>${f.legend?.length ? `<dl class="legend-list">${f.legend.map((l) => `<div><dt>${core.symbol(l.symbol, rich)}</dt><dd>${rich(l.meaning)}${l.unit ? `, ${core.symbol(l.unit, rich)}` : ''}</dd></div>`).join('')}</dl>` : ''}${f.errata ? `<p class="note warn"><span><strong>Сверка со сканом.</strong> ${rich(f.errata)}</span></p>` : ''}</div>`;
  const cellText = (s) => rich(String(s).replace(/[$]{2}/g, '$'));
  const cell = (c) => (c.from === null ? `<td>${cellText(c.text)}</td>` : `<td class="fixed">${cellText(c.text)}<span class="was"> исправлено, в распознанном тексте: «${cellText(c.from)}»</span></td>`);
  const table = (t) => `<p>${rich(t.title)}${pages([t.page])}${t.corrections?.length ? `<br><span class="muted">Исправлено ячеек по скану: ${t.corrections.length}, они выделены.</span>` : ''}</p><div class="scroll" role="region" tabindex="0" aria-label="${esc(t.title)}, прокрутка вбок"><table aria-label="${esc(t.title)}">${t.header?.length ? `<thead><tr>${t.header.map((h) => `<th scope="col">${rich(h)}</th>`).join('')}</tr></thead>` : ''}<tbody>${core.tableRows(t).map((r) => `<tr>${r.map(cell).join('')}</tr>`).join('')}</tbody></table></div>`;
  const claim = (c) => `<li>${rich(c.text)}${pages([c.page_pdf])}${chip(KIND[c.kind] || '')}${c.by_model ? ` ${who('model')}` : ''}${c.source_kind === 'figure_description_model' ? chip('по описанию рисунка') : ''}${c.needs_scan ? chip('сверить со сканом') : ''}<details><summary>${c.source_kind === 'figure_description_model' ? 'Описание рисунка' : 'Цитата автора'}</summary><blockquote>${rich(c.quote)}</blockquote></details></li>`;
  const claims = (s) => (s.claims.length ? `<ul class="claims">${s.claims.map(claim).join('')}</ul>` : '');
  const scan = (s) => list(s.needs_scan, 'ul', (x) => `<li>${rich(x.what)}${pages([x.page])}</li>`);
  const example = (e) => `<div class="card"><p><strong>Условие.</strong> ${rich(e.condition)}</p>${list(e.steps, 'ol', (x) => `<li>${rich(x)}</li>`)}<p><strong>Итог.</strong> ${rich(e.result)}${pages([e.page_pdf])}</p>${e.figure ? `<p class="muted">Нужен рисунок: ${esc(e.figure)}</p>` : ''}</div>`;
  const bookTask = (t) => `<div class="card"><p><strong>Задача ${esc(t.number)}.</strong> ${rich(t.text)}${pages([t.page_pdf])}</p>${t.figure ? `<p class="muted">Нужен рисунок: ${esc(t.figure)}</p>` : ''}</div>`;
  const dataBlock = ({ data_meaning: d, pages: p }) => `<p>${rich(d.from_chapter.text)}${pages(p)}</p><p><strong>Где ломается.</strong> ${rich(d.breaks.text)}${pages(p)}</p>${(d.hypotheses || []).map((h) => `<div class="note warn"><strong>Гипотеза, не из главы</strong><p>${rich(h.text)}</p></div>`).join('')}`;
  const pair = (title, text) => (text ? `<div><dt>${title}</dt><dd>${rich(text)}</dd></div>` : '');
  const lens = (l) => (l ? `<dl>${pair('Входные данные', l.inputs)}${pair('Ручные шаги', l.manual_steps)}${pair('Точки суждения', l.judgment_points)}${pair('Время', l.time)}${pair('Типичные ошибки', l.typical_errors)}</dl>` : '');
  const decision = (d) => (d ? `<h3>Признаки</h3>${list(d.features, 'ol', (f) => `<li>${rich(f)}</li>`)}<p><strong>Правило.</strong> ${rich(d.rule)}</p><p><strong>Вывод.</strong> ${rich(d.conclusion)}</p>${d.counterexample ? `<div class="note warn"><strong>Контрпример</strong><p>${rich(d.counterexample)}</p></div>` : ''}` : '');
  const analogy = (a) => (a ? `<p>${rich(a.text)}</p><p><strong>Где перестаёт работать.</strong> ${rich(a.breaks_where)}</p>` : '');

  /** Блоки страницы по порядку; пустые не показываются и не попадают в оглавление. */
  const sections = (s) => [
    { id: 'how', title: 'Как это работает', who: 'model', body: how(s) },
    { id: 'steps', title: 'По шагам', who: 'model', body: procedure(s) },
    { id: 'decision', title: 'Решение на данных', who: 'model', body: decision(s.decision_on_data) },
    { id: 'examples', title: 'Разбор примеров из главы', who: 'author', body: (s.worked_examples || []).map(example).join('') },
    { id: 'numbers', title: 'Цифры и условия', who: 'author', body: numbers(s) },
    { id: 'terms', title: 'Новые понятия', who: 'model', body: s.glossary.length ? `<dl>${s.glossary.map((g) => `<div><dt>${rich(g.term)}</dt><dd>${rich(g.definition)}</dd></div>`).join('')}</dl>` : '' },
    { id: 'formulas', title: 'Формулы', who: 'author', body: (s.formulas || []).map(formula).join('') },
    { id: 'tables', title: 'Таблицы книги', who: 'author', body: (s.tables || []).map(table).join('') },
    { id: 'mistake', title: 'Частая ошибка', who: byModel(s.misconception), tone: 'bad', body: s.misconception ? `<p>${rich(s.misconception.text)}</p>` : '' },
    { id: 'data', title: 'Что это значит для данных', who: byModel(s.data_meaning?.from_chapter), body: s.data_meaning ? dataBlock(s) : '' },
    { id: 'analogy', title: 'Аналогия из ИТ', who: 'model', tone: 'brand', body: analogy(s.it_analogy) },
    { id: 'labour', title: 'Ручной труд специалиста', who: 'model', body: lens(s.inefficiency_lens) },
    { id: 'now', title: 'Как это делают сейчас', who: 'model', tone: 'warn', body: s.now_practice ? `<p>${rich(s.now_practice.text)}</p><p class="by">Не из книги.</p>` : '' },
    { id: 'deeper', title: 'Глубже', who: 'model', body: (s.deeper || []).map((d) => `<p>${rich(d.text)}${pages(d.pages)}</p>`).join('') },
    { id: 'claims', title: 'Источник: мысли автора с цитатами', who: 'author', body: claims(s) },
    { id: 'scan', title: 'Что сверить со сканом', who: 'model', body: scan(s) },
    { id: 'book', title: 'Задачи из книги', who: 'author', body: (s.book_tasks || []).map(bookTask).join('') },
    { id: 'tasks', title: 'Проверьте себя', who: null, body: s.tasks.map((t) => `<div class="card task" data-task="${esc(t.id)}"></div>`).join('') },
  ].filter((x) => x.body);
  const section = (x) => `<section class="${x.tone ? `note ${x.tone}` : 'block'}" id="${x.id}"><div class="head"><h2 tabindex="-1">${x.title}</h2>${who(x.who)}</div>${x.body}</section>`;
  const toc = (s, blocks) => `<nav class="toc" aria-label="На этой странице"><details ${matchMedia('(min-width: 901px)').matches ? 'open' : ''}><summary>На этой странице</summary><ul>${blocks.map((x) => `<li><a href="${stepUrl(s, x.id)}">${x.title}</a></li>`).join('')}</ul></details></nav>`;
  const advice = (s, blocks) => {
    const [target, text] = ADVICE[s.format] || [];
    if (!text || (!target.startsWith('#') && !blocks.some((x) => x.id === target))) return '';
    return `<p><a href="${target.startsWith('#') ? target : stepUrl(s, target)}">${text}</a></p>`;
  };
  const route = (s) => (s.format ? `<p>Формат по маршруту: ${esc(s.format)}.${s.format_why ? ` ${rich(s.format_why)}` : ''}</p>` : '');

  const step = (C, s) => {
    const i = C.steps.indexOf(s);
    const [prev, next] = [C.steps[i - 1], C.steps[i + 1]];
    const blocks = sections(s);
    return `<article class="column">
      <header class="block"><p class="muted">Шаг ${s.order} из ${C.steps.length} · ${s.minutes} мин${s.threshold ? ' · пороговая идея' : ''}</p><h1 tabindex="-1">${esc(s.short_title || s.title)}</h1><p class="muted">В книге: ${esc(s.title)}${pages(s.pages)}</p>${advice(s, blocks)}</header>
      ${essence(s)}
      ${s.pictures.map(picture).join('')}
      ${toc(s, blocks)}${LEGEND}
      ${(s.videos || []).map(video).join('')}${interactive(s.interactive)}
      ${blocks.map(section).join('')}
      <footer class="row noprint">${prev ? `<a class="btn" href="${stepUrl(prev)}">Назад</a>` : '<span></span>'}<button type="button" class="btn main" data-done="${esc(s.id)}">${next ? 'Понятно, дальше' : 'Завершить курс'}</button></footer>
      <details><summary>Почему этот шаг здесь и в таком формате</summary><p>${rich(s.why_here?.text)}</p>${route(s)}</details>
    </article>`;
  };

  // ---------- разделы ----------
  const home = (C, state) => {
    const resume = C.steps.find((s) => s.order === state.last) || C.steps[0];
    const total = C.steps.reduce((a, s) => a + s.minutes, 0);
    const part = (p) => `<section class="block"><h2>${esc(p.title)}</h2><ol>${p.nodes.map((id) => C.steps.find((s) => s.id === id)).filter(Boolean).map((s) => `<li value="${s.order}"><a href="${stepUrl(s)}">${esc(s.short_title)}</a> <span class="muted">${s.minutes} мин${state.done.includes(s.id) ? ' · пройден' : ''}</span></li>`).join('')}</ol></section>`;
    return `<div class="column"><header class="block"><h1 tabindex="-1">${esc(C.title)}</h1><p class="muted">${esc(C.book)}</p></header>
      <p class="lead">Шагов: ${C.steps.length}, около ${total} минут, заданий: ${C.steps.reduce((a, s) => a + s.tasks.length, 0)}. Каждый абзац ведёт на страницу книги.</p>
      <div><a class="btn main" href="${stepUrl(resume)}">${state.last ? `Продолжить: шаг ${resume.order}` : 'Начать'}</a></div>
      ${C.parts.map(part).join('')}
      <p class="muted">Учебный слой собран моделью ${esc(C.generated_by)}; цитаты и числа проверены кодом по страницам главы.</p></div>`;
  };
  const cards = (C, state) => {
    const ids = C.steps.map((s) => s.id);
    const s = C.steps.find((x) => x.id === core.nextCard(ids, state));
    if (!s) return '<div class="column"><h1 tabindex="-1">Карточки</h1><p class="lead">Все карточки отмечены «знаю».</p><div><button type="button" class="btn" data-cards-reset>Повторить все</button></div></div>';
    const known = ids.filter((id) => state.cards[id] === 'know').length;
    const again = ids.filter((id) => state.cards[id] === 'again').length;
    return `<div class="column"><h1 tabindex="-1">Карточки</h1><p class="muted">Осталось ${ids.length - known} из ${ids.length}, из них на повтор: ${again}</p>
      <div class="flash" data-flash><h2 tabindex="-1">${s.order}. ${esc(s.short_title)}</h2><p class="muted">Вспомните суть, потом откройте ответ</p><div data-back hidden><p class="lead" tabindex="-1">${rich(s.essence)}${pages(s.pages)}</p></div></div>
      <div class="row"><button type="button" class="btn main" data-flip>Показать ответ</button></div>
      <div class="row" hidden data-rate="${esc(s.id)}"><button type="button" class="btn" data-know="again">Повторить</button><button type="button" class="btn main" data-know="know">Знаю</button></div>
      <p data-back hidden><a href="${stepUrl(s)}">Открыть шаг</a></p></div>`;
  };
  const summary = (C) => `<div class="column summary"><div class="row"><h1 tabindex="-1">Конспект</h1><button type="button" class="btn noprint" data-print>Печать в PDF</button></div><p class="muted">${esc(C.title)}. ${esc(C.book)}</p>${C.parts.map((p) => `<section class="block"><h2>${esc(p.title)}</h2>${p.nodes.map((id) => C.steps.find((s) => s.id === id)).filter(Boolean).map((s) => `<div class="card"><h3>${s.order}. ${esc(s.short_title)}</h3><p>${rich(s.essence)}${pages(s.pages)}</p>${s.data_meaning ? `<p><strong>Вывод для данных.</strong> ${rich(s.data_meaning.from_chapter.text)}</p><p><strong>Где ломается.</strong> ${rich(s.data_meaning.breaks.text)}</p>` : ''}</div>`).join('')}</section>`).join('')}</div>`;
  const map = (C) => {
    const links = core.edges(C.steps);
    const supports = (s) => links.filter(([, b]) => b === s).map(([a]) => a).sort((a, b) => a.order - b.order);
    const row = (s) => `<li data-node="${s.order}"><a class="map-step" href="${stepUrl(s)}">${s.order}. ${esc(s.short_title)}</a>${supports(s).length ? `<span class="muted map-links">опирается на ${supports(s).map((a) => `<a href="${stepUrl(a)}" aria-label="шаг ${a.order}: ${esc(a.short_title)}">${a.order}</a>`).join(' ')}</span>` : '<span class="muted map-links">начало пути</span>'}</li>`;
    return `<div class="column wide"><header class="block"><h1 tabindex="-1">Карта связей</h1><p class="muted">Дуга ведёт от шага-опоры к шагу, который на него опирается. Наведите, нажмите на строку или перейдите клавишей Tab: связи шага выделятся.</p></header><div class="map"><svg aria-hidden="true"></svg>${C.parts.map((p) => `<h2>${esc(p.title)}</h2><ul>${p.nodes.map((id) => C.steps.find((s) => s.id === id)).filter(Boolean).map(row).join('')}</ul>`).join('')}</div></div>`;
  };

  /** Дуги рисуются по местам строк: названия переносятся, поэтому высота строк разная. */
  const drawMap = (C, root) => {
    const svg = root.querySelector('svg');
    const top = root.getBoundingClientRect().top;
    const rows = new Map([...root.querySelectorAll('[data-node]')].map((li) => [Number(li.dataset.node), li.getBoundingClientRect().top - top + 22]));
    const margin = parseFloat(getComputedStyle(root).paddingLeft);
    const x = margin - 14;
    const longest = C.steps.length - 1;
    const arcs = core.edges(C.steps).map(([a, b]) => {
      const bend = x - core.arcDepth(b.order - a.order, longest, x - 2) * 4 / 3;
      return `<path data-from="${a.order}" data-to="${b.order}" d="M${x},${rows.get(a.order)} C${bend},${rows.get(a.order)} ${bend},${rows.get(b.order)} ${x},${rows.get(b.order)}"/>`;
    });
    svg.setAttribute('width', margin);
    svg.setAttribute('height', root.clientHeight);
    svg.innerHTML = arcs.join('') + [...rows].map(([order, y]) => `<circle data-dot="${order}" cx="${x}" cy="${y}" r="6"/>`).join('');
  };
  const lightMap = (root, order) => {
    const near = new Set();
    const dot = root.querySelector('circle');
    root.querySelectorAll('path').forEach((p) => {
      const on = [p.dataset.from, p.dataset.to].includes(String(order));
      p.classList.toggle('on', on);
      if (!on) return;
      dot.before(p); // выделенная дуга — поверх остальных
      near.add(p.dataset.from);
      near.add(p.dataset.to);
    });
    root.querySelectorAll('[data-node]').forEach((li) => { li.classList.toggle('near', near.has(li.dataset.node)); li.classList.toggle('here', li.dataset.node === String(order)); });
    root.querySelectorAll('[data-dot]').forEach((c) => c.classList.toggle('near', near.has(c.dataset.dot)));
  };
  const mountMap = (C, root) => {
    drawMap(C, root);
    ['pointerover', 'focusin', 'click'].forEach((name) => root.addEventListener(name, (e) => {
      const li = e.target.closest('[data-node]');
      if (li) lightMap(root, li.dataset.node);
    }));
  };

  // ---------- боковой путь ----------
  const LOGO = '<svg width="28" height="28" viewBox="0 0 512 512" aria-hidden="true"><rect width="512" height="512" rx="112" fill="#0B6E8F"/><path d="M148 330h72v-72h72v-72h72" fill="none" stroke="#fff" stroke-width="44" stroke-linecap="round" stroke-linejoin="round"/><circle cx="364" cy="186" r="30" fill="#FFB547"/></svg>';
  const TABS = [['#/', 'Курс', home], ['#/cards', 'Карточки', cards], ['#/summary', 'Конспект', summary], ['#/map', 'Карта связей', map]];
  const pathLink = (x, s, done) => `<a href="${stepUrl(x)}" ${x === s ? 'aria-current="page"' : ''}><span class="mark ${done ? 'done' : ''}" aria-hidden="true">${done ? '✓' : x.order}</span><span>${esc(x.short_title)}${done ? '<span class="sr">, пройден</span>' : ''}</span></a>`;
  const side = (C, state, { tab, s }) => {
    const count = state.done.length;
    const share = (count / C.steps.length) * 100;
    return `<a class="logo" href="#/">${LOGO}Глава → курс</a>
      <div class="progress" aria-hidden="true"><i style="width:${share}%"></i></div><p class="muted passed">Пройдено ${count} из ${C.steps.length}</p>
      <nav class="tabs" aria-label="Разделы">${TABS.map(([url, label]) => `<a href="${url}" ${!s && tab === url ? 'aria-current="page"' : ''}>${label}</a>`).join('')}</nav>
      <nav class="path" aria-label="Путь по главе">${C.parts.map((p) => `<p class="part">${esc(p.title)}</p>${p.nodes.map((id) => C.steps.find((x) => x.id === id)).filter(Boolean).map((x) => pathLink(x, s, state.done.includes(x.id))).join('')}`).join('')}</nav>
      <button type="button" class="btn theme" data-theme-toggle></button>`;
  };

  window.GlavaPages = { rich, pages, stepUrl, step, TABS, side, mountMap, drawMap };
})();
