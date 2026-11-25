"""Доверие к слою: сверка кодом, вердикты второй модели, чутьё проверок."""

import json

import pytest
import test_layer as tl
from glava.modules.layer.builder import assemble_node, chapter_block, node_issues
from glava.modules.library.registry import LibraryError
from glava.modules.llm.client import CACHE_BREAK, Reply
from glava.modules.llm.providers import _text_blocks
from glava.modules.source_text.units import Unit
from glava.modules.trust.audit import audit_layer, claim_flags, early_terms
from glava.modules.trust.entail import (
    claim_items,
    prose_items,
    trust_report,
    verdict_issues,
    verify_node,
)
from glava.modules.trust.mutate import MUTATORS, measure, mutants
from glava.pipeline.chapter import layer_of
from glava.pipeline.runtime import verifier_env
from glava.pipeline.steps.audit import build_audit
from glava.pipeline.steps.verify import build_verify
from glava.shared import paths
from glava.shared.json_files import read, save

QUOTE = "При увеличении глинистости проницаемость обычно снижается, порог 12 % не меняется"


@pytest.mark.parametrize(("text", "flag"), [
    ("При увеличении глинистости проницаемость обычно повышается, порог 12 % не меняется", "direction"),
    ("При увеличении глинистости проницаемость обычно снижается, порог 72 % не меняется", "number"),
    ("При увеличении глинистости проницаемость обычно снижается, порог 12 м не меняется", "unit"),
    ("При увеличении глинистости проницаемость обычно снижается, порог 12 % меняется", "negation"),
    ("При увеличении глинистости проницаемость всегда снижается, порог 12 % не меняется", "quantifier"),
    ("При увеличении глинистости проницаемость снижается, порог 12 % не меняется", "condition"),
])
def test_each_kind_of_damage_is_seen(text, flag):
    assert flag in claim_flags(text, QUOTE)


@pytest.mark.parametrize("text", [QUOTE, "С ростом глинистости проницаемость обычно падает, а порог 12 % не меняется (рис. 47)"])
def test_faithful_retelling_is_not_flagged(text):
    assert claim_flags(text, QUOTE) == []


def node(**over):
    claims = [{"id": "x.a#c1", "text": QUOTE, "quote": QUOTE, "page_pdf": 1}, {"id": "x.a#c2", "text": "Глина мешает потоку.", "quote": "Глина мешает потоку", "page_pdf": 1}]
    layers = {k: {"text": "Глина мешает потоку жидкости.", "by_model": True} for k in ("topic", "main", "mechanism", "practice", "nuances")}
    return {"id": "x.a", "order": 1, "claims": claims, "layers": {**layers, "deeper": []}, "terms_introduced": [], "worked_examples": [], "book_tasks": []} | over


def test_term_is_found_early_in_another_form():
    nodes = [node(layers={"main": {"text": "Микрозонды показывают многое.", "by_model": True}}), node(id="x.b", order=2, terms_introduced=["микрозондов"])]
    assert early_terms(nodes) == [{"term": "микрозондов", "explained_in": "x.b", "used_in": ["x.a"]}]


def test_audit_counts_and_lists():
    bad = {"id": "x.a#c3", "text": "Порог 99 %.", "quote": "Порог задан", "page_pdf": 1}
    report = audit_layer({"chapter": "x", "nodes": [node(claims=[*node()["claims"], bad])]})
    assert report["claims"] == 3 and [f["claim_id"] for f in report["flagged"]] == ["x.a#c3"] and report["by_flag"] == {"number": 1}


# ---------- порча
def test_mutants_are_damaged_and_repeatable():
    claims = node()["claims"]
    first = list(mutants(claims, seed=1))
    assert first == list(mutants(claims, seed=1)) and all(m.text != QUOTE for m in first)
    assert {m.kind for m in first} >= {"sign_flip", "number", "lost_condition", "overgeneralization", "negation_removed"}


def test_every_mutator_returns_a_new_text_or_nothing():
    for change in MUTATORS.values():
        assert change("Слово.") in (None,) or change("Слово.") != "Слово."


def test_blind_check_catches_nothing_and_a_sharp_one_catches_all():
    claims = node()["claims"]
    assert measure(claims, lambda t, q: [])["caught"] == 0
    sharp = measure(claims, lambda t, q: [] if t.rstrip(".") == q.rstrip(".") else ["x"])
    assert sharp["caught"] == sharp["made"] > 0 and sharp["recall"] == 1


def test_circular_damage_is_not_counted_for_the_code_check():
    assert not {"negation_added", "overgeneralization"} & set(measure(node()["claims"], lambda t, q: [])["kinds"])


def test_condition_quotes_count_as_the_source():
    claim = {"id": "x.a#c9", "text": "Если пласт однороден, порог 12 %.", "quote": "порог 12 %", "page_pdf": 1, "conditions": [{"text": "у", "quote": "пласт однороден, если"}]}
    assert claim_items(node(claims=[claim]))[0]["quote"] == "порог 12 % … пласт однороден, если"


# ---------- вторая модель
class Judge:
    name, model = "fake", "judge"

    def __init__(self, decide):
        self.decide, self.calls = decide, 0

    def ask(self, system, prompt, files=()):
        self.calls += 1
        listed = prompt.partition("# Фразы\n")[2] or prompt.partition("цитаты\n")[2]
        rows = json.JSONDecoder().raw_decode(listed)[0]
        return Reply(json.dumps({"verdicts": [self.decide(r) for r in rows]}), "judge", 1, 1, 0.01)


PROMPTS = {"claims": "c", "prose": "p"}


def test_verdicts_reach_the_report():
    def decide(row):
        is_bad = row["id"].endswith(("#c2", ":layers.main.text:1"))
        return {"id": row["id"], "verdict": "no" if is_bad else "follows", "claim_ids": [] if is_bad else ["x.a#c1"], "why": "нет"}

    claims, prose, replies = verify_node(Judge(decide), PROMPTS, node())
    report = trust_report("x", "fake/judge", claims, prose, [node()])
    assert report["claims"] == {"follows": 1, "partial": 0, "no": 1, "contradicts": 0, "unchecked": 0, "total": 2}
    assert report["prose"]["no"] == 1 and report["prose"]["total"] == 5 and report["text_chars"]["checked"] > 0 and len(replies) == 2
    assert {w["id"] for w in report["weak"]} == {"x.a#c2", "x.a:layers.main.text:1"}
    assert report["support"]["x.a:layers.topic.text:1"] == ["x.a#c1"]


def test_checker_without_json_means_unchecked():
    class Mute:
        name, model = "fake", "mute"

        def ask(self, system, prompt, files=()):
            return Reply("не знаю", "mute", 1, 1, 0.01)

    claims, prose, _ = verify_node(Mute(), PROMPTS, node())
    assert {r["verdict"] for r in (*claims, *prose)} == {"unchecked"}


def test_failed_checker_never_means_checked():
    claims, prose, _ = verify_node(Judge(lambda r: {"id": "чужой", "verdict": "follows"}), PROMPTS, node())
    assert {r["verdict"] for r in (*claims, *prose)} == {"unchecked"}


@pytest.mark.parametrize("rows", [
    [], [{"id": "a", "verdict": "да"}], [{"id": "a", "verdict": "follows", "claim_ids": []}], [{"id": "a", "verdict": "follows", "claim_ids": ["zz"]}],
    [{"id": ["a"], "verdict": "no"}], [{"verdict": "no", "claim_ids": ["zz"]}], [{"id": "a", "verdict": ["no"]}], [{"id": "a", "verdict": "follows", "claim_ids": [["c1"]]}],
    [{"id": "a", "verdict": "no", "claim_ids": []}] * 2, [{"id": "b", "verdict": "no", "claim_ids": []}], ["a"],
])
def test_bad_verdicts_are_refused(rows):
    assert verdict_issues({"verdicts": rows}, ["a"], {"c1"})


def test_short_phrases_are_not_sent():
    assert prose_items(node(layers={"main": {"text": "Да. Это фраза из пяти слов."}})) == [{"id": "x.a:layers.main.text:2", "text": "Это фраза из пяти слов."}]


# ---------- команды
@pytest.fixture
def root(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "WORKSPACE", tmp_path)
    save(tmp_path / "work" / "demo" / "layer.json", {"chapter": "demo", "nodes": [node()]})
    for name in ("verify_claims", "verify_prose"):
        (tmp_path / "prompts").mkdir(exist_ok=True)
        (tmp_path / "prompts" / f"{name}.md").write_text("п", encoding="utf-8")
    return tmp_path


def test_audit_command_needs_neither_book_nor_model(root):
    assert build_audit("demo")["sensitivity"]["made"] > 0
    assert read(root / "work" / "demo" / "audit.json")["claims"] == 2


def test_verify_command_measures_the_checker(root):
    judge = Judge(lambda r: {"id": r["id"], "verdict": "follows" if r.get("text") in (QUOTE, "Глина мешает потоку.") or ":" in r["id"] else "contradicts", "claim_ids": ["x.a#c1"]})
    report = build_verify("demo", judge, True)
    assert report["claims"]["follows"] == 2 and report["sensitivity"]["recall"] == 1
    assert report["sensitivity"]["controls"] == {"made": 2, "caught": 0} and len(report["layer_sha256"]) == 64


def test_mute_checker_has_no_measured_sharpness(root):
    class Mute(Judge):
        def ask(self, system, prompt, files=()):
            return Reply("молчу" if '"m' in prompt else super().ask(system, prompt).text, "j", 1, 1, 0.0)

    judge = Mute(lambda r: {"id": r["id"], "verdict": "follows", "claim_ids": ["x.a#c1"]})
    found = build_verify("demo", judge, True)["sensitivity"]
    assert found["recall"] is None and found["made"] == 0 and found["unchecked"] > 0
    assert "verify" in (root / "metrics.csv").read_text(encoding="utf-8")


def test_verify_without_a_single_verdict_fails(root):
    class Mute(Judge):
        def ask(self, system, prompt, files=()):
            return Reply("молчу", "j", 1, 1, 0.0)

    with pytest.raises(LibraryError, match="ни одного вердикта"):
        build_verify("demo", Mute(None), False)
    assert read(root / "work" / "demo" / "trust.json")["text_chars"]["checked"] == 0


@pytest.mark.parametrize("name", ["../x", "absent", ""])
def test_unknown_layer_is_explained(root, name):
    with pytest.raises(LibraryError):
        layer_of(name)


def test_checker_model_is_chosen_separately():
    assert verifier_env({"LLM_MODEL": "a", "LLM_VERIFY_MODEL": "b"})["LLM_MODEL"] == "b"
    assert verifier_env({"LLM_MODEL": "a"})["LLM_MODEL"] == "a"


# ---------- контекст главы
def test_whole_chapter_stands_before_the_node_and_can_be_turned_off():
    assert all(u.text in chapter_block(tl.UNITS, {}) for u in tl.UNITS)
    assert chapter_block(tl.UNITS, {"GLAVA_CONTEXT": "node"}) == ""


def test_shared_beginning_is_cached_separately():
    shared, own = _text_blocks(f"глава{CACHE_BREAK}узел")
    assert shared["cache_control"] and shared["text"] == "глава" and own == {"type": "text", "text": "узел"}
    assert _text_blocks("просто") == [{"type": "text", "text": "просто"}]


def test_quote_from_another_node_is_reported():
    units = [*tl.UNITS, Unit("p090.04", "paragraph", 90, "Соседний узел говорит совсем о другом предмете.")]
    plan = tl.plan()["nodes"][0]
    made = assemble_node(tl.raw_node(("Соседний узел говорит совсем о другом", "Плотность раствора определяет давление")), plan, 1, "lat", units)
    assert any("не из единиц узла" in i for i in node_issues(made, units, plan))


@pytest.mark.parametrize(("condition", "is_good"), [
    ({"text": "у плотного раствора", "quote": "Плотность раствора определяет"}, True), ({"text": "т", "quote": "этого автор не писал"}, False), ("строка", False), ({"text": "", "quote": "Плотность раствора"}, False),
])
def test_conditions_must_be_in_the_chapter(condition, is_good):
    raw = tl.raw_node()
    raw["claims"][0]["conditions"] = [condition]
    plan = tl.plan()["nodes"][0]
    issues = node_issues(assemble_node(raw, plan, 1, "lat", tl.UNITS), tl.UNITS, plan)
    assert (not any("условия" in i for i in issues)) is is_good
