/* Логика курса без страницы: ответы, карточки, прогресс, текст, карта. Проверяется через node --test. */
(() => {
  'use strict';

  // ---------- ответы ----------
  // ρ и похожие латинские буквы с русской клавиатуры не набрать, поэтому они приравнены к русским
  const LOOKALIKE = { a: 'а', b: 'в', c: 'с', e: 'е', h: 'н', k: 'к', m: 'м', o: 'о', p: 'р', t: 'т', x: 'х', y: 'у', 'ρ': 'р' };
  const norm = (v) => String(v ?? '').toLowerCase().replace(/ё/g, 'е').replace(/[−–—]/g, '-').replace(/[_«»"]/g, '').replace(/\s+/g, ' ').replace(/\s*([/=<>+])\s*/g, '$1')
    .trim().replace(/[.,;:!]+$/, '').replace(/[abcehkmoptxyρ]/g, (c) => LOOKALIKE[c]);

  const SUPER = '⁰¹²³⁴⁵⁶⁷⁸⁹';
  const toPower = (s) => s.replace(/⁻/g, '-').replace(/[⁰¹²³⁴⁵⁶⁷⁸⁹]/g, (c) => SUPER.indexOf(c));
  const NUMBER = /^([+-]?\d+(?:\.\d+)?)(?:e([+-]?\d+)|[·*x×х]10\^?([+-]?\d+))?/;
  // в единице цифра бывает только степенью сразу за буквой: «м3/сут», но не «17 или 18»
  const UNIT = /^(?:[a-zа-яё]-?\d?|[\sµ°%‰·/()²³⁻⁰¹⁴-⁹*.])*$/i;

  /** Число из ответа: запятая, минус, пробелы в тысячах, 2·10^-6, единица после числа. Не число — NaN. */
  const parseNumber = (value) => {
    const raw = String(value ?? '').trim().toLowerCase().replace(/[−–—]/g, '-').replace(/(\d)[\s  ](?=\d{3}(?:\D|$))/g, '$1').replace(/\s*([·*×])\s*/g, '$1').replace(/(\d),(?=\d)/g, '$1.');
    const spaced = raw.search(/\s/);
    const compact = toPower(spaced < 0 ? raw : raw.slice(0, spaced));
    const match = NUMBER.exec(compact);
    if (!match) return NaN;
    const tail = compact.slice(match[0].length) + (spaced < 0 ? '' : raw.slice(spaced).trim());
    if (!UNIT.test(tail)) return NaN;
    return Number(`${match[1]}e${match[2] ?? match[3] ?? 0}`);
  };

  const sameWord = (typed, expected) => {
    const [a, b] = [norm(typed), norm(expected)];
    if (a === b) return true;
    return /^-?\d+(?:[.,]\d+)?$/.test(b) && parseNumber(typed) === parseNumber(expected);
  };
  const near = (value, answer, tolerance) => Math.abs(value - answer) <= tolerance + 1e-9 * Math.max(1e-9, Math.abs(answer));

  const isAnswered = (task, picked, values) => (['gap', 'calc'].includes(task.type) ? values.length > 0 && values.every((v) => v.trim() !== '') : picked.length > 0);
  const isCorrect = (task, picked, values) => {
    const a = task.answer;
    if (task.type === 'single') return picked[0] === a;
    if (task.type === 'multiple') return picked.length === a.length && a.every((x) => picked.includes(x));
    if (task.type === 'order') return picked.join() === a.join();
    if (task.type === 'gap') return a.every((x, i) => sameWord(values[i], x));
    return near(parseNumber(values[0]), Number(a), task.tolerance || 0);
  };

  const shuffled = (list, seed) => list.map((o, i) => [((i + 1) * 7919 + seed.length * 104729) % 1009, o]).sort((a, b) => a[0] - b[0]).map((x) => x[1]);
  /** Начальный порядок задания: варианты перемешаны и точно не совпадают с ответом. */
  const startOrder = (options, answer, seed) => {
    const ids = shuffled(options, seed).map((o) => o.id);
    return ids.join() === answer.join() ? [...ids.slice(1), ids[0]] : ids;
  };
  const showNumber = (n) => {
    if (typeof n !== 'number') return String(n);
    const [base, power] = (n !== 0 && Math.abs(n) < 1e-3 ? n.toExponential() : String(n)).split('e');
    const shown = base.replace('.', ',');
    return power ? `${shown}·10${[...power.replace('+', '')].map((c) => (c === '-' ? '⁻' : SUPER[c])).join('')}` : shown;
  };

  // ---------- карточки: сначала новые, потом повтор по кругу ----------
  const nextCard = (ids, state) => {
    const fresh = ids.find((id) => !state.cards[id]);
    if (fresh) return fresh;
    const again = ids.filter((id) => state.cards[id] === 'again');
    return state.repeat.find((id) => again.includes(id)) ?? again[0] ?? null;
  };
  const rateCard = (state, id, mark) => {
    const rest = state.repeat.filter((x) => x !== id);
    return { cards: { ...state.cards, [id]: mark }, repeat: mark === 'again' ? [...rest, id] : rest };
  };

  // ---------- сохранённый прогресс ----------
  const isObject = (v) => v !== null && typeof v === 'object' && !Array.isArray(v);
  const pick = (value, keep) => (isObject(value) ? Object.fromEntries(Object.entries(value).filter(([k, v]) => keep(k, v))) : {});
  const list = (value, ids) => (Array.isArray(value) ? [...new Set(value)].filter((x) => ids.includes(x)) : []);
  const cleanState = (raw, ids) => {
    const r = isObject(raw) ? raw : {};
    return {
      done: list(r.done, ids),
      solved: pick(r.solved, (_, v) => typeof v === 'boolean'),
      cards: pick(r.cards, (k, v) => ids.includes(k) && ['know', 'again'].includes(v)),
      repeat: list(r.repeat, ids),
      last: Number.isInteger(r.last) ? r.last : null,
      theme: ['auto', 'light', 'dark'].includes(r.theme) ? r.theme : 'auto',
    };
  };

  // ---------- адреса: #/, #/map, #/step/3, #/step/3/how ----------
  const TABS = ['#/', '#/cards', '#/summary', '#/map'];
  const parseHash = (hash) => {
    const m = /^#\/step\/(\d+)(?:\/([\w-]+))?$/.exec(hash);
    if (m) return { tab: null, step: Number(m[1]), section: m[2] ?? null };
    return { tab: TABS.includes(hash) ? hash : '#/', step: null, section: null };
  };

  // ---------- текст: экранирование, формулы, термины ----------
  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  // k_п,эф -> k с нижним индексом
  const lower = (s) => esc(s).replace(/(\p{L}+)_([\p{L}\d]+(?:,[\p{L}\d]+)*)/gu, '$1<sub>$2</sub>');
  const FORMULA = /(\$\$[\s\S]+?\$\$|\\\[[\s\S]+?\\\]|\$[^$\n]+?\$|\\\([\s\S]+?\\\))/;
  // модель иногда пишет формулу без знаков доллара: берём кусок с командой LaTeX, кириллица в нём бывает только внутри скобок
  const braces = (inner) => `\\{(?:[^{}\\n]|${inner})*\\}`;
  const GROUP = braces(braces(braces('\\{\\}')));
  const BARE = new RegExp(`((?:[^Ѐ-ӿ\\uE000-\\uE4FF\\n\\\\{]|${GROUP})*\\\\[a-zA-Z]+(?:[^Ѐ-ӿ\\uE000-\\uE4FF\\n{]|${GROUP})*)`);
  const [OPEN, MID, CLOSE, INDEX] = ['', '', '', 0xE100];
  const TERM = /([-])([^]*)/g;
  const termSpan = (_, mark, text) => `<span class="term" role="button" tabindex="0" aria-expanded="false" data-term="${mark.charCodeAt(0) - INDEX}">${text}</span>`;

  const makeRich = (katex) => {
    // номер формулы (\tag) KaTeX понимает только в отдельной строке
    const inline = (code) => code.replace(/\\tag\s*\{\s*([^}]*?)\s*\}/g, '\\quad ($1)');
    const tex = (code, display) => {
      try { return katex.renderToString(display ? code : inline(code), { displayMode: display, throwOnError: false, strict: 'ignore' }); } catch { return esc(code); }
    };
    const bare = (s) => s.split(BARE).map((part) => (/\\[a-zA-Z]/.test(part) ? ` ${tex(part.replace(/\\[()[\]]/g, '').trim(), false)} ` : lower(part))).join('');
    return (s) => String(s ?? '').split(FORMULA).map((part) => {
      if (/^(\$\$|\\\[)/.test(part)) return tex(part.slice(2, -2), true);
      if (/^\\\(/.test(part)) return tex(part.slice(2, -2), false);
      if (/^\$[^$]/.test(part) && part.endsWith('$')) return tex(part.slice(1, -1), false);
      return bare(part);
    }).join('').replace(TERM, termSpan);
  };

  /** Формула отдельной строкой; знаки доллара вокруг не мешают. */
  const texOnly = (code, rich) => rich(`$$${String(code ?? '').trim().replace(/^[$]+|[$]+$/g, '')}$$`);
  const symbol = (code, rich) => rich(/\\[a-zA-Z]/.test(code) && !String(code).includes('$') ? `$${code}$` : code);

  const SHORT = /(?:^|[\s(])(?:рис|табл|стр|гл|см|ср|др|пр|т|е|п|д|ф|им|напр|[A-ZА-ЯЁ])\.$/i;
  /** Первая мысль отдельно: точка после «рис.» или «табл.» предложение не заканчивает. */
  const splitLead = (text) => {
    const source = String(text ?? '').trim();
    for (const m of source.matchAll(/[.!?](?=\s+[А-ЯЁA-Z«\d$(])/g)) {
      const head = source.slice(0, m.index + 1);
      if (!SHORT.test(head)) return [head, source.slice(m.index + 1).trim()];
    }
    return [source, ''];
  };

  const escRe = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  // «зона» находит «зоне» и «зоны»: отбрасываем гласную на конце и разрешаем окончание до трёх букв
  const wordPattern = (word) => {
    if (word.length < 4 || !/^[а-яё-]+$/i.test(word)) return escRe(word);
    const stem = word.replace(/[аяоеыийуюьэ]{1,2}$/i, '');
    return `${escRe(stem.length < 3 ? word : stem)}\\p{L}{0,3}`;
  };
  const termPattern = (term) => {
    const all = term.replace(/\([^)]*\)/g, ' ').trim().split(/[\s,]+/).filter(Boolean);
    const plain = all.filter((w) => /^[а-яё-]{4,}$/i.test(w));
    // обозначение после названия («номинальный диаметр d_н») в тексте часто опускают
    const words = plain.length && /[_a-zA-Zα-ωΑ-Ω]/.test(all.at(-1)) ? all.slice(0, -1) : all;
    if (!words.length) return null;
    const flags = words.length === 1 && !/^[а-яё-]{4,}$/i.test(words[0]) ? 'u' : 'iu';
    return new RegExp(`(?<![\\p{L}\\d_])${words.map(wordPattern).join('\\s+')}(?![\\p{L}\\d_])`, flags);
  };
  const formulaRanges = (text) => [...text.matchAll(new RegExp(FORMULA.source, 'g'))].map((m) => [m.index, m.index + m[0].length]);

  /** Отмечает в абзацах первое упоминание каждого термина; метки в разметку превращает rich. */
  const markTerms = (texts, terms) => {
    const order = terms.map((t, i) => [termPattern(t.term), i, t.term.length]).filter(([re]) => re).sort((a, b) => b[2] - a[2]);
    let left = order;
    return texts.map((text) => {
      const busy = formulaRanges(text);
      const found = left.reduce((acc, [re, i]) => {
        const m = re.exec(text);
        if (!m) return acc;
        const [from, to] = [m.index, m.index + m[0].length];
        const taken = [...busy, ...acc.map((x) => [x.from, x.to])].some(([a, b]) => from < b && to > a);
        return taken ? acc : [...acc, { from, to, i }];
      }, []);
      left = left.filter(([, i]) => !found.some((f) => f.i === i));
      return [...found].sort((a, b) => b.from - a.from)
        .reduce((s, f) => `${s.slice(0, f.from)}${OPEN}${String.fromCharCode(INDEX + f.i)}${MID}${s.slice(f.from, f.to)}${CLOSE}${s.slice(f.to)}`, text);
    });
  };

  // ---------- карта связей ----------
  const edges = (steps) => {
    const byId = new Map(steps.map((s) => [s.id, s]));
    return steps.flatMap((s) => [...new Set((s.links || []).filter((l) => l.type === 'prerequisite').map((l) => l.target))].map((id) => [byId.get(id), s])).filter(([a]) => a);
  };
  const MIN_ARC = 12;
  const arcDepth = (span, longest, margin) => MIN_ARC + (margin - MIN_ARC) * Math.sqrt(Math.max(0, span - 1) / Math.max(1, longest - 1));

  // ---------- таблицы книги ----------
  /** Строки таблицы с пометкой исправленных ячеек: from — что стояло в распознанном тексте. row и col считаются с нуля, без шапки. */
  const tableRows = (t) => {
    const width = Math.max(t.header?.length ?? 0, ...t.rows.map((r) => r.length));
    const fixed = new Map((t.corrections || []).map((c) => [`${c.row}:${c.col}`, c]));
    return t.rows.map((row, r) => Array.from({ length: width }, (_, c) => {
      const fix = fixed.get(`${r}:${c}`);
      return { text: fix ? String(fix.to) : String(row[c] ?? ''), from: fix ? String(fix.from) : null };
    }));
  };

  const api = { norm, parseNumber, isAnswered, isCorrect, shuffled, startOrder, showNumber, nextCard, rateCard, cleanState, parseHash, esc, makeRich, texOnly, symbol, splitLead, markTerms, edges, arcDepth, tableRows };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else window.GlavaCore = api;
})();
