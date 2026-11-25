/** Числа, даты и склонения для русского интерфейса. Неразрывный пробел держит число с единицей. */

const NBSP = ' ';
/** Склейка: диапазон страниц не рвётся на строке. */
const JOIN = '⁠';
const LOCALE = 'ru-RU';
const EMPTY = '—';
const CENT = 0.01;

const integer = new Intl.NumberFormat(LOCALE, { maximumFractionDigits: 0 });
const decimal = new Intl.NumberFormat(LOCALE, { maximumFractionDigits: 1 });
const dateTime = new Intl.DateTimeFormat(LOCALE, { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });

export function formatInt(value: number): string {
  return Number.isFinite(value) ? integer.format(value) : EMPTY;
}

export function formatMoney(value: number): string {
  if (!Number.isFinite(value)) return EMPTY;
  if (value > 0 && value < CENT) return `<${NBSP}$0,01`;
  return `$${value.toLocaleString(LOCALE, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export function formatTokens(value: number): string {
  if (!Number.isFinite(value)) return EMPTY;
  if (value >= 1_000_000) return `${decimal.format(value / 1_000_000)}${NBSP}млн`;
  if (value >= 1_000) return `${integer.format(value / 1_000)}${NBSP}тыс.`;
  return integer.format(value);
}

/** Доля в процентах. 100 % показывается только при полном покрытии, 0 % — только при нулевом. */
export function formatPercent(part: number, whole: number): string {
  if (!(whole > 0)) return EMPTY;
  const exact = (part / whole) * 100;
  const rounded = part >= whole ? 100 : Math.min(99, part > 0 ? Math.max(1, Math.round(exact)) : 0);
  return `${rounded}${NBSP}%`;
}

export function formatDateTime(iso: string | null): string {
  if (!iso) return EMPTY;
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? EMPTY : dateTime.format(date);
}

export function formatDuration(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) return EMPTY;
  const total = Math.round(seconds);
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const rest = total % 60;
  if (hours) return `${hours}${NBSP}ч ${minutes}${NBSP}мин`;
  return minutes ? `${minutes}${NBSP}мин ${rest}${NBSP}с` : `${rest}${NBSP}с`;
}

export function runDuration(start: string | null, end: string | null, now: number): string {
  if (!start) return EMPTY;
  const from = new Date(start).getTime();
  const to = end ? new Date(end).getTime() : now;
  return Number.isNaN(from) || Number.isNaN(to) ? EMPTY : formatDuration(Math.max(0, (to - from) / 1000));
}

/** Страницы подряд сворачиваются в диапазон: 9, 10, 11, 20 → «9–11, 20». */
export function formatPages(pages: number[]): string {
  const sorted = [...new Set(pages)].sort((a, b) => a - b);
  const ranges: [number, number][] = [];
  for (const page of sorted) {
    const last = ranges[ranges.length - 1];
    if (last && page === last[1] + 1) ranges[ranges.length - 1] = [last[0], page];
    else ranges.push([page, page]);
  }
  return ranges.map(([a, b]) => (a === b ? String(a) : `${a}–${JOIN}${b}`)).join(', ') || EMPTY;
}

export type Forms = readonly [one: string, few: string, many: string];

export function plural(count: number, forms: Forms): string {
  const abs = Math.abs(Math.trunc(count));
  const tens = abs % 100;
  const units = abs % 10;
  if (units === 1 && tens !== 11) return forms[0];
  if (units >= 2 && units <= 4 && (tens < 12 || tens > 14)) return forms[1];
  return forms[2];
}

export function counted(count: number, forms: Forms): string {
  return `${formatInt(count)}${NBSP}${plural(count, forms)}`;
}

export const FORMS = {
  node: ['шаг', 'шага', 'шагов'],
  lesson: ['урок', 'урока', 'уроков'],
  module: ['модуль', 'модуля', 'модулей'],
  claim: ['утверждение', 'утверждения', 'утверждений'],
  task: ['задание', 'задания', 'заданий'],
  picture: ['рисунок', 'рисунка', 'рисунков'],
  video: ['ролик', 'ролика', 'роликов'],
  remark: ['замечание', 'замечания', 'замечаний'],
  issue: ['замечание слоя', 'замечания слоя', 'замечаний слоя'],
  result: ['совпадение', 'совпадения', 'совпадений'],
  unit: ['единица', 'единицы', 'единиц'],
  chapter: ['глава', 'главы', 'глав'],
  page: ['страница', 'страницы', 'страниц'],
  file: ['файл', 'файла', 'файлов'],
} as const satisfies Record<string, Forms>;
