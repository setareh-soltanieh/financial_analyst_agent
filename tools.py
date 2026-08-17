import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Any
import httpx

logger = logging.getLogger(__name__)

CACHE_DIR = Path(__file__).parent / "cache"
CACHE_DIR.mkdir(exist_ok=True)

HEADERS = {
    # SEC EDGAR rejects requests without a real User-Agent identifying you
    "User-Agent": "Financial Analyst Agent setarehsoltanieh78@gmail.com"
}

# SEC EDGAR allows 10 req/sec 
_MIN_REQUEST_INTERVAL = 0.15  # seconds
_last_request_time = 0.0

def ttl_for_url(url: str) -> int:
    """Return the TTL (time-to-live) for a given URL in seconds."""

    if "company_tickers" in url:
        return 7 * 24 * 60 * 60  # 1 week
    return 24 * 60 * 60  # 1 day for other URLs

def _rate_limit() -> None:
    """Ensure that requests are rate-limited to avoid hitting SEC EDGAR limits."""

    global _last_request_time
    elapsed = time.time() - _last_request_time
    if elapsed < _MIN_REQUEST_INTERVAL:
        time.sleep(_MIN_REQUEST_INTERVAL - elapsed)
    _last_request_time = time.time()

def _fetch_with_retry(url: str, max_attempts: int = 3) -> Any:
    for attempt in range(max_attempts):
        _rate_limit()
        resp = httpx.get(url, headers=HEADERS, timeout=30)
        if resp.status_code == 429 or resp.status_code >= 500:
            # Retry on rate limit or server errors
            if attempt < max_attempts - 1:
                logger.warning(
                    "GET %s returned %d, retrying (attempt %d/%d)",
                    url, resp.status_code, attempt + 1, max_attempts,
                )
                time.sleep(2 ** attempt)  # Exponential backoff
                continue
        resp.raise_for_status()
        return resp.json()

# # 1. Infrastructure
def cached_get(url: str) -> Any:
    # Check if the response is already cached
    cache_file = CACHE_DIR / f"{hashlib.md5(url.encode()).hexdigest()}.json"
    if cache_file.exists():
        age = time.time() - cache_file.stat().st_mtime
        if age < ttl_for_url(url):
            logger.info("cache HIT (age %.0fs): %s", age, url)
            return json.loads(cache_file.read_text())
        logger.info("cache STALE (age %.0fs > ttl %ds): %s", age, ttl_for_url(url), url)
    else:
        logger.info("cache MISS: %s", url)
    data = _fetch_with_retry(url)
    cache_file.write_text(json.dumps(data))
    logger.info("cached response: %s", url)
    return data


# # 2. Company resolution
# resolve_company()

# # 3. Financial extraction
# pick_latest_quarterly()
# get_financials_impl()

# # 4. Other capabilities
# top_companies_impl()
# ai_disruption_impl()