/** Главное из паспорта ролика. Паспорт приходит «как есть», поэтому читается осторожно. */

export interface PassportFacts {
  rows: { title: string; text: string }[];
  checklist: { total: number; passed: number; failed: number } | null;
}

const TEXTS: [key: string, title: string][] = [
  ['prediction_question', 'Вопрос на предсказание'], ['transfer_question', 'Вопрос на перенос'], ['data_it_bridge', 'Мост к данным'],
];

const strings = (value: unknown): string[] => (Array.isArray(value) ? value.filter((v): v is string => typeof v === 'string') : []);

function answerOf(item: unknown): string {
  if (typeof item !== 'object' || item === null || !('answer' in item)) return '';
  return typeof item.answer === 'string' ? item.answer : '';
}

export function passportFacts(passport: Record<string, unknown>): PassportFacts {
  const rows = TEXTS.flatMap(([key, title]) => {
    const text = passport[key];
    return typeof text === 'string' && text ? [{ title, text }] : [];
  });
  const exaggerations = strings(passport.exaggerations);
  const answers = Array.isArray(passport.physics_checklist) ? passport.physics_checklist.map(answerOf) : [];
  // «н/п» не считается: пункт к этому ролику не относится
  const judged = answers.filter((a) => a === 'да' || a === 'нет');
  const failed = judged.filter((a) => a === 'нет').length;
  return {
    rows: exaggerations.length ? [...rows, { title: 'Преувеличения', text: exaggerations.join('\n') }] : rows,
    checklist: judged.length ? { total: judged.length, passed: judged.length - failed, failed } : null,
  };
}
