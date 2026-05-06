import altair as alt
import pandas as pd
from dash import html
import dash_vega_components as dvc

from .prediction import PredictionResult

MAIN_CHART_COLOR = "#27ae60"
MAXIMUM_COLOR = "#d68910"
PROFILE_COLORS = [
    "#8e44ad",
    "#c0392b",
    "#2980b9",
    "#d35400",
    "#e74c3c",
    "#2c3e50",
    "#f39c12",
]

# Fixed caps so the y-axis doesn't rescale as inputs change. Tuned to
# envelop realistic worst-case predictions.
POWER_AXIS_MAX = 10.0
FRACTION_AXIS_MAX = 0.12


def _vega(chart: alt.Chart, identifier: str = "None") -> html.Div:
    spec = chart.to_dict()
    # autosize.fit + contains:padding keeps axis labels inside the
    # container width instead of letting them overflow.
    spec["autosize"] = {
        "type": "fit",
        "contains": "padding",
        "resize": True,
    }
    return html.Div(
        dvc.Vega(
            id=identifier,
            opt={"renderer": "svg", "actions": False},
            spec=spec,
            style={"width": "100%", "overflow": "hidden"},
        ),
        style={"width": "100%", "minWidth": 0, "overflow": "hidden"},
    )


def power_curve_chart(result: PredictionResult) -> html.Div:
    # Bars sum to the line: profile i's contribution at hour h is
    # `probs[i] * curve[h]`, so summing over profiles recovers `curve[h]`.
    n_hours = len(result.curve)
    k = len(result.probs)
    profile_names = [f"profile-{i + 1}" for i in range(k)]

    breakdown_rows = [
        {
            "hour": h,
            "profile": profile_names[i],
            "kw": float(result.probs[i] * result.curve[h]),
        }
        for h in range(n_hours)
        for i in range(k)
    ]
    breakdown_df = pd.DataFrame(breakdown_rows)

    total_df = pd.DataFrame(
        {"hour": range(n_hours), "kw": result.curve}
    )

    x_shared = alt.X(
        "hour:Q",
        title="hour",
        scale=alt.Scale(domain=[0, n_hours - 1]),
        axis=alt.Axis(values=list(range(n_hours))),
    )
    y_shared = alt.Y(
        "kw:Q",
        title="kW",
        scale=alt.Scale(domain=[0, POWER_AXIS_MAX]),
    )

    bars = (
        alt.Chart(breakdown_df)
        .mark_bar(
            size=15,
            opacity=0.45,
            stroke=None,
            strokeWidth=0,
        )
        .encode(
            x=x_shared,
            y=alt.Y(
                "kw:Q",
                title="kW",
                stack="zero",
                scale=alt.Scale(domain=[0, POWER_AXIS_MAX]),
            ),
            color=alt.Color(
                "profile:N",
                scale=alt.Scale(
                    domain=profile_names, range=PROFILE_COLORS[:k]
                ),
                title="Latent profiles",
                legend=alt.Legend(orient="top"),
            ),
            order=alt.Order("profile:N"),
            tooltip=[
                alt.Tooltip("hour:Q", title="hour"),
                alt.Tooltip("profile:N", title="latent profile"),
                alt.Tooltip(
                    "kw:Q", title="contribution kW", format=".2f"
                ),
            ],
        )
    )

    total_base = alt.Chart(total_df).encode(
        x=x_shared,
        y=y_shared,
        tooltip=[
            alt.Tooltip("hour:Q", title="hour"),
            alt.Tooltip("kw:Q", title="total kW", format=".2f"),
        ],
    )
    total_line = total_base.mark_line(
        color=MAIN_CHART_COLOR, strokeWidth=2.5, interpolate="linear"
    )
    total_points = total_base.mark_point(
        color=MAIN_CHART_COLOR, filled=True, size=40
    )

    chart = (bars + total_line + total_points).properties(
        height=260,
        width="container",
        title="Average hourly power consumption",
    )
    return _vega(chart)


def peak_day_comparison_chart(result: PredictionResult) -> html.Div:
    df = pd.DataFrame(
        [
            {"hour": i, "kw": float(v), "profile": result.max_title}
            for i, v in enumerate(result.max_curve)
        ]
        + [
            {
                "hour": i,
                "kw": float(v),
                "profile": result.current_title,
            }
            for i, v in enumerate(result.curve)
        ]
    )
    color_scale = alt.Scale(
        domain=[result.max_title, result.current_title],
        range=[MAXIMUM_COLOR, MAIN_CHART_COLOR],
    )

    base = alt.Chart(df).encode(
        x=alt.X(
            "hour:Q",
            title="hour",
            scale=alt.Scale(domain=[0, len(result.curve) - 1]),
            axis=alt.Axis(values=list(range(len(result.curve)))),
        ),
        y=alt.Y(
            "kw:Q",
            title="kW",
            scale=alt.Scale(domain=[0, POWER_AXIS_MAX]),
        ),
        color=alt.Color(
            "profile:N",
            scale=color_scale,
            title=None,
            legend=alt.Legend(orient="top"),
        ),
        tooltip=[
            alt.Tooltip("hour:Q", title="hour"),
            alt.Tooltip("kw:Q", title="kW", format=".2f"),
            alt.Tooltip("profile:N", title=""),
        ],
    )
    lines = base.mark_line(strokeWidth=2.5, interpolate="linear")
    points = base.mark_point(filled=True, size=40)
    chart = (lines + points).properties(height=220, width="container")
    return _vega(chart)


def profile_mixture_chart(result: PredictionResult) -> html.Div:
    k = len(result.probs)
    profile_names = [f"profile-{i + 1}" for i in range(k)]
    df = pd.DataFrame(
        {"category": profile_names, "value": result.probs}
    )
    chart = (
        alt.Chart(df, title="Profile mixture")
        .properties(width="container", height=160)
        .mark_bar()
        .encode(
            x=alt.X(
                "value",
                title="contribution",
                scale=alt.Scale(domain=[0, 1]),
            ),
            y=alt.Y("category", title="latent profile"),
            color=alt.Color(
                "category",
                scale=alt.Scale(
                    domain=profile_names, range=PROFILE_COLORS[:k]
                ),
                legend=None,
            ),
            tooltip=[
                alt.Tooltip(
                    "value", title="contribution", format=".3f"
                ),
                alt.Tooltip("category", title="latent profile"),
            ],
        )
    )
    return _vega(chart)


def profile_mixture_compare_chart(
    result_a: PredictionResult,
    result_b: PredictionResult,
) -> html.Div:
    k = max(len(result_a.probs), len(result_b.probs))
    profile_names = [f"profile-{i + 1}" for i in range(k)]
    rows = []
    for i in range(k):
        if i < len(result_a.probs):
            rows.append(
                {
                    "category": profile_names[i],
                    "side": "A",
                    "value": float(result_a.probs[i]),
                }
            )
        if i < len(result_b.probs):
            rows.append(
                {
                    "category": profile_names[i],
                    "side": "B",
                    "value": float(result_b.probs[i]),
                }
            )
    df = pd.DataFrame(rows)
    chart = (
        alt.Chart(df, title="Profile mixture (A vs. B)")
        .properties(width="container", height=220)
        .mark_bar()
        .encode(
            x=alt.X(
                "value:Q",
                title="contribution",
                scale=alt.Scale(domain=[0, 1]),
            ),
            y=alt.Y("side:N", title=None, axis=alt.Axis(labels=False, ticks=False)),
            row=alt.Row(
                "category:N",
                title=None,
                header=alt.Header(labelAngle=0, labelAlign="left"),
            ),
            color=alt.Color(
                "side:N",
                scale=alt.Scale(
                    domain=["A", "B"],
                    range=[MAIN_CHART_COLOR, MAXIMUM_COLOR],
                ),
                legend=alt.Legend(orient="top", title=None),
            ),
            tooltip=[
                alt.Tooltip("category:N", title="latent profile"),
                alt.Tooltip("side:N", title="side"),
                alt.Tooltip("value:Q", title="contribution", format=".3f"),
            ],
        )
    )
    return _vega(chart)


def latent_breakdown_chart(result: PredictionResult) -> html.Div:
    k = len(result.probs)
    profile_names = [f"profile-{i + 1}" for i in range(k)]
    rows = [
        {
            "hour": hour,
            "profile": profile_names[i],
            "value": float(result.probs[i] * result.profile[hour]),
        }
        for hour in range(len(result.profile))
        for i in range(k)
    ]
    df = pd.DataFrame(rows)
    chart = (
        alt.Chart(df, title="Latent profile contribution per hour")
        .properties(height=160, width="container")
        .mark_bar(size=15)
        .encode(
            x=alt.X(
                "hour:Q",
                title="hour",
                scale=alt.Scale(domain=[0, 24]),
                axis=alt.Axis(tickCount=24),
            ),
            y=alt.Y(
                "value:Q",
                title="fraction",
                scale=alt.Scale(domain=[0, FRACTION_AXIS_MAX]),
            ),
            color=alt.Color(
                "profile:N",
                scale=alt.Scale(
                    domain=profile_names, range=PROFILE_COLORS[:k]
                ),
                title="Latent profiles",
                legend=alt.Legend(orient="top"),
            ),
            tooltip=[
                alt.Tooltip("hour:Q", title="hour"),
                alt.Tooltip(
                    "value:Q", title="contribution", format=".3f"
                ),
                alt.Tooltip("profile:N", title="latent profile"),
            ],
        )
    )
    return _vega(chart)
