"""Защита на входе: только свой хост, POST только со своих страниц, ограничение тела запроса."""

from urllib.parse import urlsplit

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from glava_server.config import Settings
from glava_server.errors import ApiError, error_response

OWN_HOSTS = frozenset({"127.0.0.1", "localhost"})
READ_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
PROTECTIVE_HEADERS = (("X-Content-Type-Options", "nosniff"), ("Cross-Origin-Resource-Policy", "same-origin"), ("Referrer-Policy", "no-referrer"))


class _BodyTooLarge(Exception):
    pass


def _host_name(host: str) -> str | None:
    try:
        return urlsplit(f"//{host}").hostname
    except ValueError:
        return None


def _problem(scope: Scope, headers: Headers, settings: Settings) -> ApiError | None:
    host = headers.get("host", "")
    if _host_name(host) not in OWN_HOSTS:
        return ApiError(400, "bad_host", "Сервер отвечает только на адрес 127.0.0.1 или localhost")
    if scope["method"] in READ_METHODS:
        return None
    if headers.get("origin") not in settings.allowed_origins | {f"http://{host}"}:
        return ApiError(400, "bad_origin", "Запрос разрешён только со страниц этого приложения")
    length = headers.get("content-length", "0")
    if length.isdecimal() and int(length) > settings.max_body_bytes:
        return _too_large(settings)
    return None


def _too_large(settings: Settings) -> ApiError:
    return ApiError(413, "too_large", f"Запрос больше {max(1, settings.max_body_bytes // 1024 ** 2)} МБ")


class Guard:
    def __init__(self, app: ASGIApp, settings: Settings) -> None:
        self.app = app
        self.settings = settings

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def protected_send(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                for name, value in PROTECTIVE_HEADERS:
                    headers.setdefault(name, value)
            await send(message)

        problem = _problem(scope, Headers(scope=scope), self.settings)
        if problem is not None:
            await error_response(problem)(scope, receive, protected_send)
            return
        await self._limited(scope, receive, protected_send)

    async def _limited(self, scope: Scope, receive: Receive, send: Send) -> None:
        size, exceeded, started = 0, False, False

        async def limited_receive() -> Message:
            nonlocal size, exceeded
            message = await receive()
            size += len(message.get("body", b""))
            if size > self.settings.max_body_bytes:
                exceeded = True
                raise _BodyTooLarge
            return message

        async def limited_send(message: Message) -> None:
            nonlocal started
            if not exceeded:
                started = True
                await send(message)

        try:
            await self.app(scope, limited_receive, limited_send)
        except _BodyTooLarge:
            pass  # ответ 413 уходит ниже: разбор тела в приложении мог и сам поймать это исключение
        if exceeded and not started:
            await error_response(_too_large(self.settings))(scope, receive, send)
