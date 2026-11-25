import type { CoverageRow, ErrataRow, Illustration, RouteRow, Task, Video } from '@/api/types';

const by = (text: string) => ({ text, by_model: true });

export const rawNode = {
  id: 'demo.pores', order: 2, title: 'Доля пустот $k = V_п / V$ и почему её не измеряют взглядом',
  difficulty: { primary: 'Ф', secondary: null }, threshold: true, pages: [11],
  why_here: by('Предыдущий шаг показал, что виден только край. Здесь появляется число.'),
  layers: {
    topic: by('Сколько места в банке занимает воздух между песчинками.'),
    main: by('Доля пустот равна \\(k = \\frac{V_п}{V}\\): объём пустот делят на весь объём банки.'),
    mechanism: by('Песчинки опираются друг на друга и оставляют промежутки. Чем ровнее песчинки, тем промежутков больше.'),
    practice: by('Наливают воду до края песка и считают, сколько вошло: $V_п = 0,35$ л.'),
    nuances: by('Вода смачивает не все промежутки, поэтому ответ немного занижен.'),
    deeper: [by('Для шаров в простой укладке $$k = 1 - \\frac{\\pi}{6} \\approx 0,48$$')],
  },
  claims: [
    { id: 'demo.pores#c1', text: 'Долю пустот находят делением: $k = V_п / V$.', kind: 'observation', page_pdf: 11, page_print: 9,
      quote: 'Доля пустот равна объёму пустот, делённому на объём банки', source_kind: 'formula', by_model: false, needs_scan: false },
    { id: 'demo.pores#c2', text: 'По виду сбоку долю пустот не узнать.', kind: 'inference', page_pdf: 11, page_print: null,
      quote: 'Через стекло видно только крайние песчинки', source_kind: 'text', by_model: false, needs_scan: false },
    { id: 'demo.pores#c3', text: 'Ровный песок занимает больше места, чем смешанный.', kind: 'assumption', page_pdf: 12, page_print: null,
      quote: 'Ровные песчинки укладываются рыхлее, чем смесь', source_kind: 'figure_caption', by_model: true, needs_scan: true },
  ],
  links: [{ type: 'prerequisite', target: 'demo.look' }, { type: 'refutes_misconception', target: 'misc.see_is_measure' }],
  misconception: { ref: 'misc.see_is_measure', text: 'Кажется, что если песок видно, то и пустоты видно.', by_model: true },
  data_meaning: {
    from_chapter: by('В данных лежит объём воды, а не доля пустот: её считают.'), breaks: by('Если песок уже мокрый, воды войдёт меньше.'),
    hypotheses: [{ text: 'Вероятно, встряхивание меняет долю на несколько процентов.', by_model: true, hypothesis: true }],
  },
  it_analogy: { text: 'Похоже на занятое место на диске: файлы видно, а свободные блоки считает система.', breaks_where: 'Песчинки нельзя дефрагментировать без встряски.', by_model: true },
  now_practice: null,
  inefficiency_lens: { inputs: 'Записи объёмов на бумаге', manual_steps: 'Пересчёт в таблицу', judgment_points: 'Считать ли банку мокрой', time: 'в главе не указано', typical_errors: 'Путают литры и доли' },
  decision_on_data: { features: ['объём воды', 'объём банки'], rule: 'Если $k > 0,4$, песок ровный.', conclusion: 'Банку относят к ровным.', counterexample: 'Мокрый ровный песок даст меньше.' },
  worked_examples: [{ page_pdf: 12, condition: 'В банку 1 л вошло 0,35 л воды.', steps: ['Записать объёмы.', 'Разделить 0,35 на 1.'], result: '$k = 0,35$', figure: 'рис. 2' }],
  book_tasks: [{ number: '7', page_pdf: 12, text: 'Сколько воды войдёт в банку 2 л при той же доле?', figure: null }],
  terms_used: [], needs_scan: [{ page: 11, what: 'Рис. 1, на который ссылается текст: в этой части его нет.' }],
  glossary: [{ term: 'доля пустот', definition: 'часть объёма, которую не занимают песчинки' }],
};

export const routes: RouteRow[] = [
  { node_id: 'demo.look', format: 'карточки', secondary_format: null, video_scores: { time: 0, invisible: 1, scale: 0, counterintuitive: 1, cause_effect: 0 }, hook_short: false, template: null, why: 'Нужно узнать и назвать.' },
  { node_id: 'demo.pores', format: 'длинное видео', secondary_format: 'интерактив', video_scores: { time: 1, invisible: 2, scale: 1, counterintuitive: 2, cause_effect: 2 }, hook_short: true, template: 'compare', why: 'Пустоты не видно, а причина важна: видео показывает укладку изнутри.' },
];

export const tasks: Task[] = [
  { id: 't1', type: 'single', step_id: 'demo.pores', claim_ids: ['demo.pores#c1'], kind: 'understanding', prompt: 'Как найти долю пустот $k$?',
    options: [{ id: 'a', text: 'Посмотреть сквозь стекло', misconception: 'misc.see_is_measure' }, { id: 'b', text: 'Разделить $V_п$ на $V$', misconception: null }],
    answer: 'b', explanation: 'Через стекло виден только край.' },
  { id: 't2', type: 'multiple', step_id: 'demo.look', claim_ids: ['demo.look#c1'], kind: 'recall', prompt: 'Что видно через стекло?',
    options: [{ id: 'a', text: 'Крайние песчинки' }, { id: 'b', text: 'Все пустоты' }, { id: 'c', text: 'Цвет песка' }], answer: ['a', 'c'], explanation: 'Пустоты внутри не видны.' },
  { id: 't3', type: 'order', step_id: 'demo.look', claim_ids: ['demo.look#c2'], kind: 'understanding', prompt: 'Расположите действия по порядку.',
    options: [{ id: 'a', text: 'Посчитать долю' }, { id: 'b', text: 'Налить воду' }, { id: 'c', text: 'Записать объём' }], answer: ['b', 'c', 'a'], explanation: 'Сначала измеряют, потом считают.' },
  { id: 't4', type: 'gap', step_id: 'demo.shake', claim_ids: ['demo.shake#c1'], kind: 'recall', prompt: 'После встряски песок занимает {{1}} места, а доля пустот становится {{2}}.', answer: ['меньше', 'ниже'], explanation: 'Песчинки укладываются плотнее.' },
  { id: 't5', type: 'calc', step_id: 'demo.pores', claim_ids: ['demo.pores#c1'], kind: 'data', prompt: 'В банку 2 л вошло 0,7 л воды. Найдите $k$.', answer: 0.35, tolerance: 0.01, unit: null, explanation: '$k = 0,7 / 2 = 0,35$.' },
];

const picture = (id: string, step: string, caption: string): Illustration => ({
  id, step_id: step, node_id: step, file: `pictures/${id}.svg`, url: `/course/demo_sand/pictures/${id}.svg`, frame_class: 'B', origin: 'code_from_model',
  label: 'схема', caption, alt: caption, source: 'построено кодом по утверждениям шага', claim_ids: [],
});

export const illustrations: Illustration[] = [
  picture('jar', 'demo.pores', 'Банка в разрезе: песчинки и промежутки, доля $k = 0,35$'),
  picture('missing', 'demo.look', 'Вид сбоку: только крайний ряд'),
];

export const videos: Video[] = [
  { id: 'v1', chapter: 'demo_sand', title: 'Почему пустоты не видно', format: '9:16', duration_s: 62, url: '/course/demo_sand/videos/v1.mp4', subtitles_url: '/course/demo_sand/videos/v1.vtt',
    passport: { prediction_question: 'Сколько воды войдёт?', transfer_question: 'А если песок мокрый?', data_it_bridge: 'Объём воды это сырой замер.', exaggerations: ['Песчинки увеличены в 20 раз'], physics_checklist: [{ item: 'объём сохраняется', answer: 'да' }, { item: 'масштаб подписан', answer: 'да' }] },
    problems: [] },
  { id: 'v2', chapter: 'demo_sand', title: 'Две банки: разбор', format: '16:9', duration_s: 134, url: '/course/demo_sand/videos/v2.mp4', subtitles_url: null,
    passport: { physics_checklist: [{ item: 'знак изменения верный', answer: 'нет' }, { item: 'есть метка кадра', answer: 'да' }] }, problems: ['Нет файла субтитров', 'На 41-й секунде кадр без метки'] },
];

export const coverage: CoverageRow[] = [
  { unit_id: 'p010.01', kind: 'heading', page_pdf: 10, excerpt: 'Песок в банке', node_ids: ['demo.look'], reason: null },
  { unit_id: 'p010.02', kind: 'paragraph', page_pdf: 10, excerpt: 'Через стекло видно только крайние песчинки', node_ids: ['demo.look', 'demo.pores'], reason: null },
  { unit_id: 'p011.01', kind: 'formula', page_pdf: 11, excerpt: '$k = V_п / V$', node_ids: ['demo.pores'], reason: null },
  { unit_id: 'p012.01', kind: 'table', page_pdf: 12, excerpt: 'Таблица объёмов', node_ids: [], reason: 'повторяет пример на той же странице' },
];

export const errata: ErrataRow[] = [
  { page: 10, md: 'крайнне песчинки', scan: 'крайние песчинки', kind: 'recognition', note: 'лишняя буква' },
  { page: 11, md: '$k = V_в / V$', scan: '$k = V_п / V$', kind: 'recognition', note: 'индекс п, а не в' },
  { page: 12, md: '0,53 л', scan: '0,53 л', kind: 'suspect', note: 'рядом в тексте 0,35 л' },
];
