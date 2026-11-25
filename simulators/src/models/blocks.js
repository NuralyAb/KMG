// Крупные блоки сцены: короткая запись → обычные объекты, функции и честные оговорки. В готовой сцене блоков уже нет.
const FIELDS = { layers: [], stack: ['beds'], well: [], log: ['value', 'min', 'max', 'color'], invasion: ['radius', 'from', 'to'], inflow: ['from', 'to', 'color'], contact: ['y'], front: ['radius'], bore: ['radius'], pores: ['water'], depth: ['from', 'to'] };
export const BLOCKS = Object.keys(FIELDS);
const FLUID = ['oil', 'gas', 'water', 'filtrate'];
const num = (v, d, w) => { const n = v === undefined ? d : +v; if (!Number.isFinite(n)) throw new Error(`блок ${w}: нужно число, дано «${v}»`); return n; };
const ru = n => String(n).replace('.', ',');
const shape = (b, top, w) => { // кровля главного тела
  const k = num(b.relief, 7, w), kind = b.shape || 'dome';
  if (kind === 'dome') return `${-top - k}+${k}*exp(-((x/blk_rx)^2+(z/blk_rz)^2))`;
  if (kind === 'flat') return `${-top}`;
  if (kind === 'tilt') return `${-top - k / 2}-${k / 2}*x/blk_hx`;
  if (kind === 'fault') return `${-top}-if(x>0,${k},0)`;
  throw new Error(`блок ${w}: shape — dome, flat, tilt, fault`);
};

export function expand(s) {
  if (!s || !s.blocks) return s || {};
  if (!Array.isArray(s.blocks)) throw new Error('blocks — массив');
  const out = { world: s.world, objects: [], functions: {}, params: {}, assumptions: [...(s.assumptions || [])], exaggerations: [...(s.exaggerations || [])] }, say = t => out.assumptions.includes(t) || out.assumptions.push(t), big = t => out.exaggerations.includes(t) || out.exaggerations.push(t), P = (n, v) => (out.params[n] = { value: v, unit: 'm', from: 'assumption' });
  for (const b of s.blocks) { const f = FIELDS[b && b.block]; if (!f) throw new Error(`нет блока «${b && b.block}» (есть: ${BLOCKS.join(', ')})`); for (const k of f) if (b[k] === undefined) throw new Error(`блок ${b.block}: нет «${k}»`); }
  const moving = s.blocks.some(b => (b.zones || []).some(z => z.to !== undefined && !Number.isFinite(+z.to)));
  if (moving) for (const b of s.blocks) if (b.block === 'well') for (const [t, y] of b.marks || []) if (Number.isFinite(+y) && !/^(верх|низ|середина)/i.test(t)) throw new Error(`блок well: метка «${t}» на постоянной глубине ${y}, а границы зон меняются от случая к случаю; глубина метки — формула модели`);
  const ground = s.blocks.filter(b => ['layers', 'stack'].includes(b.block)); if (ground.length > 1) throw new Error('блок layers или stack — один на сцену');
  const g = ground[0], own = s.world && s.world.size;
  // размеры кадра: толща над глубоким пластом срезается, ширина растёт вместе с высотой
  const L = g && g.block === 'layers', gTop = L ? num(g.depth, 4, 'layers') : 0, gTh = L ? num(g.thick, 9, 'layers') : 0, gRel = L && g.shape !== 'flat' ? num(g.relief, 7, 'layers') : 0, cov = L ? (gTop > Math.max(8, gTh * .6) ? Math.min(12, Math.max(3, gTh * .4)) : gTop) : 0, gy = L ? -(gTop - cov) : 0;
  const tall = L ? cov + gRel + gTh + Math.max(8, gTh * .25) + 1 : g ? (g.beds || []).reduce((a, b) => a + (+b.thick || 0), 0) * 1.25 + 10 : 40, X = own ? s.world.size[0] : g ? Math.max(80, Math.round(1.9 * tall / 5) * 5) : 80, Z = own ? s.world.size[2] : Math.round(X * .65), k1 = g ? X / 80 : 1, veW = s.world && s.world.ve ? s.world.ve : g ? Math.max(.4, Math.round(.45 * X / tall * 10) / 10) : 1, kv = g ? k1 * 1.6 / veW : 1;
  if (L && gy < 0) out.assumptions.push(`Толща над пластом до глубины ${ru(+(-gy).toFixed(1))} м срезана`);
  const over = s.blocks.filter(b => b.block === 'invasion').map(b => ({ when: `abs(x-(${b.x || 0}))<${b.radius} && y<${b.from} && y>${b.to}${b.show ? ` && (${b.show})` : ''}`, color: b.color || 'filtrate', name: b.name || 'Зона проникновения' }));
  const lines = s.blocks.filter(b => b.block === 'contact').map(b => ({ when: `abs(y-(${b.y}))<${(.2 * kv).toFixed(2)}${b.show ? ` && (${b.show})` : ''}`, color: b.color || 'text', name: b.name || String(b.label || 'Контакт').replace(/\s*[=:—-]?\s*\{[^}]*\}.*$/, '') || 'Контакт' }));
  // ствол крупно: радиус раствора и корка по глубине рисуются прямо на срезе
  const bore = s.blocks.filter(b => b.block === 'bore').flatMap(b => { const sh = b.show ? ` && (${b.show})` : '', bx = `abs(x-(${b.x || 0}))`, rg = `${b.from !== undefined ? ` && y<${b.from}` : ''}${b.to !== undefined ? ` && y>${b.to}` : ''}`; return [{ when: `${bx}<(${b.radius})${rg}${sh}`, color: 'mud', name: b.name || 'Ствол с раствором' }, ...(b.cake !== undefined ? [{ when: `${bx}<(${b.radius})+(${b.cake})${rg}${sh}`, color: 'text', name: 'Глинистая корка' }] : [])]; });
  if (bore.length) { if (!ground.length) throw new Error('блок bore: нужен layers или stack'); big('Ствол скважины нарисован во много раз шире настоящего'); }
  let low = -20;
  if (g) {
    P('blk_rx', X * .33); P('blk_rz', Z * .35); P('blk_rr', 14 * k1); P('blk_hx', X / 2); out.functions['blk_ground(x,z)'] = `${gy}+${(.25 * kv).toFixed(2)}*fbm(x/blk_rr,z/blk_rr,2,3)`;
    say('Форма пластов, толщины и рельеф условные; толща над пластом сжата');
  }
  if (g && g.block === 'layers') {
    const top = num(g.depth, 4, 'layers'), th = num(g.thick, 9, 'layers'), relief = g.shape === 'flat' ? 0 : num(g.relief, 7, 'layers'), body = g.body || 'sand', cover = g.cover || 'shale', base = g.base || 'dense', c = 'blk_top(x,z)', hide = g.hide === undefined ? 'revealed' : String(g.hide), open = hide !== '1' && g.open !== 'none' ? `(${hide}) && x>${num(g.open_x, 6 * k1, 'layers')}` : null;
    out.functions[`blk_top(x,z)`] = shape(g, top, 'layers'); low = -(top + relief + th + Math.max(8, th * .25));
    const zones = g.zones || []; if (zones.length > 5) throw new Error('блок layers: не больше 5 zones');
    const cond = (z, k) => [k === z.fill.length - 1 ? '1' : `(${z.fill[k].when ?? '1'})`, ...z.fill.slice(0, k).map(q => `!(${q.when})`)].join(' && ');
    zones.forEach((z, i) => { if (!Array.isArray(z.fill) || !z.fill.length) throw new Error(`блок layers: zones[${i}].fill — [{when, fluid, mix, name}]`); z.fill.forEach((f, k) => { if (k < z.fill.length - 1 && /(?<![\w.])[xyz](?!\w)/.test(String(f.when ?? ''))) throw new Error(`блок layers: zones[${i}].fill[${k}].when — без x, y, z, только величины модели; смесь двух флюидов пишется mix, границы по глубине — to`); if (!FLUID.includes(f.fluid)) throw new Error(`блок layers: zones[${i}] fluid — ${FLUID.join(', ')}`); }); if (i < zones.length - 1 && z.to === undefined) throw new Error(`блок layers: zones[${i}].to — глубина подошвы зоны (y, м)`); });
    const name = { sand: 'Песчаник', shale: 'Глина', limestone: 'Известняк', dense: 'Плотная порода', dolomite: 'Доломит', reef: 'Рифовый известняк', salt: 'Соль', anhydrite: 'Ангидрит' };
    const bottom = `min(${c}-${th},${-top - th})`, bot = zones.length > 1 && relief ? bottom : `${c}-${th}`;
    out.objects.push({ id: 'cover', type: 'solid', name_ru: g.cover_name || name[cover], lith: cover, res: 96, top: open ? `if(${open},${c}-0.12,blk_ground(x,z))` : 'blk_ground(x,z)', bottom: open ? `if(${open},${c}-0.12,${c})` : c });
    out.objects.push({ id: 'reservoir', type: 'solid', name_ru: g.body_name || name[body], lith: body, res: 90, top: c, bottom: bot, ...(zones.length ? { show: `!(${hide})` } : {}) });
    zones.forEach((z, i) => {
      const up = i ? `(${zones[i - 1].to})` : null, dn = i < zones.length - 1 ? `(${z.to})` : null, t = up === null ? c : `min(${c},${up})`, bb = dn === null ? bot : `max(${dn},${bot})`, in_ = dn === null ? null : `${c}>${dn}`;
      z.fill.forEach((f, k) => out.objects.push({ type: 'solid', lith: body, res: 90, fluid: f.fluid, ...(f.mix ? { fluid2: f.mix } : {}), pore: 1.15, top: in_ ? `if(${in_},${t},${c}-0.12)` : t, bottom: in_ ? `if(${in_},${bb},${c}-0.12)` : bb, show: `(${hide}) && ${cond(z, k)}` }));
    });
    out.objects.push({ id: 'base', type: 'solid', name_ru: g.base_name || name[base], lith: base, top: bot, bottom: String(low) });
    const zc = []; zones.forEach((z, i) => z.fill.forEach((f, k) => zc.push({ when: [...(i < zones.length - 1 ? [`y>(${z.to})`] : []), k === z.fill.length - 1 ? '1' : `(${f.when ?? '1'})`].join(' && '), color: f.fluid, ...(f.mix ? { mix: f.mix, ...(f.share !== undefined ? { share: String(f.share) } : {}) } : {}), ...(f.name && !zc.some(q => q.name === f.name) ? { name: f.name } : {}) })));
    // зона ниже может быть закрашена только после всех вариантов зоны выше
    out.objects.push({ id: 'cutaway', type: 'section', axis: 'z', at: '0', mask: `y<${open ? `if(${open},${c},blk_ground(x,z))` : 'blk_ground(x,z)'} && y>${low}`, classes: [{ when: `y>${c}`, color: cover }, { when: `y<${bot}`, color: base }, ...lines, ...bore, ...over, ...(zones.length ? [{ when: `!(${hide})`, color: body }, ...zc] : []), { when: '1', color: body }] });
    if (open) say('После ответа порода над пластом справа от скважины снята, чтобы показать тело');
    if (zones.some(z => z.fill.some(f => f.mix))) say('Смесь двух флюидов показана пятнами, их форма условна');
  }
  if (g && g.block === 'stack') {
    const beds = g.beds; if (!Array.isArray(beds) || beds.length < 2 || beds.length > 9) throw new Error('блок stack: beds — от 2 до 9 пластов [{lith, thick, vary, name, fluid}]');
    const k = g.shape === 'flat' || !g.shape ? 0 : num(g.relief, 7, 'stack'), hide = g.hide; let sum = 0;
    out.functions['blk_b0(x,z)'] = k ? shape({ ...g, relief: k }, 0.5, 'stack') : '-0.5'; if (!k) out.functions['blk_b0(x,z)'] = '-0.5+blk_ground(x,z)';
    beds.forEach((b, i) => { if (!b.lith && !(Array.isArray(b.kinds) && b.kinds.length)) throw new Error(`блок stack: beds[${i}] без lith или kinds`); const t = num(b.thick, NaN, 'stack'); sum += t; out.functions[`blk_b${i + 1}(x,z)`] = `blk_b${i}(x,z)-max(0.05,${t}${b.vary ? `+(${b.vary})` : ''})`; });
    low = -Math.ceil(sum * 1.25 + k + 3);
    beds.forEach((b, i) => { const last = i === beds.length - 1, o = { type: 'solid', id: 'bed' + (i + 1), name_ru: b.name, lith: b.lith, res: 72, top: `blk_b${i}(x,z)`, bottom: last ? String(low) : `blk_b${i + 1}(x,z)`, ...(b.fluid ? { fluid: b.fluid } : {}) };
      if (b.kinds) { const kd = (k, j) => [j === b.kinds.length - 1 ? '1' : `(${k.when})`, ...b.kinds.slice(0, j).map(q => `!(${q.when})`), ...(hide ? [`(${hide})`] : [])].join(' && '); b.kinds.forEach((k, j) => { if (!k.lith) throw new Error(`блок stack: beds[${i}].kinds[${j}] без lith`); out.objects.push({ ...o, id: j ? undefined : o.id, lith: k.lith, name_ru: undefined, show: kd(k, j) }); }); if (hide) out.objects.push({ ...o, id: undefined, name_ru: undefined, lith: 'dense', show: `!(${hide})` }); return; }
      if (hide) out.objects.push({ ...o, show: `(${hide})` }, { ...o, id: undefined, name_ru: undefined, fluid: undefined, lith: 'dense', show: `!(${hide})` }); else out.objects.push(o); });
    out.objects.push({ id: 'cutaway', type: 'section', axis: 'z', at: '0', mask: `y<blk_b0(x,z) && y>${low}`, classes: [...bore, ...over, ...(hide ? [{ when: `!(${hide})`, color: 'dense' }] : []), ...beds.flatMap((b, i) => { const w = i === beds.length - 1 ? '1' : `y>blk_b${i + 1}(x,z)`; return b.kinds ? b.kinds.map((k, j) => ({ when: j === b.kinds.length - 1 ? w : `${w} && (${k.when})`, color: k.lith, ...(k.name ? { name: k.name } : {}) })) : [{ when: w, color: b.fluid || b.lith, ...(b.fluid && b.fluid_name ? { name: b.fluid_name } : {}) }]; })] });
  }
  const from = [], mark = t => { while (from.length < out.objects.length) from.push(t); }; mark(g ? `блок ${g.block}` : ''); const D = (v, n = 2) => `${+v.toFixed(n)}`;
  s.blocks.forEach((b, i) => {
    mark(`блок ${(s.blocks[i - 1] || b).block}`); const x = num(b.x, 0, b.block);
    if (b.block === 'well') {
      const to = num(b.to, low + 5, 'well'); const top = gy + .75 * kv;
      out.objects.push({ type: 'shape', shape: 'box', at: [`${x}`, D(top - .35 * kv), D(-2.2 * k1)], size: [D(6 * k1), D(.7 * kv), D(5 * k1)], color: 'muted' }, { type: 'prefab', name: 'derrick', at: [`${x}`, D(top), D(-2.2 * k1)], scale: 1 }, ...(bore.length ? [] : [{ type: 'tube', name_ru: b.name || 'Скважина', path: [[`${x}`, D(gy + .5 * kv), '0'], [`${x}`, `${to}`, '0']], radius: D(.45 * k1), color: 'steel' }]));
      if (b.tool !== undefined) out.objects.push({ type: 'shape', name_ru: b.tool_name || 'Прибор', shape: 'cylinder', at: [`${x}`, String(b.tool), '0'], size: [D(2.2 * k1), D(2.4 * kv), D(2.2 * k1)], color: 'measure', glow: true });
      if (b.read) out.objects.push({ type: 'label', text: b.read, at: [D(x - 12 * k1), b.tool !== undefined ? String(b.tool) : D(gy + kv), D(k1)], hot: true });
      (b.marks || []).slice(0, 3).forEach(([t, y]) => out.objects.push({ type: 'label', text: t, at: [D(x + 9 * k1), String(y), D(k1)] }));
      big('Скважина и прибор толще настоящих');
    }
    if (b.block === 'log') {
      const a = num(b.from, gy - 1, 'log'), to = num(b.to, low + 6, 'log'), w = num(b.width, 9 * k1, 'log'), x0 = +(x + num(b.offset, 3 * k1, 'log')).toFixed(2), n = 44, path = [];
      for (let q = 0; q <= n; q++) { const y = (a + (to - a) * q / n).toFixed(2); path.push([`${x0}+${w}*clamp(((${String(b.value).replace(/(?<![\w.])y(?!\w)/g, `(${y})`)})-(${b.min}))/((${b.max})-(${b.min})),0,1)`, y, D(.7 * k1)]); }
      out.objects.push({ type: 'tube', path: [[`${x0}`, `${a}`, D(.6 * k1)], [`${x0}`, `${to}`, D(.6 * k1)]], radius: D(.08 * k1), color: 'muted' }, { type: 'tube', name_ru: b.name || 'Кривая прибора', path, radius: D(.22 * k1), color: b.color, ...(b.show ? { show: b.show } : {}) });
    }
    if (b.block === 'invasion') { const h = num(b.from, 0, 'invasion') - num(b.to, 0, 'invasion'); if (!(h > 0)) throw new Error('блок invasion: from выше to (y вниз отрицательный)'); out.objects.push({ type: 'shape', shape: 'cylinder', clip: true, at: [`${x}`, `${(+b.from + +b.to) / 2}`, '0'], size: [`2*(${b.radius})`, `${h}`, `2*(${b.radius})`], color: b.color || 'filtrate', ...(b.show ? { show: b.show } : {}) }); big(`Зона проникновения нарисована крупнее${b.scale ? ` в ${ru(b.scale)} раз` : ''}`); }
    if (b.block === 'inflow') { const r = num(b.reach, 22 * k1, 'inflow'); for (const sgn of [-1, 1]) out.objects.push({ type: 'arrows', vector: [`${-sgn}`, '0', '0'], box: [[x + sgn * r, (+b.from * 3 + +b.to) / 4, k1], [x + sgn * 7 * k1, (+b.from + +b.to * 3) / 4, k1]], grid: [3, Math.max(1, Math.min(3, Math.round(Math.abs(b.from - b.to) / (2.6 * kv)))), 1], scale: 2.2, color: b.color, ...(b.show ? { show: b.show } : {}) }); }
    if (b.block === 'contact') { if (!g || g.block !== 'layers') out.objects.push({ type: 'tube', name_ru: b.name || 'Контакт', path: [[`${-X / 2}`, String(b.y), '0.4'], [`${X / 2}`, String(b.y), '0.4']], radius: '0.16', color: b.color || 'text', ...(b.show ? { show: b.show } : {}) }); if (b.label) out.objects.push({ type: 'label', text: b.label, at: [`${X * .36}`, `${b.y}+${D(.8 * kv)}`, D(k1)], ...(b.show ? { show: b.show } : {}) }); }
    if (b.block === 'front') out.objects.push({ type: 'shape', name_ru: b.name || 'Фронт', shape: 'ring', at: [`${x}`, String(b.y ?? D(gy + 1.2 * kv)), '0'], size: [`2*(${b.radius})`, '30', `2*(${b.radius})`], color: b.color || 'PRESSURE', glow: true, ...(b.show ? { show: b.show } : {}) });
    if (b.block === 'pores') {
      const a = num(b.size, g ? 18 : 34, 'pores'), c = b.at || (g ? [X * .3, 11, 8] : [0, 0, 0]), p = k => `${c[k]}+(r${k + 1}-0.5)*${(a * .84).toFixed(2)}`, v = `clamp(${b.water},0,1)`, sz = k => `${(a * k).toFixed(2)}`, cube = [-1, 1], e = [];
      out.objects.push({ type: 'scatter', n: 70, name_ru: 'Зёрна породы', at: [p(0), p(1), p(2)], size: [0, 0, 0].map(() => sz(.2)), color: 'sand', lith: b.lith || 'sand' });
      const part = (color, when, name) => out.objects.push({ type: 'scatter', n: 420, name_ru: name, at: [p(0), p(1), p(2)].map((f, k) => `${c[k]}+(fract_(i*${[.618, .755, .57][k]}+r${k + 1})-0.5)*${(a * .9).toFixed(2)}`.replace('fract_', 'blk_fr')), size: [0, 0, 0].map(() => `if(${when},${sz(.062)},0)`), color });
      out.functions['blk_fr(a)'] = 'a-floor(a)'; part('water', `r3<${v}`, 'Вода в порах'); part(b.second || 'oil', `r3>=${v}`, b.second === 'gas' ? 'Газ в порах' : 'Нефть в порах');
      for (const q of cube) for (const w of cube) e.push([[-1, q, w], [1, q, w]], [[q, -1, w], [q, 1, w]], [[q, w, -1], [q, w, 1]]); e.forEach(([A, B]) => out.objects.push({ type: 'tube', path: [A, B].map(v3 => v3.map((v2, k) => `${c[k] + v2 * a / 2}`)), radius: '0.1', color: 'muted' }));
      say('Поровый образец условный: зёрна и капли нарисованы шарами, доля воды точная по числу капель'); big('Порода показана под большим увеличением');
    }
    if (b.block === 'depth') { const a = num(b.from, 0, 'depth'), z = num(b.to, -20, 'depth'), st = Math.max(1, num(b.step, 5, 'depth')), xd = num(b.x, -X / 2, 'depth'); out.objects.push({ type: 'tube', path: [[`${xd}`, `${a}`, D(k1)], [`${xd}`, `${z}`, D(k1)]], radius: D(.12 * k1), color: 'text' }); for (let y = a, n = 0; y >= z && n < 6; y -= st, n++) out.objects.push({ type: 'label', text: `${num(b.base, 0, 'depth') - y} м`, at: [`${xd}`, `${y}`, D(1.5 * k1)] }); }
  });
  if (!out.world) { const hi = +(gy + kv).toFixed(2), H = (g ? hi : 20) - (g ? low : -20), ve = veW; out.world = g ? { size: [X, +H.toFixed(2), Z], y: [low, hi], ve, camera: { yaw: 24, pitch: 20, zoom: 1.05, target: [0, -Math.round(X * .11), 0] } } : { size: [60, 40, 60], y: [-20, 20], ve: 1, camera: { yaw: 30, pitch: 20 } }; }
  if (out.world.ve && out.world.ve !== 1) big(`Вертикальный масштаб изменён в ${ru(out.world.ve)} раза`);
  out.objects.forEach(o => Object.keys(o).forEach(k => o[k] === undefined && delete o[k]));
  mark(`блок ${s.blocks.at(-1).block}`); Object.defineProperty(out, 'from', { value: from });
  out.objects.push(...(s.objects || []));
  return out;
}
