/* Задания пяти типов: выбор, несколько ответов, порядок, пропуски, расчёт. Проверка сразу, без сети. */
(() => {
  'use strict';
  const core = window.GlavaCore;
  const { esc } = core;
  const HINT = { single: 'Один верный ответ', multiple: 'Несколько верных ответов', order: 'Расставьте по порядку: перетащите строку за ручку слева или нажимайте стрелки', gap: 'Впишите пропущенные слова', calc: 'Введите число' };
  const EMPTY = { single: 'Сначала выберите ответ.', multiple: 'Сначала отметьте хотя бы один ответ.', gap: 'Заполните все пропуски.', calc: 'Введите число.' };

  /** root — пустая карточка; ctx: rich, page (страница утверждения), solved, onCheck(верно), say(текст для читалки). */
  function mount(root, task, ctx) {
    const { rich } = ctx;
    const options = core.shuffled(task.options || [], task.id);
    const byId = (id) => (task.options || []).find((o) => o.id === id);
    let picked = task.type === 'order' ? core.startOrder(task.options, task.answer, task.id) : [];
    let verdict = null;
    let shown = false;
    let solved = ctx.solved;

    const inputs = () => [...root.querySelectorAll('input')];
    const values = () => inputs().map((x) => x.value);
    const label = (id) => rich(byId(id)?.text ?? id);
    const answerText = () => {
      if (task.type === 'single') return label(task.answer);
      if (task.type === 'multiple') return task.answer.map(label).join('; ');
      if (task.type === 'order') return task.answer.map(label).join(' → ');
      if (task.type === 'gap') return task.answer.map(esc).join('; ');
      return `${esc(core.showNumber(task.answer))} ${esc(task.unit || '')}`;
    };
    const lock = () => (shown ? 'disabled' : '');
    const promptId = `q-${task.id.replace(/[^\w-]/g, '-')}`;
    const group = (html) => `<div class="options" role="group" aria-labelledby="${promptId}">${html}</div>`;

    const choice = (o) => {
      const mine = picked.includes(o.id);
      const right = shown && [].concat(task.answer).includes(o.id);
      const wrong = shown && mine && !right;
      const state = shown ? `${right ? ' right' : ''}${wrong ? ' wrong' : ''}` : `${mine ? ' on' : ''}`;
      const note = right ? (mine ? 'верно' : 'верный ответ') : wrong ? 'ваш выбор, неверно' : '';
      return `<button type="button" class="option${state}" data-id="${esc(o.id)}" aria-pressed="${mine}" ${lock()}><span>${rich(o.text)}</span>${note ? `<span class="tag">${note}</span>` : ''}</button>`;
    };
    const row = (id, i) => {
      const right = task.answer[i] === id;
      const text = esc(byId(id).text);
      const head = `<span class="num">${i + 1}.</span><span class="what">${label(id)}</span>`;
      if (shown) return `<div class="option ${right ? 'right' : 'wrong'}">${head}<span class="tag">${right ? 'на месте' : 'не на месте'}</span></div>`;
      return `<div class="option drag" data-id="${esc(id)}"><span class="grip" aria-hidden="true">⠿</span>${head}<span class="move"><button type="button" data-move="-1" aria-label="Выше: ${text}">↑</button><button type="button" data-move="1" aria-label="Ниже: ${text}">↓</button></span></div>`;
    };
    const gapText = () => rich(task.prompt).replace(/\{\{(\d+)\}\}/g, (_, n) => `<input class="gap-input" type="text" autocomplete="off" autocapitalize="off" spellcheck="false" aria-label="Пропуск ${n}" ${lock()}>`);
    const body = () => {
      if (task.type === 'gap') return `<p class="gaps">${gapText()}</p>${task.answer.some((a) => a.includes('ρ')) ? '<p class="muted">Вместо ρ можно набрать букву «р».</p>' : ''}`;
      if (task.type === 'calc') return `<label>Ответ${task.unit ? `, ${esc(task.unit)}` : ''}<br><input type="text" inputmode="text" autocomplete="off" ${lock()}></label>`;
      return group(task.type === 'order' ? picked.map(row).join('') : options.map(choice).join(''));
    };
    const result = () => `<div class="verdict ${verdict ? 'good' : 'bad'}" tabindex="-1"><strong>${verdict ? 'Верно' : 'Пока нет'}</strong><p>Верный ответ: ${answerText()}</p><p>${rich(task.explanation)}${ctx.page}</p></div><button type="button" class="btn" data-again>Ещё раз</button>`;
    const heading = () => (task.type === 'gap' ? `<h3 id="${promptId}">Заполните пропуски</h3>` : `<h3 id="${promptId}">${rich(task.prompt)}</h3>`);
    const draw = () => {
      root.innerHTML = `${heading()}<p class="muted">${HINT[task.type]}${solved ? ' · <span class="ok">решено</span>' : ''}</p>${body()}${shown ? result() : '<p class="empty" hidden></p><button type="button" class="btn main" data-check>Проверить</button>'}`;
    };
    const markInputs = (typed) => inputs().forEach((x, i) => {
      const ok = task.type === 'gap' ? core.isCorrect({ type: 'gap', answer: [task.answer[i]] }, [], [typed[i]]) : verdict;
      x.value = typed[i];
      x.classList.add(ok ? 'right' : 'wrong');
      if (!ok) x.setAttribute('aria-invalid', 'true');
    });
    const check = () => {
      const typed = values();
      if (!core.isAnswered(task, picked, typed)) {
        const note = root.querySelector('.empty');
        note.textContent = EMPTY[task.type];
        note.hidden = false;
        ctx.say(EMPTY[task.type]);
        inputs().find((x) => !x.value.trim())?.focus();
        return;
      }
      verdict = core.isCorrect(task, picked, typed);
      shown = true;
      solved = solved || verdict;
      ctx.onCheck(solved);
      draw();
      markInputs(typed);
      // фокус на вердикт читается один раз; живая область здесь дала бы повтор
      root.querySelector('.verdict').focus();
    };
    const again = () => {
      shown = false;
      picked = task.type === 'order' ? picked : [];
      draw();
      root.querySelector('input, .options button')?.focus();
    };
    const place = (id, to) => {
      const rest = picked.filter((x) => x !== id);
      picked = [...rest.slice(0, to), id, ...rest.slice(to)];
      draw();
      ctx.say(`Место ${to + 1} из ${picked.length}`);
    };
    const move = (id, shift) => {
      const to = picked.indexOf(id) + shift;
      if (to < 0 || to >= picked.length) { ctx.say(shift < 0 ? 'Уже первый' : 'Уже последний'); return; }
      place(id, to);
      root.querySelector(`[data-id="${CSS.escape(id)}"] [data-move="${shift}"]`)?.focus();
    };
    const choose = (id) => {
      if (task.type === 'single') picked = [id];
      else picked = picked.includes(id) ? picked.filter((x) => x !== id) : [...picked, id];
      draw();
      root.querySelector(`[data-id="${CSS.escape(id)}"]`)?.focus();
    };

    root.addEventListener('click', (e) => {
      const button = e.target.closest('button');
      if (!button) return;
      const id = button.closest('[data-id]')?.dataset.id;
      if ('check' in button.dataset) check();
      else if ('again' in button.dataset) again();
      else if (button.dataset.move) move(id, Number(button.dataset.move));
      else if (id) choose(id);
    });
    root.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && e.target.matches('input')) { e.preventDefault(); check(); }
    });
    // пальцем строка тянется только за ручку: иначе список не даёт прокрутить страницу
    root.addEventListener('pointerdown', (e) => {
      const item = e.target.closest('.drag');
      if (!item || shown || e.button > 0 || e.target.closest('button') || (e.pointerType !== 'mouse' && !e.target.closest('.grip'))) return;
      e.preventDefault();
      const box = item.parentNode;
      const id = item.dataset.id;
      item.classList.add('lift');
      const drag = (ev) => {
        const others = [...box.children].filter((x) => x !== item);
        const after = others.find((x) => { const r = x.getBoundingClientRect(); return ev.clientY < r.top + r.height / 2; });
        if ((after ?? null) !== item.nextElementSibling) box.insertBefore(item, after ?? null);
      };
      const drop = () => {
        document.removeEventListener('pointermove', drag);
        document.removeEventListener('pointerup', drop);
        document.removeEventListener('pointercancel', drop);
        place(id, [...box.children].indexOf(item));
      };
      document.addEventListener('pointermove', drag);
      document.addEventListener('pointerup', drop);
      document.addEventListener('pointercancel', drop);
    });
    draw();
  }

  window.GlavaTasks = { mount };
})();
