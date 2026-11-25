import { act, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { afterAll, afterEach, beforeAll, describe, expect, test, vi } from 'vitest';
import { App } from '@/app/App';
import { handlers } from '@/mocks/handlers';
import { renderApp } from '@/test/render';
import { minutesText } from './CatalogPage';
import { courseSrc, readProgress } from './progress';
import { safeTarget } from './target';

const server = setupServer(...handlers);
const envelope = (data: object) => HttpResponse.json({ success: true, data, error: null, meta: null });
const failure = (status: number, message: string) => HttpResponse.json({ success: false, data: null, error: { code: 'x', message }, meta: null }, { status });
const learner = http.get('/api/auth/me', () => envelope({ role: 'learner', protected: true }));
const asked: string[] = [];

beforeAll(() => {
  server.listen({ onUnhandledRequest: 'error' });
  server.events.on('request:start', ({ request }) => asked.push(new URL(request.url).pathname));
  const native = globalThis.fetch;
  vi.stubGlobal('fetch', (input: RequestInfo | URL, init?: RequestInit) =>
    native(typeof input === 'string' && input.startsWith('/') ? `${window.location.origin}${input}` : input, init?.signal ? { ...init, signal: undefined } : init));
});
afterEach(() => {
  server.resetHandlers();
  window.localStorage.clear();
  asked.length = 0;
});
afterAll(() => server.close());

const storage = (value: string | null) => ({ getItem: () => value });

describe('logic', () => {
  test.each([
    [null, 0, null], ['мусор', 0, null], ['[]', 0, null], ['{"done":["a","a","x"],"last":2}', 1, 2], ['{"done":"a","last":"2"}', 0, null], ['{"done":[1,null],"last":-1}', 0, null],
  ])('progress from %s', (raw, done, last) => {
    expect(readProgress('c', new Set(['a', 'b']), storage(raw))).toEqual({ done, last });
  });

  test('a blocked storage is no progress', () => {
    expect(readProgress('c', new Set(['a']), { getItem: () => { throw new Error('blocked'); } })).toEqual({ done: 0, last: null });
  });

  test('course address', () => {
    expect(courseSrc('a/b', 3)).toBe('/learn/a%2Fb/index.html#/step/3');
    expect(courseSrc('a', null)).toBe('/learn/a/index.html');
    expect(courseSrc('a', 3, '#/step/7/how')).toBe('/learn/a/index.html#/step/7/how');
    expect(courseSrc('a', 3, '#x')).toBe('/learn/a/index.html#/step/3');
  });

  test.each([
    ['/admin', '/admin'], ['/admin/chapters/x?tab=trust', '/admin/chapters/x?tab=trust'], [null, '/admin'], ['//evil.example', '/admin'], ['https://evil.example', '/admin'],
    ['/adminx', '/admin'], ['/admin\\evil', '/admin'], ['javascript:alert(1)', '/admin'], ['/', '/admin'],
  ])('login target %s', (value, expected) => expect(safeTarget(value)).toBe(expected));

  test.each([[0, '0 мин'], [45, '45 мин'], [60, '1 ч'], [75, '1 ч 15 мин']])('%s minutes', (n, text) => expect(minutesText(n)).toBe(text));
});

describe('learner', () => {
  test('sees published courses and own progress', async () => {
    server.use(learner);
    window.localStorage.setItem('glava.demo_sand', JSON.stringify({ done: ['demo.look', 'чужой'], last: 2 }));
    renderApp(<App />);
    const card = await screen.findByRole('article', { name: 'Песок в банке' });
    expect(within(card).getByText(/Пройдено 1 из 2/)).toBeVisible();
    expect(within(card).getByText(/1 ч 15 мин/)).toBeVisible();
    expect(within(card).getByRole('link', { name: 'Продолжить: Песок в банке' })).toHaveAttribute('href', '/courses/demo_sand');
    expect(screen.getByRole('link', { name: 'Вход для авторов' })).toBeVisible();
  });

  test('asks the server for nothing of the author', async () => {
    server.use(learner);
    renderApp(<App />);
    await screen.findByRole('article', { name: 'Песок в банке' });
    expect(asked.filter((p) => !p.startsWith('/api/learn') && !p.startsWith('/api/auth'))).toEqual([]);
  });

  test('opens the course where it was left and follows its progress', async () => {
    server.use(learner);
    window.localStorage.setItem('glava.demo_sand', JSON.stringify({ done: [], last: 2 }));
    renderApp(<App />, '/courses/demo_sand');
    const frame = await screen.findByTitle('Песок в банке');
    expect(frame).toHaveAttribute('src', '/learn/demo_sand/index.html#/step/2');
    window.localStorage.setItem('glava.demo_sand', JSON.stringify({ done: ['demo.look', 'demo.pores'], last: 1 }));
    act(() => void window.dispatchEvent(new StorageEvent('storage', { key: 'glava.demo_sand' })));
    expect(await screen.findByText(/2 из 2/)).toBeVisible();
    expect(frame).toHaveAttribute('src', '/learn/demo_sand/index.html#/step/2');
  });

  test('empty catalog and unknown course', async () => {
    server.use(learner, http.get('/api/learn/courses', () => envelope([])));
    renderApp(<App />);
    expect(await screen.findByText('Курсов пока нет')).toBeVisible();
    renderApp(<App />, '/courses/nope');
    expect(await screen.findByText('Такого курса нет')).toBeVisible();
  });

  test('cannot open the author screen', async () => {
    server.use(learner);
    renderApp(<App />, '/admin/library');
    expect(await screen.findByRole('heading', { name: 'Вход для авторов' })).toBeVisible();
    expect(asked).not.toContain('/api/library');
  });
});

describe('author', () => {
  test('wrong password is explained and the field is cleared', async () => {
    server.use(learner, http.post('/api/auth/login', () => failure(401, 'Пароль не подошёл')));
    renderApp(<App />, '/login');
    const field = await screen.findByLabelText(/Пароль/, { selector: 'input' });
    await userEvent.type(field, 'неверный');
    await userEvent.click(screen.getByRole('button', { name: 'Войти' }));
    expect(await screen.findByText('Пароль не подошёл')).toBeVisible();
    expect(field).toHaveValue('');
  });

  test('returns to the page that asked for login', async () => {
    let role = 'learner';
    server.use(http.get('/api/auth/me', () => envelope({ role, protected: true })), http.post('/api/auth/login', () => {
      role = 'admin';
      return envelope({ role, protected: true });
    }));
    renderApp(<App />, '/admin/library');
    await userEvent.type(await screen.findByLabelText(/Пароль/, { selector: 'input' }), 'верный пароль');
    await userEvent.click(screen.getByRole('button', { name: 'Войти' }));
    expect(await screen.findByRole('heading', { name: 'База знаний' })).toBeVisible();
    // в шапке и в меню телефона; лишнюю из двух прячет CSS, которого в тесте нет
    expect(screen.getAllByRole('button', { name: 'Выйти' })).toHaveLength(2);
  });

  test('publishes only after every remark is marked', async () => {
    const sent = vi.fn();
    server.use(http.post<{ id: string }, { accepted: string[] }>('/api/chapters/:id/publication', async ({ request }) => {
      sent((await request.json()).accepted);
      return envelope({ published_at: '2026-11-25T12:00:00Z', is_current: true, problem: null, checks: [], accepted: [] });
    }));
    renderApp(<App />, '/admin/chapters/demo_sand');
    await userEvent.click(await screen.findByRole('button', { name: 'Опубликовать' }));
    const dialog = await screen.findByRole('dialog');
    const go = await within(dialog).findByRole('button', { name: 'Опубликовать' });
    expect(go).toBeDisabled();
    for (const box of within(dialog).getAllByRole('checkbox')) await userEvent.click(box);
    await userEvent.click(go);
    await waitFor(() => expect(sent).toHaveBeenCalledWith(['flagged:2', 'no_verify:1']));
  });

  test('a course of another layer cannot be published', async () => {
    server.use(http.get('/api/chapters/:id/publication', () => envelope({ published_at: null, is_current: false, problem: 'Курс собран из другой версии слоя', checks: [], accepted: [] })));
    renderApp(<App />, '/admin/chapters/demo_sand');
    await userEvent.click(await screen.findByRole('button', { name: 'Опубликовать' }));
    const dialog = await screen.findByRole('dialog');
    expect(await within(dialog).findByRole('alert')).toHaveTextContent('другой версии слоя');
    expect(within(dialog).getByRole('button', { name: 'Опубликовать' })).toBeDisabled();
  });
});
