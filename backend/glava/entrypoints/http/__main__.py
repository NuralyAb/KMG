"""Запуск: uv run glava-server. Слушает только 127.0.0.1."""

import logging
import os
import socket
import sys

import uvicorn

from glava.entrypoints.http.app import create_app
from glava.shared.http.settings import HOST, ConfigError, settings_from_env

log = logging.getLogger("glava.http")
SHUTDOWN_S = 3  # открытый поток событий не должен держать остановку


def bind(port: int) -> socket.socket:
    """Порт занимается до чтения истории запусков: второй сервер не пометит чужие запуски упавшими."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    option = socket.SO_EXCLUSIVEADDRUSE if sys.platform == "win32" else socket.SO_REUSEADDR
    try:
        sock.setsockopt(socket.SOL_SOCKET, option, 1)
        sock.bind((HOST, port))
    except OSError as error:
        sock.close()
        raise ConfigError(f"порт {port} занят: сервер уже запущен или порт держит другая программа") from error
    return sock


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    try:
        settings = settings_from_env(os.environ)
        sock = bind(settings.port)
    except ConfigError as error:
        log.error("сервер не запущен: %s", error)
        raise SystemExit(2) from None
    with sock:
        log.info("сервер: http://%s:%s, корень: %s", HOST, settings.port, settings.root)
        config = uvicorn.Config(create_app(settings), host=HOST, port=settings.port, timeout_graceful_shutdown=SHUTDOWN_S, server_header=False)
        uvicorn.Server(config).run(sockets=[sock])


if __name__ == "__main__":
    main()
