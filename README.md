# Глава → курс

Конвейер превращает главу книги (md и PDF) в учебный слой, а слой — в демо-курс, который открывается в браузере без сервера. Слой — граф узлов, где у каждого утверждения есть дословная цитата и страница. Курс собирается только из слоя. Отдельные команды проверяют чужой пакет и собирают ролики.

Репозиторий приватный: в слоях, курсах и листах опечаток лежат дословные цитаты книг. Тексты глав, PDF, сканы и ролики в нём не хранятся.

## Посмотреть без запуска

Откройте в браузере `out/latyshova_gl5_par17-20/index.html`. Ничего ставить не нужно.

## Что нужно

| Что | Зачем |
| --- | --- |
| [uv](https://docs.astral.sh/uv/) | Python и пакеты; нужную версию Python (3.12 или новее) uv ставит сам |
| Claude Code с выполненным входом **или** ключ API Anthropic | модель |
| Главы в md; PDF книг — для сверки со сканом | их выдают организаторы, в репозитории их нет |
| ffmpeg в PATH и окружение `.venv-video` | только для роликов |
| Node.js 22 | только для `web/` и проверки `course.js` |

Проверялось на Windows 11. Шрифт кадров в роликах (Segoe UI) есть только в Windows.

## Запуск

Все команды — из корня репозитория, в PowerShell.

1. Поставьте зависимости: `uv sync --locked`.
2. Откройте `chapters.json` и укажите в `root` папку с md, в `pdf_root` — папку с PDF. Относительный путь считается от корня репозитория, например `../хакатон/books md`.
3. Включите UTF-8: `$env:PYTHONUTF8 = '1'`.
4. Проверьте, что глава читается (бесплатно, без модели): `uv run glava units latyshova_gl5_par17-20`.
5. Соберите главу одной командой:

```powershell
uv run glava build latyshova_gl5_par17-20
```

Курс появится в `out/<глава>/index.html`. Глава на 19 страниц собирается с пустым кэшем примерно 20–30 минут и стоит $10–16 по прайсу.

| Глава | Выборка | Команда |
| --- | --- | --- |
| Латышова, гл. V §17–20 | обучение | `uv run glava build latyshova_gl5_par17-20` |
| Басниев, гл. XXIII и XXIV §1 | обучение | `uv run glava build basniev_gl23-24_1` |
| Кузнецов, гл. 10 | обучение | `uv run glava build kuznetsov_gl10` |
| Вендельштейн, гл. I | контроль | `uv run glava build vendelshtein_gl1` |
| Баренблатт, §4 | контроль | `uv run glava build barenblatt_par4` |
| Барабошкин, §1.2 | контроль | `uv run glava build baraboshkin_par1-2` |

### Отдельные этапы

`build` выполняет этапы по порядку: `errata` → `layer` → `routing` → `tasks` → `illustrations` → `course`. Любой можно запустить отдельно: `uv run glava tasks <глава>`.

| Команда | Что делает | Результат |
| --- | --- | --- |
| `units` | печатает единицы главы | журнал; модель не нужна |
| `errata` | сверяет md со сканом; без PDF пропускается | `domain/<домен>/errata/<глава>.json` |
| `layer` | план, узлы, таблица покрытия, проверки | `work/<глава>/plan.json`, `layer.json`, `coverage.json`, `layer_report.json` |
| `routing` | формат для каждого узла | `work/<глава>/routing.json` |
| `tasks` | задания пяти типов | `work/<глава>/tasks.json` |
| `illustrations` | рисунки SVG | `work/<глава>/illustrations.json`, `pictures/` |
| `course` | сборка курса; модель не нужна | `out/<глава>/` |
| `review --package <папка>` | проверка чужого пакета | `out/review/<package_id>.json` |
| `video --node … --template …` | ролик по узлу | `out/<глава>/videos/` |

`--limit N` у `layer` собирает только первые N узлов — для дешёвой пробы.

### Ролик

Ролики работают в отдельном окружении. Создайте его один раз:

```powershell
uv venv .venv-video --python 3.12
uv pip install --python .venv-video\Scripts\python.exe jsonschema==4.26.0 pymupdf==2.1 pycairo==1.29.2 edge-tts==7.3.1 faster-whisper==1.2.1
```

Сборка шортса 9:16 (разбор 16:9 — `--format wide`):

```powershell
$env:PYTHONPATH = 'engine'
.venv-video\Scripts\python.exe -m glava.cli video latyshova_gl5_par17-20 --node latyshova.<узел> --template well_tool_curve --format short
```

При первом запуске скачается модель Whisper `small`. Рядом с роликом лежат паспорт, субтитры и спецификация сцены. `uv run glava video` пока не работает: пакетов для роликов нет в `pyproject.toml`.

## Переменные среды

| Переменная | По умолчанию | Что задаёт |
| --- | --- | --- |
| `LLM_PROVIDER` | `claude_code` | `claude_code` или `anthropic` |
| `LLM_MODEL` | `sonnet` | имя модели; для `anthropic` нужно полное, например `claude-sonnet-5-5` |
| `CLAUDE_EXE` | — | путь к `claude.exe`; нужен, если команды `claude` нет в PATH |
| `GLAVA_BUDGET_USD` | `25` | потолок расхода одного запуска, доллары по прайсу |
| `ANTHROPIC_API_KEY` | — | ключ для `LLM_PROVIDER=anthropic` |

Внутри сессии Claude Code путь к программе приходит сам (`CLAUDE_CODE_EXECPATH`), в обычном терминале его нет. Файл `.env` код не читает, его передают явно: `uv run --env-file .env glava build <глава>`. Образец — `.env.example`.

## Заменить модель

- **Другая модель Claude:** `$env:LLM_MODEL = 'claude-sonnet-5-5'`.
- **Прямой API:** `$env:LLM_PROVIDER = 'anthropic'`, полное имя в `LLM_MODEL`, ключ в `ANTHROPIC_API_KEY`; запуск `uv run --with anthropic glava build <глава>`. Цена считается только для моделей из `PRICES` в `engine/glava/llm/providers.py`; для остальных расход записывается как 0 и потолок не действует.
- **Другой поставщик:** класс с методом `ask(system, prompt, files) -> Reply` и ветка в `provider_from_env` того же файла. Остальной код о поставщике не знает.

Новое имя провайдера или модели — новый кэш: вся глава будет собрана и оплачена заново.

## Кэш и пересборка

Ответ модели хранится в `.cache/`. Ключ — провайдер, модель, системный промпт, вопрос и содержимое картинок. Кэш в git не попадает, поэтому на другом ПК первая сборка платная.

| Что изменили | Что сделать | Что спросится заново |
| --- | --- | --- |
| факт в `work/<глава>/layer.json` | `uv run glava course <глава>`; ролик узла — команда `video` | страница шага — бесплатно; спецификация этого ролика — платно |
| промпт `prompts/tasks.md` | `uv run glava tasks <глава>`, затем `course` | все задания |
| промпт `prompts/node.md` | `uv run glava build <глава>` | все узлы и всё, что от них зависит |
| `misconceptions.json`, `difficulty.md` | `uv run glava build <глава>` | план, узлы и дальше |
| запись листа опечаток | `layer` и следующие этапы по одному, без `errata` | узлы этих страниц и этапы, куда они входят |
| код или стиль курса | `uv run glava course <глава>` | ничего |

После ручной правки слоя не запускайте `build` и `layer`: они запишут слой заново и сотрут правку. Повтор команды с тем же кэшем вернёт те же ответы, даже неудачные; как обойти — в [плейбуке](docs/PLAYBOOK.md).

## Симуляторы

3D-сцены стоят на своих шагах курса и работают без сети. Как привязать и собрать — [docs/SIMULATORS.md](docs/SIMULATORS.md).

## Тесты

```powershell
uv run pytest
node --check engine/glava/course/assets/course.js
```

Тестам роликов нужен pycairo. В основном окружении его нет, поэтому без него падает `test_audio_problems_are_named`. Полный набор: `$env:PYTHONPATH = 'engine'`, затем `uv pip install --python .venv-video\Scripts\python.exe pytest` и `.venv-video\Scripts\python.exe -m pytest`. Те же проверки идут в GitHub Actions (`.github/workflows/ci.yml`).

## Приложение

`server/` (FastAPI, `127.0.0.1:8200`) и `web/` (React, порт 5190) — локальное приложение поверх файлов конвейера. Сейчас в разработке, контракт — [docs/API.md](docs/API.md). Курсы открываются и без него.

```powershell
cd server; uv run glava-server          # первый терминал
cd web; npm ci; npm run dev             # второй терминал, затем http://127.0.0.1:5190
```

Тесты: `cd server; uv run pytest` и `cd web; npm run typecheck; npm test; npm run build`.

## Папки

| Папка или файл | Что внутри |
| --- | --- |
| `engine/glava` | движок: разбор, этапы, проверки, курс, модуль проверки, ролики; геологии не знает |
| `engine/glava/schemas` | схемы организаторов |
| `domain/geology` | доменный пакет: заблуждения, чек-лист физики, стайлгайд, произношение, шаблоны сцен, листы опечаток |
| `prompts` | промпты всех этапов |
| `work/<глава>` | слой, покрытие, маршруты, задания, рисунки |
| `out` | курсы и ответы модуля проверки |
| `tests` | тесты движка |
| `chapters.json` | реестр глав и пути к книгам |
| `metrics.csv` | расход по этапам, строка на запуск |
| `manual_edits.csv` | журнал ручных правок |
| [MANIFEST.md](MANIFEST.md) | модели и инструменты, что уходит с ПК |
| [docs/PLAYBOOK.md](docs/PLAYBOOK.md) | работа по шагам |
| [docs/PUSH_CHECKLIST.md](docs/PUSH_CHECKLIST.md) | что можно и нельзя отправлять в GitHub |
