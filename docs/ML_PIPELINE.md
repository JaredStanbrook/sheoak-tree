# ML Pipeline

## Current Status
The ML module is under active redesign. Legacy sequence workflows were CSV/JSON-heavy and are being
migrated toward database-backed sequence storage and service boundaries.

The web workbench is intentionally disabled by default and replaced with a roadmap page (`/ai`).
Set `AI_WORKBENCH_ENABLED=1` only when working on the migration branch.

## Today (What Still Exists)
1. Event data is captured in SQLite by the core app.
2. Legacy sequence labeling/training scripts still exist under `app/services/ml/training/`.
3. Inference CLI tooling exists under `app/services/ml/inference/`.
4. Model artifacts currently write to local files in `app/services/ml/artifacts/`.

## Migration Direction
1. Replace CSV/JSON sequence persistence with database-backed sequence records.
2. Isolate data prep, labeling, and training into clear service modules.
3. Define stable dataset contracts for reproducible training and evaluation.
4. Re-enable the `/ai` workbench after new APIs and tests are complete.

## Relevant Paths
- `app/services/ml/training/train_sensor_model.py`
- `app/services/ml/training/label_advanced.py`
- `app/services/ml/training/label_mongo.py`
- `app/services/ml/inference/predict_cli.py`
- `app/services/ml/artifacts/`

## Guardrails During Migration
- Do not add new feature dependencies on legacy CSV sequence files.
- Keep training scripts runnable in isolation from web request handlers.
- Prefer additive schema changes and explicit migration notes in `docs/`.
