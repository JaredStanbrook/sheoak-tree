PYTHON?=python

install:
	$(PYTHON) -m pip install -r requirements.txt
	$(PYTHON) -m pip install -r requirements-dev.txt

run:
	$(PYTHON) run.py

dev: run

lint:
	ruff check .

format:
	ruff format .

format-check:
	ruff format --check .
	black --check .

test:
	pytest

seed-demo:
	$(PYTHON) scripts/seed_demo.py --reset
