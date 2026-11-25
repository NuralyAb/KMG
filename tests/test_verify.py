from glava.verify import (
    find_quote_page, numbers_in, quote_on_page, term_order_issues, unsupported_numbers, verify_layer,
)

PAGES = {
    90: "Оптимальная водоотдача\n(4—8 см³/ч) условия изучения разреза не ухудшает.",
    91: "Минерализация С фильтрата связана с сопротивлением $\\rho_ф$ и равна 1,5.",
}


def layer(**over):
    node = {
        "id": "lat.a", "order": 1, "title": "Водоотдача", "pages": [90],
        "layers": {"topic": f("Раствор"), "main": f("Водоотдача 4–8 см³/ч не мешает."), "mechanism": f("м"), "practice": f("п"),
                   "nuances": f("н"), "deeper": []},
        "claims": [{"id": "lat.a#c1", "text": "Водоотдача 4–8 см³/ч оптимальна.", "page_pdf": 90,
                    "quote": "Оптимальная водоотдача (4—8 см³/ч)"}],
        "terms_introduced": ["водоотдача"], "terms_used": [],
    }
    return {"chapter": "t", "source": "t.md", "nodes": [{**node, **over}]}


def f(text):
    return {"text": text, "by_model": True}


def test_quote_is_matched_ignoring_spaces_linebreaks_and_case():
    assert quote_on_page("оптимальная ВОДООТДАЧА (4—8 см³/ч)", PAGES[90])


def test_quote_with_changed_word_is_rejected():
    assert not quote_on_page("Оптимальная плотность (4—8 см³/ч)", PAGES[90])


def test_short_or_empty_quote_is_rejected():
    assert not quote_on_page("  ", PAGES[90])


def test_find_quote_page_returns_the_real_page():
    assert find_quote_page("Минерализация С фильтрата", PAGES) == 91
    assert find_quote_page("такого текста нет нигде", PAGES) is None


def test_numbers_are_normalised():
    assert numbers_in("от 4—8 см³/ч, 1,5 и 1.5, 10 %") == {"4", "8", "1.5", "10"}


def test_number_missing_from_source_is_reported():
    assert unsupported_numbers("Водоотдача 4–9", PAGES[90]) == {"9"}


def test_layer_with_wrong_page_is_reported_with_the_right_one():
    bad = layer()
    bad["nodes"][0]["claims"][0]["page_pdf"] = 91
    issues = verify_layer(bad, PAGES)
    assert any(i.code == "quote_wrong_page" and "90" in i.message for i in issues)


def test_layer_with_invented_number_is_reported():
    bad = layer()
    bad["nodes"][0]["layers"]["main"] = f("Водоотдача 77 см³/ч")
    assert any(i.code == "number_not_in_source" and "77" in i.message for i in verify_layer(bad, PAGES))


def test_correct_layer_has_no_issues():
    assert verify_layer(layer(), PAGES) == []


def test_term_used_before_it_is_introduced():
    doc = layer(terms_used=["пористость"])
    doc["nodes"].append({**doc["nodes"][0], "id": "lat.b", "order": 2, "terms_introduced": ["пористость"], "terms_used": []})
    assert any("пористость" in i.message for i in term_order_issues(doc["nodes"]))


def test_number_right_after_abbreviation_is_found():
    assert "72" in numbers_in("Рис.72. Кривые")
    assert numbers_in("12.50 и 3,5") == {"12.5", "3.5"}
