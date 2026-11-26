/*
 * Диагноз у заданий курса. Плеер ничего не знает о заблуждениях: связь держится на разметке задания
 * ([data-task], .option.wrong[data-id], .verdict), она одинакова у обоих плееров.
 */
(() => {
  const course = window.COURSE;
  const lab = window.LAB;
  if (!course || !lab) return;
  const KEY = `glava.diagnosis.${course.id}`;
  const load = () => { try { return JSON.parse(localStorage.getItem(KEY)) || {}; } catch { return {}; } };
  const save = (memory) => { try { localStorage.setItem(KEY, JSON.stringify(memory)); } catch { /* приватное окно */ } };
  const script = document.createElement('script');
  script.src = 'lab/core.js';

  const start = () => {
    const core = window.LabCore;
    const index = core.misconceptionIndex(course, lab.misconceptions || {});
    const tasks = new Map(course.steps.flatMap((s) => s.tasks.map((t) => [t.id, { task: t, step: s }])));
    const el = (tag, className, text) => { const node = document.createElement(tag); if (className) node.className = className; if (text) node.textContent = text; return node; };
    const link = (href, text) => { const a = el('a', '', text); a.href = href; return a; };

    const block = (task, step, option) => {
      const row = index.get(option.misconception);
      const box = el('div', 'diagnosis');
      box.append(el('strong', '', 'Похоже, вы рассуждаете так'));
      box.append(el('p', '', `«${(lab.misconceptions || {})[option.misconception] || option.text}»`));
      const own = row.steps.find((s) => s.misconception && s.misconception.text);
      if (own) box.append(el('p', '', own.misconception.text));
      const where = el('p', 'diagnosis-links');
      const study = row.steps.find((s) => s.id !== step.id);
      if (study) where.append(link(`#/step/${study.order}/mistake`, `Разобрать: шаг ${study.order}`));
      const again = row.tasks.find((t) => t.task.id !== task.id && t.step.id !== step.id);
      if (again) where.append(link(`#/step/${again.step.order}/tasks`, `Похожая задача: шаг ${again.step.order}`));
      where.append(link('lab.html#diagnosis', 'Все мои заблуждения'));
      box.append(where);
      return box;
    };

    const review = (card) => {
      const verdict = card.querySelector('.verdict');
      if (!verdict || verdict.dataset.diagnosed) return;
      verdict.dataset.diagnosed = '1';
      const found = tasks.get(card.dataset.task);
      if (!found || !['single', 'multiple'].includes(found.task.type)) return;
      const right = Array.isArray(found.task.answer) ? found.task.answer : [found.task.answer];
      const wrong = [...card.querySelectorAll('.option.wrong[data-id]')].map((x) => x.dataset.id);
      const picked = [...wrong, ...(verdict.classList.contains('good') ? right : [])];
      save(core.remember(load(), found.task, picked));
      core.diagnose(found.task, picked).slice(0, 2).forEach((option) => verdict.append(block(found.task, found.step, option)));
    };

    const scan = () => document.querySelectorAll('[data-task]').forEach(review);
    new MutationObserver(scan).observe(document.body, { childList: true, subtree: true });
    scan();
  };

  const style = document.createElement('style');
  style.textContent = `
    .diagnosis { margin-top: 12px; padding: 12px 14px; border-radius: 10px; background: var(--warn-soft, #fff4dc); color: var(--text, #17133f); }
    .diagnosis p { margin-top: 6px; }
    .diagnosis-links { display: flex; flex-wrap: wrap; gap: 4px 16px; }
    .diagnosis-links a { min-height: 32px; display: inline-flex; align-items: center; }
    .lab-link { position: fixed; right: 16px; bottom: 16px; z-index: 5; padding: 10px 16px; border-radius: 99px; background: var(--fill, var(--brand, #0b6e8f)); color: var(--brand-ink, #fff); font-size: 16px; font-weight: 500; text-decoration: none; box-shadow: 0 4px 16px rgb(0 0 0 / 22%); }
    body.locked .lab-link { display: none; }
    @media (max-width: 720px) { .lab-link { position: static; display: block; margin: 24px 16px; text-align: center; box-shadow: none; } }
    @media print { .lab-link { display: none; } }`;
  document.head.append(style);
  const entry = document.createElement('a');
  entry.className = 'lab-link';
  entry.href = 'lab.html';
  entry.textContent = 'Лаборатория';
  document.body.append(entry);
  script.addEventListener('load', start);
  document.head.append(script);
})();
