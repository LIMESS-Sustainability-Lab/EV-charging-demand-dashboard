import json
from functools import partial
from typing import Any, Optional

import dash_mantine_components as dmc
from dash import MATCH, Input, Output, callback, html
from dash.development.base_component import Component
from dash_pydantic_form import ids as common_ids
from dash_pydantic_form.fields import DEFAULT_FIELDS_REPR
from dash_pydantic_form.fields.base_fields import BaseField
from dash_pydantic_form.ids import field_dependent_id
from pydantic import Field
from pydantic.fields import FieldInfo
from pydantic_core import core_schema
from shapely.geometry import Point

from .InteractiveMap import InteractiveMap

MARKER_LAYER_ID = "pydf-maplocation-marker"


def _marker_layer(lng: Optional[float], lat: Optional[float]) -> dict:
    features: list[dict] = []
    if lng is not None and lat is not None:
        features.append(
            {
                "type": "Feature",
                "properties": {},
                "geometry": {
                    "type": "Point",
                    "coordinates": [lng, lat],
                },
            }
        )
    return {
        "id": MARKER_LAYER_ID,
        "type": "points",
        "data": {"type": "FeatureCollection", "features": features},
        "color": "#d62728",
        "radius": 8,
        "stroke_width": 2,
        "stroke_color": "#ffffff",
        "opacity": 1.0,
    }


class MapLocation:
    # Plain class (not a BaseModel) so dash-pydantic-form renders it via
    # MapLocationField below rather than as a nested subsection.
    __slots__ = ("lat", "lng")

    def __init__(self, lat: float, lng: float):
        self.lat = lat
        self.lng = lng

    def to_point(self) -> Point:
        return Point(self.lng, self.lat)

    def __repr__(self) -> str:
        return f"MapLocation(lat={self.lat}, lng={self.lng})"

    @classmethod
    def __get_pydantic_core_schema__(cls, _source_type, _handler):
        def _validate(v):
            if isinstance(v, cls):
                return v
            if isinstance(v, str):
                try:
                    v = json.loads(v)
                except json.JSONDecodeError as e:
                    raise ValueError(
                        f"Invalid JSON for MapLocation: {v!r}"
                    ) from e
            if isinstance(v, dict):
                return cls(lat=v["lat"], lng=v["lng"])
            raise ValueError(
                f"Cannot convert {type(v)} to MapLocation"
            )

        return core_schema.no_info_plain_validator_function(
            _validate,
            serialization=core_schema.plain_serializer_function_ser_schema(
                lambda v: {"lat": v.lat, "lng": v.lng},
                info_arg=False,
            ),
        )


class MapLocationField(BaseField):
    base_component = None
    full_width: bool = True

    class ids(BaseField.ids):
        map = partial(field_dependent_id, "_pydf-maplocation-map")

    center_lat: float = Field(default=50.08563801157197)
    center_lon: float = Field(default=14.429168701171875)
    zoom: int = Field(default=13)
    height: str = Field(default="400px")
    map_style: str = Field(
        default="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
    )

    def _render(
        self,
        *,
        item: Any,
        aio_id: str,
        form_id: str,
        field: str,
        parent: str = "",
        field_info: FieldInfo,
    ) -> Component:
        value = self.get_value(item, field, parent)

        if isinstance(value, MapLocation):
            initial_lat, initial_lng = value.lat, value.lng
        elif (
            isinstance(value, dict)
            and "lat" in value
            and "lng" in value
        ):
            initial_lat, initial_lng = value["lat"], value["lng"]
        else:
            initial_lat, initial_lng = (
                self.center_lat,
                self.center_lon,
            )

        title = self.get_title(field_info, field_name=field)
        description = self.get_description(field_info)

        hidden_value_id = common_ids.value_field(
            aio_id, form_id, field, parent, meta=""
        )
        map_id = self.ids.map(aio_id, form_id, field, parent)

        map_component = InteractiveMap(
            id=map_id,
            layers=[_marker_layer(initial_lng, initial_lat)],
            center=[self.center_lon, self.center_lat],
            zoom=self.zoom,
            height=self.height,
            mapStyle=self.map_style,
        )

        # Hidden input - dash-pydantic-form reads this as the value.
        hidden_value = html.Div(
            dmc.TextInput(
                id=hidden_value_id,
                value=json.dumps(
                    {"lat": initial_lat, "lng": initial_lng}
                ),
            ),
            style={"display": "none"},
        )

        children: list = []
        if title is not None:
            children.append(
                dmc.Text(
                    title,
                    size="sm",
                    mt=3,
                    mb=5,
                    fw=500,
                    lh=1.55,
                )
            )
        if description is not None:
            children.append(
                dmc.Text(
                    description,
                    size="xs",
                    c="dimmed",
                    mt=-5,
                    mb=5,
                    lh=1.2,
                )
            )
        children.append(map_component)
        children.append(hidden_value)

        return dmc.Stack(children, gap=0)


@callback(
    Output(
        common_ids.value_field(MATCH, MATCH, MATCH, MATCH, ""),
        "value",
        allow_duplicate=True,
    ),
    Output(
        MapLocationField.ids.map(MATCH, MATCH, MATCH, MATCH),
        "layers",
    ),
    Input(
        MapLocationField.ids.map(MATCH, MATCH, MATCH, MATCH),
        "clickedCoord",
    ),
    prevent_initial_call=True,
)
def _sync_value_from_click(coord: Optional[dict]):
    if not coord:
        from dash import no_update

        return no_update, no_update
    lng = coord["lng"]
    lat = coord["lat"]
    return (
        json.dumps({"lat": lat, "lng": lng}),
        [_marker_layer(lng, lat)],
    )


DEFAULT_FIELDS_REPR[MapLocation] = MapLocationField
