import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { afterAll, afterEach, beforeAll, describe, expect, test, vi } from 'vitest';
import { App } from '@/app/App';
import { handlers } from '@/mocks/handlers';
import { renderApp } from '@/test/render';
import { isOwnComputer, needsPrice } from '../model/model';
import { fileProblem, parseRanges, sizeText } from './files';

const server = setupServer(...handlers);
const failure = (status: number, message: string) => HttpResponse.json({ success: false, data: null, error: { code: 'x', message }, meta: null }, { status });

class QuietSource extends EventTarget {
  static CLOSED = 2;
  readyState = 1;
  close(): void {
    this.readyState = 2;
  }
}

beforeAll(() => {
  vi.stubGlobal('EventSource', QuietSource);
  server.listen({ onUnhandledRequest: 'error' });
  const native = globalThis.fetch;
  vi.stubGlobal('fetch', (input: RequestInfo | URL, init?: RequestInit) =>
    native(typeof input === 'string' && input.startsWith('/') ? `${window.location.origin}${input}` : input, init?.signal ? { ...init, signal: undefined } : init));
});
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe('files', () => {
  test.each([['5-20', [[5, 20]]], ['5–20, 25', [[5, 20], [25, 25]]], [' 7 ', [[7, 7]]]])('ranges %s', (text, expected) => {
    expect(parseRanges(text)).toEqual(expected);
  });
  test.each(['', 'а', '5-', '20-5', '0', '1;2', '1-2-3', '-5'])('bad ranges "%s"', (text) => expect(parseRanges(text)).toBeNull());

  test('wrong files are named before sending', () => {
    expect(fileProblem({ name: 'a.exe', size: 5 })).toMatch(/не подходит/);
    expect(fileProblem({ name: 'a.pdf', size: 0 })).toMatch(/пустой/);
    expect(fileProblem({ name: 'a.pdf', size: 500 * 1024 * 1024 })).toMatch(/больше/);
    expect(fileProblem({ name: 'A.PDF', size: 5 })).toBeNull();
    expect(sizeText(100)).toBe('1 КБ');
  });

  test.each([['', true], ['http://127.0.0.1:1/v1', true], ['http://localhost:1/v1', true], ['http://[::1]:1/v1', true], ['http://127.0.0.1.evil.example', false], ['https://api.example', false], ['мусор', false]])(
    'own computer %s', (url, expected) => expect(isOwnComputer(url)).toBe(expected));

  test('price is asked only where money is spent', () => {
    expect([needsPrice('openai', ''), needsPrice('local', ''), needsPrice('local', 'https://h/v1'), needsPrice('claude_code', '')]).toEqual([true, false, true, false]);
  });
});

describe('library', () => {
  test('lists books with the worst page state', async () => {
    renderApp(<App />, '/library');
    expect(await screen.findByRole('link', { name: /Песок\.txt/ })).toHaveTextContent('без текста: 1');
    expect(screen.getByRole('link', { name: /Камни\.pdf/ })).toHaveTextContent('готово');
  });

  test('empty library', async () => {
    server.use(http.get('/api/library', () => HttpResponse.json({ success: true, data: [], error: null, meta: null })));
    renderApp(<App />, '/library');
    expect(await screen.findByText('Здесь пока пусто')).toBeVisible();
  });

  test('a wrong file is refused and nothing is sent', async () => {
    const sent = vi.fn();
    server.use(http.post('/api/library', () => { sent(); return failure(500, 'x'); }));
    renderApp(<App />, '/library');
    await userEvent.upload(await screen.findByLabelText('Файлы книг'), new File(['x'], 'a.exe'), { applyAccept: false });
    expect(await screen.findByRole('alert')).toHaveTextContent('a.exe: Такой файл не подходит');
    expect(sent).not.toHaveBeenCalled();
  });

  test('page text is shown as text and reasons are visible', async () => {
    renderApp(<App />, '/library/src_0000000000aa');
    expect(await screen.findByText('Песок в банке. <b>Не разметка</b>')).toBeVisible();
    await userEvent.click(screen.getByRole('button', { name: 'Страница 2, сверить' }));
    expect(await screen.findByText('формулы могли исказиться')).toBeVisible();
    await userEvent.click(screen.getByRole('button', { name: /^нет текста/ }));
    expect(screen.queryByRole('button', { name: 'Страница 1, надёжно' })).not.toBeInTheDocument();
  });

  test('a chapter needs readable page numbers and the server has the last word', async () => {
    server.use(http.post('/api/library/:id/chapters', () => failure(422, 'Страницы без текста: 3')));
    renderApp(<App />, '/library/src_0000000000aa');
    await userEvent.type(await screen.findByLabelText(/Название главы/), 'Глава');
    await userEvent.type(screen.getByLabelText(/Страницы/, { selector: 'input' }), 'с пятой');
    await userEvent.click(screen.getByRole('button', { name: 'Создать главу' }));
    expect(await screen.findByText(/Запишите страницы так/)).toBeVisible();
    await userEvent.clear(screen.getByLabelText(/Страницы/, { selector: 'input' }));
    await userEvent.type(screen.getByLabelText(/Страницы/, { selector: 'input' }), '1-3');
    await userEvent.click(screen.getByRole('button', { name: 'Создать главу' }));
    expect(await screen.findByText('Страницы без текста: 3')).toBeVisible();
  });

  test('a created chapter opens its build tab', async () => {
    renderApp(<App />, '/library/src_0000000000aa');
    await userEvent.type(await screen.findByLabelText(/Название главы/), 'Глава');
    await userEvent.type(screen.getByLabelText(/Страницы/, { selector: 'input' }), '1-2');
    await userEvent.click(screen.getByRole('button', { name: 'Создать главу' }));
    expect(await screen.findByRole('heading', { level: 1, name: /Песок в банке/ })).toBeVisible();
  });

  test('deleting asks first and shows why it is impossible', async () => {
    server.use(http.delete('/api/library/:id', () => failure(409, 'Из этой книги сделаны главы')));
    renderApp(<App />, '/library/src_0000000000bb');
    await userEvent.click(await screen.findByRole('button', { name: 'Удалить' }));
    const dialog = await screen.findByRole('dialog');
    await userEvent.click(within(dialog).getByRole('button', { name: 'Удалить файл' }));
    expect(await within(dialog).findByRole('alert')).toHaveTextContent('сделаны главы');
  });

  test('unknown book', async () => {
    renderApp(<App />, '/library/src_nope');
    expect(await screen.findByText('Такого файла в базе знаний нет')).toBeVisible();
  });
});

describe('trust', () => {
  test('shows findings, how sharp the check is, and that nothing else was checked', async () => {
    renderApp(<App />, '/chapters/demo_sand?tab=trust');
    expect(await screen.findByText('доля пустот падает')).toBeVisible();
    expect(screen.getByText('направление')).toBeVisible();
    expect(screen.getByText(/замечено 7 из 10 ошибок/)).toBeVisible();
    expect(screen.getByText(/отчёт говорит о прежней версии/)).toBeVisible();
    expect(screen.getByText('Модель ещё не проверяла')).toBeVisible();
  });

  test('a paid check asks first', async () => {
    renderApp(<App />, '/chapters/demo_sand?tab=trust');
    await userEvent.click(await screen.findByRole('button', { name: 'Проверить моделью' }));
    expect(within(await screen.findByRole('dialog')).getByText(/Этап платный/)).toBeVisible();
  });
});

describe('model', () => {
  test('a local model stays on the computer, a remote one does not', async () => {
    const saved = vi.fn();
    server.use(http.post<never, object>('/api/settings/model', async ({ request }) => {
      const body = await request.json();
      saved(body);
      return HttpResponse.json({ success: true, data: { ...body, origin: 'file', keys: {} }, error: null, meta: null });
    }));
    renderApp(<App />, '/model');
    await userEvent.selectOptions(await screen.findByLabelText('Кто отвечает'), 'local');
    expect(screen.getByText(/останется на этом компьютере/)).toBeVisible();
    await userEvent.type(screen.getByLabelText(/Адрес сервера/), 'https://models.example/v1');
    expect(screen.getByText(/уйдёт на сервер/)).toBeVisible();
    expect(screen.getByLabelText(/Цена входа/)).toBeVisible();
    await userEvent.clear(screen.getByLabelText(/Адрес сервера/));
    await userEvent.type(screen.getByLabelText(/Имя модели/), 'qwen3');
    await userEvent.type(screen.getByLabelText(/Контекст/), '8192');
    await userEvent.click(screen.getByRole('button', { name: 'Сохранить' }));
    await waitFor(() => expect(saved).toHaveBeenCalledWith({
      provider: 'local', model: 'qwen3', base_url: null, price_in: null, price_out: null, budget_usd: null, context: 8192,
    }));
  });

  test('a missing key is named, never asked for', async () => {
    renderApp(<App />, '/model');
    await userEvent.selectOptions(await screen.findByLabelText('Кто отвечает'), 'openai');
    expect(screen.getByText('OPENAI_API_KEY')).toBeVisible();
    expect(document.querySelector('input[type="password"]')).toBeNull();
  });
});
