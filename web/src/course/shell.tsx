import { useEffect, useLayoutEffect, useRef, useState, type ComponentType } from 'react';
import { Bar, useInert } from './bits';
import { isDone, lessonsOf, stepUrl, useCourse } from './context';
import { percent } from './core';
import { Icons, Logo } from './icons';
import { itemsOf, itemUrl, type Item, type ItemKind } from './items';
import { Cards, Help, Home, MapPage, Summary } from './pages';
import type { Step } from './types';

interface Tab { url: string; label: string; Icon: ComponentType; Page: ComponentType }
export const TABS: Tab[] = [
  { url: '#/', label: 'Обзор курса', Icon: Icons.home, Page: Home }, { url: '#/cards', label: 'Карточки', Icon: Icons.cards, Page: Cards }, { url: '#/summary', label: 'Конспект', Icon: Icons.summary, Page: Summary },
  { url: '#/map', label: 'Карта связей', Icon: Icons.map, Page: MapPage }, { url: '#/help', label: 'Помощь', Icon: Icons.help, Page: Help },
];
export interface View { step: Step | null; tab: string | null; item: ItemKind | null }

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

/** Шапка: знак, курс и книга, тема, путь в каталог. */
export function Top({ isMenuOpen, onMenu }: { isMenuOpen: boolean; onMenu: () => void }) {
  const { course, catalog } = useCourse();
  return (
    <header className="top">
      <button type="button" className="round menu" data-menu aria-expanded={isMenuOpen} aria-controls="outline" aria-label="Содержание курса" onClick={onMenu}><Icons.list /></button>
      <a className="logo" href={catalog || '#/'} target={catalog ? '_top' : undefined} aria-label={catalog ? 'Глава, все курсы' : 'Глава, обзор курса'}><Logo /><span>Глава</span></a>
      <span className="top-rule" aria-hidden />
      <a className="top-course" href="#/"><strong>{course.title}</strong><span>{course.book}</span></a>
      <div className="top-end"><ThemeToggle />{catalog && <a className="btn ghost" href={catalog} target="_top">Мои курсы</a>}</div>
    </header>
  );
}

/** «Курс › Модуль 5 › Урок 5.5 › Разбор»: последний шаг — текущая страница. */
export function Crumbs({ view, item }: { view: View; item: Item | null }) {
  const { course, num } = useCourse();
  const index = view.step ? course.parts.findIndex((p) => p.nodes.includes(view.step?.id ?? '')) : -1;
  const tab = TABS.find((t) => t.url === view.tab);
  const trail: [string, string | null][] = view.step
    ? [['Обзор курса', '#/'], ...(index >= 0 ? [[`Модуль ${index + 1}`, '#/'] as [string, string]] : []), [`Урок ${num(view.step)}`, stepUrl(view.step)], [item?.kind ?? '', null]]
    : [['Обзор курса', view.tab === '#/' ? null : '#/'], ...(view.tab !== '#/' && tab ? [[tab.label, null] as [string, null]] : [])];
  return (
    <nav className="crumbs" aria-label="Вы здесь"><ol>
      {trail.map(([label, url]) => <li key={label}>{url ? <a href={url}>{label}</a> : <span aria-current="page">{label}</span>}</li>)}
    </ol></nav>
  );
}

const ICON: Record<ItemKind, ComponentType> = { video: Icons.play, talk: Icons.play, read: Icons.book, sim: Icons.layers, quiz: Icons.cards };

function ItemRow({ step, item, view }: { step: Step; item: Item; view: View }) {
  const { state } = useCourse();
  const Icon = ICON[item.id];
  const isSeen = (state.seen[step.id] ?? []).includes(item.id);
  const isHere = view.step === step && view.item === item.id;
  return (
    <li><a className="item" href={itemUrl(step, item.id)} aria-current={isHere ? 'page' : undefined}>
      <span className={`item-icon${isSeen ? ' seen' : ''}`}>{isSeen ? <Icons.check /> : <Icon />}</span>
      <span className="item-text"><span>{item.title}</span><span className="item-meta">{item.kind} · {item.meta}{isSeen && <span className="sr">, просмотрено</span>}</span></span>
    </a></li>
  );
}

function Lesson({ step, view }: { step: Step; view: View }) {
  const { state, num } = useCourse();
  const isHere = view.step === step;
  const done = isDone(state, step);
  return (
    <li className={`lesson-row${isHere ? ' here' : ''}`}>
      <a className="lesson-link" href={stepUrl(step)} aria-current={isHere && !view.item ? 'page' : undefined}>
        <span className={`lesson-mark${done ? ' done' : ''}`} aria-hidden>{done ? <Icons.check /> : null}</span>
        <span>{num(step)} {step.short_title}{done && <span className="sr">, пройден</span>}</span><span className="time num">{step.minutes} мин</span>
      </a>
      {isHere && <ul className="items">{itemsOf(step).map((x) => <ItemRow key={x.id} step={step} item={x} view={view} />)}</ul>}
    </li>
  );
}

/** Содержание слева: разделы курса и модули с уроками; у открытого урока видны его элементы. */
export function Outline({ view, isOpen, isInert }: { view: View; isOpen: boolean; isInert: boolean }) {
  const { course, state, catalog } = useCourse();
  const ref = useInert<HTMLElement>(isInert);
  const path = useRef<HTMLDivElement>(null);
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
    const row = path.current?.querySelector('.lesson-row.here')?.getBoundingClientRect();
    const box = path.current?.getBoundingClientRect();
    if (path.current && row && box && (row.top < box.top || row.bottom > box.bottom)) path.current.scrollTop += row.top - box.top - box.height / 4;
  }, [view.step, isOpen]);
  useEffect(() => { if (isOpen) path.current?.querySelector<HTMLElement>('[aria-current], summary')?.focus({ preventScroll: true }); }, [isOpen]);
  const share = percent(state.done.length, course.steps.length);
  return (
    <aside className={`outline${isOpen ? ' open' : ''}`} id="outline" aria-label="Содержание курса" ref={ref}>
      <div className="outline-scroll" ref={path}>
        <div className="outline-progress"><p><strong>Прогресс курса</strong><span className="num">{share}%</span></p><Bar share={share} /><p className="muted">Пройдено уроков: {state.done.length} из {course.steps.length}</p></div>
        <nav className="tabs" aria-label="Разделы">{TABS.map(({ url, label, Icon }) => <a key={url} href={url} aria-current={!view.step && view.tab === url ? 'page' : undefined}><Icon /><span>{label}</span></a>)}
          {catalog && <a href={catalog} target="_top"><Icons.exit /><span>Все курсы</span></a>}</nav>
        <nav className="modules-nav" aria-label="Модули и уроки">
          {course.parts.map((p, i) => {
            const list = lessonsOf(course, p);
            const count = list.filter((s) => isDone(state, s)).length;
            return (
              <details key={p.title} className="module-block" data-part={i} open={open.has(i)} onToggle={(e) => toggle(i, e.currentTarget.open)}>
                <summary><span className="module-name"><span className="module-no">Модуль {i + 1}</span>{p.title}</span><span className="module-count num">{count}/{list.length}</span><Icons.down /></summary>
                <ul>{list.map((s) => <Lesson key={s.id} step={s} view={view} />)}</ul>
              </details>
            );
          })}
        </nav>
      </div>
    </aside>
  );
}
