import type { PageState, ProviderName, RunCommand, RunState, SourceState, Verdict, Severity, StageName, StageState, TaskType } from '@/api/types';

/** Русские подписи значений контракта. Незнакомое значение показывается как есть, а не прячется. */
export function label(map: Readonly<Record<string, string>>, key: string | null | undefined): string {
  if (!key) return '—';
  return Object.hasOwn(map, key) ? (map[key] ?? key) : key;
}

export const STAGE: Record<StageName, string> = {
  errata: 'Опечатки', layer: 'Слой', routing: 'Маршрут', tasks: 'Задания', illustrations: 'Рисунки', course: 'Курс',
};

export const STAGE_STATE: Record<StageState, string> = { ready: 'готово', stale: 'устарело', missing: 'нет' };

export const COMMAND: Record<RunCommand, string> = {
  build: 'Вся сборка', ...STAGE, review: 'Проверка пакета', simulation: 'Симулятор', video: 'Ролик', extract: 'Извлечение текста', audit: 'Сверка кодом', verify: 'Проверка моделью',
};

export const RUN_STATE: Record<RunState, string> = {
  queued: 'В очереди', running: 'Идёт', done: 'Готово', failed: 'Ошибка', cancelled: 'Отменён',
};

export const DIFFICULTY: Record<string, string> = {
  'М': 'механизм', 'В': 'геологическое время', 'И': 'косвенное измерение', 'Ф': 'формализм',
  'П': 'пространство', 'Пр': 'процедура', 'Н': 'неопределённость', 'Р': 'распознавание',
};

export const CLAIM_KIND: Record<string, string> = { observation: 'наблюдение', inference: 'вывод', assumption: 'допущение' };

export const SOURCE_KIND: Record<string, string> = {
  text: 'текст', formula: 'формула', table: 'таблица', task: 'задача', figure_caption: 'подпись рисунка',
  figure_description_model: 'описание рисунка моделью',
};

export const UNIT_KIND: Record<string, string> = {
  paragraph: 'абзац', figure: 'рисунок', formula: 'формула', table: 'таблица', worked_example: 'разобранный пример',
  task: 'задача', heading: 'заголовок',
};

export const ERRATA_KIND: Record<string, string> = { recognition: 'ошибка распознавания', suspect: 'сомнительное место издания' };

export const TASK_TYPE: Record<TaskType, string> = {
  single: 'один ответ', multiple: 'несколько ответов', order: 'порядок', gap: 'пропуск', calc: 'расчёт',
};

export const TASK_KIND: Record<string, string> = {
  recall: 'вспомнить', understanding: 'понять', transfer: 'перенести', data: 'решить по данным',
};

export const SEVERITY: Record<Severity, string> = { critical: 'Критические', significant: 'Существенные', minor: 'Мелкие' };

export const CATEGORY: Record<string, string> = {
  overgeneralization: 'лишнее обобщение', sign_flip: 'перевёрнутый знак', measured_vs_inferred: 'измеренное вместо выведенного',
  lost_condition: 'потеряно условие', missing_caveat: 'нет оговорки', wrong_scaling: 'неверный масштаб',
  wrong_mechanism: 'неверный механизм', outdated_as_current: 'устаревшее как нынешнее',
  analogy_without_limit: 'аналогия без границ', frame_error: 'ошибка в кадре', other: 'другое',
};

export const SCORE: Record<string, string> = {
  time: 'меняется во времени', invisible: 'невидимое', scale: 'масштаб', counterintuitive: 'против интуиции',
  cause_effect: 'причина и следствие',
};

export const FRAME_CLASS: Record<string, string> = { A: 'A, данные', B: 'B, модель', C: 'C, внешний вид', D: 'D, настроение' };

export const ORIGIN: Record<string, string> = {
  code_from_data: 'кодом по данным', code_from_model: 'кодом по модели', photo: 'фото', redrawn_from_book: 'перерисовано',
  ai_generated: 'создано ИИ',
};

export const LINK_TYPE: Record<string, string> = {
  prerequisite: 'нужно раньше', example_of: 'пример для', refutes_misconception: 'опровергает', to_data: 'данные',
};

export const PAGE_STATE: Record<PageState, string> = { text: 'надёжно', doubtful: 'сверить', scan: 'нет текста', empty: 'пустая' };

export const SOURCE_STATE: Record<SourceState, string> = {
  uploaded: 'текст не извлечён', extracting: 'извлекается текст', ready: 'готово', failed: 'извлечь не удалось',
};

export const PROVIDER: Record<ProviderName, string> = {
  claude_code: 'Claude Code', anthropic: 'Anthropic API', openai: 'OpenAI', local: 'Своя модель (Ollama, LM Studio, vLLM)',
};

export const VERDICT: Record<Verdict, string> = {
  follows: 'следует из источника', partial: 'следует частично', no: 'в источнике нет', contradicts: 'противоречит', unchecked: 'не проверено',
};

export const FLAG: Record<string, string> = {
  number: 'число не из цитаты', unit: 'другая единица', negation: 'отрицание', direction: 'направление', quantifier: 'лишнее обобщение', condition: 'потеряна оговорка',
};

export const DAMAGE: Record<string, string> = {
  sign_flip: 'перевёрнуто направление', number: 'изменено число', unit: 'подменена единица', negation_removed: 'убрано «не»', negation_added: 'добавлено «не»',
  lost_condition: 'убрана оговорка', overgeneralization: 'добавлено «всегда»',
};
