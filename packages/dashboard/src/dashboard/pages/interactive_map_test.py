"""Smoke-test page for the new `InteractiveMap` component.

Mounts two clickable layers (points + polygons) and echoes both event
props into a JSON viewer so we can verify click routing end-to-end.
"""

import json

import dash
import dash_mantine_components as dmc
import geopandas as gpd
from dash import Input, Output, State, callback, html
from shapely.geometry import Point, Polygon

from dash_spatial_prediction import (
    InteractiveMap,
    PointsLayer,
    PolygonsLayer,
)


PRAGUE_LNG = 14.4292
PRAGUE_LAT = 50.0856

POINTS_GDF = gpd.GeoDataFrame(
    {
        "name": ["Alpha", "Bravo", "Charlie"],
        "kind": ["sample"] * 3,
        "geometry": [
            Point(PRAGUE_LNG, PRAGUE_LAT),
            Point(PRAGUE_LNG + 0.01, PRAGUE_LAT + 0.005),
            Point(PRAGUE_LNG - 0.012, PRAGUE_LAT - 0.004),
        ],
    },
    crs="EPSG:4326",
)


def _box(
    west: float, south: float, east: float, north: float
) -> Polygon:
    return Polygon(
        [
            (west, south),
            (east, south),
            (east, north),
            (west, north),
            (west, south),
        ]
    )


POLYGONS_GDF = gpd.GeoDataFrame(
    {
        "name": ["North zone", "South zone"],
        "value": [0.2, 0.85],
        "geometry": [
            _box(
                PRAGUE_LNG - 0.02,
                PRAGUE_LAT + 0.008,
                PRAGUE_LNG + 0.00,
                PRAGUE_LAT + 0.018,
            ),
            _box(
                PRAGUE_LNG + 0.005,
                PRAGUE_LAT - 0.02,
                PRAGUE_LNG + 0.025,
                PRAGUE_LAT - 0.008,
            ),
        ],
    },
    crs="EPSG:4326",
)

INITIAL_LAYERS = [
    PolygonsLayer(
        id="zones",
        data=POLYGONS_GDF,
        color_by="value",
        color_scale=[(0.0, "#f7fbff"), (1.0, "#08306b")],
        opacity=0.6,
        clickable=True,
        hoverable=True,
        tooltip="{name} - value: {value:.2f}",
    ).to_dict(),
    PointsLayer(
        id="samples",
        data=POINTS_GDF,
        color="#d62728",
        clickable=True,
        hoverable=True,
        tooltip="{name} ({kind})",
    ).to_dict(),
]

MAP_ID = "im-test-map"
LOG_ID = "im-test-log"
ADD_BTN_ID = "im-test-add-btn"


def _log_panel(title: str, payload):
    return dmc.Paper(
        dmc.Stack(
            [
                dmc.Text(title, fw="bold", size="sm"),
                dmc.Code(
                    json.dumps(payload, indent=2)
                    if payload
                    else "null",
                    block=True,
                ),
            ],
            gap="xs",
        ),
        withBorder=True,
        radius="md",
        p="sm",
    )


layout = dmc.Container(
    dmc.Stack(
        [
            dmc.Title("InteractiveMap smoke test", order=3),
            dmc.Text(
                "Hover a feature → highlight + tooltip. "
                "Click empty space → clickedCoord updates. "
                "Click a red point or a blue polygon → clickedFeature "
                "updates. Click 'Add layer' to verify live layer diffing.",
                c="gray",
                size="sm",
            ),
            dmc.Group(
                [
                    dmc.Button(
                        "Add extra point layer", id=ADD_BTN_ID
                    ),
                ]
            ),
            dmc.Paper(
                InteractiveMap(
                    id=MAP_ID,
                    layers=INITIAL_LAYERS,
                    center=[PRAGUE_LNG, PRAGUE_LAT],
                    zoom=13,
                    height="500px",
                ),
                withBorder=True,
                radius="md",
                style={"overflow": "hidden"},
            ),
            dmc.SimpleGrid(
                [
                    html.Div(id=f"{LOG_ID}-coord"),
                    html.Div(id=f"{LOG_ID}-feature"),
                ],
                cols=2,
                spacing="md",
            ),
        ],
        gap="md",
    ),
    size="xl",
    p="md",
)


@callback(
    Output(f"{LOG_ID}-coord", "children"),
    Input(MAP_ID, "clickedCoord"),
)
def _show_coord(coord):
    return _log_panel("clickedCoord", coord)


@callback(
    Output(f"{LOG_ID}-feature", "children"),
    Input(MAP_ID, "clickedFeature"),
)
def _show_feature(feature):
    return _log_panel("clickedFeature", feature)


@callback(
    Output(MAP_ID, "layers"),
    Input(ADD_BTN_ID, "n_clicks"),
    State(MAP_ID, "layers"),
    prevent_initial_call=True,
)
def _add_layer(n, current_layers):
    if not n:
        return dash.no_update
    extra_id = f"extra-{n}"
    extra = PointsLayer(
        id=extra_id,
        data={
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {"name": extra_id},
                    "geometry": {
                        "type": "Point",
                        "coordinates": [
                            PRAGUE_LNG + 0.003 * n,
                            PRAGUE_LAT - 0.003 * n,
                        ],
                    },
                }
            ],
        },
        color="#2ca02c",
        clickable=True,
    ).to_dict()
    return list(current_layers) + [extra]
