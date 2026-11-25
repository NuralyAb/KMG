// Инструменты агента. node agent/tool.mjs <задание> <команда> [аргументы]
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { spawnSync } from 'node:child_process';
import { lint } from '../src/models/compose.js';
import { Model } from '../src/models/compose.js';
import { unit } from '../src/expr.js';

const ROOT = path.resolve(import.meta.dirname, '..'), [job, cmd, ...rest] = process.argv.slice(2);
if (!/^[\w.-]+$/.test(job || '') || !cmd) { console.log('node agent/tool.mjs <задание> job|page|find|catalog|check|eval|look|play|need|finish'); process.exit(2); }
const DIR = path.join(ROOT, 'jobs', job), J = JSON.parse(fs.readFileSync(path.join(DIR, 'job.json'), 'utf8')), SIM = path.join(DIR, 'sim.json');
const opt = (n, d) => { const i = rest.indexOf('--' + n); return i < 0 ? d : rest[i + 1] === undefined || rest[i + 1].startsWith('--') ? true : rest[i + 1]; };
const log = o => fs.appendFileSync(path.join(DIR, 'log.jsonl'), JSON.stringify({ at: new Date().toISOString(), cmd, ...o }) + '\n');
const md = fs.readFileSync(J.book, 'utf8'), parts = md.split(/<!--\s*page\s+(\d+)\s*-->/), pages = {};
for (let i = 1; i < parts.length; i += 2) pages[+parts[i]] = parts[i + 1];
const norm = s => s.toLowerCase().replace(/ё/g, 'е').replace(/\s+/g, '').replace(/[*_`]/g, '');
const inJob = n => n >= J.pages[0] && n <= J.pages[1];
const load = () => JSON.parse(fs.readFileSync(SIM, 'utf8'));
const hash = () => crypto.createHash('sha1').update(fs.readFileSync(SIM)).digest('hex').slice(0, 12);

function check() {
  let s; try { s = load(); } catch (e) { return { E: ['sim.json не читается: ' + e.message], W: [] }; }
  if (s.template !== 'compose') return { E: ['template должен быть "compose"'], W: [] };
  const { E, W } = lint(s, [1, 2, 3, 4, 5, s.seed]);
  // цитаты дословно на указанной странице, страница в пределах задания
  for (const c of s.claims || []) {
    if (!c.id || !c.text || !c.quote || !c.page) { E.push(`claim ${c.id}: нужны id, text, quote, page`); continue; }
    if (!pages[c.page]) { E.push(`claim ${c.id}: страницы ${c.page} нет`); continue; }
    if (c.quote.length < 12) E.push(`claim ${c.id}: цитата слишком короткая`);
    if (!norm(pages[c.page]).includes(norm(c.quote))) { const at = Object.keys(pages).find(p => norm(pages[p]).includes(norm(c.quote))); E.push(`claim ${c.id}: цитаты нет на стр. ${c.page}${at ? ` (она на стр. ${at})` : ' — приведите дословно'}`); }
    else if (/FORMAT \d|KEYWORDS:/.test(pages[c.page])) { const before = pages[c.page]; const k = norm(before).indexOf(norm(c.quote)), f = norm(before).search(/format\d/), e = norm(before).indexOf('keywords:'); if (f >= 0 && k > f && (e < 0 || k < e)) E.push(`claim ${c.id}: это описание рисунка моделью, а не слова автора`); }
    if (!inJob(c.page)) W.push(`claim ${c.id}: стр. ${c.page} вне задания ${J.pages.join('–')} (допустимо только для предпосылки)`);
  }
  if (!(s.claims || []).some(c => inJob(c.page))) E.push('ни одного утверждения со страниц задания');
  // тексты: без разметки
  const bad = []; (function walk(o, k) { if (typeof o === 'string') { if (['text', 'q', 'why', 'title', 'intro', 'goal', 'subtitle', 'label', 'name', 'data_bridge', 'breaks_where', 'hint', 'why_3d', 'name_ru'].includes(k) && /<[a-z!/]/i.test(o)) bad.push(k); } else if (o && typeof o === 'object') for (const q in o) walk(o[q], Array.isArray(o) ? k : q); })(s, ''); if (bad.length) E.push('HTML в текстах запрещён: ' + bad.join(', '));
  return { E, W };
}
function browser(mode, extra) {
  if (!fs.existsSync(path.join(ROOT, 'dist', 'тренажёры.html'))) return { error: 'сначала npm run build' };
  fs.mkdirSync(path.join(DIR, 'shots'), { recursive: true });
  const r = spawnSync('python', ['-I', path.join(ROOT, 'agent', 'browser.py'), mode, DIR, JSON.stringify(extra)], { encoding: 'utf8', timeout: 170000, env: { ...process.env, PYTHONIOENCODING: 'utf8' } });
  const last = (r.stdout || '').trim().split('\n').pop(); try { return JSON.parse(last); } catch { return { error: (r.stderr || r.stdout || 'нет ответа').slice(-600) }; }
}
const out = x => console.log(typeof x === 'string' ? x : JSON.stringify(x, null, 1));

if (cmd === 'job') out({ ...J, hint: 'Пишите в ' + SIM });
else if (cmd === 'page') { const a = +rest[0], b = +(rest[1] || a); for (let p = a; p <= Math.min(b, a + 5); p++) out(`=== стр. ${p}${inJob(p) ? '' : ' (вне задания)'}\n` + (pages[p] || 'нет').trim()); }
else if (cmd === 'find') { const q = norm(rest.join(' ')); let n = 0; for (const p in pages) for (const l of pages[p].split('\n')) if (norm(l).includes(q) && n++ < 25) out(`стр. ${p}${inJob(+p) ? '' : ' (вне задания)'}: ${l.trim().slice(0, 400)}`); if (!n) out('не найдено'); }
else if (cmd === 'catalog') out(fs.readFileSync(path.join(ROOT, 'agent', 'CATALOG.md'), 'utf8'));
else if (cmd === 'check') { const { E, W } = check(); log({ errors: E.length, warnings: W.length, first: E.slice(0, 6) }); out(E.length ? 'ИСПРАВИТЬ:\n- ' + E.join('\n- ') : 'ОК: ошибок нет'); if (W.length) out('Замечания:\n- ' + W.join('\n- ')); }
else if (cmd === 'eval') { // eval "front; drop(300,t)" --t 0,1,10 --set k=0.2 --unit m --seed 3
  const s = load(), m = new Model(s, +(opt('seed', s.seed))), ex = rest[0].split(';').map(x => x.trim()).filter(Boolean), u = unit(opt('unit', '1') === true ? '1' : opt('unit', '1')).k, ts = opt('t') ? String(opt('t')).split(',').map(Number) : [m.E.t / m.tu.k], set = opt('set') ? Object.fromEntries(String(opt('set')).split(',').map(q => { const [a, b] = q.split('='); return [a, +b * (m.U[a] ? m.U[a].k : 1)]; })) : {};
  out('t\t' + ex.join('\t')); for (const t of ts) out(t + '\t' + ex.map(e => { try { return m.at({ ...set, t: t * m.tu.k }, () => m.fn(e)() / u).toPrecision(5); } catch (x) { return x.message; } }).join('\t')); }
else if (cmd === 'look') { const { E } = check(); if (E.length) { out('Сначала check: ' + E.length + ' ошибок, первая: ' + E[0]); process.exit(1); } const r = browser('look', { step: +opt('step', 0), t: opt('t') !== undefined ? +opt('t') : null, view: opt('view') ? String(opt('view')).split(',').map(Number) : null, mobile: !!opt('mobile'), reveal: !!opt('reveal') }); log({ shot: r.shot, issues: r.issues }); out(r); if (r.shot) out('Откройте картинку инструментом чтения файлов и посмотрите на неё.'); }
else if (cmd === 'play') { const { E } = check(); if (E.length) { out('Сначала check: ' + E[0]); process.exit(1); } const r = browser('play', {}); r.hash = hash(); fs.writeFileSync(path.join(DIR, 'play.json'), JSON.stringify(r)); log({ ok: r.ok, issues: r.issues }); out(r); }
else if (cmd === 'inspect') { const { E } = check(); if (E.length) { out('Сначала check: ' + E[0]); process.exit(1); } const n = load().steps.length - 1, r = browser('inspect', { frames: [{ step: Math.min(1, n), t: .5 }, { step: n, reveal: true, t: 1 }, { step: n, reveal: true, t: 1, view: [-65, 16, 1] }, { step: n, reveal: true, t: 1, mobile: true }] }); r.hash = hash(); fs.writeFileSync(path.join(DIR, 'play.json'), JSON.stringify(r)); log({ shot: r.shot, frames: r.frames, ok: r.ok, issues: r.issues }); out(r); }
else if (cmd === 'need') { log({ need: rest.join(' ') }); out('Записано в отчёт о покрытии: ' + rest.join(' ')); }
else if (cmd === 'finish') {
  const { E } = check(); if (E.length) { out('Нельзя: ' + E.join('; ')); process.exit(1); }
  let p; try { p = JSON.parse(fs.readFileSync(path.join(DIR, 'play.json'), 'utf8')); } catch { } if (!p || !p.ok || p.hash !== hash()) { out('Нельзя: нужен успешный play на этой же версии sim.json'); process.exit(1); }
  const looks = fs.readFileSync(path.join(DIR, 'log.jsonl'), 'utf8').split('\n').filter(Boolean).map(JSON.parse).reduce((a, x) => a + (x.cmd === 'look' && x.shot ? 1 : x.cmd === 'inspect' ? x.frames || 0 : 0), 0); if (looks < 3) { out(`Нельзя: посмотрите сцену хотя бы 3 раза (сейчас ${looks})`); process.exit(1); }
  const s = load(); fs.mkdirSync(path.join(ROOT, 'sims'), { recursive: true }); s.source_book = path.basename(J.book); fs.writeFileSync(path.join(ROOT, 'sims', job + '.json'), JSON.stringify(s, null, 1)); if (p.thumb) fs.copyFileSync(p.thumb, path.join(ROOT, 'sims', job + '.webp')); fs.writeFileSync(path.join(DIR, 'done.json'), JSON.stringify({ at: new Date().toISOString(), hash: hash() })); log({ done: true }); out('Готово: sims/' + job + '.json');
} else out('нет такой команды');
