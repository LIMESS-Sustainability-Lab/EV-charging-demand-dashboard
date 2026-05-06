from __future__ import annotations

import math
from collections import defaultdict
from typing import Any, Literal

import dash_mantine_components as dmc
import geopandas as gpd
from dash import Input, Output, callback
from dash_pydantic_form import ModelForm
from latentcurvemodel import extract_charger_spatial_features

from dashboard.latent_curve_model.charts import (
    power_curve_chart,
    profile_mixture_chart,
)
from dashboard.latent_curve_model.forms import (
    CompareFormModel,
    FormModel,
    to_form_model,
)
from dashboard.latent_curve_model.prediction import (
    build_request,
    compute_prediction,
)
from dashboard.latent_curve_model.predictor import predictor as model
from dashboard.shared.components.card import Card
from dashboard.shared.layout.prediction_page import (
    PredictionPageShell,
    Tab,
)
from dashboard.shared.utils import (
    format_value,
    is_in_prague,
    split_prefix,
)
from dash_spatial_prediction import Banner, ValueDisplay
from dash_spatial_prediction.ui import PREFIX_LABELS

TAB_PREDICTIONS = "predictions"
TAB_SPATIAL = "spatial"

DIFF_TOGGLE_ID = "compare-diff-toggle"
OUTPUT_ID = "compare-output"
TABS_ID = "compare-tabs"
FORM_AIO_ID = "compare-model"
FORM_ID = "compare-form"




def _predict(side: FormModel):
    return compute_prediction(
        model=model,
        request=build_request(side),
        month_name=side.time.month,
        weekday_name=side.time.weekday,
    )


def _prediction_column(label: str, side: FormModel) -> dmc.Stack:
    header = dmc.Badge(label, size="lg", variant="filled")
    try:
        result = _predict(side)
    except Exception as e:
        return dmc.Stack(
            [header, Banner(f"prediction error\n{e}")],
            gap="sm",
        )
    return dmc.Stack(
        [
            header,
            Card(
                "tabler:bolt",
                "Average hourly power",
                power_curve_chart(result),
            ),
            Card(
                "tabler:sum",
                "Daily total",
                ValueDisplay(
                    "Average daily power consumption",
                    f"{result.total_kwh:.2f}",
                    "kWh",
                ),
            ),
            Card(
                "tabler:layers-intersect",
                "Latent profile mixture",
                profile_mixture_chart(result),
            ),
        ],
        gap="md",
    )


def _predictions_view(parsed: CompareFormModel):
    side_a = to_form_model(parsed, "a")
    side_b = to_form_model(parsed, "b")
    return dmc.ScrollArea(
        dmc.Container(
            dmc.Grid(
                [
                    dmc.GridCol(
                        _prediction_column("A", side_a), span=6
                    ),
                    dmc.GridCol(
                        _prediction_column("B", side_b), span=6
                    ),
                ],
                gutter="md",
            ),
            size="xl",
            p="md",
        ),
        h="100%",
        type="auto",
    )




def _features_at(side: FormModel) -> dict:
    df = extract_charger_spatial_features(
        chargers=gpd.GeoDataFrame(
            {},
            geometry=gpd.points_from_xy(
                x=[side.loc.location.lng],
                y=[side.loc.location.lat],
            ),
        )
    )
    if df.empty:
        return {}
    return df.iloc[0].to_dict()


def _values_equal(a: Any, b: Any) -> bool:
    # NaN == NaN; floats compared with 1e-9 tolerance.
    if a is None and b is None:
        return True
    a_nan = isinstance(a, float) and math.isnan(a)
    b_nan = isinstance(b, float) and math.isnan(b)
    if a_nan and b_nan:
        return True
    if a_nan or b_nan:
        return False
    if isinstance(a, float) and isinstance(b, float):
        return abs(a - b) < 1e-9
    return a == b


def _format_diff(
    a: Any, b: Any
) -> tuple[str, Literal["green", "red", "orange"] | None]:
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        a_nan = isinstance(a, float) and math.isnan(a)
        b_nan = isinstance(b, float) and math.isnan(b)
        if a_nan or b_nan:
            return ("-", None)
        diff = b - a
        if diff == 0:
            return ("0", None)
        sign = "+" if diff > 0 else "−"
        magnitude = abs(diff)
        return (
            f"{sign}{format_value(magnitude)}",
            "green" if diff > 0 else "red",
        )
    if _values_equal(a, b):
        return ("=", None)
    return ("≠", "orange")


def _diff_table(
    rows: list[tuple[str, Any, Any]],
) -> dmc.Table:
    body_rows = []
    for name, va, vb in rows:
        diff_text, diff_color = _format_diff(va, vb)
        # Mantine's Text rejects a None `c` prop, so only set it when a color exists.
        text_kwargs: dict[str, Any] = {
            "size": "sm",
            "ff": "monospace",
        }
        if diff_color is not None:
            text_kwargs["c"] = diff_color
            text_kwargs["fw"] = "bold"
        diff_cell = dmc.Text(diff_text, **text_kwargs)
        body_rows.append(
            dmc.TableTr(
                [
                    dmc.TableTd(dmc.Text(name, size="sm")),
                    dmc.TableTd(
                        dmc.Text(
                            format_value(va),
                            size="sm",
                            ff="monospace",
                        ),
                        style={"textAlign": "right"},
                    ),
                    dmc.TableTd(
                        dmc.Text(
                            format_value(vb),
                            size="sm",
                            ff="monospace",
                        ),
                        style={"textAlign": "right"},
                    ),
                    dmc.TableTd(
                        diff_cell, style={"textAlign": "right"}
                    ),
                ]
            )
        )
    head = dmc.TableThead(
        dmc.TableTr(
            [
                dmc.TableTh("Feature"),
                dmc.TableTh("A", style={"textAlign": "right"}),
                dmc.TableTh("B", style={"textAlign": "right"}),
                dmc.TableTh(
                    "Δ (B − A)", style={"textAlign": "right"}
                ),
            ]
        )
    )
    return dmc.Table(
        [head, dmc.TableTbody(body_rows)],
        striped="odd",
        withTableBorder=False,
        highlightOnHover=True,
    )


def _spatial_diff_view(parsed: CompareFormModel, only_diff: bool):
    feats_a = _features_at(to_form_model(parsed, "a"))
    feats_b = _features_at(to_form_model(parsed, "b"))
    keys = sorted(set(feats_a) | set(feats_b))

    groups: dict[str, list[tuple[str, Any, Any]]] = defaultdict(list)
    diff_count = 0
    total_count = 0
    for key in keys:
        va = feats_a.get(key)
        vb = feats_b.get(key)
        equal = _values_equal(va, vb)
        total_count += 1
        if not equal:
            diff_count += 1
        if only_diff and equal:
            continue
        prefix, rest = split_prefix(key)
        groups[prefix].append((rest or key, va, vb))

    if not groups:
        return dmc.Box(
            Banner(
                "No differing features."
                if only_diff
                else "No spatial features."
            ),
            p="md",
        )

    known = [p for p in PREFIX_LABELS if p in groups]
    unknown = sorted(
        p for p in groups if p and p not in PREFIX_LABELS
    )
    ordered = known + unknown + ([""] if "" in groups else [])

    items = []
    for prefix in ordered:
        entries = groups[prefix]
        label = PREFIX_LABELS.get(prefix) or (
            prefix if prefix else "Other"
        )
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
                    dmc.AccordionPanel(_diff_table(entries)),
                ],
                value=prefix or "other",
            )
        )

    default_open = [
        p or "other" for p in ordered if len(groups[p]) <= 10
    ]

    summary = dmc.Group(
        [
            dmc.Text(
                f"{diff_count} of {total_count} features differ",
                size="sm",
                c="gray",
            ),
        ],
        justify="flex-end",
    )

    return dmc.ScrollArea(
        dmc.Container(
            dmc.Stack(
                [
                    summary,
                    dmc.Accordion(
                        items,
                        multiple=True,
                        value=default_open,
                        id="compare-spatial-accordion",
                        persistence=True,
                        persistence_type="session",
                        persisted_props=["value"],
                    ),
                ],
                gap="sm",
            ),
            size="xl",
            p="md",
        ),
        h="100%",
        type="auto",
    )




layout = PredictionPageShell(
    sidebar_title="Compare locations",
    sidebar_body=ModelForm(
        CompareFormModel, aio_id=FORM_AIO_ID, form_id=FORM_ID
    ),
    tabs=[
        Tab("Predictions", TAB_PREDICTIONS, "tabler:chart-line"),
        Tab("Spatial features diff", TAB_SPATIAL, "tabler:columns-3"),
    ],
    tabs_id=TABS_ID,
    output_id=OUTPUT_ID,
    extra_above_output=dmc.Group(
        [
            dmc.Switch(
                id=DIFF_TOGGLE_ID,
                checked=True,
                label="Show only rows where A ≠ B",
                size="sm",
            ),
        ],
        id="compare-diff-toggle-row",
        px="md",
        py="xs",
    ),
)


@callback(
    Output("compare-diff-toggle-row", "style"),
    Input(TABS_ID, "value"),
)
def _toggle_diff_visibility(tab: str):
    if tab == TAB_SPATIAL:
        return {"padding": "0.25rem 1rem"}
    return {"display": "none"}


@callback(
    Output(OUTPUT_ID, "children"),
    Input(ModelForm.ids.main(FORM_AIO_ID, FORM_ID), "data"),
    Input(TABS_ID, "value"),
    Input(DIFF_TOGGLE_ID, "checked"),
)
def _render(form_data: dict, tab: str, only_diff: bool):
    if not form_data:
        return Banner("fill in both forms to see comparisons")
    try:
        parsed = CompareFormModel(**form_data)
    except Exception as e:
        return Banner(f"error\n{e}")

    outside = [
        side
        for side, loc in (
            ("A", parsed.location_a.location),
            ("B", parsed.location_b.location),
        )
        if not is_in_prague(loc.lat, loc.lng)
    ]
    if outside:
        return Banner(
            f"Location {' and '.join(outside)} is outside Prague."
        )

    if tab == TAB_SPATIAL:
        return _spatial_diff_view(parsed, only_diff=bool(only_diff))
    return _predictions_view(parsed)
