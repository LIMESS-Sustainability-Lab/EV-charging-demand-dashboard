from dashboard.settings import settings
from latentcurvemodel import (
    ChargingProfilePredictor,
    settings as latentcurvemodel_settings,
)

latentcurvemodel_settings.postgres_connection_string = (
    settings.POSTGRES_CONNECTION_STRING
)
predictor = ChargingProfilePredictor()
