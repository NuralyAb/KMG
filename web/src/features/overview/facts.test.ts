import { describe, expect, test } from 'vitest';
import type { ChapterCard, Run, StageName, StageState } from '@/api/types';
import { ago, attentionOf, eventsOf, pipelineOf, qualityOf, sourceOf, stageOf, totalsOf } from './facts';

const NOW = new Date('2026-11-26T12:00:00Z').getTime();
const NAMES: StageName[] = ['errata', 'layer', 'routing', 'tasks', 'illustrations', 'course'];
const none: StageState[] = NAMES.map(() => 'missing');
const all: StageState[] = NAMES.map(() => 'ready');

function card(id: string, states: StageState[] = none, over: Partial<ChapterCard> = {}): ChapterCard {
  return {
    id, title: `Глава ${id}`, book: 'Латышова М. Г. Практическое руководство, 1991, гл. V §17–20', domain: 'geology', pages: [1],
    counts: { nodes: 4, claims: 9, tasks: 3, illustrations: 2, errata: 0, units: 10, units_covered: 9, videos: 0 }, issues: 0,
    stages: NAMES.map((name, i) => ({ name, state: states[i] ?? 'missing', updated_at: (states[i] ?? 'missing') === 'missing' ? null : '2026-11-26T10:00:00Z' })),
    cost_usd: 0, tokens_in: 0, tokens_out: 0, course_url: states[5] === 'ready' ? '/course/x/index.html' : null, active_run: null, ...over,
  };
}
const failed = (finished_at: string): Run => ({ id: 'r1', command: 'layer', chapter: 'a', args: {}, state: 'failed', started_at: null, finished_at, exit_code: 1, log_tail: [] });

describe('обзор', () => {
  test('числа берутся из глав, а не придумываются', () => {
    expect(totalsOf([card('a', all), card('b')], NOW)).toMatchObject({ chapters: 2, started: 1, fresh: 1, courses: 1, published: 0, covered: 18, units: 20, coverage: 0.9 });
    expect(totalsOf([], NOW).coverage).toBeNull();
  });

  test('этап конвейера готов, только когда готов у всех глав', () => {
    expect(pipelineOf([card('a', all), card('b', all)]).map((s) => s.state)).toEqual(['done', 'done', 'done', 'done', 'waiting']);
    expect(pipelineOf([card('a', all), card('b')])[1]).toMatchObject({ state: 'current', done: 1, total: 2 });
    expect(pipelineOf([]).every((s) => s.state === 'waiting')).toBe(true);
  });

  test('замечания отсортированы по серьёзности и ведут по адресу', () => {
    const stale = card('a', ['ready', 'ready', 'ready', 'ready', 'stale', 'ready'], { issues: 2 });
    const health = { status: 'ok', provider: 'claude_code', model: 'sonnet', claude_found: false, ffmpeg_found: true };
    const found = attentionOf({ chapters: [stale], now: NOW, health, runs: [failed('2026-11-26T11:00:00Z')] });
    expect(found.map((f) => f.level)).toEqual(['bad', 'bad', 'bad', 'warn', 'info']);
    expect(found.find((f) => f.id === 'stale:a')).toMatchObject({ text: 'Устарело: рисунки', to: '/admin/chapters/a?tab=build' });
    expect(attentionOf({ chapters: [card('b')], now: NOW })).toEqual([]);
  });

  test('старая ошибка запуска больше не требует внимания', () => {
    expect(attentionOf({ chapters: [], runs: [failed('2026-11-20T11:00:00Z')], now: NOW })).toEqual([]);
  });

  test('статус и этап главы', () => {
    expect([card('a'), card('a', all), card('a', all, { issues: 1 }), card('a', all, { active_run: 'r' })].map((c) => qualityOf(c).text))
      .toEqual(['Ожидает', 'Готово', 'Есть замечания', 'В работе']);
    expect([card('a'), card('a', ['ready', 'ready']), card('a', all)].map((c) => stageOf(c).text)).toEqual(['Не начата', 'Маршрут', 'Курс собран']);
  });

  test('источник, время и события', () => {
    expect(sourceOf('Латышова М. Г. Практическое руководство, 1991, гл. V §17–20')).toEqual({ who: 'Латышова, 1991', where: 'гл. V §17–20' });
    expect(sourceOf('Книга.pdf')).toEqual({ who: 'Книга', where: '' });
    expect([ago(NOW - 2 * 3_600_000, NOW), ago(NOW - 26 * 3_600_000, NOW), ago(0, NOW)]).toEqual(['2 ч назад', '1 д назад', '—']);
    expect(eventsOf([card('a', all)], [], 3)).toHaveLength(3);
  });
});
