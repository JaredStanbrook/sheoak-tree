# Repository Guidelines

## Project Structure & Module Organization
- `app/` holds the Flask application: routes (Blueprints), services (presence, sensors, ML), templates, and static assets.
- `tests/` contains unit and hardware tests (pytest discovery uses `test_*.py` or `*_test.py`).
- `migrations/` stores Alembic migrations for the SQLite database.
- `infra/` contains infrastructure scripts; `setup.sh` bootstraps the local environment.
- Entry points: `run.py` (app) and `config.py` (configuration defaults).

## Build, Test, and Development Commands
- `./setup.sh` — create virtualenv, install dependencies, and run DB migrations.
- `source venv/bin/activate` — activate the local Python environment.
- `python run.py` — start the Flask app at `http://localhost:5000`. (Primary run command used by this repo.)
- `python app/services/ml/training/train_hardware_model.py` — train the ML model artifacts.

## Coding Style & Naming Conventions
- Python 3.8+ target; keep code compatible with `py38`.
- Linting uses Ruff with `E`, `F`, `B`, `I` rules; max line length is 100 and `E501` is ignored.
- Imports should group standard, third-party, then first-party (`app`, `config`).
- Prefer clear, descriptive names for sensors/hardware classes (e.g., `MotionSensor`, `DoorContact`).

## Testing Guidelines
- Framework: `pytest` with `-v` default options.
- Run all tests: `pytest` or `pytest -v`.
- Coverage: `pytest --cov` (pytest-cov is available in requirements).
- Keep test names aligned with discovery patterns: `test_*.py` or `*_test.py`.

## Verification
- After every file modification, run: `ruff check . --fix`.
- Then run: `ruff format .` to maintain consistent style.
- If any lint errors remain that cannot be auto-fixed, stop and report them.
- Before marking a task as complete, you must run `pytest`. If tests fail, attempt fixes and re-run tests up to 3 times before asking for help.

## Commit & Pull Request Guidelines
- Commit messages in history are short, imperative sentences (e.g., “Refactors presence monitor…”).
- Keep commits scoped and describe behavior changes, not just files.
- PRs should include: a concise summary, testing notes (commands run), and screenshots for UI changes.
- If modifying hardware interactions, note whether you tested on Raspberry Pi or in MockGPIO mode.

## Configuration & Security Tips
- Local config: create a `.env` file (e.g., `FLASK_ENV=development`, `SNMP_TARGET_IP=...`).
- Avoid committing secrets; keep credentials in `.env` or environment variables.
- Network scanning uses SNMP/ARP; document any IP ranges or credentials you touch.
