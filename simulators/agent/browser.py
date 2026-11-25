# Глаза и руки агента: кадр сцены и полное прохождение. Последняя строка вывода — JSON.
import sys, json, pathlib, time
from playwright.sync_api import sync_playwright
sys.stdout.reconfigure(encoding='utf-8')
mode, job, opt = sys.argv[1], pathlib.Path(sys.argv[2]), json.loads(sys.argv[3])
root = pathlib.Path(__file__).resolve().parent.parent
url = (root / 'dist' / 'тренажёры.html').as_uri()
spec = json.loads((job / 'sim.json').read_text('utf8'))
issues, res = [], {}

PROBE = """()=>{const v=document.querySelector('#view').getBoundingClientRect(),L=[...document.querySelectorAll('.lbl')].filter(e=>e.style.display!=='none'&&e.textContent).map(e=>[e.textContent,e.getBoundingClientRect()]);
const h=document.querySelector('#hint').getBoundingClientRect(),out=[];
for(const [t,r] of L){if(r.right<v.left||r.left>v.right||r.bottom<v.top||r.top>v.bottom)continue;if(r.left<v.left-2||r.right>v.right+2)out.push('подпись обрезана: '+t);if(r.top<h.bottom&&r.bottom>h.top&&r.left<h.right&&r.right>h.left)out.push('подпись под подсказкой: '+t);}
for(let i=0;i<L.length;i++)for(let j=i+1;j<L.length;j++){const a=L[i][1],b=L[j][1],w=Math.min(a.right,b.right)-Math.max(a.left,b.left),q=Math.min(a.bottom,b.bottom)-Math.max(a.top,b.top);if(w>6&&q>4&&a.width&&b.width)out.push('подписи накладываются: '+L[i][0]+' / '+L[j][0]);}
if(document.documentElement.scrollWidth>innerWidth)out.push('горизонтальная прокрутка');return [...new Set(out)]}"""
PIX = """()=>{const s=__t.stage,c=s.renderer.domElement,k=document.createElement('canvas');k.width=64;k.height=48;s.composer.render();const g=k.getContext('2d');g.drawImage(c,0,0,64,48);const d=g.getImageData(0,0,64,48).data;let m=0,m2=0,n=64*48;for(let i=0;i<d.length;i+=4){const l=.3*d[i]+.6*d[i+1]+.1*d[i+2];m+=l;m2+=l*l}m/=n;return [m,Math.sqrt(m2/n-m*m)]}"""

def open_page(b, mobile=False):
    pg = b.new_page(viewport={'width': 390, 'height': 844} if mobile else {'width': 1280, 'height': 800})
    pg.on('pageerror', lambda e: issues.append('ошибка JS: ' + str(e)[:200]))
    pg.on('console', lambda m: issues.append('консоль: ' + m.text[:200]) if m.type == 'error' else None)
    pg.on('request', lambda r: issues.append('сеть: ' + r.url[:80]) if r.url.startswith('http') else None)
    pg.goto(url + '#3_pressure'); pg.wait_for_timeout(900)
    err = pg.evaluate("s=>{const e=__t.load(s,s.seed);document.querySelector('#home').hidden=true;return e}", spec)
    if err: issues.extend(err)
    pg.wait_for_timeout(700)
    return pg

# Выполнить текущий шаг так, как это сделал бы ученик
def act(pg, quick=False):
    inf = pg.evaluate('__t.cur.info()'); k = inf['kind']
    if inf['done'] or k is None: return False
    if k in ('predict', 'choose'): pg.locator('.opt:not(:disabled)').first.click()
    elif k == 'guess': pg.locator('button.next').last.click()
    elif k == 'pick':
        s = spec['steps'][inf['step']]; X, _, Z = spec['world']['size']; n = 0
        for i in range(60):
            if pg.evaluate('__t.cur.st.picks.length') >= s['n']: break
            fx, fz = (((i * 37) % 17) / 17 - .5) * .8, (((i * 23) % 13) / 13 - .5) * .8
            pg.evaluate('([x,z])=>__t.cur.st.pick(x,z)', [fx * X, fz * Z])
        pg.wait_for_timeout(300); b = pg.locator('button.next')
        if not b.count(): issues.append('pick: после выбора нет кнопки продолжения'); return False
        b.last.click()
    else:
        b = pg.locator('button.next').last
        if b.is_disabled():
            if spec.get('time'):
                for q in range(1, 41):
                    pg.evaluate('k=>__t.cur.setK(k)', q / 40); pg.wait_for_timeout(40)
                    if not b.is_disabled(): break
            if b.is_disabled():
                for s in pg.locator('.sl input:not(:disabled)').all():
                    for p in (0, .5, 1):
                        mn, mx = float(s.get_attribute('min')), float(s.get_attribute('max')); s.fill(str(mn + (mx - mn) * p)); pg.wait_for_timeout(80)
                        if not b.is_disabled(): break
            if b.is_disabled(): issues.append(f"шаг {inf['step']}: условие until недостижимо"); return False
        b.click()
    pg.wait_for_timeout(150 if quick else 500)
    return True

with sync_playwright() as p:
    b = p.chromium.launch(channel='chrome', args=['--enable-gpu', '--ignore-gpu-blocklist'])
    if mode == 'look':
        pg = open_page(b, opt.get('mobile'))
        while pg.evaluate('__t.cur.info().step') < opt['step']:
            if not act(pg, True): break
        if opt.get('reveal'): pg.evaluate('__t.cur.M.E.revealed=1;__t.cur.refresh()')
        if opt.get('t') is not None: pg.evaluate('k=>__t.cur.setK(k)', opt['t'])
        pg.wait_for_timeout(2200)
        if opt.get('view'): v = opt['view']; pg.evaluate('v=>__t.cur.look({yaw:v[0],pitch:v[1],zoom:v[2]||1},0)', v); pg.wait_for_timeout(700)
        issues += pg.evaluate(PROBE); m, sd = pg.evaluate(PIX)
        if m < 18 or sd < 7: issues.append('кадр почти пустой или чёрный')
        n = len(list((job / 'shots').glob('*.png'))); f = job / 'shots' / f"{n:02d}_s{opt['step']}{'_m' if opt.get('mobile') else ''}.png"; pg.screenshot(path=str(f))
        res = {'shot': str(f), 'state': pg.evaluate('__t.cur.info()'), 'brightness': round(m), 'contrast': round(sd)}
    else:
        for mobile in (False, True):
            pg = open_page(b, mobile); tag = 'телефон' if mobile else 'компьютер'; kinds = []
            for _ in range(30):
                kinds.append(pg.evaluate('__t.cur.info().kind'))
                if not act(pg): break
                issues += [f'{tag}, шаг {len(kinds)}: {x}' for x in pg.evaluate(PROBE)]
                m, sd = pg.evaluate(PIX)
                if m < 18 or sd < 7: issues.append(f'{tag}, шаг {len(kinds)}: кадр пустой')
            if not pg.evaluate('__t.cur.info().done'): issues.append(tag + ': до конца не дошли, остановка на ' + str(kinds[-1:]))
            fps = pg.evaluate("()=>new Promise(r=>{let n=0,t0=performance.now();(function f(){n++;performance.now()-t0<1200?requestAnimationFrame(f):r(Math.round(n/1.2))})()})")
            if fps < 24: issues.append(f'{tag}: {fps} кадров в секунду')
            t0 = time.time()
            for q in (1, 2, 3):  # другие случаи строятся без ошибок
                e = pg.evaluate('([s,q])=>__t.load(s,q)', [spec, 100 + q]); pg.wait_for_timeout(250)
                if e: issues.extend(e)
            if not mobile:
                pg2 = open_page(b); pg2.evaluate('__t.cur.setK(.5)'); pg2.wait_for_timeout(900); pg2.add_style_tag(content='.lbl,.badge,#hint{visibility:hidden!important}')
                pg2.screenshot(path=str(job / 'thumb.png'), clip={'x': 40, 'y': 90, 'width': 780, 'height': 520}); pg2.close()
                from PIL import Image
                Image.open(job / 'thumb.png').convert('RGB').resize((480, 320)).save(job / 'thumb.webp', quality=80); res['thumb'] = str(job / 'thumb.webp')
            res[tag] = {'шаги': kinds, 'fps': fps}; pg.close()
        hard = [i for i in set(issues) if not any(w in i for w in ('накладываются', 'обрезана', 'под подсказкой'))]
        res['ok'] = not hard
    b.close()
res['issues'] = sorted(set(issues))
print(json.dumps(res, ensure_ascii=False))
