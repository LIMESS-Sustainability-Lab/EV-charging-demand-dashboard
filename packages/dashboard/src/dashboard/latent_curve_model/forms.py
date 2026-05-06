from typing import Literal, get_args

from pydantic import BaseModel, Field

from dash_spatial_prediction import MapLocation


DEFAULT_LAT = 50.08563801157197
DEFAULT_LON = 14.429168701171875


Month = Literal[
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
]
MONTHS = get_args(Month)


Day = Literal[
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]
DAYS = get_args(Day)


Year = Literal["2022", "2023", "2024", "2025"]


ChargingType = Literal["AC", "DC"]


class LocationSelection(BaseModel):
    location: MapLocation = MapLocation(
        lat=DEFAULT_LAT, lng=DEFAULT_LON
    )


class TimeSelection(BaseModel):
    month: Month = "January"
    weekday: Day = "Monday"
    year: Year = "2024"


class ChargerSelection(BaseModel):
    charging_type: ChargingType = "AC"
    n_ac_siblings: int = Field(
        0,
        ge=0,
        description="Number of other AC charging points at the same station.",
    )
    n_dc_siblings: int = Field(
        0,
        ge=0,
        description="Number of other DC charging points at the same station.",
    )


class FormModel(BaseModel):
    loc: LocationSelection
    time: TimeSelection
    charger: ChargerSelection


class SamplingSelection(BaseModel):
    radius_m: int = Field(
        200,
        ge=10,
        le=2000,
        description="Sampling disk radius around the picked location, in metres.",
    )
    n_samples: int = Field(
        16,
        ge=4,
        le=150,
        description="Number of stratified samples drawn inside the disk.",
    )


class SamplingFormModel(BaseModel):
    loc: LocationSelection = LocationSelection()
    time: TimeSelection = TimeSelection()
    charger: ChargerSelection = ChargerSelection()
    sampling: SamplingSelection = SamplingSelection()


class CompareFormModel(BaseModel):
    # Location is per-side; time and charger are shared so the
    # comparison stays apples-to-apples.
    location_a: LocationSelection = LocationSelection()
    location_b: LocationSelection = LocationSelection()
    time: TimeSelection = TimeSelection()
    charger: ChargerSelection = ChargerSelection()


def to_form_model(comp: "CompareFormModel", side: str) -> FormModel:
    if side == "a":
        loc = comp.location_a
    elif side == "b":
        loc = comp.location_b
    else:
        raise ValueError(f"unknown side: {side!r}")
    return FormModel(loc=loc, time=comp.time, charger=comp.charger)
