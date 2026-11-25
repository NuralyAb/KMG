"""Вёрстка книг контрольной выборки: колонтитулы с номером страницы, подпись внутри абзаца, глава посреди страницы."""

import pytest
from glava.modules.layer.builder import plan_issues
from glava.modules.library.api import LibraryError
from glava.modules.source_text.units import parse_units
from glava.pipeline.chapter import cut_units

FOOTER = "© Центр профессиональной переподготовки специалистов нефтегазового дела ТПУ"


def _page(number: int, body: str, footer_first: bool) -> str:
    tail = f"{FOOTER}\n\n{number}" if footer_first else f"{number}\n\n{FOOTER}"
    return f"1.2. Дельты [Deltas]\n\n{body} на странице {number}, достаточно длинный абзац о дельте.\n\n{tail}"


PAGES = {n: _page(n, "Текст", n % 2 == 0) for n in range(30, 34)}


def test_running_lines_and_page_numbers_can_be_skipped():
    units = parse_units(PAGES)
    furniture = {u.text for u in units if u.skippable}
    assert furniture == {FOOTER, "1.2. Дельты [Deltas]", "30", "31", "32", "33"}
    assert not any(u.skippable for u in units if u.text.startswith("Текст"))
    # длинный колонтитул «© …» план может пропустить, абзац главы — нет
    footers = [u.unit_id for u in units if u.text == FOOTER]
    plan = {"nodes": [{"slug": "a", "unit_ids": [u.unit_id for u in units if not u.skippable], "terms_introduced": []}],
            "skipped": [{"unit_id": uid, "reason": "колонтитул"} for uid in footers], "parts": [{"slugs": ["a"]}]}
    assert not [i for i in plan_issues(plan, units) if "нельзя пропустить" in i]


def test_chapter_heading_is_not_taken_for_running_line():
    pages = {n: f"ГЛАВА XXIII\n\nАбзац страницы {n} о неустановившемся притоке к скважине.\n\n{n}" for n in range(1, 4)}
    pages[1] = "# Глава XXIII\n\n" + pages[1].split("\n\n", 1)[1]
    units = parse_units(pages)
    assert not next(u for u in units if u.text == "# Глава XXIII").skippable
    assert all(u.skippable for u in units if u.text == "ГЛАВА XXIII")


def test_running_lines_need_three_pages():
    units = parse_units({30: PAGES[30], 31: PAGES[31]})
    assert not any(u.skippable and not u.text.isdigit() for u in units)


def test_caption_glued_to_paragraph_becomes_its_own_unit():
    page = "Границами переходной зоны являются: вверху – подош внизу – зеркало воды, в интерв: Рис. 32. Определение положения ВНК по данным сопротивлений.\n\nДругой абзац (рис. 32)."
    units = parse_units({27: page})
    assert [u.kind for u in units] == ["paragraph", "figure", "paragraph"]
    assert units[1].text.startswith("Рис. 32. Определение")
    assert units[0].text.endswith("в интерв:")


def test_heading_with_caption_is_not_split():
    units = parse_units({107: "### Рис.77. Кривые зависимости. Рис. 78. Ещё одна"})
    assert len(units) == 1


def test_cut_units_drops_neighbour_sections():
    page = "Конец § 3 о безнапорном движении грунтовых вод.\n\n## § 4. Нестационарное движение\n\nАбзац § 4.\n\n## § 5. Газ\n\nАбзац § 5."
    units = cut_units("x", parse_units({38: page}), "## § 4.", "## § 5.")
    assert [u.text for u in units] == ["## § 4. Нестационарное движение", "Абзац § 4."]
    assert units[0].unit_id == "p038.02"


def test_cut_units_without_marks_keeps_everything():
    units = parse_units({38: "Абзац один.\n\nАбзац два."})
    assert cut_units("x", units, None, None) == units


def test_cut_units_fails_before_paid_steps_when_mark_is_missing():
    with pytest.raises(LibraryError, match="starts_at"):
        cut_units("x", parse_units({38: "Абзац."}), "## § 9.", None)
