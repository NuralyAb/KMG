import { useEffect, type ReactNode } from 'react';
import { Pages, Rich, Bar } from './bits';
import { stepUrl, useCourse } from './context';
import { Icons } from './icons';
import { itemFor, itemsOf, itemUrl, type Item } from './items';
import { PictureFigure } from './PictureFigure';
import { Scene } from './Scene';
import { BlockSection, blocksOf, Essence, type Block } from './sections';
import type { Step } from './types';
import { VideoPlayer } from './VideoPlayer';

function Notes({ step }: { step: Step }) {
  const { store, state } = useCourse();
  return (
    <section className="block" id="notes">
      <h2 tabIndex={-1}>Мои заметки</h2><label className="muted" htmlFor="note">Сохраняются только в этом браузере</label>
      <textarea id="note" rows={6} placeholder="Что запомнить или уточнить" value={state.notes[step.id] ?? ''} onChange={(e) => store.set({ notes: { ...state.notes, [step.id]: e.currentTarget.value } })} />
    </section>
  );
}

function Advice({ step, blocks }: { step: Step; blocks: Block[] }) {
  if (step.format === 'карточки') return <p><a href="#/cards">Этот урок удобно закрепить карточками</a></p>;
  if (step.format === 'практикум на данных' && blocks.some((b) => b.id === 'decision')) return <p><a href={stepUrl(step, 'decision')}>Главное в этом уроке — решение на данных</a></p>;
  return null;
}

const Why = ({ step }: { step: Step }) => (
  <section className="block">
    <details><summary>Почему этот урок здесь и в таком формате</summary><p><Rich text={step.why_here?.text} /></p>{step.format && <p>Формат по маршруту: {step.format}. <Rich text={step.format_why} /></p>}</details>
    <p><a href="#/help">Что значат пометки «автор» и «модель»</a></p>
  </section>
);

/** Чтение: суть, схема, объяснение, формулы и данные, источник с цитатами — одной статьёй. */
function Reading({ step, hasNotes }: { step: Step; hasNotes: boolean }) {
  const blocks = blocksOf(step);
  const { store, state } = useCourse();
  const of = (...tabs: string[]): ReactNode => blocks.filter((b) => tabs.includes(b.tab)).map((b) => <BlockSection key={b.id} block={b} />);
  return (
    <div className="column reading">
      <div className="view-toggle">
        <button type="button" className="link-button" aria-pressed={state.full} onClick={() => store.set({ full: !state.full })}>{state.full ? 'Короткий вид' : 'Показать всё'}</button>
      </div>
      <Essence step={step} />
      {step.pictures.map((p) => <PictureFigure key={p.id} picture={p} />)}
      <Advice step={step} blocks={blocks} />
      {of('about', 'data')}
      <details className="source"><summary>Источник: мысли автора с цитатами и что сверить со сканом</summary><div className="column">{of('source')}</div></details>
      <Why step={step} />
      {hasNotes && <Notes step={step} />}
    </div>
  );
}

function Quiz({ step }: { step: Step }) {
  const { state } = useCourse();
  const solved = step.tasks.filter((t) => state.solved[t.id] === true).length;
  return (
    <div className="column">
      {step.tasks.length > 0 && <div className="quiz-head"><p><strong>Решено {solved} из {step.tasks.length}</strong><span className="muted">Ответ проверяется сразу, после проверки видно пояснение и страницу книги</span></p><Bar share={Math.round((solved / step.tasks.length) * 100)} /></div>}
      {blocksOf(step).filter((b) => b.tab === 'tasks').map((b) => <BlockSection key={b.id} block={b} />)}
    </div>
  );
}

function Body({ step, item, onDone }: { step: Step; item: Item; onDone: () => void }) {
  if (item.id === 'video') return <><div className="stage">{step.videos.map((v) => <figure key={v.src}><VideoPlayer video={v} /><figcaption>{v.label && <span className="chip">{v.label}</span>} {v.title}</figcaption></figure>)}</div><Notes step={step} /></>;
  if (item.id === 'talk' && step.narration) return <><Scene step={step} narration={step.narration} onDone={onDone} /><Notes step={step} /></>;
  // содержимое этого узла рисует assets/simulation.js: контракт — data-interactive и data-params
  if (item.id === 'sim' && step.interactive) return <div className="stage"><div className="screen sims" data-interactive={step.interactive.kind} data-params={JSON.stringify(step.interactive.params ?? {})} /></div>;
  if (item.id === 'quiz') return <Quiz step={step} />;
  return <Reading step={step} hasNotes={!itemsOf(step).some((x) => x.id === 'talk' || x.id === 'video')} />;
}

/** Шаги урока над содержанием: видно, где вы и что впереди. */
function Stepper({ step, items, at }: { step: Step; items: Item[]; at: number }) {
  const { state } = useCourse();
  const seen = state.seen[step.id] ?? [];
  if (items.length < 2) return null;
  return (
    <nav className="stepper noprint" aria-label="Элементы урока"><ol>
      {items.map((x, i) => {
        const isSeen = seen.includes(x.id) && i !== at;
        return (
          <li key={x.id} className={i === at ? 'now' : isSeen ? 'seen' : undefined}>
            <a href={itemUrl(step, x.id)} aria-current={i === at ? 'step' : undefined}>
              <span className="stepper-dot" aria-hidden>{isSeen ? <Icons.check /> : i + 1}</span>
              <span className="stepper-text"><span>{x.kind}</span><span className="stepper-meta">{x.meta}{isSeen && <span className="sr">, просмотрено</span>}</span></span>
            </a>
          </li>
        );
      })}
    </ol></nav>
  );
}

/** Страница элемента урока: что это, сколько займёт, само содержание и переход к следующему элементу. */
export function Lesson({ step, section }: { step: Step; section: string | null }) {
  const { course, num, store } = useCourse();
  const items = itemsOf(step);
  const item = itemFor(step, section);
  const at = items.findIndex((x) => x.id === item.id);
  const i = course.steps.indexOf(step);
  const [prev, next] = [course.steps[i - 1], course.steps[i + 1]];
  const nextItem = items[at + 1];
  const prevItem = items[at - 1];
  const prevStep = prev && itemsOf(prev).at(-1);

  useEffect(() => {
    const seen = store.get().seen[step.id] ?? [];
    if (!seen.includes(item.id)) store.set({ seen: { ...store.get().seen, [step.id]: [...seen, item.id] } });
  }, [store, step.id, item.id]);
  const finish = (): void => {
    store.set({ done: [...new Set([...store.get().done, step.id])] });
    location.hash = next ? stepUrl(next) : '#/';
  };
  const forward = (): void => { if (nextItem) location.hash = itemUrl(step, nextItem.id); else finish(); };
  const back = prevItem ? itemUrl(step, prevItem.id) : prev && prevStep ? itemUrl(prev, prevStep.id) : null;

  return (
    <article className="lesson" data-item={item.id}>
      <header className="item-head">
        <p className="item-kind"><span className="kicker">Урок {num(step)}</span>{item.kind}<span aria-hidden> · </span>{item.meta}{step.threshold && <span className="kicker key">пороговая идея</span>}</p>
        <h1 tabIndex={-1}>{item.id === 'read' ? item.title : `${item.title}: ${step.short_title}`}</h1>
        <p className="muted">{step.title}<Pages list={step.pages} /></p>
      </header>
      <Stepper step={step} items={items} at={at} />
      <Body step={step} item={item} onDone={forward} />
      <footer className="item-foot noprint">
        {back ? <a className="btn" href={back}><Icons.left />Назад</a> : <span />}
        <div className="item-next">
          {nextItem && <button type="button" className="btn ghost" data-done={step.id} onClick={finish}>Отметить урок пройденным</button>}
          <button type="button" className="btn main" data-next onClick={forward}>{nextItem ? <>Дальше: {nextItem.kind.toLowerCase()}<Icons.right /></> : next ? <>Урок пройден, дальше<Icons.right /></> : 'Завершить курс'}</button>
        </div>
      </footer>
    </article>
  );
}
