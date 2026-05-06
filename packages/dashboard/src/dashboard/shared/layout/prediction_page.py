from dataclasses import dataclass
from typing import Optional

import dash_mantine_components as dmc
from dash_iconify import DashIconify


@dataclass
class Tab:
    label: str
    value: str
    icon: str


def PredictionPageShell(
    *,
    sidebar_title: str,
    sidebar_body,
    tabs: list[Tab],
    tabs_id: str,
    output_id: str,
    initial_tab: Optional[str] = None,
    extra_above_output=None,
):
    selected = (
        initial_tab if initial_tab is not None else tabs[0].value
    )

    main_children: list = [
        dmc.Tabs(
            [
                dmc.TabsList(
                    [
                        dmc.TabsTab(
                            t.label,
                            value=t.value,
                            leftSection=DashIconify(
                                icon=t.icon, width=16
                            ),
                        )
                        for t in tabs
                    ],
                ),
            ],
            id=tabs_id,
            value=selected,
            px="sm",
            pt="sm",
        ),
        dmc.Divider(),
    ]
    if extra_above_output is not None:
        main_children.append(extra_above_output)
    main_children.append(
        dmc.Box(id=output_id, style={"flex": 1, "minHeight": 0})
    )

    return dmc.Box(
        dmc.Group(
            [
                dmc.Stack(
                    [
                        dmc.Title(sidebar_title, order=4, p="sm"),
                        dmc.Divider(),
                        dmc.ScrollArea(
                            dmc.Box(sidebar_body, p="md"),
                            style={"flex": 1, "minHeight": 0},
                            type="auto",
                        ),
                    ],
                    gap=0,
                    h="100%",
                    style={
                        "flex": "0 0 33.3333%",
                        "backgroundColor": "var(--mantine-color-gray-1)",
                        "borderRight": "1px solid var(--mantine-color-gray-3)",
                        "boxShadow": "2px 0 6px rgba(0, 0, 0, 0.04)",
                    },
                ),
                dmc.Stack(
                    main_children,
                    gap=0,
                    h="100%",
                    style={
                        "flex": "1 1 auto",
                        "minWidth": 0,
                        "minHeight": 0,
                    },
                ),
            ],
            gap=0,
            align="stretch",
            wrap="nowrap",
            h="100%",
            style={"maxWidth": "1800px", "margin": "0 auto"},
        ),
        style={"height": "calc(100dvh - 100px)"},
    )
