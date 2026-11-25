import type { LearnCourse, Publication } from '@/api/types';

export const courses: LearnCourse[] = [
  { id: 'demo_sand', title: 'Песок в банке', book: 'Учебная книга', steps: 2, minutes: 75, tasks: 3, published_at: '2026-11-25T12:00:00Z',
    parts: [{ title: 'Часть', steps: [{ id: 'demo.look', order: 1, title: 'Что видно', minutes: 35 }, { id: 'demo.pores', order: 2, title: 'Пустоты', minutes: 40 }] }] },
];

export const publication: Publication = {
  published_at: null, is_current: false, problem: null, accepted: [],
  checks: [{ code: 'flagged:2', text: 'Утверждений, которые расходятся с цитатой: 2' }, { code: 'no_verify:1', text: 'Вторая модель эту версию слоя не проверяла' }],
};
