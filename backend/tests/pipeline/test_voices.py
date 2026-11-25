"""Голоса: ElevenLabs без сети, ключ не утекает, потолок знаков, один голос на ролик."""

import base64
import io
import json
import urllib.error

import pytest
from glava.modules.video.check import sync_error
from glava.modules.video.speech import Speech, dictionaries, say_all, unspoken_chars
from glava.modules.video.timeline import place
from glava.modules.video.voices import (
    Edge,
    ElevenLabs,
    SpeechFailed,
    VoiceNotConfigured,
    Word,
    list_voices,
    max_chars,
    voice_env,
    voice_from_env,
    words_from_characters,
)
from glava.shared import paths

KEY, VOICE_ID = "sk_test_secret_key", "JBFqnCBsd6RMkjVDRZzb"
ENV = {"ELEVENLABS_API_KEY": KEY, "ELEVENLABS_VOICE_ID": VOICE_ID}


def reply(text):
    starts = [i * 0.1 for i in range(len(text))]
    return {"audio_base64": base64.b64encode(b"mp3").decode(),
            "alignment": {"characters": list(text), "character_start_times_seconds": starts, "character_end_times_seconds": [s + 0.1 for s in starts]}}


def http_error(code, detail):
    return urllib.error.HTTPError("https://api.elevenlabs.io", code, "", {}, io.BytesIO(json.dumps({"detail": detail}).encode()))


class Server:
    def __init__(self, *answers):
        self.answers, self.calls = list(answers), []

    def __call__(self, url, headers, payload):
        self.calls.append((url, headers, payload))
        answer = self.answers.pop(0) if len(self.answers) > 1 else self.answers[0]
        if isinstance(answer, Exception):
            raise answer
        return answer if answer is not None else reply(payload["text"])


def voice(server, **over):
    return ElevenLabs(KEY, VOICE_ID, post=server, sleep=lambda s: None, **over)


def test_words_come_from_character_times():
    words = words_from_characters(list("ро́ст — да."), [i * 0.1 for i in range(11)], [i * 0.1 + 0.1 for i in range(11)])
    assert [w.text for w in words] == ["ро́ст", "да."]
    assert words[0].start == 0 and words[1].start == pytest.approx(0.8)


def test_request_has_key_voice_and_settings():
    server = Server(None)
    audio, words = voice(server, speed=0.9).speak("Глинистая корка")
    url, headers, payload = server.calls[0]
    assert audio == b"mp3" and len(words) == 2
    assert VOICE_ID in url and "with-timestamps" in url and KEY not in url
    assert headers["xi-api-key"] == KEY
    assert payload["model_id"] == "eleven_multilingual_v2" and payload["voice_settings"]["speed"] == 0.9
    assert "language_code" not in payload


def test_newer_models_get_the_language_and_no_speed():
    payload = voice(Server(None), model="eleven_v4").payload("да")
    assert payload["language_code"] == "ru"
    assert "speed" not in payload["voice_settings"]


def test_stress_marks_can_be_turned_off():
    assert voice(Server(None)).prepare("колле́ктор") == "колле́ктор"
    assert voice(Server(None), stress=False).prepare("колле́ктор") == "коллектор"


def test_busy_service_is_retried():
    server = Server(http_error(429, "busy"), http_error(500, "oops"), None)
    assert voice(server).speak("да")[0] == b"mp3"
    assert len(server.calls) == 3


@pytest.mark.parametrize("code", [401, 402, 404])
def test_hopeless_errors_stop_at_once_and_do_not_show_the_key(code):
    server = Server(http_error(code, {"message": "quota exceeded"}))
    with pytest.raises(SpeechFailed, match="quota exceeded") as caught:
        voice(server).speak("да")
    assert len(server.calls) == 1
    assert KEY not in str(caught.value)


def test_key_is_not_in_repr_description_or_cache_key():
    made = voice_from_env(ENV)
    assert KEY not in repr(made) + json.dumps(made.describe()) + made.key


def test_ready_phrases_are_not_paid_twice(tmp_path):
    server = Server(None)
    first = say_all(["раз", "два"], tmp_path, voice(server), None, 100)
    second = say_all(["раз", "два"], tmp_path, voice(server), None, 100)
    assert (first.paid_chars, second.paid_chars, len(server.calls)) == (6, 0, 2)
    assert unspoken_chars(["раз", "три"], tmp_path, voice(server)) == 3


def test_ceiling_stops_before_the_first_request(tmp_path):
    server = Server(None)
    with pytest.raises(VoiceNotConfigured, match="потолок 5"):
        say_all(["длинная фраза"], tmp_path, voice(server), None, 5)
    assert server.calls == []


def test_fallback_voices_the_whole_film(tmp_path):
    broken, spare = Server(None, http_error(402, "quota")), Server(None)
    made = say_all(["раз", "два"], tmp_path, voice(broken), voice(spare, speed=1.0), 100)
    assert made.voice.post is spare
    assert len(spare.calls) == 2


def test_provider_is_chosen_by_key_and_by_name():
    assert isinstance(voice_from_env({}), Edge)
    assert isinstance(voice_from_env(ENV), ElevenLabs)
    assert isinstance(voice_from_env({**ENV, "VOICE_PROVIDER": "edge"}), Edge)
    assert isinstance(voice_from_env(ENV, "edge"), Edge)


@pytest.mark.parametrize("env", [{"VOICE_PROVIDER": "elevenlabs"}, {"ELEVENLABS_API_KEY": KEY}, {**ENV, "ELEVENLABS_SPEED": "2"}, {**ENV, "ELEVENLABS_STABILITY": "много"},
                                 {**ENV, "ELEVENLABS_VOICE_ID": "../x"}, {"VOICE_PROVIDER": "чудо"}])
def test_wrong_settings_are_explained(env):
    with pytest.raises(VoiceNotConfigured):
        voice_from_env(env)


def test_env_file_gives_only_voice_settings(tmp_path):
    file = tmp_path / ".env"
    file.write_text("# ключ\nELEVENLABS_API_KEY='abc'\nANTHROPIC_API_KEY=чужое\nELEVENLABS_SPEED=0.9\nELEVENLABS_MODEL=\n", encoding="utf-8")
    assert voice_env(file, {"ELEVENLABS_SPEED": "1.0", "PATH": "x"}) == {"ELEVENLABS_API_KEY": "abc", "ELEVENLABS_SPEED": "1.0"}
    assert max_chars({}) > 0


def test_voices_are_listed_without_spending(tmp_path):
    def get(url, headers):
        if url.endswith("/voices"):
            return {"voices": [{"voice_id": VOICE_ID, "name": "Голос", "labels": {"gender": "male"}}]}
        raise http_error(401, "нет права")

    rows = list_voices(ENV, get)
    assert VOICE_ID in rows[0] and "user_read" in rows[1]
    with pytest.raises(VoiceNotConfigured):
        list_voices({}, get)


def test_sync_is_measured_by_matching_words():
    beats = [{"say": "раз два", "pause_after": 0}]
    placed, _ = place(beats, [Speech(None, 2.0, (Word(0.0, 0.4, "раз"), Word(0.5, 0.9, "два")))])
    assert sync_error(placed, [Word(0.3, 0.5, "раз"), Word(0.8, 1.0, "два")]) == pytest.approx(0.1)
    assert sync_error(placed, [Word(0.3, 0.5, "иное")]) is None


@pytest.mark.parametrize("domain", ["geology", "drilling"])
def test_pack_dictionaries_join(domain):
    folder = paths.workspace() / "domain" / domain
    short, stress = dictionaries("\n".join((folder / f).read_text(encoding="utf-8") for f in ("pronunciation.md", "stress_dictionary.md")))
    assert short and all(v.count("́") == 1 for v in stress.values())


def test_drilling_pack_ids_are_unique():
    folder = paths.workspace() / "domain" / "drilling"
    for name in ("misconceptions.json", "physics_checklist.json"):
        ids = [x["id"] for x in json.loads((folder / name).read_text(encoding="utf-8"))]
        assert len(ids) == len(set(ids)) >= 15
