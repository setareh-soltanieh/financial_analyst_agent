import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

from tools import cached_get

data = cached_get("https://www.sec.gov/files/company_tickers.json")

print(len(data))