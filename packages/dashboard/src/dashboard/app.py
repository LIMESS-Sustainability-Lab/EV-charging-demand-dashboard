import os
from importlib.metadata import version
from typing import cast

import dash
import dash_mantine_components as dmc
import dash_spatial_prediction  # noqa: F401 - registers _js_dist/_css_dist
from dash import html

from dashboard.router import register_pages
from dashboard.settings import settings

DASHBOARD_VERSION = version("dashboard")

_here = os.path.dirname(os.path.abspath(__file__))

app = dash.Dash(
    __name__,
    title="Charging Demand Model",
    use_pages=True,
    pages_folder="",  # router does discovery
    assets_folder=os.path.join(_here, "assets"),
)
app._favicon = "favicon.svg"  # type: ignore[assignment]

register_pages()

# LIMESS brand palette. Mantine wants 10-entry lists keyed 0..9; the
# brand defines 500-900 (slots 5-9), tints are extrapolated.
_LIMESS_SHADES = [
    "#f2f8ea",
    "#e2efd1",
    "#c7df9f",
    "#abcf6c",
    "#95c347",
    "#88bf49",
    "#74a63a",
    "#6a9735",
    "#54792a",
    "#3f5b20",
]
_SAND_SHADES = [
    "#fbfaf9",
    "#f6f5f4",
    "#edece8",
    "#e4e2dd",
    "#dbd8d1",
    "#d2cfc6",
    "#aba79c",
    "#847f71",
    "#423f38",
    "#161513",
]

# Mantine iterates palette values with .forEach, so each entry must be
# a 10-element list - not a dict, despite the dmc TypedDict.
BRAND_THEME = cast(
    dmc.MantineProvider.Theme,
    {
        "fontFamily": "DM Sans, ui-sans-serif, system-ui, sans-serif",
        "headings": {
            "fontFamily": "DM Sans, ui-sans-serif, system-ui, sans-serif",
            "fontWeight": "600",
            "sizes": {
                "h1": {"fontSize": "32px", "lineHeight": "1.1"},
                "h2": {"fontSize": "24px", "lineHeight": "1.2"},
                "h3": {"fontSize": "20px", "lineHeight": "1.25"},
                "h4": {"fontSize": "16px", "lineHeight": "1.35"},
            },
        },
        "primaryColor": "limess",
        "primaryShade": 6,
        "colors": {
            "limess": _LIMESS_SHADES,
            "gray": _SAND_SHADES,
        },
    },
)


def _nav_links():
    return [
        dmc.NavLink(
            label=page.get("name", page["module"]),
            href=page["relative_path"],
            active="partial",
        )
        for page in dash.page_registry.values()
    ]


app.layout = dmc.MantineProvider(
    dmc.AppShell(
        [
            dmc.AppShellHeader(
                dmc.Group(
                    [
                        dmc.Title(
                            "Prague Charging Dashboard", order=3
                        ),
                        html.Img(
                            src=dash.get_asset_url("logo.svg"),
                            alt="LIMESS",
                            style={"height": "32px"},
                        ),
                    ],
                    justify="space-between",
                    px="md",
                    h="100%",
                ),
            ),
            dmc.AppShellNavbar(
                dmc.Stack(
                    _nav_links(),
                    gap="xs",
                    p="sm",
                ),
            ),
            dmc.AppShellMain(
                dash.page_container,
                h="100%",
            ),
            dmc.AppShellFooter(
                dmc.Group(
                    [
                        dmc.Text(
                            [
                                "built by ",
                                dmc.Anchor(
                                    "LIMESS Lab",
                                    href="https://limess-lab.com/",
                                    target="_blank",
                                    underline="always",
                                ),
                                ", Department of Economics, Management and Humanities, Faculty of Electrical Engineering, Czech Technical University in Prague",
                            ],
                            id="authors-list",
                            size="sm",
                            c="gray",
                        ),
                        dmc.Text(
                            f"v{DASHBOARD_VERSION}",
                            size="sm",
                            c="gray",
                        ),
                    ],
                    justify="space-between",
                    px="md",
                    h="100%",
                ),
            ),
        ],
        header={"height": 60},
        navbar={"width": 220, "breakpoint": "sm"},
        footer={"height": 40},
        style={"height": "100vh"},
    ),
    theme=BRAND_THEME,
)

server = app.server

if __name__ == "__main__":
    app.run(
        debug=settings.ENVIRONMENT == "development",
        host="0.0.0.0",
    )
