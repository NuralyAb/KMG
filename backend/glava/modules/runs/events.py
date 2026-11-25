"""Поток событий запуска (SSE): сначала накопленный журнал, дальше новые строки и смена состояния."""

import asyncio
import json
import time
from collections.abc import AsyncIterator
from typing import Any

from glava.modules.runs.manager import RunManager
from glava.modules.runs.store import decode

KEEPALIVE_S = 15


def _event(name: str, data: dict[str, Any]) -> str:
    return f"event: {name}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def run_events(manager: RunManager, run_id: str, poll_seconds: float) -> AsyncIterator[str]:
    offset, rest, shown, last_sent = 0, b"", None, time.monotonic()
    while True:
        # состояние читается раньше журнала: после конца процесса журнал уже полон
        record = manager.get(run_id)
        chunk = await asyncio.to_thread(manager.store.read_from, run_id, offset)
        offset += len(chunk)
        *lines, rest = (rest + chunk).split(b"\n")
        if not record.is_active and not chunk and rest:
            lines, rest = [rest], b""
        for line in lines:
            yield _event("log", {"line": decode(line)})
        if chunk:
            last_sent = time.monotonic()
            if not record.is_active:
                continue
        if record.state != shown:
            shown, last_sent = record.state, time.monotonic()
            yield _event("state", {"state": record.state, "exit_code": record.exit_code})
        if not record.is_active:
            return
        if time.monotonic() - last_sent > KEEPALIVE_S:
            last_sent = time.monotonic()
            yield ": жду\n\n"
        await asyncio.sleep(poll_seconds)
