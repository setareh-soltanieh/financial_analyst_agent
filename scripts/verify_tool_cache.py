"""Manual verification for ToolCallCacheMiddleware.

Calls the middleware directly with a fake tool + handler (no live MCP
servers, no API keys needed) and asserts that:
  1. an identical second call is served from the cache without invoking
     the underlying handler again,
  2. cache keys are insensitive to ticker casing and to explicit-vs-default
     argument values,
  3. a different call (different args) is a fresh miss,
  4. error results are never cached.

Run with: uv run python scripts/verify_tool_cache.py
"""

import asyncio
import tempfile
from pathlib import Path

from langchain.agents.middleware.types import ToolCallRequest
from langchain_core.messages import ToolMessage

from financial_analyst_agent.tool_cache import ToolCallCacheMiddleware, ToolResultCache


class FakeTool:
    def __init__(self, name: str, args_schema: dict) -> None:
        self.name = name
        self.args_schema = args_schema


def make_request(tool: FakeTool, args: dict, call_id: str) -> ToolCallRequest:
    return ToolCallRequest(
        tool_call={"name": tool.name, "args": args, "id": call_id},
        tool=tool,
        state={},
        runtime=None,
    )


async def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        db_path = str(Path(tmp) / "tool_cache_test.sqlite3")
        middleware = ToolCallCacheMiddleware(ToolResultCache(db_path))

        calls = []

        async def handler(request: ToolCallRequest) -> ToolMessage:
            calls.append(request.tool_call["args"])
            return ToolMessage(
                content=f"result-for-{request.tool_call['args']}",
                tool_call_id=request.tool_call["id"],
                name=request.tool_call["name"],
            )

        tool = FakeTool(
            "edgar_trends",
            {
                "properties": {
                    "identifier": {"type": "string"},
                    "concepts": {"type": "array", "default": ["revenue", "net_income"]},
                    "periods": {"type": "integer", "default": 8},
                    "period": {"type": "string", "default": "annual"},
                    "include_growth": {"type": "boolean", "default": True},
                }
            },
        )

        # 1. First call: miss, handler invoked.
        r1 = await middleware.awrap_tool_call(
            make_request(tool, {"identifier": "MSFT", "period": "annual"}, "call-1"), handler
        )
        assert len(calls) == 1, "expected the real handler to run on a miss"

        # 2. Identical call, explicit vs default `period`: hit, handler NOT invoked again.
        r2 = await middleware.awrap_tool_call(
            make_request(tool, {"identifier": "msft"}, "call-2"), handler
        )
        assert len(calls) == 1, "expected a cache hit to skip the real handler"
        assert r2.content == r1.content, "cached content should match the original result"
        print("PASS: identical call (case/default-insensitive) served from cache")

        # 3. Different args: miss again.
        await middleware.awrap_tool_call(
            make_request(tool, {"identifier": "AAPL", "period": "annual"}, "call-3"), handler
        )
        assert len(calls) == 2, "a different identifier should not hit the cache"
        print("PASS: different args produce a fresh miss")

        # 4. Error results are not cached.
        async def error_handler(request: ToolCallRequest) -> ToolMessage:
            calls.append(request.tool_call["args"])
            return ToolMessage(
                content="boom", tool_call_id=request.tool_call["id"], name=request.tool_call["name"], status="error"
            )

        error_tool = FakeTool("edgar_search", {"properties": {"query": {"type": "string"}}})
        await middleware.awrap_tool_call(
            make_request(error_tool, {"query": "widgets"}, "call-4"), error_handler
        )
        n_before = len(calls)
        await middleware.awrap_tool_call(
            make_request(error_tool, {"query": "widgets"}, "call-5"), error_handler
        )
        assert len(calls) == n_before + 1, "error results must not be cached"
        print("PASS: error results are not cached (retried on next call)")

        print("\nAll tool_cache checks passed.")


if __name__ == "__main__":
    asyncio.run(main())
