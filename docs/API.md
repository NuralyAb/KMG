# Приложение «Глава → курс»: контракт API

Локальное приложение одного пользователя поверх конвейера `engine/glava`. Главы и ролики не публикуются, поэтому сервер слушает только `127.0.0.1`. Бэкенд — `server/` (FastAPI, порт 8200), фронтенд — `web/` (React + Vite, порт 5190, прокси `/api` и `/course` на 8200). Источник данных — файлы конвейера: `chapters.json`, `work/<глава>/*.json`, `domain/<домен>/errata/<глава>.json`, `out/<глава>/`, `out/review/*.json`, `metrics.csv`. Своей базы нет.

## Общие правила

- Ответ: `{"success": true, "data": …, "error": null, "meta": {…}|null}`; ошибка: `{"success": false, "data": null, "error": {"code": "not_found", "message": "понятный текст по-русски"}, "meta": null}` с кодом 400, 404, 409, 413, 422 или 500.
- Идентификаторы глав и пакетов проверяются по `^[A-Za-z0-9_][A-Za-z0-9_.-]*$` и по реестру; путь к файлу из запроса не строится.
- POST принимается только с `Origin` `http://127.0.0.1:5190`, `http://localhost:5190` или того же хоста; тело до 80 МБ.
- `key.json` не читается и не отдаётся никогда.
- Даты — ISO 8601, деньги — доллары по прайсу (`float`).

## Типы

```ts
type StageName = 'errata' | 'layer' | 'routing' | 'tasks' | 'illustrations' | 'course'
type Stage = { name: StageName; state: 'missing' | 'ready' | 'stale'; updated_at: string | null } // stale: результат старше файла предыдущего этапа
type ChapterCard = {
  id: string; title: string; book: string; domain: string; pages: number[]
  counts: { nodes: number; claims: number; tasks: number; illustrations: number; errata: number; units: number; units_covered: number; videos: number }
  issues: number // замечания layer_report.json
  stages: Stage[]; cost_usd: number; tokens_in: number; tokens_out: number; course_url: string | null // "/course/<id>/index.html"
  active_run: string | null
}
type NodeRow = { id: string; order: number; title: string; short_title: string; difficulty: { primary: string; secondary: string | null }; threshold: boolean; pages: number[]; claims: number; tasks: number; format: string | null; needs_scan: number }
type ChapterDetail = ChapterCard & { parts: { title: string; nodes: NodeRow[] }[] }
type NodeDetail = { node: object /* узел layer.json как есть */; route: object | null; tasks: object[]; illustrations: object[]; prev: string | null; next: string | null }
type Run = { id: string; command: 'build' | StageName | 'review' | 'video' | 'simulation'; chapter: string; args: object; state: 'queued' | 'running' | 'done' | 'failed' | 'cancelled'; started_at: string | null; finished_at: string | null; exit_code: number | null; log_tail: string[] }
type Remark = { target: string; category: string; severity: 'critical' | 'significant' | 'minor'; problem: string; fix: string; page_pdf: number | null; quote: string | null }
type Review = { package_id: string; chapter: string | null; created_at: string; remarks: Remark[]; counts: { critical: number; significant: number; minor: number } }
type Video = { id: string; chapter: string; title: string; format: '9:16' | '16:9'; duration_s: number; url: string; subtitles_url: string | null; passport: object; problems: string[] }
type MetricRow = { chapter: string; stage: string; nodes: number; llm_tokens_in: number; llm_tokens_out: number; money_usd: number; person_minutes: number; mentor_minutes: number; video_seconds: number; manual_share: number }
```

## Маршруты

| Метод и путь | Ответ `data` |
| --- | --- |
| GET `/api/health` | `{status: "ok", provider: string, model: string, claude_found: boolean, ffmpeg_found: boolean}` |
| GET `/api/books` | `{id, title, file, uploaded, has_pdf}[]` |
| POST `/api/books` (форма: `file` md, `pdf`) | книга, 201 |
| GET `/api/books/{id}` | книга, `sections: {id, title, level, first, last}[]`, `first_page`, `last_page`, `domains` |
| POST `/api/books/{id}/chapters` `{title, pages: [[9, 14], [20, 30]], domain}` | `{id}`, 201 |
| GET `/api/chapters` | `ChapterCard[]` |
| GET `/api/chapters/{id}` | `ChapterDetail` |
| GET `/api/chapters/{id}/nodes/{node_id}` | `NodeDetail` |
| GET `/api/chapters/{id}/coverage?uncovered=0\|1` | строки `coverage.json`; `meta: {total, covered, skipped}` |
| GET `/api/chapters/{id}/errata` | записи листа опечаток `{page, md, scan, kind, note}`; `meta: {recognition, suspect}` |
| GET `/api/chapters/{id}/routing` | `routes` |
| GET `/api/chapters/{id}/tasks?type=&node=` | задания; `meta: {total, by_type}` |
| GET `/api/chapters/{id}/illustrations` | записи `illustrations.json`, поле `url` = `/course/<id>/<file>` |
| GET `/api/chapters/{id}/videos` | `Video[]` |
| GET `/api/search?q=&chapter=&page=&limit=` | утверждения `{chapter, node_id, node_title, claim_id, text, quote, page_pdf}`; поиск без учёта регистра и «ё», `q` от 2 знаков; `meta: {total, page, limit}` |
| GET `/api/metrics` | `MetricRow[]`; `meta: {cost_usd, tokens_in, tokens_out}` |
| GET `/api/runs` | `Run[]`, новые сверху |
| POST `/api/runs` `{command, chapter, limit?, node?, format?, template?}` | `Run`, код 201; 409, если по главе уже идёт сборка |
| GET `/api/runs/{id}` | `Run` |
| GET `/api/runs/{id}/events` | SSE: события `log` `{line}`, `state` `{state, exit_code}`; при подключении отдаёт уже накопленный журнал |
| POST `/api/runs/{id}/cancel` | `Run` |
| GET `/api/reviews` | `Review[]` |
| GET `/api/reviews/{package_id}` | `Review` |
| POST `/api/reviews` multipart: `chapter`, `file` (zip с `package.json` и `frames/`) | `Run` команды review, код 201. Zip распаковывается безопасно: без выхода из папки, только `package.json` и картинки, файл с «key» в имени отбрасывается |
| GET `/course/{id}/…` | статические файлы `out/<id>/` (курс, рисунки, ролики) |

Запуск сборки — отдельный процесс `uv run glava <команда> <глава>` из корня репозитория с `PYTHONUTF8=1`, вывод идёт в журнал запуска `work/runs/<id>.log`. Одновременно не больше двух процессов, остальные в очереди. После перезапуска сервера незавершённые запуски помечаются `failed`.

## Экраны фронтенда

1. **Главы** `/`: карточка главы с этапами, покрытием, числом шагов, утверждений, заданий, ценой; кнопки «Открыть курс», «Собрать».
2. **Глава** `/chapters/:id`: вкладки Путь, Покрытие, Опечатки, Задания, Рисунки, Ролики, Сборка (этапы, журнал запуска вживую).
3. **Узел** `/chapters/:id/nodes/:nodeId`: слои, утверждения с цитатой и страницей, маршрут, задания, рисунок, назад / дальше.
4. **Проверка пакета** `/review`, `/review/:packageId`: загрузка zip, ход проверки, замечания по тяжести с исправлением, страницей и цитатой.
5. **Запуски** `/runs`, **Расход** `/metrics`, **Поиск** `/search`.

Дизайн — METU: токены `METU/web/src/app/tokens.css`, рамка и белый лист, IBM Plex Sans, петроль, светлая и тёмная тема. Телефон 390 px и десктоп 1280 px без прокрутки вбок, текст от 16 px, видимый фокус.
