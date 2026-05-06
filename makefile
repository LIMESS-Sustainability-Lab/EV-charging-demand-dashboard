install:
	uv sync --group local
	cd packages/dash-spatial-prediction && npm install

build-components:
	cd packages/dash-spatial-prediction && npm run build

dashboard-dev:
	ENVIRONMENT=development uv run -m dashboard.app

dashboard-production:
	ENVIRONMENT=production uv run -m gunicorn dashboard.app:server --bind 0.0.0.0:8050

dashboard:
	uv run -m gunicorn dashboard.app:server --bind 0.0.0.0:8050

dev:
	make dashboard-dev

format:
	uv run ruff format packages

lint:
	uv run ruff check packages
	uv run mypy packages

fix:
	uv run ruff format packages
	uv run ruff check --fix packages
