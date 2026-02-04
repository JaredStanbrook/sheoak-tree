# Sheoak Tree Smart Monitor

Real-time smart home monitoring with Flask, SSE streaming, network presence detection, and hardware event analytics.

## Why this project
- Built for a real sharehouse setup with Raspberry Pi support.
- Privacy-first presence tracking (local network only, no GPS).
- Includes a complete local dev flow, CI checks, and mock mode for demos.

## Features
- Live dashboard for sensor and relay state with streaming updates.
- Presence detection via ARP, mDNS, and optional SNMP correlation.
- Analysis dashboard with trend, distribution, and event drill-down charts.
- AI labeling/training workflow is in active migration (CSV -> DB) and staged for a future release.
- Mock GPIO mode for local demos without hardware.

## Stack
- Backend: Flask, SQLAlchemy, Alembic
- Frontend: Jinja templates, vanilla JS modules, Chart.js, custom CSS
- Data: SQLite for app events/device state
- ML: pandas, scikit-learn, XGBoost

## Project Layout
```text
app/
  routes/           # Flask blueprints
  services/         # Presence, hardware, system, ML services
  templates/        # Jinja templates
  static/           # CSS, JS, assets
migrations/         # Alembic migrations
tests/              # Unit + functional tests
infra/              # System/service scripts
docs/               # Architecture and deployment guides
```

## Quickstart
```bash
./setup.sh
source venv/bin/activate
cp .env.example .env
python run.py
```

App runs at `http://localhost:5000`.

## Standard Dev Commands
```bash
make run      # start app
make lint     # ruff check . --fix
make format   # ruff format .
make test     # pytest
make check    # lint + format + tests
make gpio-usage  # report GPIO pin usage from hardware config
```

If you prefer direct commands:
```bash
./venv/bin/ruff check . --fix
./venv/bin/ruff format .
./venv/bin/pytest -v
```

## Demo Workflow
```bash
make seed
# in another terminal (with app running and DEMO_MODE=1 in .env)
make replay
```

## ML Workflow
```bash
make train
```

## Deployment
- Docker compose files: `docker-compose.yml`, `docker-compose.prod.yml`
- Gunicorn entrypoint: `gunicorn -c gunicorn.conf.py wsgi:app`
- Raspberry Pi guide: `docs/DEPLOY_RPI.md`

## Docs
- Architecture: `docs/ARCHITECTURE.md`
- ML pipeline: `docs/ML_PIPELINE.md`
- Deployment: `docs/DEPLOYMENT.md`
- Troubleshooting: `docs/TROUBLESHOOTING.md`

## Testing and Quality Gates
- Lint: Ruff (`E`, `F`, `B`, `I`)
- Formatting: Ruff formatter
- Tests: pytest (`tests/`)
- CI: GitHub Actions for lint, format check, and tests

## Security
- Never commit `.env` or credentials.
- Keep network scan targets and SNMP credentials in environment variables.

## License
MIT (`LICENSE`).
