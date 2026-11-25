"""Правило ϰ→π: у Баренблатта распознаватель читает пьезопроводность ϰ как π."""

from glava.modules.errata.api import not_caught
from glava.modules.source_text.api import kappa_suspects, parse_units
from glava.pipeline.chapter import Chapter, errata_of
from glava.shared import paths
from glava.shared.json_files import save

# первые строки пишут ϰ верно (так глава объявляет обозначение), дальше — подмены со страницы 43 книги
PAGE_41 = ("Асимптотика при $L^2/\\varkappa t \\gg 1$ и при малых временах $\\varkappa t \\ll L^2$.\n\n"
           "$$x/2\\sqrt{\\varkappa t}$$\n\n$$\\exp(-\\pi^2 \\varkappa t/L^2)$$")
PAGE_43 = ("$$p(r, t) = 2^{-1} p^* E_i (-r^2/4\\pi t). \\tag{II.107}$$\n\n"
           "$$p = Q_\\mu (4\\pi k h)^{-1} \\ln(2,25\\pi t/\\rho^2), \\tag{II.108}$$\n\n"
           "$$I_0(z) \\approx e^z (2\\pi z)^{-1/2}, \\quad K_0(z) \\approx e^{-z} (\\pi/2z)^{1/2}$$\n\n"
           "Отношение $\\pi/\\rho^2$ и $\\pi = 0,57r^2/t_1$.")


def units(first=PAGE_41):
    return parse_units({41: first, 43: PAGE_43})


def test_swapped_kappa_is_found_and_real_pi_is_left():
    found = kappa_suspects(units())
    wrong = [(e["page"], e["md"], e["scan"]) for e in found]
    assert all(page == 43 for page, _, _ in wrong), "π² перед ϰt на странице 41 — настоящее π"
    joined = " ".join(scan for _, _, scan in wrong)
    for fixed in ("4\\varkappa t", "2,25\\varkappa t", "\\varkappa/\\rho^2", "\\varkappa = 0,57"):
        assert fixed in joined
    assert "2\\varkappa z" not in joined and "\\varkappa/2z" not in joined, "π в асимптотиках Бесселя — настоящее"
    assert "4\\varkappa k h" not in joined, "2πkh и 4πkh не трогаются"
    assert all(e["kind"] == "recognition" and e["md"] in u.text for e in found for u in units() if u.unit_id == e["unit_id"])


def test_rule_is_silent_when_chapter_has_no_kappa():
    assert kappa_suspects(units("Глава без пьезопроводности.")) == []


def test_entries_already_in_model_list_are_not_repeated():
    found = kappa_suspects(units())
    model = [{**found[0], "scan": "как в книге"}]
    assert len(not_caught(found, model)) == len(found) - 1


def test_rule_entries_reach_the_layer_through_errata_of(tmp_path, monkeypatch):
    from glava.pipeline.steps.errata import build_errata

    monkeypatch.setattr(paths, "WORKSPACE", tmp_path)
    chapter = Chapter("c", "c", "t", "b", tmp_path, tuple(units()), "c.md")
    save(chapter.errata_file.with_suffix(".manual.json"), {"entries": [{"page": 43, "md": "руками", "scan": "x", "kind": "recognition"}]})
    build_errata(chapter, provider=None)
    entries = errata_of(chapter)
    assert any("4\\varkappa t" in e["scan"] for e in entries) and any(e["md"] == "руками" for e in entries)
