import geopandas as gpd
import dash_mantine_components as dmc
from dash import Input, Output, callback
from dash_pydantic_form import ModelForm
from latentcurvemodel import extract_charger_spatial_features

from dashboard.latent_curve_model.charts import (
    DC_POWER_AXIS_MAX,
    POWER_AXIS_MAX,
    peak_day_comparison_chart,
    power_curve_chart,
    profile_mixture_chart,
)
from dashboard.latent_curve_model.forms import FormModel
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
from dashboard.shared.utils import is_in_prague
from dash_spatial_prediction import (
    Banner,
    FeatureGroups,
    ValueDisplay,
    feature_row_from_df,
)

TAB_PREDICTION = "prediction"
TAB_SPATIAL = "spatial"
TABS_ID = "interactive-map-tabs"
OUTPUT_ID = "interactive-map-output"
FORM_AIO_ID = "interactive-map-model"
FORM_ID = "interactive-map-form"


@callback(
    Output(OUTPUT_ID, "children"),
    Input(ModelForm.ids.main(FORM_AIO_ID, FORM_ID), "data"),
    Input(TABS_ID, "value"),
)
def use_form_data(form_data: dict, tab: str):
    if not form_data:
        return Banner("fill in the form to see predictions")
    try:
        parsed = FormModel(**form_data)
    except Exception as e:
        return Banner(f"error\n{e}")

    if not is_in_prague(
        parsed.loc.location.lat, parsed.loc.location.lng
    ):
        return Banner("Selected location is outside Prague.")

    if tab == TAB_SPATIAL:
        return _spatial_features_view(parsed)
    return _prediction_view(parsed)


def _prediction_view(parsed: FormModel):
    result = compute_prediction(
        model=model,
        request=build_request(parsed),
        month_name=parsed.time.month,
        weekday_name=parsed.time.weekday,
    )
    y_axis_max = (
        DC_POWER_AXIS_MAX
        if parsed.charger.charging_type == "DC"
        else POWER_AXIS_MAX
    )

    return dmc.ScrollArea(
        dmc.Container(
            dmc.Stack(
                [
                    Card(
                        "tabler:bolt",
                        "Average hourly power",
                        power_curve_chart(
                            result,
                            y_axis_max=y_axis_max,
                        ),
                    ),
                    dmc.SimpleGrid(
                        [
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
                                "tabler:flame",
                                "Peak day",
                                ValueDisplay(
                                    label=result.max_title,
                                    value=f"{result.max_total_kwh:.2f}",
                                    unit="kWh",
                                ),
                            ),
                            Card(
                                "tabler:chart-bar",
                                "Peak-day comparison",
                                peak_day_comparison_chart(
                                    result,
                                    y_axis_max=y_axis_max,
                                ),
                            ),
                            Card(
                                "tabler:layers-intersect",
                                "Latent profile mixture",
                                profile_mixture_chart(result),
                            ),
                        ],
                        cols=2,
                        spacing="md",
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


def _spatial_features_view(parsed: FormModel):
    return dmc.ScrollArea(
        dmc.Container(
            dmc.Stack(
                [
                    Card(
                        "tabler:map-pin",
                        "Location",
                        dmc.Text(
                            f"lat: {parsed.loc.location.lat:.5f}  ·  "
                            f"lng: {parsed.loc.location.lng:.5f}",
                            size="sm",
                            c="gray",
                        ),
                    ),
                    Card(
                        "tabler:layout-grid",
                        "Spatial features",
                        FeatureGroups(
                            feature_row_from_df(
                                extract_charger_spatial_features(
                                    chargers=gpd.GeoDataFrame(
                                        {},
                                        geometry=gpd.points_from_xy(
                                            x=[
                                                parsed.loc.location.lng
                                            ],
                                            y=[
                                                parsed.loc.location.lat
                                            ],
                                        ),
                                    )
                                )
                            )
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


layout = PredictionPageShell(
    sidebar_title="Prediction parameters",
    sidebar_body=ModelForm(
        FormModel, aio_id=FORM_AIO_ID, form_id=FORM_ID
    ),
    tabs=[
        Tab("Model prediction", TAB_PREDICTION, "tabler:chart-line"),
        Tab("Spatial features", TAB_SPATIAL, "tabler:map-2"),
    ],
    tabs_id=TABS_ID,
    output_id=OUTPUT_ID,
)
