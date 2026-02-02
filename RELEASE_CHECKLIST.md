# Release Checklist (v1.0.0)

## Repo Hygiene
- [x] Remove tracked secrets/local artifacts (.env, app/data/app.db, logs)
- [x] Add .env.example with safe placeholders
- [x] Ensure .gitignore covers logs/ and local DB artifacts
- [x] Confirm no secrets committed

## Configuration & App Wiring
- [x] Centralize config in app/config.py and update imports
- [x] Add required env vars (SECRET_KEY, DATABASE_URL, SOCKETIO_ASYNC_MODE, GPIO_MODE, TIMEZONE, etc.)
- [x] Add version constant (1.0.0) in a single place
- [x] Provide systemd service example for app + background jobs

## Real-Time & Reliability
- [x] Flask-SocketIO wired end-to-end (server + client + docs)
- [x] SSE fallback remains available
- [x] Presence scanning handles missing tools/timeouts with backoff
- [x] GPIO permission failures degrade to mock with clear logging
- [x] Logging is structured, rate-limited where needed, and configurable

## Demoability
- [x] scripts/seed_demo.py seeds realistic devices/events
- [x] scripts/replay_events.py can animate the UI (demo mode gated)
- [x] README includes demo instructions and screenshot guidance

## Packaging & DX
- [x] Makefile (install/dev/lint/format/test/run/seed-demo)
- [x] requirements-dev.txt and tool configs (ruff/black/mypy)
- [x] CI workflow runs lint/format/tests

## Documentation
- [x] README refreshed for portfolio release
- [x] LICENSE, CHANGELOG, RELEASE_NOTES, SECURITY, CONTRIBUTING, CODE_OF_CONDUCT
- [x] docs/ARCHITECTURE.md, docs/DEPLOY_RPI.md, docs/ML_PIPELINE.md, docs/TROUBLESHOOTING.md

