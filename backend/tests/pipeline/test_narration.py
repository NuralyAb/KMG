"""Озвученные разборы: фразы из слоя, чтение обозначений, дорожка и время фраз. Сеть не нужна."""

import asyncio

import pytest
from glava.modules.course.build import inline_svg
from glava.modules.narration import voice as voices
from glava.modules.narration.build import narrate, ready_narrations
from glava.modules.narration.script import reader, sentences, write_script
from glava.modules.narration.voice import Voice, VoiceFailed, speak_all

TABLES = """
| Пишется | Читается | Расшифровка |
| --- | --- | --- |
| Pн, kв | пэ эн, ка вэ | параметры |
| ГИС | гэ и эс | исследования |

| Слово | С ударением |
| --- | --- |
| бурение | буре́ние |
"""
READ = reader(TABLES)


def node(main: str, how: str = "", claims: tuple = ()) -> dict:
    return {"id": "lat.a", "short_title": "Параметр Pн", "claims": list(claims), "pages": [5],
            "layers": {"main": {"text": main}, "mechanism": {"text": how}, "practice": {"text": ""}}}


def test_symbols_operators_and_stresses_are_read_aloud():
    assert READ.say("Если Pн* > 1, а kв = 2, нужно бурение.") == "Если пэ эн со звёздочкой больше 1, а ка вэ равно 2, нужно буре́ние."
    assert READ.say("Бурение и ГИС") == "Буре́ние и гэ и эс"
    assert READ.say("строят связь Pн = f(kв)") == "строят связь пэ эн от ка вэ"
    assert READ.say("точка на рис. 7") == "точка на рисунке 7"


@pytest.mark.parametrize("text", ["ρх неизвестно", "Rt и Sw", "x_1 мало", r"\frac{1}{2}", "3 см³"])
def test_unknown_symbols_are_not_guessed(text):
    assert READ.say(text) is None


def test_a_dot_after_fig_does_not_end_the_sentence():
    assert sentences("Точку ставят на рис. 7 и читают. Потом сравнивают.") == ["Точку ставят на рис. 7 и читают.", "Потом сравнивают."]


def test_essence_is_spoken_first_and_explanation_follows():
    beats, skipped = write_script(node("Суть шага такая. Вторая мысль здесь.", "Порода держит воду в порах. Это видно на рис. 7."), READ)
    assert [b.kind for b in beats] == ["title", "main", "main", "how"]
    assert beats[0].say == "Параметр пэ эн." and skipped == ["Это видно на рис. 7."]


def test_a_phrase_that_leans_on_a_skipped_one_is_skipped_too():
    beats, skipped = write_script(node("Суть шага такая. Вторая мысль здесь.", "Берут Rt с диаграммы прибора. Затем его сравнивают с порогом. Порода держит воду."), READ)
    assert [b.text for b in beats][-1] == "Порода держит воду." and len(skipped) == 2


def test_talk_about_the_book_is_not_an_explanation():
    beats, skipped = write_script(node("Суть шага такая. Вторая мысль здесь.", "В выданных единицах формул нет. Порода держит воду."), READ)
    assert skipped == ["В выданных единицах формул нет."] and beats[-1].text == "Порода держит воду."


def test_without_the_first_thought_there_is_no_story():
    assert write_script(node("Считают по Rt напрямую."), READ)[0] == []
    assert write_script(node("Считают по Rt напрямую. Вторая мысль здесь.", "Порода держит воду в порах."), READ)[0] == []


def test_a_phrase_knows_its_claim_and_page():
    claim = {"id": "lat.a#c1", "text": "Параметр насыщения связывает сопротивление пласта", "page_pdf": 92}
    beats, _ = write_script(node("Параметр насыщения связывает сопротивление пласта. Совсем иное дело.", "", (claim,)), READ)
    assert (beats[1].claim_id, beats[1].page) == ("lat.a#c1", 92) and beats[2].claim_id is None


async def quiet(text: str, _: Voice) -> bytes:
    return b"\xff" * (6000 * max(1, len(text.split())))


def test_track_times_follow_the_sound(tmp_path):
    made = narrate([node("Суть шага такая. Вторая мысль здесь.")], READ, tmp_path / "out" / "narration", tmp_path / "cache", Voice(), quiet)
    step = made["steps"]["lat.a"]
    assert [(b["start"], b["end"]) for b in step["beats"]] == [(0, 3), (3, 6), (6, 9)] and step["duration"] == 9
    assert (tmp_path / "out" / step["audio"]).stat().st_size == 54_000
    page = ready_narrations(made, tmp_path / "out")["lat.a"]
    assert "say" not in page["beats"][0] and page["beats"][1]["text"] == "Суть шага такая."
    assert ready_narrations(made, tmp_path) == {}


def test_an_old_track_is_removed_and_ready_phrases_are_not_asked_again(tmp_path):
    out, cache, asked = tmp_path / "narration", tmp_path / "cache", []

    async def counted(text: str, voice: Voice) -> bytes:
        asked.append(text)
        return await quiet(text, voice)

    narrate([node("Суть шага такая. Вторая мысль здесь.")], READ, out, cache, Voice(), counted)
    narrate([node("Суть шага такая. Другая мысль здесь вот.")], READ, out, cache, Voice(), counted)
    assert len(list(out.glob("*.mp3"))) == 1 and len(asked) == 4


def test_a_silent_service_is_an_error_not_a_hole(tmp_path, monkeypatch):
    async def nothing(*_: object) -> bytes:
        return b""

    async def now(_: float) -> None:
        return None

    monkeypatch.setattr(voices.asyncio, "sleep", now)
    with pytest.raises(VoiceFailed, match="пустой ответ"):
        speak_all(["фраза"], Voice(), tmp_path, nothing)
    assert asyncio.run(quiet("а б", Voice()))


@pytest.mark.parametrize("bad", ["<script>1</script>", '<rect onload="x()"/>', '<image href="x"/>', "<foreignObject/>", "<style>a</style>", '<a href="#"/>', "<!DOCTYPE svg>"])
def test_only_drawing_svg_goes_into_the_page(tmp_path, bad):
    good = '<svg viewBox="0 0 4 4"><rect/><text>а &lt; б</text></svg>'
    (tmp_path / "a.svg").write_text(good, encoding="utf-8")
    (tmp_path / "b.svg").write_text(good.replace("<rect/>", bad), encoding="utf-8")
    assert inline_svg(tmp_path / "a.svg") == {"svg": good}
    assert inline_svg(tmp_path / "b.svg") == {}
