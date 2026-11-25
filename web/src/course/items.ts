import { blocksOf } from './sections';
import type { Step } from './types';

/** Урок делится на элементы, как на больших площадках: смотреть, читать, пробовать, проверять себя. */
export type ItemKind = 'video' | 'talk' | 'read' | 'sim' | 'quiz';
export interface Item { id: ItemKind; title: string; kind: string; meta: string }

const clock = (t: number): string => `${Math.floor(t / 60)}:${String(Math.round(t % 60)).padStart(2, '0')}`;
const counted = (n: number, [one, few, many]: [string, string, string]): string => {
  const [tens, units] = [n % 100, n % 10];
  return `${n} ${tens > 10 && tens < 20 ? many : units === 1 ? one : units > 1 && units < 5 ? few : many}`;
};

export function itemsOf(step: Step): Item[] {
  const sims = (step.interactive?.params as { items?: unknown[] } | undefined)?.items?.length ?? 0;
  const quiz = step.tasks.length + (step.book_tasks?.length ?? 0);
  return [
    ...(step.videos.length ? [{ id: 'video' as const, title: step.videos[0]?.title ?? step.short_title, kind: 'Ролик', meta: step.videos.length > 1 ? `${step.videos.length} ролика` : 'видео' }] : []),
    ...(step.narration ? [{ id: 'talk' as const, title: 'Разбор урока', kind: 'Видео', meta: clock(step.narration.duration) }] : []),
    { id: 'read', title: step.short_title || step.title, kind: 'Чтение', meta: `${step.minutes} мин` },
    ...(step.interactive ? [{ id: 'sim' as const, title: sims > 1 ? 'Симуляторы' : 'Симулятор', kind: 'Практика', meta: sims > 1 ? counted(sims, ['сцена', 'сцены', 'сцен']) : '3D' }] : []),
    ...(quiz ? [{ id: 'quiz' as const, title: 'Проверьте себя', kind: 'Тренировка', meta: counted(step.tasks.length || quiz, ['задание', 'задания', 'заданий']) }] : []),
  ];
}

const ITEMS = new Set<string>(['video', 'talk', 'read', 'sim', 'quiz']);
const NOTES = 'notes';

/** Элемент по адресу: имя элемента или раздела чтения (#/step/3/how ведёт в чтение и к разделу). */
export function itemFor(step: Step, section: string | null): Item {
  const items = itemsOf(step);
  const first = items[0] as Item;
  if (!section) return first;
  if (ITEMS.has(section)) return items.find((x) => x.id === section) ?? first;
  if (section === NOTES) return items.find((x) => x.id === 'talk' || x.id === 'video') ?? items.find((x) => x.id === 'read') ?? first;
  const tab = blocksOf(step).find((b) => b.id === section)?.tab;
  return items.find((x) => x.id === (tab === 'tasks' ? 'quiz' : 'read')) ?? first;
}

export const itemUrl = (step: Step, item: ItemKind): string => `#/step/${step.order}/${item}`;
