"""Runtime configuration for the financial analyst agent."""

import os
import sys

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
    "edgar_company",        # profile, financials, filings, ownership in one call
    "edgar_search",         # find companies by name or list filings by form type
    "edgar_filing",         # structured context for a filing (accession number or URL)
    "edgar_read",           # extract specific sections (risk factors, MD&A, business)
    "edgar_text_search",    # full-text search across filing content (EFTS)
    "edgar_compare",        # compare multiple companies or an industry
    "edgar_ownership",      # insider transactions (Form 4) or institutional holders (13F)
    "edgar_trends",         # financial time series with growth rates
    "edgar_screen",         # discover companies by industry, exchange, or state
    "edgar_notes",          # notes/disclosures behind financial statement numbers

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

    "read_pdf",
    "search_pdf",
]

RUN_LIMITS = {"recursion_limit": 30, "timeout_seconds": 180}
