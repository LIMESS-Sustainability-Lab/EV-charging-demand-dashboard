from dataclasses import dataclass

import numpy as np
from latentcurvemodel import (
    ChargingProfilePredictor,
    PredictionRequest,
    Spatial,
    Station,
    Temporal,
)

from .forms import FormModel

MONTHS = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)
DAYS = (
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
)


def build_request(form: FormModel) -> PredictionRequest:
    return PredictionRequest(
        spatial=Spatial(
            lon=form.loc.location.lng, lat=form.loc.location.lat
        ),
        station=Station(
            charging_type=form.charger.charging_type,
            n_ac_siblings=form.charger.n_ac_siblings,
            n_dc_siblings=form.charger.n_dc_siblings,
        ),
        temporal=Temporal(
            year=int(form.time.year),
            month=MONTHS.index(form.time.month) + 1,
            weekday=DAYS.index(form.time.weekday) + 1,
        ),
    )


@dataclass
class PredictionResult:
    curve: np.ndarray  # shape (24,), kW/hour
    total_kwh: float
    profile: np.ndarray  # shape (24,), normalised
    probs: np.ndarray  # shape (k,), mixture weights
    current_title: str

    max_curve: np.ndarray  # shape (24,), peak day's kW/hour
    max_total_kwh: float
    max_title: str


def compute_prediction(
    *,
    model: ChargingProfilePredictor,
    request: PredictionRequest,
    month_name: str,
    weekday_name: str,
) -> PredictionResult:
    profile, total_power, probs = model.predict_components(request)
    profile = np.asarray(profile).squeeze(0)
    total_power_scalar = float(np.asarray(total_power).squeeze())
    probs = np.asarray(probs).squeeze(0)
    curve = profile * total_power_scalar

    max_curve, max_total, max_month, max_weekday = _year_maximum(
        model, request
    )

    return PredictionResult(
        curve=curve,
        total_kwh=float(curve.sum()),
        profile=profile,
        probs=probs,
        current_title=f"{weekday_name}s of {month_name}",
        max_curve=max_curve,
        max_total_kwh=max_total,
        max_title=f"{DAYS[max_weekday - 1]}s of {MONTHS[max_month - 1]}",
    )


def _year_maximum(
    model: ChargingProfilePredictor,
    request: PredictionRequest,
) -> tuple[np.ndarray, float, int, int]:
    # 84 sweep requests share the same Spatial, so the predictor's
    # spatial pipeline runs once (via its lru_cache).
    sweep = [
        PredictionRequest(
            spatial=request.spatial,
            station=request.station,
            temporal=Temporal(
                year=request.temporal.year, month=m, weekday=wd
            ),
        )
        for m in range(1, 13)
        for wd in range(1, 8)
    ]
    profiles, total_powers, _ = model.predict_components(sweep)
    profiles = np.asarray(profiles)
    total_powers = np.asarray(total_powers).reshape(-1)

    curves = profiles * total_powers[:, None]
    daily_totals = curves.sum(axis=1)
    argmax = int(daily_totals.argmax())

    return (
        curves[argmax],
        float(daily_totals[argmax]),
        sweep[argmax].temporal.month,
        sweep[argmax].temporal.weekday,
    )
