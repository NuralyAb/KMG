import { useEffect, useLayoutEffect, useRef, useState, type KeyboardEvent, type ReactNode } from 'react';
import { Pages, Rich } from './bits';
import { stepUrl, useCourse } from './context';
import { Icons } from './icons';
import { PictureFigure } from './PictureFigure';
import { BlockSection, blocksOf, Essence, type Block, type TabId } from './sections';
import { Stage } from './Stage';
import type { Step } from './types';

const TABS: [TabId, string][] = [['about', 'Описание'], ['data', 'Формулы и данные'], ['tasks', 'Задания'], ['source', 'Источник'], ['notes', 'Заметки']];

/** Скрытая вкладка остаётся доступной поиску браузера: hidden="until-found", его React 18 сам не умеет. */
function Panel({ id, isOpen, onFound, children }: { id: TabId; isOpen: boolean; onFound: () => void; children: ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);
  useLayoutEffect(() => { if (isOpen) ref.current?.removeAttribute('hidden'); else ref.current?.setAttribute('hidden', 'until-found'); }, [isOpen]);
  useEffect(() => {
    const el = ref.current;
    el?.addEventListener('beforematch', onFound);
    return () => el?.removeEventListener('beforematch', onFound);
  });
  return <div className="panel column" role="tabpanel" id={`panel-${id}`} aria-labelledby={`tab-${id}`} data-panel={id} ref={ref}>{children}</div>;
}

function Advice({ step, blocks }: { step: Step; blocks: Block[] }) {
  if (step.format === 'карточки') return <p><a href="#/cards">Этот урок удобно закрепить карточками</a></p>;
  if (step.format === 'практикум на данных' && blocks.some((b) => b.id === 'decision')) return <p><a href={stepUrl(step, 'decision')}>Главное в этом уроке — решение на данных</a></p>;
  return null;
}

function Practice({ step, onOpen }: { step: Step; onOpen: () => void }) {
  const { state } = useCourse();
  if (!step.tasks.length) return null;
  const left = step.tasks.filter((t) => state.solved[t.id] !== true).length;
  return (
    <div className="callout noprint">
      <p><strong>{left ? 'Проверьте себя' : 'Задания решены'}</strong><br /><span className="muted">{left ? `Осталось заданий: ${left}` : 'Можно идти дальше'}</span></p>
      <button type="button" className="btn" onClick={onOpen}>К заданиям</button>
    </div>
  );
}

function Notes({ step }: { step: Step }) {
  const { store, state } = useCourse();
  return (
    <section className="block" id="notes">
      <h2 tabIndex={-1}>Мои заметки</h2><label className="muted" htmlFor="note">Сохраняются только в этом браузере</label>
      <textarea id="note" rows={8} placeholder="Что запомнить или уточнить" value={state.notes[step.id] ?? ''} onChange={(e) => store.set({ notes: { ...state.notes, [step.id]: e.currentTarget.value } })} />
    </section>
  );
}

const Why = ({ step }: { step: Step }) => (
  <section className="block">
    <details><summary>Почему этот урок здесь и в таком формате</summary><p><Rich text={step.why_here?.text} /></p>{step.format && <p>Формат по маршруту: {step.format}. <Rich text={step.format_why} /></p>}</details>
    <p><a href="#/help">Что значат пометки «автор» и «модель»</a></p>
  </section>
);

/** section и visit приходят из адреса: ссылка на раздел открывает его вкладку, даже если нажата второй раз. */
export function Lesson({ step, section, visit }: { step: Step; section: string | null; visit: number }) {
  const { course, num, store } = useCourse();
  const blocks = blocksOf(step);
  const tabOf = (id: string | null): TabId | undefined => (id === 'notes' ? 'notes' : id?.startsWith('claim-') ? 'source' : id === 'essence' ? 'about' : blocks.find((b) => b.id === id)?.tab);
  const [tab, setTab] = useState<TabId>(() => tabOf(section) ?? 'about');
  const [seen, setSeen] = useState(visit);
  if (seen !== visit) {
    setSeen(visit);
    setTab(tabOf(section) ?? tab);
  }
  const list = useRef<HTMLDivElement>(null);
  const i = course.steps.indexOf(step);
  const [prev, next] = [course.steps[i - 1], course.steps[i + 1]];
  const of = (id: TabId): ReactNode => blocks.filter((b) => b.tab === id).map((b) => <BlockSection key={b.id} block={b} />);

  const select = (id: TabId, focus = false): void => {
    setTab(id);
    const button = list.current?.querySelector<HTMLElement>(`[data-tab="${id}"]`);
    if (focus) button?.focus({ preventScroll: true });
    button?.scrollIntoView({ block: 'nearest', inline: 'nearest' });
  };
  const openTasks = (): void => { select('tasks', true); list.current?.scrollIntoView(); };
  const filled = TABS.filter(([id]) => id === 'about' || id === 'source' || id === 'notes' || blocks.some((b) => b.tab === id));
  const onKey = (e: KeyboardEvent): void => {
    const at = filled.findIndex(([id]) => id === tab);
    const to = { ArrowRight: at + 1, ArrowLeft: at - 1, Home: 0, End: filled.length - 1 }[e.key];
    const found = to === undefined ? undefined : filled[(to + filled.length) % filled.length];
    if (!found) return;
    e.preventDefault();
    select(found[0], true);
  };
  const body: Record<TabId, ReactNode> = {
    about: <><Essence step={step} />{step.pictures.map((p) => <PictureFigure key={p.id} picture={p} />)}<Advice step={step} blocks={blocks} />{of('about')}<Practice step={step} onOpen={openTasks} /></>,
    data: of('data'), tasks: of('tasks'), source: <>{of('source')}<Why step={step} /></>, notes: <Notes step={step} />,
  };
  const finish = (): void => {
    store.set({ done: [...new Set([...store.get().done, step.id])] });
    location.hash = next ? stepUrl(next) : '#/';
  };
  return (
    <article className="lesson">
      <header><h1 tabIndex={-1}>Урок {num(step)}: {step.short_title || step.title}</h1><p className="muted">{step.title}<Pages list={step.pages} /> ·&nbsp;{step.minutes}&nbsp;мин{step.threshold && ' · пороговая идея'}</p></header>
      <Stage step={step} onTasks={openTasks} />
      <div className="panels">
        <div className="lesson-tabs" role="tablist" aria-label="Разделы урока" ref={list} onKeyDown={onKey}>
          {filled.map(([id, label]) => (
            <button key={id} type="button" role="tab" id={`tab-${id}`} aria-controls={`panel-${id}`} aria-selected={id === tab} tabIndex={id === tab ? 0 : -1} data-tab={id} onClick={() => select(id)}>
              {label}{id === 'tasks' && step.tasks.length > 0 && <> <span className="count num">{step.tasks.length}</span></>}
            </button>
          ))}
        </div>
        {filled.map(([id]) => <Panel key={id} id={id} isOpen={id === tab} onFound={() => setTab(id)}>{body[id]}</Panel>)}
      </div>
      <footer className="row noprint">
        {prev ? <a className="btn" href={stepUrl(prev)}><Icons.left />Назад</a> : <span />}
        <button type="button" className="btn main" data-done={step.id} onClick={finish}>{next ? <>Понятно, дальше<Icons.right /></> : 'Завершить курс'}</button>
      </footer>
    </article>
  );
}
