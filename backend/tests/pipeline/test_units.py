from glava.modules.source_text.units import parse_units, read_pages

MD = """<!-- page 4 -->
Не наша страница.
<!-- page 5 -->
# Глава I

Первый абзац про пласт.

$$k = a + b,$$

где a - первое число.

| Метод | Признак |
|---|---|
| ПС | минимум |

Задача

85. Выделить коллекторы по диаграмме (рис.67).
<!-- page 6 -->
Рис. 68. Кривые ПС и ГК.

━━━ FORMAT 2: WELL LOG / КАРОТАЖНАЯ ДИАГРАММА ━━━

Глубина: 2190–2250 м.

1. Глубина, м: 2190.
----
Абзац после рисунка.
<!-- page 7 -->
Тоже не наша.
"""


def test_read_pages_keeps_only_requested_range():
    pages = read_pages(MD, [(5, 6)])
    assert sorted(pages) == [5, 6]
    assert "Первый абзац" in pages[5]


def test_units_have_stable_ids_and_pages():
    units = parse_units(read_pages(MD, [(5, 6)]))
    assert units[0].unit_id == "p005.01"
    assert all(u.unit_id.startswith(f"p{u.page_pdf:03d}.") for u in units)
    assert len({u.unit_id for u in units}) == len(units)


def test_unit_kinds_are_recognised():
    kinds = {u.kind for u in parse_units(read_pages(MD, [(5, 6)]))}
    assert {"heading", "paragraph", "formula", "table", "task", "figure"} <= kinds


def test_figure_description_block_is_one_unit():
    figures = [u for u in parse_units(read_pages(MD, [(6, 6)])) if u.kind == "figure"]
    described = [u for u in figures if "FORMAT 2" in u.text]
    assert len(described) == 1
    assert "2190." in described[0].text
    assert "Абзац после рисунка" not in described[0].text


def test_no_text_is_lost_between_units():
    pages = read_pages(MD, [(5, 6)])
    squeezed = "".join("".join(u.text for u in parse_units(pages)).split()).replace("----", "")
    original = "".join("".join(pages.values()).split()).replace("----", "")
    assert squeezed == original


def test_blocks_written_by_the_recogniser_are_marked():
    described = [u for u in parse_units(read_pages(MD, [(6, 6)])) if "FORMAT 2" in u.text]
    assert described[0].by_recogniser is True
