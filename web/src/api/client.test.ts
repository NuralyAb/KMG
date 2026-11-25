import { afterEach, describe, expect, test, vi } from 'vitest';
import { ApiError, apiPath, courseHref, errorMessage, get, post, unwrap } from './client';

const envelope = (body: object, status = 200): Response => new Response(JSON.stringify(body), { status });

afterEach(() => vi.unstubAllGlobals());

describe('unwrap', () => {
  test('returns data and meta of a successful reply', () => {
    expect(unwrap<number[], { total: number }>({ success: true, data: [1], error: null, meta: { total: 1 } }, 200))
      .toEqual({ data: [1], meta: { total: 1 } });
  });

  test('missing meta becomes null', () => {
    expect(unwrap({ success: true, data: {}, error: null }, 200).meta).toBeNull();
  });

  test('throws the human message, code and status of a failed reply', () => {
    const call = () => unwrap({ success: false, data: null, error: { code: 'busy', message: 'По главе уже идёт сборка' }, meta: null }, 409);
    expect(call).toThrow('По главе уже идёт сборка');
    try {
      call();
    } catch (error) {
      expect(error).toMatchObject({ code: 'busy', status: 409 });
    }
  });

  test.each([null, 'text', [], { data: 1 }, { success: 'yes' }])('rejects a reply without the envelope: %j', (body) => {
    expect(() => unwrap(body, 200)).toThrow('неизвестном формате');
  });

  test('an unreadable 5xx reply (proxy, backend down) says the server does not answer', () => {
    expect(() => unwrap(null, 502)).toThrow('Сервер не отвечает');
  });

  test('success without data is an error', () => {
    expect(() => unwrap({ success: true, data: null }, 200)).toThrow(ApiError);
  });
});

describe('request', () => {
  test('get reads the envelope', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(envelope({ success: true, data: { id: 'a' }, error: null, meta: null })));
    expect((await get<{ id: string }>('/api/x')).data.id).toBe('a');
  });

  test('post sends JSON', async () => {
    const fetchMock = vi.fn().mockResolvedValue(envelope({ success: true, data: {}, error: null, meta: null }, 201));
    vi.stubGlobal('fetch', fetchMock);
    await post('/api/runs', { command: 'build', chapter: 'a' });
    expect(fetchMock).toHaveBeenCalledWith('/api/runs', expect.objectContaining({ method: 'POST', body: '{"command":"build","chapter":"a"}' }));
  });

  test('a network failure becomes a clear ApiError', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')));
    await expect(get('/api/x')).rejects.toMatchObject({ code: 'network', status: 0 });
  });

  test('HTML instead of JSON is rejected', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('<!doctype html>', { status: 200 })));
    await expect(get('/api/x')).rejects.toMatchObject({ code: 'bad_envelope' });
  });
});

describe('paths', () => {
  test('encodes segments and drops empty parameters', () => {
    expect(apiPath(['chapters', 'a/b', 'tasks'], { type: '', node: 'x.y', limit: 5, page: null })).toBe('/api/chapters/a%2Fb/tasks?node=x.y&limit=5');
  });

  test.each(['javascript:alert(1)', 'https://evil.example/course/x', '//evil.example', '/course/../api/runs', '/api/runs', '', null])(
    'does not link to %s', (url) => expect(courseHref(url)).toBeNull());

  test('links to files of the course', () => expect(courseHref('/course/a/index.html')).toBe('/course/a/index.html'));

  test('errorMessage handles anything thrown', () => {
    expect(errorMessage(new Error('раз'))).toBe('раз');
    expect(errorMessage('раз')).toBe('Неизвестная ошибка');
  });
});
