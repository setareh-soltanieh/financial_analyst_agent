"""Runtime configuration for the financial analyst agent."""

import os
import sys

from dotenv import load_dotenv

load_dotenv()

SEC_EDGAR_USER_AGENT = os.environ.get("SEC_EDGAR_USER_AGENT", "")
TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY", "")
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
    },
    "yfmcp": {
        "command": "uvx",
        "args": ["yfmcp@latest"],
        "transport": "stdio",
    },
}

ALLOWED_TOOLS = [
    "lookup",
    "cik",
    "financial",
    "income",
    "filing",
    "search",
    "extract",
    "pdf",
    "yfinance_get_top",
]

RUN_LIMITS = {"recursion_limit": 30, "timeout_seconds": 180}
