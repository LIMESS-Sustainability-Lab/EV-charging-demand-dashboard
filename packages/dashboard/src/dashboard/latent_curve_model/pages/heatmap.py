from __future__ import annotations

import base64
from functools import lru_cache

import altair as alt
import dash_mantine_components as dmc
import dash_vega_components as dvc
from dash import Input, Output, callback, html
from dash_pydantic_form import ModelForm
from latentcurvemodel import (
    Station,
    Temporal,
    latent_profile_curves_frame,
    plot_latent_profile_heatmaps,
    plot_total_kwh_heatmap,
)

from dashboard.latent_curve_model.forms import (
    DAYS,
    MONTHS,
    HeatmapFormModel,
)
from dashboard.latent_curve_model.charts import PROFILE_COLORS
from dashboard.latent_curve_model.predictor import heatmap_predictor
from dashboard.shared.components.card import Card
from dashboard.shared.layout.prediction_page import (
    PredictionPageShell,
    Tab,
)
from dash_spatial_prediction import Banner, ValueDisplay

TAB_TOTAL = "total"
TAB_LATENT = "latent"

OUTPUT_ID = "heatmap-output"
TABS_ID = "heatmap-tabs"
FORM_AIO_ID = "heatmap-model"
FORM_ID = "heatmap-form"


def _image_src(png: bytes) -> str:
    encoded = base64.b64encode(png).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _profile_sort_key(col: str) -> int:
    return int(col.removeprefix("profile_").removesuffix("_prob"))


def _title(parsed: HeatmapFormModel) -> str:
    return (
        f"{parsed.charger.charging_type}, "
        f"{parsed.charger.n_ac_siblings} AC siblings, "
        f"{parsed.charger.n_dc_siblings} DC siblings - "
        f"{parsed.time.weekday}s of {parsed.time.month} {parsed.time.year}"
    )


@lru_cache(maxsize=16)
def _predict_cached(
    charging_type: str,
    n_ac_siblings: int,
    n_dc_siblings: int,
    year: int,
    month: int,
    weekday: int,
    target_step_m: int,
):
    return heatmap_predictor.predict_latent_profile_contributions(
        Station(
            charging_type=charging_type,
            n_ac_siblings=n_ac_siblings,
            n_dc_siblings=n_dc_siblings,
        ),
        Temporal(year=year, month=month, weekday=weekday),
        target_step_m=target_step_m,
    )


def _predict(parsed: HeatmapFormModel):
    return _predict_cached(
        parsed.charger.charging_type,
        parsed.charger.n_ac_siblings,
        parsed.charger.n_dc_siblings,
        int(parsed.time.year),
        MONTHS.index(parsed.time.month) + 1,
        DAYS.index(parsed.time.weekday) + 1,
        int(parsed.heatmap.target_step_m),
    )


def _summary_cards(gdf):
    values = gdf["total_kwh"]
    return dmc.SimpleGrid(
        [
            Card(
                "tabler:grid-dots",
                "Cells",
                ValueDisplay(
                    "Displayed grid cells",
                    f"{len(gdf):,}",
                    "",
                ),
            ),
            Card(
                "tabler:chart-arrows-vertical",
                "Mean",
                ValueDisplay(
                    "Average daily total",
                    f"{float(values.mean()):.2f}",
                    "kWh",
                ),
            ),
            Card(
                "tabler:arrow-down",
                "Minimum",
                ValueDisplay(
                    "Lowest daily total",
                    f"{float(values.min()):.2f}",
                    "kWh",
                ),
            ),
            Card(
                "tabler:arrow-up",
                "Maximum",
                ValueDisplay(
                    "Highest daily total",
                    f"{float(values.max()):.2f}",
                    "kWh",
                ),
            ),
        ],
        cols=4,
        spacing="md",
    )


def _image_card(title: str, png: bytes):
    return Card(
        "tabler:photo",
        title,
        html.Img(
            src=_image_src(png),
            style={
                "display": "block",
                "width": "100%",
                "height": "auto",
            },
        ),
    )


@lru_cache(maxsize=1)
def _latent_profile_curve_specs():
    df = latent_profile_curves_frame(heatmap_predictor.predictor)
    profiles = df["profile"].unique().tolist()
    hours = sorted(df["hour"].unique().tolist())
    y_max = float(df["value"].max() * 1.05)

    specs = []
    for idx, profile in enumerate(profiles):
        profile_df = df[df["profile"] == profile]
        color = PROFILE_COLORS[idx % len(PROFILE_COLORS)]
        is_left_column = idx % 2 == 0
        is_bottom_row = idx >= len(profiles) - 2
        base = alt.Chart(profile_df).encode(
            x=alt.X(
                "hour:Q",
                title="hour" if is_bottom_row else None,
                scale=alt.Scale(domain=[min(hours), max(hours)]),
                axis=alt.Axis(values=hours),
            ),
            y=alt.Y(
                "value:Q",
                title="normalized power" if is_left_column else None,
                scale=alt.Scale(domain=[0, y_max]),
            ),
            tooltip=[
                alt.Tooltip("profile:N", title="profile"),
                alt.Tooltip("hour:Q", title="hour"),
                alt.Tooltip("value:Q", title="normalized power", format=".3f"),
            ],
        )
        area = base.mark_area(
            color=color,
            opacity=0.14,
            interpolate="linear",
        )
        line = base.mark_line(
            color=color,
            strokeWidth=2.2,
            interpolate="linear",
        )
        chart = (area + line).properties(
            width="container",
            height=150,
            title=profile,
        )
        spec = chart.to_dict()
        spec["autosize"] = {
            "type": "fit",
            "contains": "padding",
            "resize": True,
        }
        spec["config"] = {
            **spec.get("config", {}),
            "view": {"continuousWidth": 420, "stroke": "transparent"},
            "title": {
                "anchor": "start",
                "fontSize": 12,
                "fontWeight": "bold",
            },
        }
        specs.append(spec)
    return specs


def _latent_profile_curve_chart(spec: dict):
    return html.Div(
        dvc.Vega(
            spec=spec,
            opt={"renderer": "svg", "actions": False},
            style={
                "display": "block",
                "width": "100%",
                "overflow": "hidden",
            },
        ),
        style={
            "width": "100%",
            "minWidth": 0,
            "overflow": "hidden",
        },
    )


def _latent_profile_curves_card():
    return Card(
        "tabler:activity",
        "Latent profile shapes",
        dmc.SimpleGrid(
            [
                _latent_profile_curve_chart(spec)
                for spec in _latent_profile_curve_specs()
            ],
            cols=2,
            spacing="md",
        ),
    )


def _total_view(parsed: HeatmapFormModel, gdf):
    title = _title(parsed)
    scale_label = "log scale" if parsed.heatmap.log_total_kwh else "linear scale"
    png = plot_total_kwh_heatmap(
        gdf,
        title=f"Predicted daily charging demand ({scale_label}) - {title}",
        cell_size_m=float(parsed.heatmap.target_step_m),
        log_scale=parsed.heatmap.log_total_kwh,
    )
    return _image_card("Daily total heatmap", png)


def _latent_view(parsed: HeatmapFormModel, gdf):
    profile_cols = sorted(
        [
            c
            for c in gdf.columns
            if c.startswith("profile_") and c.endswith("_prob")
        ],
        key=_profile_sort_key,
    )
    maps_png = plot_latent_profile_heatmaps(
        gdf,
        profile_cols=profile_cols,
        title=f"Latent profile mixture - {_title(parsed)}",
        value_label="mixture weight",
        cell_size_m=float(parsed.heatmap.target_step_m),
    )
    return dmc.Stack(
        [
            _image_card("Latent profile contribution maps", maps_png),
            _latent_profile_curves_card(),
        ],
        gap="md",
    )


@callback(
    Output(OUTPUT_ID, "children"),
    Input(ModelForm.ids.main(FORM_AIO_ID, FORM_ID), "data"),
    Input(TABS_ID, "value"),
)
def _render(form_data: dict, tab: str):
    if not form_data:
        return Banner("fill in the form to generate the heatmap")
    try:
        parsed = HeatmapFormModel(**form_data)
        gdf = _predict(parsed)
    except Exception as e:
        return Banner(f"heatmap error\n{e}")

    if len(gdf) == 0:
        return Banner("No grid cells available for this heatmap.")

    body = (
        _latent_view(parsed, gdf)
        if tab == TAB_LATENT
        else _total_view(parsed, gdf)
    )
    return dmc.ScrollArea(
        dmc.Container(
            dmc.Stack(
                [
                    # _summary_cards(gdf),
                    body,
                ],
                gap="md",
            ),
            size="xl",
            p="md",
        ),
        h="100%",
        type="auto",
    )


layout = PredictionPageShell(
    sidebar_title="Demand heatmap",
    sidebar_body=ModelForm(
        HeatmapFormModel, aio_id=FORM_AIO_ID, form_id=FORM_ID
    ),
    tabs=[
        Tab("Daily total", TAB_TOTAL, "tabler:map-2"),
        Tab("Latent profiles", TAB_LATENT, "tabler:layers-intersect"),
    ],
    tabs_id=TABS_ID,
    output_id=OUTPUT_ID,
)
