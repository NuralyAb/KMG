# Симулятор внутри собранного курса: открыть с диска без сети, запустить на месте, пройти, закрыть. python course_play.py <папка курса> <номер шага> [папка кадров]
import pathlib
import sys
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding='utf-8')
course, step = pathlib.Path(sys.argv[1]).resolve(), sys.argv[2]
shots = pathlib.Path(sys.argv[3]) if len(sys.argv) > 3 else None
bad, ok = [], []


def check(name, good):
    (ok if good else bad).append(name)


with sync_playwright() as p:
    b = p.chromium.launch(channel='chrome', args=['--enable-gpu', '--ignore-gpu-blocklist'])
    for tag, size in (('d', {'width': 1280, 'height': 800}), ('m', {'width': 390, 'height': 844})):
        ctx = b.new_context(viewport=size, offline=True)
        pg = ctx.new_page()
        pg.on('pageerror', lambda e: bad.append('JS: ' + str(e)[:200]))
        pg.on('console', lambda m: bad.append('консоль: ' + m.text[:200]) if m.type == 'error' else None)
        pg.on('request', lambda r: bad.append('сеть: ' + r.url[:90]) if r.url.startswith('http') else None)
        pg.goto((course / 'index.html').as_uri() + '#/')
        pg.evaluate('n=>{location.hash="#/step/"+n}', step)
        pills = pg.locator('.pills button:has-text("Симулятор")')
        pg.wait_for_selector('.pills, .sim-box')
        if pills.count():
            pills.first.click()  # первым слайдом стоит разбор
        pg.wait_for_selector('.sim-box')
        check(tag + ': две сцены на выбор', pg.locator('.sim-tab').count() == 2)
        check(tag + ': сцена не грузится заранее', pg.locator('iframe').count() == 0)
        check(tag + ': нет горизонтальной прокрутки', not pg.evaluate('document.documentElement.scrollWidth>innerWidth'))
        pg.locator('.sim-box').first.scroll_into_view_if_needed()
        pg.wait_for_timeout(400)
        if shots:
            pg.screenshot(path=str(shots / f'{tag}_course.png'))
        pg.locator('.sim-go').click()
        pg.wait_for_selector('.sim-box[data-state="live"]', timeout=30000)
        check(tag + ': сцена на месте, новой вкладки нет', len(ctx.pages) == 1 and pg.locator('dialog').count() == 0)
        f = pg.frame_locator('.sim-box iframe')
        f.locator('.opt').first.click(timeout=20000)
        f.locator('button.main').first.click()
        f.locator('.chip').first.wait_for(timeout=25000)
        n = f.locator('.chip').count()
        for i in range(n):
            f.locator('.chip').nth(i).click()
            t = f.locator('button.alt:has-text("Испытать")')
            if t.count():
                t.first.click()
            pg.wait_for_timeout(120)
        f.locator('button:has-text("Завершить и вскрыть")').click()
        f.locator('text=нефтяных пластов найдено').wait_for(timeout=8000)
        check(tag + ': пройден до итога', True)
        f.locator('.hon summary').click()
        check(tag + ': источники из слоя', f.locator('.hon').inner_text().find('αСП = 0,7') > 0)
        check(tag + ': шапка проигрывателя спрятана', not f.locator('header').is_visible())
        pg.wait_for_timeout(1500)
        if shots:
            pg.screenshot(path=str(shots / f'{tag}_sim.png'))
        pg.get_by_role('button', name='Закрыть симулятор').click()
        check(tag + ': закрыт и выгружен', pg.locator('iframe').count() == 0 and pg.locator('.sim-go').is_visible())
        pg.locator('.sim-tab').nth(1).click()
        pg.locator('.sim-go').click()
        f.locator('#panel h2:has-text("солёный раствор")').wait_for(timeout=15000)
        pg.go_back()
        pg.wait_for_timeout(600)
        check(tag + ': «назад» выгружает сцену', pg.locator('iframe').count() == 0)
        ctx.close()
    b.close()
print('прошло:', len(ok))
print('\n'.join('ОШИБКА ' + x for x in bad) or 'ошибок нет')
sys.exit(bool(bad))
