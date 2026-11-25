"""Кто пришёл: ученик или автор. Без пароля автора сервер открыт целиком, с паролем всё, кроме экрана ученика, требует входа."""

import hashlib
import hmac
import secrets
import threading
import time
from collections.abc import Callable
from http.cookies import CookieError, SimpleCookie

from starlette.datastructures import Headers
from starlette.types import ASGIApp, Receive, Scope, Send

from glava_server.errors import ApiError, error_response

COOKIE = "glava_admin"
SESSION_S = 12 * 3600
MAX_FAILURES, WINDOW_S = 5, 60
# ученику открыто только перечисленное: новый адрес закрыт, пока его не добавили сюда
PUBLIC = ("/api/learn", "/api/auth", "/learn")


class Access:
    def __init__(self, password: str | None, clock: Callable[[], float] = time.monotonic) -> None:
        self._password = password
        self._clock = clock
        self._lock = threading.Lock()
        self._sessions: dict[str, float] = {}
        self._failures: list[float] = []

    @property
    def is_protected(self) -> bool:
        return self._password is not None

    def login(self, password: str) -> str:
        """Новый сеанс; неверные попытки считаются на весь сервер: он слушает один компьютер."""
        if self._password is None:
            raise ApiError(409, "conflict", "Пароль автора не задан, вход не нужен")
        now = self._clock()
        with self._lock:
            self._failures = [t for t in self._failures if now - t < WINDOW_S]
            if len(self._failures) >= MAX_FAILURES:
                raise ApiError(429, "too_many", "Слишком много неверных попыток, подождите минуту")
            # попытка записывается до сравнения: иначе одновременные запросы обошли бы счётчик
            self._failures.append(now)
        if not hmac.compare_digest(_digest(password), _digest(self._password)):
            raise ApiError(401, "wrong_password", "Пароль не подошёл")
        token = secrets.token_urlsafe(32)
        with self._lock:
            self._failures = []
            self._sessions = {k: t for k, t in self._sessions.items() if t > now} | {_digest(token).hex(): now + SESSION_S}
        return token

    def logout(self, token: str | None) -> None:
        with self._lock:
            self._sessions.pop(_digest(token or "").hex(), None)

    def is_admin(self, token: str | None) -> bool:
        if self._password is None:
            return True
        with self._lock:
            return bool(token) and self._sessions.get(_digest(token or "").hex(), 0) > self._clock()


def _digest(text: str) -> bytes:
    return hashlib.sha256(text.encode("utf-8", "surrogatepass")).digest()


def token_of(headers: Headers) -> str | None:
    try:
        found = SimpleCookie(headers.get("cookie", "")).get(COOKIE)
    except CookieError:
        return None
    return found.value if found else None


def is_public(path: str) -> bool:
    return any(path == p or path.startswith(f"{p}/") for p in PUBLIC)


class AccessGuard:
    def __init__(self, app: ASGIApp, access: Access) -> None:
        self.app = app
        self.access = access

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and not is_public(scope["path"]) and not self.access.is_admin(token_of(Headers(scope=scope))):
            await error_response(ApiError(401, "auth_required", "Этот раздел открывается после входа автора"))(scope, receive, send)
            return
        await self.app(scope, receive, send)
