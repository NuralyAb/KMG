# Каталог кирпичиков

Один файл `sim.json`, `"template": "compose"`. Координаты в метрах: x вправо, y вверх, z к зрителю, центр мира (0, ?, 0). Глубина растёт вниз: y отрицательный.

## Формулы
`+ - * / ^ < > <= >= == != && || ! ?:`, числа, имена. Функции: sin cos tan exp ln log10 sqrt abs min max pow floor sign atan2 hypot mod clamp(v,a,b) lerp(a,b,k) smooth(a,b,v) step(a,v) gauss(v)=exp(-v²) erf E1 noise(x,y,z,n) fbm(x,y,z,n) if(c,a,b). noise и fbm дают −1..1, последний аргумент — номер; `seed` в нём делает случаи разными.
Имена: параметры, переменные, состояния, `t` (секунды!), `T` (доля времени 0..1), `step` (номер шага с 0), `revealed` (0/1), `picks`, `seed`, id шагов guess (значение в СИ) и choose (номер ответа, −1 до ответа).

## Модель (всё считается в СИ, единицы переводятся сами)
```json
"params": {
  "k":  {"value": 0.2, "unit": "um2", "from": "assumption", "range": [0.1, 0.4], "control": [0.05, 0.8, 0.01, "Проницаемость"]},
  "h1": {"range": [4, 10], "unit": "m", "from": "book", "claim": "c2"}
},
"tables": {"por": {"x_unit": "m", "y_unit": "%", "rows": [[0, 5], [10, 20]]}},
"functions": {"top(x,z)": "h1*gauss(x/R)"},
"states": {"V": {"init": "0", "rate": "Q*(1-V/Vmax)", "unit": "m3"}},
"vars": {"front": {"expr": "2*sqrt(kap*t)", "unit": "m", "label": "Радиус", "digits": 0}},
"time": {"min": 0, "max": 100, "unit": "kyr", "log": false, "duration": 10, "label": "Время", "stages": [{"until": 0.5, "text": "Сначала…"}, {"until": 1, "text": "Потом…"}]}
```
`range` — случайное значение в каждом случае. `control` — ползунок. `from: "book"` требует claim, и число должно быть в цитате. Остальное — `assumption`.
Единицы: m cm mm um km kg g t s min h d yr kyr Myr Pa kPa MPa bar atm N mPas D mD % deg C ohm ppt; составные через * / и степень: m3/d, 1/Pa, g/cm3, ohm*m, um2, m/yr.

## Мир
`"world": {"size": [X, Y, Z], "y": [низ, верх], "ve": 5, "camera": {"yaw": 30, "pitch": 24, "zoom": 1, "target": [0,0,0]}}`. ve — вертикальное преувеличение, его обязательно назвать в exaggerations.
Мир автоматически помещается в кадр: больше 100 «единиц» в ширину он не бывает. Высота на экране = (верх − низ)·ve / max(X, Z); держите её 0,15–0,5 ширины, иначе плоско или не влезет.

## Объекты (`objects`)
Общие поля: `id`, `show` (формула), `opacity` (формула), `name_ru` (в легенду), `clip: false` (не резать разрезом).
| type | Обязательное | Прочее |
|---|---|---|
| solid | top(x,z), bottom(x,z), lith | fluid (oil/water/gas — точки в порах), pore, res. Тело между поверхностями на всю площадь; где top ≤ bottom — толщина 0 |
| surface | y(x,z) | lith или color; value(x,z)+min+max+color — раскраска; contour — шаг изолиний, м; res до 160 |
| section | axis "x"/"z", at (формула) | classes: [{when(x,y,z), color, name}] по порядку или value(x,y,z)+min+max+color; mask(x,y,z); **разрезает** все тела перед собой (cut:false — не резать). Плоскость отдельно от тел: рисует вычисленное |
| water | level | bottom |
| tube | path [[x,y,z],…] (минимум 2 точки), radius | color, smooth |
| prefab | name: derrick, truck, tool; at | scale, rot |
| shape | shape: sphere, box, cylinder, ring, plane; at; size [x,y,z]; color или lith | glow, round (шар без преувеличения), clip:true |
| scatter | n, at, size (формулы от i, r1, r2, r3 ∈ 0..1), color | lith, shape sphere/box, round:false. Зёрна, обломки, организмы |
| particles | velocity [vx,vy,vz] м/с от x,y,z; box [[x,y,z],[x,y,z]]; color | n, size, speed (ускорение показа — назвать), where(x,y,z) — где можно быть |
| arrows | vector, box, color | grid [8,1,8], scale. Длина ~ корень из модуля |
| label | text с {формула:единица:знаков}, at | hot |
| column | at [x,z] или "picks"; value(x,y,z); top(x,z); bottom(x,z); min; max | color, good(x,y,z,v), good_color. Столбик свойств, как керн |

Цвета только из легенды, одно обозначение — одно значение: породы sand shale limestone dolomite dense reef salt anhydrite; флюиды oil gas water filtrate mud; кривые SP GR RES POR PRESSURE; measure (прибор), unc (неопределённость), steel, text, muted. lith — только породы.

## Графики (`charts`)
`{"id": "c1", "title": "…", "kind": "xy"|"depth", "x": {"var": "t"|параметр|своё имя, "min", "max", "unit", "label"}, "y": {"min", "max", "label"}, "lines": [{"expr", "color", "unit", "label", "dash"}], "cursor": "формула"}`. Если x.var — своё имя, оно доступно в expr. depth — ось x направлена вниз, как на планшете. По t линия рисуется до текущего момента.

## Игра (`steps`, по порядку)
- `predict`: q, options, answer (номер), why, misconception. **Первый шаг.** Ответ раскрывается в конце.
- `explore`: text, use, until (формула: когда можно дальше), button, title.
- `guess`: id, text, min, max, unit, truth (формула), log, label. Прогноз числа. Границы — в unit.
- `pick`: text, n, target (id surface/solid), score(x,z) ≥ 0, min_dist. Выбор мест, лучший план считается сам.
- `choose`: id, q, options: [{text, correct (формула), why}]. Верен ровно один в каждом случае; лучше, чтобы он зависел от случая.
- `reveal`: text. Ставит revealed=1, показывает прогноз против расчёта.
Общее: title, hint (строка над сценой), camera {yaw,pitch,zoom,target}, use: ["time", "param:k", "chart:c1", "read:front"].
Затем автоматически: разбор предположения, `transfer` {q, options, answer, why}, data_bridge, analogy {text, breaks_where}.

## Честность
`claims`: [{id, text (своими словами), quote (дословно из md), page}]. `checks`: минимум 3 условия физики {name, expr > 0, over: {x: [от, до, точек], t: [в единицах времени]}}. `examples`: числа автора {name, at: {t, параметр}, expr, unit, expect, tol}. `assumptions`, `exaggerations` — списки строк. `why_3d`, `misconception`.
Верхний уровень ещё: id, title, goal, intro, subtitle, node_id, difficulty {primary, secondary} (М В И Ф П Пр Н Р), provenance: "симуляция" или "схема", seed.
