import math
from functools import lru_cache
from typing import Any

from shapely import wkt
from shapely.geometry import Point
from shapely.geometry.base import BaseGeometry
from sqlalchemy import text

from dashboard.shared.data.engine import get_engine


@lru_cache(maxsize=1)
def prague_polygon() -> BaseGeometry:
    sql = text(
        'SELECT ST_AsText(ST_Transform(geometry, 4326)) AS wkt '
        'FROM public.area_kraje WHERE "OBJECTID" = 1'
    )
    with get_engine().connect() as conn:
        row = conn.execute(sql).fetchone()
    if row is None:
        raise RuntimeError(
            "Prague boundary not found in public.area_kraje (OBJECTID=1)."
        )
    return wkt.loads(row[0])


def is_in_prague(lat: float, lng: float) -> bool:
    return prague_polygon().contains(Point(lng, lat))


def format_value(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        if math.isnan(value):
            return "-"
        if value == 0:
            return "0"
        if abs(value) < 1:
            return f"{value:.4g}"
        return f"{value:,.2f}"
    if isinstance(value, int):
        return f"{value:,}"
    return str(value)


def split_prefix(key: str) -> tuple[str, str]:
    if "_" in key:
        prefix, _, rest = key.partition("_")
        return prefix, rest
    return "", key
