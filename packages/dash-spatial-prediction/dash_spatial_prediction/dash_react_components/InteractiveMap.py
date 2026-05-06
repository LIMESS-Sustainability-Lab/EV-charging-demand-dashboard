from dash.development.base_component import (
    Component,
    _explicitize_args,
)


class InteractiveMap(Component):
    """A bidirectional map component using MapLibre GL.

    Accepts declarative layers from the server and reports back clicks
    on empty space (clickedCoord) or on features of clickable layers
    (clickedFeature).

    Keyword arguments:

    - id (string; optional):
        Component ID.

    - layers (list of dicts; optional):
        Declarative layer specs. Each entry: {id, type, data, color?,
        color_by?, color_scale?, opacity?, clickable?}. type is one of
        "points", "polygons", "lines". data is a GeoJSON FeatureCollection.

    - center (list of numbers; default [14.4292, 50.0856]):
        Initial map center as [lng, lat].

    - zoom (number; default 13):
        Initial zoom level.

    - height (string; default '400px'):
        CSS height of the map container.

    - mapStyle (string; optional):
        MapLibre style URL or object.

    - clickedCoord (dict; optional):
        {lng, lat} for the most recent click that hit no feature of a
        clickable layer. Written by the component via setProps.

    - clickedFeature (dict; optional):
        {layer_id, properties, lng, lat} for the most recent click that
        hit a feature of a clickable layer. Written by the component
        via setProps.
    """

    _children_props: list[str] = []
    _base_nodes = ["children"]
    _namespace = "dash_react_components"
    _type = "InteractiveMap"

    @_explicitize_args
    def __init__(
        self,
        id=Component.UNDEFINED,
        layers=Component.UNDEFINED,
        center=Component.UNDEFINED,
        zoom=Component.UNDEFINED,
        height=Component.UNDEFINED,
        mapStyle=Component.UNDEFINED,
        clickedCoord=Component.UNDEFINED,
        clickedFeature=Component.UNDEFINED,
        **kwargs,
    ):
        self._prop_names = [
            "id",
            "layers",
            "center",
            "zoom",
            "height",
            "mapStyle",
            "clickedCoord",
            "clickedFeature",
        ]
        self._valid_wildcard_attributes = []
        self.available_properties = [
            "id",
            "layers",
            "center",
            "zoom",
            "height",
            "mapStyle",
            "clickedCoord",
            "clickedFeature",
        ]
        self.available_wildcard_properties = []
        _explicit_args = kwargs.pop("_explicit_args")
        _locals = locals()
        _locals.update(kwargs)
        args = {
            k: _locals[k] for k in _explicit_args if k != "children"
        }
        super().__init__(**args)
