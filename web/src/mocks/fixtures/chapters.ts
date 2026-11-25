import type { ChapterCard, ChapterDetail, NodeRow, Stage, StageName, StageState } from '@/api/types';

/** Выдуманные данные: про песок в стеклянной банке, без текстов книг. */

const AT = '2026-11-25T14:20:00+05:00';

const stages = (states: StageState[]): Stage[] =>
  (['errata', 'layer', 'routing', 'tasks', 'illustrations', 'course'] as StageName[])
    .map((name, i) => ({ name, state: states[i] ?? 'missing', updated_at: states[i] === 'missing' ? null : AT }));

const none = stages(['missing', 'missing', 'missing', 'missing', 'missing', 'missing']);
const zero = { nodes: 0, claims: 0, tasks: 0, illustrations: 0, errata: 0, units: 0, units_covered: 0, videos: 0 };

export const demo: ChapterCard = {
  id: 'demo_sand', title: 'Песок в банке: что мы видим и что додумываем', book: 'Образец А. Учебная книга, 2020, гл. 1', domain: 'demo',
  pages: [10, 11, 12, 13, 14], counts: { nodes: 4, claims: 7, tasks: 5, illustrations: 2, errata: 3, units: 12, units_covered: 11, videos: 2 },
  issues: 2, stages: stages(['ready', 'ready', 'ready', 'stale', 'ready', 'ready']), cost_usd: 16.4231, tokens_in: 2_903_000, tokens_out: 1_190_000,
  course_url: '/course/demo_sand/index.html', active_run: null,
};

export const running: ChapterCard = {
  id: 'demo_water', title: 'Как вода проходит через слой песка', book: 'Образец Б. Учебная книга, 2018, гл. 3', domain: 'demo',
  pages: [30, 31, 32], counts: { ...zero, errata: 9, units: 40 }, issues: 0,
  stages: stages(['ready', 'missing', 'missing', 'missing', 'missing', 'missing']), cost_usd: 0.9182, tokens_in: 328_797, tokens_out: 24_988,
  course_url: null, active_run: 'run-live',
};

export const waiting: ChapterCard[] = [
  { id: 'demo_stones', title: 'Камни разного размера', book: 'Образец В. Учебная книга, 2012, гл. 10', domain: 'demo', pages: [5, 6, 7, 9], counts: zero,
    issues: 0, stages: none, cost_usd: 0, tokens_in: 0, tokens_out: 0, course_url: null, active_run: null },
  { id: 'demo_pressure', title: 'Давление в закрытой банке', book: 'Образец Г. Учебная книга, 1984, §4', domain: 'demo', pages: [38, 39], counts: zero,
    issues: 0, stages: none, cost_usd: 0, tokens_in: 0, tokens_out: 0, course_url: null, active_run: null },
];

const node = (order: number, slug: string, title: string, extra: Partial<NodeRow> = {}): NodeRow => ({
  id: `demo.${slug}`, order, title, short_title: title, difficulty: { primary: 'М', secondary: null }, threshold: false,
  pages: [9 + order], claims: 2, tasks: 1, format: 'карточки', needs_scan: 0, ...extra,
});

export const nodes: NodeRow[] = [
  node(1, 'look', 'Что видно через стекло', { difficulty: { primary: 'И', secondary: 'Н' }, tasks: 2 }),
  node(2, 'pores', 'Доля пустот $k = V_п / V$ и почему её не измеряют взглядом', { threshold: true, difficulty: { primary: 'Ф', secondary: null }, format: 'длинное видео', tasks: 2, claims: 3 }),
  node(3, 'shake', 'Что меняется, если банку встряхнуть', { needs_scan: 1, format: 'интерактив', claims: 1 }),
  node(4, 'decide', 'Решение по двум банкам', { difficulty: { primary: 'Пр', secondary: 'Н' }, format: 'практикум на данных', claims: 1, tasks: 0 }),
];

export const demoDetail: ChapterDetail = {
  ...demo,
  parts: [{ title: 'Наблюдение', nodes: nodes.slice(0, 2) }, { title: 'Проверка и решение', nodes: nodes.slice(2) }],
};

export const cards: ChapterCard[] = [demo, running, ...waiting];

export const detailOf = (id: string): ChapterDetail | null => {
  if (id === demo.id) return demoDetail;
  const card = cards.find((c) => c.id === id);
  return card ? { ...card, parts: [] } : null;
};
