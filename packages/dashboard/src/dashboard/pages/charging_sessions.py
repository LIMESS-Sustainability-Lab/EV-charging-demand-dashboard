import ast
from functools import lru_cache
from typing import Optional

import altair as alt
import dash
import dash_ag_grid as dag
import dash_mantine_components as dmc
import dash_vega_components as dvc
import geopandas as gpd
import pandas as pd
from dash import Input, Output, State, callback, dcc, html
from dash_iconify import DashIconify
from sqlalchemy import text

from dash_spatial_prediction import (
    Banner,
    InteractiveMap,
    PointsLayer,
)
from dashboard.shared.data.engine import get_engine


PRAGUE_LNG = 14.4378
PRAGUE_LAT = 50.0755

MAP_ID = "cs-map"
STORE_ID = "cs-selected"
TABS_ID = "cs-tabs"

LIFETIME_BODY_ID = "cs-lifetime-body"
HOURLY_BODY_ID = "cs-hourly-body"
LIFETIME_CHART_ID = "cs-lifetime-chart"
SESSIONS_BODY_ID = "cs-sessions-body"
STATION_BODY_ID = "cs-station-body"

YEAR_ID = "cs-year"
MONTH_ID = "cs-month"
WEEKDAY_ID = "cs-weekday"
CP_FILTER_ID = "cs-cp-filter"

CHARGERS_LAYER_ID = "chargers"
HIGHLIGHT_LAYER_ID = "chargers-highlight"

TAB_OVERVIEW = "overview"
TAB_SESSIONS = "sessions"
TAB_DURATION_POWER = "duration_power"

DURATION_POWER_BODY_ID = "cs-duration-power-body"
DURATION_POWER_SCALE_ID = "cs-duration-power-scale"

# Match the SQL filter so all chargers share the same canvas.
DURATION_POWER_X_MAX = 1700
DURATION_POWER_Y_MAX = 120



@lru_cache(maxsize=1)
def _load_chargers_gdf() -> gpd.GeoDataFrame:
    sql = text(
        """
        SELECT
            u.charger_id,
            u.utilization,
            u.ncs_total,
            u.primary_connector_type,
            COALESCE(u.geometry, cp.geom_centroid) AS geometry
        FROM pre.charging_sessions_lifetime_utilization u
        LEFT JOIN (
            SELECT charger_id,
                   ST_Centroid(ST_Collect(geometry)) AS geom_centroid
            FROM public.chargers_pre
            WHERE geometry IS NOT NULL
            GROUP BY charger_id
        ) cp USING (charger_id)
        WHERE COALESCE(u.geometry, cp.geom_centroid) IS NOT NULL
        """
    )
    return gpd.read_postgis(sql, get_engine(), geom_col="geometry")


def _query_lifetime(charger_id: str) -> Optional[pd.Series]:
    sql = text(
        "SELECT * FROM pre.charging_sessions_lifetime_utilization "
        "WHERE charger_id = :cid"
    )
    df = pd.read_sql(sql, get_engine(), params={"cid": charger_id})
    return df.iloc[0] if len(df) else None


def _query_session_span(charger_id: str) -> dict:
    sql = text(
        """
        SELECT
            MIN(charging_start) AS first_session,
            MAX(charging_start) AS last_session,
            COUNT(*) AS n_sessions
        FROM pre.charging_sessions_prague
        WHERE charger_id = :cid
        """
    )
    df = pd.read_sql(sql, get_engine(), params={"cid": charger_id})
    if not len(df):
        return {
            "first_session": None,
            "last_session": None,
            "n_sessions": 0,
        }
    return df.iloc[0].to_dict()


def _query_hourly(
    charger_id: str,
    year: Optional[int],
    month: Optional[int],
    weekday: Optional[int],
) -> pd.DataFrame:
    sql = text(
        """
        SELECT
            EXTRACT(HOUR FROM hour_start)::int AS hour,
            AVG(kwh)::float AS avg_kwh,
            COUNT(*) AS n
        FROM pre.charging_sessions_hourly_bins
        WHERE charger_id = :cid
          AND (:year IS NULL OR EXTRACT(YEAR FROM hour_start) = :year)
          AND (:month IS NULL OR EXTRACT(MONTH FROM hour_start) = :month)
          AND (:weekday IS NULL OR EXTRACT(ISODOW FROM hour_start) = :weekday)
        GROUP BY 1
        ORDER BY 1
        """
    )
    # pandas-stubs disallows None in params; SQLAlchemy handles it fine.
    return pd.read_sql(
        sql,
        get_engine(),
        params={  # type: ignore[arg-type]
            "cid": charger_id,
            "year": year,
            "month": month,
            "weekday": weekday,
        },
    )


def _query_lifetime_daily(charger_id: str) -> pd.DataFrame:
    # `charging_sessions_hourly_bins` is zero-filled upstream, so a
    # plain GROUP BY yields a dense daily series.
    sql = text(
        """
        SELECT
            date_trunc('day', hour_start)::date AS day,
            SUM(kwh)::float AS kwh
        FROM pre.charging_sessions_hourly_bins
        WHERE charger_id = :cid
        GROUP BY 1
        ORDER BY 1
        """
    )
    return pd.read_sql(sql, get_engine(), params={"cid": charger_id})


def _query_cp_values(charger_id: str) -> list[Optional[str]]:
    sql = text(
        "SELECT DISTINCT charging_point_id "
        "FROM pre.charging_sessions_prague "
        "WHERE charger_id = :cid "
        "ORDER BY charging_point_id NULLS LAST"
    )
    df = pd.read_sql(sql, get_engine(), params={"cid": charger_id})
    return df["charging_point_id"].tolist()


def _query_sessions(
    charger_id: str, cp_filter: Optional[str]
) -> pd.DataFrame:
    # AgGrid paginates client-side, so no LIMIT here.
    sql = text(
        """
        SELECT charger_id, charging_point_id, charging_start, charging_end,
               consumption_kwh, connector_type, outlet_number
        FROM pre.charging_sessions_prague
        WHERE charger_id = :cid
          AND (
               :cp IS NULL
            OR (:cp = '__unassigned__' AND charging_point_id IS NULL)
            OR charging_point_id = :cp
          )
        ORDER BY charging_start DESC
        """
    )
    # pandas-stubs disallows None in params; SQLAlchemy handles it fine.
    return pd.read_sql(
        sql,
        get_engine(),
        params={"cid": charger_id, "cp": cp_filter},  # type: ignore[arg-type]
    )


def _query_duration_power(charger_id: str) -> pd.DataFrame:
    sql = text(
        """
        SELECT
            css.evse_id,
            css.charging_point_id,
            cp.connector_power_type,
            cp.connector_power_kw,
            css.consumption_kwh,
            ROUND(
                EXTRACT(EPOCH FROM (css.charging_end - css.charging_start))::numeric / 60,
                3
            ) AS duration_m
        FROM pre.charging_sessions_prague css
        JOIN public.charging_points_pre cp ON css.evse_id = cp.evse_id
        WHERE css.evse_id IS NOT NULL
          AND css.charger_id = :cid
          AND (css.charging_end - css.charging_start) > INTERVAL '0 minutes'
          AND (css.charging_end - css.charging_start) < INTERVAL '1700 minutes'
          AND css.consumption_kwh < 120
        """
    )
    return pd.read_sql(sql, get_engine(), params={"cid": charger_id})


def _query_station(charger_id: str) -> pd.DataFrame:
    sql = text(
        "SELECT charger_id, charging_point_id, evse_id, connectors, "
        "capabilities, cpo_id "
        "FROM public.chargers_pre "
        "WHERE charger_id = :cid "
        "ORDER BY charging_point_id"
    )
    return pd.read_sql(sql, get_engine(), params={"cid": charger_id})




MONTH_NAMES = [
    "",
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
]
WEEKDAY_NAMES = ["", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _chargers_layer(gdf: gpd.GeoDataFrame) -> dict:
    return PointsLayer(
        id=CHARGERS_LAYER_ID,
        data=gdf[["charger_id", "geometry"]],
        color="#2ca02c",
        radius=5,
        stroke_width=1,
        stroke_color="#ffffff",
        clickable=True,
        hoverable=True,
        tooltip="{charger_id}",
    ).to_dict()


def _highlight_layer(charger_id: Optional[str]) -> Optional[dict]:
    if not charger_id:
        return None
    try:
        gdf = _load_chargers_gdf()
    except Exception:
        return None
    sel = gdf.loc[
        gdf["charger_id"] == charger_id, ["charger_id", "geometry"]
    ]
    if sel.empty:
        return None
    return PointsLayer(
        id=HIGHLIGHT_LAYER_ID,
        data=sel,
        color="#e74c3c",
        radius=11,
        stroke_width=3,
        stroke_color="#ffffff",
        # Pass clicks through to the base layer so the user can click
        # a different charger even if the highlight covers it.
        clickable=False,
        hoverable=False,
    ).to_dict()


def _hourly_chart(df: pd.DataFrame) -> html.Div:
    if df.empty:
        return Banner("No hourly bins match those filters.")
    base = alt.Chart(df).encode(
        x=alt.X(
            "hour:Q",
            title="hour",
            scale=alt.Scale(domain=[0, 23]),
            axis=alt.Axis(values=list(range(24))),
        ),
        y=alt.Y("avg_kwh:Q", title="avg kWh / hour"),
        tooltip=[
            alt.Tooltip("hour:Q", title="hour"),
            alt.Tooltip("avg_kwh:Q", title="avg kWh", format=".2f"),
            alt.Tooltip("n:Q", title="# hourly rows"),
        ],
    )
    area = base.mark_area(
        color="#27ae60",
        opacity=0.35,
        line={"color": "#27ae60", "strokeWidth": 2.5},
        interpolate="linear",
    )
    points = base.mark_point(color="#27ae60", filled=True, size=45)
    chart = (area + points).properties(height=320, width="container")
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


def _lifetime_chart(df: pd.DataFrame) -> html.Div:
    if df.empty:
        return Banner("No hourly bins for this charger.")
    chart = (
        alt.Chart(df)
        .mark_area(
            color="#2e86de",
            opacity=0.35,
            line={"color": "#2e86de", "strokeWidth": 1.2},
            interpolate="linear",
        )
        .properties(height=200, width="container")
        .encode(
            x=alt.X("day:T", title="date"),
            y=alt.Y("kwh:Q", title="daily kWh"),
            tooltip=[
                alt.Tooltip("day:T", title="day"),
                alt.Tooltip("kwh:Q", title="kWh", format=".1f"),
            ],
        )
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


def _duration_power_chart(
    df: pd.DataFrame, *, global_scale: bool = True
) -> html.Div:
    """Scatter of session duration (min) vs consumption (kWh), colored
    by plug type (power_type + power_kw). One point per session.

    `global_scale=True` pins x and y to the SQL filter caps (1700 min,
    120 kWh) so all chargers are directly comparable. False lets the
    axes autoscale to the selected charger's range.
    """
    if df.empty:
        return Banner(
            "No sessions for this charger have an evse_id matching "
            "charging_points_pre."
        )

    plot_df = df.copy()
    plot_df["plug_type"] = (
        plot_df["connector_power_type"].astype(str)
        + " · "
        + plot_df["connector_power_kw"]
        .round(0)
        .astype("Int64")
        .astype(str)
        + " kW"
    )
    plug_to_kw: dict[str, float] = dict(
        zip(plot_df["plug_type"], plot_df["connector_power_kw"])
    )
    plug_order = sorted(plug_to_kw, key=lambda p: plug_to_kw[p])

    x_scale = (
        alt.Scale(domain=[0, DURATION_POWER_X_MAX])
        if global_scale
        else alt.Undefined
    )
    y_scale = (
        alt.Scale(domain=[0, DURATION_POWER_Y_MAX])
        if global_scale
        else alt.Undefined
    )

    chart = (
        alt.Chart(plot_df)
        .mark_circle(size=42, opacity=0.55)
        .properties(height=520, width="container")
        .encode(
            x=alt.X(
                "duration_m:Q",
                title="duration (min)",
                scale=x_scale,
            ),
            y=alt.Y(
                "consumption_kwh:Q",
                title="consumption (kWh)",
                scale=y_scale,
            ),
            color=alt.Color(
                "plug_type:N",
                title="plug type",
                sort=plug_order,
                legend=alt.Legend(orient="right"),
            ),
            tooltip=[
                alt.Tooltip(
                    "duration_m:Q",
                    title="duration (min)",
                    format=".1f",
                ),
                alt.Tooltip(
                    "consumption_kwh:Q", title="kWh", format=".2f"
                ),
                alt.Tooltip("plug_type:N", title="plug"),
                alt.Tooltip("evse_id:N", title="EVSE"),
                alt.Tooltip("charging_point_id:N", title="CP"),
            ],
        )
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


def _stat_table(rows: list[tuple[str, str]]) -> dmc.Table:
    """Compact 2-column label/value table in the FeatureGroups style.

    Labels left, monospace right-aligned values, striped, no borders.
    """
    return dmc.Table(
        [
            dmc.TableTbody(
                [
                    dmc.TableTr(
                        [
                            dmc.TableTd(dmc.Text(label, size="sm")),
                            dmc.TableTd(
                                dmc.Text(
                                    value,
                                    size="sm",
                                    ff="monospace",
                                ),
                                style={"textAlign": "right"},
                            ),
                        ]
                    )
                    for label, value in rows
                ]
            )
        ],
        striped="odd",
        withTableBorder=False,
        highlightOnHover=True,
    )


def _section_header(
    label: str, count: Optional[int] = None
) -> dmc.Group:
    children = [dmc.Text(label, fw="bold", size="sm")]
    if count is not None:
        children.append(
            dmc.Badge(
                str(count), size="sm", variant="light", color="gray"
            )
        )
    return dmc.Group(children, gap="sm")


def _lifetime_panel(charger_id: Optional[str]) -> html.Div:
    if not charger_id:
        return Banner("Click a charger on the map.")
    row = _query_lifetime(charger_id)
    if row is None:
        return Banner(f"No lifetime row for charger {charger_id}.")

    def _fmt(v, decimals=2, suffix=""):
        if pd.isna(v):
            return "-"
        return f"{v:.{decimals}f}{suffix}"

    span = _query_session_span(charger_id)

    def _fmt_ts(ts):
        if ts is None or pd.isna(ts):
            return "-"
        return pd.to_datetime(ts).strftime("%Y-%m-%d %H:%M")

    first_ts = span["first_session"]
    last_ts = span["last_session"]
    if (
        first_ts is not None
        and last_ts is not None
        and not pd.isna(first_ts)
        and not pd.isna(last_ts)
    ):
        days = (
            pd.to_datetime(last_ts) - pd.to_datetime(first_ts)
        ).total_seconds() / 86400.0
        span_str = f"{days:.0f} days"
    else:
        span_str = "-"

    operation = [
        ("First session", _fmt_ts(first_ts)),
        ("Last session", _fmt_ts(last_ts)),
        ("Observation span", span_str),
        ("Operating days", _fmt(row["operating_days"], 0)),
    ]

    overall = [
        ("Utilization", _fmt(row["utilization"] * 100, 1, " %")),
        ("Sessions (total)", _fmt(row["ncs_total"], 0)),
        ("Avg daily sessions", _fmt(row["ncs"], 2)),
        ("Avg daily energy", _fmt(row["cdm"], 2, " kWh")),
        ("Avg daily charging time", _fmt(row["ctm"], 2, " h")),
        (
            "Primary connector",
            str(row["primary_connector_type"] or "-"),
        ),
        ("EVSE count", _fmt(row["evse_count"], 0)),
    ]
    weekday_vs = [
        (
            "Weekday utilization",
            _fmt(row["utilization_weekday"] * 100, 1, " %"),
        ),
        (
            "Weekend utilization",
            _fmt(row["utilization_weekend"] * 100, 1, " %"),
        ),
        ("Weekday avg sessions", _fmt(row["ncs_weekday"], 2)),
        ("Weekend avg sessions", _fmt(row["ncs_weekend"], 2)),
        ("Weekday avg energy", _fmt(row["cdm_weekday"], 2, " kWh")),
        ("Weekend avg energy", _fmt(row["cdm_weekend"], 2, " kWh")),
        ("Weekday avg ch. time", _fmt(row["ctm_weekday"], 2, " h")),
        ("Weekend avg ch. time", _fmt(row["ctm_weekend"], 2, " h")),
    ]
    return dmc.Stack(
        [
            _section_header("Operation", len(operation)),
            _stat_table(operation),
            _section_header("Overall", len(overall)),
            _stat_table(overall),
            _section_header("Weekday vs weekend", len(weekday_vs)),
            _stat_table(weekday_vs),
        ],
        gap="xs",
    )


_SESSIONS_COLUMN_DEFS = [
    {
        "field": "charging_start",
        "headerName": "Start",
        "width": 170,
        "sort": "desc",
        "sortable": True,
        "filter": "agDateColumnFilter",
    },
    {
        "field": "charging_end",
        "headerName": "End",
        "width": 170,
        "sortable": True,
        "filter": "agDateColumnFilter",
    },
    {
        "field": "duration_min",
        "headerName": "Dur (min)",
        "width": 110,
        "type": "numericColumn",
        "sortable": True,
        "filter": "agNumberColumnFilter",
        "valueFormatter": {
            "function": "params.value == null ? '-' : params.value.toFixed(0)"
        },
    },
    {
        "field": "consumption_kwh",
        "headerName": "kWh",
        "width": 90,
        "type": "numericColumn",
        "sortable": True,
        "filter": "agNumberColumnFilter",
        "valueFormatter": {
            "function": "params.value == null ? '-' : params.value.toFixed(2)"
        },
    },
    {
        "field": "avg_kw",
        "headerName": "Avg kW",
        "width": 100,
        "type": "numericColumn",
        "sortable": True,
        "filter": "agNumberColumnFilter",
        "valueFormatter": {
            "function": "params.value == null ? '-' : params.value.toFixed(2)"
        },
    },
    {
        "field": "connector_type",
        "headerName": "Connector",
        "width": 180,
        "sortable": True,
        "filter": "agTextColumnFilter",
    },
    {
        "field": "charging_point_id",
        "headerName": "CP",
        "width": 90,
        "sortable": True,
        "filter": "agTextColumnFilter",
        "valueFormatter": {
            "function": "params.value == null ? '\\u2014' : params.value"
        },
    },
    {
        "field": "outlet_number",
        "headerName": "Outlet",
        "width": 90,
        "type": "numericColumn",
        "sortable": True,
        "filter": "agNumberColumnFilter",
        "valueFormatter": {
            "function": "params.value == null ? '-' : params.value.toFixed(0)"
        },
    },
]


def _sessions_table(df: pd.DataFrame) -> html.Div:
    if df.empty:
        return Banner("No sessions match those filters.")

    start = pd.to_datetime(df["charging_start"])
    end = pd.to_datetime(df["charging_end"])
    duration_min = (end - start).dt.total_seconds() / 60.0
    avg_kw = df["consumption_kwh"] / (duration_min / 60.0)
    avg_kw = avg_kw.where(duration_min > 0)

    grid_df = df.copy()
    grid_df["duration_min"] = duration_min
    grid_df["avg_kw"] = avg_kw
    grid_df["charging_start"] = grid_df["charging_start"].astype(str)
    grid_df["charging_end"] = grid_df["charging_end"].astype(str)

    row_data = grid_df.to_dict(orient="records")

    return html.Div(
        dag.AgGrid(
            id="cs-sessions-grid",
            rowData=row_data,
            columnDefs=_SESSIONS_COLUMN_DEFS,
            defaultColDef={
                "resizable": True,
                "sortable": True,
                "filter": True,
                "floatingFilter": True,
            },
            dashGridOptions={
                "pagination": True,
                "paginationPageSize": 50,
                "paginationPageSizeSelector": [25, 50, 100, 200, 500],
                "animateRows": False,
                "rowHeight": 28,
                "headerHeight": 32,
            },
            style={"height": "620px", "width": "100%"},
            className="ag-theme-alpine",
            columnSize="sizeToFit",
        ),
    )


def _parse_pyrepr(value) -> list:
    """Safely parse a Python-repr string (single quotes) into a list.

    `chargers_pre.connectors` and `.capabilities` are stored as literal
    Python `repr()` strings, not JSON.
    """
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    try:
        parsed = ast.literal_eval(str(value))
    except (ValueError, SyntaxError):
        return []
    if isinstance(parsed, (list, tuple)):
        return list(parsed)
    return [parsed]


def _connector_rows(connectors_raw) -> list[dict]:
    """One row per connector on a CP."""
    parsed = _parse_pyrepr(connectors_raw)
    out: list[dict] = []
    for c in parsed:
        if isinstance(c, dict):
            out.append(
                {
                    "id": c.get("id", "-"),
                    "standard": c.get("standard", "-"),
                    "format": c.get("format", "-"),
                    "power_type": c.get("power_type", "-"),
                    "power_kw": c.get("power_kw"),
                }
            )
    return out


def _badges_from_list(items: list[str]) -> html.Div:
    if not items:
        return dmc.Text("-", size="xs", c="gray")
    return dmc.Group(
        [
            dmc.Badge(
                str(x),
                variant="light",
                size="xs",
                radius="sm",
            )
            for x in items
        ],
        gap=4,
    )


def _station_table(df: pd.DataFrame) -> html.Div:
    if df.empty:
        return Banner("No chargers_pre rows for this charger.")
    header = dmc.TableThead(
        dmc.TableTr(
            [
                dmc.TableTh("CP"),
                dmc.TableTh("EVSE"),
                dmc.TableTh("CPO"),
                dmc.TableTh("#Conn"),
                dmc.TableTh("Standard"),
                dmc.TableTh("Format"),
                dmc.TableTh("Power type"),
                dmc.TableTh("kW"),
                dmc.TableTh("Capabilities"),
            ]
        )
    )
    body_rows = []
    for _, r in df.iterrows():
        conns = _connector_rows(r["connectors"])
        caps = _parse_pyrepr(r["capabilities"])

        if not conns:
            # No parseable connectors: keep one empty row so the
            # CP/EVSE/CPO/Capabilities columns still render.
            body_rows.append(
                dmc.TableTr(
                    [
                        dmc.TableTd(
                            str(r["charging_point_id"] or "-")
                        ),
                        dmc.TableTd(str(r["evse_id"] or "-")),
                        dmc.TableTd(str(r["cpo_id"] or "-")),
                        dmc.TableTd("0"),
                        dmc.TableTd("-"),
                        dmc.TableTd("-"),
                        dmc.TableTd("-"),
                        dmc.TableTd("-"),
                        dmc.TableTd(_badges_from_list(caps)),
                    ]
                )
            )
            continue

        for i, conn in enumerate(conns):
            body_rows.append(
                dmc.TableTr(
                    [
                        # Only fill these on the first connector row.
                        dmc.TableTd(
                            str(r["charging_point_id"] or "-")
                            if i == 0
                            else ""
                        ),
                        dmc.TableTd(
                            str(r["evse_id"] or "-") if i == 0 else ""
                        ),
                        dmc.TableTd(
                            str(r["cpo_id"] or "-") if i == 0 else ""
                        ),
                        dmc.TableTd(
                            str(len(conns)) if i == 0 else ""
                        ),
                        dmc.TableTd(str(conn["standard"])),
                        dmc.TableTd(str(conn["format"])),
                        dmc.TableTd(str(conn["power_type"])),
                        dmc.TableTd(
                            f"{conn['power_kw']:.1f}"
                            if isinstance(
                                conn["power_kw"], (int, float)
                            )
                            else "-"
                        ),
                        dmc.TableTd(
                            _badges_from_list(caps) if i == 0 else ""
                        ),
                    ]
                )
            )
    return dmc.ScrollArea(
        dmc.Table(
            [header, dmc.TableTbody(body_rows)],
            striped=True,
            withTableBorder=False,
            stickyHeader=True,
            fz="xs",
        ),
        h=520,
        type="auto",
    )


def _cp_filter_options(
    charger_id: Optional[str],
) -> list[dict]:
    options: list[dict] = [{"label": "All", "value": "__all__"}]
    if not charger_id:
        return options
    for cp in _query_cp_values(charger_id):
        if cp is None:
            options.append(
                {"label": "unassigned", "value": "__unassigned__"}
            )
        else:
            options.append({"label": str(cp), "value": str(cp)})
    return options




def _initial_layers() -> list[dict]:
    try:
        gdf = _load_chargers_gdf()
        return [_chargers_layer(gdf)]
    except Exception:
        return []


def _overview_panel() -> dmc.TabsPanel:
    """Overview tab: lifetime stats + hourly curve side by side, station below."""
    hourly_controls = dmc.Group(
        [
            dmc.Select(
                id=YEAR_ID,
                data=_year_options,
                value="__all__",
                label="Year",
                size="xs",
                w=100,
            ),
            dmc.Select(
                id=MONTH_ID,
                data=_month_options,
                value="__all__",
                label="Month",
                size="xs",
                w=110,
            ),
            dmc.Select(
                id=WEEKDAY_ID,
                data=_weekday_options,
                value="__all__",
                label="Weekday",
                size="xs",
                w=110,
            ),
        ],
        gap="xs",
    )

    main_content = dmc.Grid(
        [
            dmc.GridCol(
                dmc.Stack(
                    [
                        _section_header("Lifetime stats"),
                        html.Div(id=LIFETIME_BODY_ID),
                    ],
                    gap="xs",
                ),
                span=5,
            ),
            dmc.GridCol(
                dmc.Stack(
                    [
                        _section_header("Lifetime daily energy"),
                        html.Div(id=LIFETIME_CHART_ID),
                        dmc.Group(
                            [
                                _section_header(
                                    "Hourly demand curve"
                                ),
                                hourly_controls,
                            ],
                            justify="space-between",
                            align="end",
                            wrap="wrap",
                        ),
                        html.Div(id=HOURLY_BODY_ID),
                    ],
                    gap="xs",
                ),
                span=7,
            ),
        ],
        gutter="md",
    )

    accordion = dmc.Accordion(
        [
            dmc.AccordionItem(
                [
                    dmc.AccordionControl(
                        dmc.Text("Stats & demand curves", fw="bold")
                    ),
                    dmc.AccordionPanel(main_content),
                ],
                value="main",
            ),
            dmc.AccordionItem(
                [
                    dmc.AccordionControl(
                        dmc.Text(
                            "Station / charging points", fw="bold"
                        )
                    ),
                    dmc.AccordionPanel(html.Div(id=STATION_BODY_ID)),
                ],
                value="station",
            ),
        ],
        multiple=True,
        value=["main", "station"],
        variant="separated",
    )

    return dmc.TabsPanel(accordion, value=TAB_OVERVIEW, pt="sm")


def _duration_power_panel() -> dmc.TabsPanel:
    return dmc.TabsPanel(
        dmc.Stack(
            [
                dmc.Group(
                    [
                        dmc.Text("Axis scale:", size="sm", c="gray"),
                        dmc.SegmentedControl(
                            id=DURATION_POWER_SCALE_ID,
                            data=["Global", "Local"],
                            value="Global",
                            size="xs",
                        ),
                    ],
                    gap="xs",
                ),
                html.Div(id=DURATION_POWER_BODY_ID),
            ],
            gap="sm",
        ),
        value=TAB_DURATION_POWER,
        pt="sm",
    )


def _sessions_panel() -> dmc.TabsPanel:
    return dmc.TabsPanel(
        dmc.Stack(
            [
                dmc.Select(
                    id=CP_FILTER_ID,
                    data=[{"label": "All", "value": "__all__"}],
                    value="__all__",
                    label="Charging point",
                    size="xs",
                    w=200,
                ),
                html.Div(id=SESSIONS_BODY_ID),
            ],
            gap="sm",
        ),
        value=TAB_SESSIONS,
        pt="sm",
    )


_year_options = [{"label": "All", "value": "__all__"}] + [
    {"label": str(y), "value": str(y)} for y in range(2022, 2026)
]
_month_options = [{"label": "All", "value": "__all__"}] + [
    {"label": MONTH_NAMES[m], "value": str(m)} for m in range(1, 13)
]
_weekday_options = [{"label": "All", "value": "__all__"}] + [
    {"label": WEEKDAY_NAMES[d], "value": str(d)} for d in range(1, 8)
]


layout = dmc.Box(
    dmc.Stack(
        [
            dmc.Group(
                [
                    dmc.Title("Charging sessions explorer", order=3),
                    dmc.Group(
                        [
                            DashIconify(icon="tabler:bolt", width=18),
                            dmc.Text(
                                "Selected:",
                                size="sm",
                                c="gray",
                            ),
                            dmc.Text(
                                "-",
                                id="cs-selected-label",
                                fw="bold",
                            ),
                        ],
                        gap="xs",
                    ),
                ],
                justify="space-between",
                align="baseline",
            ),
            dmc.Text(
                "All Prague chargers that appear in the sessions table. "
                "Click a charger to populate the panels below.",
                c="gray",
                size="sm",
            ),
            dmc.Paper(
                InteractiveMap(
                    id=MAP_ID,
                    layers=_initial_layers(),
                    center=[PRAGUE_LNG, PRAGUE_LAT],
                    zoom=11,
                    height="520px",
                ),
                withBorder=True,
                radius="md",
                style={"overflow": "hidden"},
            ),
            dmc.Paper(
                dmc.Tabs(
                    [
                        dmc.TabsList(
                            [
                                dmc.TabsTab(
                                    "Overview", value=TAB_OVERVIEW
                                ),
                                dmc.TabsTab(
                                    "Sessions", value=TAB_SESSIONS
                                ),
                                dmc.TabsTab(
                                    "Duration × power",
                                    value=TAB_DURATION_POWER,
                                ),
                            ]
                        ),
                        _overview_panel(),
                        _sessions_panel(),
                        _duration_power_panel(),
                    ],
                    id=TABS_ID,
                    value=TAB_OVERVIEW,
                ),
                withBorder=True,
                radius="md",
                p="md",
            ),
            dcc.Store(id=STORE_ID, data=None),
        ],
        gap="md",
    ),
    px="md",
    py="md",
    style={"maxWidth": "1800px", "margin": "0 auto"},
)




@callback(
    Output(STORE_ID, "data"),
    Output("cs-selected-label", "children"),
    Input(MAP_ID, "clickedFeature"),
    State(STORE_ID, "data"),
    prevent_initial_call=True,
)
def _on_feature_click(
    feature: Optional[dict], current: Optional[str]
):
    if not feature:
        return dash.no_update, dash.no_update
    cid = (feature.get("properties") or {}).get("charger_id")
    if not cid:
        return dash.no_update, dash.no_update
    return cid, cid


@callback(
    Output(MAP_ID, "layers"),
    Input(STORE_ID, "data"),
)
def _update_map_layers(cid: Optional[str]):
    try:
        base = _chargers_layer(_load_chargers_gdf())
    except Exception:
        return []
    highlight = _highlight_layer(cid)
    return [base] + ([highlight] if highlight else [])


@callback(
    Output(LIFETIME_BODY_ID, "children"),
    Input(STORE_ID, "data"),
)
def _render_lifetime(cid: Optional[str]):
    return _lifetime_panel(cid)


@callback(
    Output(HOURLY_BODY_ID, "children"),
    Input(STORE_ID, "data"),
    Input(YEAR_ID, "value"),
    Input(MONTH_ID, "value"),
    Input(WEEKDAY_ID, "value"),
)
def _render_hourly(
    cid: Optional[str],
    year: str,
    month: str,
    weekday: str,
):
    if not cid:
        return Banner("Click a charger on the map.")

    def _coerce(v: str) -> Optional[int]:
        return None if v == "__all__" else int(v)

    df = _query_hourly(
        cid, _coerce(year), _coerce(month), _coerce(weekday)
    )
    return _hourly_chart(df)


@callback(
    Output(LIFETIME_CHART_ID, "children"),
    Input(STORE_ID, "data"),
)
def _render_lifetime_chart(cid: Optional[str]):
    if not cid:
        return Banner("Click a charger on the map.")
    df = _query_lifetime_daily(cid)
    return _lifetime_chart(df)


@callback(
    Output(CP_FILTER_ID, "data"),
    Output(CP_FILTER_ID, "value"),
    Input(STORE_ID, "data"),
)
def _refresh_cp_options(cid: Optional[str]):
    return _cp_filter_options(cid), "__all__"


@callback(
    Output(SESSIONS_BODY_ID, "children"),
    Input(STORE_ID, "data"),
    Input(CP_FILTER_ID, "value"),
)
def _render_sessions(cid: Optional[str], cp_filter: str):
    if not cid:
        return Banner("Click a charger on the map.")
    cp = None if cp_filter == "__all__" else cp_filter
    df = _query_sessions(cid, cp)
    return _sessions_table(df)


@callback(
    Output(STATION_BODY_ID, "children"),
    Input(STORE_ID, "data"),
)
def _render_station(cid: Optional[str]):
    if not cid:
        return Banner("Click a charger on the map.")
    df = _query_station(cid)
    return _station_table(df)


@callback(
    Output(DURATION_POWER_BODY_ID, "children"),
    Input(STORE_ID, "data"),
    Input(DURATION_POWER_SCALE_ID, "value"),
)
def _render_duration_power(cid: Optional[str], scale: str):
    if not cid:
        return Banner("Click a charger on the map.")
    df = _query_duration_power(cid)
    return _duration_power_chart(df, global_scale=(scale == "Global"))
