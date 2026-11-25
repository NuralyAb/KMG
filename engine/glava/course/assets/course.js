/* Каркас курса: состояние, адреса, меню, тема, карточки. Всё строится из window.COURSE, без сервера и сети. */
(() => {
  'use strict';
  const { COURSE: C, GlavaCore: core, GlavaPages: ui, GlavaTasks: tasks } = window;
  const app = document.getElementById('app');
  if (!C || !core || !ui || !tasks) { app.textContent = 'Курс не загрузился: рядом с index.html должны лежать data.js и папка assets.'; return; }
  const KEY = `glava.${C.id}`;
  const NARROW = matchMedia('(max-width: 900px)');
  const DARK = matchMedia('(prefers-color-scheme: dark)');
  const live = document.getElementById('live');

  // ---------- состояние в браузере ----------
  const load = () => { try { return JSON.parse(localStorage.getItem(KEY)); } catch { return null; } };
  let state = core.cleanState(load(), C.steps.map((s) => s.id));
  const set = (patch) => { state = { ...state, ...patch }; try { localStorage.setItem(KEY, JSON.stringify(state)); } catch { /* приватное окно: прогресс живёт до закрытия */ } };
  let sayTimer = 0;
  const say = (text) => { live.textContent = ''; clearTimeout(sayTimer); sayTimer = setTimeout(() => { live.textContent = text; }, 60); };

  // ---------- тема ----------
  const isDark = () => state.theme === 'dark' || (state.theme === 'auto' && DARK.matches);
  const applyTheme = () => {
    document.documentElement.dataset.theme = state.theme;
    const button = app.querySelector('[data-theme-toggle]');
    if (button) button.textContent = isDark() ? 'Светлая тема' : 'Тёмная тема';
  };

  // ---------- меню пути на телефоне ----------
  const menuOpen = () => Boolean(app.querySelector('.side.open'));
  const setMenu = (open) => {
    const [side, button, main] = ['.side', '[data-menu]', 'main'].map((x) => app.querySelector(x));
    if (!side || side.classList.contains('open') === open) return;
    side.classList.toggle('open', open);
    button.setAttribute('aria-expanded', open);
    main.inert = open;
    document.querySelector('.skip').inert = open;
    document.body.classList.toggle('locked', open);
    if (open) (side.querySelector('.path [aria-current]') || side.querySelector('a')).focus();
    else button.focus();
  };
  const trapTab = (e) => {
    const stops = [app.querySelector('[data-menu]'), ...app.querySelectorAll('.side a, .side button')];
    const edge = e.shiftKey ? stops[0] : stops.at(-1);
    if (document.activeElement !== edge) return;
    e.preventDefault();
    (e.shiftKey ? stops.at(-1) : stops[0]).focus();
  };

  // ---------- страница ----------
  const mountTasks = (s) => app.querySelectorAll('[data-task]').forEach((el) => {
    const task = s.tasks.find((t) => t.id === el.dataset.task);
    const claim = C.steps.flatMap((x) => x.claims).find((c) => c.id === task.claim_ids?.[0]);
    const page = claim ? ui.pages([claim.page_pdf]) : '';
    tasks.mount(el, task, { rich: ui.rich, page, say, solved: state.solved[task.id] === true, onCheck: (ok) => set({ solved: { ...state.solved, [task.id]: ok } }) });
  });
  // соседний .vtt с file:// не читается, поэтому текст субтитров лежит в data.js
  const mountVideos = () => app.querySelectorAll('video[data-vtt]').forEach((v) => {
    const { vtt, subtitles } = v.dataset;
    if (!vtt && !subtitles) return;
    const track = document.createElement('track');
    Object.assign(track, { kind: 'subtitles', srclang: 'ru', label: 'Русские', default: true, src: vtt ? URL.createObjectURL(new Blob([vtt], { type: 'text/vtt' })) : subtitles });
    v.append(track);
  });
  let shown = null;
  const here = () => {
    const at = core.parseHash(location.hash);
    const s = at.step === null ? null : C.steps.find((x) => x.order === at.step) || null;
    return { ...at, s, tab: s ? null : at.tab ?? '#/' };
  };
  const render = ({ s, tab }) => {
    const [, label, page] = ui.TABS.find(([url]) => url === tab) || [];
    if (s) set({ last: s.order });
    const name = s ? `${s.order}. ${s.short_title}` : label;
    document.title = tab === '#/' ? C.title : `${name} — ${C.title}`;
    document.body.classList.remove('locked');
    document.querySelector('.skip').inert = false;
    app.innerHTML = `<div class="bar"><button type="button" class="btn" data-menu aria-expanded="false" aria-controls="side">Путь</button><strong>${core.esc(s ? s.short_title : tab === '#/' ? C.title : label)}</strong></div><div class="shell"><aside class="side" id="side" aria-label="Путь по курсу">${ui.side(C, state, { tab, s })}</aside><main class="sheet" id="main" tabindex="-1">${s ? ui.step(C, s) : page(C, state)}</main></div>`;
    if (s) { mountTasks(s); mountVideos(); }
    const map = app.querySelector('.map');
    if (map) ui.mountMap(C, map);
    applyTheme();
    const [side, current] = [app.querySelector('.side'), app.querySelector('.path [aria-current]')];
    if (current && current.offsetTop + current.offsetHeight > side.clientHeight) side.scrollTop = current.offsetTop - side.clientHeight / 2;
  };

  // ---------- переходы: адрес, «назад» и место на странице ----------
  const savedY = () => { try { return history.state?.y ?? 0; } catch { return 0; } };
  let scrollTimer = 0;
  const keepY = () => { clearTimeout(scrollTimer); scrollTimer = setTimeout(() => { try { history.replaceState({ y: scrollY }, ''); } catch { /* песочница */ } }, 150); };
  const toSection = (id) => {
    const el = document.getElementById(id);
    if (!el || !app.contains(el)) return false;
    el.scrollIntoView();
    el.querySelector('h2')?.focus({ preventScroll: true });
    return true;
  };
  const go = ({ first = false } = {}) => {
    clearTimeout(scrollTimer);
    const at = here();
    const key = at.s ? at.s.id : at.tab;
    const fresh = key !== shown;
    if (fresh) render(at);
    else if (menuOpen()) setMenu(false);
    shown = key;
    if (at.section && toSection(at.section)) return;
    const y = savedY();
    scrollTo(0, y);
    if (!first && fresh) app.querySelector('h1')?.focus({ preventScroll: true });
  };
  try { history.scrollRestoration = 'manual'; } catch { /* старый браузер */ }

  // ---------- действия ----------
  const finish = (id) => {
    const next = C.steps[C.steps.findIndex((s) => s.id === id) + 1];
    set({ done: [...new Set([...state.done, id])] });
    location.hash = next ? ui.stepUrl(next) : '#/';
  };
  const rerender = (focus) => { render(here()); scrollTo(0, 0); app.querySelector(focus)?.focus({ preventScroll: true }); };
  const flip = () => {
    const rate = app.querySelector('[data-rate]');
    if (!rate?.hidden) return;
    app.querySelector('[data-flip]').closest('.row').hidden = true;
    app.querySelector('.flash > .muted').hidden = true;
    app.querySelectorAll('[data-back]').forEach((x) => { x.hidden = false; });
    rate.hidden = false;
    app.querySelector('.flash .lead').focus();
  };
  const rate = (el) => { set(core.rateCard(state, el.closest('[data-rate]').dataset.rate, el.dataset.know)); rerender('.flash h2, h1'); };
  const toggleTheme = () => { set({ theme: isDark() ? 'light' : 'dark' }); applyTheme(); say(isDark() ? 'Тёмная тема включена' : 'Светлая тема включена'); };
  const toggleTerm = (el) => {
    const open = el.getAttribute('aria-expanded') !== 'true';
    el.setAttribute('aria-expanded', open);
    const id = `term-${el.dataset.term}`;
    document.getElementById(id)?.remove();
    if (!open) return;
    const g = here().s.glossary[Number(el.dataset.term)];
    const note = document.createElement('p');
    note.id = id;
    note.className = 'note term-note';
    note.innerHTML = `<span><strong>${ui.rich(g.term)}.</strong> ${ui.rich(g.definition)}</span>`;
    el.closest('p').after(note);
    say(note.textContent);
  };

  app.addEventListener('click', (e) => {
    const term = e.target.closest('.term');
    if (term) { toggleTerm(term); return; }
    const link = e.target.closest('a[href^="#/"]');
    // повторный клик по тому же адресу не даёт hashchange, а меню и место на странице сменить нужно
    if (link && link.getAttribute('href') === (location.hash || '#/') && !e.ctrlKey && !e.metaKey && !e.shiftKey) { e.preventDefault(); go(); return; }
    if (e.target.closest('[data-flash]') && !String(getSelection())) { flip(); return; }
    const el = e.target.closest('button');
    if (!el) return;
    const d = el.dataset;
    if (d.done) finish(d.done);
    else if ('menu' in d) setMenu(!menuOpen());
    else if ('themeToggle' in d) toggleTheme();
    else if ('print' in d) window.print();
    else if ('flip' in d) flip();
    else if (d.know) rate(el);
    else if ('cardsReset' in d) { set({ cards: {}, repeat: [] }); rerender('.flash h2'); }
  });
  app.addEventListener('keydown', (e) => {
    if (e.target.matches('.term') && ['Enter', ' '].includes(e.key)) { e.preventDefault(); toggleTerm(e.target); }
  });
  document.addEventListener('keydown', (e) => {
    if (!menuOpen()) return;
    if (e.key === 'Escape') setMenu(false);
    else if (e.key === 'Tab') trapTab(e);
  });
  NARROW.addEventListener('change', () => { if (!NARROW.matches) setMenu(false); });
  DARK.addEventListener('change', applyTheme);
  let resizeTimer = 0;
  const redraw = () => { const map = app.querySelector('.map'); if (map) ui.drawMap(C, map); };
  addEventListener('resize', () => { clearTimeout(resizeTimer); resizeTimer = setTimeout(redraw, 100); });
  document.fonts?.ready.then(redraw);
  addEventListener('scroll', keepY, { passive: true });
  // ссылка «К содержанию» не должна менять адрес шага
  document.querySelector('.skip').addEventListener('click', (e) => { e.preventDefault(); document.getElementById('main').focus(); });
  addEventListener('hashchange', () => go());
  go({ first: true });
})();
