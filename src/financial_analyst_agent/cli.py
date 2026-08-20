"""Command-line interface for the financial analyst agent."""

import argparse
import asyncio

from .agent import build_agent, run_query
from .mcp import load_tools

DEMO_QUERIES = [
    "What was Apple's net income based on their latest quarterly report?",
    "What are the top 5 public companies in healthcare by market cap?",
    "What are the top 3 companies in healthcare, and what was the reported net income for each?",
    "How can AI disrupt the healthcare industry? Base facts on sources.",
    "What was Stripe's net income last quarter?",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Research public-company financial data.")
    parser.add_argument("--demo", action="store_true", help="Run built-in example queries.")
    parser.add_argument("--list-tools", action="store_true", help="List tools discovered from MCP servers.")
    parser.add_argument("--list-allowed-tools", action="store_true", help="List all allowed tools from MCP servers.")
    parser.add_argument("query", nargs="*", help="Question for the agent.")
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    if args.list_tools:
        await load_tools(list_only=True)
        return

    if args.list_allowed_tools:
            await load_tools(list_allowed_tools=True)
            return

    agent = await build_agent()
    if args.demo:
        for query in DEMO_QUERIES:
            print(f"\n=== Q: {query}\n")
            print(await run_query(agent, query))
    elif args.query:
        print(await run_query(agent, " ".join(args.query)))
    else:
        print("Financial analyst agent. Press Ctrl-C to exit.")
        while True:
            try:
                query = input("\nyou> ").strip()
            except (KeyboardInterrupt, EOFError):
                print()
                break
            if query:
                print("\n" + await run_query(agent, query))


def run() -> None:
    """Console-script entry point."""
    asyncio.run(main())


if __name__ == "__main__":
    run()
