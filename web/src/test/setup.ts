import '@testing-library/jest-dom/vitest';
import { cleanup, configure } from '@testing-library/react';
import { afterEach, vi } from 'vitest';

// экраны грузятся лениво: первый импорт на холодном кэше дольше секунды
configure({ asyncUtilTimeout: 8_000 });
afterEach(() => cleanup());

// Mantine спрашивает тему и размеры, jsdom этого не умеет
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: (query: string) => ({
    matches: false, media: query, onchange: null, addListener: vi.fn(), removeListener: vi.fn(),
    addEventListener: vi.fn(), removeEventListener: vi.fn(), dispatchEvent: vi.fn(),
  }),
});

class ResizeObserverStub {
  observe(): void {}
  unobserve(): void {}
  disconnect(): void {}
}
vi.stubGlobal('ResizeObserver', ResizeObserverStub);
window.HTMLElement.prototype.scrollIntoView = vi.fn();
window.scrollTo = vi.fn();
