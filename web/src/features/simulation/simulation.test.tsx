import { fireEvent, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { afterAll, afterEach, beforeAll, describe, expect, test, vi } from 'vitest';
import type { NodeSimulations, SimulationRun } from '@/api/simulations';
import { handlers } from '@/mocks/handlers';
import { renderApp } from '@/test/render';
import { SimulationSection } from './SimulationSection';

const server = setupServer(...handlers);
const SCENE = { id: 'log', title: 'Где нефть', goal: 'Найдите пласт', label: 'симуляция', poster_url: null, player_url: '/course/a/assets/sim/player.html#log' };
const RUN: SimulationRun = {
  id: 'r1', state: 'running', is_design_only: false, started_at: new Date().toISOString(), finished_at: null, retry: 0, reason: null,
  stages: [{ name: 'facts', state: 'done' }, { name: 'design', state: 'done' }, { name: 'model', state: 'now' }, { name: 'scene', state: 'wait' }],
};
const show = (data: NodeSimulations) => {
  server.use(http.get('*/api/chapters/a/nodes/n/simulations', () => HttpResponse.json({ success: true, data, error: null, meta: null })));
  return renderApp(<SimulationSection chapter="a" node="n" />);
};
const say = (frame: HTMLIFrameElement, data: object): void => {
  fireEvent(window, new MessageEvent('message', { data, source: frame.contentWindow }));
};

beforeAll(() => {
  server.listen({ onUnhandledRequest: 'error' });
  const intercepted = globalThis.fetch;
  vi.stubGlobal('fetch', (input: RequestInfo | URL, init?: RequestInit) =>
    intercepted(typeof input === 'string' && input.startsWith('/') ? `${window.location.origin}${input}` : input, init?.signal ? { ...init, signal: undefined } : init));
});
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe('scene in the page', () => {
  test('loads only on demand, in place, and closes', async () => {
    const user = userEvent.setup();
    show({ scenes: [SCENE], run: null });
    const start = await screen.findByRole('button', { name: 'Запустить симулятор «Где нефть»' });
    expect(document.querySelector('iframe')).toBeNull();

    await user.click(start);
    const frame = screen.getByTitle<HTMLIFrameElement>('Где нефть');
    expect(frame).toHaveAttribute('src', SCENE.player_url);
    expect(screen.getByRole('status')).toHaveTextContent('Загружаем 3D-сцену');

    say(frame, { sim: 'ready' });
    expect(screen.queryByText('Загружаем 3D-сцену')).toBeNull();
    await user.click(screen.getByRole('button', { name: 'Закрыть симулятор' }));
    expect(document.querySelector('iframe')).toBeNull();
  });

  test('a broken scene says why and can be retried', async () => {
    const user = userEvent.setup();
    show({ scenes: [SCENE], run: null });
    await user.click(await screen.findByRole('button', { name: /Запустить/ }));
    say(screen.getByTitle<HTMLIFrameElement>('Где нефть'), { sim: 'error', text: 'Нужен WebGL 2.' });

    expect(screen.getByRole('alert')).toHaveTextContent('Нужен WebGL 2.');
    await user.click(screen.getByRole('button', { name: 'Повторить' }));
    expect(screen.getByTitle('Где нефть')).toBeVisible();
  });

  test('messages of other windows are ignored', async () => {
    const user = userEvent.setup();
    show({ scenes: [SCENE], run: null });
    await user.click(await screen.findByRole('button', { name: /Запустить/ }));
    fireEvent(window, new MessageEvent('message', { data: { sim: 'ready' }, source: window }));

    expect(screen.getByText('Загружаем 3D-сцену')).toBeVisible();
  });
});

describe('agent at work', () => {
  test('shows what is done and what goes on', async () => {
    show({ scenes: [], run: { ...RUN, retry: 1 } });
    expect(await screen.findByText('ИИ-агент строит симулятор')).toBeVisible();
    expect(within(screen.getByRole('list')).getByText('Считает физику')).toHaveAttribute('aria-current', 'step');
    expect(screen.getByRole('status')).toHaveTextContent('Сейчас: Считает физику. Готово 2 из 4');
    expect(screen.getByText(/попытка 1/)).toBeVisible();
    expect(screen.getByRole('button', { name: 'Остановить' })).toBeEnabled();
  });

  test('a failed run gives the reason', async () => {
    show({ scenes: [], run: { ...RUN, state: 'failed', reason: 'общий потолок 1.5' } });
    expect(await screen.findByText(/общий потолок 1.5/)).toBeVisible();
    expect(screen.getByText('Агент не достроил симулятор.')).toBeVisible();
  });

  test('a finished design asks for the next run', async () => {
    show({ scenes: [], run: { ...RUN, state: 'done', is_design_only: true } });
    expect(await screen.findByText('Замысел готов.')).toBeVisible();
  });

  test('nothing to show, no section', async () => {
    const { container } = show({ scenes: [], run: null });
    await new Promise((resolve) => setTimeout(resolve, 100));
    expect(container.querySelector('section')).toBeNull();
  });
});
