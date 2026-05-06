## Development

### Project structure

The repo is a uv workspace with two packages:

- **`dash-spatial-prediction`** — reusable Dash component library. Wraps
  a MapLibre map (`InteractiveMap`), a pydantic-form-compatible map
  picker (`MapLocation` / `MapLocationField`), declarative pydantic
  layer specs (points, lines, polygons), and a few presentational
  primitives (`Banner`, `ValueDisplay`, `FeatureGroups`). Owns all the
  geo/map dependencies (`geopandas`, `maplibre-gl`).

- **`dashboard`** — the Dash app itself. Consumes the library above,
  adds model-specific glue.

Inside `dashboard`, the source is grouped by domain rather than by
function:

- **`latent_curve_model/`** holds everything tied to the model:
  predictor singleton, request builder, prediction wrapper, form
  schemas, chart builders, and the model-driven pages. This is the
  only place that imports from `latentcurvemodel`.
- **`shared/`** is app-internal infrastructure that's deliberately
  model-agnostic: layout shells, reusable components, the Postgres
  engine getter, formatting helpers, the Prague-boundary check.
- **`pages/`** at the top level holds development / data-exploration
  pages that don't drive the model (raw SQL viewers, library demos).
  Gated behind `ENABLE_DEV_PAGES`.
- **`app.py`** is the Dash factory + theme + `AppShell`; **`router.py`**
  is the single source of truth for which page modules are mounted.

`latentcurvemodel` is a sibling repo (path dependency in the workspace
`pyproject.toml`), not a subdirectory of this project.

### Routing

Pages are registered through [packages/dashboard/src/dashboard/router.py](packages/dashboard/src/dashboard/router.py).
A `Route` is data — module path, URL, nav label — and `register_pages()`
imports each module and binds it to the Dash page registry. Pages
themselves don't call `dash.register_page`; they only define a `layout`
global (and any callbacks).

The `pages/` directory holds development/data-exploration pages that
are not part of the model demo. They're gated behind
`ENABLE_DEV_PAGES=true` in `.env` and hidden in production by default.

### Page anatomy

Model pages share a layout shell from
[shared/layout/prediction_page.py](packages/dashboard/src/dashboard/shared/layout/prediction_page.py):
left sidebar holds a `dash-pydantic-form` `ModelForm`, right side has
`dmc.Tabs` above an output container. Page modules pass a `FormModel`
subclass + their tabs and own the `@callback` that re-renders the
output.

Form schemas live in
[latent_curve_model/forms.py](packages/dashboard/src/dashboard/latent_curve_model/forms.py):
`FormModel` (single-location), `CompareFormModel` (two-location),
`SamplingFormModel` (single + sampling parameters). They share the
`LocationSelection` / `TimeSelection` / `ChargerSelection` building
blocks so the comparison stays apples-to-apples.
 
The model glue (`build_request`, `compute_prediction`, the predictor
singleton) is in `latent_curve_model/`. Pages call those helpers; they
never construct `latentcurvemodel` types directly.

### Prerequisites

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) package manager
- A sibling clone of `LatentCurveModel` at `../LatentCurveModel` (path
  dependency in the workspace `pyproject.toml`)
- Node.js (only when rebuilding the React component bundle)

### 1. Install dependencies

```bash
make install
```

Runs `uv sync` and `npm install` in `packages/dash-spatial-prediction`.

### 2. Build the React components

```bash
make build-components
```

Only needed when the TypeScript sources under
`packages/dash-spatial-prediction/src/ts/` change. The built bundle is
committed, so a fresh `uv sync` alone is enough to run the app.

### 3. Configure `.env`

```bash
cp .env.template .env
```

Then edit `.env` to fill in your values. See `.env.template` for the
available settings.

### 4. Run the dashboard

```bash
make dev
```

Navigate to http://localhost:8050.

### Working on the React components

When actively developing the React components, run the Vite watcher in
a separate terminal for automatic rebuilds:

```bash
cd packages/dash-spatial-prediction
npm run watch
```

### `latentcurvemodel`: dev vs prod source

`latentcurvemodel` has two sources gated by mutually-exclusive
dependency groups declared in the workspace `pyproject.toml`:

- `--group prod` → installs the pinned commit from the private GitHub
  repo. This is what Dokploy uses (see `Dockerfile`).
- `--group local` → installs `../LatentCurveModel` as an editable path
  dep. `make install` defaults to this.

Switch between them with `uv sync --group <name>`. The two groups can
never be active at the same time (uv enforces it via
`tool.uv.conflicts`).

When you bump the model: tag / push to the LatentCurveModel repo, then
update the `rev = "..."` in `pyproject.toml` here, commit, push.
Dokploy rebuilds with the new pin on next deploy.

### Formatting and linting

Formatting is handled by [Ruff](https://docs.astral.sh/ruff/). Linting is split between Ruff (style, unused imports,
import order, ~600 rules) and [mypy](https://mypy.readthedocs.io/) (type
checking).

```bash
make format    # auto-format everything under packages/
make lint      # report lint + type issues, no edits
make fix       # auto-format AND auto-fix what Ruff can fix
```

`make lint` exits non-zero if there are issues, so it's CI-friendly.
`make fix` covers most Ruff fixes (unused imports, import order, etc.);
mypy issues need human attention.
