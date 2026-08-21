"""Agent construction and query execution."""

import braintrust
braintrust.auto_instrument()  # this line should be before langchain imports

import time
from typing import Any

from langchain.agents import create_agent
from langchain_anthropic import ChatAnthropic
from langchain_anthropic.middleware import AnthropicPromptCachingMiddleware

from .config import RUN_LIMITS
from .mcp import load_tools
from .prompts import SYSTEM_PROMPT


async def build_agent() -> Any:
    tools = await load_tools()
    llm = ChatAnthropic(
        model="claude-sonnet-4-6",
        temperature=0,
        max_tokens=4000
    )
    # Tags the (stable) system prompt and tool definitions with one
    # breakpoint, and re-tags the last message on every turn with a second,
    # so the growing tool-call/tool-result history is cached incrementally
    # instead of resent uncached each turn.
    return create_agent(
        llm,
        tools,
        system_prompt=SYSTEM_PROMPT,
        middleware=[AnthropicPromptCachingMiddleware()],
    )


async def run_query(agent: Any, query: str) -> str:
    deadline = time.monotonic() + RUN_LIMITS["timeout_seconds"]
    final = None
    config = {"recursion_limit": RUN_LIMITS["recursion_limit"]}

    async for chunk in agent.astream(
        {"messages": [("user", query)]}, config=config, stream_mode="values"
    ):
        final = chunk
        if time.monotonic() > deadline:
            return "Execution budget exceeded; no verified final answer. Try a narrower query."

    if final is None:
        return "The agent returned no result."
    return str(final["messages"][-1].content)
