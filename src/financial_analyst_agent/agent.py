"""Agent construction and query execution."""

import braintrust
braintrust.auto_instrument()  # this line should be before langchain imports

import time
from typing import Any

from langchain.agents import create_agent
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import SystemMessage

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
    # Anthropic renders tools -> system -> messages, so a cache_control
    # breakpoint on the (stable) system prompt covers the tool definitions
    # too, leaving only the per-query messages uncached.
    system_message = SystemMessage(
        content=[
            {
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ]
    )
    return create_agent(llm, tools, system_prompt=system_message)


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
