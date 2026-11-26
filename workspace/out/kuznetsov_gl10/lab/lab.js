/* Лаборатория: слепая скважина, диагноз заблуждений, карта ручного труда, паспорт переноса. */
(() => {
  const { COURSE: course, LAB: lab, LabCore: core, LabWell: well } = window;
  const { esc, ru } = well;
  const main = document.getElementById('main');
  const read = (key, fallback) => { try { return JSON.parse(localStorage.getItem(key)) ?? fallback; } catch { return fallback; } };
  const write = (key, value) => { try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* приватное окно: до закрытия страницы */ } };
  const store = { get: (k, f) => read(`glava.lab.${course.id}.${k}`, f), set: (k, v) => write(`glava.lab.${course.id}.${k}`, v) };
  const MEMORY = `glava.diagnosis.${course.id}`;
  const theme = read(`glava.${course.id}`, {})?.theme;
  if (theme === 'dark' || theme === 'light') document.documentElement.dataset.theme = theme;
  const stepLink = (s, section = '') => `<a href="index.html#/step/${s.order}${section}">шаг ${s.order}, ${esc(s.short_title)}</a>`;

  // --- диагноз ---

  const index = core.misconceptionIndex(course, lab.misconceptions || {});
  const questions = core.diagnosticTasks(course, index);
  const STATE = {
    caught: ['Похоже, ещё мешает', 'no'], beaten: ['Было, но вы его обошли', 'ok'], clear: ['Не проявилось', 'ok'], unknown: ['Ещё не проверяли', ''],
  };

  const misconceptionMap = () => {
    const memory = read(MEMORY, {});
    const rows = [...index.values()].map((r) => ({ ...r, state: core.standing(memory[r.id]) }));
    const seen = rows.filter((r) => r.state !== 'unknown');
    if (!seen.length) return '<p class="muted">Карта заполнится после ответов: здесь или в заданиях курса.</p>';
    const order = ['caught', 'beaten', 'clear'];
    return `<ul class="verdicts">${seen.sort((a, b) => order.indexOf(a.state) - order.indexOf(b.state)).map((r) => `<li class="card ${STATE[r.state][1]}"><p class="state">${STATE[r.state][0]}</p>${r.context ? `<p class="muted">${esc(r.context)}</p>` : ''}<p>«${esc(r.text)}»</p>
      ${r.state === 'caught' ? `<p>Что делать: ${[...r.steps.slice(0, 2).map((s) => `прочитать ${stepLink(s, '/mistake')}`), ...r.tasks.slice(0, 1).map((t) => `решить задание, ${stepLink(t.step, '/tasks')}`)].join('; ')}.</p>` : ''}</li>`).join('')}</ul>`;
  };

  const diagnosisPage = () => {
    let at = -1;
    let picked = null;
    let isShown = false;
    const answers = [];
    const shuffled = (task) => [...task.options].map((o, i) => [((i + 1) * 7919 + task.id.length * 31) % 101, o]).sort((a, b) => a[0] - b[0]).map(([, o]) => o);

    const draw = () => {
      const entry = questions[at];
      if (at < 0) {
        main.innerHTML = `<div class="page"><h1>Диагноз заблуждений</h1><p>${questions.length} вопросов по всей главе. Неверные варианты построены на типичных заблуждениях, поэтому ошибка показывает ход мысли, а не только пробел.</p>
          <p class="muted">Вывод по одному ответу — предположение. Ответы хранятся только в этом браузере.</p><button class="btn main" data-start ${questions.length ? '' : 'disabled'}>Начать</button>
          <h2>Карта заблуждений</h2>${misconceptionMap()}</div>`;
        return;
      }
      if (!entry) {
        const right = answers.filter(Boolean).length;
        main.innerHTML = `<div class="page"><h1 tabindex="-1">Верно ${right} из ${questions.length}</h1><p>Ниже — что за этим стоит. Начните с красных строк.</p>${misconceptionMap()}<button class="btn" data-home>К началу</button></div>`;
        main.querySelector('h1').focus({ preventScroll: true });
        window.scrollTo(0, 0);
        return;
      }
      const { task, step } = entry;
      const found = isShown ? core.diagnose(task, [picked]) : [];
      const isRight = [].concat(task.answer).includes(picked);
      const option = (o) => {
        const right = isShown && [].concat(task.answer).includes(o.id);
        const mine = picked === o.id;
        return `<button class="option ${right ? 'right' : isShown && mine ? 'wrong' : mine ? 'on' : ''}" data-pick="${esc(o.id)}" aria-pressed="${mine}" ${isShown ? 'disabled' : ''}>${esc(o.text)}${right ? ' <b>верный ответ</b>' : ''}</button>`;
      };
      main.innerHTML = `<div class="page"><p class="muted">Вопрос ${at + 1} из ${questions.length}</p><h2 tabindex="-1">${esc(task.prompt)}</h2><div class="options">${shuffled(task).map(option).join('')}</div>
        ${isShown ? `<div class="card ${isRight ? 'ok' : 'no'}"><p class="state">${isRight ? 'Верно' : 'Неверно'}</p><p>${esc(task.explanation)}</p>${found.map((o) => `<p><b>Похоже, вы рассуждаете так:</b> «${esc(index.get(o.misconception).text)}»</p>`).join('')}<p class="muted">Разобрано: ${stepLink(step)}</p></div><button class="btn main" data-next>Дальше</button>`
        : `<button class="btn main" data-check ${picked ? '' : 'disabled'}>Проверить</button>`}</div>`;
      main.querySelector(isShown ? '[data-next]' : 'h2').focus({ preventScroll: !isShown });
    };
    main.onclick = (e) => {
      const has = (name) => e.target.closest(`[data-${name}]`);
      if (has('start')) { at = 0; picked = null; isShown = false; answers.length = 0; }
      else if (has('pick')) picked = has('pick').dataset.pick;
      else if (has('check')) {
        isShown = true;
        answers.push([].concat(questions[at].task.answer).includes(picked));
        write(MEMORY, core.remember(read(MEMORY, {}), questions[at].task, [picked]));
      } else if (has('next')) { at += 1; picked = null; isShown = false; }
      else if (has('home')) at = -1;
      else return;
      draw();
    };
    draw();
  };

  // --- карта ручного труда ---

  const PLANS = [['', 'не решено'], ['auto', 'автоматизировать'], ['help', 'помочь подсказкой'], ['human', 'оставить человеку']];
  const labourPage = () => {
    const rows = core.labourRows(course);
    const plans = store.get('plans', {});
    const row = (r) => `<li class="card labour" data-row="${esc(r.id)}"><h3>${esc(r.title)} <span class="muted">шаг ${r.order}</span></h3>
      <dl><div><dt>На входе</dt><dd>${esc(r.inputs)}</dd></div><div><dt>Руками</dt><dd>${esc(r.manual)}</dd></div><div><dt>Где нужно суждение</dt><dd>${esc(r.judgment)}</dd></div>
      <div><dt>Типичные ошибки</dt><dd>${esc(r.errors)}</dd></div>${r.time && !/не указан/.test(r.time) ? `<div><dt>Время</dt><dd>${esc(r.time)}</dd></div>` : ''}${r.breaks ? `<div><dt>Что ломается в данных</dt><dd>${esc(r.breaks)}</dd></div>` : ''}
      ${r.hypotheses.length ? `<div><dt>Гипотеза модели</dt><dd>${r.hypotheses.map(esc).join(' ')}</dd></div>` : ''}</dl>
      <div class="plan"><label>Решение <select data-plan>${PLANS.map(([k, t]) => `<option value="${k}" ${(plans[r.id]?.plan || '') === k ? 'selected' : ''}>${t}</option>`).join('')}</select></label>
      <label class="note">Идея <input type="text" data-note maxlength="300" value="${esc(plans[r.id]?.note || '')}" placeholder="что попробовать и как проверить"></label></div>
      <p class="muted">Стр. ${r.pages.join(', ')}. <a href="index.html#/step/${r.order}">Открыть шаг</a></p></li>`;
    const tally = () => PLANS.slice(1).map(([k, t]) => `${t}: ${rows.filter((r) => plans[r.id]?.plan === k).length}`).join(', ');
    main.innerHTML = `<div class="page wide"><h1>Карта ручного труда</h1><p>Что специалист делает руками и где без его суждения не обойтись. Отметьте решение, допишите идею и выгрузите список для команды.</p>
      <p class="muted">Поля заполнила модель по главе, поэтому это гипотезы для разговора с геологом. Денег и сроков здесь нет: в главе их нет. Узлов с разбором: ${rows.length} из ${course.steps.length}.</p>
      <p><b data-tally>${tally()}</b></p><button class="btn main" data-csv>Скачать таблицу (CSV)</button><ul class="verdicts">${rows.map(row).join('')}</ul></div>`;
    main.onclick = (e) => {
      if (!e.target.closest('[data-csv]')) return;
      const table = [['Шаг', 'Название', 'На входе', 'Ручные шаги', 'Точки суждения', 'Типичные ошибки', 'Что ломается в данных', 'Решение команды', 'Идея', 'Страницы'],
        ...rows.map((r) => [r.order, r.title, r.inputs, r.manual, r.judgment, r.errors, r.breaks, PLANS.find(([k]) => k === (plans[r.id]?.plan || ''))[1], plans[r.id]?.note || '', r.pages.join(', ')])];
      const a = document.createElement('a');
      a.href = URL.createObjectURL(new Blob([core.toCsv(table)], { type: 'text/csv;charset=utf-8' }));
      a.download = `${course.id}-ручной-труд.csv`;
      a.click();
      setTimeout(() => URL.revokeObjectURL(a.href), 1000);
    };
    main.oninput = (e) => {
      const id = e.target.closest('[data-row]')?.dataset.row;
      if (!id) return;
      const box = e.target.closest('[data-row]');
      plans[id] = { plan: box.querySelector('[data-plan]').value, note: box.querySelector('[data-note]').value };
      store.set('plans', plans);
      main.querySelector('[data-tally]').textContent = tally();
    };
  };

  // --- паспорт переноса ---

  const MARK = { good: ['✓', 'ok', 'в порядке'], warn: ['!', 'warn', 'посмотреть'], bad: ['✗', 'no', 'не выполнено'], unknown: ['?', '', 'не измерено'] };
  const TEMPLATE = { ready: 'сцена готова', template: 'есть шаблон', new: 'нужен новый' };
  const passportPage = () => {
    const p = lab.passport;
    const checks = p.checks.map((c) => `<tr class="${MARK[c.state][1]}"><td><span title="${MARK[c.state][2]}">${MARK[c.state][0]}</span><span class="sr">${MARK[c.state][2]}</span></td><th scope="row">${esc(c.title)}${c.note ? `<small>${esc(c.note)}</small>` : ''}</th><td>${esc(c.value)}</td><td class="muted">${esc(c.target)}</td></tr>`).join('');
    const templates = p.templates.map((t) => `<tr><td>${t.order}</td><th scope="row">${esc(t.title)}</th><td>${esc(t.difficulty.primary)}${t.difficulty.secondary ? `+${esc(t.difficulty.secondary)}` : ''}</td><td>${esc(t.format)}</td><td>${t.score}</td><td class="${t.state === 'new' ? 'no' : 'ok'}">${TEMPLATE[t.state]}${t.template ? `: ${esc(t.template)}` : ''}</td></tr>`).join('');
    const top = Math.max(...p.cost.stages.map((s) => s.usd), 0.01);
    main.innerHTML = `<div class="page wide"><h1>Паспорт переноса</h1><p>${esc(p.title)}. ${esc(p.book)}</p>
      <div class="facts"><div><b>${p.counts.pages}</b><span>страниц</span></div><div><b>${p.counts.nodes}</b><span>шагов</span></div><div><b>${p.counts.claims}</b><span>утверждений</span></div><div><b>$${ru(p.cost.total_usd, 2)}</b><span>расход по журналу</span></div><div><b>$${ru(p.cost.per_node_usd, 2)}</b><span>на узел</span></div></div>
      <h2>Требования</h2><div class="scroll" tabindex="0" role="region" aria-label="Требования"><table><thead><tr><th></th><th>Что</th><th>Сейчас</th><th>Нужно</th></tr></thead><tbody>${checks}</tbody></table></div>
      <h2>Шаблоны для узлов с движением</h2><p class="muted">Балл — сумма пяти критериев видеоёмкости, от 0 до 10.</p><div class="scroll" tabindex="0" role="region" aria-label="Шаблоны"><table><thead><tr><th>Шаг</th><th>Узел</th><th>Трудность</th><th>Формат</th><th>Балл</th><th>Шаблон</th></tr></thead><tbody>${templates}</tbody></table></div>
      <h2>На что ушли деньги</h2><p class="muted">Все прогоны вместе, с повторными.</p><ul class="bars">${p.cost.stages.map((s) => `<li><span>${esc(s.stage)}</span><i><u style="width:${(100 * s.usd) / top}%"></u></i><b>$${ru(s.usd, 2)}</b></li>`).join('')}</ul>
      ${p.scan_pages.length ? `<h2>Где нужен скан</h2><p>Страницы ${p.scan_pages.join(', ')}: числа и подписи с рисунков.</p>` : ''}</div>`;
  };

  // --- страницы ---

  const wellPage = () => { main.innerHTML = '<div class="page wide"><div data-root></div></div>'; well.mount(main.querySelector('[data-root]'), lab.practice, course, store); };
  const PAGES = [...(lab.practice ? [['well', 'Слепая скважина', wellPage]] : []), ['diagnosis', 'Диагноз', diagnosisPage], ['labour', 'Ручной труд', labourPage], ['passport', 'Паспорт', passportPage]];
  // паспорт с расходом нужен автору и жюри: у ученика в меню его нет, открывается по адресу lab.html#passport
  const MENU = PAGES.filter(([k]) => k !== 'passport');
  const nav = document.querySelector('.tabs');
  const open = () => {
    const id = location.hash.slice(1);
    const page = PAGES.find(([k]) => k === id) || PAGES[0];
    main.onclick = null;
    main.oninput = null;
    nav.innerHTML = (page[0] === 'passport' ? PAGES : MENU).map(([k, title]) => `<a href="#${k}" ${k === page[0] ? 'aria-current="page"' : ''}>${title}</a>`).join('');
    document.title = `${page[1]} — ${course.title}`;
    page[2]();
    window.scrollTo(0, 0);
  };
  document.querySelector('.skip').addEventListener('click', (e) => { e.preventDefault(); main.focus(); });
  window.addEventListener('hashchange', open);
  open();
})();
