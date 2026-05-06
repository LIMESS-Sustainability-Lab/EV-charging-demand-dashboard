import math
from collections import defaultdict
from typing import Any, Optional

import dash_mantine_components as dmc
import pandas as pd

# Unknown prefixes fall through to the raw token.
PREFIX_LABELS = {
    "morph": "Number of buildings by urban morphology",
    "zsj": "Census (ZSJ)",
    "pricemap": "Rent price map",
    "bld": "Buildings",
    "land": "Nearby land uses",
    "poi": "Points of interest",
    "net": "Street network",
}


def Banner(text: str):
    return dmc.Alert(
        text,
        color="gray",
        variant="light",
        mt="md",
    )


def ValueDisplay(
    label: str,
    value: str,
    unit: str = "",
    sublabel: Optional[str] = None,
):
    return dmc.Paper(
        dmc.Stack(
            [
                dmc.Text(label, size="sm", c="gray", ta="center"),
                *(
                    [
                        dmc.Text(
                            sublabel, size="xs", c="gray", ta="center"
                        )
                    ]
                    if sublabel
                    else []
                ),
                dmc.Group(
                    [
                        dmc.Text(value, size="xl", fw="bold"),
                        dmc.Text(unit, size="sm", c="gray"),
                    ],
                    gap="xs",
                    justify="center",
                    align="baseline",
                ),
            ],
            gap="xs",
            align="center",
        ),
        withBorder=False,
        p="sm",
    )


def _format_value(value: Any) -> str:
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


def _split_prefix(key: str) -> tuple[str, str]:
    if "_" in key:
        prefix, _, rest = key.partition("_")
        return prefix, rest
    return "", key


def FeatureGroups(row: dict):
    # Render a flat dict of features as prefix-grouped accordion tables.
    # Keys sharing a prefix_ form a group; the rest fall under "Other".
    groups: dict[str, list[tuple[str, Any]]] = defaultdict(list)
    for key, value in row.items():
        prefix, rest = _split_prefix(key)
        groups[prefix].append((rest or key, value))

    # Known prefixes first (in PREFIX_LABELS order), then alphabetical,
    # then the unprefixed bucket as "Other".
    known = [p for p in PREFIX_LABELS if p in groups]
    unknown = sorted(
        p for p in groups if p and p not in PREFIX_LABELS
    )
    ordered = known + unknown + ([""] if "" in groups else [])

    items: list[Any] = []
    for prefix in ordered:
        entries = groups[prefix]
        label = PREFIX_LABELS.get(prefix) or (
            prefix if prefix else "Other"
        )
        rows = [
            dmc.TableTr(
                [
                    dmc.TableTd(dmc.Text(k, size="sm")),
                    dmc.TableTd(
                        dmc.Text(
                            _format_value(v),
                            size="sm",
                            ff="monospace",
                        ),
                        style={"textAlign": "right"},
                    ),
                ]
            )
            for k, v in entries
        ]
        items.append(
            dmc.AccordionItem(
                [
                    dmc.AccordionControl(
                        dmc.Group(
                            [
                                dmc.Text(label, fw="bold"),
                                dmc.Badge(
                                    f"{len(entries)}",
                                    size="sm",
                                    variant="light",
                                    color="gray",
                                ),
                            ],
                            gap="sm",
                        )
                    ),
                    dmc.AccordionPanel(
                        dmc.Table(
                            [dmc.TableTbody(rows)],
                            striped="odd",
                            withTableBorder=False,
                            highlightOnHover=True,
                        )
                    ),
                ],
                value=prefix or "other",
            )
        )

    # Open small groups by default; leave long lists collapsed.
    # persistence keeps the user's choice across callback re-renders.
    default_open = [
        p or "other" for p in ordered if len(groups[p]) <= 10
    ]
    return dmc.Accordion(
        items,
        multiple=True,
        value=default_open,
        id="spatial-features-accordion",
        persistence=True,
        persistence_type="session",
        persisted_props=["value"],
    )


def feature_row_from_df(df: "pd.DataFrame") -> dict:
    if df.empty:
        return {}
    return df.iloc[0].to_dict()
