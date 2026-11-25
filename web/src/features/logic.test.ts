import { describe, expect, test } from 'vitest';
import { rawNode, tasks } from '@/mocks/fixtures/content';
import { metrics, reviews } from '@/mocks/fixtures/work';
import type { Task } from '@/api/types';
import { passportFacts } from './chapter/passport';
import { groupRows, totalOf } from './metrics/aggregate';
import { normalizeNode } from './node/model';
import { categoriesOf, filterRemarks, groupBySeverity, packageProblem } from './review/remarks';
import { appendLine, LOG_LIMIT } from './runs/useRunEvents';
import { calcAnswer, choiceOptions, gapPieces, orderedSteps } from './tasks/answer';

const taskOf = (type: Task['type']): Task => {
  const found = tasks.find((t) => t.type === type);
  if (!found) throw new Error(`нет задания ${type}`);
  return found;
};

describe('task answers', () => {
  test('single and multiple mark the right options', () => {
    expect(choiceOptions(taskOf('single')).filter((o) => o.isRight).map((o) => o.id)).toEqual(['b']);
    expect(choiceOptions(taskOf('multiple')).filter((o) => o.isRight).map((o) => o.id)).toEqual(['a', 'c']);
  });
  test('order lists texts in the right order and shows an unknown id', () => {
    expect(orderedSteps(taskOf('order'))).toEqual(['Налить воду', 'Записать объём', 'Посчитать долю']);
    expect(orderedSteps({ ...taskOf('order'), answer: ['zzz'] })).toEqual(['zzz']);
  });
  test('gap puts answers in place', () => {
    expect(gapPieces(taskOf('gap')).filter((p) => p.kind === 'gap').map((p) => p.value)).toEqual(['меньше', 'ниже']);
  });
  test('a gap inside a formula becomes a box and cannot break the formula', () => {
    const pieces = gapPieces({ ...taskOf('gap'), prompt: 'Итог $k = {{1}}$.', answer: ['0,35}$<b>'] });
    expect(pieces).toEqual([{ kind: 'text', value: 'Итог \\(k = \\boxed{\\text{0,35<b>}}\\).' }]);
  });
  test('a missing gap answer is visible', () => {
    expect(gapPieces({ ...taskOf('gap'), answer: [] })).toContainEqual({ kind: 'gap', value: '…' });
  });
  test('calc shows tolerance and unit', () => {
    expect(calcAnswer({ ...taskOf('calc'), unit: 'МПа' })).toBe('0,35 ± 0,01 МПа');
    expect(calcAnswer({ ...taskOf('calc'), tolerance: null })).toBe('0,35');
  });
});

describe('normalizeNode', () => {
  test('reads a full node', () => {
    const node = normalizeNode(rawNode);
    expect(node?.blocks.map((b) => b.key)).toEqual(['topic', 'main', 'mechanism', 'practice', 'nuances']);
    expect(node?.claims).toHaveLength(3);
    expect(node?.claims[2]).toMatchObject({ needsScan: true, page: 12, byModel: true });
    expect(node?.dataBlocks.at(-1)?.field.isHypothesis).toBe(true);
    expect(node?.lens).toHaveLength(5);
  });
  test('missing fields become empty, not a crash', () => {
    expect(normalizeNode({ id: 'x' })).toMatchObject({ title: 'x', blocks: [], claims: [], misconception: null, analogy: null, lens: [], decision: null });
  });
  test('wrong types are ignored', () => {
    expect(normalizeNode({ id: 'x', layers: 'нет', claims: [1, null, {}], pages: ['a', 2], links: {} })).toMatchObject({ pages: [2], links: [] });
  });
  test.each([null, undefined, 'x', [], {}])('not a node: %j', (raw) => expect(normalizeNode(raw)).toBeNull());
});

describe('remarks', () => {
  const remarks = reviews[0]?.remarks ?? [];
  const all = { severity: 'all', category: '', text: '' } as const;
  test('filters by severity, category and text', () => {
    expect(filterRemarks(remarks, all)).toHaveLength(4);
    expect(filterRemarks(remarks, { ...all, severity: 'significant' })).toHaveLength(2);
    expect(filterRemarks(remarks, { ...all, category: 'sign_flip' })).toHaveLength(1);
    expect(filterRemarks(remarks, { ...all, text: 'РАСТЁТ' })).toHaveLength(1);
    expect(filterRemarks(remarks, { ...all, text: 'нет такого' })).toHaveLength(0);
  });
  test('groups go from critical to minor', () => {
    expect(groupBySeverity(remarks).map((g) => g.severity)).toEqual(['critical', 'significant', 'minor']);
    expect(groupBySeverity([])).toEqual([]);
  });
  test('categories are unique', () => expect(categoriesOf([...remarks, ...remarks])).toHaveLength(4));
  test('only a non-empty zip is accepted', () => {
    expect(packageProblem(new File(['x'], 'a.ZIP'))).toBeNull();
    expect(packageProblem(new File(['x'], 'a.rar'))).toMatch('.zip');
    expect(packageProblem(new File([], 'a.zip'))).toMatch('пустой');
    const big = new File(['x'], 'a.zip');
    Object.defineProperty(big, 'size', { value: 81 * 1024 * 1024 });
    expect(packageProblem(big)).toMatch('80 МБ');
  });
});

describe('metrics', () => {
  test('groups by stage, the most expensive first', () => {
    const groups = groupRows(metrics, 'stage');
    expect(groups[0]).toMatchObject({ key: 'layer', runs: 2 });
    expect(groups[0]?.cost).toBeCloseTo(12.15);
  });
  test('measure changes the order', () => {
    expect(groupRows(metrics, 'chapter', 'tokens').map((g) => g.key)).toEqual(['demo_sand', 'demo_water']);
  });
  test('total equals the sum of the groups', () => {
    const sum = groupRows(metrics, 'stage').reduce((s, g) => s + g.tokensIn, 0);
    expect(totalOf(metrics).tokensIn).toBe(sum);
    expect(totalOf([]).cost).toBe(0);
  });
});

describe('run log', () => {
  test('keeps only the last lines and does not mutate', () => {
    const full = Array.from({ length: LOG_LIMIT }, (_, i) => String(i));
    const next = appendLine(full, 'новая');
    expect(next).toHaveLength(LOG_LIMIT);
    expect(next.at(-1)).toBe('новая');
    expect(full[0]).toBe('0');
  });
});

describe('passport', () => {
  test('counts judged answers and skips н/п', () => {
    const facts = passportFacts({ prediction_question: 'Что будет?', exaggerations: ['раз'], physics_checklist: [{ answer: 'да' }, { answer: 'нет' }, { answer: 'н/п' }, null] });
    expect(facts.checklist).toEqual({ total: 2, passed: 1, failed: 1 });
    expect(facts.rows.map((r) => r.title)).toEqual(['Вопрос на предсказание', 'Преувеличения']);
  });
  test('an empty passport gives nothing', () => expect(passportFacts({})).toEqual({ rows: [], checklist: null }));
});
