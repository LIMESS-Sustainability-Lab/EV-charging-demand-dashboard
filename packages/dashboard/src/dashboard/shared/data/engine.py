from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from dashboard.settings import settings


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    return create_engine(settings.POSTGRES_CONNECTION_STRING)
