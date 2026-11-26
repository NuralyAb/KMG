/* Правила лаборатории без интерфейса: их проверяет backend/tests/course_ui/lab.test.js. */
(() => {
  // --- слепая скважина ---

  /** Балл 0–100: уверенный верный ответ дороже, уверенная ошибка обнуляет. Правило Брайера: выгодно называть честную уверенность. */
  const points = (isRight, confidence) => {
    const p = confidence / 100;
    return Math.round(100 * (isRight ? 1 - (1 - p) ** 2 : 1 - p ** 2));
  };

  const isScored = (practice, interval) => !(interval.truth in (practice.unscored || {}));

  const robotAnswer = (robot, interval, threshold) => {
    const m = interval.medians;
    if (robot.porosity !== undefined) {
      if (m.GR > robot.shale_gr) return 'shale';
      if (interval.porosity_density < robot.porosity) return 'tight';
    }
    const value = robot.param === 'pn' ? interval.pn : m[robot.param];
    return value !== null && value > threshold ? 'oil' : 'water';
  };

  const intervalsOf = (practice) => practice.wells.flatMap((w) => w.intervals.map((i) => ({ ...i, well: w.id })));

  const robotScore = (practice, robot, threshold) => {
    const rows = intervalsOf(practice).filter((i) => isScored(practice, i));
    return { right: rows.filter((i) => robotAnswer(robot, i, threshold) === i.truth).length, total: rows.length };
  };

  /** Есть ли порог, при котором робот не ошибается ни разу: перебор по шкале. */
  const bestThreshold = (practice, robot, steps = 200) => {
    let best = { threshold: robot.threshold, right: -1, total: 0 };
    for (let i = 0; i <= steps; i += 1) {
      const threshold = robot.min * (robot.max / robot.min) ** (i / steps);
      const score = robotScore(practice, robot, threshold);
      if (score.right > best.right) best = { threshold, ...score };
    }
    return best;
  };

  const summary = (practice, answers) => {
    const rows = intervalsOf(practice).filter((i) => isScored(practice, i) && answers[i.id]);
    const marked = rows.map((i) => ({ isRight: answers[i.id].choice === i.truth, confidence: answers[i.id].confidence }));
    const right = marked.filter((m) => m.isRight).length;
    const mean = (list) => (list.length ? list.reduce((a, b) => a + b, 0) / list.length : 0);
    return {
      right, total: rows.length, points: Math.round(mean(marked.map((m) => points(m.isRight, m.confidence)))),
      confidence: Math.round(mean(marked.map((m) => m.confidence))), accuracy: rows.length ? Math.round((100 * right) / rows.length) : 0,
    };
  };

  // --- диагноз заблуждений ---

  /** Где встречается каждое заблуждение: варианты ответа, которые на нём построены. */
  const misconceptionIndex = (course, known) => {
    const index = new Map();
    for (const step of course.steps) {
      for (const task of step.tasks) {
        for (const option of task.options || []) {
          if (!option.misconception) continue;
          const row = index.get(option.misconception) || { id: option.misconception, text: known[option.misconception] || option.text, context: known[option.misconception] ? '' : task.prompt, tasks: [], steps: [] };
          row.tasks.push({ task, step, option });
          index.set(option.misconception, row);
        }
      }
    }
    for (const step of course.steps) {
      const ref = step.misconception && step.misconception.ref;
      if (ref && index.has(ref)) index.get(ref).steps.push(step);
    }
    return index;
  };

  /** Что показал ответ: выбранные неверные варианты с записанным заблуждением. */
  const diagnose = (task, picked) => {
    const right = Array.isArray(task.answer) ? task.answer : [task.answer];
    return (task.options || []).filter((o) => picked.includes(o.id) && !right.includes(o.id) && o.misconception);
  };

  /** Вопросы диагностики: сначала частые заблуждения, по два вопроса на каждое, дальше разные места главы. */
  const diagnosticTasks = (course, index, size = 10) => {
    const usable = [...index.values()].map((row) => ({ ...row, tasks: row.tasks.filter((t) => t.task.type === 'single') })).filter((row) => row.tasks.length);
    const frequent = usable.filter((row) => row.tasks.length > 1).sort((a, b) => b.tasks.length - a.tasks.length);
    const taken = new Map();
    const take = (entry) => { if (taken.size < size && !taken.has(entry.task.id)) taken.set(entry.task.id, entry); };
    for (const row of frequent) { take(row.tasks[0]); take(row.tasks[Math.floor(row.tasks.length / 2)]); }
    const rest = usable.filter((row) => row.tasks.length === 1).map((row) => row.tasks[0]).filter((e) => !taken.has(e.task.id));
    const gap = Math.max(1, Math.floor(rest.length / Math.max(1, size - taken.size)));
    for (let i = 0; i < rest.length; i += gap) take(rest[i]);
    return [...taken.values()].sort((a, b) => a.step.order - b.step.order);
  };

  /** Память ученика: сколько раз заблуждение сработало и сколько раз подряд его обошли после этого. */
  const remember = (memory, task, picked) => {
    const caught = new Set(diagnose(task, picked).map((o) => o.misconception));
    const offered = new Set((task.options || []).map((o) => o.misconception).filter(Boolean));
    const next = { ...memory };
    for (const id of offered) {
      const was = next[id] || { hits: 0, avoided: 0 };
      next[id] = caught.has(id) ? { hits: was.hits + 1, avoided: 0 } : { ...was, avoided: was.avoided + 1 };
    }
    return next;
  };

  /** clear — обходил всегда, beaten — попался, потом обошёл, caught — попался и ещё не обошёл. */
  const standing = (row) => (!row ? 'unknown' : row.hits === 0 ? 'clear' : row.avoided > 0 ? 'beaten' : 'caught');

  // --- карта ручного труда ---

  const labourRows = (course) => course.steps.filter((s) => s.inefficiency_lens).map((s) => {
    const { inputs, manual_steps: manual, judgment_points: judgment, time, typical_errors: errors } = s.inefficiency_lens;
    return { id: s.id, order: s.order, title: s.short_title, inputs, manual, judgment, time, errors, pages: s.pages || [],
      breaks: (s.data_meaning && s.data_meaning.breaks && s.data_meaning.breaks.text) || '', hypotheses: ((s.data_meaning && s.data_meaning.hypotheses) || []).map((h) => h.text || h) };
  });

  const csvCell = (value) => {
    const text = String(value ?? '');
    // ячейка, которая начинается как формула, в Excel выполнилась бы
    const safe = /^[=+\-@\t]/.test(text) ? `'${text}` : text;
    return `"${safe.replace(/"/g, '""')}"`;
  };
  const toCsv = (rows) => `﻿${rows.map((r) => r.map(csvCell).join(';')).join('\r\n')}`;

  const api = { points, isScored, robotAnswer, robotScore, bestThreshold, intervalsOf, summary, misconceptionIndex, diagnose, diagnosticTasks, remember, standing, labourRows, toCsv };
  if (typeof module === 'object' && module.exports) module.exports = api;
  else window.LabCore = api;
})();
