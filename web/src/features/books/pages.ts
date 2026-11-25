export interface Section { id: string; title: string; level: number; first: number; last: number }
export type Range = [number, number];

/** Соседние и пересекающиеся отрезки сливаются: глава и её параграфы не считаются дважды. */
export function rangesOf(sections: readonly Section[]): Range[] {
  const sorted = sections.map((s): Range => [s.first, s.last]).sort((a, b) => a[0] - b[0]);
  return sorted.reduce<Range[]>((done, [first, last]) => {
    const previous = done.at(-1);
    if (!previous || first > previous[1] + 1) return [...done, [first, last]];
    return [...done.slice(0, -1), [previous[0], Math.max(previous[1], last)]];
  }, []);
}

export const pagesText = (ranges: readonly Range[]): string => ranges.map(([a, b]) => (a === b ? `${a}` : `${a}-${b}`)).join(', ');

/** «9-14, 20–30» → отрезки; непонятная запись даёт пустой список. */
export function parsePages(text: string): Range[] {
  const parts = text.split(/[,;]/).map((p) => p.trim()).filter(Boolean);
  const found = parts.map((p) => /^(\d{1,4})(?:\s*[-–—]\s*(\d{1,4}))?$/.exec(p));
  if (found.some((m) => m === null)) return [];
  const ranges = found.map((m): Range => [Number(m?.[1]), Number(m?.[2] ?? m?.[1])]);
  return ranges.some(([a, b]) => a > b) ? [] : ranges;
}
