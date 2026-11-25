import { http, HttpResponse, delay } from 'msw';
import type { Run, RunRequest } from '@/api/types';
import { cards, detailOf, nodes } from './fixtures/chapters';
import { coverage, errata, illustrations, rawNode, routes, tasks, videos } from './fixtures/content';
import { model, pageText, sources, trust } from './fixtures/library';
import { courses, publication } from './fixtures/learn';
import { logLines, metrics, reviews, runs as startRuns } from './fixtures/work';

const LINE_MS = 700;
const ok = (data: object, meta: object | null = null, status = 200) => HttpResponse.json({ success: true, data, error: null, meta }, { status });
const fail = (status: number, code: string, message: string) =>
  HttpResponse.json({ success: false, data: null, error: { code, message }, meta: null }, { status });

let runs: Run[] = startRuns;
const patchRun = (id: string, patch: Partial<Run>): Run | undefined => {
  runs = runs.map((r) => (r.id === id ? { ...r, ...patch } : r));
  return runs.find((r) => r.id === id);
};

const makeRun = (body: { command: Run['command']; chapter: string; args?: Record<string, unknown> }): Run => {
  const run: Run = {
    id: `run-${runs.length + 1}`, command: body.command, chapter: body.chapter, args: body.args ?? {}, state: 'running',
    started_at: new Date().toISOString(), finished_at: null, exit_code: null, log_tail: [],
  };
  runs = [run, ...runs];
  return run;
};

const isActive = (run: Run): boolean => run.state === 'running' || run.state === 'queued';
const activeOf = (chapter: string): string | null => runs.find((r) => r.chapter === chapter && isActive(r))?.id ?? null;

/** Журнал по строке, затем состояние done, как отдаёт сервер. */
function eventStream(run: Run): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  const event = (name: string, data: object) => encoder.encode(`event: ${name}\ndata: ${JSON.stringify(data)}\n\n`);
  return new ReadableStream({
    async start(controller) {
      const lines = isActive(run) ? logLines : run.log_tail;
      controller.enqueue(event('state', { state: run.state, exit_code: run.exit_code }));
      for (const line of lines) {
        if (isActive(run)) await delay(LINE_MS);
        if (runs.find((r) => r.id === run.id)?.state === 'cancelled') break;
        controller.enqueue(event('log', { line }));
      }
      const current = runs.find((r) => r.id === run.id) ?? run;
      const last = isActive(current) ? patchRun(run.id, { state: 'done', exit_code: 0, finished_at: new Date().toISOString(), log_tail: lines }) ?? current : current;
      controller.enqueue(event('state', { state: last.state, exit_code: last.exit_code }));
      controller.close();
    },
  });
}

const JAR = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 260"><rect width="400" height="260" fill="#fff"/><rect x="130" y="30" width="140" height="200" rx="10" fill="none" stroke="#0B6E8F" stroke-width="4"/>${Array.from({ length: 24 }, (_, i) => `<circle cx="${150 + (i % 4) * 33}" cy="${90 + Math.floor(i / 4) * 24}" r="11" fill="#D9A441"/>`).join('')}</svg>`;

export const handlers = [
  http.get('/api/health', () => ok({ status: 'ok', provider: 'mock', model: 'заглушка', claude_found: true, ffmpeg_found: true })),
  http.get('/api/chapters', () => ok(cards.map((c) => ({ ...c, active_run: activeOf(c.id) })))),
  http.get('/api/chapters/:id', ({ params }) => {
    const detail = detailOf(String(params.id));
    return detail ? ok({ ...detail, active_run: activeOf(detail.id) }) : fail(404, 'not_found', 'Такой главы нет в реестре');
  }),
  http.get('/api/chapters/:id/nodes/:node', ({ params }) => {
    const at = nodes.findIndex((n) => n.id === params.node);
    const row = nodes[at];
    if (!row) return fail(404, 'not_found', 'Такого шага нет в слое');
    const node = row.id === rawNode.id ? rawNode : { ...rawNode, id: row.id, order: row.order, title: row.title, threshold: row.threshold, difficulty: row.difficulty, misconception: null, worked_examples: [], claims: rawNode.claims.slice(0, row.claims), needs_scan: [] };
    return ok({
      node, route: routes.find((r) => r.node_id === row.id) ?? null, tasks: tasks.filter((t) => t.step_id === row.id),
      illustrations: illustrations.filter((i) => i.step_id === row.id), prev: nodes[at - 1]?.id ?? null, next: nodes[at + 1]?.id ?? null,
    });
  }),
  http.get('/api/chapters/:id/coverage', ({ request, params }) => {
    if (params.id !== 'demo_sand') return ok([], { total: 0, covered: 0, skipped: 0 });
    const only = new URL(request.url).searchParams.get('uncovered') === '1';
    const covered = coverage.filter((r) => r.node_ids.length > 0).length;
    return ok(only ? coverage.filter((r) => r.node_ids.length === 0) : coverage, { total: coverage.length, covered, skipped: coverage.length - covered });
  }),
  http.get('/api/chapters/:id/errata', ({ params }) => ok(params.id === 'demo_sand' ? errata : [], { recognition: 2, suspect: 1 })),
  http.get('/api/chapters/:id/trust', () => ok(trust)),
  http.get('/api/chapters/:id/routing', () => ok(routes)),
  http.get('/api/chapters/:id/tasks', ({ request, params }) => {
    const query = new URL(request.url).searchParams;
    const all = params.id === 'demo_sand' ? tasks : [];
    const shown = all.filter((t) => (!query.get('type') || t.type === query.get('type')) && (!query.get('node') || t.step_id === query.get('node')));
    const byType = Object.fromEntries(['single', 'multiple', 'order', 'gap', 'calc'].map((type) => [type, all.filter((t) => t.type === type).length]));
    return ok(shown, { total: shown.length, by_type: byType });
  }),
  http.get('/api/chapters/:id/nodes/:node/simulations', () => ok({ scenes: [], run: null })),
  http.get('/api/chapters/:id/illustrations', ({ params }) => ok(params.id === 'demo_sand' ? illustrations : [])),
  http.get('/api/chapters/:id/videos', ({ params }) => ok(params.id === 'demo_sand' ? videos : [])),
  http.get('/api/search', ({ request }) => {
    const q = (new URL(request.url).searchParams.get('q') ?? '').toLowerCase().replaceAll('ё', 'е');
    const found = rawNode.claims.filter((c) => `${c.text} ${c.quote}`.toLowerCase().replaceAll('ё', 'е').includes(q));
    return ok(found.map((c) => ({ chapter: 'demo_sand', node_id: rawNode.id, node_title: rawNode.title, claim_id: c.id, text: c.text, quote: c.quote, page_pdf: c.page_pdf })), { total: found.length, page: 1, limit: 20 });
  }),
  http.get('/api/metrics', () => ok(metrics, {
    cost_usd: metrics.reduce((s, r) => s + r.money_usd, 0), tokens_in: metrics.reduce((s, r) => s + r.llm_tokens_in, 0), tokens_out: metrics.reduce((s, r) => s + r.llm_tokens_out, 0),
  })),
  http.get('/api/runs', () => ok(runs)),
  http.post<never, RunRequest>('/api/runs', async ({ request }) => {
    const body = await request.json();
    if (activeOf(body.chapter)) return fail(409, 'busy', 'По этой главе уже идёт сборка');
    return ok(makeRun(body), null, 201);
  }),
  http.get('/api/runs/:id', ({ params }) => {
    const run = runs.find((r) => r.id === params.id);
    return run ? ok(run) : fail(404, 'not_found', 'Такого запуска нет');
  }),
  http.get('/api/runs/:id/events', ({ params }) => {
    const run = runs.find((r) => r.id === params.id);
    if (!run) return fail(404, 'not_found', 'Такого запуска нет');
    return new HttpResponse(eventStream(run), { headers: { 'Content-Type': 'text/event-stream', 'Cache-Control': 'no-cache' } });
  }),
  http.post('/api/runs/:id/cancel', ({ params }) => {
    const run = patchRun(String(params.id), { state: 'cancelled', finished_at: new Date().toISOString() });
    return run ? ok(run) : fail(404, 'not_found', 'Такого запуска нет');
  }),
  http.get('/api/auth/me', () => ok({ role: 'admin', protected: false })),
  http.post('/api/auth/login', () => fail(409, 'conflict', 'Пароль автора не задан, вход не нужен')),
  http.post('/api/auth/logout', () => ok({ role: 'admin', protected: false })),
  http.get('/api/learn/courses', () => ok(courses)),
  http.get('/api/learn/courses/:id', ({ params }) => {
    const found = courses.find((c) => c.id === params.id);
    return found ? ok(found) : fail(404, 'not_found', 'Такого курса нет');
  }),
  http.get('/learn/*', () => new HttpResponse('<!doctype html><p>Курс</p>', { headers: { 'Content-Type': 'text/html' } })),
  http.get('/api/chapters/:id/publication', () => ok(publication)),
  http.post('/api/chapters/:id/publication', () => ok({ ...publication, published_at: '2026-11-25T12:00:00Z', is_current: true })),
  http.delete('/api/chapters/:id/publication', () => ok(publication)),
  http.get('/api/library', () => ok(sources.map(({ page_list: _, ...s }) => s))),
  http.post('/api/library', async () => {
    await delay(300);
    return ok(sources[0] ?? {}, null, 201);
  }),
  http.get('/api/library/:id', ({ params }) => {
    const found = sources.find((s) => s.id === params.id);
    return found ? ok(found) : fail(404, 'not_found', 'Такого файла в базе знаний нет');
  }),
  http.get('/api/library/:id/pages/:page', ({ params }) => ok({ page: Number(params.page), text: pageText })),
  http.get('/api/library/:id/original', () => new HttpResponse(null, { status: 404 })),
  http.post('/api/library/:id/extract', ({ params }) => ok(makeRun({ command: 'extract', chapter: String(params.id) }), null, 201)),
  http.post('/api/library/:id/chapters', () => ok({ id: 'demo_sand' }, null, 201)),
  http.delete('/api/library/chapters/:id', ({ params }) => ok({ id: String(params.id) })),
  http.delete('/api/library/:id', ({ params }) => ok({ id: String(params.id) })),
  http.get('/api/domains', () => ok(['general', 'geology'])),
  http.get('/api/settings/model', () => ok(model)),
  http.post<never, object>('/api/settings/model', async ({ request }) => ok({ ...model, ...(await request.json()), origin: 'file' })),
  http.get('/api/reviews', () => ok(reviews)),
  http.get('/api/reviews/:id', ({ params }) => {
    const review = reviews.find((r) => r.package_id === params.id);
    return review ? ok(review) : fail(404, 'not_found', 'Такой проверки нет');
  }),
  http.post('/api/reviews', async () => {
    await delay(800);
    return ok(makeRun({ command: 'review', chapter: 'demo_sand', args: { package_id: 'demo_package' } }), null, 201);
  }),
  http.get('/course/:id/pictures/jar.svg', () => new HttpResponse(JAR, { headers: { 'Content-Type': 'image/svg+xml' } })),
  http.get('/course/*', () => new HttpResponse(null, { status: 404 })),
];
