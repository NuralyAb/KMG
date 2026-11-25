"""Выбор модели и OpenAI-совместимый сервер. Настоящей сети нет: отвечает сервер на этом же компьютере."""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from glava.modules.llm import compatible
from glava.modules.llm.client import BudgetExceeded, Reply, ask_json, cached, metered
from glava.modules.llm.compatible import (
    LOCAL_URL,
    OPENAI_URL,
    OpenAiCompatible,
    is_loopback,
)
from glava.modules.llm.providers import (
    PRICES,
    AnthropicApi,
    ProviderUnavailable,
    provider_from_env,
)


def answer(text="да", tokens_in=1000, reason="stop"):
    return {"choices": [{"message": {"content": text}, "finish_reason": reason}], "usage": {"prompt_tokens": tokens_in, "completion_tokens": 100}}


@pytest.fixture
def server(monkeypatch):
    """Отвечает по очереди парами (код, тело); запросы остаются в server.seen."""
    monkeypatch.setattr(compatible.time, "sleep", lambda _: None)

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            http.seen.append((self.path, dict(self.headers), body))
            code, data = http.queue.pop(0) if len(http.queue) > 1 else http.queue[0]
            raw = json.dumps(data).encode()
            self.send_response(code)
            if code in (302, 307):
                self.send_header("Location", f"{http.url}/elsewhere")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def log_message(self, *_):
            pass

    http = HTTPServer(("127.0.0.1", 0), Handler)
    http.seen, http.queue, http.url = [], [(200, answer())], f"http://127.0.0.1:{http.server_port}/v1"
    threading.Thread(target=http.serve_forever, daemon=True).start()
    yield http
    http.shutdown()
    http.server_close()


def test_answer_tokens_and_cost(server):
    reply = OpenAiCompatible("m", server.url, "k", 2.0, 10.0).ask("система", "вопрос")
    assert (reply.text, reply.input_tokens, reply.output_tokens) == ("да", 1000, 100)
    assert reply.cost_usd == pytest.approx(0.003)
    path, headers, body = server.seen[0]
    assert path == "/v1/chat/completions" and headers["Authorization"] == "Bearer k"
    assert [m["content"] for m in body["messages"]] == ["система", "вопрос"]


def test_images_travel_inside_the_request(server, tmp_path):
    scan = tmp_path / "p.png"
    scan.write_bytes(b"png")
    OpenAiCompatible("m", server.url).ask("s", "p", [scan])
    _, headers, body = server.seen[0]
    picture, text = body["messages"][1]["content"]
    assert picture["image_url"]["url"] == "data:image/png;base64,cG5n" and text["text"] == "p"
    assert "Authorization" not in headers


def test_busy_server_is_asked_again(server):
    server.queue = [(503, {}), (429, {}), (200, answer())]
    assert OpenAiCompatible("m", server.url).ask("s", "p").text == "да"


def test_bad_request_is_not_repeated_and_key_is_not_shown(server):
    server.queue = [(401, {"error": {"message": "нет доступа"}})]
    with pytest.raises(ProviderUnavailable, match="нет доступа") as caught:
        OpenAiCompatible("m", server.url, "sk-secret").ask("s", "p")
    assert len(server.seen) == 1 and "sk-secret" not in str(caught.value)
    assert "sk-secret" not in repr(OpenAiCompatible("m", server.url, "sk-secret"))


@pytest.mark.parametrize("code", [302, 307])
def test_redirect_is_not_followed(server, code):
    server.queue = [(code, {}), (200, answer())]
    with pytest.raises(ProviderUnavailable):
        OpenAiCompatible("m", server.url, "k").ask("s", "p")
    assert len(server.seen) == 1


@pytest.mark.parametrize("data", [{}, {"choices": []}, [], {"choices": [{"message": None}]}])
def test_foreign_answer_is_named(server, data):
    server.queue = [(200, data)]
    with pytest.raises(ProviderUnavailable, match="формате"):
        OpenAiCompatible("m", server.url).ask("s", "p")


@pytest.mark.parametrize(("chars", "tokens"), [(9000, 1000), (4300, 1000), (24_000, 4096), (13_000, 4096), (90_000, 8192)])
def test_silently_cut_chapter_is_refused(server, chars, tokens):
    """Ollama с контекстом 4096 отвечает на главу из 45 тысяч токенов без ошибки."""
    server.queue = [(200, answer(tokens_in=tokens))]
    with pytest.raises(ProviderUnavailable, match="часть главы отброшена"):
        OpenAiCompatible("m", server.url).ask("s", "я" * chars)


@pytest.mark.parametrize(("chars", "tokens"), [(4000, 1000), (8000, 3777), (100, 512), (9000, 4096)])
def test_whole_chapter_is_accepted(server, chars, tokens):
    server.queue = [(200, answer(tokens_in=tokens))]
    assert OpenAiCompatible("m", server.url).ask("s", "я" * chars).text == "да"


def test_stated_context_is_the_limit(server):
    server.queue = [(200, answer(tokens_in=5950))]
    assert OpenAiCompatible("m", server.url, context=7000).ask("s", "я" * 9000).text == "да"
    with pytest.raises(ProviderUnavailable, match="отброшена"):
        OpenAiCompatible("m", server.url, context=6000).ask("s", "я" * 9000)


@pytest.mark.parametrize("usage", [None, [], "x", {}, {"prompt_tokens": 0, "completion_tokens": 1}, {"prompt_tokens": float("nan"), "completion_tokens": 1},
                                   {"prompt_tokens": -5, "completion_tokens": 1}, {"prompt_tokens": "9", "completion_tokens": 1}, {"prompt_tokens": 9}])
def test_unknown_spending_is_refused(server, usage):
    server.queue = [(200, {**answer(), "usage": usage})]
    with pytest.raises(ProviderUnavailable, match="токенов"):
        OpenAiCompatible("m", server.url, None, 1.0, 1.0).ask("s", "p")


def test_refused_answer_is_still_paid_for(server):
    server.queue = [(200, answer(tokens_in=4096))]
    provider = metered(OpenAiCompatible("m", server.url, None, 1000.0, 1000.0), budget_usd=4.0)
    with pytest.raises(ProviderUnavailable):
        provider.ask("s", "я" * 90_000)
    with pytest.raises(BudgetExceeded):
        provider.ask("s", "p")


def test_not_a_number_does_not_pass_the_budget():
    class Odd:
        name, model = "x", "x"

        def ask(self, system, prompt):
            return Reply("да", "x", 1, 1, float("nan"))

    with pytest.raises(BudgetExceeded):
        metered(Odd(), 25.0).ask("s", "p")


@pytest.mark.parametrize("answer_body", [(401, {"error": {"message": "bad Bearer sk-secret"}}), (400, {"headers": "Bearer sk-secret"})])
def test_server_cannot_print_the_key_back(server, answer_body):
    server.queue = [answer_body]
    with pytest.raises(ProviderUnavailable) as caught:
        OpenAiCompatible("m", server.url, "sk-secret").ask("s", "p")
    assert "sk-secret" not in str(caught.value)
    server.queue = [(200, answer(text="ключ sk-secret-0123456789"))]
    assert "sk-secret" not in OpenAiCompatible("m", server.url, "sk-secret-0123456789").ask("s", "p").text


@pytest.mark.parametrize("key", ["1", "ollama", "EMPTY", "local"])
def test_placeholder_key_does_not_distort_the_answer(server, key):
    server.queue = [(200, answer(text="ollama: 12.1 EMPTY local"))]
    assert OpenAiCompatible("m", server.url, key).ask("s", "p").text == "ollama: 12.1 EMPTY local"


def test_address_is_not_written_into_the_layer():
    env = {"LLM_PROVIDER": "local", "LLM_MODEL": "m", "LLM_CONTEXT": "8192", "LLM_BASE_URL": "http://localhost:8000/v1"}
    assert "localhost" not in provider_from_env(env).name


def test_filtered_answer_is_not_complete(server):
    server.queue = [(200, answer(reason="content_filter"))]
    assert OpenAiCompatible("m", server.url).ask("s", "p").is_cut


def test_cut_answer_is_neither_accepted_nor_cached(server, tmp_path):
    server.queue = [(200, answer(text='{"entries": []}', reason="length"))]
    provider = cached(OpenAiCompatible("m", server.url), tmp_path)
    with pytest.raises(ValueError, match="обрезан"):
        ask_json(provider, "s", "p", lambda d: [], attempts=2)
    assert not list(tmp_path.glob("*.json"))
    server.queue = [(200, answer(text='{"entries": [1]}'))]
    assert ask_json(provider, "s", "p", lambda d: [])[0] == {"entries": [1]}


def test_bad_answer_does_not_stay_in_cache_when_the_next_attempt_fails(server, tmp_path):
    server.queue = [(200, answer(text='обрывок {"a":')), (401, {"error": "нет"})]
    with pytest.raises(ProviderUnavailable):
        ask_json(cached(OpenAiCompatible("m", server.url), tmp_path), "s", "p", lambda d: [])
    assert not list(tmp_path.glob("*.json"))


@pytest.mark.parametrize(("text", "expected"), [('<think>пусто {"entries": []}</think>{"entries": [1]}', {"entries": [1]}), ('{"a": 1}', {"a": 1}),
                                                ('черновик {"entries": []}</think>{"entries": [2]}', {"entries": [2]}), ('{"note": "тег <think> и </think>"}', {"note": "тег <think> и </think>"})])
def test_thoughts_are_not_the_answer(server, text, expected):
    server.queue = [(200, answer(text=text))]
    assert ask_json(OpenAiCompatible("m", server.url), "s", "p", lambda d: [])[0] == expected


def test_list_content_is_refused(server):
    server.queue = [(200, {**answer(), "choices": [{"message": {"content": ["да"]}}]})]
    with pytest.raises(ProviderUnavailable, match="формате"):
        OpenAiCompatible("m", server.url).ask("s", "p")


# ---------- выбор из переменных среды
def test_local_model_needs_only_a_name():
    provider = provider_from_env({"LLM_PROVIDER": "local", "LLM_MODEL": "qwen3", "LLM_CONTEXT": "8192"})
    assert (provider.name, provider.model, provider.base_url, provider.key) == ("local", "qwen3", LOCAL_URL, None)


def test_openai_goes_only_to_its_own_address():
    env = {"LLM_PROVIDER": "openai", "LLM_MODEL": "m", "OPENAI_API_KEY": "k", "LLM_PRICE_IN": "1", "LLM_PRICE_OUT": "4", "LLM_BASE_URL": "http://evil.example/v1"}
    provider = provider_from_env(env)
    assert (provider.base_url, provider.key, provider.name) == (OPENAI_URL, "k", "openai")


def test_openai_key_is_not_sent_to_another_server():
    provider = provider_from_env({"LLM_PROVIDER": "local", "LLM_MODEL": "m", "LLM_CONTEXT": "8192", "OPENAI_API_KEY": "k"})
    assert provider.key is None


def test_two_servers_do_not_share_the_cache():
    def name(url):
        return provider_from_env({"LLM_PROVIDER": "local", "LLM_MODEL": "m", "LLM_CONTEXT": "8192", "LLM_BASE_URL": url}).name

    urls = (LOCAL_URL, "http://localhost:1234/v1", "http://localhost:8000/v1", "http://localhost:8000/b/v1", "https://localhost:8000/v1")
    assert len({name(u) for u in urls}) == 5


def test_scheme_case_does_not_matter():
    env = {"LLM_PROVIDER": "local", "LLM_MODEL": "m", "LLM_CONTEXT": "8192", "LLM_BASE_URL": "HTTPS://models.example/v1", "LLM_API_KEY": "k", "LLM_PRICE_IN": "0", "LLM_PRICE_OUT": "0"}
    assert provider_from_env(env).key == "k"


@pytest.mark.parametrize("env", [
    {"LLM_PROVIDER": "local"},
    {"LLM_PROVIDER": "local", "LLM_MODEL": "m"},
    {"LLM_PROVIDER": "local", "LLM_MODEL": " "},
    {"LLM_PROVIDER": "local", "LLM_MODEL": "m", "LLM_PRICE_IN": "5"},
    {"LLM_PROVIDER": "local", "LLM_MODEL": "m", "LLM_BASE_URL": "http://user:hunter2@127.0.0.1:1/v1"},
    {"LLM_PROVIDER": "local", "LLM_MODEL": "m", "LLM_BASE_URL": "http://127.0.0.1:1/v1?api_key=hunter2"},
    {"LLM_PROVIDER": "local", "LLM_MODEL": "m", "LLM_BASE_URL": "http://[::1"},
    {"LLM_PROVIDER": "local", "LLM_MODEL": "m", "LLM_BASE_URL": "http://127.0.0.1:99999/v1"},
    {"LLM_PROVIDER": "openai", "LLM_MODEL": "m", "OPENAI_API_KEY": "k", "LLM_PRICE_IN": "0", "LLM_PRICE_OUT": "0"},
    {"LLM_PROVIDER": "openai", "LLM_MODEL": "m", "LLM_PRICE_IN": "1", "LLM_PRICE_OUT": "1"},
    {"LLM_PROVIDER": "openai", "LLM_MODEL": "m", "OPENAI_API_KEY": "k"},
    {"LLM_PROVIDER": "openai", "LLM_MODEL": "m", "OPENAI_API_KEY": "k", "LLM_PRICE_IN": "дёшево", "LLM_PRICE_OUT": "1"},
    {"LLM_PROVIDER": "openai", "LLM_MODEL": "m", "OPENAI_API_KEY": "k", "LLM_PRICE_IN": "nan", "LLM_PRICE_OUT": "1"},
    {"LLM_PROVIDER": "local", "LLM_MODEL": "m", "LLM_BASE_URL": "https://models.example/v1"},
    {"LLM_PROVIDER": "local", "LLM_MODEL": "m", "LLM_BASE_URL": "http://models.example/v1", "LLM_API_KEY": "k", "LLM_PRICE_IN": "0", "LLM_PRICE_OUT": "0"},
    {"LLM_PROVIDER": "local", "LLM_MODEL": "m", "LLM_API_KEY": "ключ"},
    {"LLM_PROVIDER": "local", "LLM_MODEL": "m", "LLM_API_KEY": "a\nb"},
    {"LLM_PROVIDER": "local", "LLM_MODEL": "m", "LLM_BASE_URL": "file:///etc/passwd"},
    {"LLM_PROVIDER": "local", "LLM_MODEL": "m", "LLM_BASE_URL": "127.0.0.1:11434/v1"},
    {"LLM_PROVIDER": "anthropic", "LLM_MODEL": "неизвестная"},
    {"LLM_PROVIDER": "другой"},
])
def test_wrong_settings_stop_before_spending(env):
    with pytest.raises(ProviderUnavailable) as caught:
        provider_from_env(env)
    assert "hunter2" not in str(caught.value)


@pytest.mark.parametrize(("url", "expected"), [
    ("http://127.0.0.1:1/v1", True), ("http://localhost/v1", True), ("http://[::1]:1/v1", True),
    ("http://192.168.0.5/v1", False), ("http://127.0.0.1.evil.example/v1", False), ("http://localhost.evil.example/v1", False),
])
def test_loopback(url, expected):
    assert is_loopback(url) is expected


# ---------- цены Anthropic
def test_anthropic_is_still_chosen():
    assert isinstance(provider_from_env({"LLM_PROVIDER": "anthropic", "LLM_MODEL": "claude-sonnet-5-5"}), AnthropicApi)


def test_cached_tokens_are_paid_for():
    short, _ = PRICES["claude-sonnet-5-5"]
    assert short.cost(1_000_000, 0, 0, 0) == pytest.approx(2.0)
    assert short.cost(0, 1_000_000, 0, 0) == pytest.approx(2.5)
    assert short.cost(0, 0, 1_000_000, 0) == pytest.approx(0.1)


def test_long_haiku_prompt_costs_more():
    short, long = PRICES["claude-haiku-5-5"]
    assert (short.tokens_in, short.tokens_out, long.tokens_in, long.tokens_out) == (0.1, 0.5, 0.5, 2.5)
