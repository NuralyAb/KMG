import type { MetricRow, Review, Run } from '@/api/types';

const run = (id: string, extra: Partial<Run>): Run => ({
  id, command: 'build', chapter: 'demo_sand', args: {}, state: 'done', started_at: '2026-11-25T13:00:00+05:00', finished_at: '2026-11-25T13:24:10+05:00',
  exit_code: 0, log_tail: ['слой: узлов 4, утверждений 7', 'курс: out/demo_sand/index.html'], ...extra,
});

export const runs: Run[] = [
  run('run-live', { chapter: 'demo_water', command: 'layer', state: 'running', started_at: '2026-11-25T14:30:00+05:00', finished_at: null, exit_code: null, log_tail: ['план: узлов 12, собираю 12'] }),
  run('run-done', {}),
  run('run-fail', { command: 'tasks', state: 'failed', exit_code: 1, started_at: '2026-11-25T12:10:00+05:00', finished_at: '2026-11-25T12:10:42+05:00', log_tail: ['задания: узел demo.shake', 'ошибка: модель не ответила'] }),
];

export const logLines = [
  'план: узлов 12, собираю 12', 'узел 1 из 12 готов', 'узел 2 из 12 готов', 'узел 3 из 12: повтор, цитата не найдена на странице 31',
  'узел 3 из 12 готов', 'узел 4 из 12 готов',
];

export const reviews: Review[] = [
  { package_id: 'demo_package', chapter: 'demo_sand', created_at: '2026-11-24T18:00:00+05:00', counts: { critical: 1, significant: 2, minor: 1 },
    remarks: [
      { target: 'C004', category: 'sign_flip', severity: 'critical', problem: 'Сказано, что после встряски доля пустот растёт.', fix: 'После встряски доля пустот $k$ уменьшается.', page_pdf: 13, quote: 'Встряхнутый песок ложится плотнее, \\(k\\) меньше' },
      { target: 'C009', category: 'measured_vs_inferred', severity: 'significant', problem: 'Доля пустот названа измеренной.', fix: 'Измеряют объём воды, долю считают.', page_pdf: 11, quote: 'Доля равна объёму пустот, делённому на объём банки' },
      { target: 'F02', category: 'frame_error', severity: 'significant', problem: 'На кадре не подписан масштаб.', fix: 'Подписать увеличение песчинок.', page_pdf: null, quote: null },
      { target: 'C015', category: 'missing_caveat', severity: 'minor', problem: 'Нет оговорки про мокрый песок.', fix: 'Добавить: вода входит хуже, если песок мокрый.', page_pdf: 12, quote: 'Мокрый песок примет меньше' },
    ] },
  { package_id: 'demo_clean', chapter: null, created_at: '2026-11-23T09:30:00+05:00', counts: { critical: 0, significant: 0, minor: 0 }, remarks: [] },
];

const row = (chapter: string, stage: string, inTokens: number, outTokens: number, money: number): MetricRow => ({
  chapter, stage, nodes: 4, llm_tokens_in: inTokens, llm_tokens_out: outTokens, money_usd: money, person_minutes: 0, mentor_minutes: 0, video_seconds: 0, manual_share: 0,
});

export const metrics: MetricRow[] = [
  row('demo_sand', 'errata', 328_000, 25_000, 0.92), row('demo_sand', 'layer', 1_391_000, 760_000, 11.79), row('demo_sand', 'layer', 457_000, 354_000, 0.36),
  row('demo_sand', 'routing', 12_500, 9_800, 0.15), row('demo_sand', 'tasks', 130_000, 48_900, 1.02), row('demo_sand', 'illustrations', 243_000, 58_000, 1.54),
  row('demo_water', 'errata', 328_797, 24_988, 0.9182), row('demo_sand', 'review', 751_000, 39_900, 2.82),
];
