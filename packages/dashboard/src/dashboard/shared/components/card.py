import dash_mantine_components as dmc
from dash_iconify import DashIconify


def Card(icon: str, title: str, body):
    return dmc.Paper(
        dmc.Stack(
            [
                dmc.Group(
                    [
                        DashIconify(icon=icon, width=18),
                        dmc.Text(title, fw="bold"),
                    ],
                    gap="xs",
                ),
                body,
            ],
            gap="sm",
        ),
        withBorder=True,
        radius="md",
        p="md",
    )
