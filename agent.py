import asyncio

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_anthropic import ChatAnthropic
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.checkpoint.memory import InMemorySaver
import sys
import os
import time
import argparse

load_dotenv()
SEC_EDGAR_USER_AGENT=os.environ.get("SEC_EDGAR_USER_AGENT", "")
TAVILY_API_KEY=os.environ.get('TAVILY_API_KEY', '')
FMP_API_KEY = os.environ.get("FMP_API_KEY", "")

SERVERS = {
    "sec_edgar": {
        "command": sys.executable,
        "args": ["-m", "sec_edgar_mcp.server"],
        "env": {"SEC_EDGAR_USER_AGENT": SEC_EDGAR_USER_AGENT},
        "transport": "stdio",
    },
    "tavily": {
        "url": f"https://mcp.tavily.com/mcp/?tavilyApiKey={TAVILY_API_KEY}",
        "transport": "streamable_http",
    },
    "citra": {
      "command": "npx",
      "args": ["-y", "@sylphx/citra"],
      "transport": "stdio",
    },
    "fmp": {
        "url": f"https://financialmodelingprep.com/mcp?apikey={FMP_API_KEY}",
        "transport": "streamable_http",
    }, # I am facing some limitations with the free plan
    "yfmcp": {
      "command": "uvx",
      "args": ["yfmcp@latest"],
      "transport": "stdio",
    },
}

ALLOWED_TOOLS = [
    "lookup", "cik",            # company resolution
    "financial", "income",      # statements / financial facts
    "filing",                   # latest 10-Q/10-K discovery
    "search", "extract",        # tavily research
    "read_pdf",                 # citra read pdf for the fall back
    "yfinance_get_top",         # For finding top companies in a specific sector
]

SYSTEM_PROMPT = """You are a financial analyst agent. Reliability contract:
1. NEVER state a financial figure that did not come from a tool result.
2. VERIFICATION DUTY — before citing any financial figure from a tool,
   confirm the result includes a filing reference (form type and/or SEC
   URL/accession) and an identifiable period. If a result lacks these,
   say the figure could not be verified rather than citing it. If revenue,
   cost of revenue, and gross profit are all present, check that
   revenue - cost is approximately gross profit; disclose any mismatch.
3. Always report the exact period end date with every figure (fiscal
   quarters differ from calendar quarters).
4. For top-N-by-industry questions, use web research tools and clearly
   attribute the source and as-of date; market caps change daily.
5. For AI-disruption questions: facts about adoption must come from search
   results with sources; forward-looking analysis is your synthesis over
   those facts and should read as reasoning, not reported fact.
6. Multi-company questions: gather per-company data, and if some companies
   fail, report successes and explicitly list failures. Partial answers
   with disclosed gaps beat silent omissions.
7. If a question needs no tools or is out of scope, say so plainly."""


RUN_LIMITS = {"recursion_limit": 30, "timeout_seconds": 180}
 
DEMO_QUERIES = [
    "What was Apple's net income based on their latest quarterly report?",
    "What are the top 5 public companies in healthcare by market cap?",
    "What are the top 3 companies in healthcare, and what was the reported "
    "net income for each?",
    "How can AI disrupt the healthcare industry? Base facts on sources.",
    "What was Stripe's net income last quarter?",   # reliability demo: refusal
]

async def load_tools(list_only: bool = False):
    client = MultiServerMCPClient(SERVERS)
    tools = await client.get_tools()
    if list_only:
        for t in tools:
            print(f"  {t.name}: {(t.description or '')[:90]}")
        return []
    curated = [t for t in tools 
               if any(k in t.name.lower() for k in ALLOWED_TOOLS)]
    print(f"Discovered {len(tools)} tools; curated to {len(curated)}: "
          f"{[t.name for t in curated]}\n")
    return curated

async def run_query(agent, query: str, thread_id: str = "cli") -> str:
    deadline = time.time() + RUN_LIMITS["timeout_seconds"]
    final = None
    config = {"recursion_limit": RUN_LIMITS["recursion_limit"],
              "configurable": {"thread_id": thread_id}}
    async for chunk in agent.astream({"messages": [("user", query)]}, 
                               config=config, stream_mode="values"):
        final = chunk
        if time.time() > deadline:
            return ("Execution budget exceeded; no verified final answer. "
                    "Try a narrower query.")
    return final["messages"][-1].content

async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--list-tools", action="store_true")
    parser.add_argument("query", nargs="*")
    args = parser.parse_args()
 
    if args.list_tools:
        await load_tools(list_only=True)
        return
 
    tools = await load_tools()
    llm = ChatAnthropic(model="claude-sonnet-4-6", temperature=0, max_tokens=4000)
    agent = create_agent(llm, tools, system_prompt=SYSTEM_PROMPT,
                          checkpointer=InMemorySaver())

    if args.demo:
        for i, q in enumerate(DEMO_QUERIES):
            print(f"\n=== Q: {q}\n")
            print(await run_query(agent, q, thread_id=f"demo-{i}"))
    elif args.query:
        print(await run_query(agent, " ".join(args.query)))
    else:
        print("Financial analyst agent (MCP composition). Ctrl-C to exit.")
        while True:
            try:
                q = input("\nyou> ").strip()
            except (KeyboardInterrupt, EOFError):
                break
            if q:
                print("\n" + await run_query(agent, q))
 
 
if __name__ == "__main__":
    asyncio.run(main())