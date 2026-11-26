"""Новые шаблоны сцен под типы трудности двойников: сейсмический клин, проградация дельты, тонкие прослои, двойная пористость.

Физика проверяется без cairo (шаблон грузится и без него не нужен только рисунок), отрисовка — если cairo есть.
"""

import importlib.util
import math

import pytest
from glava.shared import paths

DOMAIN = paths.workspace() / "domain"
HAS_CAIRO = importlib.util.find_spec("cairo") is not None

WEDGE = {"host_lith": "shale", "host_v": 2800, "host_rho": 2.4, "layer_lith": "sand", "layer_v": 2400, "layer_rho": 2.1, "freq": 30,
         "max_thickness": 80, "width": 1200, "noise": 0.15, "polarity": "normal"}
DELTA = {"sea": [[0, 0], [1, 0]], "supply": 120000, "depth": 40, "front": 1500, "width": 8000, "start": 1500, "bar_depth": 4, "prodelta_depth": 15,
         "well": 0.5, "curve": "GR", "filtrate": "fresh"}
THIN = {"layers": [{"lith": "shale", "h": 3, "fluid": None},
                   *[x for _ in range(6) for x in ({"lith": "sand", "h": 0.3, "fluid": "oil"}, {"lith": "shale", "h": 0.2, "fluid": None})],
                   {"lith": "shale", "h": 3, "fluid": None}],
        "rho_res": 40, "rho_shale": 2, "window": 1.5, "window_fine": 0.05}
FRACTURE = {"lith": "limestone", "matrix_porosity": 0.15, "matrix_perm": 0.5, "fracture_porosity": 0.005, "fracture_perm": 500, "block": 1.0,
            "drawdown": 5, "omega": None, "lam": None}
SCENES = [("seismic_wedge", WEDGE, [{"trace": 0.5, "seismic": 1}, {"tuning": 1, "trace": 0.2}, {"naive": 1, "focus": 3}, {"true_scale": 1}]),
          ("delta_progradation", DELTA, [{"time": 0.4, "lines": 1}, {"time": 1, "facies": 1, "well": 1}, {"naive": 1, "focus": 2}, {"true_scale": 1}]),
          ("thin_layers_log", THIN, [{"tool": 0.6}, {"tool": 1, "naive": 1}, {"fine": 1, "pack": 1, "focus": 3}, {"true_scale": 1}]),
          ("fracture_matrix", FRACTURE, [{"time": 0.3, "flow": 1}, {"time": 1, "naive": 1}, {"curve": 1, "focus": 2}, {"true_scale": 1}])]


def template(name):
    from glava.modules.drawing.api import load_module

    if not HAS_CAIRO:
        pytest.skip("шаблон импортирует cairo")
    file = DOMAIN / "geology" / "video" / f"{name}.py"
    # тесты написаны раньше шаблона: пока его нет, они пропускаются, а не роняют main
    if not file.exists():
        pytest.skip(f"шаблон {name} ещё не написан")
    return load_module(file)


def beat(action):
    return {"say": "слово", "claim_id": None, "on_screen": "Подпись", "label": "симуляция", "frame_class": "A", "action": action, "is_analogy": False, "pause_after": 0, "role": "step"}


@pytest.mark.parametrize(("name", "params", "actions"), SCENES, ids=[s[0] for s in SCENES])
@pytest.mark.parametrize("kind", ["short", "wide"])
def test_scene_draws_in_both_formats(name, params, actions, kind):
    from glava.modules.drawing.api import load_style
    from glava.modules.video.render import frame
    from glava.modules.video.speech import Speech
    from glava.modules.video.timeline import place
    from glava.modules.video.voices import Word

    scene, beats = template(name), [beat({}), *(beat(a) for a in actions)]
    assert scene.check(params, beats) == []
    placed, total = place(beats, [Speech(None, 2.0, (Word(0, 1.8, "слово"),)) for _ in beats])
    plaque = scene.plaque(params, kind)
    assert "увелич" in plaque or "масштаб" in plaque
    spec = {"format": kind, "params": params, "plaque": [plaque], "prediction_question": "?"}
    style = load_style(DOMAIN / "geology")
    blank = bytes(frame(0.0, spec, placed, scene, style).get_data())
    for moment in (total * 0.4, total * 0.7, total - 0.1):
        assert bytes(frame(moment, spec, placed, scene, style).get_data()) != blank


@pytest.mark.parametrize(("name", "params", "actions"), SCENES, ids=[s[0] for s in SCENES])
def test_unknown_action_and_missing_params_are_refused(name, params, actions):
    scene = template(name)
    assert scene.check(params, [beat({"чудо": 1})])
    assert scene.check({}, [beat({})])
    assert {"true_scale", "naive"} <= scene.ACTIONS
    assert len([f for f in scene.FITS if f]) >= 4 and scene.SUMMARY.startswith(name)


def test_legend_colors_come_from_the_styleguide():
    import json

    style = json.loads((DOMAIN / "geology" / "styleguide.json").read_text(encoding="utf-8"))
    for lith in ("shale", "sand", "limestone"):
        assert lith in style["lithology"]


# --- сейсмический клин ---------------------------------------------------------------------------------------------

def test_ricker_wavelet_shape():
    w = template("seismic_wedge")
    assert w.ricker(0, 30) == 1
    assert w.ricker(0.01, 30) == pytest.approx(w.ricker(-0.01, 30))
    side = 1 / (math.pi * 30) * math.sqrt(1.5)
    assert w.ricker(side, 30) < 0
    assert sum(w.ricker(i / 10000 - 0.1, 30) for i in range(2001)) / 10000 == pytest.approx(0, abs=1e-4)


def test_reflection_coefficients_from_impedance():
    w = template("seismic_wedge")
    top, base = w.reflections(WEDGE)
    z1, z2 = 2800 * 2.4, 2400 * 2.1
    assert top == pytest.approx((z2 - z1) / (z2 + z1)) and base == -top and top < 0


def test_thick_layer_resolves_and_shows_true_thickness():
    w = template("seismic_wedge")
    lam = w.wavelength(WEDGE)
    assert w.amplitude(WEDGE, lam) == pytest.approx(1, abs=0.01)
    assert w.apparent(WEDGE, 0.75 * lam) == pytest.approx(0.75 * lam, rel=0.03)


def test_tuning_near_quarter_wavelength_with_amplitude_boost():
    w = template("seismic_wedge")
    lam, tune = w.wavelength(WEDGE), w.tuning(WEDGE)
    assert 0.15 * lam < tune < 0.3 * lam
    assert w.amplitude(WEDGE, tune) > 1.3
    assert w.amplitude(WEDGE, tune) == max(a for _, a in w.curve(WEDGE))


def test_thin_layer_not_resolved_but_detected_by_amplitude():
    """Эталонный атом: «Сейсмика — не фотография»."""
    w = template("seismic_wedge")
    lam = w.wavelength(WEDGE)
    thin = [lam * k for k in (0.025, 0.05, 0.1)]
    seen = [w.apparent(WEDGE, h) for h in thin]
    assert max(seen) - min(seen) < 0.05 * lam
    assert all(s > h for s, h in zip(seen, thin, strict=True)) and seen[0] > 4 * thin[0]
    assert w.amplitude(WEDGE, 2 * thin[0]) == pytest.approx(2 * w.amplitude(WEDGE, thin[0]), rel=0.05)
    assert w.detection(WEDGE) < w.tuning(WEDGE)
    quiet = {**WEDGE, "noise": 0.5}
    assert w.detection(quiet) > w.detection(WEDGE)


def test_trace_chart_and_section_share_one_model():
    w = template("seismic_wedge")
    r = abs(w.reflections(WEDGE)[0])
    for h in (5, 15, 40):
        peak = max(abs(v) for _, v in w.trace(WEDGE, h, 2000))
        assert peak / r == pytest.approx(w.amplitude(WEDGE, h), rel=0.02)


def test_reverse_polarity_flips_the_trace():
    w = template("seismic_wedge")
    a, b = w.trace(WEDGE, 20, 50), w.trace({**WEDGE, "polarity": "reverse"}, 20, 50)
    assert all(x[1] == pytest.approx(-y[1]) for x, y in zip(a, b, strict=True))


def test_wedge_refuses_bad_scenes():
    w = template("seismic_wedge")
    assert w.check({**WEDGE, "layer_v": 2800, "layer_rho": 2.4}, [])
    assert w.check({**WEDGE, "max_thickness": 10}, [])
    assert w.check({**WEDGE, "freq": 200}, [])
    assert w.check({**WEDGE, "polarity": "любая"}, [])
    assert w.check(WEDGE, [beat({"trace": 2})])
    assert "раз" in w.plaque(WEDGE, "wide")


# --- проградация дельты -------------------------------------------------------------------------------------------

def test_delta_mass_balance_and_shore_moves_seaward():
    d = template("delta_progradation")
    for t in (0.25, 0.5, 1):
        assert d.deposited(DELTA, t) == pytest.approx(DELTA["supply"] * t, rel=1e-3)
    shores = [d.shoreline(DELTA, i / 10) for i in range(11)]
    assert shores == sorted(shores) and shores[-1] > shores[0] + DELTA["front"] * 0.5


def test_delta_facies_coarsen_upward():
    d = template("delta_progradation")
    order = {k: i for i, k in enumerate(("prodelta", "front", "bar", "channel"))}
    column = d.column_at(DELTA, DELTA["well"], 1.0)
    kinds = [order[k] for _, _, k in column]
    assert kinds == sorted(kinds) and kinds[0] == 0 and kinds[-1] == 3
    curve = d.log_curve(DELTA, DELTA["well"], 1.0, 40)
    clay = [v for _, v in curve]
    assert clay[0] < clay[len(clay) // 2] < clay[-1]


def test_delta_facies_follow_water_depth():
    d = template("delta_progradation")
    assert d.facies_at(DELTA, 0) == "channel"
    assert d.facies_at(DELTA, 2) == "bar"
    assert d.facies_at(DELTA, 10) == "front"
    assert d.facies_at(DELTA, 30) == "prodelta"


def test_delta_time_lines_are_inclined_not_flat():
    """Одна линия времени (поверхность склона) пересекает разные фации и разные высоты."""
    d = template("delta_progradation")
    surface = d.history(DELTA)[1][d.STEPS // 2]
    assert max(surface) - min(surface) > DELTA["depth"] * 0.8


def test_delta_well_before_the_delta_arrives_is_empty():
    d = template("delta_progradation")
    assert d.column_at(DELTA, DELTA["well"], 0.0) == []


def test_delta_refuses_bad_scenes():
    d = template("delta_progradation")
    assert d.check({**DELTA, "well": 0.95}, [])
    assert d.check({**DELTA, "bar_depth": 20}, [])
    assert d.check({**DELTA, "sea": [[0, 0], [1, -10]]}, [])
    assert d.check(DELTA, [beat({"time": 0.8}), beat({"time": 0.4})])


# --- тонкие прослои ------------------------------------------------------------------------------------------------

def test_tiny_window_sees_true_layers():
    t = template("thin_layers_log")
    top, _ = t.pack(THIN)
    for depth, rho in ((top + 0.15, 40), (top + 0.4, 2), (1.0, 2)):
        assert t.apparent(THIN, depth, 0.01) == pytest.approx(rho, rel=1e-6)


def test_wide_window_smooths_to_pack_resistivity():
    t = template("thin_layers_log")
    share = t.pack_shale_share(THIN)
    assert share == pytest.approx(0.4)
    assert t.reading(THIN) == pytest.approx(t.pack_resistivity(THIN, share), rel=0.05)
    top, bottom = t.pack(THIN)
    inside = [t.apparent(THIN, top + 1 + k * 0.05, THIN["window"]) for k in range(20)]
    assert max(inside) < 0.5 * THIN["rho_res"]
    assert max(inside) - min(inside) < 0.2 * t.reading(THIN)


def test_fine_window_resolves_layers():
    t = template("thin_layers_log")
    top, bottom = t.pack(THIN)
    fine = [t.apparent(THIN, top + k * 0.01, THIN["window_fine"]) for k in range(int((bottom - top) / 0.01))]
    assert max(fine) == pytest.approx(THIN["rho_res"], rel=0.01) and min(fine) == pytest.approx(THIN["rho_shale"], rel=0.01)


def test_shale_share_and_effective_thickness_from_one_equation():
    t = template("thin_layers_log")
    for share in (0.1, 0.4, 0.8):
        assert t.share_from(THIN, t.pack_resistivity(THIN, share)) == pytest.approx(share)
    estimated = t.share_from(THIN, t.reading(THIN))
    assert estimated == pytest.approx(t.pack_shale_share(THIN), abs=0.05)
    top, bottom = t.pack(THIN)
    assert t.effective(THIN, 0.4) == pytest.approx((bottom - top) * 0.6)


def test_curve_stays_between_layer_values():
    t = template("thin_layers_log")
    total = t.edges(THIN)[-1]
    values = [t.apparent(THIN, total * k / 100, THIN["window"]) for k in range(101)]
    assert all(THIN["rho_shale"] - 1e-9 <= v <= THIN["rho_res"] + 1e-9 for v in values)


def test_thin_layers_refuse_bad_scenes():
    t = template("thin_layers_log")
    assert t.check({**THIN, "window": 0.1}, [])
    assert t.check({**THIN, "rho_res": 2.2}, [])
    bad = [dict(x) for x in THIN["layers"]]
    bad[2]["fluid"] = "oil"
    assert t.check({**THIN, "layers": bad}, [])
    assert t.check({**THIN, "window_fine": 0.25}, [])


# --- двойная пористость --------------------------------------------------------------------------------------------

def test_fractures_store_little_but_conduct_most():
    f = template("fracture_matrix")
    omega = f.storativity(FRACTURE)
    assert 0 < omega < 0.1
    assert f.conduct_share(FRACTURE) > 0.9


def test_fracture_pressure_falls_first_then_matrix_feeds_it():
    f = template("fracture_matrix")
    early, late = f.state(FRACTURE, 0.02), f.state(FRACTURE, 0.6)
    assert early["fracture"] > early["matrix"]
    assert late["matrix"] > early["matrix"]
    drops = [f.state(FRACTURE, k / 20)["fracture"] for k in range(21)]
    assert all(b >= a - 1e-9 for a, b in zip(drops, drops[1:], strict=False))
    assert drops[-1] == pytest.approx(FRACTURE["drawdown"], rel=0.05)
    assert f.state(FRACTURE, 1.0)["matrix"] == pytest.approx(FRACTURE["drawdown"], rel=0.05)


def test_fracture_derivative_has_a_dip():
    """Классическая подпись двойной пористости: «ямка» на производной давления между двумя радиальными режимами."""
    f = template("fracture_matrix")
    times, derivative = f.derivative(FRACTURE)
    low = min(range(len(derivative)), key=derivative.__getitem__)
    assert 0 < low < len(derivative) - 1
    assert derivative[low] < 0.6 * derivative[0] and derivative[low] < 0.6 * derivative[-1]
    assert derivative[0] == pytest.approx(derivative[-1], rel=0.15)


def test_fracture_refuses_bad_scenes():
    f = template("fracture_matrix")
    assert f.check({**FRACTURE, "fracture_porosity": 0.3}, [])
    assert f.check({**FRACTURE, "fracture_perm": 0.1}, [])
    assert f.check(FRACTURE, [beat({"time": 0.8}), beat({"time": 0.2})])
