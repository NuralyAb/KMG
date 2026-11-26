# Аудит собранного курса по ТЗ в браузере без сети: 390 и 1280 px, светлая и тёмная тема.
# python course_audit.py <папка курса> [папка кадров]
import json
import pathlib
import sys
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding='utf-8')
course = pathlib.Path(sys.argv[1]).resolve()
shots = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else None
if shots:
    shots.mkdir(parents=True, exist_ok=True)
ok, bad = [], []
URL = (course / 'index.html').as_uri()


def check(name, good, detail=''):
    (ok if good else bad).append(name + (f' — {detail}' if detail and not good else ''))


# мелкий шрифт: видимые текстовые узлы мельче 16 px (кроме формул KaTeX, индексов и скрытого для читалки)
SMALL = '''() => {
  const out = {};
  const walk = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  while (walk.nextNode()) {
    const t = walk.currentNode; const el = t.parentElement;
    if (!t.textContent.trim() || !el || el.closest('.katex, sub, sup, .sr, svg, [hidden], .skip, dialog:not([open])')) continue;
    const r = el.getBoundingClientRect(); if (!r.width || !r.height) continue;
    const size = parseFloat(getComputedStyle(el).fontSize);
    if (size < 15.5) { const k = (el.className && typeof el.className === 'string' ? '.' + el.className.split(' ')[0] : el.tagName.toLowerCase()) + ' ' + size + 'px'; out[k] = (out[k] || 0) + 1; }
  }
  return out;
}'''
# длина строки: самая длинная строка абзацев страницы в знаках
LINE = '''() => {
  let worst = 0, where = '';
  for (const p of document.querySelectorAll('main p, main li, main dd')) {
    if (!p.offsetParent || p.closest('table, .katex')) continue;
    const range = document.createRange(); const text = p.textContent; if (text.length < 80) continue;
    const lines = new Map();
    const walk = document.createTreeWalker(p, NodeFilter.SHOW_TEXT);
    while (walk.nextNode()) {
      const node = walk.currentNode;
      for (let i = 0; i < node.length; i++) {
        range.setStart(node, i); range.setEnd(node, i + 1);
        const r = range.getClientRects()[0]; if (!r) continue;
        const y = Math.round(r.top); lines.set(y, (lines.get(y) || 0) + 1);
      }
    }
    for (const n of lines.values()) if (n > worst) { worst = n; where = text.slice(0, 40); }
  }
  return [worst, where];
}'''
OVERFLOW = 'document.documentElement.scrollWidth > innerWidth + 1'


def pages(pg):
    return ['#/', '#/step/1', '#/step/11', '#/step/27', '#/step/41', '#/cards', '#/summary', '#/map', '#/help']


with sync_playwright() as p:
    b = p.chromium.launch(channel='chrome')
    for tag, size in (('m', {'width': 390, 'height': 844}), ('d', {'width': 1280, 'height': 800})):
        for scheme in ('light', 'dark'):
            ctx = b.new_context(viewport=size, offline=True, color_scheme=scheme, has_touch=tag == 'm', is_mobile=tag == 'm')
            pg = ctx.new_page()
            pg.on('pageerror', lambda e: bad.append('JS: ' + str(e)[:200]))
            pg.on('request', lambda r: bad.append('сеть: ' + r.url[:90]) if not r.url.startswith(('file:', 'data:', 'blob:')) else None)
            pg.goto(URL + '#/')
            pg.wait_for_selector('h1')
            k = f'{tag}{size["width"]} {scheme}'
            theme = pg.evaluate("getComputedStyle(document.body).backgroundColor")
            check(f'{k}: тема применена', (theme.startswith('rgb(2') or theme.startswith('rgb(1')) if scheme == 'light' else not theme.startswith('rgb(2'), theme)
            small, longest = {}, 0
            for h in pages(pg):
                pg.evaluate('h => { location.hash = h }', h)
                pg.wait_for_timeout(350)
                for tab in (['about', 'data', 'tasks', 'source'] if '/step/' in h else [None]):
                    if tab:
                        t = pg.locator(f'[data-tab="{tab}"]')
                        if not t.count():
                            continue
                        t.click()
                        pg.wait_for_timeout(120)
                    check(f'{k} {h} {tab or ""}: нет горизонтальной прокрутки', not pg.evaluate(OVERFLOW), str(pg.evaluate('document.documentElement.scrollWidth')))
                    for key, n in pg.evaluate(SMALL).items():
                        small[key] = small.get(key, 0) + n
                    worst, where = pg.evaluate(LINE)
                    longest = max(longest, worst)
                    if worst > 80:
                        bad.append(f'{k} {h} {tab}: строка {worst} знаков «{where}»')
                if shots and scheme == 'light' and h in ('#/step/11',):
                    pg.locator('[data-tab="data"]').click()
                    pg.locator('.scroll').first.scroll_into_view_if_needed()
                    pg.screenshot(path=str(shots / f'{tag}_table.png'))
            check(f'{k}: текст не мельче 16 px', not small, json.dumps(small, ensure_ascii=False))
            ok.append(f'{k}: самая длинная строка {longest} знаков')
            # широкая таблица прокручивается внутри
            pg.evaluate('location.hash="#/step/27"'); pg.wait_for_timeout(300); pg.locator('[data-tab="data"]').click()
            sc = pg.locator('.scroll').first
            check(f'{k}: таблица шире экрана прокручивается внутри', sc.evaluate('e => getComputedStyle(e).overflowX') in ('auto', 'scroll'))
            if shots and scheme == 'dark' or shots and tag == 'm':
                pg.evaluate('location.hash="#/step/1"'); pg.wait_for_timeout(400)
                pg.screenshot(path=str(shots / f'{tag}_{scheme}_step.png'))
            ctx.close()

    # навигация, прогресс, место, клавиатура, задания, карточки — на телефоне с касанием
    ctx = b.new_context(viewport={'width': 390, 'height': 844}, offline=True, has_touch=True, is_mobile=True)
    pg = ctx.new_page()
    pg.on('pageerror', lambda e: bad.append('JS: ' + str(e)[:200]))
    pg.goto(URL + '#/')
    pg.wait_for_selector('h1')
    pg.keyboard.press('Tab')
    skip = pg.evaluate('document.activeElement.className')
    check('первый Tab — «К содержанию»', skip == 'skip', skip)
    check('«К содержанию» видна при фокусе', pg.locator('.skip').evaluate('e => e.getBoundingClientRect().top >= 0'))
    pg.keyboard.press('Enter')
    check('«К содержанию» ведёт в main', pg.evaluate('document.activeElement.id') == 'main')
    pg.keyboard.press('Tab')
    ring = pg.evaluate('(() => { const s = getComputedStyle(document.activeElement); return s.outlineStyle !== "none" && parseFloat(s.outlineWidth) > 0 || s.boxShadow !== "none" })()')
    check('видимый фокус', ring)
    alts = pg.evaluate('''async () => { const out = []; for (let i = 1; i <= 44; i++) { location.hash = '#/step/' + i; await new Promise(r => setTimeout(r, 60));
      for (const img of document.querySelectorAll('main img')) if (!img.alt || img.alt.length < 10) out.push(i); } return out; }''')
    check('альтернативный текст у всех картинок', not alts, str(alts))
    pg.evaluate('location.hash="#/step/1"'); pg.wait_for_timeout(300)
    check('заголовок шага и полное название рядом', pg.locator('.lesson header h1').count() == 1 and pg.locator('.lesson header p.muted').inner_text().strip() != '')
    check('оглавление шага (вкладки)', pg.locator('[role=tab]').count() >= 3)
    pg.locator('[data-done]').click(); pg.wait_for_timeout(300)
    check('«дальше» ведёт на шаг 2', pg.evaluate('location.hash') == '#/step/2')
    check('прогресс растёт', 'Пройдено 2%' in pg.locator('.plan-share').inner_text() or '1 из 44' in pg.locator('.plan-share').inner_text(), pg.locator('.plan-share').inner_text())
    pg.mouse.wheel(0, 900); pg.wait_for_timeout(400)
    y = pg.evaluate('scrollY')
    pg.locator('footer a.btn').click(); pg.wait_for_timeout(300)
    check('«назад» ведёт на шаг 1', pg.evaluate('location.hash') == '#/step/1')
    pg.go_back(); pg.wait_for_timeout(500)
    check('возврат к месту на странице', abs(pg.evaluate('scrollY') - y) < 30, f'{y} -> {pg.evaluate("scrollY")}')
    pg.evaluate('location.hash="#/"'); pg.wait_for_timeout(300)
    check('«Продолжить» с места остановки', 'Урок 1.2' in pg.locator('.hero h2').inner_text() or 'Продолжить' in pg.locator('.hero a').inner_text(), pg.locator('.hero').inner_text()[:80])
    # задания: число, типы, проверка, верный ответ и пояснение, ссылка на утверждение
    data = pg.evaluate('window.COURSE.steps.flatMap(s => s.tasks.map(t => t.type))')
    check('заданий ≥ 15', len(data) >= 15, str(len(data)))
    check('типов заданий ≥ 4', len(set(data)) >= 4, str(set(data)))
    pg.evaluate('location.hash="#/step/1"'); pg.wait_for_timeout(300)
    pg.locator('[data-tab="tasks"]').click()
    card = pg.locator('.task:has(button.option)').first
    card.locator('.option').first.click()
    card.locator('[data-check]').click()
    v = card.locator('.verdict')
    check('проверка сразу, верный ответ и пояснение', v.count() == 1 and 'Верный ответ' in v.inner_text())
    link = v.locator('a[href*="claim"]')
    check('ссылка на утверждение у задания', link.count() == 1)
    if link.count():
        link.click(); pg.wait_for_timeout(400)
        check('ссылка открывает утверждение во вкладке «Источник»', pg.locator('[data-tab="source"][aria-selected="true"]').count() == 1 and pg.evaluate('document.activeElement.matches(".claims li") && document.activeElement.querySelector("details").open'))
    # перетаскивание пальцем
    order_step = pg.evaluate('window.COURSE.steps.find(s => s.tasks.some(t => t.type === "order")).order')
    pg.evaluate(f'location.hash="#/step/{order_step}"'); pg.wait_for_timeout(300)
    pg.locator('[data-tab="tasks"]').click()
    again = pg.locator('.task:has(.rows) [data-again]')
    if again.count():
        again.first.click()
    rows = pg.locator('.rows:has(.grip)').first
    rows.scroll_into_view_if_needed()
    before = rows.evaluate('r => [...r.querySelectorAll("[data-id]")].map(x => x.dataset.id).join()')
    g = rows.locator('.grip').first.bounding_box()
    last = rows.locator('[data-id]').last.bounding_box()
    cdp = ctx.new_cdp_session(pg)
    x, y0, y1 = g['x'] + g['width'] / 2, g['y'] + g['height'] / 2, last['y'] + last['height'] - 4
    cdp.send('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': [{'x': x, 'y': y0}]})
    for i in range(1, 11):
        cdp.send('Input.dispatchTouchEvent', {'type': 'touchMove', 'touchPoints': [{'x': x, 'y': y0 + (y1 - y0) * i / 10}]})
        pg.wait_for_timeout(30)
    cdp.send('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []})
    pg.wait_for_timeout(200)
    after = rows.evaluate('r => [...r.querySelectorAll("[data-id]")].map(x => x.dataset.id).join()')
    check('перетаскивание пальцем меняет порядок', before != after, before)
    # карточки на все узлы
    pg.evaluate('location.hash="#/cards"'); pg.wait_for_timeout(300)
    check('карточки «знаю / повторить» на все узлы', 'из 44' in pg.locator('main').inner_text())
    pg.locator('[data-flip]').click(); pg.locator('[data-know="know"]').click(); pg.wait_for_timeout(200)
    check('карточка отмечается «знаю»', 'Осталось 43 из 44' in pg.locator('main').inner_text())
    # карта
    pg.evaluate('location.hash="#/map"'); pg.wait_for_timeout(500)
    check('карта связей нарисована', pg.locator('.map svg path').count() > 10, str(pg.locator('.map svg path').count()))
    # конспект и печать
    pg.evaluate('location.hash="#/summary"'); pg.wait_for_timeout(300)
    check('конспект: кнопка «Печать в PDF»', pg.locator('button:has-text("Печать в PDF")').count() == 1)
    check('конспект: все уроки', pg.locator('.summary .card').count() == 44)
    # сводка для проверки на новичках
    pg.evaluate('location.hash="#/help"'); pg.wait_for_timeout(300)
    check('сводка результатов в «Помощи»', pg.locator('[data-results]').count() == 1)
    ctx.close()

    # печать: без меню, без прокрутки вбок
    ctx = b.new_context(viewport={'width': 1280, 'height': 800}, offline=True)
    pg = ctx.new_page()
    pg.goto(URL + '#/summary'); pg.wait_for_selector('.summary')
    pg.emulate_media(media='print')
    check('печать: меню и кнопки скрыты', not pg.locator('.side').is_visible() and not pg.locator('.summary button').is_visible())
    if shots:
        pg.pdf(path=str(shots / 'summary.pdf'))
        check('PDF конспекта собран', (shots / 'summary.pdf').stat().st_size > 50000)
    ctx.close()

    # анимации при prefers-reduced-motion
    ctx = b.new_context(viewport={'width': 1280, 'height': 800}, offline=True, reduced_motion='reduce')
    pg = ctx.new_page()
    pg.goto(URL + '#/step/1'); pg.wait_for_selector('h1')
    slow = pg.evaluate('''[...document.querySelectorAll('*')].filter(e => { const s = getComputedStyle(e);
      return parseFloat(s.transitionDuration) > 0.02 || (s.animationName !== 'none' && parseFloat(s.animationDuration) > 0.02) }).map(e => e.className || e.tagName).slice(0, 5)''')
    check('prefers-reduced-motion гасит анимации', not slow, str(slow))
    smooth = pg.evaluate('getComputedStyle(document.documentElement).scrollBehavior')
    check('prefers-reduced-motion: без плавной прокрутки', smooth != 'smooth')
    ctx.close()
    b.close()

size = sum(f.stat().st_size for f in course.rglob('*') if f.is_file() and 'videos' not in f.parts) / 2**20
check('курс без видео ≤ 30 МБ', size <= 30, f'{size:.1f} МБ')
print(f'курс без видео: {size:.1f} МБ')
print('прошло:', len(ok))
print('\n'.join(ok))
print('\n'.join('ОШИБКА ' + x for x in bad) or 'ошибок нет')
sys.exit(bool(bad))
