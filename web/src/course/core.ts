/** Логика курса без страницы: ответы, карточки, прогресс, текст, карта. */
import type { BookTable, Part, Step, Task, TaskOption, Term } from './types';

// ---------- ответы ----------
// ρ и похожие латинские буквы с русской клавиатуры не набрать, поэтому они приравнены к русским
const LOOKALIKE: Record<string, string> = { a: 'а', b: 'в', c: 'с', e: 'е', h: 'н', k: 'к', m: 'м', o: 'о', p: 'р', t: 'т', x: 'х', y: 'у', 'ρ': 'р' };
export const norm = (v: unknown): string => String(v ?? '').toLowerCase().replace(/ё/g, 'е').replace(/[−–—]/g, '-').replace(/[_«»"]/g, '').replace(/\s+/g, ' ').replace(/\s*([/=<>+])\s*/g, '$1')
  .trim().replace(/[.,;:!]+$/, '').replace(/[abcehkmoptxyρ]/g, (c) => LOOKALIKE[c] ?? c);

const SUPER = '⁰¹²³⁴⁵⁶⁷⁸⁹';
const toPower = (s: string): string => s.replace(/⁻/g, '-').replace(/[⁰¹²³⁴⁵⁶⁷⁸⁹]/g, (c) => String(SUPER.indexOf(c)));
const NUMBER = /^([+-]?\d+(?:\.\d+)?)(?:e([+-]?\d+)|[·*x×х]10\^?([+-]?\d+))?/;
// в единице цифра бывает только степенью сразу за буквой: «м3/сут», но не «17 или 18»
const UNIT = /^(?:[a-zа-яё]-?\d?|[\sµ°%‰·/()²³⁻⁰¹⁴-⁹*.])*$/i;

/** Число из ответа: запятая, минус, пробелы в тысячах, 2·10^-6, единица после числа. Не число — NaN. */
export const parseNumber = (value: unknown): number => {
  const raw = String(value ?? '').trim().toLowerCase().replace(/[−–—]/g, '-').replace(/(\d)[\s  ](?=\d{3}(?:\D|$))/g, '$1').replace(/\s*([·*×])\s*/g, '$1').replace(/(\d),(?=\d)/g, '$1.');
  const spaced = raw.search(/\s/);
  const compact = toPower(spaced < 0 ? raw : raw.slice(0, spaced));
  const match = NUMBER.exec(compact);
  if (!match) return NaN;
  const tail = compact.slice(match[0].length) + (spaced < 0 ? '' : raw.slice(spaced).trim());
  if (!UNIT.test(tail)) return NaN;
  return Number(`${match[1]}e${match[2] ?? match[3] ?? 0}`);
};

const sameWord = (typed: unknown, expected: unknown): boolean => {
  const a = norm(typed);
  const b = norm(expected);
  if (a === b) return true;
  return /^-?\d+(?:[.,]\d+)?$/.test(b) && parseNumber(typed) === parseNumber(expected);
};
const near = (value: number, answer: number, tolerance: number): boolean => Math.abs(value - answer) <= tolerance + 1e-9 * Math.max(1e-9, Math.abs(answer));

type Checked = Pick<Task, 'type' | 'answer'> & { tolerance?: number | null };
export const isAnswered = (task: Pick<Task, 'type'>, picked: string[], values: string[]): boolean => (['gap', 'calc'].includes(task.type) ? values.length > 0 && values.every((v) => v.trim() !== '') : picked.length > 0);
export const isCorrect = (task: Checked, picked: string[], values: string[]): boolean => {
  const a = task.answer;
  const list = Array.isArray(a) ? a : [];
  if (task.type === 'single') return picked[0] === a;
  if (task.type === 'multiple') return picked.length === list.length && list.every((x) => picked.includes(x));
  if (task.type === 'order') return picked.join() === list.join();
  if (task.type === 'gap') return list.every((x, i) => sameWord(values[i], x));
  return near(parseNumber(values[0]), Number(a), task.tolerance || 0);
};

export const shuffled = <T>(list: T[], seed: string): T[] => list.map((o, i) => ({ at: ((i + 1) * 7919 + seed.length * 104729) % 1009, o })).sort((a, b) => a.at - b.at).map((x) => x.o);
/** Начальный порядок задания: варианты перемешаны и точно не совпадают с ответом. */
export const startOrder = (options: TaskOption[], answer: string[], seed: string): string[] => {
  const ids = shuffled(options, seed).map((o) => o.id);
  return ids.join() === answer.join() ? [...ids.slice(1), ...ids.slice(0, 1)] : ids;
};
export const showNumber = (n: unknown): string => {
  if (typeof n !== 'number') return String(n);
  const [base = '', power] = (n !== 0 && Math.abs(n) < 1e-3 ? n.toExponential() : String(n)).split('e');
  const shown = base.replace('.', ',');
  return power ? `${shown}·10${[...power.replace('+', '')].map((c) => (c === '-' ? '⁻' : SUPER[Number(c)])).join('')}` : shown;
};

// ---------- карточки: сначала новые, потом повтор по кругу ----------
type Cards = Pick<State, 'cards' | 'repeat'>;
export const nextCard = (ids: string[], state: Cards): string | null => {
  const fresh = ids.find((id) => !state.cards[id]);
  if (fresh) return fresh;
  const again = ids.filter((id) => state.cards[id] === 'again');
  return state.repeat.find((id) => again.includes(id)) ?? again[0] ?? null;
};
export const rateCard = (state: Cards, id: string, mark: CardMark): Cards => {
  const rest = state.repeat.filter((x) => x !== id);
  return { cards: { ...state.cards, [id]: mark }, repeat: mark === 'again' ? [...rest, id] : rest };
};

// ---------- сохранённый прогресс ----------
type Raw = Record<string, unknown>;
export type CardMark = 'know' | 'again';
export type Theme = 'auto' | 'light' | 'dark';
export interface State {
  done: string[]; solved: Record<string, boolean>; cards: Record<string, CardMark>; repeat: string[]; last: number | null; theme: Theme; notes: Record<string, string>;
}
const THEMES: readonly unknown[] = ['auto', 'light', 'dark'];
const isObject = (v: unknown): v is Raw => v !== null && typeof v === 'object' && !Array.isArray(v);
const pick = <T>(value: unknown, keep: (k: string, v: unknown) => boolean): Record<string, T> => (isObject(value) ? Object.fromEntries(Object.entries(value).filter(([k, v]) => keep(k, v))) as Record<string, T> : {});
const list = (value: unknown, ids: string[]): string[] => (Array.isArray(value) ? [...new Set(value)].filter((x): x is string => typeof x === 'string' && ids.includes(x)) : []);
export const cleanState = (raw: unknown, ids: string[]): State => {
  const r: Raw = isObject(raw) ? raw : {};
  return {
    done: list(r.done, ids),
    solved: pick<boolean>(r.solved, (_, v) => typeof v === 'boolean'),
    cards: pick<CardMark>(r.cards, (k, v) => ids.includes(k) && (v === 'know' || v === 'again')),
    repeat: list(r.repeat, ids),
    last: typeof r.last === 'number' && Number.isInteger(r.last) ? r.last : null,
    theme: THEMES.includes(r.theme) ? r.theme as Theme : 'auto',
    notes: pick<string>(r.notes, (k, v) => ids.includes(k) && typeof v === 'string' && v !== ''),
  };
};

// ---------- адреса: #/, #/map, #/help, #/step/3, #/step/3/how ----------
const TABS = ['#/', '#/cards', '#/summary', '#/map', '#/help'];
export interface Place { tab: string | null; step: number | null; section: string | null }
/** Якорь утверждения на странице урока: #/step/3/claim-… открывает его во вкладке «Источник». */
export const claimAnchor = (id: string): string => `claim-${id.replace(/[^\w-]/g, '-')}`;
export const parseHash = (hash: string): Place => {
  const m = /^#\/step\/(\d+)(?:\/([\w-]+))?$/.exec(hash);
  if (m) return { tab: null, step: Number(m[1]), section: m[2] ?? null };
  return { tab: TABS.includes(hash) ? hash : '#/', step: null, section: null };
};

// ---------- текст: экранирование, формулы, термины ----------
const ENTITIES: Record<string, string> = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
export const esc = (s: unknown): string => String(s ?? '').replace(/[&<>"']/g, (c) => ENTITIES[c] ?? c);
// k_п,эф -> k с нижним индексом
const lower = (s: string): string => esc(s).replace(/(\p{L}+)_([\p{L}\d]+(?:,[\p{L}\d]+)*)/gu, '$1<sub>$2</sub>');
const FORMULA = /(\$\$[\s\S]+?\$\$|\\\[[\s\S]+?\\\]|\$[^$\n]+?\$|\\\([\s\S]+?\\\))/;
// модель иногда пишет формулу без знаков доллара: берём кусок с командой LaTeX, кириллица в нём бывает только внутри скобок
const braces = (inner: string): string => `\\{(?:[^{}\\n]|${inner})*\\}`;
const GROUP = braces(braces(braces('\\{\\}')));
const BARE = new RegExp(`((?:[^Ѐ-ӿ\\uE000-\\uE4FF\\n\\\\{]|${GROUP})*\\\\[a-zA-Z]+(?:[^Ѐ-ӿ\\uE000-\\uE4FF\\n{]|${GROUP})*)`);
const [OPEN, MID, CLOSE, INDEX] = ['', '', '', 0xE100];
const TERM = /([-])([^]*)/g;
const termSpan = (_: string, mark: string, text: string): string => `<span class="term" role="button" tabindex="0" aria-expanded="false" data-term="${mark.charCodeAt(0) - INDEX}">${text}</span>`;

export type Rich = (s: unknown) => string;
export const makeRich = (katex: Window['katex']): Rich => {
  // номер формулы (\tag) KaTeX понимает только в отдельной строке
  const inline = (code: string): string => code.replace(/\\tag\s*\{\s*([^}]*?)\s*\}/g, '\\quad ($1)');
  const tex = (code: string, display: boolean): string => {
    if (!katex) return esc(code);
    try { return katex.renderToString(display ? code : inline(code), { displayMode: display, throwOnError: false, strict: 'ignore' }); } catch { return esc(code); }
  };
  const bare = (s: string): string => s.split(BARE).map((part) => (/\\[a-zA-Z]/.test(part) ? ` ${tex(part.replace(/\\[()[\]]/g, '').trim(), false)} ` : lower(part))).join('');
  return (s) => String(s ?? '').split(FORMULA).map((part) => {
    if (/^(\$\$|\\\[)/.test(part)) return tex(part.slice(2, -2), true);
    if (/^\\\(/.test(part)) return tex(part.slice(2, -2), false);
    if (/^\$[^$]/.test(part) && part.endsWith('$')) return tex(part.slice(1, -1), false);
    return bare(part);
  }).join('').replace(TERM, termSpan);
};

/** Формула отдельной строкой; знаки доллара вокруг не мешают. */
export const texOnly = (code: unknown, rich: Rich): string => rich(`$$${String(code ?? '').trim().replace(/^[$]+|[$]+$/g, '')}$$`);
export const symbol = (code: string, rich: Rich): string => rich(/\\[a-zA-Z]/.test(code) && !String(code).includes('$') ? `$${code}$` : code);

const SHORT = /(?:^|[\s(])(?:рис|табл|стр|гл|см|ср|др|пр|т|е|п|д|ф|им|напр|[A-ZА-ЯЁ])\.$/i;
/** Первая мысль отдельно: точка после «рис.» или «табл.» предложение не заканчивает. */
export const splitLead = (text: unknown): [string, string] => {
  const source = String(text ?? '').trim();
  for (const m of source.matchAll(/[.!?](?=\s+[А-ЯЁA-Z«\d$(])/g)) {
    const head = source.slice(0, m.index + 1);
    if (!SHORT.test(head)) return [head, source.slice(m.index + 1).trim()];
  }
  return [source, ''];
};

const escRe = (s: string): string => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
// «зона» находит «зоне» и «зоны»: отбрасываем гласную на конце и разрешаем окончание до трёх букв
const wordPattern = (word: string): string => {
  if (word.length < 4 || !/^[а-яё-]+$/i.test(word)) return escRe(word);
  const stem = word.replace(/[аяоеыийуюьэ]{1,2}$/i, '');
  return `${escRe(stem.length < 3 ? word : stem)}\\p{L}{0,3}`;
};
const termPattern = (term: string): RegExp | null => {
  const all = term.replace(/\([^)]*\)/g, ' ').trim().split(/[\s,]+/).filter(Boolean);
  const plain = all.filter((w) => /^[а-яё-]{4,}$/i.test(w));
  // обозначение после названия («номинальный диаметр d_н») в тексте часто опускают
  const words = plain.length && /[_a-zA-Zα-ωΑ-Ω]/.test(all.at(-1) ?? '') ? all.slice(0, -1) : all;
  if (!words.length) return null;
  const flags = words.length === 1 && !/^[а-яё-]{4,}$/i.test(words[0] ?? '') ? 'u' : 'iu';
  return new RegExp(`(?<![\\p{L}\\d_])${words.map(wordPattern).join('\\s+')}(?![\\p{L}\\d_])`, flags);
};
type Range = [number, number];
const formulaRanges = (text: string): Range[] => [...text.matchAll(new RegExp(FORMULA.source, 'g'))].map((m) => [m.index, m.index + m[0].length]);

/** Отмечает в абзацах первое упоминание каждого термина; метки в разметку превращает rich. */
interface Found { from: number; to: number; i: number }
export const markTerms = (texts: string[], terms: Term[]): string[] => {
  let left = terms.flatMap((t, i) => { const re = termPattern(t.term); return re ? [{ re, i, size: t.term.length }] : []; }).sort((a, b) => b.size - a.size);
  return texts.map((text) => {
    const busy = formulaRanges(text);
    const found = left.reduce<Found[]>((acc, { re, i }) => {
      const m = re.exec(text);
      if (!m) return acc;
      const [from, to] = [m.index, m.index + m[0].length];
      const taken = [...busy, ...acc.map((x): Range => [x.from, x.to])].some(([a, b]) => from < b && to > a);
      return taken ? acc : [...acc, { from, to, i }];
    }, []);
    left = left.filter(({ i }) => !found.some((f) => f.i === i));
    return [...found].sort((a, b) => b.from - a.from)
      .reduce((s, f) => `${s.slice(0, f.from)}${OPEN}${String.fromCharCode(INDEX + f.i)}${MID}${s.slice(f.from, f.to)}${CLOSE}${s.slice(f.to)}`, text);
  });
};

// ---------- содержание курса ----------
/** Номер урока внутри модуля: «2.3». Урок вне модулей остаётся со сквозным номером. */
export const numbering = (parts: Pick<Part, 'nodes'>[], steps: Pick<Step, 'id' | 'order'>[]): Map<string, string> => {
  const inside = parts.flatMap((p, i) => p.nodes.map((id, k): [string, string] => [id, `${i + 1}.${k + 1}`]));
  return new Map([...steps.map((s): [string, string] => [s.id, String(s.order)]), ...inside]);
};
/** 100 % только за весь курс, 0 % только пока ничего не пройдено. */
export const percent = (count: number, total: number): number => {
  if (count >= total) return total > 0 ? 100 : 0;
  return count === 0 ? 0 : Math.min(99, Math.max(1, Math.round((count / total) * 100)));
};
const AUTHORS = /^((?:[А-ЯЁ][а-яё]+(?:-[А-ЯЁ][а-яё]+)?\s+(?:[А-ЯЁ]\.\s?){1,2}(?:,\s*)?)+)(.*)$/;
/** «Латышова М. Г. Практическое руководство…» -> автор и название; без автора — только название. */
export interface Book { author: string; title: string; initials: string }
export const splitBook = (book: unknown): Book => {
  const text = String(book ?? '').trim();
  const m = AUTHORS.exec(text);
  if (!m?.[1] || !m[2]) return { author: '', title: text, initials: '' };
  const author = m[1].trim().replace(/,$/, '');
  const [surname = '', first = ''] = author.split(/\s+/);
  return { author, title: m[2].trim(), initials: surname.charAt(0) + first.charAt(0) };
};

// ---------- карта связей ----------
type Linked = Pick<Step, 'id' | 'order' | 'links'>;
export const edges = <T extends Linked>(steps: T[]): [T, T][] => {
  const byId = new Map(steps.map((s) => [s.id, s]));
  return steps.flatMap((s) => [...new Set((s.links ?? []).filter((l) => l.type === 'prerequisite').map((l) => l.target))].flatMap((id): [T, T][] => { const from = byId.get(id); return from ? [[from, s]] : []; }));
};
const MIN_ARC = 12;
export const arcDepth = (span: number, longest: number, margin: number): number => MIN_ARC + (margin - MIN_ARC) * Math.sqrt(Math.max(0, span - 1) / Math.max(1, longest - 1));

// ---------- таблицы книги ----------
/** Строки таблицы с пометкой исправленных ячеек: from — что стояло в распознанном тексте. row и col считаются с нуля, без шапки. */
export interface Cell { text: string; from: string | null }
export const tableRows = (t: Pick<BookTable, 'header' | 'rows' | 'corrections'>): Cell[][] => {
  const width = Math.max(t.header?.length ?? 0, ...t.rows.map((r) => r.length));
  const fixed = new Map((t.corrections || []).map((c) => [`${c.row}:${c.col}`, c]));
  return t.rows.map((row, r) => Array.from({ length: width }, (_, c) => {
    const fix = fixed.get(`${r}:${c}`);
    return { text: fix ? String(fix.to) : String(row[c] ?? ''), from: fix ? String(fix.from) : null };
  }));
};
