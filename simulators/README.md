# 3D-тренажёры: заготовки

Открыть: `dist/тренажёры.html`. Сервер и интернет не нужны, нужен браузер с WebGL 2.

## Как устроено

| Слой | Где | Что делает |
|---|---|---|
| Модель | `src/models` | Физика без графики. Из неё берутся картинка, кривые и итог |
| 3D-заготовки | `src/prefabs.js`, `src/core.js` | Вышка, станция, прибор, срез недр, порода с флюидом |
| Шаблон | `src/templates` | Правила игры: `log_decision`, `pressure_field`, `body_explore` |
| Сцена | `scenes/*.json` | Параметры, допущения, источники, вопросы. Кода нет |
| Проверка | `src/validate.js` | Не собирает сцену, которая нарушает инварианты |

## Новая сцена

1. Скопируйте похожий файл в `scenes`. Для варианта хватит `"extends": "имя"` и отличий; `"ключ!"` заменяет объект целиком.
2. `npm run build` проверит сцену на нескольких случаях и соберёт HTML.
3. `node --test tests/*.mjs` — физика. `python tests/play.py` (и `play.py mob`) — прохождение кликами.

## Новый шаблон

Модель экспортирует `buildCase(spec, seed)` и `invariants`, шаблон — `build(stage, spec, seed, panel)`. Зарегистрируйте их в `src/validate.js` и `src/main.js`.

## Агент: глава → симуляция

`node agent/pipeline.mjs delta2 --book "../../хакатон/books md/ctrl_baraboshkin_b.md" --pages 34-35 --plan` показывает шаги и размер запросов, модель не вызывает. Без `--plan` запускает модель и тратит лимит.

Шаги: facts → design → model → scene → game → look → (critic) → finish. Модели и потолки — `agent/steps.json`. `--to design` — остановиться и посмотреть замысел, `--from scene` — переделать с шага, `--critic` — добавить критика. Результаты и расход — `jobs/<задание>/`.

Проверка без модели: `npm test`; с браузером — переменная `FULL=1`.

## Материалы

Фактуры и небо: Poly Haven, лицензия CC0 (sandstone_cracks, cliff_side, coral_mud_01, marble_cliff_01, rock_face_03, aerial_grass_rock, kloofendal_48d_partly_cloudy_puresky). Это фото поверхностей, а не керн. Three.js — MIT. Цвета — из легенды организаторов.

Не публиковать: в сценах есть числа и формулировки из глав.
