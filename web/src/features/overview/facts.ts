/** Числа и замечания обзора. Только то, что есть в данных конвейера: ни прогнозов, ни примеров. */
import type { ChapterCard, Health, Publication, Review, Run, StageName } from '@/api/types';
import { counted, FORMS } from '@/lib/format';
import { COMMAND, label, RUN_STATE, STAGE } from '@/lib/labels';

const WEEK_MS = 7 * 24 * 3600 * 1000;
const DAY_MS = 24 * 3600 * 1000;

const path = (id: string, tab = ''): string => `/admin/chapters/${encodeURIComponent(id)}${tab && `?tab=${tab}`}`;
const ready = (c: ChapterCard, names: readonly StageName[]): boolean => names.every((n) => c.stages.find((s) => s.name === n)?.state === 'ready');
const started = (c: ChapterCard): boolean => c.active_run !== null || c.stages.some((s) => s.state !== 'missing');
const coverage = (c: ChapterCard): number | null => (c.counts.units > 0 ? c.counts.units_covered / c.counts.units : null);
const maxTime = (c: ChapterCard): number => Math.max(0, ...c.stages.map((s) => (s.updated_at ? new Date(s.updated_at).getTime() || 0 : 0)));

export const isStarted = started;
export const coverageOf = coverage;
export const updatedAt = maxTime;

export interface Totals {
  chapters: number; started: number; fresh: number; courses: number; published: number; coverage: number | null; covered: number; units: number;
}

export function totalsOf(chapters: ChapterCard[], now: number): Totals {
  const withUnits = chapters.filter((c) => coverage(c) !== null);
  const covered = withUnits.reduce((s, c) => s + c.counts.units_covered, 0);
  const units = withUnits.reduce((s, c) => s + c.counts.units, 0);
  return {
    chapters: chapters.length, started: chapters.filter(started).length,
    fresh: chapters.filter((c) => maxTime(c) > now - WEEK_MS).length,
    courses: chapters.filter((c) => c.course_url).length, published: chapters.filter((c) => c.published_at).length,
    coverage: units > 0 ? covered / units : null, covered, units,
  };
}

export type StepState = 'done' | 'current' | 'waiting';
export interface PipelineStep { title: string; done: number; total: number; state: StepState }

const STEPS: readonly (readonly [string, (c: ChapterCard) => boolean])[] = [
  ['Сверка со сканом', (c) => ready(c, ['errata'])],
  ['Учебный слой', (c) => ready(c, ['layer'])],
  ['Форматы и задания', (c) => ready(c, ['routing', 'tasks', 'illustrations'])],
  ['Сборка курса', (c) => ready(c, ['course'])],
  ['Публикация', (c) => Boolean(c.published_at)],
];

export function pipelineOf(chapters: ChapterCard[]): PipelineStep[] {
  const total = chapters.length;
  return STEPS.map(([title, isDone]) => {
    const done = chapters.filter(isDone).length;
    return { title, done, total, state: total > 0 && done === total ? 'done' : done > 0 ? 'current' : 'waiting' };
  });
}

export type Level = 'bad' | 'warn' | 'info';
export interface Attention { id: string; level: Level; text: string; where: string; to: string }

export interface AttentionInput {
  chapters: ChapterCard[]; reviews?: Review[]; runs?: Run[]; health?: Health; publications?: { chapter: ChapterCard; state: Publication }[]; now: number;
}

const ORDER: Record<Level, number> = { bad: 0, warn: 1, info: 2 };

/** Что требует внимания. Каждая строка ведёт туда, где это исправляют. */
export function attentionOf({ chapters, reviews = [], runs = [], health, publications = [], now }: AttentionInput): Attention[] {
  const found: Attention[] = [];
  const add = (id: string, level: Level, text: string, where: string, to: string): void => void found.push({ id, level, text, where, to });
  for (const c of chapters) {
    if (c.issues > 0) add(`issues:${c.id}`, 'bad', counted(c.issues, FORMS.issue), c.title, path(c.id));
    const stale = c.stages.filter((s) => s.state === 'stale');
    if (stale.length) add(`stale:${c.id}`, 'warn', `Устарело: ${stale.map((s) => label(STAGE, s.name).toLowerCase()).join(', ')}`, c.title, path(c.id, 'build'));
    if (started(c) && c.counts.units > c.counts.units_covered) {
      add(`units:${c.id}`, 'info', `Не покрыто: ${counted(c.counts.units - c.counts.units_covered, FORMS.unit)} главы`, c.title, path(c.id, 'coverage'));
    }
  }
  for (const { chapter, state } of publications) {
    if (state.problem) add(`publish:${chapter.id}`, 'warn', state.problem, chapter.title, path(chapter.id, 'trust'));
    for (const check of state.checks) add(`check:${chapter.id}:${check.code}`, 'warn', check.text, chapter.title, path(chapter.id, 'trust'));
  }
  for (const r of reviews) {
    if (r.counts.critical > 0) add(`review:${r.package_id}`, 'bad', `Критических замечаний: ${r.counts.critical}`, `Пакет ${r.package_id}`, `/admin/review/${encodeURIComponent(r.package_id)}`);
  }
  for (const run of runs) {
    const ended = run.finished_at ? new Date(run.finished_at).getTime() : 0;
    if (run.state === 'failed' && ended > now - DAY_MS) {
      add(`run:${run.id}`, 'bad', `${label(COMMAND, run.command)}: ошибка`, chapters.find((c) => c.id === run.chapter)?.title ?? run.chapter, `/admin/runs?run=${encodeURIComponent(run.id)}`);
    }
  }
  if (health?.provider === 'claude_code' && !health.claude_found) add('claude', 'bad', 'Не найден Claude Code: сборка не запустится', 'Настройки', '/admin/model');
  if (health && !health.ffmpeg_found) add('ffmpeg', 'info', 'Не найден ffmpeg: ролики не соберутся', 'Настройки', '/admin/model');
  return found.sort((a, b) => ORDER[a.level] - ORDER[b.level]);
}

export type Quality = { tone: 'good' | 'warn' | 'bad' | 'info' | 'neutral'; text: string };

export function qualityOf(c: ChapterCard): Quality {
  if (c.active_run) return { tone: 'info', text: 'В работе' };
  if (!started(c)) return { tone: 'neutral', text: 'Ожидает' };
  if (c.issues > 0) return { tone: 'bad', text: 'Есть замечания' };
  if (c.stages.some((s) => s.state === 'stale')) return { tone: 'warn', text: 'Устарело' };
  if (c.published_at) return { tone: 'good', text: 'Опубликован' };
  return c.course_url ? { tone: 'good', text: 'Готово' } : { tone: 'info', text: 'Не завершено' };
}

export interface StageNow { text: string; tone: 'brand' | 'info' | 'good' | 'neutral' }

/** На каком этапе глава: первый неготовый, а если готовы все — курс. */
export function stageOf(c: ChapterCard): StageNow {
  if (!started(c)) return { text: 'Не начата', tone: 'neutral' };
  if (c.published_at) return { text: 'Опубликован', tone: 'good' };
  const next = c.stages.find((s) => s.state === 'missing');
  if (next) return { text: label(STAGE, next.name), tone: next.name === 'course' ? 'info' : 'brand' };
  return { text: 'Курс собран', tone: 'good' };
}

/** «Латышова М. Г. Практическое…, 1991, гл. V §17–20» → автор с годом и место в книге. */
export function sourceOf(book: string): { who: string; where: string } {
  const year = /\b(1[89]\d\d|20\d\d)\b/.exec(book);
  const author = /^[А-ЯЁA-Z][\p{L}-]+/u.exec(book)?.[0] ?? book;
  const where = year ? book.slice(year.index + 4).replace(/^[\s,.]+/, '') : '';
  return { who: year ? `${author}, ${year[0]}` : author, where };
}

export interface Event { id: string; title: string; where: string; at: number; kind: 'run' | 'stage'; state: 'good' | 'bad' | 'live' | 'plain'; to: string }

/** Последние события: запуски и обновления этапов. */
export function eventsOf(chapters: ChapterCard[], runs: Run[], limit: number): Event[] {
  const name = (id: string): string => chapters.find((c) => c.id === id)?.title ?? id;
  const fromRuns = runs.map((r): Event => ({
    id: r.id, kind: 'run', title: `${label(COMMAND, r.command)}: ${RUN_STATE[r.state].toLowerCase()}`, where: name(r.chapter),
    at: new Date(r.finished_at ?? r.started_at ?? 0).getTime() || 0, to: `/admin/runs?run=${encodeURIComponent(r.id)}`,
    state: r.state === 'failed' ? 'bad' : r.state === 'done' ? 'good' : r.state === 'running' ? 'live' : 'plain',
  }));
  const fromStages = chapters.flatMap((c) => c.stages.filter((s) => s.updated_at).map((s): Event => ({
    id: `${c.id}:${s.name}`, kind: 'stage', title: `${label(STAGE, s.name)}: обновлено`, where: c.title, at: new Date(s.updated_at ?? 0).getTime() || 0, to: path(c.id), state: 'plain',
  })));
  return [...fromRuns, ...fromStages].sort((a, b) => b.at - a.at).slice(0, limit);
}

/** «2 ч назад». Дальше недели — датой. */
export function ago(at: number, now: number): string {
  if (!at) return '—';
  const minutes = Math.max(0, Math.round((now - at) / 60_000));
  if (minutes < 1) return 'только что';
  if (minutes < 60) return `${minutes} мин назад`;
  if (minutes < 24 * 60) return `${Math.round(minutes / 60)} ч назад`;
  if (minutes < 7 * 24 * 60) return `${Math.round(minutes / 1440)} д назад`;
  return new Date(at).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short', year: 'numeric' });
}
