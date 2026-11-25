const test = require('node:test');
const assert = require('node:assert');
const { readFileSync, existsSync } = require('node:fs');
const path = require('node:path');
const core = require('../../glava/modules/lab/assets/core.js');

const practice = JSON.parse(readFileSync(path.join(__dirname, '../../../workspace/domain/geology/practice/volve_blind.json'), 'utf8'));
const [naive, chapter] = practice.robots;

test('уверенная ошибка стоит дороже честной неуверенности', () => {
  assert.ok(core.points(true, 90) > core.points(true, 50));
  assert.ok(core.points(false, 90) < core.points(false, 50));
  assert.strictEqual(core.points(true, 50), core.points(false, 50));
});

test('порог по сопротивлению не работает ни при каком значении, правило главы работает', () => {
  assert.deepStrictEqual(core.robotScore(practice, naive, naive.threshold), { right: 5, total: 10 });
  assert.ok(core.bestThreshold(practice, naive).right < 10);
  assert.deepStrictEqual(core.robotScore(practice, chapter, chapter.threshold), { right: 10, total: 10 });
});

test('спорный интервал в счёт не идёт', () => {
  const all = core.intervalsOf(practice);
  const answers = Object.fromEntries(all.map((i) => [i.id, { choice: i.truth, confidence: 90 }]));
  const s = core.summary(practice, answers);
  assert.strictEqual(all.length, 11);
  assert.deepStrictEqual([s.right, s.total, s.accuracy], [10, 10, 100]);
});

test('у каждого интервала есть пояснение, класс и показания', () => {
  const classes = new Set([...practice.classes.map((c) => c.id), ...Object.keys(practice.unscored)]);
  for (const i of core.intervalsOf(practice)) {
    assert.ok(practice.reasons[i.id], i.id);
    assert.ok(classes.has(i.truth), i.id);
    for (const c of practice.curves) assert.strictEqual(typeof i.medians[c.id], 'number');
  }
});

const task = (id, misconception, type = 'single') => ({ id, type, prompt: `вопрос ${id}`, answer: type === 'single' ? 'a' : ['a'], options: [{ id: 'a', text: 'верно', misconception: null }, { id: 'b', text: 'неверно', misconception }] });
const course = { steps: [
  { id: 's1', order: 1, misconception: { ref: 'm1', text: 'почему это не так' }, tasks: [task('t1', 'm1'), task('t2', 'm2')] },
  { id: 's2', order: 2, misconception: null, tasks: [task('t3', 'm1'), task('t4', 'm3', 'multiple')] },
] };

test('заблуждение называется своими словами, а без них — текстом варианта и вопросом', () => {
  const index = core.misconceptionIndex(course, { m1: 'известное' });
  assert.strictEqual(index.get('m1').text, 'известное');
  assert.strictEqual(index.get('m1').steps[0].id, 's1');
  assert.deepStrictEqual([index.get('m2').text, index.get('m2').context], ['неверно', 'вопрос t2']);
});

test('диагноз ставится только за выбранный неверный вариант', () => {
  assert.deepStrictEqual(core.diagnose(course.steps[0].tasks[0], ['a']), []);
  assert.deepStrictEqual(core.diagnose(course.steps[0].tasks[0], ['b']).map((o) => o.misconception), ['m1']);
});

test('память: попался, потом обошёл, потом снова попался', () => {
  const t = course.steps[0].tasks[0];
  let memory = core.remember({}, t, ['b']);
  assert.strictEqual(core.standing(memory.m1), 'caught');
  memory = core.remember(memory, t, ['a']);
  assert.strictEqual(core.standing(memory.m1), 'beaten');
  memory = core.remember(memory, t, ['b']);
  assert.strictEqual(core.standing(memory.m1), 'caught');
  assert.strictEqual(core.standing(core.remember({}, t, ['a']).m1), 'clear');
  assert.strictEqual(core.standing(undefined), 'unknown');
});

test('диагностика не берёт вопрос дважды и начинает с частых заблуждений', () => {
  const picked = core.diagnosticTasks(course, core.misconceptionIndex(course, {}), 2).map((e) => e.task.id);
  assert.deepStrictEqual(picked, ['t1', 't3']);
});

test('таблица: формула в ячейке не выполнится', () => {
  const csv = core.toCsv([['=1+1', 'а"б', null]]);
  assert.strictEqual(csv, '﻿"\'=1+1";"а""б";""');
});

test('диагноз опирается на разметку задания, которая есть в плеере', () => {
  const root = path.join(__dirname, '../../..');
  const files = ['backend/glava/modules/course/assets/tasks.js', 'web/src/course/TaskCard.tsx'].map((f) => path.join(root, f)).filter(existsSync);
  assert.ok(files.length > 0);
  for (const file of files) {
    const text = readFileSync(file, 'utf8');
    for (const mark of ['data-id=', 'verdict', 'wrong', 'option']) assert.ok(text.includes(mark), `${file}: ${mark}`);
  }
});
