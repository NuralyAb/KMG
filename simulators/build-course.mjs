// Проигрыватель для курса и сцены глав. Результат кладётся в engine/ и work/, поэтому команде `glava course` Node не нужен.
import fs from 'node:fs';
import path from 'node:path';
import { build } from 'esbuild';
import { resolve } from './src/extends.js';
import { validate } from './src/validate.js';

const ROOT = path.resolve(import.meta.dirname, '..'), PLAYER = path.join(ROOT, 'engine', 'glava', 'course', 'assets', 'sim');
const raw = Object.fromEntries(fs.readdirSync('scenes').filter(f => f.endsWith('.json')).map(f => [f.slice(0, -5), JSON.parse(fs.readFileSync('scenes/' + f, 'utf8'))]));
const used = JSON.parse(fs.readFileSync('course.json', 'utf8'));

for (const [chapter, steps] of Object.entries(used)) {
  const work = path.join(ROOT, 'work', chapter), dir = path.join(work, 'simulations');
  if (!fs.existsSync(path.join(work, 'layer.json'))) { console.log('пропуск, слоя нет:', chapter); continue; }
  fs.mkdirSync(dir, { recursive: true });
  // сцены агента не трогаем, обновляем только свои
  const cf = path.join(work, 'simulations.json'), out = {}, old = fs.existsSync(cf) ? JSON.parse(fs.readFileSync(cf, 'utf8')).steps : {};
  for (const [node, list] of Object.entries(steps)) out[node] = list.map(({ scene, as, claims }) => {
    const s = resolve(raw, scene), e = validate(s, [s.seed, 1, 2, 3, 4, 5]);
    if (e.length) throw new Error(`${scene}: ${e.join('; ')}`);
    fs.writeFileSync(path.join(dir, as + '.json'), JSON.stringify(s, null, 1) + '\n');
    if (fs.existsSync(`tex/thumb_${scene}.webp`)) fs.copyFileSync(`tex/thumb_${scene}.webp`, path.join(dir, as + '.webp'));
    return { scene: as, claims };
  });
  for (const [node, list] of Object.entries(old)) { const a = list.filter(x => x.origin === 'agent'); if (a.length) out[node] = [...(out[node] || []), ...a]; }
  fs.writeFileSync(cf, JSON.stringify({ chapter, steps: out }, null, 1) + '\n');
  console.log('✓', chapter, Object.values(out).flat().length, 'сцен');
}

// Фактуры отдельно от кода: файлы меньше 5 МБ, и правка кода не меняет их в git.
const files = fs.readdirSync('tex').filter(f => f.endsWith('.webp') && !f.startsWith('thumb_'));
const b64 = f => fs.readFileSync(f).toString('base64');
fs.rmSync(PLAYER, { recursive: true, force: true }); fs.mkdirSync(PLAYER, { recursive: true });
fs.writeFileSync(path.join(PLAYER, 'textures.js'), 'globalThis.SIM_FILES=' + JSON.stringify(Object.fromEntries(files.map(f => [f, 'data:image/webp;base64,' + b64('tex/' + f)]))) + ';\n');
fs.writeFileSync(path.join(PLAYER, 'sky.js'), `globalThis.SIM_FILES["sky.hdr"]="${b64('assets/sky.hdr')}";\n`);
await build({
  entryPoints: ['src/main.js'], bundle: true, minify: true, format: 'iife', target: 'es2022', charset: 'utf8', outfile: path.join(PLAYER, 'player.js'), legalComments: 'eof',
  plugins: [{ name: 'files', setup(b) {
    b.onResolve({ filter: /^scenes$/ }, () => ({ path: 'scenes', namespace: 's' }));
    b.onLoad({ filter: /.*/, namespace: 's' }, () => ({ contents: 'export default globalThis.SIM_SCENES || {scenes:{},thumbs:{}}', loader: 'js' }));
    b.onResolve({ filter: /\.(webp|hdr)$/ }, a => ({ path: path.basename(a.path), namespace: 'f' }));
    b.onLoad({ filter: /.*/, namespace: 'f' }, a => ({ loader: 'js', contents: a.path.endsWith('.hdr') ? `export default Uint8Array.from(atob(globalThis.SIM_FILES[${JSON.stringify(a.path)}]),c=>c.charCodeAt(0))` : `export default globalThis.SIM_FILES[${JSON.stringify(a.path)}]||''` }));
  } }],
});
const tags = ['textures.js', 'sky.js', '../../simulations.js', 'player.js'].map(s => `<script src="${s}"></script>`).join('\n');
fs.writeFileSync(path.join(PLAYER, 'player.html'), fs.readFileSync('src/index.html', 'utf8').replace('<body>', '<body class="embed">').replace('<!--BUNDLE-->', tags));
for (const f of fs.readdirSync(PLAYER)) console.log(f, (fs.statSync(path.join(PLAYER, f)).size / 1e6).toFixed(2) + ' МБ');
