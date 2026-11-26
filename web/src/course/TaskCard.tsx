import { useEffect, useRef, useState, type PointerEvent as ReactPointerEvent } from 'react';
import { Html, Pages, Rich } from './bits';
import { stepUrl, useCourse } from './context';
import { claimAnchor, isAnswered, isCorrect, shuffled, showNumber, startOrder } from './core';
import { say } from './store';
import type { Task } from './types';

const HINT = { single: 'Один верный ответ', multiple: 'Несколько верных ответов', order: 'Расставьте по порядку: перетащите строку за ручку слева или нажимайте стрелки', gap: 'Впишите пропущенные слова', calc: 'Введите число' };
const EMPTY = { single: 'Сначала выберите ответ.', multiple: 'Сначала отметьте хотя бы один ответ.', order: '', gap: 'Заполните все пропуски.', calc: 'Введите число.' };
const BLANK = /\{\{(\d+)\}\}/;
const answers = (task: Task): string[] => (Array.isArray(task.answer) ? task.answer : [String(task.answer)]);

interface PartProps { task: Task; picked: string[]; setPicked: (ids: string[]) => void; isShown: boolean }

function Options({ task, picked, setPicked, isShown }: PartProps) {
  const choose = (id: string): void => {
    if (task.type === 'single') setPicked([id]);
    else setPicked(picked.includes(id) ? picked.filter((x) => x !== id) : [...picked, id]);
  };
  return shuffled(task.options ?? [], task.id).map((o) => {
    const isMine = picked.includes(o.id);
    const isRight = isShown && answers(task).includes(o.id);
    const isWrong = isShown && isMine && !isRight;
    const look = isShown ? `${isRight ? ' right' : ''}${isWrong ? ' wrong' : ''}` : isMine ? ' on' : '';
    const note = isRight ? (isMine ? 'верно' : 'верный ответ') : isWrong ? 'ваш выбор, неверно' : '';
    return <button key={o.id} type="button" className={`option${look}`} data-id={o.id} aria-pressed={isMine} disabled={isShown} onClick={() => choose(o.id)}><Rich text={o.text} />{note && <span className="tag">{note}</span>}</button>;
  });
}

function OrderRows({ task, picked, setPicked, isShown }: PartProps) {
  const box = useRef<HTMLDivElement>(null);
  const [lifted, setLifted] = useState('');
  const focus = useRef<{ id: string; shift: number } | null>(null);
  useEffect(() => {
    const at = focus.current;
    focus.current = null;
    if (at) box.current?.querySelector<HTMLElement>(`[data-id="${CSS.escape(at.id)}"] [data-move="${at.shift}"]`)?.focus();
  }, [picked]);
  const text = (id: string): string => task.options?.find((o) => o.id === id)?.text ?? id;
  const placed = (list: string[], id: string, to: number): string[] => {
    const rest = list.filter((x) => x !== id);
    return [...rest.slice(0, to), id, ...rest.slice(to)];
  };
  const move = (id: string, shift: number): void => {
    const to = picked.indexOf(id) + shift;
    if (to < 0 || to >= picked.length) { say(shift < 0 ? 'Уже первый' : 'Уже последний'); return; }
    focus.current = { id, shift };
    setPicked(placed(picked, id, to));
    say(`Место ${to + 1} из ${picked.length}`);
  };
  // пальцем строка тянется только за ручку: иначе список не даёт прокрутить страницу
  const lift = (e: ReactPointerEvent<HTMLDivElement>, id: string): void => {
    const target = e.target as Element;
    if (e.button > 0 || target.closest('button') || (e.pointerType !== 'mouse' && !target.closest('.grip'))) return;
    e.preventDefault();
    setLifted(id);
    let list = picked;
    const drag = (ev: PointerEvent): void => {
      const others = [...(box.current?.querySelectorAll<HTMLElement>('[data-id]') ?? [])].filter((x) => x.dataset.id !== id);
      const after = others.findIndex((x) => { const r = x.getBoundingClientRect(); return ev.clientY < r.top + r.height / 2; });
      const next = placed(list, id, after < 0 ? others.length : after);
      if (next.join() === list.join()) return;
      list = next;
      setPicked(next);
    };
    const drop = (): void => {
      document.removeEventListener('pointermove', drag);
      document.removeEventListener('pointerup', drop);
      document.removeEventListener('pointercancel', drop);
      setLifted('');
      say(`Место ${list.indexOf(id) + 1} из ${list.length}`);
    };
    document.addEventListener('pointermove', drag);
    document.addEventListener('pointerup', drop);
    document.addEventListener('pointercancel', drop);
  };
  return (
    <div className="rows" ref={box}>
      {picked.map((id, i) => {
        const isRight = answers(task)[i] === id;
        const head = <><span className="num">{i + 1}.</span><span className="what"><Rich text={text(id)} /></span></>;
        if (isShown) return <div key={id} className={`option ${isRight ? 'right' : 'wrong'}`}>{head}<span className="tag">{isRight ? 'на месте' : 'не на месте'}</span></div>;
        return (
          <div key={id} className={`option drag${lifted === id ? ' lift' : ''}`} data-id={id} onPointerDown={(e) => lift(e, id)}>
            <span className="grip" aria-hidden>⠿</span>{head}
            <span className="move">
              <button type="button" data-move="-1" aria-label={`Выше: ${text(id)}`} onClick={() => move(id, -1)}>↑</button>
              <button type="button" data-move="1" aria-label={`Ниже: ${text(id)}`} onClick={() => move(id, 1)}>↓</button>
            </span>
          </div>
        );
      })}
    </div>
  );
}

interface InputProps { task: Task; values: string[]; setValues: (values: string[]) => void; isShown: boolean }

/** Пропуски стоят посреди текста с формулами: текст делится по {{1}}, {{2}} и собирается с полями. */
function Gaps({ task, values, setValues, isShown }: InputProps) {
  const { rich } = useCourse();
  const pieces = rich(task.prompt).split(BLANK);
  return (
    <>
      <p className="gaps">{pieces.map((piece, i) => {
        if (i % 2 === 0) return <Html key={i} html={piece} />;
        const n = (i - 1) / 2;
        const isRight = isCorrect({ type: 'gap', answer: [answers(task)[n] ?? ''] }, [], [values[n] ?? '']);
        return <input key={i} className={`gap-input${isShown ? (isRight ? ' right' : ' wrong') : ''}`} type="text" autoComplete="off" autoCapitalize="off" spellCheck={false} aria-label={`Пропуск ${piece}`}
          aria-invalid={isShown && !isRight ? true : undefined} disabled={isShown} value={values[n] ?? ''} onChange={(e) => { const text = e.currentTarget.value; setValues(values.map((v, k) => (k === n ? text : v))); }} />;
      })}</p>
      {answers(task).some((a) => a.includes('ρ')) && <p className="muted">Вместо ρ можно набрать букву «р».</p>}
    </>
  );
}

function Calc({ task, values, setValues, isShown, isRight }: InputProps & { isRight: boolean }) {
  return (
    <label>Ответ{task.unit ? `, ${task.unit}` : ''}<br />
      <input type="text" inputMode="text" autoComplete="off" disabled={isShown} className={isShown ? (isRight ? 'right' : 'wrong') : ''} aria-invalid={isShown && !isRight ? true : undefined}
        value={values[0] ?? ''} onChange={(e) => setValues([e.currentTarget.value])} />
    </label>
  );
}

function Answer({ task }: { task: Task }) {
  const label = (id: string): string => task.options?.find((o) => o.id === id)?.text ?? id;
  if (task.type === 'calc') return <>{showNumber(task.answer)} {task.unit ?? ''}</>;
  if (task.type === 'gap') return <>{answers(task).join('; ')}</>;
  return <>{answers(task).map((id, i) => <span key={id}>{i > 0 && (task.type === 'order' ? ' → ' : '; ')}<Rich text={label(id)} /></span>)}</>;
}

/** Задание одного из пяти типов: проверка сразу, без сети. */
export function TaskCard({ task }: { task: Task }) {
  const { course, store, state } = useCourse();
  const root = useRef<HTMLDivElement>(null);
  const [picked, setPicked] = useState(() => (task.type === 'order' ? startOrder(task.options ?? [], answers(task), task.id) : []));
  const blank = task.type === 'gap' ? answers(task).map(() => '') : [''];
  const [values, setValues] = useState(blank);
  const [verdict, setVerdict] = useState<boolean | null>(null);
  const [warning, setWarning] = useState('');
  const isShown = verdict !== null;
  const isFirst = useRef(true);
  const promptId = `q-${task.id.replace(/[^\w-]/g, '-')}`;
  const claim = course.steps.flatMap((s) => s.claims).find((c) => c.id === task.claim_ids?.[0]);
  const owner = claim && course.steps.find((s) => s.claims.includes(claim));

  useEffect(() => {
    if (isFirst.current) { isFirst.current = false; return; }
    // фокус на вердикт читается один раз; живая область здесь дала бы повтор
    root.current?.querySelector<HTMLElement>(isShown ? '.verdict' : 'input, .options button')?.focus();
  }, [isShown]);

  const check = (): void => {
    if (!isAnswered(task, picked, values)) {
      setWarning(EMPTY[task.type]);
      say(EMPTY[task.type]);
      [...(root.current?.querySelectorAll('input') ?? [])].find((x) => !x.value.trim())?.focus();
      return;
    }
    const isRight = isCorrect(task, picked, values);
    setWarning('');
    setVerdict(isRight);
    const { solved, first } = store.get();
    // первая попытка записывается один раз: по ней считают долю решённых новичками
    store.set({ solved: { ...solved, [task.id]: solved[task.id] === true || isRight }, first: task.id in first ? first : { ...first, [task.id]: isRight } });
  };
  const again = (): void => {
    setVerdict(null);
    setValues(blank);
    if (task.type !== 'order') setPicked([]);
  };
  const parts = { task, picked, setPicked, isShown };
  return (
    <div className="card task" data-task={task.id} data-type={task.type} ref={root} onKeyDown={(e) => { if (e.key === 'Enter' && e.target instanceof HTMLInputElement) { e.preventDefault(); check(); } }}>
      <h3 id={promptId}>{task.type === 'gap' ? 'Заполните пропуски' : <Rich text={task.prompt} />}</h3>
      <p className="muted">{HINT[task.type]}{state.solved[task.id] === true && <> · <span className="ok">решено</span></>}</p>
      {task.type === 'gap' && <Gaps task={task} values={values} setValues={setValues} isShown={isShown} />}
      {task.type === 'calc' && <Calc task={task} values={values} setValues={setValues} isShown={isShown} isRight={verdict === true} />}
      {task.type === 'order' && <div className="options" role="group" aria-labelledby={promptId}><OrderRows {...parts} /></div>}
      {(task.type === 'single' || task.type === 'multiple') && <div className="options" role="group" aria-labelledby={promptId}><Options {...parts} /></div>}
      {isShown ? (
        <>
          <div className={`verdict ${verdict ? 'good' : 'bad'}`} tabIndex={-1}><strong>{verdict ? 'Верно' : 'Пока нет'}</strong><p>Верный ответ: <Answer task={task} /></p><p><Rich text={task.explanation} /><Pages list={claim && [claim.page_pdf]} /></p>{claim && owner && <p><a href={stepUrl(owner, claimAnchor(claim.id))} data-claim>Проверить по утверждению автора</a></p>}</div>
          <button type="button" className="btn" data-again onClick={again}>Ещё раз</button>
        </>
      ) : (
        <>
          {warning && <p className="empty">{warning}</p>}
          <button type="button" className="btn main" data-check onClick={check}>Проверить</button>
        </>
      )}
    </div>
  );
}
