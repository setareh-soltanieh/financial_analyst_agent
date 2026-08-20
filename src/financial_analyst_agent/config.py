"""Runtime configuration for the financial analyst agent."""

import os
import sys

from dotenv import load_dotenv

load_dotenv()

SEC_EDGAR_USER_AGENT = os.environ.get("SEC_EDGAR_USER_AGENT")
TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY")
ALPHAVANTAGE_API_KEY = os.environ.get("ALPHAVANTAGE_API_KEY")

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
    "yfmcp": {
        "command": "uvx",
        "args": ["yfmcp@latest"],
        "transport": "stdio",
    },
    "alphavantage": {
        "command": "uvx",
        "args": ["--with", "python-dotenv", "--with", "mcp==1.9.4", "alphavantage-mcp"],
        "transport": "stdio",
        "env": {"ALPHAVANTAGE_API_KEY": ALPHAVANTAGE_API_KEY}
    },
}

ALLOWED_TOOLS = [
    "search_companies",
    "get_company_info",
    "get_recent_filings",
    "get_financials",
    "get_segment_data",
    "get_filing_sections",
    "compare_periods",
    "get_filing_content",   # ← re-added: fallback for non-GAAP / narrative-only disclosures

    "yfinance_get_top",
    "yfinance_get_ticker_info",
    "yfinance_get_financials",
    "yfinance_screen",

    "company_overview",
    "income_statement",
    "balance_sheet",
    "symbol_search",

    "tavily_search",
    "tavily_extract",
    "tavily_map",
    "tavily_crawl",
    "tavily_research",

    "pdf",
]

RUN_LIMITS = {"recursion_limit": 30, "timeout_seconds": 180}
