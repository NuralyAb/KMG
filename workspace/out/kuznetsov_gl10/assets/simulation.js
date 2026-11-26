/* Симуляторы шага: сцена запускается прямо на странице, по кнопке. Пока агент её строит, на месте сцены виден ход работы. */
(() => {
  'use strict';
  const SLOW_MS = 12_000;
  const FAIL_MS = 60_000;
  const POLL_MS = 4_000;
  const IDLE_POLL_MS = 20_000;
  const CALM = matchMedia('(prefers-reduced-motion: reduce)');
  const STAGES = {
    facts: 'Берёт факты шага из книги', design: 'Придумывает задачу', model: 'Считает физику', scene: 'Строит 3D-сцену', game: 'Составляет задание',
    look: 'Смотрит кадры и исправляет', finish: 'Проходит сам от начала до конца', course: 'Ставит в курс',
  };

  // стили рядом со скриптом: симуляторы не зависят от оформления курса
  const here = document.currentScript.src;
  const link = document.createElement('link');
  Object.assign(link, { rel: 'stylesheet', href: new URL('simulation.css', here).href });
  document.head.append(link);

  const make = (tag, cls = '', text = '') => {
    const el = document.createElement(tag);
    if (cls) el.className = cls;
    if (text) el.textContent = text;
    return el;
  };
  const button = (cls, text, onClick) => {
    const el = make('button', cls, text);
    el.type = 'button';
    el.addEventListener('click', onClick);
    return el;
  };

  const ICONS = {
    full: '<path d="M4 9V4h5M15 4h5v5M20 15v5h-5M9 20H4v-5"/>', small: '<path d="M9 4v5H4M20 9h-5V4M15 20v-5h5M4 15h5v5"/>', close: '<path d="M6 6l12 12M18 6L6 18"/>',
  };
  const face = (el, icon, label) => {
    el.innerHTML = `<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICONS[icon]}</svg>`;
    el.setAttribute('aria-label', label);
    el.title = label;
  };

  // ---------- сцена на месте ----------
  const isFull = (box) => document.fullscreenElement === box || box.classList.contains('sim-max');
  const toggleFull = (box) => {
    if (document.fullscreenElement === box) document.exitFullscreen();
    else if (document.fullscreenEnabled && box.requestFullscreen) box.requestFullscreen().catch(() => box.classList.toggle('sim-max'));
    else box.classList.toggle('sim-max');
  };

  const player = (items) => {
    const box = make('section', 'sim-box');
    const bar = make('div', 'sim-bar');
    const screen = make('div', 'sim-screen');
    const live = make('div', 'sim-note');
    live.setAttribute('role', 'status');
    let item = items[0];
    let stopWaiting = () => {};

    const tabs = items.map((x) => button('sim-tab', x.title, () => { if (x !== item || box.dataset.state !== 'idle') { item = x; idle(); } }));
    const head = make('div', 'sim-head');
    if (items.length > 1) {
      head.setAttribute('role', 'group');
      head.setAttribute('aria-label', 'Симуляторы шага');
      head.append(...tabs);
    } else head.append(make('strong', '', item.title));
    const next = button('sim-act', 'Новый случай', () => screen.querySelector('iframe')?.contentWindow.postMessage({ sim: 'next' }, '*'));
    const off = button('sim-act icon', '', () => { if (isFull(box)) toggleFull(box); idle(); box.querySelector('.sim-go').focus(); });
    face(off, 'close', 'Закрыть симулятор');
    const full = button('sim-act icon', '', () => { toggleFull(box); showFull(); });
    const showFull = () => { if (isFull(box)) face(full, 'small', 'Свернуть'); else face(full, 'full', 'Во весь экран'); };
    showFull();
    box.addEventListener('fullscreenchange', showFull);
    const acts = make('div', 'sim-acts');
    acts.append(next, full, off);
    bar.append(head, acts);

    const set = (state, ...content) => {
      stopWaiting();
      box.dataset.state = state;
      acts.hidden = state !== 'live';
      tabs.forEach((t, i) => t.setAttribute('aria-pressed', items[i] === item));
      live.textContent = '';
      screen.replaceChildren(...content);
    };
    const poster = () => {
      if (!item.poster) return [];
      const img = make('img', 'sim-poster');
      Object.assign(img, { src: item.poster, alt: `Кадр симулятора «${item.title}»`, loading: 'lazy' });
      return [img];
    };
    const idle = () => {
      const card = make('div', 'sim-cover');
      const go = button('sim-go', 'Запустить', () => start());
      go.setAttribute('aria-label', `Запустить симулятор «${item.title}»`);
      card.append(make('span', 'sim-label', item.label), make('p', 'sim-goal', item.goal), go);
      set('idle', ...poster(), card);
    };
    const fail = (text) => {
      const card = make('div', 'sim-cover');
      const retry = button('sim-go', 'Повторить', () => start());
      card.append(make('p', 'sim-goal', text), retry);
      set('error', ...poster(), card);
      live.textContent = text;
    };
    const start = () => {
      const frame = make('iframe');
      Object.assign(frame, { title: item.title, src: `assets/sim/player.html#${encodeURIComponent(item.id)}` });
      frame.setAttribute('allow', 'fullscreen');
      const wait = make('div', 'sim-wait');
      const words = make('p', '', 'Загружаем 3D-сцену');
      wait.append(...poster(), make('span', 'sim-spin'), words);
      set('loading', frame, wait);
      live.textContent = 'Загружаем 3D-сцену';
      box.scrollIntoView({ block: 'nearest', behavior: CALM.matches ? 'auto' : 'smooth' });
      const slow = setTimeout(() => { words.textContent = 'Сцена большая, ещё немного'; }, SLOW_MS);
      const dead = setTimeout(() => fail('Сцена не открылась. Проверьте, что страница открыта в обычном браузере, и попробуйте ещё раз.'), FAIL_MS);
      const heard = (e) => {
        if (e.source !== frame.contentWindow || !e.data?.sim) return;
        if (e.data.sim === 'error') { fail(String(e.data.text || 'Сцена не запустилась.')); return; }
        stopWaiting();
        box.dataset.state = 'live';
        acts.hidden = false;
        live.textContent = 'Сцена готова';
        wait.remove();
        frame.focus({ preventScroll: true });
      };
      addEventListener('message', heard);
      stopWaiting = () => { clearTimeout(slow); clearTimeout(dead); removeEventListener('message', heard); stopWaiting = () => {}; };
    };
    box.append(bar, screen, live);
    idle();
    return box;
  };

  // ---------- агент строит сцену ----------
  const since = (iso) => {
    const s = Math.max(0, Math.round((Date.now() - Date.parse(iso)) / 1000));
    return Number.isFinite(s) ? `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}` : '';
  };
  const building = (build) => {
    const box = make('section', 'sim-build');
    const done = build.stages.filter((x) => x.state === 'done').length;
    const now = build.stages.filter((x) => x.state === 'now').map((x) => STAGES[x.name] || x.name);
    const head = make('div', 'sim-build-head');
    const title = make('strong', '', build.state === 'queued' ? 'Симулятор ждёт очереди' : 'ИИ-агент строит симулятор');
    const time = make('span', 'sim-time', build.started_at ? since(build.started_at) : '');
    head.append(make('span', 'sim-spin'), title, time);
    const bar = make('div', 'sim-progress');
    const fill = make('i');
    fill.style.setProperty('--share', done / build.stages.length);
    bar.append(fill);
    const list = make('ol', 'sim-stages');
    build.stages.forEach((x) => {
      const li = make('li', '', STAGES[x.name] || x.name);
      li.dataset.state = x.state;
      if (x.state === 'now') li.setAttribute('aria-current', 'step');
      list.append(li);
    });
    const word = make('p', 'sr', now.length ? `Сейчас: ${now.join(', ')}. Готово ${done} из ${build.stages.length}` : '');
    word.setAttribute('role', 'status');
    box.append(head, bar, list, make('p', 'sim-hint', 'Обычно это 5–15 минут. Можно читать дальше: сцена появится здесь сама.'), word);
    const tick = setInterval(() => { if (!box.isConnected) clearInterval(tick); else if (build.started_at) time.textContent = since(build.started_at); }, 1000);
    return box;
  };
  const ended = (text) => {
    const box = make('section', 'sim-build');
    const word = make('p', '', text);
    word.setAttribute('role', 'status');
    box.append(word);
    return box;
  };

  // ---------- опрос сервера: только когда курс открыт на платформе ----------
  const place = /^\/(course|learn)\/([^/]+)\//.exec(location.pathname);
  const api = location.protocol.startsWith('http') && place
    ? (place[1] === 'learn' ? `/api/learn/courses/${place[2]}/simulations/building` : `/api/chapters/${place[2]}/simulations/building`) : null;
  let root = null;
  let builds = [];
  let seen = '';      // шаг, по которому работа агента уже была видна
  let timer = 0;

  const stepNow = () => {
    const found = /^#\/step\/(\d+)/.exec(location.hash);
    return found ? (window.COURSE?.steps || []).find((s) => s.order === Number(found[1])) : undefined;
  };
  const slot = () => {
    const old = root.querySelector('[data-sim-slot]');
    if (old) return old;
    const el = make('div', 'noprint');
    el.dataset.simSlot = '';
    const after = root.querySelector('main .stage') || root.querySelector('main [data-interactive]') || root.querySelector('main header') || root.querySelector('main h1');
    if (!after) return null;
    after.after(el);
    return el;
  };
  /** Курс пересобран на месте: новая сцена встаёт в открытый шаг без перезагрузки страницы. */
  const takeNew = async (step) => {
    const text = await (await fetch('data.js', { cache: 'no-store' })).text();
    const fresh = JSON.parse(text.slice(text.indexOf('{'), text.lastIndexOf('}') + 1)).steps.find((s) => s.id === step.id);
    const had = step.interactive?.params?.items?.length || 0;
    const items = fresh?.interactive?.params?.items || [];
    if (items.length <= had) return null;
    step.interactive = fresh.interactive;
    return items;
  };
  const showEnd = async (step) => {
    if (place[1] === 'learn') return ended('Агент закончил работу. Симулятор появится здесь, когда автор проверит его и обновит курс.');
    const items = await takeNew(step).catch(() => null);
    if (!items) return ended('Агент остановился, новой сцены в курсе нет. Причина видна в запусках.');
    root.querySelectorAll('[data-interactive="simulation"]').forEach((el) => { el.hidden = true; });
    return player(items);
  };
  const show = async () => {
    const step = stepNow();
    if (!root?.isConnected || !step) return;
    const build = builds.find((b) => b.step_id === step.id);
    if (build) {
      seen = step.id;
      slot()?.replaceChildren(building(build));
    } else if (seen === step.id) {
      seen = '';
      const el = await showEnd(step);
      if (stepNow() === step) slot()?.replaceChildren(el);
    }
  };
  const poll = async () => {
    clearTimeout(timer);
    if (!api) return;
    try {
      if (!document.hidden) {
        const answer = await fetch(api);
        if (!answer.ok) return; // курс лежит не на платформе
        builds = (await answer.json()).data || [];
        await show();
      }
    } catch { /* сервер перезапускается: спросим в следующий раз */ }
    clearTimeout(timer);
    timer = setTimeout(poll, builds.length ? POLL_MS : IDLE_POLL_MS);
  };
  document.addEventListener('visibilitychange', () => { if (!document.hidden && timer) poll(); });

  const mount = (el) => {
    root = el;
    el.querySelectorAll('[data-interactive="simulation"]').forEach((x) => {
      const { items = [] } = JSON.parse(x.dataset.params);
      x.classList.add('noprint');
      x.replaceChildren(...(items.length ? [player(items)] : []));
    });
    if (timer) show(); else poll();
  };
  window.Simulations = { mount };
})();
