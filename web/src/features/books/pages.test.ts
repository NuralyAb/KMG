import { describe, expect, it } from 'vitest';
import { pagesText, parsePages, rangesOf } from './pages';

const section = (first: number, last: number) => ({ id: `${first}`, title: 't', level: 1, first, last });

describe('страницы новой главы', () => {
  it('сливает главу с её параграфами и соседей', () => {
    expect(rangesOf([section(494, 500), section(474, 493), section(480, 485)])).toEqual([[474, 500]]);
    expect(rangesOf([section(9, 14), section(20, 30)])).toEqual([[9, 14], [20, 30]]);
  });
  it('читает запись человека', () => {
    expect(parsePages('9-14, 20–30; 35')).toEqual([[9, 14], [20, 30], [35, 35]]);
    expect(pagesText([[9, 14], [35, 35]])).toBe('9-14, 35');
  });
  it('непонятное не превращает в страницы', () => {
    for (const bad of ['', 'abc', '5-', '9-3', '1-2, x']) expect(parsePages(bad)).toEqual([]);
  });
});
