"""Runtime configuration for the financial analyst agent."""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

EDGAR_IDENTITY = os.environ.get("EDGAR_IDENTITY")
TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY")
ALPHAVANTAGE_API_KEY = os.environ.get("ALPHAVANTAGE_API_KEY")

SERVERS = {
    "sec_edgar": {
        "command": sys.executable,
        "args": ["-m", "edgar.ai"],
        "env": {"EDGAR_IDENTITY": EDGAR_IDENTITY},
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
    "edgar_company",        
    "edgar_search",         
    "edgar_filing",         
    "edgar_read",           
    "edgar_text_search",    
    "edgar_compare",        
    "edgar_ownership",      
    "edgar_trends",         
    "edgar_screen",         
    "edgar_notes",          

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

# --- Tool-result cache -------------------------------------------------
# Persists MCP tool call results across runs so repeated eval/demo passes
# don't re-hit SEC EDGAR/Tavily/AlphaVantage/yfinance for identical calls.
# Disable entirely with TOOL_CACHE_ENABLED=false (e.g. to rule the cache
# out while debugging a stale-data issue).
TOOL_CACHE_ENABLED = os.environ.get("TOOL_CACHE_ENABLED", "true").strip().lower() not in (
    "0",
    "false",
    "no",
)
TOOL_CACHE_DB_PATH = os.environ.get(
    "TOOL_CACHE_DB_PATH",
    str(Path(__file__).resolve().parents[2] / "cache" / "tool_cache.sqlite3"),
)
TOOL_CACHE_DEFAULT_TTL_SECONDS = int(os.environ.get("TOOL_CACHE_DEFAULT_TTL_SECONDS", 3600))

# Tools whose results are session-local (local file paths) or otherwise
# unsuited to a shared cache — never cached regardless of TOOL_CACHE_ENABLED.
TOOL_CACHE_EXCLUDED_TOOLS = {"pdf_evidence", "read_pdf", "search_pdf"}

# Per-tool TTLs, grouped by how fast the underlying data actually changes.
TOOL_CACHE_TTL_SECONDS = {
    # SEC EDGAR: filings and the facts derived from them are point-in-time
    # and immutable once published, so these can be cached aggressively.
    "edgar_company": 86400,
    "edgar_filing": 86400,
    "edgar_read": 86400,
    "edgar_compare": 86400,
    "edgar_trends": 86400,
    "edgar_notes": 86400,
    # Search/screen/ownership results can shift as new filings land.
    "edgar_search": 21600,
    "edgar_text_search": 21600,
    "edgar_ownership": 21600,
    "edgar_screen": 21600,

    # yfinance: ticker info and screeners carry live price/market-cap data.
    "yfinance_get_ticker_info": 900,
    "yfinance_screen": 900,
    "yfinance_get_top": 3600,
    "yfinance_get_financials": 86400,

    # AlphaVantage fundamentals update on a quarterly filing cadence.
    "symbol_search": 86400,
    "income_statement": 86400,
    "balance_sheet": 86400,
    "company_overview": 21600,

    # Tavily: live web content, cached for a partial day.
    "tavily_search": 21600,
    "tavily_extract": 21600,
    "tavily_crawl": 21600,
    "tavily_map": 21600,
    "tavily_research": 21600,
}

# Argument keys never accounted into the cache key even if a server starts
# sending them (per-call identifiers that don't affect the result).
TOOL_CACHE_IGNORED_ARG_KEYS = {"request_id", "trace_id", "session_id", "call_id", "idempotency_key"}

# Argument keys treated as ticker/CIK identifiers and upper-cased for the
# cache key, so "msft" and "MSFT" hit the same entry.
TOOL_CACHE_TICKER_ARG_KEYS = {"identifier", "identifiers", "symbol", "ticker"}
