from functools import lru_cache
from typing import Optional

import dash
import dash_mantine_components as dmc
import geopandas as gpd
import networkx as nx
import osmnx as ox
from dash import Input, Output, State, callback, html
from dash_iconify import DashIconify
from shapely.geometry import Point

from dash_spatial_prediction import (
    InteractiveMap,
    LinesLayer,
    PointsLayer,
    linear_size_scale,
    viridis_scale,
)
from dashboard.shared.data.engine import get_engine


PRAGUE_LNG = 14.4292
PRAGUE_LAT = 50.0856

NODES_TABLE = "osm.network_nodes_statistic"
EDGES_TABLE = "osm.network_edges_statistic"
BC_COL = "node_bc"

MAP_ID = "nn-map"
CLICK_LAYER = "clicked"
NODE_LAYER = "nearest-node"
EGO_EDGES_LAYER = "ego-edges"
EGO_NODES_LAYER = "ego-nodes"

RADIUS_ID = "nn-radius"
RADIUS_DEFAULT = 400  # meters (edge-length units)
INFO_ID = "nn-info"


# Multi-MB tables; cache once per process.
@lru_cache(maxsize=1)
def _load_graph() -> "nx.MultiDiGraph":
    nodes = gpd.read_postgis(
        f"SELECT * FROM {NODES_TABLE}",
        get_engine(),
        geom_col="geometry",
    ).set_index("osmid")
    edges = gpd.read_postgis(
        f"SELECT * FROM {EDGES_TABLE}",
        get_engine(),
        geom_col="geometry",
    ).set_index(["u", "v", "key"])
    return ox.graph_from_gdfs(nodes, edges)


def _ego_layers(
    lng: float, lat: float, radius: int
) -> tuple[list, dict]:
    G = _load_graph()
    node_id = ox.distance.nearest_nodes(G, [lng], [lat])[0]
    ego = nx.ego_graph(G, node_id, radius=radius, distance="length")

    ego_nodes = ox.graph_to_gdfs(ego, nodes=True, edges=False)
    ego_edges = ox.graph_to_gdfs(ego, nodes=False, edges=True)

    # OSMnx node geometry lives on the GeoDataFrame, not the node attrs.
    center_node = G.nodes[node_id]
    center_point = Point(center_node["x"], center_node["y"])
    center_gdf = gpd.GeoDataFrame(
        {"geometry": [center_point]},
        crs=ego_nodes.crs or "EPSG:4326",
    )

    click_gdf = gpd.GeoDataFrame(
        {"geometry": [Point(lng, lat)]},
        crs="EPSG:4326",
    )

    node_bc = G.nodes[node_id].get(BC_COL)

    # Color/size ramps span the ego range, not the whole city's.
    node_bc_vals = (
        ego_nodes["node_bc"].dropna()
        if "node_bc" in ego_nodes
        else None
    )
    edge_bc_vals = (
        ego_edges["edge_bc"].dropna()
        if "edge_bc" in ego_edges
        else None
    )
    node_lo = (
        float(node_bc_vals.min())
        if node_bc_vals is not None and not node_bc_vals.empty
        else 0.0
    )
    node_hi = (
        float(node_bc_vals.max())
        if node_bc_vals is not None and not node_bc_vals.empty
        else 1.0
    )
    edge_lo = (
        float(edge_bc_vals.min())
        if edge_bc_vals is not None and not edge_bc_vals.empty
        else 0.0
    )
    edge_hi = (
        float(edge_bc_vals.max())
        if edge_bc_vals is not None and not edge_bc_vals.empty
        else 1.0
    )

    info = {
        "node_id": int(node_id),
        "node_bc": float(node_bc) if node_bc is not None else None,
        "ego_nodes": len(ego_nodes),
        "ego_edges": len(ego_edges),
        "node_bc_range": (node_lo, node_hi),
        "edge_bc_range": (edge_lo, edge_hi),
    }

    layers = [
        LinesLayer(
            id=EGO_EDGES_LAYER,
            data=ego_edges,
            color_by="edge_bc",
            color_scale=viridis_scale(edge_lo, edge_hi),
            size_by="edge_bc",
            size_scale=linear_size_scale(
                edge_lo, edge_hi, min_px=1.5, max_px=7.0
            ),
            opacity=0.95,
        ).to_dict(),
        PointsLayer(
            id=NODE_LAYER,
            data=center_gdf,
            color="#d62728",
            radius=7,
            hoverable=True,
            tooltip="nearest node",
        ).to_dict(),
        PointsLayer(
            id=CLICK_LAYER,
            data=click_gdf,
            color="#000000",
            opacity=0.9,
            radius=5,
        ).to_dict(),
    ]
    return layers, info


def _info_panel(info: Optional[dict], error: Optional[str] = None):
    if error:
        return dmc.Alert(error, color="red", variant="light")
    if not info:
        return dmc.Text(
            "Click the map to find the nearest street-network node.",
            size="sm",
            c="gray",
        )
    nl, nh = info["node_bc_range"]
    el, eh = info["edge_bc_range"]
    rows = [
        ("Nearest OSM node", f"{info['node_id']}"),
        (
            "Node betweenness (node_bc)",
            f"{info['node_bc']:.3e}"
            if info["node_bc"] is not None
            else "-",
        ),
        ("Ego node_bc range", f"{nl:.2e} – {nh:.2e}"),
        ("Ego edge_bc range", f"{el:.2e} – {eh:.2e}"),
        ("Ego nodes", f"{info['ego_nodes']}"),
        ("Ego edges", f"{info['ego_edges']}"),
    ]
    return dmc.Stack(
        [
            dmc.Group(
                [
                    dmc.Text(label, size="sm", c="gray"),
                    dmc.Text(value, size="sm", fw=500, ml="auto"),
                ],
                gap="xs",
            )
            for label, value in rows
        ],
        gap="xs",
    )


layout = dmc.Container(
    dmc.Stack(
        [
            dmc.Title("Nearest street network", order=3),
            dmc.Text(
                "Click anywhere on the map; the page queries "
                f"{NODES_TABLE} / {EDGES_TABLE}, finds the nearest node, "
                "and overlays its ego subgraph. The first click triggers "
                "the one-time graph load (may take a few seconds).",
                c="gray",
                size="sm",
            ),
            dmc.Group(
                [
                    dmc.Text("Ego radius (m):", size="sm"),
                    dmc.NumberInput(
                        id=RADIUS_ID,
                        value=RADIUS_DEFAULT,
                        min=50,
                        max=3000,
                        step=50,
                        w=120,
                    ),
                ],
                gap="sm",
            ),
            dmc.Grid(
                [
                    dmc.GridCol(
                        dmc.Paper(
                            InteractiveMap(
                                id=MAP_ID,
                                layers=[],
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
                                                icon="tabler:route",
                                                width=18,
                                            ),
                                            dmc.Text(
                                                "Nearest node",
                                                fw="bold",
                                            ),
                                        ],
                                        gap="xs",
                                    ),
                                    dmc.Divider(),
                                    html.Div(id=INFO_ID),
                                ],
                                gap="sm",
                            ),
                            withBorder=True,
                            radius="md",
                            p="md",
                        ),
                        span=4,
                    ),
                ],
                gutter="md",
            ),
        ],
        gap="md",
    ),
    size="xl",
    p="md",
)


@callback(
    Output(MAP_ID, "layers"),
    Output(INFO_ID, "children"),
    Input(MAP_ID, "clickedCoord"),
    State(RADIUS_ID, "value"),
    prevent_initial_call=True,
)
def _on_click(coord: Optional[dict], radius: Optional[int]):
    if not coord:
        return dash.no_update, dash.no_update
    try:
        layers, info = _ego_layers(
            coord["lng"], coord["lat"], int(radius or RADIUS_DEFAULT)
        )
    except Exception as e:
        return [], _info_panel(None, error=f"{type(e).__name__}: {e}")
    return layers, _info_panel(info)
