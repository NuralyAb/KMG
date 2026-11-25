'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const core = require(path.join(__dirname, '../../engine/glava/course/assets/core.js'));
const katex = { renderToString: (code, o) => `[${o.displayMode ? 'D' : 'I'}:${code}]` };
const rich = core.makeRich(katex);

// ---------- ответы ----------
const gap = (answer) => ({ type: 'gap', answer });
const calc = (answer, tolerance, unit = null) => ({ type: 'calc', answer, tolerance, unit });

test('gap ignores case, ё, spaces, comma and the final dot', () => {
  assert.ok(core.isCorrect(gap(['чёрный сланец', '2,5']), [], ['  Черный   СЛАНЕЦ. ', '2.50']));
  assert.ok(!core.isCorrect(gap(['больше']), [], ['меньше']));
});

test('gap accepts Greek rho and Latin look-alikes typed on a Russian keyboard', () => {
  assert.ok(core.isCorrect(gap(['ρпм/ρгл', 'Rк']), [], ['рпм / ргл', 'RK']));
  assert.ok(!core.isCorrect(gap(['ρпм/ρгл']), [], ['рпм/рзп']));
});

test('gap does not mistake one number for another', () => {
  assert.ok(!core.isCorrect(gap(['1083']), [], ['1083,5']));
});

test('calc understands comma, unit, minus sign, powers and thousands', () => {
  assert.ok(core.isCorrect(calc(2.5, 0.05, 'МПа'), [], ['2,5 МПа']));
  assert.ok(core.isCorrect(calc(-5, 0, null), [], ['−5']));
  assert.ok(core.isCorrect(calc(2e-6, 2e-8, 'м³/(Па·сут·м)'), [], ['2·10^-6']));
  assert.ok(core.isCorrect(calc(2e-6, 2e-8), [], ['0,000002']));
  assert.ok(core.isCorrect(calc(2e-6, 2e-8), [], ['2*10⁻⁶']));
  assert.ok(core.isCorrect(calc(1083, 1), [], ['1 083']));
  assert.ok(core.isCorrect(calc(50, 0.5, 'п.п.'), [], ['50%']));
});

test('calc counts the edge of the tolerance as correct and rejects text', () => {
  assert.ok(core.isCorrect(calc(208.7, 0.5), [], ['209,2']));
  assert.ok(!core.isCorrect(calc(208.7, 0.5), [], ['209,3']));
  assert.ok(!core.isCorrect(calc(0, 0), [], ['']));
  assert.ok(!core.isCorrect(calc(0, 0), [], ['много']));
  for (const typed of ['17 18', '17 или 18', '17-18', '17.5.1', '17,5,1']) assert.ok(!core.isCorrect(calc(17, 0.1), [], [typed]), typed);
});

test('calc accepts a unit of several words and a unit with digits', () => {
  assert.ok(core.isCorrect(calc(3, 0.05, 'отн. ед.'), [], ['3 отн. ед.']));
  assert.ok(core.isCorrect(calc(6, 0.05), [], ['6 безразмерная величина']));
  assert.ok(core.isCorrect(calc(6, 0.05), [], ['6 м3/сут']));
  assert.ok(core.isCorrect(calc(6, 0.05), [], ['6 м³/(Па·сут·м)']));
});

test('single, multiple and order compare identifiers', () => {
  assert.ok(core.isCorrect({ type: 'single', answer: 'a' }, ['a'], []));
  assert.ok(core.isCorrect({ type: 'multiple', answer: ['a', 'c'] }, ['c', 'a'], []));
  assert.ok(!core.isCorrect({ type: 'multiple', answer: ['a', 'c'] }, ['a'], []));
  assert.ok(core.isCorrect({ type: 'order', answer: ['b', 'a'] }, ['b', 'a'], []));
  assert.ok(!core.isCorrect({ type: 'order', answer: ['b', 'a'] }, ['a', 'b'], []));
});

test('an empty answer is not checked yet', () => {
  assert.ok(!core.isAnswered({ type: 'single' }, [], []));
  assert.ok(core.isAnswered({ type: 'single' }, ['a'], []));
  assert.ok(!core.isAnswered({ type: 'gap' }, [], ['слово', ' ']));
  assert.ok(core.isAnswered({ type: 'order' }, ['a', 'b'], []));
});

test('order task never starts solved and keeps every option', () => {
  for (const answer of [['a', 'b'], ['b', 'a', 'c'], ['a', 'b', 'c', 'd']]) {
    for (const seed of ['t1', 'step.two', 'x']) {
      const start = core.startOrder([...answer].sort().map((id) => ({ id })), answer, seed);
      assert.notDeepEqual(start, answer);
      assert.deepEqual([...start].sort(), [...answer].sort());
    }
  }
});

test('shown numbers use the Russian comma and powers of ten', () => {
  assert.equal(core.showNumber(2.5), '2,5');
  assert.equal(core.showNumber(1083), '1083');
  assert.equal(core.showNumber(0.000002), '2·10⁻⁶');
});

// ---------- карточки ----------
test('repeat cards rotate until each one is known', () => {
  const ids = ['a', 'b', 'c'];
  let state = { cards: {}, repeat: [] };
  const seen = [];
  for (const mark of ['again', 'again', 'again', 'again', 'again']) {
    const id = core.nextCard(ids, state);
    seen.push(id);
    state = { ...state, ...core.rateCard(state, id, mark) };
  }
  assert.deepEqual(seen, ['a', 'b', 'c', 'a', 'b']);
  for (let i = 0; i < 3; i += 1) state = { ...state, ...core.rateCard(state, core.nextCard(ids, state), 'know') };
  assert.equal(core.nextCard(ids, state), null);
});

test('repeat marks saved by an older version are not lost', () => {
  assert.equal(core.nextCard(['a', 'b'], { cards: { a: 'know', b: 'again' }, repeat: [] }), 'b');
});

// ---------- состояние ----------
test('broken progress falls back to a clean state', () => {
  const clean = { done: [], solved: {}, cards: {}, repeat: [], last: null, theme: 'auto' };
  for (const raw of [null, 5, 'x', [], { done: null, solved: [], cards: 'no', repeat: {}, last: {}, theme: 'pink' }]) assert.deepEqual(core.cleanState(raw, ['a']), clean);
});

test('progress of unknown steps is dropped, the rest survives', () => {
  const state = core.cleanState({ done: ['a', 'gone', 'a'], solved: { t: true, z: 'yes' }, cards: { a: 'know', gone: 'again' }, repeat: ['gone'], last: 2, theme: 'dark' }, ['a', 'b']);
  assert.deepEqual(state, { done: ['a'], solved: { t: true }, cards: { a: 'know' }, repeat: [], last: 2, theme: 'dark' });
});

// ---------- адреса ----------
test('hash is parsed into a tab or a step with a section', () => {
  assert.deepEqual(core.parseHash('#/step/12/how'), { tab: null, step: 12, section: 'how' });
  assert.deepEqual(core.parseHash('#/step/12'), { tab: null, step: 12, section: null });
  assert.deepEqual(core.parseHash('#/map'), { tab: '#/map', step: null, section: null });
  assert.deepEqual(core.parseHash(''), { tab: '#/', step: null, section: null });
  assert.deepEqual(core.parseHash('#/step/x'), { tab: '#/', step: null, section: null });
});

// ---------- текст ----------
test('text is escaped and indexes become subscripts', () => {
  assert.equal(rich('<b> k_п,эф & "x"'), '&lt;b&gt; k<sub>п,эф</sub> &amp; &quot;x&quot;');
});

test('formulas are found with and without dollar signs', () => {
  assert.equal(rich('$a$ и $$b$$'), '[I:a] и [D:b]');
  assert.match(rich('отношение \\rho_{\\mathrm{n}} больше'), /\[I:\\rho_\{\\mathrm\{n\}\}\]/);
});

test('a formula number does not break an inline formula', () => {
  assert.ok(!rich('1 / \\rho_{n} = 2 \\tag {63}').includes('tag'));
  assert.match(rich('1 / \\rho_{n} = 2 \\tag {63}'), /\(63\)/);
});

test('a formula block is shown on its own line with or without dollar signs', () => {
  assert.equal(core.texOnly('a=b', rich), '[D:a=b]');
  assert.equal(core.texOnly(' $$a=b$$ ', rich), '[D:a=b]');
});

test('a bare formula keeps Cyrillic letters inside braces', () => {
  assert.match(rich('Здесь \\rho_{\\text{п}} = \\frac{\\chi_{\\text{гл}}}{2} растёт'), /^Здесь\s+\[I:\\rho_\{\\text\{п\}\} = \\frac\{\\chi_\{\\text\{гл\}\}\}\{2\}\]\s+растёт$/);
});

test('a legend symbol is a formula only when it has a LaTeX command', () => {
  assert.equal(core.symbol('\\rho_{\\text{п}}', rich), '[I:\\rho_{\\text{п}}]');
  assert.equal(core.symbol('$k_п$', rich), '[I:k_п]');
  assert.equal(core.symbol('χ_гл', rich), 'χ<sub>гл</sub>');
});

test('unbalanced braces of a cut quote are handled without hanging', () => {
  assert.equal(typeof rich(`\\rho_{${'{a'.repeat(400)}`), 'string');
});

test('lead is split after the first thought, not after an abbreviation', () => {
  assert.deepEqual(core.splitLead('Порог виден на рис. 69 и в табл. 22. Дальше вывод. И ещё.'), ['Порог виден на рис. 69 и в табл. 22.', 'Дальше вывод. И ещё.']);
  assert.deepEqual(core.splitLead('Одна мысль'), ['Одна мысль', '']);
});

// ---------- термины ----------
const terms = [{ term: 'зона проникновения', definition: '1' }, { term: 'фильтрат', definition: '2' }, { term: 'Pн', definition: '3' }];

test('first mention of a term is marked in any case form', () => {
  const [first, second] = core.markTerms(['В зоне проникновения есть фильтрата много.', 'Фильтрат снова.'], terms);
  assert.equal(rich(first), 'В <span class="term" role="button" tabindex="0" aria-expanded="false" data-term="0">зоне проникновения</span> есть <span class="term" role="button" tabindex="0" aria-expanded="false" data-term="1">фильтрата</span> много.');
  assert.equal(second, 'Фильтрат снова.');
});

test('a different word and a formula are not marked', () => {
  const [a, b] = core.markTerms(['Фильтрация и $Pн > 1$ идут рядом.', 'Параметр Pн больше.'], terms);
  assert.equal(a, 'Фильтрация и $Pн > 1$ идут рядом.');
  assert.match(rich(b), /data-term="2">Pн</);
});

test('a symbol glued to the term name does not hide the term', () => {
  const [a] = core.markTerms(['Номинальный диаметр задан заранее.'], [{ term: 'номинальный диаметр d_н', definition: '' }]);
  assert.match(rich(a), /data-term="0">Номинальный диаметр</);
});

test('markers do not leak into a bare formula next to the term', () => {
  const [a] = core.markTerms(['Фильтрат \\rho_{n} растёт.'], terms);
  assert.match(rich(a), /фильтрат<\/span>\s+\[I:\\rho_\{n\}\]/i);
});

// ---------- карта ----------
test('longer links bend further and stay inside the margin', () => {
  const depth = [1, 5, 20, 43].map((span) => core.arcDepth(span, 43, 80));
  assert.deepEqual([...depth].sort((x, y) => x - y), depth);
  assert.ok(new Set(depth).size === depth.length && depth.at(-1) <= 80 && depth[0] >= 12);
});

test('neighbours of a step are its supports and the steps that rest on it', () => {
  const steps = [{ id: 'a', order: 1, links: [] }, { id: 'b', order: 2, links: [{ type: 'prerequisite', target: 'a' }, { type: 'prerequisite', target: 'a' }, { type: 'refutes_misconception', target: 'm' }] }];
  assert.deepEqual(core.edges(steps).map(([x, y]) => [x.id, y.id]), [['a', 'b']]);
});

// ---------- таблицы ----------
test('table rows are padded and a correction keeps the original value', () => {
  const rows = core.tableRows({ header: ['a', 'b'], rows: [['1'], ['2', '3']], corrections: [{ row: 1, col: 1, from: '8', to: '3' }] });
  assert.deepEqual(rows, [[{ text: '1', from: null }, { text: '', from: null }], [{ text: '2', from: null }, { text: '3', from: '8' }]]);
});
