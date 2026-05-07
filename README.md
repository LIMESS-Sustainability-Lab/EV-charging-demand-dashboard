# Charging Demand Interactive Dashboard
<img src="https://uptime-monitor.jakubzika.com/badge/charging-model-public/status"/>



Interactive dashboard wrapping neural-net model for predicting EV charger demand in Prague.


## Pages

### Location prediction (`/interactive-map`)

Pick a single point in Prague, a calendar slot (year / month / weekday),
and a charger configuration (AC or DC, sibling counts). The page
returns the model's mean hourly power curve for that day, the daily
total in kWh, the peak day across the chosen year, and the latent
profile mixture that produced the curve.

### Compare locations (`/compare-locations`)

Two side-by-side locations with the same time and charger settings,
so the prediction differences are entirely due to spatial inputs. Each
column shows its own power curve, daily total, and latent profile
mixture. A second tab renders a feature-by-feature spatial diff
(grouped by feature family, with an option to hide rows where A and B
agree).

### Location prediction with uncertainty (`/sample-uncertainty`)

Sampling around the picked point, with the
disk radius and sample count both configurable. Each sample is run
through the model and the page shows the hourly power curve as a
mean with a 5-95% band, plus a histogram + KDE of the daily totals.
Useful for gauging how sensitive the prediction is to small spatial
shifts.

## Contributing

For questions or support, contact the author at `zikajak3@fel.cvut.cz`

## License

This project is licensed under the MIT License. See the LICENSE file for details.

## Development

For development documentation, please reffer to [development docs](docs/DEVELOPMENT.md)

