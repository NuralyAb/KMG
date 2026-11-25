import type { MetricRow } from '@/api/types';

export type GroupKey = 'stage' | 'chapter';
export type Measure = 'cost' | 'tokens';

export interface Group {
  key: string; runs: number; cost: number; tokensIn: number; tokensOut: number; personMinutes: number; mentorMinutes: number;
  videoSeconds: number;
}

const empty = (key: string): Group => ({
  key, runs: 0, cost: 0, tokensIn: 0, tokensOut: 0, personMinutes: 0, mentorMinutes: 0, videoSeconds: 0,
});

const add = (group: Group, row: MetricRow): Group => ({
  ...group,
  runs: group.runs + 1,
  cost: group.cost + row.money_usd,
  tokensIn: group.tokensIn + row.llm_tokens_in,
  tokensOut: group.tokensOut + row.llm_tokens_out,
  personMinutes: group.personMinutes + row.person_minutes,
  mentorMinutes: group.mentorMinutes + row.mentor_minutes,
  videoSeconds: group.videoSeconds + row.video_seconds,
});

export const measureOf = (group: Group, measure: Measure): number =>
  measure === 'cost' ? group.cost : group.tokensIn + group.tokensOut;

/** Складывает строки metrics.csv по этапу или главе, самое дорогое сверху. */
export function groupRows(rows: MetricRow[], by: GroupKey, measure: Measure = 'cost'): Group[] {
  const groups = rows.reduce((acc, row) => new Map(acc).set(row[by], add(acc.get(row[by]) ?? empty(row[by]), row)), new Map<string, Group>());
  return [...groups.values()].sort((a, b) => measureOf(b, measure) - measureOf(a, measure) || a.key.localeCompare(b.key, 'ru'));
}

export function totalOf(rows: MetricRow[]): Group {
  return rows.reduce(add, empty('total'));
}
