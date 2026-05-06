import importlib
from dataclasses import dataclass

import dash

from dashboard.settings import settings


@dataclass(frozen=True)
class Route:
    module: str
    path: str
    name: str


ROUTES: list[Route] = [
    Route(
        module="dashboard.latent_curve_model.pages.interactive_map",
        path="/interactive-map",
        name="Location prediction",
    ),
    Route(
        module="dashboard.latent_curve_model.pages.compare_locations",
        path="/compare-locations",
        name="Compare locations",
    ),
    Route(
        module="dashboard.latent_curve_model.pages.sample_uncertainty",
        path="/sample-uncertainty",
        name="Location prediction with uncertainty",
    ),
    *(
        [
            Route(
                module="dashboard.pages.charging_sessions",
                path="/charging-sessions",
                name="Charging sessions",
            ),
            Route(
                module="dashboard.pages.nearest_network",
                path="/nearest-network",
                name="Nearest network",
            ),
            Route(
                module="dashboard.pages.place_points",
                path="/place-points",
                name="Place points",
            ),
            Route(
                module="dashboard.pages.interactive_map_test",
                path="/interactive-map-test",
                name="InteractiveMap test",
            ),
        ]
        if settings.ENABLE_DEV_PAGES
        else []
    ),
]


def register_pages() -> None:
    for route in ROUTES:
        module = importlib.import_module(route.module)
        dash.register_page(
            route.module,
            path=route.path,
            name=route.name,
            layout=getattr(module, "layout", None),
        )
