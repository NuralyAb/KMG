import socket

import pytest

from glava_server import __main__ as entry
from glava_server.config import ConfigError


def test_socket_is_bound_to_loopback_only() -> None:
    with entry.bind(0) as sock:
        assert sock.getsockname()[0] == "127.0.0.1"


def test_busy_port_gives_readable_error() -> None:
    with socket.socket() as busy:
        busy.bind(("127.0.0.1", 0))
        busy.listen()

        with pytest.raises(ConfigError, match="занят"):
            entry.bind(busy.getsockname()[1])


def test_main_reports_wrong_settings_and_exits(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GLAVA_PORT", "нет")

    with pytest.raises(SystemExit) as caught:
        entry.main()

    assert caught.value.code == 2


def test_main_serves_on_bound_socket(monkeypatch: pytest.MonkeyPatch) -> None:
    served: list[str] = []
    monkeypatch.setenv("GLAVA_PORT", "8399")
    monkeypatch.setattr(entry.uvicorn.Server, "run", lambda self, sockets: served.append(sockets[0].getsockname()[0]))

    entry.main()

    assert served == ["127.0.0.1"]
