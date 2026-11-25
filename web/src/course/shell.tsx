import { useEffect, useLayoutEffect, useRef, useState, type ComponentType } from 'react';
import { Bar, useInert } from './bits';
import { isDone, lessonsOf, stepUrl, useCourse } from './context';
import { percent, splitBook } from './core';
import { Icons, Logo, Mark } from './icons';
import { Cards, Help, Home, MapPage, Summary } from './pages';
import type { Step } from './types';

interface Tab { url: string; label: string; Icon: ComponentType; Page: ComponentType }
export const TABS: Tab[] = [
  { url: '#/', label: 'Курс', Icon: Icons.home, Page: Home }, { url: '#/cards', label: 'Карточки', Icon: Icons.cards, Page: Cards }, { url: '#/summary', label: 'Конспект', Icon: Icons.summary, Page: Summary },
  { url: '#/map', label: 'Карта связей', Icon: Icons.map, Page: MapPage }, { url: '#/help', label: 'Помощь', Icon: Icons.help, Page: Help },
];
export interface View { step: Step | null; tab: string | null }

const current = (url: string, { step, tab }: View): 'true' | 'page' | undefined => (step ? (url === '#/' ? 'true' : undefined) : tab === url ? 'page' : undefined);

export function Side({ view, isInert }: { view: View; isInert: boolean }) {
  const { catalog } = useCourse();
  const ref = useInert<HTMLElement>(isInert);
  return (
    <aside className="side" aria-label="Разделы курса" ref={ref}>
      <a className="logo" href="#/" aria-label="Глава, начало курса"><Logo /><span>ГЛАВА</span></a>
      <nav className="tabs" aria-label="Разделы">{TABS.slice(0, 4).map(({ url, label, Icon }) => <a key={url} href={url} aria-current={current(url, view)}><Icon /><span>{label}</span></a>)}</nav>
      <div className="side-foot">
        <a href="#/help" aria-current={current('#/help', view)}><Icons.help /><span>Помощь</span></a>
        {catalog && <a href={catalog} target="_top"><Icons.exit /><span>Все курсы</span></a>}
      </div>
    </aside>
  );
}

const SYSTEM_DARK = '(prefers-color-scheme: dark)';
function ThemeToggle() {
  const { store, state } = useCourse();
  const [isSystemDark, setSystemDark] = useState(() => matchMedia(SYSTEM_DARK).matches);
  useEffect(() => {
    const media = matchMedia(SYSTEM_DARK);
    const changed = (): void => setSystemDark(media.matches);
    media.addEventListener('change', changed);
    return () => media.removeEventListener('change', changed);
  }, []);
  useLayoutEffect(() => { document.documentElement.dataset.theme = state.theme; }, [state.theme]);
  const isDark = state.theme === 'dark' || (state.theme === 'auto' && isSystemDark);
  return <button type="button" className="round" data-theme-toggle aria-label={isDark ? 'Включить светлую тему' : 'Включить тёмную тему'} onClick={() => store.set({ theme: isDark ? 'light' : 'dark' })}>{isDark ? <Icons.sun /> : <Icons.moon />}</button>;
}

export function Top({ view, isMenuOpen, onMenu }: { view: View; isMenuOpen: boolean; onMenu: () => void }) {
  const { course, catalog, num } = useCourse();
  const here = view.step ? `${num(view.step)} ${view.step.short_title}` : TABS.find((t) => t.url === view.tab)?.label;
  return (
    <header className="top">
      <nav className="crumbs" aria-label="Вы здесь"><ol>
        {catalog && <li className="crumb-all"><a href={catalog} target="_top">Мои курсы</a></li>}
        {view.tab !== '#/' && <li className="crumb-course"><a href="#/">{course.title}</a></li>}
        <li className="crumb-here"><span aria-current="page">{view.tab === '#/' && catalog ? course.title : here}</span></li>
      </ol></nav>
      <div className="top-end">
        <ThemeToggle />
        <button type="button" className="btn menu" data-menu aria-expanded={isMenuOpen} aria-controls="plan" onClick={onMenu}><Icons.list /><span>Содержание</span></button>
      </div>
    </header>
  );
}

function PlanPart({ index, isOpen, onToggle, view }: { index: number; isOpen: boolean; onToggle: (open: boolean) => void; view: View }) {
  const { course, state, num } = useCourse();
  const part = course.parts[index];
  if (!part) return null;
  return (
    <details className="part" data-part={index} open={isOpen} onToggle={(e) => onToggle(e.currentTarget.open)}>
      <summary><span>{index + 1}. {part.title}</span><Icons.down /></summary>
      <ul>{lessonsOf(course, part).map((s) => {
        const done = isDone(state, s);
        return (
          <li key={s.id}><a href={stepUrl(s)} aria-current={s === view.step ? 'page' : undefined}>
            <Mark state={s === view.step ? 'now' : done ? 'done' : 'todo'} /><span>{num(s)} {s.short_title}{done && <span className="sr">, пройден</span>}</span><span className="time num">{s.minutes} мин</span>
          </a></li>
        );
      })}</ul>
    </details>
  );
}

/** Содержание справа; на узком экране открывается поверх страницы. */
export function Plan({ view, isOpen }: { view: View; isOpen: boolean }) {
  const { course, state } = useCourse();
  const book = splitBook(course.book);
  const path = useRef<HTMLElement>(null);
  const at = view.step ?? course.steps.find((s) => s.order === state.last) ?? course.steps[0];
  const mine = course.parts.findIndex((p) => at !== undefined && p.nodes.includes(at.id));
  // раскрытые модули помнятся до закрытия страницы; модуль текущего урока раскрывается сам
  const [open, setOpen] = useState<ReadonlySet<number>>(() => new Set([mine]));
  const [seen, setSeen] = useState(at?.id);
  if (seen !== at?.id) {
    setSeen(at?.id);
    setOpen(new Set([...open, mine]));
  }
  const toggle = (i: number, on: boolean): void => setOpen((was) => { const next = new Set(was); if (on) next.add(i); else next.delete(i); return next; });

  useLayoutEffect(() => {
    const row = path.current?.querySelector('[aria-current]')?.getBoundingClientRect();
    const box = path.current?.getBoundingClientRect();
    if (path.current && row && box && (row.top < box.top || row.bottom > box.bottom)) path.current.scrollTop += row.top - box.top - box.height / 3;
  }, [view.step, isOpen]);
  useEffect(() => { if (isOpen) path.current?.querySelector<HTMLElement>('[aria-current], summary')?.focus({ preventScroll: true }); }, [isOpen]);

  const share = percent(state.done.length, course.steps.length);
  return (
    <aside className={`plan${isOpen ? ' open' : ''}`} id="plan" aria-label="Содержание курса">
      <div className="plan-card"><span className="plan-icon"><Icons.layers /></span><p className="plan-title">{course.title}</p><p className="plan-share num">Пройдено {share}%, {state.done.length} из {course.steps.length}</p><Bar share={share} /></div>
      <nav className="path" aria-label="Уроки по модулям" ref={path}>{course.parts.map((p, i) => <PlanPart key={p.title} index={i} view={view} isOpen={open.has(i)} onToggle={(on) => toggle(i, on)} />)}</nav>
      <a className="plan-help" href="#/help"><Icons.help />Помощь</a>
      <a className="author" href="#/"><span className="avatar" aria-hidden>{book.initials || <Icons.book />}</span><span className="author-text"><strong>{book.author || 'Книга'}</strong><span className="muted">{book.title}</span></span><Icons.right /></a>
    </aside>
  );
}
