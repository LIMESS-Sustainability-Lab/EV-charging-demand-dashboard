from .InteractiveMap import InteractiveMap  # noqa: F401
from .map_location import MapLocation, MapLocationField  # noqa: F401

__version__ = "0.1.0"

_js_dist = [
    {
        "relative_package_path": "dash_react_components.js",
        "namespace": "dash_react_components",
    }
]

_css_dist = [
    {
        "relative_package_path": "dash_react_components.css",
        "namespace": "dash_react_components",
    }
]
