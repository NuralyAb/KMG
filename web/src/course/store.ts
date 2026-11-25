import { useSyncExternalStore } from 'react';
import { cleanState, type State } from './core';
import type { Course } from './types';

/** Прогресс ученика: localStorage браузера, ключ glava.<id>. Формат читает и каталог (features/learn/progress.ts). */
export interface Store { get: () => State; set: (patch: Partial<State>) => void; subscribe: (listener: () => void) => () => void }

export function createStore(course: Course): Store {
  const key = `glava.${course.id}`;
  const load = (): unknown => {
    try { return JSON.parse(localStorage.getItem(key) ?? 'null'); } catch { return null; }
  };
  let state = cleanState(load(), course.steps.map((s) => s.id));
  const listeners = new Set<() => void>();
  return {
    get: () => state,
    set: (patch) => {
      state = { ...state, ...patch };
      try { localStorage.setItem(key, JSON.stringify(state)); } catch { /* приватное окно: прогресс живёт до закрытия */ }
      listeners.forEach((listener) => listener());
    },
    subscribe: (listener) => { listeners.add(listener); return () => { listeners.delete(listener); }; },
  };
}

export const useStore = (store: Store): State => useSyncExternalStore(store.subscribe, store.get);

let timer = 0;
/** Текст для читалки: единственная живая область стоит в index.html. */
export function say(text: string): void {
  const live = document.getElementById('live');
  if (!live) return;
  live.textContent = '';
  window.clearTimeout(timer);
  timer = window.setTimeout(() => { live.textContent = text; }, 60);
}
