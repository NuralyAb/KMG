import json

import pytest
from glava.modules.course.build import build_course
from glava.modules.simulations.publish import bound_scene, publish_simulations
from test_course_build import LAYER, TASKS, read_data

SCENE = {"id": "s", "title": "Проба", "intro": "вводная", "provenance": "симуляция", "sources": [{"claim": "старое", "page": 1}]}


def chapter(tmp_path, steps, scene=None):
    (tmp_path / "simulations").mkdir()
    (tmp_path / "simulations" / "log.json").write_text(json.dumps(scene or SCENE), encoding="utf-8")
    config = tmp_path / "simulations.json"
    config.write_text(json.dumps({"steps": steps}), encoding="utf-8")
    return config


def player(tmp_path):
    folder = tmp_path / "player"
    folder.mkdir()
    (folder / "player.html").write_text("x", encoding="utf-8")
    return folder


GOOD = {"lat.a": [{"scene": "log", "claims": ["lat.a#c1"]}]}


def test_sources_come_from_the_layer(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    blocks = publish_simulations(LAYER, chapter(tmp_path, GOOD), player(tmp_path), out)
    scenes = json.loads((out / "simulations.js").read_text(encoding="utf-8").removeprefix("globalThis.SIM_SCENES=").rstrip(";\n"))["scenes"]
    assert scenes["log"]["sources"] == [{"claim": "Плотность раствора определяет давление в скважине.", "page": 90, "claim_id": "lat.a#c1"}]
    assert scenes["log"]["node_id"] == "lat.a"
    assert blocks["lat.a"]["interactive"]["params"]["items"][0]["title"] == "Проба"
    assert (out / "assets" / "sim" / "player.html").exists()


@pytest.mark.parametrize(("steps", "message"), [
    ({"lat.zzz": GOOD["lat.a"]}, "неизвестных шагов"),
    ({"lat.a": [{"scene": "log", "claims": ["lat.a#c99"]}]}, "в слое нет утверждений"),
    ({"lat.a": [{"scene": "log", "claims": []}]}, "нет утверждений слоя"),
    ({"lat.a": [{"scene": "../log", "claims": ["lat.a#c1"]}]}, "недопустимое имя"),
])
def test_broken_binding_is_an_error(tmp_path, steps, message):
    with pytest.raises(ValueError, match=message):
        publish_simulations(LAYER, chapter(tmp_path, steps), player(tmp_path), tmp_path / "out")


def test_unknown_label_is_refused():
    with pytest.raises(ValueError, match="метка"):
        bound_scene({**SCENE, "provenance": "фото"}, ["lat.a#c1"], {"lat.a#c1": LAYER["nodes"][0]["claims"][0]})


def test_course_without_simulations_stays_light(tmp_path):
    out = build_course(LAYER, {"routes": []}, TASKS, [], tmp_path / "out", simulations=tmp_path / "none.json")
    assert not (out / "assets" / "sim").exists() and not (out / "simulations.js").exists()
    assert read_data(out)["steps"][0]["interactive"] is None


def test_course_with_simulations(tmp_path):
    out = build_course(LAYER, {"routes": []}, TASKS, [], tmp_path / "out", simulations=chapter(tmp_path, GOOD))
    assert read_data(out)["steps"][0]["interactive"]["kind"] == "simulation"
    page = (out / "index.html").read_text(encoding="utf-8")
    assert page.index("simulation.js") < page.index("course.js\"")


def test_removed_simulations_disappear_after_rebuild(tmp_path):
    config = chapter(tmp_path, GOOD)
    out = build_course(LAYER, {"routes": []}, TASKS, [], tmp_path / "out", simulations=config)
    config.write_text(json.dumps({"steps": {}}), encoding="utf-8")
    build_course(LAYER, {"routes": []}, TASKS, [], out, simulations=config)
    assert not (out / "simulations.js").exists() and not (out / "assets" / "sim").exists()


def test_other_extras_of_the_step_survive(tmp_path):
    extras = {"lat.a": {"procedure": [{"text": "шаг"}]}}
    out = build_course(LAYER, {"routes": []}, TASKS, [], tmp_path / "out", extras=extras, simulations=chapter(tmp_path, GOOD))
    step = read_data(out)["steps"][0]
    assert step["procedure"] and step["interactive"]["kind"] == "simulation"
