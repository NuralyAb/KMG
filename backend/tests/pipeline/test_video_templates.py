"""Шаблоны роликов: физика модели состояния, отказ от неверных сцен, рисование без ошибок в обоих форматах."""

import json
import math

import pytest
from glava.shared import paths

pytest.importorskip("cairo")

from glava.modules.drawing.api import load_module, load_style  # noqa: E402
from glava.modules.video.overlay import LAYOUTS  # noqa: E402
from glava.modules.video.render import frame  # noqa: E402
from glava.modules.video.speech import Speech  # noqa: E402
from glava.modules.video.timeline import place  # noqa: E402
from glava.modules.video.voices import Word  # noqa: E402

DOMAIN = paths.workspace() / "domain"
PRESSURE = {"p0": 20, "unit": "МПа", "drop": 0.5, "kappa": 1.0, "t_max": 36000, "stop": 24000, "radius": 400, "rw": 0.1, "thickness": 10, "observe": 120, "lith": "sand"}
REEF = {"sea": [[0, 10], [0.45, 60], [0.6, 30], [1, 120]], "max_growth": 110, "photic": 40, "erosion": 40, "base": 0, "half_width": 800, "slope": 0.6,
        "zones": [{"key": "core", "label": "ядро"}], "observe": 0.0}
KICK = {"depth": 3000, "density": 1250, "area": 0.03, "gas": 2.0, "hole_mm": 216, "casing": 1800, "formation": 38}
INVASION = {"mode": "neutron", "depth_max": 0.6, "contact": 2, "cased": True, "probes": [{"label": "НГК", "depth": 0.4, "curve": "NEUTRON"}], "layers": [
    {"label": "газ", "lith": "sand", "fluid": "gas", "perm": 0.9, "native": 3.0, "invaded": 1.5}, {"label": "газ, плохая", "lith": "sand", "fluid": "gas", "perm": 0.3, "native": 3.0, "invaded": 1.5},
    {"label": "нефть", "lith": "sand", "fluid": "oil", "perm": 0.6, "native": 1.4, "invaded": 1.4}]}
WELL = {"show_drilling": True, "depth_top": 0, "depth_bottom": 8, "depth_tick": 2, "curves": [{"key": "CALIPER", "prop": "d", "label": "диаметр", "unit": "", "min": 0.7, "max": 1.4}], "layers": [
    {"top": 0, "bottom": 4, "lith": "shale", "label": "глина", "fluid": None, "permeable": False, "wall": 1.25, "cake": 0, "props": {}},
    {"top": 4, "bottom": 8, "lith": "sand", "label": "коллектор", "fluid": "water", "permeable": True, "wall": 1.0, "cake": 0.08, "props": {}}]}
SCENES = [("geology", "invasion_zone", INVASION, [{"invade": 1, "tracks": 1}, {"casing": 1}, {"dissipate": 1, "history": 1}, {"contact": 1}]),
          ("geology", "well_tool_curve", WELL, [{"drill": 1}, {"pull": 1, "washout": 1}, {"tool": 1, "cake": 1}]),
          ("geology", "pressure_wave", PRESSURE, [{"time": 0.4, "observe": 1}, {"time": 1, "naive": 1}, {"true_scale": 1}]),
          ("geology", "reef_growth", REEF, [{"time": 0.6, "pores": 1}, {"time": 1, "zones": 1, "well": 1}, {"true_scale": 1}]),
          ("drilling", "gas_kick", KICK, [{"open": 0.2, "scales": 1, "pit": 1}, {"shut": 1}, {"closed": 1}, {"true_scale": 1}])]


def template(domain, name):
    return load_module(DOMAIN / domain / "video" / f"{name}.py")


def beat(action):
    return {"say": "слово", "claim_id": None, "on_screen": "Подпись", "label": "симуляция", "frame_class": "A", "action": action, "is_analogy": False, "pause_after": 0, "role": "step"}


@pytest.mark.parametrize(("domain", "name", "params", "actions"), SCENES, ids=[s[1] for s in SCENES])
@pytest.mark.parametrize("kind", list(LAYOUTS))
def test_scene_draws_in_both_formats(domain, name, params, actions, kind):
    scene, beats = template(domain, name), [beat({}), *(beat(a) for a in actions)]
    assert scene.check(params, beats) == []
    placed, total = place(beats, [Speech(None, 2.0, (Word(0, 1.8, "слово"),)) for _ in beats])
    spec = {"format": kind, "params": params, "plaque": [scene.plaque(params, kind)], "prediction_question": "?"}
    blank = bytes(frame(0.0, spec, placed, scene, load_style(DOMAIN / domain)).get_data())
    assert bytes(frame(total - 0.1, spec, placed, scene, load_style(DOMAIN / domain)).get_data()) != blank


@pytest.mark.parametrize(("domain", "name", "params", "actions"), SCENES, ids=[s[1] for s in SCENES])
def test_unknown_action_and_missing_params_are_refused(domain, name, params, actions):
    scene = template(domain, name)
    assert scene.check(params, [beat({"чудо": 1})])
    assert scene.check({}, [beat({})])


def test_exponential_integral_matches_the_tables():
    e1 = template("geology", "pressure_wave").e1
    for x, value in ((0.01, 4.03793), (0.5, 0.55977), (1.0, 0.21938), (5.0, 0.0011483)):
        assert e1(x) == pytest.approx(value, rel=1e-4)


def test_pressure_wave_physics():
    scene = template("geology", "pressure_wave")
    drops = [scene.drop_at(PRESSURE, r, 10000) for r in (0.1, 10, 100, 300)]
    assert drops == sorted(drops, reverse=True) and drops[-1] > 0
    assert scene.drop_at(PRESSURE, 100, 20000) > scene.drop_at(PRESSURE, 100, 5000)
    assert scene.reach(PRESSURE, 4000) == pytest.approx(2 * scene.reach(PRESSURE, 1000))
    assert scene.drop_at(PRESSURE, 0.1, 30000) < scene.drop_at(PRESSURE, 0.1, 23999)
    later = [scene.drop_at(PRESSURE, 300, t) for t in (24000, 27000)]
    assert later[1] > later[0]


def test_reef_physics():
    scene = template("geology", "reef_growth")
    heights = [scene.height(REEF, i / 50) for i in range(51)]
    steps = [b - a for a, b in zip(heights, heights[1:], strict=False)]
    assert max(steps) <= REEF["max_growth"] / 50 * 1.01
    assert scene.growth_state(REEF, 0.6) == "осушён"
    assert scene.height(REEF, 0.62) < scene.height(REEF, 0.5)
    drowned = {**REEF, "sea": [[0, 10], [0.2, 200], [1, 400]]}
    assert scene.growth_state(drowned, 1) == "утонул"
    assert scene.height(drowned, 1) == scene.height(drowned, 0.5)


def test_gas_in_an_open_well_expands_mostly_near_the_surface():
    scene = template("drilling", "gas_kick")
    states = [scene.opened(KICK, i / 20) for i in range(21)]
    volumes = [s["volume"] for s in states]
    assert volumes == sorted(volumes) and volumes[-1] > 3 * volumes[0]
    assert volumes[-1] - volumes[-2] > 10 * (volumes[1] - volumes[0])
    assert states[-1]["hole"] < states[0]["hole"]
    assert all(b["bottom"] <= a["bottom"] + 1e-6 for a, b in zip(states, states[1:], strict=False))
    amount = [s["gas"] * s["volume"] for s in states]
    assert max(amount) == pytest.approx(min(amount))


def test_gas_in_a_closed_well_raises_pressure_everywhere():
    scene = template("drilling", "gas_kick")
    start = scene.opened(KICK, 0.1)
    low, high = scene.closed(KICK, start, 0.0), scene.closed(KICK, start, 1.0)
    assert low["hole"] == pytest.approx(start["hole"]) and low["surface"] == pytest.approx(0, abs=1e-9)
    assert high["volume"] == low["volume"]
    assert high["hole"] > low["hole"] and high["surface"] > low["surface"]
    assert math.isclose(high["hole"] - low["hole"], high["surface"] - low["surface"], rel_tol=1e-9)


def test_gas_kick_needs_a_shut_well_before_closed_rise():
    scene = template("drilling", "gas_kick")
    assert scene.check(KICK, [beat({"closed": 0.5})])
    assert scene.check(KICK, [beat({"shut": 1}), beat({"open": 0.5})])


def test_invasion_zone_physics():
    scene = template("geology", "invasion_zone")
    quick, slow, _ = INVASION["layers"]
    assert scene.extent(quick, INVASION, 1, 0) > scene.extent(slow, INVASION, 1, 0)
    assert scene.extent(quick, INVASION, 1, 0.7) == 0 < scene.extent(slow, INVASION, 1, 0.7)
    small, large = scene.extent(quick, INVASION, 0.2, 0.3), scene.extent(quick, INVASION, 1, 0.3)
    assert small == 0 < large
    assert scene.extent(quick, INVASION, 1, 0.1) < scene.extent(quick, INVASION, 1, 0)
    shallow, deep = {"depth": 0.1}, {"depth": 0.8}
    zone = scene.grown(quick, INVASION, 0.3)
    assert abs(scene.reading(quick, shallow, zone) - quick["invaded"]) < abs(scene.reading(quick, deep, zone) - quick["invaded"])
    assert scene.reading(quick, deep, 0) == quick["native"]
    assert scene.reading(quick, deep, 1) == pytest.approx(quick["invaded"])


def test_invasion_zone_refuses_growth_behind_casing():
    scene = template("geology", "invasion_zone")
    assert scene.check(INVASION, [beat({"casing": 1}), beat({"invade": 1})])
    assert scene.check({**INVASION, "layers": INVASION["layers"][::-1]}, [beat({})])


def test_tool_goes_down_only_after_the_string_is_pulled():
    scene = template("geology", "well_tool_curve")
    assert scene.check(WELL, [beat({"tool": 4})])
    assert scene.check({**WELL, "show_drilling": False}, [beat({"drill": 1})])
    assert scene.wall(WELL, 2, 0) == pytest.approx(1.0) and scene.wall(WELL, 2, 1) == pytest.approx(1.25)


def test_shipped_specs_pass_their_own_checks():
    from glava.modules.video.api import spec_issues

    for file in sorted((paths.workspace() / "work").glob("*/video_specs/*.json")):
        spec = json.loads(file.read_text(encoding="utf-8"))
        layer = json.loads((file.parents[1] / "layer.json").read_text(encoding="utf-8"))
        node = next(n for n in layer["nodes"] if n["id"] == spec["node_id"])
        domain = DOMAIN / json.loads((paths.workspace() / "chapters.json").read_text(encoding="utf-8"))["chapters"][spec["chapter"]]["domain"]
        checklist = json.loads((domain / "physics_checklist.json").read_text(encoding="utf-8"))
        assert spec_issues(spec, node, load_module(domain / "video" / f"{spec['template']}.py"), checklist, spec["format"]) == []
