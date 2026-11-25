import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';
import { Bar, Pages, Rich } from './bits';
import { isDone, lessonsOf, stepUrl, useCourse } from './context';
import { arcDepth, edges, nextCard, percent, rateCard, type CardMark } from './core';
import { Icons } from './icons';
import { Results } from './Results';
import type { Part, Step } from './types';

const sum = (list: number[]): number => list.reduce((a, b) => a + b, 0);

function Module({ part, index }: { part: Part; index: number }) {
  const { course, state } = useCourse();
  const list = lessonsOf(course, part);
  const count = list.filter((s) => isDone(state, s)).length;
  const go = list.find((s) => !isDone(state, s)) ?? list[0];
  if (!go) return null;
  return (
    <li><a className="module" href={stepUrl(go)}>
      <span className="module-mark num" aria-hidden>{index + 1}</span><strong>{part.title}</strong><span className="muted">Уроков: {list.length} · {sum(list.map((s) => s.minutes))} мин</span>
      <Bar share={percent(count, list.length)} /><span className="muted">Пройдено {count} из {list.length}</span>
    </a></li>
  );
}

export function Home() {
  const { course, state, num } = useCourse();
  const resume = course.steps.find((s) => s.order === state.last) ?? course.steps[0];
  const facts = [['Уроков', course.steps.length], ['Минут', sum(course.steps.map((s) => s.minutes))], ['Заданий', sum(course.steps.map((s) => s.tasks.length))]] as const;
  const isFinished = percent(state.done.length, course.steps.length) === 100;
  return (
    <div className="lesson">
      <header><h1 tabIndex={-1}>{course.title}</h1><p className="muted">{course.book}</p></header>
      {resume && (
        <section className="hero">
          <div><p>{isFinished ? 'Курс пройден' : state.last ? 'Вы остановились здесь' : 'Начните с первого урока'}</p><h2>Урок {num(resume)}: {resume.short_title}</h2></div>
          <a className="btn" href={stepUrl(resume)}>{state.last ? 'Продолжить' : 'Начать'}<Icons.right /></a>
          <dl className="hero-facts">{facts.map(([word, value]) => <div key={word}><dt>{word}</dt><dd className="num">{value}</dd></div>)}</dl>
        </section>
      )}
      <section className="block"><h2>Модули</h2><ul className="modules">{course.parts.map((p, i) => <Module key={p.title} part={p} index={i} />)}</ul></section>
      <p className="muted">Каждый абзац ведёт на страницу книги. Учебный слой собран моделью {course.generated_by}; цитаты и числа проверены кодом по страницам главы.</p>
    </div>
  );
}

function Flash({ step }: { step: Step }) {
  const { store, num } = useCourse();
  const [isOpen, setOpen] = useState(false);
  const answer = useRef<HTMLParagraphElement>(null);
  useEffect(() => { if (isOpen) answer.current?.focus(); }, [isOpen]);
  const flip = (): void => { if (!String(getSelection())) setOpen(true); };
  const rate = (mark: CardMark): void => store.set(rateCard(store.get(), step.id, mark));
  return (
    <>
      <div className="flash" data-flash onClick={flip}>
        <h2 tabIndex={-1}>{num(step)} {step.short_title}</h2>
        {isOpen ? <p className="lead" tabIndex={-1} ref={answer}><Rich text={step.essence} /><Pages list={step.pages} /></p> : <p className="muted">Вспомните суть, потом откройте ответ</p>}
      </div>
      {isOpen
        ? <><div className="row"><button type="button" className="btn" data-know="again" onClick={() => rate('again')}>Повторить</button><button type="button" className="btn main" data-know="know" onClick={() => rate('know')}>Знаю</button></div><p><a href={stepUrl(step)}>Открыть урок</a></p></>
        : <div className="row"><button type="button" className="btn main" data-flip onClick={() => setOpen(true)}>Показать ответ</button></div>}
    </>
  );
}

export function Cards() {
  const { course, store, state } = useCourse();
  const ids = course.steps.map((s) => s.id);
  const step = course.steps.find((s) => s.id === nextCard(ids, state));
  const count = (mark: CardMark): number => ids.filter((id) => state.cards[id] === mark).length;
  // одна и та же карточка может выпасть на повтор снова: ключ меняется с каждой оценкой
  const [turn, setTurn] = useState({ cards: state.cards, n: 0 });
  if (turn.cards !== state.cards) setTurn({ cards: state.cards, n: turn.n + 1 });
  const root = useRef<HTMLDivElement>(null);
  useEffect(() => { if (turn.n > 0) (root.current?.querySelector<HTMLElement>('.flash h2') ?? root.current?.querySelector('h1'))?.focus({ preventScroll: true }); }, [turn.n]);
  return (
    <div className="column" ref={root}>
      <h1 tabIndex={-1}>Карточки</h1>
      {step
        ? <><p className="muted">Осталось {ids.length - count('know')} из {ids.length}, из них на повтор: {count('again')}</p><Flash key={turn.n} step={step} /></>
        : <><p className="lead">Все карточки отмечены «знаю».</p><div><button type="button" className="btn" onClick={() => store.set({ cards: {}, repeat: [] })}>Повторить все</button></div></>}
    </div>
  );
}

export function Summary() {
  const { course, num } = useCourse();
  return (
    <div className="column summary">
      <div className="row"><h1 tabIndex={-1}>Конспект</h1><button type="button" className="btn noprint" onClick={() => window.print()}>Печать в PDF</button></div>
      <p className="muted">{course.title}. {course.book}</p>
      {course.parts.map((p) => (
        <section key={p.title} className="block"><h2>{p.title}</h2>
          {lessonsOf(course, p).map((s) => (
            <div key={s.id} className="card"><h3>{num(s)} {s.short_title}</h3><p><Rich text={s.essence} /><Pages list={s.pages} /></p>
              {s.data_meaning && <><p><strong>Вывод для данных.</strong> <Rich text={s.data_meaning.from_chapter.text} /></p><p><strong>Где ломается.</strong> <Rich text={s.data_meaning.breaks.text} /></p></>}
            </div>
          ))}
        </section>
      ))}
    </div>
  );
}

interface Drawing { x: number; height: number; width: number; rows: Map<number, number> }
const DOT_FROM_TOP = 22;

/** Дуги рисуются по местам строк: названия переносятся, поэтому высота строк разная. */
function useDrawing(root: React.RefObject<HTMLDivElement | null>): Drawing | null {
  const [drawing, setDrawing] = useState<Drawing | null>(null);
  const measure = useCallback(() => {
    const el = root.current;
    if (!el) return;
    const top = el.getBoundingClientRect().top;
    const rows = new Map([...el.querySelectorAll<HTMLElement>('[data-node]')].map((li) => [Number(li.dataset.node), li.getBoundingClientRect().top - top + DOT_FROM_TOP]));
    const width = parseFloat(getComputedStyle(el).paddingLeft);
    setDrawing({ x: width - 14, width, height: el.clientHeight, rows });
  }, [root]);
  useLayoutEffect(() => {
    measure();
    void document.fonts?.ready.then(measure);
    window.addEventListener('resize', measure);
    return () => window.removeEventListener('resize', measure);
  }, [measure]);
  return drawing;
}

export function MapPage() {
  const { course, num } = useCourse();
  const root = useRef<HTMLDivElement>(null);
  const [here, setHere] = useState<number | null>(null);
  const drawing = useDrawing(root);
  const links = edges(course.steps);
  const touching = links.filter(([a, b]) => a.order === here || b.order === here);
  const near = new Set(touching.flatMap(([a, b]) => [a.order, b.order]));
  const light = (target: EventTarget): void => {
    const li = (target as Element).closest<HTMLElement>('[data-node]');
    if (li) setHere(Number(li.dataset.node));
  };
  const arc = ([a, b]: [Step, Step], d: Drawing): string => {
    const bend = d.x - arcDepth(b.order - a.order, course.steps.length - 1, d.x - 2) * 4 / 3;
    const [from, to] = [d.rows.get(a.order) ?? 0, d.rows.get(b.order) ?? 0];
    return `M${d.x},${from} C${bend},${from} ${bend},${to} ${d.x},${to}`;
  };
  // выделенная дуга — поверх остальных
  const drawn = [...links.filter((l) => !touching.includes(l)), ...touching];
  const supports = (s: Step): Step[] => links.filter(([, b]) => b === s).map(([a]) => a).sort((a, b) => a.order - b.order);
  return (
    <div className="column wide">
      <header className="block"><h1 tabIndex={-1}>Карта связей</h1><p className="muted">Дуга ведёт от урока-опоры к уроку, который на него опирается. Наведите, нажмите на строку или перейдите клавишей Tab: связи урока выделятся.</p></header>
      <div className="map" ref={root} onPointerOver={(e) => light(e.target)} onFocus={(e) => light(e.target)} onClick={(e) => light(e.target)}>
        <svg aria-hidden width={drawing?.width ?? 0} height={drawing?.height ?? 0}>
          {drawing && drawn.map((l) => <path key={`${l[0].order}-${l[1].order}`} className={touching.includes(l) ? 'on' : undefined} d={arc(l, drawing)} />)}
          {drawing && [...drawing.rows].map(([order, y]) => <circle key={order} className={near.has(order) ? 'near' : undefined} cx={drawing.x} cy={y} r={6} />)}
        </svg>
        {course.parts.map((p) => [
          <h2 key={p.title}>{p.title}</h2>,
          <ul key={`${p.title}-list`}>{lessonsOf(course, p).map((s) => (
            <li key={s.id} data-node={s.order} className={`${near.has(s.order) ? 'near' : ''}${here === s.order ? ' here' : ''}`}>
              <a className="map-step" href={stepUrl(s)}>{num(s)} {s.short_title}</a>
              <span className="muted map-links">{supports(s).length === 0 ? 'начало пути' : <>опирается на {supports(s).map((a) => <span key={a.id}><a href={stepUrl(a)} aria-label={`урок ${num(a)}: ${a.short_title}`}>{num(a)}</a> </span>)}</>}</span>
            </li>
          ))}</ul>,
        ])}
      </div>
    </div>
  );
}

const LEGEND = [
  ['chip who author', 'автор', 'Мысль, число или пример из книги; у каждой мысли раскрывается дословная цитата.'],
  ['chip who model', 'модель', 'Пересказ, пояснение или аналогия, написанные моделью по мыслям автора. Если они расходятся с цитатой, верьте цитате.'],
  ['chip', 'наблюдение', 'Автор сообщает факт или правило измерения.'],
  ['chip', 'вывод', 'Автор выводит это из других фактов.'],
  ['chip', 'допущение', 'Верно только при названном условии или принято для задачи.'],
  ['chip', 'сверить со сканом', 'Текст страницы распознан с потерями или описан по рисунку, поэтому деталь стоит проверить по книге.'],
  ['', 'стр. N', 'Страница книги по файлу PDF, с которой взят абзац.'],
] as const;

export const Help = () => (
  <div className="column">
    <h1 tabIndex={-1}>Помощь</h1>
    <section className="block"><h2>Кто это написал и что значат пометки</h2><dl className="legend">{LEGEND.map(([look, name, text]) => <div key={name}><dt><span className={look}>{name}</span></dt><dd>{text}</dd></div>)}</dl></section>
    <section className="block"><h2>Прогресс</h2><p>Урок считается пройденным после кнопки «Понятно, дальше». Прогресс, ответы и заметки хранятся только в этом браузере.</p></section>
    <Results />
  </div>
);
