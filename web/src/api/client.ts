/** Запросы к серверу и разбор общего конверта ответа {success, data, error, meta}. */

export class ApiError extends Error {
  readonly code: string;
  readonly status: number;

  constructor(message: string, code: string, status: number) {
    super(message);
    this.name = 'ApiError';
    this.code = code;
    this.status = status;
  }
}

export interface Reply<T, M = null> { data: T; meta: M }

const OFFLINE = 'Сервер не отвечает. Проверьте, что бэкенд запущен на 127.0.0.1:8200.';
const BROKEN = 'Сервер ответил в неизвестном формате.';

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

/** Достаёт данные из конверта или бросает ApiError с текстом для человека. */
export function unwrap<T, M = null>(body: unknown, status: number): Reply<T, M> {
  if (!isRecord(body) || typeof body.success !== 'boolean') {
    throw new ApiError(status >= 500 ? OFFLINE : BROKEN, 'bad_envelope', status);
  }
  if (!body.success) {
    const error = isRecord(body.error) ? body.error : {};
    const message = typeof error.message === 'string' && error.message ? error.message : `Ошибка сервера (${status})`;
    throw new ApiError(message, typeof error.code === 'string' ? error.code : 'unknown', status);
  }
  if (body.data === undefined || body.data === null) throw new ApiError(BROKEN, 'empty_data', status);
  // форма data описана контрактом; сырой узел слоя дополнительно проверяет normalizeNode
  return { data: body.data as T, meta: (body.meta ?? null) as M };
}

export function parseJson(text: string): unknown {
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

export async function request<T, M = null>(path: string, init?: RequestInit): Promise<Reply<T, M>> {
  let response: Response;
  try {
    response = await fetch(path, init);
  } catch (error: unknown) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error;
    throw new ApiError(OFFLINE, 'network', 0);
  }
  return unwrap<T, M>(parseJson(await response.text()), response.status);
}

export function get<T, M = null>(path: string, signal?: AbortSignal): Promise<Reply<T, M>> {
  return request<T, M>(path, { signal });
}

export function post<T>(path: string, body?: unknown): Promise<Reply<T>> {
  return request<T>(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body ?? {}),
  });
}

/** Отправка формы с ходом загрузки: fetch не умеет сообщать об отправленных байтах. */
export function uploadForm<T>(path: string, form: FormData, onProgress: (share: number) => void): Promise<T> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open('POST', path);
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable && event.total > 0) onProgress(event.loaded / event.total);
    };
    xhr.onerror = () => reject(new ApiError(OFFLINE, 'network', 0));
    xhr.onload = () => {
      try {
        resolve(unwrap<T>(parseJson(xhr.responseText), xhr.status).data);
      } catch (error: unknown) {
        reject(error);
      }
    };
    xhr.send(form);
  });
}

/** Собирает путь из сегментов: каждый кодируется, пустые параметры запроса выпадают. */
export function apiPath(segments: string[], query?: Record<string, string | number | null | undefined>): string {
  const path = `/api/${segments.map(encodeURIComponent).join('/')}`;
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query ?? {})) {
    if (value !== null && value !== undefined && value !== '') params.set(key, String(value));
  }
  const tail = params.toString();
  return tail ? `${path}?${tail}` : path;
}

/** Ссылки на файлы курса приходят с сервера: пропускаются только пути внутри /course/. */
export function courseHref(url: string | null | undefined): string | null {
  if (!url || !url.startsWith('/course/') || url.includes('..') || url.includes('\\')) return null;
  return url;
}

export function errorMessage(error: unknown): string {
  return error instanceof Error && error.message ? error.message : 'Неизвестная ошибка';
}
