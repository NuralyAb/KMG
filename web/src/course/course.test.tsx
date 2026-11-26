import { act, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest';
import { App } from './App';
import type { Course, Step } from './types';

const step = (order: number, more: Partial<Step> = {}): Step => ({
  id: `s${order}`, order, minutes: 3, title: `Полное название ${order}`, short_title: `Шаг ${order}`, essence: 'Первая мысль. Вторая мысль.', pages: [9 + order],
  how: [{ title: 'Механизм', paragraphs: [{ text: 'Пористость мала. <b>Не разметка</b>.', pages: [10] }] }], deeper: [], glossary: [{ term: 'пористость', definition: 'доля пустот' }],
  claims: [{ id: `s${order}#c1`, text: 'Мысль', quote: 'Цитата', page_pdf: 12, kind: 'inference' }], tasks: [], pictures: [], videos: [], interactive: null,
  procedure: [], numbers: [], formulas: [], tables: [], ...more,
});
const course: Course = {
  id: 'demo', title: 'Песок в банке', book: 'Иванов А. Б. Книга о песке', generated_by: 'модель',
  parts: [{ title: 'Начало', nodes: ['s1', 's2'] }, { title: 'Конец', nodes: ['s3'] }],
  steps: [
    step(1, {
      numbers: [{ text: 'Порог 5 %', page: 11 }],
      pictures: [{ id: 'p', file: 'pictures/a.svg', alt: 'Схема банки', caption: 'Банка', label: 'схема' }],
      interactive: { kind: 'simulation', params: { items: [{ id: 'x' }] } },
      narration: { audio: 'narration/a.mp3', duration: 6, beats: [{ kind: 'title', text: 'Шаг 1', start: 0, end: 2 }, { kind: 'main', text: 'Пористость мала у песка.', start: 2, end: 6, page: 11 }] },
      tasks: [
        { id: 't1', type: 'single', prompt: 'Что внутри?', options: [{ id: 'a', text: 'Песок' }, { id: 'b', text: 'Вода' }], answer: 'a', explanation: 'Потому что песок.', claim_ids: ['s1#c1'] },
        { id: 't2', type: 'gap', prompt: 'В банке {{1}} и {{2}}.', answer: ['песок', '5'], explanation: 'Так.' },
        { id: 't3', type: 'order', prompt: 'Порядок', options: [{ id: 'x', text: 'Икс' }, { id: 'y', text: 'Игрек' }], answer: ['x', 'y'], explanation: 'Так.' },
      ],
    }),
    step(2), step(3),
  ],
};

const saved = (): Record<string, unknown> => JSON.parse(localStorage.getItem('glava.demo') ?? '{}') as Record<string, unknown>;
const open = (hash: string) => {
  window.location.hash = hash;
  return render(<App course={course} />);
};
const goTo = async (hash: string): Promise<void> => act(async () => { window.location.hash = hash; window.dispatchEvent(new HashChangeEvent('hashchange')); await Promise.resolve(); });

beforeEach(() => {
  vi.stubGlobal('scrollTo', vi.fn());
  vi.stubGlobal('matchMedia', () => ({ matches: false, addEventListener: () => {}, removeEventListener: () => {} }));
  Element.prototype.scrollIntoView = vi.fn();
  window.Simulations = { mount: vi.fn() };
});
afterEach(() => {
  localStorage.clear();
  window.location.hash = '';
  vi.unstubAllGlobals();
});

describe('course', () => {
  test('the overview shows the program, progress and the way back in', () => {
    open('#/');
    expect(screen.getByRole('heading', { level: 1, name: 'Песок в банке' })).toBeVisible();
    expect(screen.getByRole('link', { name: /Начать/ })).toHaveAttribute('href', '#/step/1');
    const outline = screen.getByRole('complementary', { name: 'Содержание курса' });
    expect(within(outline).getByText('1.2 Шаг 2')).toBeInTheDocument();
    expect(within(outline).getByText('2.1 Шаг 3')).toBeInTheDocument();
    expect(within(screen.getByRole('complementary', { name: 'О курсе' })).getByText('Иванов А. Б.')).toBeInTheDocument();
  });

  test('a lesson opens on its first item; the outline lists the items of the open lesson only', () => {
    const { container } = open('#/step/1');
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Разбор урока: Шаг 1');
    const items = [...container.querySelectorAll('.outline .item')].map((x) => x.getAttribute('href'));
    expect(items).toEqual(['#/step/1/talk', '#/step/1/read', '#/step/1/sim', '#/step/1/quiz']);
    expect(container.querySelector('.outline .item[aria-current]')).toHaveAttribute('href', '#/step/1/talk');
    expect(screen.getByRole('navigation', { name: 'Вы здесь' })).toHaveTextContent('Обзор курсаМодуль 1Урок 1.1Видео');
  });

  test('next goes item by item, then marks the lesson done and opens the next one', async () => {
    open('#/step/2');
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Шаг 2');
    await userEvent.click(screen.getByRole('button', { name: /Урок пройден, дальше/ }));
    expect(window.location.hash).toBe('#/step/3');
    expect(saved()).toMatchObject({ done: ['s2'], seen: { s2: ['read'] } });
    await goTo('#/step/1/sim');
    await userEvent.click(screen.getByRole('button', { name: /Дальше: тренировка/ }));
    expect(window.location.hash).toBe('#/step/1/quiz');
  });

  test('a seen item gets a check in the outline', async () => {
    const { container } = open('#/step/1/read');
    await goTo('#/step/1/quiz');
    const read = container.querySelector('.outline .item[href="#/step/1/read"]');
    expect(read).toHaveTextContent('просмотрено');
    expect(container.querySelector('.outline .item[href="#/step/1/sim"]')).not.toHaveTextContent('просмотрено');
  });

  test('layer text never becomes markup', () => {
    const { container } = open('#/step/1/read');
    expect(container.querySelector('#how b')).toBeNull();
    expect(container.querySelector('#how')).toHaveTextContent('<b>Не разметка</b>');
  });

  test('nothing from the layer is run as markup: pages, captions, formulas, tables, terms', async () => {
    const evil = '<img src=x onerror=alert(1)>';
    const bad = step(1, {
      short_title: evil, title: evil, essence: evil, pages: [evil as unknown as number], glossary: [{ term: evil, definition: evil }], numbers: [{ text: evil, page: evil as unknown as number }],
      formulas: [{ tex: evil, page: 1, legend: [{ symbol: evil, meaning: evil, unit: evil }] }], tables: [{ title: evil, page: 1, header: [evil], rows: [[evil]], corrections: [{ row: 0, col: 0, from: evil, to: evil }] }],
      claims: [{ id: 'c', text: evil, quote: evil, page_pdf: 1, kind: evil }],
      tasks: [{ id: 't', type: 'gap', prompt: `${evil} {{1}}`, answer: [evil], explanation: evil }],
    });
    window.location.hash = '#/step/1/read';
    const { container } = render(<App course={{ ...course, title: evil, book: evil, steps: [bad] }} />);
    expect(container.querySelector('img')).toBeNull();
    expect(container).toHaveTextContent(`стр. ${evil}`);
    await goTo('#/step/1/quiz');
    expect(container.querySelector('img')).toBeNull();
  });

  test('a section address opens the item that holds it', () => {
    const { container } = open('#/step/1/numbers');
    expect(container.querySelector('[data-item]')).toHaveAttribute('data-item', 'read');
    expect(container.querySelector('#numbers')).toBeInTheDocument();
  });

  test('notes belong to the lesson and survive reopening', async () => {
    const { unmount } = open('#/step/1/notes');
    await userEvent.type(screen.getByLabelText('Сохраняются только в этом браузере'), 'запомнить');
    unmount();
    open('#/step/1/notes');
    expect(screen.getByLabelText('Сохраняются только в этом браузере')).toHaveValue('запомнить');
    await goTo('#/step/2/notes');
    expect(screen.getByLabelText('Сохраняются только в этом браузере')).toHaveValue('');
  });

  test('a term is explained under its paragraph', async () => {
    const { container } = open('#/step/1/read');
    const term = screen.getByRole('button', { name: 'Пористость' });
    await userEvent.click(term);
    expect(container.querySelector('.term-note')).toHaveTextContent('доля пустот');
    expect(term).toHaveAttribute('aria-expanded', 'true');
    await userEvent.click(term);
    expect(container.querySelector('.term-note')).toBeNull();
  });

  test('the simulation item keeps its contract and is mounted when opened', async () => {
    const { container } = open('#/step/1');
    expect(window.Simulations?.mount).not.toHaveBeenCalled();
    await goTo('#/step/1/sim');
    const node = container.querySelector<HTMLElement>('[data-interactive="simulation"]');
    expect(JSON.parse(node?.dataset.params ?? '{}')).toEqual({ items: [{ id: 'x' }] });
    expect(window.Simulations?.mount).toHaveBeenCalledTimes(1);
  });

  test('pictures stand in the reading; a lesson without media has no stage', async () => {
    const { container } = open('#/step/1/read');
    expect(screen.getByAltText('Схема банки')).toBeInTheDocument();
    await goTo('#/step/2');
    expect(container.querySelector('.stage, [data-scene]')).toBeNull();
  });
});

describe('walkthrough', () => {
  const play = (container: HTMLElement, at: number): HTMLAudioElement => {
    const audio = container.querySelector('audio');
    if (!audio) throw new Error('нет дорожки');
    Object.defineProperty(audio, 'paused', { value: false, configurable: true });
    audio.currentTime = at;
    act(() => { audio.dispatchEvent(new Event('seeked')); audio.dispatchEvent(new Event('play')); });
    return audio;
  };

  test('the scene shows the phrase that sounds, its term and page; the transcript follows', () => {
    const { container } = open('#/step/1/talk');
    const scene = container.querySelector<HTMLElement>('[data-scene]');
    expect(scene).toHaveTextContent('Смотреть разбор, 0:06');
    play(container, 3);
    expect(scene?.querySelector('.scene-phrase')).toHaveTextContent('Пористость мала у песка.');
    expect(scene?.querySelector('.scene-term')).toHaveTextContent('пористость');
    expect(scene).toHaveTextContent('стр. 11');
    expect(container.querySelector('.transcript [aria-current]')).toHaveTextContent('Пористость мала у песка.');
  });

  test('a transcript line seeks the track', async () => {
    const { container } = open('#/step/1/talk');
    const audio = container.querySelector('audio') as HTMLAudioElement;
    audio.play = vi.fn(() => Promise.resolve());
    Object.defineProperty(audio, 'readyState', { value: 1, configurable: true });
    await userEvent.click(screen.getByRole('button', { name: /Пористость мала у песка/ }));
    expect(audio.currentTime).toBeCloseTo(2.01);
    expect(audio.play).toHaveBeenCalled();
  });

  test('after the end the scene leads to the next item; a missing track is named', async () => {
    const { container } = open('#/step/1/talk');
    const audio = play(container, 6);
    Object.defineProperty(audio, 'paused', { value: true, configurable: true });
    act(() => { audio.dispatchEvent(new Event('ended')); });
    await userEvent.click(within(container.querySelector('[data-scene]') as HTMLElement).getByRole('button', { name: 'Дальше' }));
    expect(window.location.hash).toBe('#/step/1/read');
    await goTo('#/step/1/talk');
    const fresh = container.querySelector('audio') as HTMLAudioElement;
    act(() => { fresh.dispatchEvent(new Event('error')); });
    expect(container.querySelector('[data-scene]')).toHaveTextContent('Озвучка не загрузилась');
  });
});

describe('tasks', () => {
  const card = (container: HTMLElement, id: string): HTMLElement => {
    const el = container.querySelector<HTMLElement>(`[data-task="${id}"]`);
    if (!el) throw new Error(id);
    return el;
  };

  test('an empty answer is stopped, a wrong one shows the right one, a solved task stays solved', async () => {
    const { container } = open('#/step/1/quiz');
    const task = within(card(container, 't1'));
    await userEvent.click(task.getByRole('button', { name: 'Проверить' }));
    expect(task.getByText('Сначала выберите ответ.')).toBeVisible();
    await userEvent.click(task.getByRole('button', { name: 'Вода' }));
    await userEvent.click(task.getByRole('button', { name: 'Проверить' }));
    expect(task.getByText('Пока нет').parentElement).toHaveFocus();
    expect(task.getByText(/Верный ответ/)).toHaveTextContent('Песок');
    expect(task.getByText('стр. 12', { exact: false })).toBeVisible();
    await userEvent.click(task.getByRole('button', { name: 'Ещё раз' }));
    await userEvent.click(task.getByRole('button', { name: 'Песок' }));
    await userEvent.click(task.getByRole('button', { name: 'Проверить' }));
    expect(saved()).toMatchObject({ solved: { t1: true } });
    await userEvent.click(task.getByRole('button', { name: 'Ещё раз' }));
    await userEvent.click(task.getByRole('button', { name: 'Вода' }));
    await userEvent.click(task.getByRole('button', { name: 'Проверить' }));
    expect(saved()).toMatchObject({ solved: { t1: true } });
  });

  test('the verdict links to the claim, which opens in the source block with its quote', async () => {
    const { container } = open('#/step/1/tasks');
    const task = within(card(container, 't1'));
    await userEvent.click(task.getByRole('button', { name: 'Вода' }));
    await userEvent.click(task.getByRole('button', { name: 'Проверить' }));
    const link = task.getByRole('link', { name: 'Проверить по утверждению автора' });
    expect(link).toHaveAttribute('href', '#/step/1/claim-s1-c1');
    await goTo('#/step/1/claim-s1-c1');
    const claim = container.querySelector('#claim-s1-c1');
    expect(claim?.closest('details.source')).toHaveAttribute('open');
    expect(claim).toHaveFocus();
    expect(claim?.querySelector('details')).toHaveAttribute('open');
  });

  test('gaps are checked one by one, Enter checks', async () => {
    const { container } = open('#/step/1/quiz');
    const task = within(card(container, 't2'));
    await userEvent.type(task.getByLabelText('Пропуск 1'), 'Песок');
    await userEvent.type(task.getByLabelText('Пропуск 2'), '6{Enter}');
    expect(task.getByLabelText('Пропуск 1')).toHaveClass('right');
    expect(task.getByLabelText('Пропуск 2')).toHaveAttribute('aria-invalid', 'true');
  });

  test('order never starts solved and is solved by arrows', async () => {
    const { container } = open('#/step/1/quiz');
    const task = within(card(container, 't3'));
    await userEvent.click(task.getByRole('button', { name: 'Выше: Икс' }));
    expect(task.getByRole('button', { name: 'Выше: Икс' })).toHaveFocus();
    await userEvent.click(task.getByRole('button', { name: 'Проверить' }));
    expect(task.getByText('Верно')).toBeVisible();
  });
});

test('cards go through new ones, then repeats', async () => {
  open('#/cards');
  for (const mark of ['Повторить', 'Знаю', 'Знаю']) {
    await userEvent.click(screen.getByRole('button', { name: 'Показать ответ' }));
    await userEvent.click(screen.getByRole('button', { name: mark }));
  }
  expect(screen.getByText(/Осталось 1 из 3, из них на повтор: 1/)).toBeVisible();
  expect(screen.getByRole('heading', { name: '1.1 Шаг 1' })).toHaveFocus();
  // единственная оставшаяся карточка выпадает снова и снова закрыта
  await userEvent.click(screen.getByRole('button', { name: 'Показать ответ' }));
  await userEvent.click(screen.getByRole('button', { name: 'Повторить' }));
  expect(screen.getByRole('button', { name: 'Показать ответ' })).toBeVisible();
});

describe('results for newcomers', () => {
  test('first attempt is kept, the summary is copied as text and can be wiped', async () => {
    const writeText = vi.fn(() => Promise.resolve());
    vi.stubGlobal('navigator', { ...navigator, clipboard: { writeText } });
    vi.stubGlobal('confirm', vi.fn(() => true));
    const { container } = open('#/step/1/tasks');
    const task = within(container.querySelector<HTMLElement>('[data-task="t1"]')!);
    await userEvent.click(task.getByRole('button', { name: 'Вода' }));
    await userEvent.click(task.getByRole('button', { name: 'Проверить' }));
    await userEvent.click(task.getByRole('button', { name: 'Ещё раз' }));
    await userEvent.click(task.getByRole('button', { name: 'Песок' }));
    await userEvent.click(task.getByRole('button', { name: 'Проверить' }));
    expect(saved()).toMatchObject({ solved: { t1: true }, first: { t1: false } });
    await goTo('#/help');
    await userEvent.click(screen.getByRole('button', { name: 'Скопировать результат' }));
    expect(writeText).toHaveBeenCalledWith(expect.stringContaining('Решено с первой попытки: 0 из 1 начатых'));
    expect(screen.getByRole('status')).toHaveTextContent('Результат скопирован');
    await userEvent.click(screen.getByRole('button', { name: 'Стереть для следующего участника' }));
    expect(saved()).toMatchObject({ solved: {}, first: {}, done: [] });
  });
});
