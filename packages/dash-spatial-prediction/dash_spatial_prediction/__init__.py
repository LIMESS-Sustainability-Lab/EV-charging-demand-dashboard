import sys as _sys

from . import dash_react_components as _drc
from .dash_react_components import (
    InteractiveMap,
    MapLocation,
    MapLocationField,
)
from .layers import (
    LinesLayer,
    PointsLayer,
    PolygonsLayer,
    linear_size_scale,
    viridis_scale,
)
from .ui import (
    Banner,
    FeatureGroups,
    ValueDisplay,
    feature_row_from_df,
)

# Dash's asset loader:
# 1. registers the top-level module of each Component class (here,
#    `dash_spatial_prediction`) and reads its `_js_dist` / `_css_dist`.
# 2. for each entry, imports `namespace` as a top-level module to resolve
#    the on-disk path of the asset file.
# We re-expose the subpackage's dist lists here so step 1 finds them, and
# alias the subpackage as top-level `dash_react_components` so step 2 works.
_sys.modules.setdefault("dash_react_components", _drc)

_js_dist = _drc._js_dist
_css_dist = _drc._css_dist

__version__ = _drc.__version__

__all__ = [
    "Banner",
    "FeatureGroups",
    "InteractiveMap",
    "LinesLayer",
    "MapLocation",
    "MapLocationField",
    "PointsLayer",
    "PolygonsLayer",
    "ValueDisplay",
    "feature_row_from_df",
    "linear_size_scale",
    "viridis_scale",
]
