"""Persistent cache for MCP tool-call results.

Wraps tool dispatch as LangChain agent middleware: before a tool call is
handed to its MCP server, we check a SQLite-backed store keyed on the tool
name and a canonical form of its arguments; on a miss we let the call
through and store the result (skipping errors) under that key with a
per-tool TTL.
"""

from __future__ import annotations

import logging
import sqlite3
import time
from contextlib import closing
from pathlib import Path
from typing import Any

from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import ToolMessage

from .config import (
    TOOL_CACHE_DB_PATH,
    TOOL_CACHE_DEFAULT_TTL_SECONDS,
    TOOL_CACHE_EXCLUDED_TOOLS,
    TOOL_CACHE_IGNORED_ARG_KEYS,
    TOOL_CACHE_TICKER_ARG_KEYS,
    TOOL_CACHE_TTL_SECONDS,
)

logger = logging.getLogger("financial_analyst_agent.tool_cache")


def _tool_arg_defaults(tool: Any) -> dict[str, Any]:
    """Read {arg_name: default_value} out of a tool's JSON args_schema."""
    schema = getattr(tool, "args_schema", None) or {}
    properties = schema.get("properties", {}) if isinstance(schema, dict) else {}
    return {name: spec["default"] for name, spec in properties.items() if "default" in spec}


def _canon_scalar(key: str, value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value).strip()
    return text.upper() if key in TOOL_CACHE_TICKER_ARG_KEYS else text.lower()


def _canon_value(key: str, value: Any) -> str:
    if isinstance(value, list):
        return ",".join(sorted(_canon_scalar(key, item) for item in value))
    return _canon_scalar(key, value)


def build_cache_key(tool_name: str, args: dict[str, Any], tool: Any = None) -> str:
    """Build a deterministic cache key from a tool name + its call arguments.

    Missing arguments are filled from the tool's declared schema defaults
    first, so an explicit `period="annual"` and an omitted `period` (which
    defaults to `"annual"`) produce the same key — both dispatch the same
    underlying call. Ticker/CIK-shaped args are upper-cased, other strings
    are lower-cased, list args are sorted, and IDs that shouldn't affect
    identity (see TOOL_CACHE_IGNORED_ARG_KEYS) are dropped before sorting
    the remaining args into `key=value` pairs.
    """
    merged = {**_tool_arg_defaults(tool), **args}
    parts = [
        f"{name}={_canon_value(name, value)}"
        for name, value in sorted(merged.items())
        if name not in TOOL_CACHE_IGNORED_ARG_KEYS and value not in (None, "")
    ]
    return f"{tool_name}:" + "|".join(parts)


class ToolResultCache:
    """SQLite-backed key/value store for cached tool results."""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as conn, conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tool_cache (
                    cache_key TEXT PRIMARY KEY,
                    tool_name TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    expires_at REAL NOT NULL
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, timeout=5)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def get(self, key: str) -> str | None:
        with closing(self._connect()) as conn, conn:
            row = conn.execute(
                "SELECT content, expires_at FROM tool_cache WHERE cache_key = ?", (key,)
            ).fetchone()
        if row is None:
            return None
        content, expires_at = row
        if expires_at < time.time():
            self.delete(key)
            return None
        return content

    def set(self, key: str, tool_name: str, content: str, ttl_seconds: int) -> None:
        now = time.time()
        with closing(self._connect()) as conn, conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO tool_cache
                    (cache_key, tool_name, content, created_at, expires_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (key, tool_name, content, now, now + ttl_seconds),
            )

    def delete(self, key: str) -> None:
        with closing(self._connect()) as conn, conn:
            conn.execute("DELETE FROM tool_cache WHERE cache_key = ?", (key,))


class ToolCallCacheMiddleware(AgentMiddleware):
    """Serves cached ToolMessages for repeat tool calls, bypassing dispatch."""

    def __init__(self, store: ToolResultCache | None = None) -> None:
        super().__init__()
        self.tools = []
        self._store = store or ToolResultCache(TOOL_CACHE_DB_PATH)

    def _ttl_for(self, tool_name: str) -> int:
        return TOOL_CACHE_TTL_SECONDS.get(tool_name, TOOL_CACHE_DEFAULT_TTL_SECONDS)

    def _maybe_store(self, tool_name: str, key: str, result: Any) -> None:
        if not isinstance(result, ToolMessage) or result.status == "error":
            return
        self._store.set(key, tool_name, str(result.content), self._ttl_for(tool_name))

    async def awrap_tool_call(self, request, handler):
        tool_name = request.tool.name if request.tool else request.tool_call["name"]
        if tool_name in TOOL_CACHE_EXCLUDED_TOOLS:
            return await handler(request)

        key = build_cache_key(tool_name, request.tool_call.get("args", {}), request.tool)
        cached = self._store.get(key)
        if cached is not None:
            logger.info("tool_cache HIT tool=%s key=%s", tool_name, key)
            return ToolMessage(content=cached, tool_call_id=request.tool_call["id"], name=tool_name)

        logger.info("tool_cache MISS tool=%s key=%s", tool_name, key)
        result = await handler(request)
        self._maybe_store(tool_name, key, result)
        return result

    def wrap_tool_call(self, request, handler):
        tool_name = request.tool.name if request.tool else request.tool_call["name"]
        if tool_name in TOOL_CACHE_EXCLUDED_TOOLS:
            return handler(request)

        key = build_cache_key(tool_name, request.tool_call.get("args", {}), request.tool)
        cached = self._store.get(key)
        if cached is not None:
            logger.info("tool_cache HIT tool=%s key=%s", tool_name, key)
            return ToolMessage(content=cached, tool_call_id=request.tool_call["id"], name=tool_name)

        logger.info("tool_cache MISS tool=%s key=%s", tool_name, key)
        result = handler(request)
        self._maybe_store(tool_name, key, result)
        return result
