"""Sync helpers that reuse a background event loop for async SDK methods."""

from __future__ import annotations

import asyncio
from threading import Lock, Thread
from typing import Any, Coroutine


class SyncRunner:
    """Run async SDK methods from sync code without duplicating logic."""

    _lock = Lock()
    _loop: asyncio.AbstractEventLoop | None = None
    _thread: Thread | None = None

    @classmethod
    def _ensure_loop(cls) -> asyncio.AbstractEventLoop:
        if cls._loop is not None:
            return cls._loop

        with cls._lock:
            if cls._loop is not None:
                return cls._loop

            loop = asyncio.new_event_loop()
            thread = Thread(target=loop.run_forever, daemon=True, name="alloynative-sync")
            thread.start()
            cls._loop = loop
            cls._thread = thread
            return loop

    @classmethod
    def run(cls, coro: Coroutine[Any, Any, Any]) -> Any:
        """Synchronously wait for an async coroutine on the shared loop."""

        loop = cls._ensure_loop()
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        return future.result()
