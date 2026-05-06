from typing import Optional

import dash
import dash_mantine_components as dmc
from dash import ALL, Input, Output, State, callback, dcc, html
from dash_iconify import DashIconify

from dash_spatial_prediction import InteractiveMap, PointsLayer

NoUpdate = dash.NoUpdate

PRAGUE_LNG = 14.4292
PRAGUE_LAT = 50.0856

MAP_ID = "pp-map"
STORE_ID = "pp-store"
LIST_ID = "pp-list"
CLEAR_ID = "pp-clear"

# Stable id so the React side only diffs `data`, not the whole layer.
POINTS_LAYER_ID = "placed"


def _points_gj(points: list[dict]) -> dict:
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"index": i},
                "geometry": {
                    "type": "Point",
                    "coordinates": [p["lng"], p["lat"]],
                },
            }
            for i, p in enumerate(points)
        ],
    }


def _build_layer(points: list[dict]) -> dict:
    return PointsLayer(
        id=POINTS_LAYER_ID,
        data=_points_gj(points),
        color="#2ca02c",
        hoverable=True,
        tooltip="point #{index}",
    ).to_dict()


def _point_row(index: int, point: dict):
    return dmc.Group(
        [
            dmc.Text(f"#{index}", fw="bold", size="sm", w=36),
            dmc.Text(
                f"lng {point['lng']:.5f}  ·  lat {point['lat']:.5f}",
                size="sm",
                c="gray",
                style={"flex": 1, "fontFamily": "monospace"},
            ),
            dmc.ActionIcon(
                DashIconify(icon="tabler:x", width=14),
                id={"type": "pp-delete", "index": index},
                color="red",
                variant="subtle",
                size="sm",
            ),
        ],
        gap="sm",
        wrap="nowrap",
    )


layout = dmc.Container(
    dmc.Stack(
        [
            dmc.Title("Place points demo", order=3),
            dmc.Text(
                "Click on the map to drop a point. "
                "Use the side list to review, delete individually, or "
                "clear all.",
                c="gray",
                size="sm",
            ),
            dmc.Group(
                [
                    dmc.Button(
                        "Clear all",
                        id=CLEAR_ID,
                        variant="light",
                        color="red",
                        leftSection=DashIconify(
                            icon="tabler:trash", width=16
                        ),
                    ),
                ]
            ),
            dmc.Grid(
                [
                    dmc.GridCol(
                        dmc.Paper(
                            InteractiveMap(
                                id=MAP_ID,
                                layers=[_build_layer([])],
                                center=[PRAGUE_LNG, PRAGUE_LAT],
                                zoom=13,
                                height="560px",
                            ),
                            withBorder=True,
                            radius="md",
                            style={"overflow": "hidden"},
                        ),
                        span=8,
                    ),
                    dmc.GridCol(
                        dmc.Paper(
                            dmc.Stack(
                                [
                                    dmc.Group(
                                        [
                                            DashIconify(
                                                icon="tabler:map-pin",
                                                width=18,
                                            ),
                                            dmc.Text(
                                                "Placed points",
                                                fw="bold",
                                            ),
                                            dmc.Badge(
                                                "0",
                                                id=f"{LIST_ID}-count",
                                                variant="light",
                                                ml="auto",
                                            ),
                                        ],
                                        gap="xs",
                                    ),
                                    dmc.Divider(),
                                    dmc.ScrollArea(
                                        html.Div(
                                            id=LIST_ID,
                                            style={
                                                "display": "flex",
                                                "flexDirection": "column",
                                                "gap": "6px",
                                            },
                                        ),
                                        h=490,
                                        type="auto",
                                    ),
                                ],
                                gap="sm",
                                h="100%",
                            ),
                            withBorder=True,
                            radius="md",
                            p="md",
                            h="100%",
                        ),
                        span=4,
                    ),
                ],
                gutter="md",
            ),
            dcc.Store(id=STORE_ID, data=[]),
        ],
        gap="md",
    ),
    size="xl",
    p="md",
)


@callback(
    Output(STORE_ID, "data"),
    Input(MAP_ID, "clickedCoord"),
    Input({"type": "pp-delete", "index": ALL}, "n_clicks"),
    Input(CLEAR_ID, "n_clicks"),
    State(STORE_ID, "data"),
    prevent_initial_call=True,
)
def _mutate_store(
    clicked_coord: Optional[dict],
    delete_clicks: list[Optional[int]],
    clear_clicks: Optional[int],
    points: list[dict],
) -> list[dict] | NoUpdate:
    trigger = dash.ctx.triggered_id

    if trigger == CLEAR_ID:
        return [] if clear_clicks else dash.no_update

    if trigger == MAP_ID:
        if not clicked_coord:
            return dash.no_update
        return list(points) + [
            {"lng": clicked_coord["lng"], "lat": clicked_coord["lat"]}
        ]

    if (
        isinstance(trigger, dict)
        and trigger.get("type") == "pp-delete"
    ):
        idx = trigger["index"]
        matching = [
            n
            for n, pid in zip(
                delete_clicks,
                dash.ctx.inputs_list[1],
            )
            if pid["id"]["index"] == idx
        ]
        if not matching or not matching[0]:
            return dash.no_update
        if 0 <= idx < len(points):
            return [p for i, p in enumerate(points) if i != idx]

    return dash.no_update


@callback(
    Output(MAP_ID, "layers"),
    Output(LIST_ID, "children"),
    Output(f"{LIST_ID}-count", "children"),
    Input(STORE_ID, "data"),
)
def _render_from_store(points: list[dict]):
    layers = [_build_layer(points)]
    if not points:
        list_children = dmc.Text(
            "No points yet - click the map to start.",
            size="sm",
            c="gray",
            ta="center",
            py="md",
        )
    else:
        list_children = [
            _point_row(i, p) for i, p in enumerate(points)
        ]
    return layers, list_children, str(len(points))
