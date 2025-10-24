"""
Main routes
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
from app import socketio, logger


bp = Blueprint("main", __name__)


def require_motion_app(f):
    """Decorator to ensure motion_app is available"""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not hasattr(current_app, "motion_app") or current_app.motion_app is None:
            return jsonify({"error": "Motion sensor service not available"}), 503
        return f(*args, **kwargs)

    return decorated_function


@bp.route("/")
def index():
    """Main page"""
    return render_template("index.html")


@bp.route("/download/activity")
def download_activity():
    """Download complete activity log as CSV"""
    if os.path.exists(current_app.motion_app.log_file):
        return send_file(
            current_app.motion_app.log_file,
            as_attachment=True,
            download_name=f'sensor_activity_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv',
        )
    else:
        return jsonify({"error": "Activity log file not found"}), 404


@socketio.on("connect")
def handle_connect():
    """Handle client connection"""
    if not hasattr(current_app, "motion_app") or current_app.motion_app is None:
        logger.warning("Client connected but motion_app not available")
        emit("error", {"message": "Sensor service not available"})
        return False

    logger.info("Client connected")
    emit(
        "sensor_update",
        {
            "all_sensors": current_app.motion_app.get_sensor_data(),
            "timestamp": datetime.now().isoformat(),
        },
    )

@socketio.on("disconnect")
def handle_disconnect():
    """Handle client disconnection"""
    logger.info("Client disconnected")


@socketio.on("request_activity_data")
def handle_activity_request(data):
    """Handle request for activity data"""
    hours = data.get("hours", 24)
    activity_data = current_app.motion_app.get_activity_data(hours)
    emit(
        "activity_data",
        {
            "activity": activity_data,
            "hours": hours,
            "timestamp": datetime.now().isoformat(),
        },
    )


@socketio.on("request_frequency_data")
def handle_frequency_request(data):
    """Handle request for frequency data"""
    hours = data.get("hours", 24)
    interval = data.get("interval", 30)
    frequency_data = current_app.motion_app.get_frequency_data(hours, interval)
    emit(
        "frequency_data",
        {
            "frequency": frequency_data,
            "hours": hours,
            "interval": interval,
            "timestamp": datetime.now().isoformat(),
        },
    )
