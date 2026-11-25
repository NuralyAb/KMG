# Прохождение всех тренажёров настоящими кликами. Нужны Chrome и playwright.
import sys, pathlib
from playwright.sync_api import sync_playwright
root = pathlib.Path(__file__).resolve().parent.parent
url = (root / 'dist' / 'тренажёры.html').as_uri()
mob = 'mob' in sys.argv
out = pathlib.Path(sys.argv[sys.argv.index('--out') + 1]) if '--out' in sys.argv else None
errs, ok = [], []
def check(n, c): (ok if c else errs).append(n)
with sync_playwright() as p:
    b = p.chromium.launch(channel='chrome', args=['--enable-gpu', '--ignore-gpu-blocklist'])
    ctx = b.new_context(viewport={'width': 390, 'height': 844} if mob else {'width': 1280, 'height': 800}, has_touch=mob, offline=True)
    pg = ctx.new_page()
    pg.on('pageerror', lambda e: errs.append('JS: ' + str(e)[:200]))
    pg.on('console', lambda m: errs.append('console: ' + m.text[:200]) if m.type == 'error' else None)
    pg.on('request', lambda r: errs.append('сеть: ' + r.url[:80]) if r.url.startswith('http') else None)
    def shot(n): out and pg.screenshot(path=str(out / f"{'m' if mob else 'd'}_play_{n}.png"))
    def go(k): pg.goto('about:blank'); pg.goto(url + '#' + k); pg.wait_for_timeout(1200)

    pg.goto(url); pg.wait_for_timeout(1500); shot('home')
    check('карточки на старте', pg.locator('.card').count() >= 5)
    pg.locator('.card').nth(2).click(); pg.wait_for_timeout(900)
    check('карточка открывает тренажёр', 'Догони' in pg.inner_text('#panel h2 >> nth=0') and not pg.is_visible('#home'))
    pg.click('#all'); pg.wait_for_timeout(700); check('кнопка возвращает к выбору', pg.is_visible('#home'))

    for k in ('1_log_fresh', '2_log_salty'):
        go(k); pg.click('.opt >> nth=0'); pg.click('button.main'); pg.wait_for_selector('.chip', timeout=20000); pg.wait_for_timeout(500); shot(k + '_ready')
        check(k + ': пласты скрыты до решения', pg.evaluate("Object.keys(__t.cur.st.tested).length===0&&!__t.cur.st.done"))
        n = pg.locator('.chip').count()
        for i in range(n):
            pg.click(f'.chip >> nth={i}'); pg.wait_for_timeout(120)
            t = pg.locator('button.alt:visible')
            if t.count() and 'Испытать' in t.first.inner_text(): t.first.click(); pg.wait_for_timeout(120)
        check(k + ': испытаний ровно 3', pg.evaluate("Object.keys(__t.cur.st.tested).length") == 3)
        pg.click('button:has-text("Завершить и вскрыть")'); pg.wait_for_timeout(2600); shot(k + '_end')
        check(k + ': есть итог', pg.locator('text=нефтяных пластов найдено').count() == 1)
        check(k + ': перенос отвечается', (pg.click('text=Проверьте перенос >> xpath=.. >> .opt >> nth=1'), pg.locator('.opt.ok').count())[1] >= 1)

    check('подсказка дошла до конца', 'Шаг 5 из 5' in pg.inner_text('#hint'))
    go('3_pressure'); pg.click('.opt >> nth=1'); pg.click('button:has-text("Пустить скважину")'); pg.wait_for_timeout(5000); shot('pressure_run')
    pg.wait_for_selector('text=дошло по расчёту', timeout=20000); pg.wait_for_timeout(800); shot('pressure_end')
    a = pg.evaluate("__t.cur.p.Q"); pg.locator('text=Дебит, м³/сут').locator('xpath=ancestor::label').locator('input').fill('120'); pg.wait_for_timeout(300)
    check('давление: ползунок меняет модель', pg.evaluate("__t.cur.p.Q") == 120 and a != 120)

    for k in ('4_reef_dome', '5_reef_atoll'):
        go(k); pg.click('.opt >> nth=0'); pg.wait_for_selector('#panel >> text=Нажмите на риф', timeout=20000); pg.wait_for_timeout(700)
        bx = pg.locator('#view canvas').first.bounding_box()
        for dx, dy in ((0, .02), (-.16, .06), (.15, .06), (-.08, .16), (.1, .17), (0, .2), (0, -.02)):
            if pg.evaluate("__t.cur.st.wells.length") >= 3: break
            pg.mouse.click(bx['x'] + bx['width'] * (.5 + dx), bx['y'] + bx['height'] * (.45 + dy)); pg.wait_for_timeout(250)
        check(k + ': три скважины по клику', pg.evaluate("__t.cur.st.wells.length") == 3)
        pg.wait_for_timeout(1800); shot(k + '_wells')
        pg.click('button:has-text("Разрезать риф")'); pg.wait_for_timeout(2800); shot(k + '_end')
        check(k + ': есть итог', pg.locator('text=от лучшего плана').count() == 1)

    for i in range(8): pg.click('#next'); pg.wait_for_timeout(250)
    check('новый случай строится', pg.evaluate("__t.cur.cs.seed") != 11)
    go('5_reef_atoll'); pg.click('#edit'); j = pg.input_value('#json')
    pg.fill('#json', j.replace('4.5', '20').replace('9.5', '30')); pg.click('#apply'); pg.wait_for_timeout(400); shot('spec_bad')
    check('неверная физика отвергнута', 'Сцена не собрана' in pg.inner_text('#msg'))
    pg.fill('#json', j.replace('"H": [\n   320', '"H": [\n   250')); pg.click('#apply'); pg.wait_for_timeout(600)
    check('верная правка собрана', not pg.evaluate("document.querySelector('#spec').open"))
    check('нет горизонтальной прокрутки', not pg.evaluate("document.documentElement.scrollWidth>innerWidth"))
    b.close()
print('прошло:', len(ok)); print('\n'.join('ОШИБКА ' + e for e in errs) or 'ошибок нет'); sys.exit(bool(errs))
