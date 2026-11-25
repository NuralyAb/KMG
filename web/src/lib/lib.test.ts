import { describe, expect, test } from 'vitest';
import { counted, FORMS, formatDateTime, formatDuration, formatInt, formatMoney, formatPages, formatPercent, formatTokens, plural, runDuration } from './format';
import { splitFormulas } from './formula';
import { highlight } from './highlight';
import { DIFFICULTY, label } from './labels';

const plain = (text: string): string => text.replace(/⁠/g, '').replace(/[  ]/g, ' ');

describe('splitFormulas', () => {
  test('text without formulas stays one piece', () => {
    expect(splitFormulas('Просто текст')).toEqual([{ kind: 'text', value: 'Просто текст' }]);
  });

  test('splits all four delimiters', () => {
    expect(splitFormulas('a $x$ b \\(y\\) c $$z$$ d \\[w\\]')).toEqual([
      { kind: 'text', value: 'a ' }, { kind: 'math', value: 'x', display: false }, { kind: 'text', value: ' b ' },
      { kind: 'math', value: 'y', display: false }, { kind: 'text', value: ' c ' }, { kind: 'math', value: 'z', display: true },
      { kind: 'text', value: ' d ' }, { kind: 'math', value: 'w', display: true },
    ]);
  });

  test('keeps inner parentheses and commands', () => {
    expect(splitFormulas('\\(k = \\frac{V_п}{V} \\left(1\\right)\\)')).toEqual([{ kind: 'math', value: 'k = \\frac{V_п}{V} \\left(1\\right)', display: false }]);
  });

  test('money is not a formula', () => {
    expect(splitFormulas('от $5 до $10')).toEqual([{ kind: 'text', value: 'от $5 до $10' }]);
    expect(splitFormulas('стоит \\$5')).toEqual([{ kind: 'text', value: 'стоит $5' }]);
  });

  test.each(['не закрыто $x', 'не закрыто \\(x', '$$', '$ $', '\\(\\)'])('an incomplete delimiter stays text: %s', (text) => {
    expect(splitFormulas(text)).toEqual([{ kind: 'text', value: text }]);
  });

  test('an escaped dollar inside a formula does not close it', () => {
    expect(splitFormulas('$a \\$ b$')).toEqual([{ kind: 'math', value: 'a \\$ b', display: false }]);
  });

  test('empty text gives no pieces', () => expect(splitFormulas('')).toEqual([]));
});

describe('highlight', () => {
  test('ignores case and ё', () => {
    expect(highlight('Жёсткий ЖЕСТКИЙ', 'жестк')).toEqual([
      { text: 'Жёстк', hit: true }, { text: 'ий ', hit: false }, { text: 'ЖЕСТК', hit: true }, { text: 'ИЙ', hit: false },
    ]);
  });
  test('an empty query marks nothing', () => expect(highlight('текст', '  ')).toEqual([{ text: 'текст', hit: false }]));
  test('a query is not a regular expression', () => expect(highlight('a.c abc', '.')).toContainEqual({ text: '.', hit: true }));
});

describe('format', () => {
  test('money', () => {
    expect(plain(formatMoney(16.4231))).toBe('$16,42');
    expect(plain(formatMoney(0.004))).toBe('< $0,01');
    expect(plain(formatMoney(0))).toBe('$0,00');
    expect(formatMoney(Number.NaN)).toBe('—');
  });
  test('tokens', () => {
    expect(formatTokens(950)).toBe('950');
    expect(plain(formatTokens(12_496))).toBe('12 тыс.');
    expect(plain(formatTokens(1_391_722))).toBe('1,4 млн');
  });
  test('percent shows 100 only for full coverage and 0 only for none', () => {
    expect(plain(formatPercent(999, 1000))).toBe('99 %');
    expect(plain(formatPercent(1000, 1000))).toBe('100 %');
    expect(plain(formatPercent(1, 1000))).toBe('1 %');
    expect(plain(formatPercent(0, 10))).toBe('0 %');
    expect(formatPercent(0, 0)).toBe('—');
  });
  test('pages fold into ranges', () => {
    expect(plain(formatPages([11, 9, 10, 20, 20]))).toBe('9–11, 20');
    expect(formatPages([])).toBe('—');
  });
  test('durations', () => {
    expect(plain(formatDuration(42))).toBe('42 с');
    expect(plain(formatDuration(134))).toBe('2 мин 14 с');
    expect(plain(formatDuration(7_320))).toBe('2 ч 2 мин');
    expect(formatDuration(-1)).toBe('—');
  });
  test('run duration uses now for a running one', () => {
    const start = '2026-11-25T10:00:00Z';
    expect(plain(runDuration(start, null, Date.parse('2026-11-25T10:00:30Z')))).toBe('30 с');
    expect(plain(runDuration(start, '2026-11-25T10:01:00Z', 0))).toBe('1 мин 0 с');
    expect(runDuration(null, null, 0)).toBe('—');
    expect(runDuration('мусор', null, 0)).toBe('—');
  });
  test('dates survive rubbish', () => {
    expect(formatDateTime(null)).toBe('—');
    expect(formatDateTime('мусор')).toBe('—');
    expect(formatDateTime('2026-11-25T10:00:00Z')).toMatch(/нояб/);
  });
  test.each([[1, 'шаг'], [2, 'шага'], [5, 'шагов'], [11, 'шагов'], [12, 'шагов'], [21, 'шаг'], [44, 'шага'], [112, 'шагов']])('plural %i', (n, word) => {
    expect(plural(n, FORMS.node)).toBe(word);
  });
  test('counted', () => expect(plain(counted(1628, FORMS.claim))).toBe('1 628 утверждений'));
  test('integer', () => expect(plain(formatInt(10_000))).toBe('10 000'));
});

describe('label', () => {
  test('known, unknown and empty values', () => {
    expect(label(DIFFICULTY, 'М')).toBe('механизм');
    expect(label(DIFFICULTY, 'toString')).toBe('toString');
    expect(label(DIFFICULTY, null)).toBe('—');
  });
});
