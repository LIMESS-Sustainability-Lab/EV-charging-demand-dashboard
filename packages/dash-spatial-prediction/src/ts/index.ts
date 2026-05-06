import InteractiveMap from "./components/InteractiveMap";

// Register with Dash's component registry
(window as any).dash_react_components = {
  InteractiveMap,
};

export { InteractiveMap };
