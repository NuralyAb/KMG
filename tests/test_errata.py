"""Лист опечаток: расхождения md со сканом попадают в подсказку узла, цитата остаётся дословной."""

import json

from glava.llm import Reply
from glava.stages.errata import errata_issues, for_pages, make_errata, number_sources, prompt_block, suspects_in
from glava.verify import verify_layer

PAGES = {96: "Пределы (1-10) · 10³ мкм². Коэффициент k_n больше 5.", 97: "Текст."}
ENTRY = {"page": 96, "md": "k_n больше 5", "scan": "kв больше 7", "kind": "recognition", "note": "индекс"}


class Fake:
    name, model = "fake", "fake"

    def __init__(self, answer):
        self.answer, self.files = answer, []

    def ask(self, system, prompt, files=()):
        self.files = list(files)
        return Reply(json.dumps(self.answer, ensure_ascii=False), "fake", 1, 1, 0.0)


def test_entry_must_quote_the_page():
    assert errata_issues({"entries": [ENTRY]}, PAGES[96]) == []
    assert errata_issues({"entries": [{**ENTRY, "md": "такого текста нет"}]}, PAGES[96])
    assert errata_issues({"entries": [{**ENTRY, "scan": ENTRY["md"]}]}, PAGES[96])
    assert errata_issues({"entries": [{**ENTRY, "kind": "догадка"}]}, PAGES[96])
    assert errata_issues({}, PAGES[96])


def test_make_errata_keeps_only_valid_entries(tmp_path):
    image = tmp_path / "p.png"
    image.write_bytes(b"x")
    fake = Fake({"entries": [ENTRY, {**ENTRY, "md": "нет на странице"}]})
    found, _ = make_errata(fake, "s", 96, PAGES[96], image)
    assert found == [ENTRY]
    assert fake.files == [image]


def test_prompt_block_lists_only_own_pages():
    block = prompt_block(for_pages([ENTRY], [96]))
    assert "kв больше 7" in block
    assert "дословно" in block
    assert prompt_block(for_pages([ENTRY], [97])) == ""


def test_numbers_from_the_scan_are_supported_but_quotes_stay_verbatim():
    node = {"id": "n", "order": 1, "pages": [96], "terms_introduced": [],
            "layers": {k: {"text": ""} for k in ("topic", "main", "mechanism", "practice", "nuances")},
            "claims": [{"id": "n#c1", "text": "kв больше 7.", "quote": "Коэффициент k_n больше 5", "page_pdf": 96}]}
    assert [i.code for i in verify_layer({"nodes": [node]}, PAGES)] == ["number_not_in_source"]
    assert verify_layer({"nodes": [node]}, PAGES, number_sources([ENTRY])) == []
    fake_quote = {**node, "claims": [{**node["claims"][0], "quote": "Коэффициент kв больше 7"}]}
    assert "quote_not_found" in [i.code for i in verify_layer({"nodes": [fake_quote]}, PAGES, number_sources([ENTRY]))]


def test_partly_overlapping_quote_meets_the_suspect():
    suspect = {**ENTRY, "kind": "suspect", "md": "(1-10) · 10³ мкм², для газовых - (0,1-1) · 10³ мкм²"}
    assert suspects_in(["Для нефтеносных коллекторов оно лежит в пределах (1-10) · 10³ мкм²"], [suspect]) == [suspect]
    assert suspects_in(["Критическое значение зависит от свойств флюидов"], [suspect]) == []
    assert suspects_in(["(1-10) · 10³ мкм²"], [{**suspect, "kind": "recognition"}]) == []
