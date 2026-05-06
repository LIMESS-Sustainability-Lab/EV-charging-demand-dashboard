import json
import warnings
from typing import Any, Literal, Optional, Union

import geopandas as gpd
from pydantic import BaseModel, ConfigDict, Field, field_validator

_WGS84 = "EPSG:4326"


def _gdf_to_geojson(gdf: gpd.GeoDataFrame) -> dict:
    if gdf.crs is None:
        warnings.warn(
            "GeoDataFrame has no CRS set; assuming EPSG:4326 (WGS84). "
            "Set `gdf.set_crs(...)` explicitly to silence this warning.",
            stacklevel=3,
        )
    elif str(gdf.crs) != _WGS84 and gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(_WGS84)
    # to_json returns a string; round-trip to dict so the serialized
    # layer is clean JSON rather than a string-inside-dict.
    return json.loads(gdf.to_json())


class _BaseLayer(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    id: str
    data: Union[dict, gpd.GeoDataFrame] = Field(
        default_factory=lambda: {
            "type": "FeatureCollection",
            "features": [],
        },
        description="GeoJSON FeatureCollection or a GeoDataFrame.",
    )
    color: Optional[str] = None
    color_by: Optional[str] = None
    color_scale: Optional[list[tuple[float, str]]] = None
    size_by: Optional[str] = Field(
        default=None,
        description=(
            "Property name whose value drives the feature size "
            "(`radius` for points, `line_width` for lines). Requires "
            "`size_scale` to be set."
        ),
    )
    size_scale: Optional[list[tuple[float, float]]] = Field(
        default=None,
        description=(
            "List of (stop, size_in_px) pairs defining a linear "
            "interpolation of feature size on the `size_by` property."
        ),
    )
    opacity: float = 1.0
    clickable: bool = False
    hoverable: bool = False
    tooltip: Optional[str] = Field(
        default=None,
        description=(
            "Optional tooltip template shown on hover when `hoverable` "
            "is True. Uses `{property_name}` placeholders that are "
            "substituted from the feature's properties, e.g. "
            "'Demand: {value:.2f}'."
        ),
    )

    @field_validator("data", mode="before")
    @classmethod
    def _coerce_data(cls, v: Any) -> dict:
        if isinstance(v, gpd.GeoDataFrame):
            return _gdf_to_geojson(v)
        if isinstance(v, dict):
            return v
        raise TypeError(
            f"`data` must be a GeoJSON dict or GeoDataFrame, got {type(v).__name__}"
        )

    def to_dict(self) -> dict:
        return self.model_dump()


class PointsLayer(_BaseLayer):
    type: Literal["points"] = "points"
    radius: float = Field(
        default=6.0, description="Circle radius in pixels."
    )
    stroke_width: float = Field(
        default=1.0,
        description="Outline width in pixels. Set to 0 for no outline.",
    )
    stroke_color: str = Field(
        default="#ffffff", description="Outline color."
    )


class PolygonsLayer(_BaseLayer):
    type: Literal["polygons"] = "polygons"


class LinesLayer(_BaseLayer):
    type: Literal["lines"] = "lines"
    line_width: float = Field(
        default=2.0, description="Line width in pixels."
    )


# Viridis palette - perceptually uniform, color-blind safe.
_VIRIDIS_COLORS = [
    "#440154",
    "#443983",
    "#31688e",
    "#21918c",
    "#35b779",
    "#8fd744",
    "#fde725",
]


def viridis_scale(
    lo: float, hi: float, *, n: int = 7
) -> list[tuple[float, str]]:
    if hi <= lo:
        hi = lo + 1e-9
    n = max(2, min(n, len(_VIRIDIS_COLORS)))
    idxs = [
        round(i * (len(_VIRIDIS_COLORS) - 1) / (n - 1))
        for i in range(n)
    ]
    colors = [_VIRIDIS_COLORS[i] for i in idxs]
    return [
        (lo + (hi - lo) * i / (n - 1), c)
        for i, c in enumerate(colors)
    ]


def linear_size_scale(
    lo: float, hi: float, *, min_px: float, max_px: float
) -> list[tuple[float, float]]:
    if hi <= lo:
        hi = lo + 1e-9
    return [(lo, min_px), (hi, max_px)]


__all__ = [
    "PointsLayer",
    "PolygonsLayer",
    "LinesLayer",
    "viridis_scale",
    "linear_size_scale",
]
