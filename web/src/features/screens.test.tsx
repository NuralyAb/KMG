import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, test, vi } from 'vitest';
import { App } from '@/app/App';
import { handlers } from '@/mocks/handlers';
import { renderApp } from '@/test/render';

const base = (path: string): string => `${window.location.origin}${path}`;
const server = setupServer(...handlers);
const envelope = (data: object, meta: object | null = null) => HttpResponse.json({ success: true, data, error: null, meta });
const failure = (status: number, code: string, message: string) =>
  HttpResponse.json({ success: false, data: null, error: { code, message }, meta: null }, { status });

// по ролям ищется только там, где нет формул: getComputedStyle в jsdom падает на MathML от KaTeX
/** Управляемая замена EventSource: jsdom его не знает. */
class FakeSource extends EventTarget {
  static last: FakeSource | null = null;
  static CLOSED = 2;
  readyState = 1;
  onopen: (() => void) | null = null;
  onerror: (() => void) | null = null;
  readonly url: string;
  constructor(url: string) {
    super();
    this.url = url;
    FakeSource.last = this;
  }
  close(): void {
    this.readyState = 2;
  }
  emit(name: string, data: object): void {
    this.dispatchEvent(new MessageEvent(name, { data: JSON.stringify(data) }));
  }
}

beforeAll(() => {
  // node fetch не понимает относительных путей
  const native = globalThis.fetch;
  server.listen({ onUnhandledRequest: 'error' });
  const intercepted = globalThis.fetch;
  vi.stubGlobal('fetch', (input: RequestInfo | URL, init?: RequestInit) =>
    (intercepted ?? native)(typeof input === 'string' && input.startsWith('/') ? base(input) : input, init?.signal ? { ...init, signal: undefined } : init));
});
beforeEach(() => vi.stubGlobal('EventSource', FakeSource));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe('chapters', () => {
  test('shows chapters, splits built and not built', async () => {
    renderApp(<App />);
    const entry = await screen.findByRole('article', { name: /Песок в банке/ });
    expect(within(entry).getByRole('link', { name: /Открыть курс/ })).toHaveAttribute('href', '/course/demo_sand/index.html');
    expect(within(entry).getByText('устарело')).toBeVisible();
    expect(screen.getByRole('heading', { name: 'Ещё не собраны' })).toBeVisible();
    expect(screen.getByRole('button', { name: 'Собрать: Давление в закрытой банке' })).toBeEnabled();
  });

  test('empty registry', async () => {
    server.use(http.get('/api/chapters', () => envelope([])));
    renderApp(<App />);
    expect(await screen.findByText('Глав пока нет')).toBeVisible();
  });

  test('server error shows its message and can be retried', async () => {
    server.use(http.get('/api/chapters', () => failure(500, 'broken', 'Файл chapters.json не читается'), { once: true }));
    renderApp(<App />);
    expect(await screen.findByText('Файл chapters.json не читается')).toBeVisible();
    await userEvent.click(screen.getByRole('button', { name: 'Повторить' }));
    expect(await screen.findByRole('article', { name: /Песок в банке/ })).toBeVisible();
  });

  test('a paid build asks first and shows a conflict', async () => {
    server.use(http.post('/api/runs', () => failure(409, 'busy', 'По этой главе уже идёт сборка')));
    renderApp(<App />);
    await userEvent.click(await screen.findByRole('button', { name: 'Собрать: Камни разного размера' }));
    const dialog = await screen.findByRole('dialog');
    expect(within(dialog).getByText(/Модель работает платно/)).toBeVisible();
    await userEvent.click(within(dialog).getByRole('button', { name: 'Запустить' }));
    expect(await within(dialog).findByRole('alert')).toHaveTextContent('По этой главе уже идёт сборка');
  });
});

describe('chapter', () => {
  test('path rows link to nodes and filters narrow them', async () => {
    renderApp(<App />, '/chapters/demo_sand');
    const row = (await screen.findByText('Что видно через стекло')).closest('a');
    expect(row).toHaveAttribute('href', '/chapters/demo_sand/nodes/demo.look');
    await userEvent.click(screen.getByRole('button', { name: /Сверить со сканом/ }));
    expect(screen.queryByText('Что видно через стекло')).not.toBeInTheDocument();
    expect(screen.getByText(/встряхнуть/)).toBeVisible();
  });

  test('coverage tab lists skipped units with the reason', async () => {
    renderApp(<App />, '/chapters/demo_sand?tab=coverage');
    expect(await screen.findByText('повторяет пример на той же странице')).toBeVisible();
    await userEvent.click(screen.getByRole('button', { name: /Не вошли/ }));
    await waitFor(() => expect(screen.queryByText('p010.01')).not.toBeInTheDocument());
  });

  test('tasks show the right answer', async () => {
    renderApp(<App />, '/chapters/demo_sand?tab=tasks');
    expect(await screen.findByText('Разделить', { exact: false, selector: 'li[data-right] span' })).toBeVisible();
    expect(screen.getByText('меньше').closest('.task-gap')).not.toBeNull();
  });

  test('unknown chapter', async () => {
    renderApp(<App />, '/chapters/nope');
    expect(await screen.findByText('Такой главы нет в реестре')).toBeVisible();
    expect(screen.queryByRole('button', { name: 'Повторить' })).not.toBeInTheDocument();
  });

  test('live log streams lines and stops at the final state', async () => {
    renderApp(<App />, '/chapters/demo_water?tab=build');
    const log = await screen.findByRole('log');
    const source = FakeSource.last;
    expect(source?.url).toBe('/api/runs/run-live/events');
    source?.onopen?.();
    source?.emit('log', { line: '<b>узел 1 готов</b>' });
    expect(await within(log).findByText('<b>узел 1 готов</b>')).toBeVisible();
    source?.emit('state', { state: 'failed', exit_code: 2 });
    expect(await screen.findByText('код 2')).toBeVisible();
    expect(source?.readyState).toBe(2);
    expect(screen.queryByRole('button', { name: 'Остановить' })).not.toBeInTheDocument();
  });
});

describe('node', () => {
  test('claims stand next to the quote and the page', async () => {
    renderApp(<App />, '/chapters/demo_sand/nodes/demo.pores');
    expect(await screen.findByText('По виду сбоку долю пустот не узнать.')).toBeVisible();
    expect(screen.getByText('Через стекло видно только крайние песчинки')).toBeVisible();
    expect(screen.getByText(/в книге 9/)).toBeVisible();
    expect(screen.getByText('длинное видео')).toBeVisible();
    expect(document.querySelector('.katex')).not.toBeNull();
  });

  test('arrow keys page through nodes', async () => {
    renderApp(<App />, '/chapters/demo_sand/nodes/demo.pores');
    await screen.findByText('По виду сбоку долю пустот не узнать.');
    await userEvent.keyboard('{ArrowRight}');
    expect(await screen.findByRole('heading', { level: 1, name: /встряхнуть/ })).toBeVisible();
  });

  test('HTML in chapter data is shown as text', async () => {
    server.use(http.get('/api/chapters/:id/nodes/:node', () => envelope({
      node: { id: 'x', title: '<img src=x onerror=alert(1)>', claims: [], layers: { main: { text: '$\\href{javascript:alert(1)}{x}$ <script>1</script>', by_model: true } } },
      route: null, tasks: [], illustrations: [], prev: null, next: null,
    })));
    renderApp(<App />, '/chapters/demo_sand/nodes/x');
    expect(await screen.findByRole('heading', { level: 1 })).toHaveTextContent('<img src=x onerror=alert(1)>');
    expect(document.querySelector('main script, main img, main a[href^="javascript"]')).toBeNull();
  });
});

describe('review', () => {
  test('remarks are grouped and filtered', async () => {
    renderApp(<App />, '/review/demo_package');
    expect(await screen.findByRole('region', { name: 'Критические' })).toBeVisible();
    await userEvent.selectOptions(screen.getByRole('combobox', { name: 'Вид ошибки' }), 'frame_error');
    expect(screen.queryByRole('region', { name: 'Критические' })).not.toBeInTheDocument();
    expect(screen.getByText('На кадре не подписан масштаб.')).toBeVisible();
  });

  test('a wrong file is refused before sending', async () => {
    renderApp(<App />, '/review');
    await screen.findByRole('link', { name: /demo_package/ });
    await userEvent.upload(screen.getByLabelText('Файл пакета'), new File(['x'], 'a.txt'), { applyAccept: false });
    expect(await screen.findByRole('alert')).toHaveTextContent('Нужен файл .zip');
    expect(screen.getByRole('button', { name: 'Загрузить и проверить' })).toBeDisabled();
  });

  test('a package without remarks', async () => {
    renderApp(<App />, '/review/demo_clean');
    expect(await screen.findByText('Замечаний нет')).toBeVisible();
  });
});

describe('other screens', () => {
  test('metrics: chart and table agree', async () => {
    renderApp(<App />, '/metrics');
    const chart = await screen.findByRole('figure');
    expect(within(chart).getAllByRole('listitem')[0]).toHaveTextContent('Слой$12,15');
    await userEvent.click(screen.getByRole('button', { name: 'По главам' }));
    expect(within(chart).getAllByRole('listitem')).toHaveLength(2);
  });

  test('search highlights and needs two letters', async () => {
    renderApp(<App />, '/search');
    expect(await screen.findByText('Введите хотя бы два знака')).toBeVisible();
    await userEvent.type(screen.getByRole('searchbox', { name: 'Что найти' }), 'РОВНЫЙ');
    expect(await screen.findByText('Ровный')).toHaveProperty('tagName', 'MARK');
  });

  test('search with no results', async () => {
    renderApp(<App />, '/search?q=zzzz');
    expect(await screen.findByText('Ничего не нашлось')).toBeVisible();
  });

  test('runs can be empty', async () => {
    server.use(http.get('/api/runs', () => envelope([])));
    renderApp(<App />, '/runs');
    expect(await screen.findByText('Запусков ещё не было')).toBeVisible();
  });

  test('unknown address', async () => {
    renderApp(<App />, '/nowhere');
    expect(await screen.findByText('Такой страницы нет')).toBeVisible();
  });
});
