import { useEffect, useMemo, useRef, useState, type KeyboardEvent, type MouseEvent, type ReactNode } from 'react';
import { Chip, Html, Items, Pages, Rich, WhoChip, type Who } from './bits';
import { useCourse } from './context';
import { claimAnchor, markTerms, plural, splitLead, symbol, tableRows, teaser, texOnly } from './core';
import { say } from './store';
import { TaskCard } from './TaskCard';
import type { BookTable, Claim, Formula, Step } from './types';

export type TabId = 'about' | 'data' | 'tasks' | 'source' | 'notes';
/** open — блок виден сразу; остальные в коротком виде свёрнуты, а hint говорит, что внутри. */
export interface Block { id: string; tab: TabId; title: string; who: Who | null; tone?: 'bad' | 'brand' | 'warn'; body: ReactNode; open?: boolean; hint?: string }

const KIND: Record<string, string> = { observation: 'наблюдение', inference: 'вывод', assumption: 'допущение' };
const byModel = (field?: { by_model?: boolean } | null): Who => (field?.by_model === false ? 'author' : 'model');

const SHOWN = 2;

/** Свёрнутый кусок: заголовок и что внутри. Ссылка на блок раскрывает его сама (App.toSection). */
export function Fold({ title, hint, full, children, id }: { title: ReactNode; hint?: ReactNode; full: boolean; children: ReactNode; id?: string }) {
  return (
    <details className="fold" id={id} open={full || undefined}>
      <summary><span className="fold-title">{title}</span>{hint && <span className="hint">{hint}</span>}</summary>
      <div className="fold-body">{children}</div>
    </details>
  );
}

export function Essence({ step }: { step: Step }) {
  const [first, rest] = splitLead(step.essence);
  return <section className="block" id="essence"><h2 className="sr" tabIndex={-1}>Суть</h2><p className="lead"><strong><Rich text={first} /></strong> <Rich text={rest} /><Pages list={step.pages} /> <WhoChip who="model" /></p></section>;
}

/** Абзацы объяснения. Термин отмечен внутри текста; по нажатию под абзацем открывается определение. */
function How({ step }: { step: Step }) {
  const { rich, state } = useCourse();
  const full = state.full;
  const root = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState<number | null>(null);
  const marked = useMemo(() => markTerms(step.how.flatMap((b) => b.paragraphs.map((p) => p.text)), step.glossary), [step]);
  useEffect(() => {
    root.current?.querySelectorAll<HTMLElement>('.term').forEach((x) => x.setAttribute('aria-expanded', String(Number(x.dataset.term) === open)));
  }, [open]);
  const toggle = (e: MouseEvent | KeyboardEvent): void => {
    const term = (e.target as Element).closest<HTMLElement>('.term');
    if (!term) return;
    e.preventDefault();
    const next = Number(term.dataset.term) === open ? null : Number(term.dataset.term);
    setOpen(next);
    const found = next === null ? undefined : step.glossary[next];
    if (found) say(`${found.term}. ${found.definition}`);
  };
  let at = 0;
  return (
    <div className="block" ref={root} onClick={toggle} onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') toggle(e); }}>
      {step.how.map((b, i) => {
        const paragraphs = b.paragraphs.map((p) => {
          const index = at++;
          const html = rich(marked[index]);
          const term = open !== null && html.includes(`data-term="${open}"`) ? step.glossary[open] : undefined;
          return [
            <p key={index}><Html html={html} /><Pages list={p.pages} /></p>,
            term && <p key={`t${index}`} className="note term-note"><span><strong><Rich text={term.term} />.</strong> <Rich text={term.definition} /></span></p>,
          ];
        });
        // механизм виден сразу и коротко, практика и нюансы раскрываются по желанию
        if (i > 0) return <Fold key={b.title} title={b.title} hint={teaser(b.paragraphs[0]?.text)} full={full}>{paragraphs}</Fold>;
        const rest = paragraphs.length - SHOWN;
        return [<h3 key={b.title} className="sr">{b.title}</h3>, ...paragraphs.slice(0, rest < 2 ? undefined : SHOWN),
          rest >= 2 && <Fold key="more" title={`Ещё ${plural(rest, ['абзац', 'абзаца', 'абзацев'])} о механизме`} full={full}>{paragraphs.slice(SHOWN)}</Fold>];
      })}
    </div>
  );
}

function FormulaCard({ formula }: { formula: Formula }) {
  const { rich } = useCourse();
  return (
    <div className="card">
      <div className="formula"><Html html={texOnly(formula.tex, rich)} /><Pages list={[formula.page]} /></div>
      {!!formula.legend?.length && <dl className="legend-list">{formula.legend.map((l) => <div key={l.symbol}><dt><Html html={symbol(l.symbol, rich)} /></dt><dd><Rich text={l.meaning} />{l.unit && <>, <Html html={symbol(l.unit, rich)} /></>}</dd></div>)}</dl>}
      {formula.errata && <p className="note warn"><span><strong>Сверка со сканом.</strong> <Rich text={formula.errata} /></span></p>}
    </div>
  );
}

const inCell = (text: string): string => text.replace(/[$]{2}/g, '$');
function Table({ table }: { table: BookTable }) {
  return (
    <>
      <p><Rich text={table.title} /><Pages list={[table.page]} />{!!table.corrections?.length && <><br /><span className="muted">Исправлено ячеек по скану: {table.corrections.length}, они выделены.</span></>}</p>
      <div className="scroll" role="region" tabIndex={0} aria-label={`${table.title}, прокрутка вбок`}>
        <table aria-label={table.title}>
          {!!table.header?.length && <thead><tr>{table.header.map((h, i) => <th key={i} scope="col"><Rich text={h} /></th>)}</tr></thead>}
          <tbody>{tableRows(table).map((row, r) => <tr key={r}>{row.map((c, i) => (c.from === null
            ? <td key={i}><Rich text={inCell(c.text)} /></td>
            : <td key={i} className="fixed"><Rich text={inCell(c.text)} /><span className="was"> исправлено, в распознанном тексте: «<Rich text={inCell(c.from)} />»</span></td>))}</tr>)}</tbody>
        </table>
      </div>
    </>
  );
}

function ClaimRow({ claim }: { claim: Claim }) {
  const isFigure = claim.source_kind === 'figure_description_model';
  return (
    <li id={claimAnchor(claim.id)} tabIndex={-1}><Rich text={claim.text} /><Pages list={[claim.page_pdf]} />{KIND[claim.kind] && <Chip>{KIND[claim.kind]}</Chip>}{claim.by_model && <> <WhoChip who="model" /></>}{isFigure && <Chip>по описанию рисунка</Chip>}{claim.needs_scan && <Chip>сверить со сканом</Chip>}
      <details><summary>{isFigure ? 'Описание рисунка' : 'Цитата автора'}</summary><blockquote><Rich text={claim.quote} /></blockquote></details></li>
  );
}

const Pair = ({ title, text }: { title: string; text?: string | null }) => (text ? <div><dt>{title}</dt><dd><Rich text={text} /></dd></div> : null);

function DataMeaning({ step }: { step: Step }) {
  const d = step.data_meaning;
  if (!d) return null;
  return (
    <>
      <p><Rich text={d.from_chapter.text} /><Pages list={step.pages} /></p><p><strong>Где ломается.</strong> <Rich text={d.breaks.text} /><Pages list={step.pages} /></p>
      {d.hypotheses?.map((h) => <div key={h.text} className="note warn"><strong>Гипотеза, не из главы</strong><p><Rich text={h.text} /></p></div>)}
    </>
  );
}

function Decision({ step }: { step: Step }) {
  const d = step.decision_on_data;
  if (!d) return null;
  return (
    <>
      <h3>Признаки</h3><Items list={d.features} as="ol">{(f) => <li><Rich text={f} /></li>}</Items>
      <p><strong>Правило.</strong> <Rich text={d.rule} /></p><p><strong>Вывод.</strong> <Rich text={d.conclusion} /></p>
      {d.counterexample && <div className="note warn"><strong>Контрпример</strong><p><Rich text={d.counterexample} /></p></div>}
    </>
  );
}

/** Блоки урока по вкладкам; пустые не показываются. */
export function blocksOf(s: Step): Block[] {
  const lens = s.inefficiency_lens;
  const when = (has: unknown, body: ReactNode): ReactNode => ((Array.isArray(has) ? has.length > 0 : has) ? body : null);
  const all: Block[] = [
    { id: 'how', tab: 'about', title: 'Как это работает', who: 'model', open: true, body: when(s.how, <How step={s} />) },
    { id: 'steps', tab: 'about', title: 'По шагам', who: 'model', hint: plural(s.procedure?.length ?? 0, ['действие', 'действия', 'действий']), body: when(s.procedure, <Items list={s.procedure} as="ol">{(x) => <li><Rich text={x.text} /><Pages list={x.pages} /></li>}</Items>) },
    { id: 'decision', tab: 'data', title: 'Решение на данных', who: 'model', open: true, body: when(s.decision_on_data, <Decision step={s} />) },
    { id: 'examples', tab: 'data', title: 'Разбор примеров из главы', who: 'author', hint: plural(s.worked_examples?.length ?? 0, ['пример', 'примера', 'примеров']), body: when(s.worked_examples ?? [], s.worked_examples?.map((e, i) => (
      <div key={i} className="card"><p><strong>Условие.</strong> <Rich text={e.condition} /></p><Items list={e.steps} as="ol">{(x) => <li><Rich text={x} /></li>}</Items><p><strong>Итог.</strong> <Rich text={e.result} /><Pages list={[e.page_pdf]} /></p>{e.figure && <p className="muted">Нужен рисунок: {e.figure}</p>}</div>))) },
    { id: 'numbers', tab: 'data', title: 'Цифры и условия', who: 'author', hint: plural(s.numbers?.length ?? 0, ['условие', 'условия', 'условий']), body: when(s.numbers, <Items list={s.numbers} className="facts">{(x) => <li><Rich text={x.text} /><Pages list={[x.page]} /></li>}</Items>) },
    { id: 'terms', tab: 'about', title: 'Новые понятия', who: 'model', hint: names(s.glossary.map((g) => g.term)), body: when(s.glossary, <dl>{s.glossary.map((g) => <div key={g.term}><dt><Rich text={g.term} /></dt><dd><Rich text={g.definition} /></dd></div>)}</dl>) },
    { id: 'formulas', tab: 'data', title: 'Формулы', who: 'author', hint: plural(s.formulas.length, ['формула', 'формулы', 'формул']), body: when(s.formulas, s.formulas.map((f, i) => <FormulaCard key={i} formula={f} />)) },
    { id: 'tables', tab: 'data', title: 'Таблицы книги', who: 'author', hint: plural(s.tables.length, ['таблица', 'таблицы', 'таблиц']), body: when(s.tables, s.tables.map((t, i) => <Table key={i} table={t} />)) },
    { id: 'mistake', tab: 'about', title: 'Частая ошибка', who: byModel(s.misconception), tone: 'bad', open: true, body: when(s.misconception, <p><Rich text={s.misconception?.text} /></p>) },
    { id: 'data', tab: 'data', title: 'Что это значит для данных', who: byModel(s.data_meaning?.from_chapter), hint: teaser(s.data_meaning?.from_chapter.text), body: when(s.data_meaning, <DataMeaning step={s} />) },
    { id: 'analogy', tab: 'about', title: 'Аналогия из ИТ', who: 'model', tone: 'brand', hint: teaser(s.it_analogy?.text), body: when(s.it_analogy, <><p><Rich text={s.it_analogy?.text} /></p><p><strong>Где перестаёт работать.</strong> <Rich text={s.it_analogy?.breaks_where} /></p></>) },
    { id: 'labour', tab: 'data', title: 'Ручной труд специалиста', who: 'model', hint: teaser(lens?.manual_steps), body: when(lens, <dl><Pair title="Входные данные" text={lens?.inputs} /><Pair title="Ручные шаги" text={lens?.manual_steps} /><Pair title="Точки суждения" text={lens?.judgment_points} /><Pair title="Время" text={lens?.time} /><Pair title="Типичные ошибки" text={lens?.typical_errors} /></dl>) },
    { id: 'now', tab: 'data', title: 'Как это делают сейчас', who: 'model', tone: 'warn', hint: teaser(s.now_practice?.text), body: when(s.now_practice, <><p><Rich text={s.now_practice?.text} /></p><p className="by">Не из книги.</p></>) },
    { id: 'deeper', tab: 'about', title: 'Глубже', who: 'model', hint: teaser(s.deeper?.[0]?.text), body: when(s.deeper, s.deeper.map((d, i) => <p key={i}><Rich text={d.text} /><Pages list={d.pages} /></p>)) },
    { id: 'claims', tab: 'source', title: 'Источник: мысли автора с цитатами', who: 'author', body: when(s.claims, <ul className="claims">{s.claims.map((c) => <ClaimRow key={c.id} claim={c} />)}</ul>) },
    { id: 'scan', tab: 'source', title: 'Что сверить со сканом', who: 'model', body: when(s.needs_scan ?? [], <Items list={s.needs_scan}>{(x) => <li><Rich text={x.what} /><Pages list={[x.page]} /></li>}</Items>) },
    { id: 'tasks', tab: 'tasks', title: 'Проверьте себя', who: null, open: true, body: when(s.tasks, s.tasks.map((t) => <TaskCard key={t.id} task={t} />)) },
    { id: 'book', tab: 'tasks', title: 'Задачи из книги', who: 'author', body: when(s.book_tasks ?? [], s.book_tasks?.map((t) => (
      <div key={t.number} className="card"><p><strong>Задача {t.number}.</strong> <Rich text={t.text} /><Pages list={[t.page_pdf]} /></p>{t.figure && <p className="muted">Нужен рисунок: {t.figure}</p>}</div>))) },
  ];
  return all.filter((x) => x.body !== null);
}

const names = (items: string[], max = 3): string => items.slice(0, max).join(', ') + (items.length > max ? ` и ещё ${items.length - max}` : '');

/** Открытый блок — раздел страницы; свёрнутый — строка с подсказкой. full раскрывает всё. */
export function BlockSection({ block }: { block: Block }) {
  const { state } = useCourse();
  const head = <><h2 tabIndex={-1}>{block.title}</h2>{block.who && <WhoChip who={block.who} />}</>;
  if (block.open) return <section className={block.tone ? `note ${block.tone}` : 'block'} id={block.id}><div className="head">{head}</div>{block.body}</section>;
  return <Fold id={block.id} title={head} hint={block.hint} full={state.full}>{block.tone ? <div className={`note ${block.tone}`}>{block.body}</div> : block.body}</Fold>;
}
