VENV ?= venv
PYTHON ?= $(VENV)/bin/python
RUFF ?= $(VENV)/bin/ruff
PYTEST ?= $(VENV)/bin/pytest

.PHONY: setup run lint format test check train seed replay gpio-usage

setup:
	./setup.sh

run:
	$(PYTHON) run.py

lint:
	$(RUFF) check . --fix

format:
	$(RUFF) format .

test:
	$(PYTEST)

check: lint format test

train:
	$(PYTHON) app/services/ml/training/train_sensor_model.py

seed:
	$(PYTHON) scripts/seed_demo.py --reset

replay:
	$(PYTHON) scripts/replay_events.py --limit 80 --delay-ms 500

gpio-usage:
	$(PYTHON) scripts/detect_gpio_usage.py
