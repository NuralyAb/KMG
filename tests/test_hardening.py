"""Дефекты, найденные ревью: чужие пути, кривые ответы модели, лазейки проверки."""

import json
from pathlib import Path

import pytest
import test_layer as tl
from test_illustrations import NODES, STYLE, TEMPLATES, scene
from test_review import PACKAGE, PAGES, PROMPTS, REMARK, Scripted

from glava.llm import BudgetExceeded, Reply, ask_json, cached, metered
from glava.review.engine import load_package, review_package, workspace
from glava.scenes import scene_issues
from glava.scenes.formula import evaluate
from glava.stages.illustrations import illustration_issues
from glava.stages.layer import assemble_node, drop_unsupported, plan_issues, repair_pages
from glava.stages.tasks import make_tasks
from glava.units import Unit
from glava.verify import verify_layer


class Says:
    name, model = "fake", "fake"

    def __init__(self, *answers, cost=0.0):
        self.answers, self.cost, self.calls = list(answers), cost, 0

    def ask(self, system, prompt, files=()):
        self.calls += 1
        return Reply(self.answers[min(self.calls, len(self.answers)) - 1], "fake", 1, 1, self.cost)


# ---------- чужой пакет
def package_folder(tmp_path, **over):
    folder = tmp_path / "pack"
    (folder / "frames").mkdir(parents=True)
    (folder / "package.json").write_text(json.dumps({**PACKAGE, **over}), encoding="utf-8")
    (folder / "frames" / "F01.png").write_bytes(b"png")
    return folder


FRAME = {"id": "F01", "video_id": "v", "file": "frames/F01.png", "t": 1, "frame_class": "A", "label": "схема", "shows": "разрез"}


def test_good_package_is_loaded(tmp_path):
    assert load_package(package_folder(tmp_path, frames=[FRAME]))["package_id"] == "p"


@pytest.mark.parametrize("over", [
    {"frames": [{**FRAME, "file": "../../key.json"}]}, {"frames": [{**FRAME, "file": "C:/secret.png"}]}, {"package_id": "../../x"},
    {"items": [{"id": "C1", "type": "claim"}]}, {"frames": [{**FRAME, "file": "frames/F01.json"}]},
])
def test_bad_package_is_refused(tmp_path, over):
    with pytest.raises(ValueError):
        load_package(package_folder(tmp_path, **over))


@pytest.mark.parametrize("name", ["..", ".", ""])
def test_workspace_never_leaves_its_root(tmp_path, name):
    root = tmp_path / "work" / "review"
    keep = tmp_path / "work" / "layer.json"
    root.mkdir(parents=True)
    keep.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError):
        workspace(package_folder(tmp_path), root, name)
    assert keep.exists()


def test_workspace_copies_only_images(tmp_path):
    source = package_folder(tmp_path)
    (source / "frames" / "key.txt").write_text("ответы", encoding="utf-8")
    target = workspace(source, tmp_path / "work", "pack")
    assert {p.name for p in target.rglob("*") if p.is_file()} == {"package.json", "F01.png"}


def test_text_confidence_and_fake_quote_do_not_break_the_answer():
    class Odd(Scripted):
        def ask(self, system, prompt, files=()):
            reply = super().ask(system, prompt, files)
            return Reply(reply.text.replace('"confidence": 90', '"confidence": "90"'), "fake", 1, 1, 0.0)

    answer, _ = review_package(PACKAGE, PAGES, Odd([{**REMARK, "quote": "этого автор не писал никогда"}], {"C001"}), PROMPTS, "")
    assert answer["remarks"][0]["quote"] is None
    assert answer["remarks"][0]["page_pdf"] == 9


# ---------- ответы модели
def test_validator_crash_becomes_a_remark_for_the_model():
    def check(data):
        return [] if data.get("ok") else ["нет"]

    provider = Says("[1]", '{"ok": true}')
    assert ask_json(provider, "s", "p", check)[0] == {"ok": True}


def test_newline_slug_is_refused():
    assert plan_issues(tl.plan(slug="mud\n"), tl.UNITS)
    assert plan_issues(tl.plan(slug="../x"), tl.UNITS)


def test_invalid_tasks_are_dropped_one_by_one():
    nodes = [{"id": "lat.a", "title": "т", "claims": [{"id": "lat.a#c1", "text": "т"}], "layers": {}}]
    good = {"id": "t1", "type": "single", "step_id": "lat.a", "claim_ids": ["lat.a#c1"], "prompt": "Что?", "answer": "a",
            "options": [{"id": "a", "text": "1"}, {"id": "b", "text": "2"}], "explanation": "Так.", "kind": "recall"}
    answer = json.dumps({"tasks": [good, {"type": "calc"}, {**good, "id": "t2", "answer": "z"}]})
    found, _ = make_tasks(Says(answer), "s", nodes)
    assert [t["id"] for t in found] == ["t1"]


def test_budget_stops_the_run():
    provider = metered(Says("{}", cost=1.0), budget_usd=1.5)
    provider.ask("s", "1")
    provider.ask("s", "2")
    with pytest.raises(BudgetExceeded):
        provider.ask("s", "3")


def test_broken_cache_file_is_a_miss(tmp_path):
    inner = Says("ответ")
    provider = cached(inner, tmp_path)
    provider.ask("s", "p")
    next(tmp_path.glob("*.json")).write_text('{"text": "об', encoding="utf-8")
    assert provider.ask("s", "p").text == "ответ"
    assert inner.calls == 2


# ---------- лазейки проверки
def node_with(**over):
    plan = tl.plan()
    return assemble_node({**tl.raw_node(), **over}, plan["nodes"][0], 1, "x", tl.UNITS)


PAGE_TEXT = {90: "\n".join(u.text for u in tl.UNITS)}


@pytest.mark.parametrize("over", [
    {"misconception": {"ref": "misc.a", "text": "Порог 77 %.", "by_model": True}},
    {"data_meaning": {"from_chapter": tl.text("77 столбцов"), "breaks": tl.text(""), "hypotheses": []}},
    {"it_analogy": {"text": "Как 77 серверов.", "breaks_where": "", "by_model": True}},
    {"glossary": [{"term": "водоотдача", "definition": "Обычно 77."}]},
    {"decision_on_data": {"features": ["77"], "rule": "", "conclusion": "", "counterexample": ""}},
])
def test_invented_numbers_are_found_in_every_field(over):
    assert any("77" in i.message for i in verify_layer({"nodes": [node_with(**over)]}, PAGE_TEXT))


def test_unit_of_a_claim_is_set_by_its_quote():
    raw = tl.raw_node()
    swapped = {**raw, "claims": [{**c, "unit_id": "p090.02"} for c in raw["claims"]]}
    node = assemble_node(swapped, tl.plan()["nodes"][0], 1, "x", tl.UNITS)
    assert [c["unit_id"] for c in node["claims"]] == ["p090.02", "p090.03"]


def test_figure_description_is_never_shown_as_the_author():
    units = [tl.UNITS[0], tl.UNITS[1], Unit("p090.03", "figure", 90, tl.UNITS[2].text, by_recogniser=True)]
    node = assemble_node(tl.raw_node(), tl.plan()["nodes"][0], 1, "x", units)
    assert node["claims"][1]["source_kind"] == "figure_description_model"
    assert node["claims"][1]["by_model"] is True


def test_right_page_is_kept_when_the_quote_repeats():
    node = {"claims": [{"quote": "повторяющаяся цитата", "page_pdf": 7}]}
    pages = {5: "повторяющаяся цитата", 7: "повторяющаяся цитата"}
    assert repair_pages(node, pages)["claims"][0]["page_pdf"] == 7


def test_number_from_another_page_does_not_keep_a_claim():
    node = {**node_with(), "pages": [90]}
    claims = [{**node["claims"][0], "text": "Порог 55 %."}]
    _, dropped = drop_unsupported({**node, "claims": claims}, {**PAGE_TEXT, 91: "Всего 55."})
    assert dropped == [claims[0]["id"]]


# ---------- рисунки
PLOT = {"x_label": "x", "y_label": "y", "numeric": True, "params": {}, "series": [{"name": "к", "formula": "7.77 * x", "from": 5, "to": 20}]}


def test_numbers_inside_a_formula_are_checked():
    bad = illustration_issues({"illustrations": [scene(template="plot", data=PLOT)]}, NODES, TEMPLATES, STYLE)
    assert any("7.77" in i for i in bad)
    fine = {**PLOT, "series": [{"name": "к", "formula": "20 * x + 5", "from": 5, "to": 20}]}
    assert illustration_issues({"illustrations": [scene(template="plot", data=fine)]}, NODES, TEMPLATES, STYLE) == []


def test_big_numbers_keep_their_digits():
    node = [{**NODES[0], "claims": [{**NODES[0]["claims"][0], "text": "Объём 1500000 и 123456,7 м."}]}]
    data = {"unit": "м", "items": [{"name": "а", "value": 1500000}, {"name": "б", "value": 123456.7}]}
    assert illustration_issues({"illustrations": [scene(data=data, caption="Объём", alt="Объём")]}, node, TEMPLATES, STYLE) == []


@pytest.mark.parametrize("formula", ["10**50*10**50*10**50*10**50*10**50*10**50*10**50", "(((9**50)**50)**50)**50", "exp(9999)"])
def test_huge_formula_is_refused_quickly(formula):
    with pytest.raises(ValueError):
        evaluate(formula, {})


def test_fault_trap_rises_to_the_fault_and_special_layers_have_their_place():
    template = TEMPLATES["section"]
    seal, sand = {"lithology": "shale", "label": "покрышка"}, {"lithology": "sand", "label": "пласт", "fluids": ["oil", "water"]}
    base = {"lithology": "shale", "label": "глина"}
    fault = {"shape": "fault", "layers": [seal, sand, base]}
    assert template.tops(fault, 0.5)[1] < template.tops(fault, 0.0)[1]
    assert scene_issues(template, {"shape": "pinchout", "layers": [base, seal, sand]}, STYLE)
    assert scene_issues(template, {"shape": "reef", "layers": [seal, {**sand, "fluids": []}, base]}, STYLE)


def test_course_escapes_pages():
    folder = Path(__file__).resolve().parents[1] / "engine/glava/course/assets"
    script = "".join(f.read_text(encoding="utf-8") for f in sorted(folder.glob("*.js")))
    assert "list.map(esc).join" in script
    assert "list.join" not in script


def test_failed_answers_are_not_kept_for_the_next_run(tmp_path):
    inner = Says('{"n": 1}')
    for _ in range(2):
        ask_json(cached(inner, tmp_path), "s", "p", lambda d: ["плохо"], attempts=2)
    assert inner.calls == 4


def test_good_answers_stay_in_the_cache(tmp_path):
    inner = Says('{"n": 1}')
    for _ in range(2):
        ask_json(cached(inner, tmp_path), "s", "p", lambda d: [], attempts=2)
    assert inner.calls == 1


def test_unknown_price_is_refused():
    from glava.llm.providers import ProviderUnavailable, provider_from_env

    with pytest.raises(ProviderUnavailable):
        provider_from_env({"LLM_PROVIDER": "anthropic", "LLM_MODEL": "новая-модель"})
