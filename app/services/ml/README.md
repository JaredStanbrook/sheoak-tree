# ML Module Notes

## Status
This module is not release-ready yet. It is being refactored from legacy file-based sequence storage
(CSV/JSON artifacts) to database-backed sequence persistence.

## What to Treat as Legacy
- `training/label_advanced.py`
- `training/label_mongo.py`
- Ad-hoc sequence exports and local artifacts used for experimentation

## Migration Expectations
- Keep legacy scripts working for developer experimentation.
- Avoid wiring new product features directly to legacy training internals.
- Build new sequence persistence and APIs behind explicit versioned boundaries.

## Entry Points (Current)
- Training: `python app/services/ml/training/train_sensor_model.py`
- Inference CLI: `python app/services/ml/inference/predict_cli.py --help`
