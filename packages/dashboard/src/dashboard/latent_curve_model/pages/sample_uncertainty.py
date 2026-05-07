from __future__ import annotations

import math
from functools import lru_cache
from typing import NamedTuple, Optional

import altair as alt
import dash_mantine_components as dmc
import dash_vega_components as dvc
import numpy as np
import pandas as pd
from dash import Input, Output, State, callback, html
from dash_iconify import DashIconify
from dash_pydantic_form import ModelForm
from latentcurvemodel import (
    PredictionRequest,
    Spatial,
    Station,
    Temporal,
)

from dashboard.latent_curve_model.forms import (
    DAYS,
    MONTHS,
    SamplingFormModel,
)
from dashboard.latent_curve_model.predictor import predictor as model
from dashboard.shared.layout.prediction_page import (
    PredictionPageShell,
    Tab,
)
from dashboard.shared.utils import is_in_prague
from dash_spatial_prediction import (
    Banner,
    InteractiveMap,
    PointsLayer,
    PolygonsLayer,
    ValueDisplay,
)

MAP_ID = "su-map"
OUTPUT_ID = "su-output"
TABS_ID = "su-tabs"
FORM_AIO_ID = "su-model"
FORM_ID = "su-form"
SUBMIT_ID = "su-submit"

TAB_PREDICTION = "prediction"
TAB_PREVIEW = "preview"

EARTH_R_M = 6_371_000.0


class Sample(NamedTuple):
    lat: float
    lng: float


def _seed_from_coord(
    lat: float, lng: float, n: int, radius_m: float
) -> int:
    # Round to ~1 m precision so float jitter doesn't change the seed
    # when the same point is clicked twice.
    key = (round(lat, 6), round(lng, 6), int(n), int(radius_m))
    return hash(key) & 0xFFFFFFFF


def _poisson_disk(
    center_lat: float,
    center_lng: float,
    radius_m: float,
    n: int,
    seed: Optional[int] = None,
) -> list[Sample]:
    if seed is None:
        seed = _seed_from_coord(center_lat, center_lng, n, radius_m)
    rng = np.random.default_rng(seed)

    # 0.7 packing constant chosen to converge quickly even at n=150
    # while still looking spread out.
    min_dist_m = 0.7 * radius_m / math.sqrt(max(n, 1))
    min_dist_sq = min_dist_m * min_dist_m

    cos_lat = math.cos(math.radians(center_lat))

    samples: list[Sample] = []
    accepted_xy: list[tuple[float, float]] = []

    max_attempts = 30 * n
    attempts = 0
    while len(samples) < n and attempts < max_attempts:
        attempts += 1
        u = rng.uniform()
        v = rng.uniform()
        r = radius_m * math.sqrt(u)
        a = 2 * math.pi * v
        x = r * math.cos(a)
        y = r * math.sin(a)
        ok = True
        for px, py in accepted_xy:
            if (x - px) ** 2 + (y - py) ** 2 < min_dist_sq:
                ok = False
                break
        if not ok:
            continue
        accepted_xy.append((x, y))
        d_lat = y / EARTH_R_M
        d_lng = x / (EARTH_R_M * cos_lat)
        samples.append(
            Sample(
                lat=center_lat + math.degrees(d_lat),
                lng=center_lng + math.degrees(d_lng),
            )
        )
    return samples


_stratified_disk = _poisson_disk


def _disk_polygon(
    center_lat: float,
    center_lng: float,
    radius_m: float,
    n_vertices: int = 64,
) -> dict:
    cos_lat = math.cos(math.radians(center_lat))
    coords = []
    for i in range(n_vertices + 1):
        a = 2 * math.pi * i / n_vertices
        d_lat = (radius_m * math.sin(a)) / EARTH_R_M
        d_lng = (radius_m * math.cos(a)) / (EARTH_R_M * cos_lat)
        coords.append(
            [
                center_lng + math.degrees(d_lng),
                center_lat + math.degrees(d_lat),
            ]
        )
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [coords],
                },
            }
        ],
    }


def _form_fingerprint(parsed: SamplingFormModel) -> tuple:
    # Hashable summary of every input that affects the prediction.
    return (
        round(parsed.loc.location.lat, 6),
        round(parsed.loc.location.lng, 6),
        int(parsed.sampling.radius_m),
        int(parsed.sampling.n_samples),
        parsed.charger.charging_type,
        int(parsed.charger.n_ac_siblings),
        int(parsed.charger.n_dc_siblings),
        int(parsed.time.year),
        parsed.time.month,
        parsed.time.weekday,
    )


@lru_cache(maxsize=64)
def _predict_cached(fp: tuple) -> tuple[np.ndarray, np.ndarray]:
    (
        lat,
        lng,
        radius_m,
        n_samples,
        charging_type,
        n_ac,
        n_dc,
        year,
        month_name,
        weekday_name,
    ) = fp
    samples = _stratified_disk(lat, lng, radius_m, n_samples)
    requests = [
        PredictionRequest(
            spatial=Spatial(lon=s.lng, lat=s.lat),
            station=Station(
                charging_type=charging_type,
                n_ac_siblings=n_ac,
                n_dc_siblings=n_dc,
            ),
            temporal=Temporal(
                year=year,
                month=MONTHS.index(month_name) + 1,
                weekday=DAYS.index(weekday_name) + 1,
            ),
        )
        for s in samples
    ]
    profiles, total_powers, _ = model.predict_components(requests)
    profiles = np.asarray(profiles)
    if profiles.ndim == 3:
        # predictor sometimes returns (1, N, 24)
        profiles = profiles.reshape(-1, profiles.shape[-1])
    total_powers = np.asarray(total_powers).reshape(-1)
    curves = profiles * total_powers[:, None]
    return curves, curves.sum(axis=1)


def _predict_many(parsed: SamplingFormModel):
    return _predict_cached(_form_fingerprint(parsed))


def _hourly_uncertainty_chart(curves: np.ndarray) -> html.Div:
    n_hours = curves.shape[1]
    mean = curves.mean(axis=0)
    p5 = np.percentile(curves, 5, axis=0)
    p95 = np.percentile(curves, 95, axis=0)
    df = pd.DataFrame(
        {
            "hour": np.arange(n_hours),
            "mean": mean,
            "lo": p5,
            "hi": p95,
        }
    )

    base = alt.Chart(df).encode(
        x=alt.X(
            "hour:Q",
            title="hour",
            scale=alt.Scale(domain=[0, n_hours - 1]),
            axis=alt.Axis(values=list(range(n_hours))),
        ),
    )
    band = base.mark_area(color="#27ae60", opacity=0.25).encode(
        y=alt.Y("lo:Q", title="kW"),
        y2=alt.Y2("hi:Q"),
    )
    line = base.mark_line(
        color="#27ae60", strokeWidth=2.5, interpolate="linear"
    ).encode(
        y=alt.Y("mean:Q"),
        tooltip=[
            alt.Tooltip("hour:Q", title="hour"),
            alt.Tooltip("mean:Q", title="mean kW", format=".2f"),
            alt.Tooltip("lo:Q", title="p5", format=".2f"),
            alt.Tooltip("hi:Q", title="p95", format=".2f"),
        ],
    )
    points = base.mark_point(
        color="#27ae60", filled=True, size=40
    ).encode(y=alt.Y("mean:Q"))

    chart = (band + line + points).properties(
        height=320,
        width="container",
        title="Average hourly power (mean ± 5–95%)",
    )
    spec = chart.to_dict()
    spec["autosize"] = {
        "type": "fit",
        "contains": "padding",
        "resize": True,
    }
    return html.Div(
        dvc.Vega(
            spec=spec,
            opt={"renderer": "svg", "actions": False},
            style={"width": "100%"},
        ),
        style={"width": "100%"},
    )


def _total_distribution_chart(totals: np.ndarray) -> html.Div:
    """Histogram + KDE overlay of the daily total kWh across samples."""
    if totals.size == 0:
        return Banner("No samples available.")

    df = pd.DataFrame({"kwh": totals})
    mean = float(totals.mean())
    p5 = float(np.percentile(totals, 5))
    p95 = float(np.percentile(totals, 95))

    # Histogram: count of samples per kWh bin.
    n_bins = max(8, int(np.sqrt(len(totals)) * 2))
    hist = (
        alt.Chart(df)
        .mark_bar(color="#27ae60", opacity=0.5)
        .encode(
            x=alt.X(
                "kwh:Q",
                bin=alt.Bin(maxbins=n_bins),
                title="daily total (kWh)",
            ),
            y=alt.Y("count()", title="# samples"),
            tooltip=[
                alt.Tooltip(
                    "kwh:Q",
                    bin=alt.Bin(maxbins=n_bins),
                    title="kWh range",
                ),
                alt.Tooltip("count()", title="samples"),
            ],
        )
    )

    layers: list[alt.Chart] = [hist]
    if totals.std() > 1e-6 and len(totals) >= 3:
        try:
            from scipy.stats import gaussian_kde

            xs = np.linspace(
                float(totals.min()), float(totals.max()), 200
            )
            kde = gaussian_kde(totals)
            density = kde(xs)
            # KDE integrates to 1; scale to histogram's count axis.
            bin_width = (totals.max() - totals.min()) / max(n_bins, 1)
            scaled = density * len(totals) * bin_width
            kde_df = pd.DataFrame({"kwh": xs, "y": scaled})
            kde_line = (
                alt.Chart(kde_df)
                .mark_line(
                    color="#1f5f3a",
                    strokeWidth=2.0,
                    interpolate="linear",
                )
                .encode(
                    x=alt.X("kwh:Q"),
                    y=alt.Y("y:Q"),
                )
            )
            layers.append(kde_line)
        except Exception:
            pass

    rules_df = pd.DataFrame(
        {
            "kwh": [mean, p5, p95],
            "label": ["mean", "p5", "p95"],
        }
    )
    rules = (
        alt.Chart(rules_df)
        .mark_rule(
            strokeDash=[4, 4], color="#444444", strokeWidth=1.2
        )
        .encode(
            x="kwh:Q",
            tooltip=[
                alt.Tooltip("label:N", title=""),
                alt.Tooltip("kwh:Q", title="kWh", format=".2f"),
            ],
        )
    )
    layers.append(rules)

    chart = alt.layer(*layers).properties(
        height=200,
        width="container",
        title="Daily total distribution",
    )
    spec = chart.to_dict()
    spec["autosize"] = {
        "type": "fit",
        "contains": "padding",
        "resize": True,
    }
    return html.Div(
        dvc.Vega(
            spec=spec,
            opt={"renderer": "svg", "actions": False},
            style={"width": "100%"},
        ),
        style={"width": "100%"},
    )


def _total_summary(totals: np.ndarray):
    mean = float(totals.mean())
    p5 = float(np.percentile(totals, 5))
    p95 = float(np.percentile(totals, 95))
    return ValueDisplay(
        label="Average daily power consumption",
        value=f"{mean:.2f}",
        unit="kWh",
        sublabel=f"p5 {p5:.2f} · p95 {p95:.2f}",
    )


def _card(icon: str, title: str, body):
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


def _initial_layers(parsed: SamplingFormModel) -> list[dict]:
    samples = _stratified_disk(
        parsed.loc.location.lat,
        parsed.loc.location.lng,
        parsed.sampling.radius_m,
        parsed.sampling.n_samples,
    )
    disk = _disk_polygon(
        parsed.loc.location.lat,
        parsed.loc.location.lng,
        parsed.sampling.radius_m,
    )
    sample_features = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"i": i},
                "geometry": {
                    "type": "Point",
                    "coordinates": [s.lng, s.lat],
                },
            }
            for i, s in enumerate(samples)
        ],
    }
    centre_feature = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {},
                "geometry": {
                    "type": "Point",
                    "coordinates": [
                        parsed.loc.location.lng,
                        parsed.loc.location.lat,
                    ],
                },
            }
        ],
    }
    return [
        PolygonsLayer(
            id="su-disk",
            data=disk,
            color="#1f77b4",
            opacity=0.15,
        ).to_dict(),
        PointsLayer(
            id="su-samples",
            data=sample_features,
            color="#1f77b4",
            radius=4,
            stroke_width=0,
            opacity=0.9,
        ).to_dict(),
        PointsLayer(
            id="su-centre",
            data=centre_feature,
            color="#d62728",
            radius=8,
            stroke_width=2,
            stroke_color="#ffffff",
        ).to_dict(),
    ]


_DEFAULT_FORM = SamplingFormModel()


layout = PredictionPageShell(
    sidebar_title="Location uncertainty",
    sidebar_body=ModelForm(
        SamplingFormModel, aio_id=FORM_AIO_ID, form_id=FORM_ID
    ),
    sidebar_footer=dmc.Button(
        "Predict",
        id=SUBMIT_ID,
        fullWidth=True,
    ),
    tabs=[
        Tab("Prediction", TAB_PREDICTION, "tabler:chart-line"),
        Tab("Sample preview", TAB_PREVIEW, "tabler:map"),
    ],
    tabs_id=TABS_ID,
    output_id=OUTPUT_ID,
)


def _parse(form_data: dict) -> Optional[SamplingFormModel]:
    if not form_data:
        return None
    try:
        return SamplingFormModel(**form_data)
    except Exception:
        return None


def _preview_view(form_data: dict):
    parsed = _parse(form_data) or _DEFAULT_FORM
    return dmc.Box(
        InteractiveMap(
            id=MAP_ID,
            layers=_initial_layers(parsed),
            center=[
                parsed.loc.location.lng,
                parsed.loc.location.lat,
            ],
            zoom=15,
            height="100%",
        ),
        style={
            "height": "100%",
            "padding": "var(--mantine-spacing-md)",
        },
    )


def _prediction_view(form_data: dict, clicks: Optional[int]):
    if not clicks:
        return Banner("Adjust the form, then click Run prediction.")
    parsed = _parse(form_data)
    if parsed is None:
        return Banner("fill in the form to see predictions")
    if not is_in_prague(
        parsed.loc.location.lat, parsed.loc.location.lng
    ):
        return Banner("Selected location is outside Prague.")
    try:
        curves, totals = _predict_many(parsed)
    except Exception as e:
        return Banner(f"prediction error\n{e}")

    return dmc.ScrollArea(
        dmc.Container(
            dmc.Stack(
                [
                    _card(
                        "tabler:bolt",
                        "Hourly power across samples",
                        _hourly_uncertainty_chart(curves),
                    ),
                    _card(
                        "tabler:sum",
                        "Daily total",
                        dmc.Stack(
                            [
                                _total_summary(totals),
                                _total_distribution_chart(totals),
                            ],
                            gap="sm",
                        ),
                    ),
                ],
                gap="md",
            ),
            size="xl",
            p="md",
        ),
        h="100%",
        type="auto",
    )


@callback(
    Output(OUTPUT_ID, "children"),
    Input(SUBMIT_ID, "n_clicks"),
    Input(TABS_ID, "value"),
    State(ModelForm.ids.main(FORM_AIO_ID, FORM_ID), "data"),
)
def _render(clicks: Optional[int], tab: str, form_data: dict):
    if tab == TAB_PREVIEW:
        return _preview_view(form_data)
    return _prediction_view(form_data, clicks)
