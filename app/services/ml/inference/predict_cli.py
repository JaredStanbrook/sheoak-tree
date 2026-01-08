#!/usr/bin/env python3
"""
CLI to load trained models and predict labels for hardware sequences.

Usage examples:
  python predict_cli.py --model rf --model-path random_forest_model.pkl --encoder-path label_encoder.pkl --input sequences.json
  python predict_cli.py --model xgb --input single_sequence.json

The script replicates the feature extraction used by the trainer so it can predict
for arbitrary sequence dictionaries.
"""

import argparse
import json
import os
import sys
from datetime import datetime

import joblib
import numpy as np
import pandas as pd


def extract_features(sequence):
    """Replicate the feature extraction from hardwaresequenceTrainer.

    Args:
        sequence: dict representing a single sequence

    Returns:
        dict of numeric features
    """
    features = {}

    features["duration_minutes"] = sequence.get("duration_minutes", 0)
    features["time_since_last_seq_hours"] = sequence.get("time_since_last_seq_hours", 0)
    features["window_count"] = sequence.get("window_count", 0)
    raw_events = sequence.get("raw_events", []) or []
    features["total_events"] = len(raw_events)

    # Time-based
    start_time = (
        datetime.fromisoformat(sequence["start_time"]) if sequence.get("start_time") else None
    )
    if start_time:
        features["hour_of_day"] = start_time.hour
        features["day_of_week"] = start_time.weekday()
        features["is_night"] = 1 if (start_time.hour >= 22 or start_time.hour <= 6) else 0
        features["is_weekend"] = 1 if start_time.weekday() >= 5 else 0
    else:
        features["hour_of_day"] = 0
        features["day_of_week"] = 0
        features["is_night"] = 0
        features["is_weekend"] = 0

    # Event-based
    if raw_events:
        hardware_counts = {}
        hardware_types = {}
        motion_detected = motion_cleared = 0
        door_opened = door_closed = 0

        for event in raw_events:
            hardware = event.get("hardware_name", "unknown")
            hardware_type = event.get("hardware_type", "unknown")
            hardware_counts[hardware] = hardware_counts.get(hardware, 0) + 1
            hardware_types[hardware_type] = hardware_types.get(hardware_type, 0) + 1

            ev = event.get("event", "")
            if ev == "Motion Detected":
                motion_detected += 1
            elif ev == "Motion Cleared":
                motion_cleared += 1
            elif ev == "Door Opened":
                door_opened += 1
            elif ev == "Door Closed":
                door_closed += 1

        features["motion_detected_count"] = motion_detected
        features["motion_cleared_count"] = motion_cleared
        features["door_opened_count"] = door_opened
        features["door_closed_count"] = door_closed

        features["unique_hardwares"] = len(hardware_counts)
        features["unique_hardware_types"] = len(hardware_types)
        features["max_hardware_activations"] = (
            max(hardware_counts.values()) if hardware_counts else 0
        )
        features["event_rate"] = len(raw_events) / max(features["duration_minutes"], 0.1)

        timestamps = [
            datetime.fromisoformat(e["timestamp"]) for e in raw_events if e.get("timestamp")
        ]
        if len(timestamps) > 1:
            time_diffs = [
                (timestamps[i + 1] - timestamps[i]).total_seconds()
                for i in range(len(timestamps) - 1)
            ]
            features["avg_time_between_events"] = float(np.mean(time_diffs))
            features["max_time_between_events"] = float(np.max(time_diffs))
            features["min_time_between_events"] = float(np.min(time_diffs))
            features["std_time_between_events"] = float(np.std(time_diffs))
        else:
            features["avg_time_between_events"] = 0.0
            features["max_time_between_events"] = 0.0
            features["min_time_between_events"] = 0.0
            features["std_time_between_events"] = 0.0

        state_changes = sum(
            1
            for i in range(len(raw_events) - 1)
            if raw_events[i].get("state") != raw_events[i + 1].get("state")
        )
        features["state_transitions"] = state_changes

        hardware_probs = np.array(list(hardware_counts.values())) / len(raw_events)
        features["hardware_diversity"] = float(
            -np.sum(hardware_probs * np.log2(hardware_probs + 1e-10))
        )
    else:
        # Defaults
        features.update(
            {
                "motion_detected_count": 0,
                "motion_cleared_count": 0,
                "door_opened_count": 0,
                "door_closed_count": 0,
                "unique_hardwares": 0,
                "unique_hardware_types": 0,
                "max_hardware_activations": 0,
                "event_rate": 0.0,
                "avg_time_between_events": 0.0,
                "max_time_between_events": 0.0,
                "min_time_between_events": 0.0,
                "std_time_between_events": 0.0,
                "state_transitions": 0,
                "hardware_diversity": 0.0,
            }
        )

    return features


def load_json_input(path):
    with open(path, "r") as f:
        data = json.load(f)

    # If file contains a list of sequences, return that; if it contains dict with 'sequences', use it
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "sequences" in data:
        return data["sequences"]
    # Otherwise assume it's a single sequence dict
    if isinstance(data, dict):
        return [data]
    raise ValueError("Unsupported JSON input format")


def main():
    parser = argparse.ArgumentParser(
        description="Predict labels for hardware sequences using saved models"
    )
    parser.add_argument("--model", choices=["rf", "xgb"], default="rf", help="Which model to use")
    parser.add_argument(
        "--model-path",
        default="random_forest_model.pkl",
        help="Path to Random Forest model (joblib)",
    )
    parser.add_argument(
        "--xgb-path", default="xgboost_model.pkl", help="Path to XGBoost model (joblib)"
    )
    parser.add_argument(
        "--encoder-path", default="label_encoder.pkl", help="Path to label encoder (joblib)"
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Path to input JSON (single sequence, list, or dataset with sequences key)",
    )
    parser.add_argument(
        "--sequence-id", type=int, help="Optional sequence_id to predict (if input contains many)"
    )
    parser.add_argument("--output-csv", help="Optional output CSV path to write predictions")

    args = parser.parse_args()

    # Load input
    sequences = load_json_input(args.input)

    # Optionally filter by sequence_id
    if args.sequence_id is not None:
        sequences = [s for s in sequences if s.get("sequence_id") == args.sequence_id]
        if not sequences:
            print(f"No sequence with id {args.sequence_id} found in input")
            sys.exit(1)

    # Load model and encoder
    model_path = args.model_path if args.model == "rf" else args.xgb_path
    if not os.path.exists(model_path):
        print(f"Model file not found: {model_path}")
        sys.exit(1)

    model = joblib.load(model_path)

    if not os.path.exists(args.encoder_path):
        print(f"Label encoder not found: {args.encoder_path}")
        sys.exit(1)
    encoder = joblib.load(args.encoder_path)

    results = []
    for seq in sequences:
        feat = extract_features(seq)
        X_new = pd.DataFrame([feat])

        # Reorder features to match model if possible
        if hasattr(model, "feature_names_in_"):
            expected = list(model.feature_names_in_)
            missing = [c for c in expected if c not in X_new.columns]
            for c in missing:
                X_new[c] = 0
            X_new = X_new[expected]

        # Predict
        try:
            pred = model.predict(X_new)[0]
            proba = model.predict_proba(X_new)[0]
        except Exception as e:
            print(f"Prediction failed for sequence {seq.get('sequence_id')}: {e}")
            continue

        # Map prediction to label name
        try:
            label = encoder.inverse_transform([pred])[0]
            proba_dict = {encoder.classes_[i]: float(prob) for i, prob in enumerate(proba)}
        except Exception:
            # Fallback if encoder isn't available or classes differ
            label = str(pred)
            proba_dict = {str(i): float(p) for i, p in enumerate(proba)}

        out = {
            "sequence_id": seq.get("sequence_id"),
            "predicted_label": label,
            "probabilities": proba_dict,
        }
        results.append(out)

        print(
            f"Sequence {out['sequence_id']}: {out['predicted_label']} (probs: {out['probabilities']})"
        )

    if args.output_csv:
        import csv

        with open(args.output_csv, "w", newline="") as f:
            writer = csv.writer(f)
            # header
            header = (
                ["sequence_id", "predicted_label"] + list(results[0]["probabilities"].keys())
                if results
                else ["sequence_id", "predicted_label"]
            )
            writer.writerow(header)
            for r in results:
                row = [r["sequence_id"], r["predicted_label"]] + [
                    r["probabilities"].get(k, 0) for k in header[2:]
                ]
                writer.writerow(row)
        print(f"Predictions saved to {args.output_csv}")


if __name__ == "__main__":
    main()
