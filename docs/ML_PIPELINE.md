# ML Pipeline

## Overview
The ML pipeline learns from sequences of hardware events to classify activity patterns.

## Steps
1. Data capture: hardware events stored in SQLite and CSV logs.
2. Sequence generation: events bucketed into windows (see training scripts).
3. Labeling: via `/ai` UI or CLI helpers.
4. Training: `python app/services/ml/training/train_hardware_model.py`.
5. Evaluation: metrics + artifacts saved to disk.

## Files
- `app/services/ml/training/train_hardware_model.py`
- `app/services/ml/training/label_helper.py`
- `app/services/ml/training/label_mongo.py`

## Notes
- Keep labels consistent to avoid model drift.
- Store generated artifacts outside git (ignored by `.gitignore`).
