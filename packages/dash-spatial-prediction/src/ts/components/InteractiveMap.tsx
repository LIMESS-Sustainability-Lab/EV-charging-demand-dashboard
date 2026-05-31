import React, { useMemo, useRef, useState } from "react";
import {
  Layer,
  Map as MapGL,
  Popup,
  Source,
  type MapLayerMouseEvent,
  type MapRef,
} from "react-map-gl/maplibre";
import "maplibre-gl/dist/maplibre-gl.css";

type LayerType = "points" | "polygons" | "lines";

interface LayerSpec {
  id: string;
  type: LayerType;
  data: GeoJSON.FeatureCollection;
  color?: string | null;
  color_by?: string | null;
  color_scale?: Array<[number, string]> | null;
  size_by?: string | null;
  size_scale?: Array<[number, number]> | null;
  opacity?: number;
  clickable?: boolean;
  hoverable?: boolean;
  tooltip?: string | null;
  radius?: number;
  stroke_width?: number;
  stroke_color?: string;
  line_width?: number;
}

interface ClickedCoord {
  lng: number;
  lat: number;
}

interface ClickedFeature {
  layer_id: string;
  properties: Record<string, unknown>;
  lng: number;
  lat: number;
}

interface InteractiveMapProps {
  id?: string;
  layers?: LayerSpec[];
  center?: [number, number];
  zoom?: number;
  height?: string;
  mapStyle?: string | object;
  clickedCoord?: ClickedCoord | null;
  clickedFeature?: ClickedFeature | null;
  setProps?: (props: Record<string, unknown>) => void;
}

const LAYER_PREFIX = "lyr-";
const SOURCE_PREFIX = "src-";
const layerIdFor = (id: string) => `${LAYER_PREFIX}${id}`;
const sourceIdFor = (id: string) => `${SOURCE_PREFIX}${id}`;
const fromLayerId = (mlId: string) =>
  mlId.startsWith(LAYER_PREFIX) ? mlId.slice(LAYER_PREFIX.length) : mlId;

// Switch between a base value and a hovered value based on MapLibre's
// per-feature `hover` feature-state (driven by mousemove below).
const hoverCase = (base: unknown, hovered: unknown): unknown => [
  "case",
  ["boolean", ["feature-state", "hover"], false],
  hovered,
  base,
];

const mapLibreLayerType = (t: LayerType): "circle" | "fill" | "line" =>
  t === "points" ? "circle" : t === "polygons" ? "fill" : "line";

// Build a MapLibre paint spec for the given layer type from our simple
// color / color_by / color_scale / size_by fields.
const buildPaint = (layer: LayerSpec): Record<string, unknown> => {
  const opacity = layer.opacity ?? 1.0;
  const hoverable = !!layer.hoverable;

  const baseColor: unknown = layer.color_by
    ? layer.color_scale && layer.color_scale.length >= 2
      ? [
          "interpolate",
          ["linear"],
          ["get", layer.color_by],
          ...layer.color_scale.flatMap(([stop, color]) => [stop, color]),
        ]
      : ["to-color", ["get", layer.color_by]]
    : (layer.color ?? "#3388ff");

  const sizeExpr = (fallback: number): unknown =>
    layer.size_by && layer.size_scale && layer.size_scale.length >= 2
      ? [
          "interpolate",
          ["linear"],
          ["get", layer.size_by],
          ...layer.size_scale.flatMap(([stop, size]) => [stop, size]),
        ]
      : fallback;

  if (layer.type === "points") {
    const radius = sizeExpr(layer.radius ?? 6);
    const strokeW = layer.stroke_width ?? 1;
    const strokeC = layer.stroke_color ?? "#ffffff";
    const hoverRadius: unknown =
      typeof radius === "number" ? radius + 3 : ["+", radius as never, 3];
    return {
      "circle-radius": hoverable ? hoverCase(radius, hoverRadius) : radius,
      "circle-color": baseColor,
      "circle-opacity": opacity,
      "circle-stroke-width": hoverable
        ? hoverCase(strokeW, Math.max(strokeW, 2) + 1)
        : strokeW,
      "circle-stroke-color": hoverable
        ? hoverCase(strokeC, "#222222")
        : strokeC,
    };
  }
  if (layer.type === "polygons") {
    return {
      "fill-color": baseColor,
      "fill-opacity": hoverable
        ? hoverCase(opacity, Math.min(1, opacity + 0.25))
        : opacity,
      "fill-outline-color": hoverable
        ? hoverCase("#333333", "#111111")
        : "#333333",
    };
  }
  // lines
  const lineWidth = sizeExpr(layer.line_width ?? 2);
  const hoverLineWidth: unknown =
    typeof lineWidth === "number" ? lineWidth + 2 : ["+", lineWidth as never, 2];
  return {
    "line-color": baseColor,
    "line-opacity": opacity,
    "line-width": hoverable ? hoverCase(lineWidth, hoverLineWidth) : lineWidth,
  };
};

// Render a tooltip template like "Demand: {value}" using a feature's
// properties. Supports `{name}` and `{name:.Nf}` (numeric format).
const renderTooltip = (
  template: string,
  properties: Record<string, unknown>,
): string =>
  template.replace(/\{([^{}]+)\}/g, (_match, expr: string) => {
    const colon = expr.indexOf(":");
    const key = (colon >= 0 ? expr.slice(0, colon) : expr).trim();
    const fmt = colon >= 0 ? expr.slice(colon + 1).trim() : "";
    const raw = properties[key];
    if (raw === undefined || raw === null) return "";
    const floatFmt = /^\.(\d+)f$/.exec(fmt);
    if (floatFmt && typeof raw === "number") {
      return raw.toFixed(Number(floatFmt[1]));
    }
    return String(raw);
  });

const InteractiveMap: React.FC<InteractiveMapProps> = ({
  id,
  layers = [],
  center = [14.4292, 50.0856],
  zoom = 13,
  height = "400px",
  mapStyle = "https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json",
  setProps,
}) => {
  const mapRef = useRef<MapRef | null>(null);

  // Feature-state bookkeeping for hover highlight. Keyed by source id so
  // we can clear on layer removal.
  const hoveredRef = useRef<{ sourceId: string; featureId: number | string } | null>(null);

  const [popup, setPopup] = useState<
    { lng: number; lat: number; html: string } | null
  >(null);
  const [cursor, setCursor] = useState<string>("auto");

  const clickableLayerIds = useMemo(
    () => layers.filter((l) => l.clickable).map((l) => layerIdFor(l.id)),
    [layers],
  );
  const hoverableLayerIds = useMemo(
    () => layers.filter((l) => l.hoverable).map((l) => layerIdFor(l.id)),
    [layers],
  );
  const interactiveLayerIds = useMemo(
    () => Array.from(new Set([...clickableLayerIds, ...hoverableLayerIds])),
    [clickableLayerIds, hoverableLayerIds],
  );

  const layersById = useMemo(() => {
    const m = new Map<string, LayerSpec>();
    for (const l of layers) m.set(l.id, l);
    return m;
  }, [layers]);

  const onClick = (e: MapLayerMouseEvent) => {
    if (!setProps) return;
    const { lng, lat } = e.lngLat;

    const hit = (e.features ?? []).find((f) =>
      clickableLayerIds.includes(f.layer.id),
    );

    if (hit) {
      setProps({
        clickedFeature: {
          layer_id: fromLayerId(hit.layer.id),
          properties: hit.properties ?? {},
          lng,
          lat,
        },
        clickedCoord: null,
      });
    } else {
      setProps({
        clickedCoord: { lng, lat },
        clickedFeature: null,
      });
    }
  };

  const clearHover = () => {
    const map = mapRef.current?.getMap();
    const h = hoveredRef.current;
    if (map && h) {
      map.setFeatureState(
        { source: h.sourceId, id: h.featureId },
        { hover: false },
      );
    }
    hoveredRef.current = null;
    if (popup) setPopup(null);
    setCursor("auto");
  };

  const onMouseMove = (e: MapLayerMouseEvent) => {
    const map = mapRef.current?.getMap();
    if (!map) return;
    if (hoverableLayerIds.length === 0) {
      clearHover();
      return;
    }
    const feat = (e.features ?? []).find((f) =>
      hoverableLayerIds.includes(f.layer.id),
    );
    if (!feat) {
      clearHover();
      return;
    }

    const featureId = feat.id;
    const sourceId = feat.source;
    const prev = hoveredRef.current;
    if (
      featureId !== undefined &&
      featureId !== null &&
      (!prev ||
        prev.sourceId !== sourceId ||
        prev.featureId !== featureId)
    ) {
      if (prev) {
        map.setFeatureState(
          { source: prev.sourceId, id: prev.featureId },
          { hover: false },
        );
      }
      map.setFeatureState(
        { source: sourceId, id: featureId },
        { hover: true },
      );
      hoveredRef.current = { sourceId, featureId };
    }
    setCursor("pointer");

    const userLayerId = fromLayerId(feat.layer.id);
    const tpl = layersById.get(userLayerId)?.tooltip;
    if (tpl) {
      setPopup({
        lng: e.lngLat.lng,
        lat: e.lngLat.lat,
        html: renderTooltip(tpl, feat.properties ?? {}),
      });
    } else if (popup) {
      setPopup(null);
    }
  };

  return (
    <div id={id} style={{ height, width: "100%" }}>
      <MapGL
        ref={mapRef}
        initialViewState={{
          longitude: center[0],
          latitude: center[1],
          zoom,
        }}
        mapStyle={mapStyle as string}
        interactiveLayerIds={interactiveLayerIds}
        onClick={onClick}
        onMouseMove={onMouseMove}
        onMouseLeave={clearHover}
        cursor={cursor}
        style={{ height: "100%", width: "100%" }}
      >
        {layers.map((layer) => (
          <Source
            key={sourceIdFor(layer.id)}
            id={sourceIdFor(layer.id)}
            type="geojson"
            data={layer.data}
            generateId
          >
            <Layer
              id={layerIdFor(layer.id)}
              type={mapLibreLayerType(layer.type)}
              paint={buildPaint(layer) as never}
            />
          </Source>
        ))}
        {popup && (
          <Popup
            longitude={popup.lng}
            latitude={popup.lat}
            closeButton={false}
            closeOnClick={false}
            offset={12}
          >
            <div dangerouslySetInnerHTML={{ __html: popup.html }} />
          </Popup>
        )}
      </MapGL>
    </div>
  );
};

(InteractiveMap as any).defaultProps = {
  layers: [],
  center: [14.4292, 50.0856],
  zoom: 13,
  height: "400px",
  mapStyle: "https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json",
  clickedCoord: null,
  clickedFeature: null,
};

export default InteractiveMap;
