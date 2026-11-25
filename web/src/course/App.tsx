import { useEffect, useLayoutEffect, useMemo, useRef, useState, type KeyboardEvent, type MouseEvent } from 'react';
import { useInert } from './bits';
import { CourseProvider, courseTools } from './context';
import { parseHash } from './core';
import { Lesson } from './Lesson';
import { Plan, Side, TABS, Top, type View } from './shell';
import { createStore, useStore } from './store';
import type { Course } from './types';

const NARROW = '(max-width: 1000px)';
const SCROLL_MS = 150;

/** Внутри приложения курс стоит в рамке, и «Мои курсы» ведут в каталог; у курса с диска каталога нет. */
const catalogUrl = (): string => (window.parent !== window && location.protocol.startsWith('http') ? '/' : '');

interface Visit { hash: string; n: number }
const savedY = (): number => {
  const y: unknown = (history.state as { y?: unknown } | null)?.y;
  return typeof y === 'number' ? y : 0;
};

function toSection(root: HTMLElement | null, id: string): boolean {
  const el = document.getElementById(id);
  if (!el || !root?.contains(el)) return false;
  el.scrollIntoView();
  el.querySelector('h2')?.focus({ preventScroll: true });
  return true;
}

/** Адреса: #/, #/map, #/step/3, #/step/3/how. «Назад» возвращает и место на странице. */
function useVisit(): [Visit, () => void] {
  const [visit, setVisit] = useState<Visit>({ hash: location.hash, n: 0 });
  const go = (): void => setVisit(({ n }) => ({ hash: location.hash, n: n + 1 }));
  useEffect(() => {
    let timer = 0;
    const keepY = (): void => {
      window.clearTimeout(timer);
      timer = window.setTimeout(() => { try { history.replaceState({ y: window.scrollY }, ''); } catch { /* песочница */ } }, SCROLL_MS);
    };
    const changed = (): void => { window.clearTimeout(timer); go(); };
    try { history.scrollRestoration = 'manual'; } catch { /* старый браузер */ }
    window.addEventListener('hashchange', changed);
    window.addEventListener('scroll', keepY, { passive: true });
    return () => { window.clearTimeout(timer); window.removeEventListener('hashchange', changed); window.removeEventListener('scroll', keepY); };
  }, []);
  return [visit, go];
}

export function App({ course }: { course: Course }) {
  const store = useMemo(() => createStore(course), [course]);
  const tools = useMemo(() => courseTools(course), [course]);
  const catalog = useMemo(catalogUrl, []);
  const state = useStore(store);
  const [visit, go] = useVisit();
  const [isMenuOpen, setMenu] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const shown = useRef('');
  const main = useInert<HTMLElement>(isMenuOpen);

  const place = parseHash(visit.hash);
  const step = place.step === null ? null : course.steps.find((s) => s.order === place.step) ?? null;
  const view: View = { step, tab: step ? null : place.tab ?? '#/' };
  const tab = TABS.find((t) => t.url === view.tab);
  const key = step?.id ?? view.tab ?? '#/';
  const order = step?.order;
  const title = step ? `${tools.num(step)} ${step.short_title} — ${course.title}` : view.tab === '#/' ? course.title : `${tab?.label} — ${course.title}`;

  useLayoutEffect(() => { document.title = title; }, [title]);
  useLayoutEffect(() => setMenu(false), [visit]);
  useEffect(() => { if (order !== undefined) store.set({ last: order }); }, [order, store]);
  // сцену симулятора в узел [data-interactive] ставит assets/simulation.js, один раз на урок
  useEffect(() => { if (order !== undefined && root.current) window.Simulations?.mount(root.current); }, [order]);
  useEffect(() => {
    const isNew = shown.current !== key;
    const isFirst = shown.current === '';
    shown.current = key;
    if (place.section && toSection(root.current, place.section)) return;
    window.scrollTo(0, savedY());
    if (isNew && !isFirst) root.current?.querySelector('h1')?.focus({ preventScroll: true });
    // эффект привязан к переходу, а не к каждой отрисовке
  }, [visit]);

  useEffect(() => {
    document.body.classList.toggle('locked', isMenuOpen);
    const skip = document.querySelector('.skip');
    skip?.toggleAttribute('inert', isMenuOpen);
    const media = matchMedia(NARROW);
    const widened = (): void => { if (!media.matches) setMenu(false); };
    media.addEventListener('change', widened);
    return () => media.removeEventListener('change', widened);
  }, [isMenuOpen]);
  useEffect(() => {
    const skip = document.querySelector('.skip');
    // ссылка «К содержанию» не должна менять адрес урока
    const jump = (e: Event): void => { e.preventDefault(); document.getElementById('main')?.focus(); };
    skip?.addEventListener('click', jump);
    return () => skip?.removeEventListener('click', jump);
  }, []);

  // повторный клик по тому же адресу не даёт hashchange, а меню и место на странице сменить нужно
  const onClick = (e: MouseEvent): void => {
    const link = (e.target as Element).closest('a[href^="#/"]');
    if (!link || e.ctrlKey || e.metaKey || e.shiftKey || link.getAttribute('href') !== (location.hash || '#/')) return;
    e.preventDefault();
    go();
  };
  const menuButton = (): HTMLElement | null => root.current?.querySelector<HTMLElement>('[data-menu]') ?? null;
  const onKey = (e: KeyboardEvent): void => {
    if (!isMenuOpen) return;
    if (e.key === 'Escape') { setMenu(false); menuButton()?.focus(); return; }
    if (e.key !== 'Tab') return;
    const stops = [menuButton(), ...root.current?.querySelectorAll<HTMLElement>('.plan a, .plan summary') ?? []].filter((x): x is HTMLElement => x !== null && x.offsetParent !== null);
    if (document.activeElement !== (e.shiftKey ? stops[0] : stops.at(-1))) return;
    e.preventDefault();
    (e.shiftKey ? stops.at(-1) : stops[0])?.focus();
  };

  return (
    <CourseProvider value={{ ...tools, store, state, catalog }}>
      <div className="shell" ref={root} onClick={onClick} onKeyDown={onKey}>
        <Side view={view} isInert={isMenuOpen} />
        <Top view={view} isMenuOpen={isMenuOpen} onMenu={() => setMenu(!isMenuOpen)} />
        <main className="sheet" id="main" tabIndex={-1} ref={main}>
          {step ? <Lesson key={step.id} step={step} section={place.section} visit={visit.n} /> : tab && <tab.Page key={tab.url} />}
        </main>
        <Plan view={view} isOpen={isMenuOpen} />
      </div>
    </CourseProvider>
  );
}
