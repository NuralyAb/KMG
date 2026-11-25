// Симуляторы шага: карточка с кадром, сама сцена грузится только по кнопке, в окне поверх курса.
(() => {
  const open = (item) => {
    const box = document.createElement('dialog');
    box.className = 'sim-window';
    box.setAttribute('aria-label', item.title);
    const bar = document.createElement('div');
    bar.className = 'sim-bar';
    const name = document.createElement('strong');
    name.textContent = item.title;
    const close = document.createElement('button');
    Object.assign(close, { type: 'button', className: 'btn', textContent: 'Закрыть' });
    const frame = document.createElement('iframe');
    Object.assign(frame, { title: item.title, src: `assets/sim/player.html#${encodeURIComponent(item.id)}` });
    frame.setAttribute('allow', 'fullscreen');
    bar.append(name, close);
    box.append(bar, frame);
    document.body.append(box);
    const leave = () => box.close();
    close.addEventListener('click', leave);
    // смена шага кнопкой «назад» не должна оставлять окно поверх курса
    addEventListener('hashchange', leave, { once: true });
    box.addEventListener('close', () => { removeEventListener('hashchange', leave); box.remove(); });
    box.showModal();
    close.focus();
  };

  const card = (item) => {
    const el = document.createElement('figure');
    el.className = 'sim-card';
    if (item.poster) {
      const img = document.createElement('img');
      Object.assign(img, { src: item.poster, alt: `Кадр симулятора «${item.title}»`, loading: 'lazy', width: 480, height: 320 });
      el.append(img);
    }
    const text = document.createElement('figcaption');
    const title = document.createElement('strong');
    title.textContent = item.title;
    const chip = document.createElement('span');
    chip.className = 'chip';
    chip.textContent = item.label;
    const goal = document.createElement('p');
    goal.textContent = item.goal;
    const go = document.createElement('button');
    Object.assign(go, { type: 'button', className: 'btn main', textContent: 'Открыть симулятор' });
    go.setAttribute('aria-label', `Открыть симулятор «${item.title}»`);
    go.addEventListener('click', () => open(item));
    text.append(title, ' ', chip, goal, go);
    el.append(text);
    return el;
  };

  const mount = (root) => root.querySelectorAll('[data-interactive="simulation"]').forEach((el) => {
    const { items = [] } = JSON.parse(el.dataset.params);
    el.classList.add('noprint');
    el.replaceChildren(...items.map(card));
  });
  window.Simulations = { mount };
})();
