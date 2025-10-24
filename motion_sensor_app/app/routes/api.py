"""
API routes
"""

from flask import Flask, render_template, jsonify, send_file, send_from_directory, request, Blueprint, current_app
from flask_socketio import SocketIO, emit
import RPi.GPIO as GPIO
import json
import time
import threading
import logging
import csv
import os
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import List, Dict, Any

bp = Blueprint("api", __name__)


def get_processor():
    """Get or create processor instance"""
    if not hasattr(current_app, "_sequence_processor"):
        from app.services.label_advanced import SensorSequenceProcessor

        current_app._sequence_processor = SensorSequenceProcessor("sensor_activity.csv")
    return current_app._sequence_processor


@bp.route("/sensors")
def api_sensors():
    """API endpoint to get current sensor states"""
    return jsonify(
        {
            "sensors": current_app.motion_app.get_sensor_data(),
            "timestamp": datetime.now().isoformat(),
        }
    )


@bp.route("/activity/<int:hours>")
def api_activity(hours):
    """API endpoint to get activity data for activity log"""
    activity_data = current_app.motion_app.get_activity_data(hours)
    return jsonify(
        {
            "activity": activity_data,
            "timestamp": datetime.now().isoformat(),
            "hours": hours,
        }
    )


@bp.route("/frequency/<int:hours>/<int:interval>")
def api_frequency(hours, interval):
    """API endpoint to get frequency data for graphs"""
    frequency_data = current_app.motion_app.get_frequency_data(hours, interval)
    return jsonify(
        {
            "frequency": frequency_data,
            "timestamp": datetime.now().isoformat(),
            "hours": hours,
            "interval_minutes": interval,
        }
    )


@bp.route("/sequences/process", methods=["POST"])
def process_sequences():
    """Process sequences (full or incremental)"""
    try:
        processor = get_processor()
        data = request.json
        window_size = data.get("window_size", 60)
        sequence_gap_threshold = data.get("sequence_gap_threshold", 300)
        incremental = data.get("incremental", False)

        # Process sequences
        result = processor.process_sequences(
            window_size=window_size,
            sequence_gap_threshold=sequence_gap_threshold,
            incremental=incremental,
        )

        # Save state after processing
        processor.save_persistent_state()

        return jsonify(
            {
                "success": True,
                "result": result,
                "message": f'{"Incremental" if incremental else "Full"} processing completed',
                "timestamp": datetime.now().isoformat(),
            }
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@bp.route("/sequences/list")
def get_sequences_list():
    """Get paginated list of sequences"""
    try:
        processor = get_processor()
        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 20, type=int)

        # Load state if not already loaded
        try:
            processor.load_persistent_state()
        except:
            pass  # State might already be loaded

        result = processor.get_sequence_list(page=page, per_page=per_page)
        print(result)
        return jsonify(
            {"success": True, **result, "timestamp": datetime.now().isoformat()}
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@bp.route("/sequences/<int:sequence_id>")
def get_sequence_detail(sequence_id):
    """Get detailed information for a specific sequence"""
    try:
        processor = get_processor()
        # Load state if not already loaded
        try:
            processor.load_persistent_state()
        except:
            pass

        sequence = processor.get_sequence(sequence_id)

        if sequence:
            return jsonify(
                {
                    "success": True,
                    "sequence": sequence,
                    "timestamp": datetime.now().isoformat(),
                }
            )
        else:
            return (
                jsonify(
                    {"success": False, "error": f"Sequence {sequence_id} not found"}
                ),
                404,
            )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@bp.route("/sequences/<int:sequence_id>/label", methods=["PUT"])
def update_sequence_label(sequence_id):
    """Update label for a specific sequence"""
    try:
        processor = get_processor()
        data = request.json
        label = data.get("label")

        if not label:
            return jsonify({"success": False, "error": "Label is required"}), 400

        # Load state if not already loaded
        try:
            processor.load_persistent_state()
        except:
            pass

        success = processor.update_sequence_label(sequence_id, label)

        if success:
            processor.save_persistent_state()
            return jsonify(
                {
                    "success": True,
                    "message": f'Label updated to "{label}" for sequence {sequence_id}',
                    "timestamp": datetime.now().isoformat(),
                }
            )
        else:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": f"Failed to update label for sequence {sequence_id}",
                    }
                ),
                400,
            )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@bp.route("/sequences/statistics")
def get_label_statistics():
    """Get label statistics"""
    try:
        processor = get_processor()
        # Load state if not already loaded
        try:
            processor.load_persistent_state()
        except:
            pass

        stats = processor.get_label_statistics()

        return jsonify(
            {
                "success": True,
                "statistics": stats,
                "timestamp": datetime.now().isoformat(),
            }
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@bp.route("/sequences/state/load", methods=["POST"])
def load_processor_state():
    """Load processor state"""
    try:
        processor = get_processor()
        processor.load_persistent_state()
        stats = processor.get_label_statistics()

        return jsonify(
            {
                "success": True,
                "message": "State loaded successfully",
                "statistics": stats,
                "timestamp": datetime.now().isoformat(),
            }
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# app/routes/api.py
@bp.route("/health")
def health_check():
    """Health check endpoint"""
    health_status = {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "services": {},
    }

    # Check motion app
    if hasattr(current_app, "motion_app") and current_app.motion_app:
        try:
            current_app.motion_app.get_sensor_data()
            health_status["services"]["motion_sensor"] = "operational"
        except Exception as e:
            health_status["services"]["motion_sensor"] = f"error: {str(e)}"
            health_status["status"] = "degraded"
    else:
        health_status["services"]["motion_sensor"] = "not_initialized"
        health_status["status"] = "degraded"

    status_code = 200 if health_status["status"] == "healthy" else 503
    return jsonify(health_status), status_code
