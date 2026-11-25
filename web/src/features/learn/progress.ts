/** Прогресс пишет сам курс в браузер ученика: ключ glava.<id>. Здесь он только читается. */

export interface Progress { done: number; last: number | null }

export const progressKey = (course: string): string => `glava.${course}`;

/** Чужие и лишние шаги не считаются: в браузере могла остаться запись о прежней версии курса. */
export function readProgress(course: string, steps: ReadonlySet<string>, storage: Pick<Storage, 'getItem'> = window.localStorage): Progress {
  try {
    const raw: unknown = JSON.parse(storage.getItem(progressKey(course)) ?? 'null');
    if (typeof raw !== 'object' || raw === null) return { done: 0, last: null };
    const { done, last } = raw as { done?: unknown; last?: unknown };
    const found = Array.isArray(done) ? new Set(done.filter((id): id is string => typeof id === 'string' && steps.has(id))).size : 0;
    return { done: found, last: typeof last === 'number' && Number.isInteger(last) && last > 0 ? last : null };
  } catch {
    return { done: 0, last: null };
  }
}

/** Адрес файла курса внутри /learn/; шаг, на котором остановились, — в хвосте адреса. */
export function courseSrc(course: string, last: number | null): string {
  return `/learn/${encodeURIComponent(course)}/index.html${last === null ? '' : `#/step/${last}`}`;
}
