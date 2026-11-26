import pytest
from glava.modules.layer.builder import (
    assemble_node,
    coverage_rows,
    node_issues,
    plan_issues,
)
from glava.modules.source_text.units import Unit

UNITS = [
    Unit("p090.01", "heading", 90, "# Глава"),
    Unit("p090.02", "paragraph", 90, "Оптимальная водоотдача (4—8 см³/ч) не мешает исследованию разреза."),
    Unit("p090.03", "paragraph", 90, "Плотность раствора определяет давление в скважине."),
]


def plan(**over):
    node = {"slug": "mud", "title": "Раствор", "short_title": "Раствор и измерения", "why_here": "первый", "threshold": False,
            "difficulty": {"primary": "И", "secondary": None}, "unit_ids": ["p090.02", "p090.03"], "terms_introduced": ["водоотдача"]}
    return {"parts": [{"title": "Часть", "slugs": ["mud"]}], "nodes": [{**node, **over}],
            "skipped": [{"unit_id": "p090.01", "reason": "заголовок"}]}


def text(value):
    return {"text": value, "by_model": True}


def raw_node(quotes=("Оптимальная водоотдача (4—8 см³/ч)", "Плотность раствора определяет давление")):
    claims = [{"text": "Утверждение.", "kind": "observation", "page_pdf": 90, "unit_id": u, "quote": q, "source_kind": "text", "by_model": False}
              for u, q in zip(("p090.02", "p090.03"), quotes, strict=False)]
    return {"layers": {k: text("т") for k in ("topic", "main", "mechanism", "practice", "nuances")} | {"deeper": []},
            "claims": claims, "misconception": None, "prerequisites": [], "terms_used": [], "needs_scan": [],
            "data_meaning": {"from_chapter": text("д"), "breaks": text("л"), "hypotheses": []},
            "it_analogy": {"text": "а", "breaks_where": "г", "by_model": True}, "now_practice": None, "inefficiency_lens": None,
            "decision_on_data": None, "worked_examples": [], "book_tasks": [], "glossary": [{"term": "водоотдача", "definition": "…"}]}


def test_full_plan_has_no_issues():
    assert plan_issues(plan(), UNITS) == []


def test_uncovered_unit_is_reported():
    assert any("p090.03" in i for i in plan_issues(plan(unit_ids=["p090.02"]), UNITS))


def test_text_unit_cannot_be_skipped():
    bad = plan(unit_ids=["p090.02"])
    bad["skipped"].append({"unit_id": "p090.03", "reason": "слишком подробно"})
    assert any("p090.03" in i for i in plan_issues(bad, UNITS))


def test_term_explained_twice_is_reported():
    bad = plan()
    bad["nodes"].append({**bad["nodes"][0], "slug": "second"})
    assert any("водоотдача" in i for i in plan_issues(bad, UNITS))


def test_good_node_passes_schema_and_quote_checks():
    node = assemble_node(raw_node(), plan()["nodes"][0], order=1, prefix="lat", units=UNITS)
    assert node["id"] == "lat.mud" and node["claims"][0]["id"] == "lat.mud#c1" and node["pages"] == [90]
    assert node_issues(node, UNITS, plan()["nodes"][0]) == []


def test_invented_quote_is_reported():
    node = assemble_node(raw_node(("Такой фразы в книге нет совсем", "Плотность раствора определяет давление")),
                         plan()["nodes"][0], order=1, prefix="lat", units=UNITS)
    assert any("Такой фразы" in i for i in node_issues(node, UNITS, plan()["nodes"][0]))


def test_unit_without_any_claim_is_reported():
    raw = raw_node()
    raw["claims"] = raw["claims"][:1]
    node = assemble_node(raw, plan()["nodes"][0], order=1, prefix="lat", units=UNITS)
    assert any("p090.03" in i for i in node_issues(node, UNITS, plan()["nodes"][0]))


def test_coverage_lists_every_unit_with_node_or_reason():
    rows = coverage_rows(plan(), UNITS, "lat")
    assert [r["unit_id"] for r in rows] == [u.unit_id for u in UNITS]
    assert rows[0]["reason"] == "заголовок" and rows[1]["node_ids"] == ["lat.mud"]


# ---------- цитата не обрывается внутри формулы ----------
FORMULA_PAGE = "Перепишем:\n$$P = f \\left( \\xi, \\frac{Q_0 \\mu}{2\\pi k h} \\right)\n\\quad \\xi = \\frac{r}{2\\sqrt{\\kappa t}}. \\quad (23.43)$$\nПродифференцируем (23.43)."


@pytest.mark.parametrize("cut", [
    "$$P = f \\left( \\xi, \\frac{Q_0 \\mu}{2\\pi k h} \\right)",           # оборван конец
    "\\quad \\xi = \\frac{r}{2\\sqrt{\\kappa t}}. \\quad (23.43)$$",       # оборвано начало
    "\\frac{Q_0 \\mu}{2\\pi k h}",                                          # середина без долларов
])
def test_quote_cut_inside_a_formula_gets_the_whole_formula(cut):
    from glava.modules.layer.builder import whole_formulas
    from glava.shared.evidence import quote_on_page

    unit = Unit("p480.01", "paragraph", 480, FORMULA_PAGE)
    fixed = whole_formulas({"quote": cut, "conditions": [{"text": "у", "quote": cut}]}, [unit])
    for quote in (fixed["quote"], fixed["conditions"][0]["quote"]):
        assert quote.count("$$") == 2 and "(23.43)$$" in quote and quote.startswith("$$P")
        assert quote_on_page(quote, FORMULA_PAGE)


def test_whole_quotes_and_text_quotes_are_left_alone():
    from glava.modules.layer.builder import whole_formulas

    unit = Unit("p480.01", "paragraph", 480, FORMULA_PAGE)
    for quote in ("Продифференцируем (23.43).", FORMULA_PAGE):
        assert whole_formulas({"quote": quote}, [unit])["quote"] == quote
