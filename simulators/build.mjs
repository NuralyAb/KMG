// Сборка: сцены + движок + фактуры → один HTML, открывается без сервера и интернета.
import fs from 'node:fs';
import { build } from 'esbuild';
import { resolve } from './src/extends.js';
import { validate } from './src/validate.js';

const raw = Object.fromEntries(fs.readdirSync('scenes').filter(f => f.endsWith('.json')).sort().map(f => [f.slice(0, -5), JSON.parse(fs.readFileSync('scenes/' + f, 'utf8'))]));
const thumbs = {};
if (fs.existsSync('sims')) for (const f of fs.readdirSync('sims')) { const n = f.replace(/\.\w+$/, ''); if (f.endsWith('.json')) raw[n] = JSON.parse(fs.readFileSync('sims/' + f, 'utf8')); if (f.endsWith('.webp')) thumbs[n] = 'data:image/webp;base64,' + fs.readFileSync('sims/' + f).toString('base64'); }
let bad = 0;
for (const k in raw) {
  const s = resolve(raw, k), e = validate(s, [s.seed, 1, 2, 3, 4, 5]);
  console.log(e.length ? '✗' : '✓', k, e.join('; ')); bad += e.length;
}
if (bad) { console.error('Сборка остановлена: сцены нарушают физику.'); process.exit(1); }
const r = await build({
  entryPoints: ['src/main.js'], bundle: true, minify: true, write: false, format: 'iife', target: 'es2022', charset: 'utf8',
  loader: { '.webp': 'dataurl', '.hdr': 'binary' },
  plugins: [{ name: 'scenes', setup(b) { b.onResolve({ filter: /^scenes$/ }, () => ({ path: 'scenes', namespace: 's' })); b.onLoad({ filter: /.*/, namespace: 's' }, () => ({ contents: JSON.stringify({ scenes: raw, thumbs }), loader: 'json' })); } }],
});
const js = r.outputFiles[0].text.replace(/<\/script/gi, '<\\/script');
fs.mkdirSync('dist', { recursive: true });
const html = fs.readFileSync('src/index.html', 'utf8').split('<!--BUNDLE-->').join('<script>' + js + '</script>');
fs.writeFileSync('dist/тренажёры.html', html);
console.log('dist/тренажёры.html', (html.length / 1e6).toFixed(1) + ' МБ');
