# Глава → курс

Конвейер превращает главу книги (md и PDF) в учебный слой, а слой — в демо-курс, который открывается в браузере без сервера. Слой — граф узлов, где у каждого утверждения есть дословная цитата и страница. Курс собирается только из слоя. Отдельные команды проверяют чужой пакет и собирают ролики.

Репозиторий приватный: в слоях, курсах и листах опечаток лежат дословные цитаты книг. Тексты глав, PDF, сканы и ролики в нём не хранятся.

## Посмотреть без запуска

Откройте в браузере `workspace/out/latyshova_gl5_par17-20/index.html`. Ничего ставить не нужно.

## Что нужно

| Что | Зачем |
| --- | --- |
| [uv](https://docs.astral.sh/uv/) | Python и пакеты; нужную версию Python (3.12 или новее) uv ставит сам |
| Claude Code с выполненным входом **или** ключ API Anthropic | модель |
| Главы в md; PDF книг — для сверки со сканом | их выдают организаторы, в репозитории их нет |
| окружение `.venv-video`; ffmpeg — из PATH, `FFMPEG_EXE` или пакета `imageio-ffmpeg` | только для роликов |
| Node.js 22 | только для `web/` и проверки `course.js` |

Проверялось на Windows 11. Шрифт кадров в роликах (Segoe UI) есть только в Windows.

## Запуск

Все команды — из корня репозитория, в PowerShell.

1. Поставьте зависимости: `uv sync --locked`.
2. Откройте `workspace/chapters.json` и укажите в `root` папку с md, в `pdf_root` — папку с PDF. Относительный путь считается от `workspace/`, например `../../хакатон/books md`.
3. Включите UTF-8: `$env:PYTHONUTF8 = '1'`.
4. Проверьте, что глава читается (бесплатно, без модели): `uv run glava units latyshova_gl5_par17-20`.
5. Соберите главу одной командой:

```powershell
uv run glava build latyshova_gl5_par17-20
```

Курс появится в `workspace/out/<глава>/index.html`. Глава на 19 страниц собирается с пустым кэшем примерно 20–30 минут и стоит $10–16 по прайсу.

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
| `errata` | сверяет md со сканом; без PDF пропускается | `workspace/domain/<домен>/errata/<глава>.json` |
| `layer` | план, узлы, таблица покрытия, проверки | `workspace/work/<глава>/plan.json`, `layer.json`, `coverage.json`, `layer_report.json` |
| `routing` | формат для каждого узла | `workspace/work/<глава>/routing.json` |
| `tasks` | задания пяти типов | `workspace/work/<глава>/tasks.json` |
| `illustrations` | рисунки SVG | `workspace/work/<глава>/illustrations.json`, `pictures/` |
| `course` | сборка курса; модель не нужна | `workspace/out/<глава>/` |
| `extract <файл> [--vision]` | страницы загруженной книги; с `--vision` ненадёжные страницы читает модель | `workspace/library/<файл>/text.md`, `pages.json` |
| `audit` | сверка утверждений с цитатами кодом и её чутьё; модель и книга не нужны | `workspace/work/<глава>/audit.json` |
| `verify [--mutants]` | вторая модель сверяет утверждения с цитатами и фразы с утверждениями | `workspace/work/<глава>/trust.json` |
| `review --package <папка>` | проверка чужого пакета | `workspace/out/review/<package_id>.json` |
| `video --node … --template …` | ролик по узлу: спецификацию пишет модель | `workspace/work/<глава>/video_specs/`, `workspace/out/<глава>/videos/` |
| `video --spec <файл>` | ролик из готовой спецификации; модель не нужна | то же |
| `rebuild [--node …]` | после правки факта: проверка слоя, ролики и страница шага | то же и `workspace/out/<глава>/` |
| `voices` | голоса ElevenLabs и остаток знаков; знаки не тратит | журнал |
| `templates` | каким шаблоном закрыт каждый видеоёмкий узел; модель не нужна | `workspace/work/<глава>/template_coverage.json` |
| `ready [глава]` | чего не хватает по ТЗ; без главы — все обучающие и серия роликов | журнал |
| `process [глава]` | деньги и минуты на узел и на минуту видео | `workspace/out/process.csv` |

`--limit N` у `layer` собирает только первые N узлов — для дешёвой пробы.

### Ролик

Ролики работают в отдельном окружении. Создайте его один раз:

```powershell
uv venv .venv-video --python 3.12
uv pip install --python .venv-video\Scripts\python.exe jsonschema==4.26.0 pymupdf==2.1 pycairo==1.29.2 edge-tts==7.3.1 faster-whisper==1.2.1 imageio-ffmpeg numpy
```

Сборка шортса 9:16 (разбор 16:9 — `--format wide`):

```powershell
$env:PYTHONPATH = 'backend'
.venv-video\Scripts\python.exe -m glava video latyshova_gl5_par17-20 --node latyshova.<узел> --template well_tool_curve --format short
```

**Голос.** Скопируйте `.env.example` в `.env`, впишите `ELEVENLABS_API_KEY`, выберите голос командой `.venv-video\Scripts\python.exe -m glava voices` и впишите `ELEVENLABS_VOICE_ID`. Без ключа ролик озвучит бесплатный голос Microsoft; выбрать голос вручную — `--voice elevenlabs` или `--voice edge`. Готовые фразы повторно не оплачиваются, потолок — `ELEVENLABS_MAX_CHARS`. По ТЗ синтез — голосами Microsoft, другой сервис назван запасным путём: ElevenLabs основным голосом согласуйте с организаторами. Вся серия — одним голосом: после выбора пересоберите все ролики, это проверяет `ready`.

Ролик из готовой спецификации, без модели:

```powershell
.venv-video\Scripts\python.exe -m glava video latyshova_gl5_par17-20 --spec workspace\work\latyshova_gl5_par17-20\video_specs\latyshova_mud_effects_on_borehole_short.json
```

`--spec-only` останавливает команду после спецификации: её смотрит ментор до рендера.

При первом запуске скачается модель Whisper `small`. Рядом с роликом лежат паспорт, субтитры и спецификация сцены. Пакеты роликов — группа `video` в `pyproject.toml`.

## Переменные среды

| Переменная | По умолчанию | Что задаёт |
| --- | --- | --- |
| `LLM_PROVIDER` | `claude_code` | `claude_code`, `anthropic`, `openai` или `local` |
| `LLM_MODEL` | `sonnet` | имя модели; для `anthropic` нужно полное, например `claude-sonnet-5-5`; для `openai` и `local` обязательно |
| `CLAUDE_EXE` | — | путь к `claude.exe`; нужен, если команды `claude` нет в PATH |
| `LLM_VERIFY_MODEL` | как `LLM_MODEL` | модель для `verify`; лучше другая: свою ошибку модель замечает хуже |
| `GLAVA_CONTEXT` | `chapter` | `node` — не давать узлу всю главу (для моделей с коротким контекстом) |
| `GLAVA_FREE_NUMBERS` | — | `1` — разрешить в расчётных заданиях числа, которых нет в книге |
| `GLAVA_BUDGET_USD` | `25` | потолок расхода одного запуска, доллары по прайсу |
| `ANTHROPIC_API_KEY` | — | ключ для `LLM_PROVIDER=anthropic` |
| `OPENAI_API_KEY` | — | ключ для `LLM_PROVIDER=openai`; на другие адреса не отправляется |
| `LLM_BASE_URL` | `http://127.0.0.1:11434/v1` | адрес сервера для `local` (по умолчанию Ollama) |
| `LLM_API_KEY` | — | ключ для `local`, если сервер его требует |
| `LLM_CONTEXT` | — | размер контекста локальной модели в токенах, как он настроен на сервере; для `local` обязателен: по нему ловится обрезка запроса |
| `LLM_PRICE_IN`, `LLM_PRICE_OUT` | — | доллары за миллион токенов; обязательны для `openai` и для `local` на другом компьютере, иначе потолок расхода не сработает |

Внутри сессии Claude Code путь к программе приходит сам (`CLAUDE_CODE_EXECPATH`), в обычном терминале его нет. Из файла `.env` код сам читает только голос роликов (`VOICE_*`, `ELEVENLABS_*`), остальное передают явно: `uv run --env-file .env glava build <глава>`. Образец — `.env.example`.

## Заменить модель

- **Другая модель Claude:** `$env:LLM_MODEL = 'claude-sonnet-5-5'`.
- **Прямой API:** `$env:LLM_PROVIDER = 'anthropic'`, полное имя в `LLM_MODEL`, ключ в `ANTHROPIC_API_KEY`; запуск `uv run --extra anthropic glava build <глава>`. Цена берётся из `PRICES` в `backend/glava/modules/llm/providers.py`; модель без цены не запускается.
- **OpenAI:** `$env:LLM_PROVIDER = 'openai'`, имя в `LLM_MODEL`, ключ в `OPENAI_API_KEY`, цены в `LLM_PRICE_IN` и `LLM_PRICE_OUT`. Дополнительных пакетов не нужно.
- **Локальная модель:** `$env:LLM_PROVIDER = 'local'`, имя в `LLM_MODEL`; подходит любой сервер с API OpenAI (Ollama, LM Studio, vLLM), адрес — в `LLM_BASE_URL`. Этапам `errata` и `review` нужна модель, которая видит картинки. У Ollama увеличьте `OLLAMA_CONTEXT_LENGTH`: при малом контексте она молча отбрасывает часть главы. Сильная обрезка ловится сама, точная проверка — по `LLM_CONTEXT`.
- **Другой поставщик:** класс с методом `ask(system, prompt, files) -> Reply` и ветка в `provider_from_env` того же файла. Остальной код о поставщике не знает.

Новое имя провайдера или модели — новый кэш: вся глава будет собрана и оплачена заново.

## Кэш и пересборка

Ответ модели хранится в `.cache/`. Ключ — провайдер, модель, системный промпт, вопрос и содержимое картинок. Кэш в git не попадает, поэтому на другом ПК первая сборка платная.

| Что изменили | Что сделать | Что спросится заново |
| --- | --- | --- |
| факт в `workspace/work/<глава>/layer.json` | `uv run glava course <глава>`; ролик узла — команда `video` | страница шага — бесплатно; спецификация этого ролика — платно |
| промпт `backend/glava/pipeline/prompts/tasks.md` | `uv run glava tasks <глава>`, затем `course` | все задания |
| промпт `backend/glava/pipeline/prompts/node.md` | `uv run glava build <глава>` | все узлы и всё, что от них зависит |
| `misconceptions.json`, `difficulty.md` | `uv run glava build <глава>` | план, узлы и дальше |
| запись листа опечаток | `layer` и следующие этапы по одному, без `errata` | узлы этих страниц и этапы, куда они входят |
| код или стиль курса | `uv run glava course <глава>` | ничего |

После ручной правки слоя не запускайте `build` и `layer`: они запишут слой заново и сотрут правку. Повтор команды с тем же кэшем вернёт те же ответы, даже неудачные; как обойти — в [плейбуке](docs/PLAYBOOK.md).

## Новая глава из книги

В приложении: «Книги» → загрузить md с метками страниц и, если есть, PDF → отметить разделы → «Создать курс». Оглавление строит программа без модели, страницы можно поправить. Глава попадает в `workspace/chapters.json`, файлы — в `workspace/books/` (в git не идут). Сборка запускается отдельно и стоит денег.

## Симуляторы

3D-сцены стоят на своих шагах курса и работают без сети. Как привязать и собрать — [docs/SIMULATORS.md](docs/SIMULATORS.md).

## Тесты

```powershell
uv run pytest
cd web; npm ci; npm test
```

Тестам роликов нужен pycairo. В основном окружении его нет, поэтому без него падает `test_audio_problems_are_named`. Полный набор: `$env:PYTHONPATH = 'backend'`, затем `uv pip install --python .venv-video\Scripts\python.exe pytest` и `.venv-video\Scripts\python.exe -m pytest`. Те же проверки идут в GitHub Actions (`.github/workflows/ci.yml`).

## Приложение

`backend/` (FastAPI, `127.0.0.1:8200`) и `web/` (React, порт 5190) — локальное приложение поверх файлов конвейера. Сейчас в разработке, контракт — [docs/API.md](docs/API.md). Курсы открываются и без него.

```powershell
uv run glava-server          # первый терминал
cd web; npm ci; npm run dev             # второй терминал, затем http://127.0.0.1:5190
```

Тесты: `uv run pytest` и `cd web; npm run typecheck; npm test; npm run build`.

## Озвученные разборы

`.venv-video\Scripts\python.exe -m glava narrate <глава>` делает разбор каждого шага: фразы берутся из слоя дословно, голос Microsoft бесплатный, модель не нужна. Это не mp4: дорожка лежит в `workspace/out/<глава>/narration/`, а картинку — фразы и схему, которая проступает по ходу рассказа, — рисует плеер. Обозначения, которых нет в `pronunciation.md`, голос не угадывает: такая фраза пропускается, список — в `workspace/work/<глава>/narration.json`. Готовые фразы берутся из кэша; сервис часто отвечает пусто, повторы встроены. Ролики mp4 (`video`) стоят на сцене первыми, разбор — рядом.

## Плеер курса

Сам курс — React-приложение `web/src/course`. `cd web; npm run build:course` собирает его одним файлом в `backend/glava/modules/course/assets/course.js`; файл лежит в git, поэтому конвейеру Node не нужен, а курс открывается двойным щелчком без сервера. Правите `web/src/course` — пересоберите плеер и закоммитьте `course.js`: CI сверяет его с кодом. Оформление курса — `course.css` там же, сборка ему не нужна.

## Ученик и автор

`http://127.0.0.1:5190/` — экран ученика: опубликованные курсы и прогресс. `/admin` — экран автора. Чтобы ученик не попал к автору, запустите сервер с паролем: `$env:GLAVA_ADMIN_PASSWORD = '…'` (от 8 знаков). Курс появляется у учеников после кнопки «Опубликовать» на странице главы; снимок лежит в `workspace/published/` и в git не попадает. Сервер слушает только этот компьютер, прогресс хранится в браузере, поэтому у двух учеников на одном компьютере он общий.

## База знаний

Раздел «База знаний» в приложении: загрузите PDF, DOCX, MD, TXT или картинку, сверьте извлечённый текст со страницами, выберите страницы и предметную область — глава появится в списке. Файлы лежат в `workspace/library/`; они, их слои, курсы и листы опечаток (`lib_*`) в git не попадают. Страницы, которым нельзя верить (скан, слой распознавания, формулы, колонки), помечены, а утверждения с них просят сверки. Предметная область по умолчанию — `workspace/domain/general`.

## Папки

| Папка или файл | Что внутри |
| --- | --- |
| `backend/glava` | Python: конвейер и сервер, один проект. Устройство — [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) |
| `backend/architecture.toml` | разрешённые зависимости модулей, их проверяет тест |
| `backend/tests` | `pipeline`, `http`, `architecture` |
| `web` | React: экраны ученика и автора (`src`), плеер курса (`src/course`) |
| `simulators` | 3D-симуляторы и агент, который их строит |
| `workspace` | данные: доменные пакеты, слои, курсы, реестр глав, расход; загруженные книги в git не идут |
| `docs` | документация |
| `scripts` | разовые команды разработчика |
| `manual_edits.csv` | журнал ручных правок |
| [MANIFEST.md](MANIFEST.md) | модели и инструменты, что уходит с ПК |

После перехода со старой раскладки один раз выполните `uv run python scripts/migrate_workspace.py --apply`: загруженные книги, публикации и журналы переедут в `workspace/`. Кэш ответов модели `.cache/` остаётся на месте.
