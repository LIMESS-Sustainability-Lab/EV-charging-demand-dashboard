# Urban EV Charging Demand Dashboard
![status](https://uptime-monitor.jakubzika.com/badge/charging-model-public/status)
[![DOI](https://zenodo.org/badge/1231152215.svg)](https://doi.org/10.5281/zenodo.20071167)

<!-- <img src="http://zenodo.org/badge/DOI/10.5281/zenodo.20069103.svg"/> -->


Interactive dashboard wrapping neural-net model for predicting EV charger demand in Prague.


## Pages

### Location prediction

This pages allows selecting a point in map, a time slot and charging point and charging station configuration. 
The model then presents the estimated power consumption for the filled  parameters; together with predicted mixture of profiles and their contribution.

### Compare locations

Same as location prediction, but allows to compare two locations at once. For the same chosen time slot and charging popint and charging station.

### Location prediction with uncertainty

Allows seleting a point in map, time slot, charging point and charging station, number of samples and radius. 

To mitigate low spatial autocorrelation. It samples specified number of locations, which are then turned into predictions. Presents the predictions with uncertainty bound.

### Demand heatmap

Renders Prague-wide demand from the `LatentCurveModel` precomputed grid artifact. The page generates static raster-style Python plots rather than interactive map tiles:

- daily total kWh heatmap, with optional log color scale
- latent profile contribution heatmaps
- learned latent profile curves

The page expects the installed `latentcurvemodel` package to expose `GridHeatmapPredictor` and the packaged `prague_grid_raw.parquet` / `prague_grid_meta.json` artifacts.

## Contributing

For questions or support, contact the author at `zikajak3@fel.cvut.cz`

## License

This project is licensed under the MIT License. See the LICENSE file for details.

## Development

For development documentation, please reffer to [development docs](docs/DEVELOPMENT.md)
