import { useState } from 'react';
import { useCourse } from './context';
import { results, resultsText } from './core';
import { say } from './store';

/** Копия в буфер: сначала Clipboard API, без него — выделенный текст и команда копирования. */
async function copy(text: string, box: HTMLTextAreaElement | null): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    box?.select();
    try { return document.execCommand('copy'); } catch { return false; }
  }
}

/** Сводка для проверки курса на новичках: считается из прогресса в этом браузере, никуда не отправляется. */
export function Results() {
  const { course, store, state, num } = useCourse();
  const [status, setStatus] = useState('');
  const r = results(course, state);
  const nums = new Map(course.steps.map((s) => [s.id, num(s)]));
  const text = resultsText(course, state, (id) => nums.get(id) ?? id, new Date().toLocaleString('ru-RU'));
  const onCopy = async (): Promise<void> => {
    const done = await copy(text, document.querySelector<HTMLTextAreaElement>('#results-text'));
    const word = done ? 'Результат скопирован' : 'Скопировать не вышло: выделите текст ниже и скопируйте вручную';
    setStatus(word);
    say(word);
  };
  const reset = (): void => {
    if (!window.confirm('Стереть прогресс, ответы, карточки и заметки в этом браузере?')) return;
    store.set({ done: [], solved: {}, first: {}, cards: {}, repeat: [], last: null, notes: {} });
    setStatus('Прогресс стёрт');
  };
  return (
    <section className="block" id="results" data-results>
      <h2 tabIndex={-1}>Мои результаты</h2>
      <p className="muted">Считается по ответам в этом браузере. Ничего не отправляется: результат копируется в буфер обмена текстом.</p>
      <dl>
        <div><dt>Решено с первой попытки</dt><dd className="num">{r.first} из {r.tried} начатых</dd></div>
        <div><dt>Решено всего</dt><dd className="num">{r.solved} из {r.tried} начатых, заданий в курсе {r.tasks}</dd></div>
        <div><dt>Уроков пройдено</dt><dd className="num">{r.done} из {r.steps}</dd></div>
      </dl>
      <div className="row noprint">
        <button type="button" className="btn main" data-copy onClick={() => void onCopy()}>Скопировать результат</button>
        <button type="button" className="btn" data-reset onClick={reset}>Стереть для следующего участника</button>
      </div>
      {status && <p role="status">{status}</p>}
      <label className="muted" htmlFor="results-text">Текст результата</label>
      <textarea id="results-text" rows={8} readOnly value={text} />
    </section>
  );
}
