import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

from tools import cached_get, resolve_company

print(resolve_company("Meta"))