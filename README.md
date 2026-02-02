# Sheoak Tree Smart Monitor

Sheoak Tree is a Flask + Flask-SocketIO smart home monitor built for a real sharehouse. It blends live hardware signals, non-invasive network presence detection, and ML-based pattern analysis into a glassmorphism dashboard that runs on a Raspberry Pi or in local mock mode.

## Features
- Live dashboard (SocketIO, with SSE fallback) for GPIO and sensor events.
- Presence detection via ARP/MDNS/SNMP scanning (no GPS, no tracking outside your LAN).
- ML analytics pipeline for labeling sequences and training Random Forest/XGBoost models.
- “Survival Guide” PDF embedded for house rules and maintenance.
- Glassmorphism UI with responsive layouts.
- Mock GPIO mode for demos on macOS/Windows/Linux.

## Tech Stack
- Backend: Python 3.8+, Flask, Flask-SocketIO, SQLAlchemy, Alembic
- Realtime: SocketIO (gevent/websocket in prod, threading in dev)
- Frontend: Vanilla JS (ES modules), Chart.js, custom CSS
- Hardware: Raspberry Pi GPIO (with MockGPIO fallback)
- ML: Pandas, scikit-learn, XGBoost

## Architecture (High Level)
```
┌─────────────────────────────┐
│         Browser UI          │
│  Live / Presence / Analysis │
└─────────────┬───────────────┘
              │ SocketIO / SSE
┌─────────────▼───────────────┐
│          Flask App          │
│  Blueprints + Templates     │
├─────────────┬───────────────┤
│ Service Manager              │
│  - Hardware Manager           │
│  - Presence Monitor           │
│  - SNMP Scanner (optional)    │
│  - System Monitor             │
├─────────────┴───────────────┤
│ SQLite (events, devices)     │
└─────────────┬───────────────┘
              │ GPIO / SNMP / ARP
┌─────────────▼───────────────┐
│   Raspberry Pi Hardware      │
└─────────────────────────────┘
```

## Quickstart (Local Dev)
```bash
./setup.sh
source venv/bin/activate
cp .env.example .env
python run.py
```
Visit `http://localhost:5000`.

## Raspberry Pi Setup (Summary)
```bash
sudo apt-get install -y python3-venv
./setup.sh
cp .env.example .env
# Edit .env: set GPIO_MODE=real, TIMEZONE, SNMP settings, etc.
python run.py
```
For a production service, see `docs/DEPLOY_RPI.md`.

## Mock Mode (No GPIO Required)
Set `GPIO_MODE=mock` in `.env` (default). The app will simulate sensor changes so the UI stays lively in demos.

## SocketIO (eventlet/gevent)
- Use SocketIO for real-time updates (better than long-polling/SSE under load).
- Production: prefer gevent + gevent-websocket worker.
- Optional: install eventlet and set `SOCKETIO_ASYNC_MODE=eventlet` if you prefer eventlet.

Example production run:
```bash
gunicorn -c gunicorn.conf.py wsgi:app
```

## Presence Detection (Privacy-First)
Presence is inferred only from your local network:
- Active ping sweep + ARP table mapping (no internet / GPS tracking)
- Optional SNMP client table ingest
- mDNS enrichment for device names

## ML Pipeline (High Level)
1. Capture events to SQLite and CSV.
2. Label sequences via `/ai` (or CLI tools).
3. Train model: `python app/services/ml/training/train_hardware_model.py`.
4. Inference runs in the app (feature flags planned).

See `docs/ML_PIPELINE.md` for details.

## Demo / Screenshots
- Seed demo data:
```bash
python scripts/seed_demo.py --reset
```
- Replay into a running server (requires `DEMO_MODE=1` in `.env`):
```bash
python scripts/replay_events.py --limit 80 --delay-ms 500
```

**Screenshots**
- `docs/screenshots/dashboard.png` (placeholder)
- `docs/screenshots/presence.png` (placeholder)
- `docs/screenshots/analysis.png` (placeholder)

To capture:
1) Run mock mode + seed demo
2) Trigger replay
3) Screenshot each page at 1440px width

## Known Limitations & Roadmap
- No advanced authentication (planned)
- ML inference is early-stage (training scripts exist)
- Hardware camera/audio drivers are stubbed

## Release Tagging
```bash
git tag -a v1.0.0 -m "v1.0.0"
git push origin v1.0.0
```

## Security / Secrets Hygiene
Do not commit `.env` or real device credentials. See `.env.example` and `SECURITY.md`.

## License
MIT. See `LICENSE`.
