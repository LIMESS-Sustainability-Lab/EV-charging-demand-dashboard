from dashboard.settings import settings
from latentcurvemodel import (
    ChargingProfilePredictor,
    settings as latentcurvemodel_settings,
)

latentcurvemodel_settings.POSTGRES_CONNECTION_STRING = (
    settings.POSTGRES_CONNECTION_STRING
)
predictor = ChargingProfilePredictor()
