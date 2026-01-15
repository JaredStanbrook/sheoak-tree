#!/usr/bin/env python3
"""
Motion Sensor Web App for Raspberry Pi
Live display of NC (Normally Closed) contact hardwares via web interface
 with persistent logging and frequency-based activity graphs in Perth timezone
HARDWARE WIRING CONFIGURATIONS:
1. All hardwares: NC (Normally Closed) contacts
   - Use internal pull-up resistors
   - With 1k Ohm resistor in series for noise reduction
   - HIGH = motion detected, LOW = no motion
"""

import csv
import logging
import os
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List

import RPi.GPIO as GPIO
from flask import (
    Flask,
    jsonify,
    render_template,
    request,
    send_file,
)
from flask_socketio import SocketIO, emit
from label_advanced import hardwaresequenceProcessor

# Try to import pandas for data processing
try:
    import pandas as pd

    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

if not PANDAS_AVAILABLE:
    logger.warning("pandas not available. Graphing features will be limited.")


@dataclass
class MotionSensor:
    """Class to hold hardware information"""

    pin: int
    name: str
    hardware_type: str = "motion"  # "motion" or "door"


# Flask app setup
app = Flask(__name__)
app.config["SECRET_KEY"] = "motion_hardware_secret_key_2024"
socketio = SocketIO(app, cors_allowed_origins="*", path="/sheoak/socket.io")


class MotionSensorWebApp:
    def __init__(self, socketio_instance, debounce_ms=100):
        self.socketio = socketio_instance
        # Define hardwares with GPIO pins, names, and types
        # 23,4,5 GPIO are broken
        self.hardwares = [
            MotionSensor(2, "Living Room", "motion"),
            MotionSensor(6, "Hallway", "motion"),
            MotionSensor(18, "Door", "door"),
            MotionSensor(3, "Kitchen", "motion"),
        ]

        # Sensor states
        self.hardware_states = [False] * len(self.hardwares)
        self.previous_states = [False] * len(self.hardwares)
        self.last_activity = {}

        # Debounce tracking
        self.debounce_ms = debounce_ms
        self.last_change_time = {hardware.name: datetime.min for hardware in self.hardwares}

        # Activity logging
        self.log_file = "hardware_activity.csv"
        self.setup_logging()

        # Setup GPIO
        self.setup_gpio()

        # Start monitoring thread
        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self.monitor_hardwares, daemon=True)
        self.monitor_thread.start()

    def setup_logging(self):
        """Initialize CSV logging file with headers if it doesn't exist"""
        if not os.path.exists(self.log_file):
            with open(self.log_file, "w", newline="") as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(
                    [
                        "timestamp",
                        "hardware_name",
                        "hardware_type",
                        "gpio_pin",
                        "state",
                        "event",
                    ]
                )
            logger.info(f"Created new activity log file: {self.log_file}")

    def log_activity(self, hardware: MotionSensor, state: bool, event: str):
        """Log hardware activity to CSV file using system local time (Perth)"""
        try:
            # Use system local time (should be set to Perth timezone)
            local_time = datetime.now()

            with open(self.log_file, "a", newline="") as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(
                    [
                        local_time.isoformat(),
                        hardware.name,
                        hardware.hardware_type,
                        hardware.pin,
                        1 if state else 0,
                        event,
                    ]
                )
        except Exception as e:
            logger.error(f"Error logging activity: {e}")

    def setup_gpio(self):
        """Initialize GPIO pins for hardwares"""
        try:
            # Set GPIO mode
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)

            # Initialize hardware pins based on hardware type
            for hardware in self.hardwares:
                GPIO.setup(hardware.pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
                logger.info(
                    f"Initialized {hardware.name} ({hardware.hardware_type}) on GPIO pin {hardware.pin}"
                )

        except Exception as e:
            logger.error(f"Failed to setup GPIO: {e}")
            raise

    def read_hardwares(self) -> bool:
        """Read all hardwares with debounce and return True if any state changed"""
        state_changed = False

        for i, hardware in enumerate(self.hardwares):
            try:
                raw_reading = GPIO.input(hardware.pin)

                # Convert raw GPIO reading into logical state
                if hardware.hardware_type == "door":
                    new_state = raw_reading == GPIO.HIGH  # HIGH = door open
                else:
                    new_state = raw_reading == GPIO.HIGH  # HIGH = motion detected

                # Debounce check
                if new_state != self.previous_states[i]:
                    now = datetime.now()
                    elapsed_ms = (now - self.last_change_time[hardware.name]).total_seconds() * 1000
                    if elapsed_ms >= self.debounce_ms:
                        # Accept state change
                        self.previous_states[i] = new_state
                        self.hardware_states[i] = new_state
                        self.last_change_time[hardware.name] = now
                        state_changed = True
                        # Update last activity time (using system local time)
                        self.last_activity[hardware.name] = datetime.now()

                        # Log + emit
                        event = (
                            "Motion Detected"
                            if hardware.hardware_type == "motion" and new_state
                            else (
                                "Motion Cleared"
                                if hardware.hardware_type == "motion"
                                else (
                                    "Door Opened"
                                    if hardware.hardware_type == "door" and new_state
                                    else "Door Closed"
                                )
                            )
                        )
                        logger.info(f"{event} - {hardware.name}")
                        self.log_activity(hardware, new_state, event)
                        # Emit real-time update via WebSocket
                        self.socketio.emit(
                            "hardware_update",
                            {
                                "hardware_name": hardware.name,
                                "hardware_index": i,
                                "hardware_type": hardware.hardware_type,
                                "value": 1 if new_state else 0,
                                "event": event,
                                "timestamp": datetime.now().isoformat(),
                                "all_hardwares": self.get_hardware_data(),
                            },
                        )

            except Exception as e:
                logger.error(f"Error reading hardware {hardware.name}: {e}")

        return state_changed

    def get_hardware_data(self) -> List[Dict[str, Any]]:
        """Get current hardware data"""
        data = []

        for i, hardware in enumerate(self.hardwares):
            last_activity = self.last_activity.get(hardware.name)

            # Determine status based on hardware type
            if hardware.hardware_type == "motion":
                status = "Motion Detected" if self.hardware_states[i] else "No Motion"
            elif hardware.hardware_type == "door":
                status = "Door Open" if self.hardware_states[i] else "Door Closed"
            else:
                status = "Active" if self.hardware_states[i] else "Inactive"

            data.append(
                {
                    "name": hardware.name,
                    "type": hardware.hardware_type,
                    "value": 1 if self.hardware_states[i] else 0,
                    "gpio_pin": hardware.pin,
                    "status": status,
                    "last_activity": (last_activity.isoformat() if last_activity else None),
                }
            )

        return data

    def get_frequency_data(self, hours: int = 24, interval_minutes: int = 30) -> Dict[str, Any]:
        """Get frequency-based activity data for graphing using system local time"""
        try:
            if not os.path.exists(self.log_file):
                return {
                    "hardwares": {},
                    "timestamps": [],
                    "interval_minutes": interval_minutes,
                }

            # Calculate time range using system local time
            local_now = datetime.now()
            cutoff_time = local_now - timedelta(hours=hours)

            # Read and process data
            activity_data = []

            if PANDAS_AVAILABLE:
                # Use pandas for efficient processing
                df = pd.read_csv(self.log_file)
                df["timestamp"] = pd.to_datetime(df["timestamp"])

                # Filter by time range
                df = df[df["timestamp"] >= cutoff_time]

                # Only count activation events (state = 1)
                df = df[df["state"] == 1]

                activity_data = df.to_dict("records")
            else:
                # Fallback: manual processing
                with open(self.log_file, "r") as csvfile:
                    reader = csv.DictReader(csvfile)
                    for row in reader:
                        try:
                            # Parse timestamp
                            timestamp = datetime.fromisoformat(
                                row["timestamp"].replace("Z", "+00:00")
                            )
                            if timestamp.tzinfo is not None:
                                # Convert timezone-aware to naive local time
                                timestamp = timestamp.replace(tzinfo=None)

                            # Only include recent data and activation events
                            if timestamp >= cutoff_time and int(row["state"]) == 1:
                                activity_data.append(
                                    {
                                        "timestamp": timestamp,
                                        "hardware_name": row["hardware_name"],
                                        "hardware_type": row["hardware_type"],
                                    }
                                )
                        except (ValueError, KeyError) as e:
                            logger.warning(f"Error parsing row: {e}")
                            continue

            # Create time intervals
            current_time = cutoff_time
            end_time = local_now
            time_intervals = []

            while current_time < end_time:
                interval_end = current_time + timedelta(minutes=interval_minutes)
                time_intervals.append(
                    {
                        "start": current_time,
                        "end": min(interval_end, end_time),
                        "label": current_time.strftime("%I:%M %p"),  # 12-hour format
                    }
                )
                current_time = interval_end

            # Count activity frequency for each hardware in each interval
            hardware_names = [hardware.name for hardware in self.hardwares]
            frequency_data = {hardware: [] for hardware in hardware_names}
            timestamps = []

            for interval in time_intervals:
                timestamps.append(interval["label"])

                # Count activations for each hardware in this interval
                for hardware_name in hardware_names:
                    count = 0
                    for event in activity_data:
                        event_time = event["timestamp"]
                        if (
                            interval["start"] <= event_time < interval["end"]
                            and event["hardware_name"] == hardware_name
                        ):
                            count += 1

                    frequency_data[hardware_name].append(count)

            return {
                "hardwares": frequency_data,
                "timestamps": timestamps,
                "interval_minutes": interval_minutes,
                "total_intervals": len(timestamps),
                "timezone": "Local Time (Perth)",
            }

        except Exception as e:
            logger.error(f"Error getting frequency data: {e}")
            return {
                "hardwares": {},
                "timestamps": [],
                "interval_minutes": interval_minutes,
            }

    def get_activity_data(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get activity data for basic activity log using system local time"""
        try:
            if not os.path.exists(self.log_file):
                return []

            # Calculate cutoff time using system local time
            local_now = datetime.now()
            cutoff_time = local_now - timedelta(hours=hours)

            if not PANDAS_AVAILABLE:
                # Fallback: read CSV manually and filter last N entries
                activity_data = []
                with open(self.log_file, "r") as csvfile:
                    reader = csv.DictReader(csvfile)
                    for row in reader:
                        try:
                            timestamp = datetime.fromisoformat(
                                row["timestamp"].replace("Z", "+00:00")
                            )
                            if timestamp.tzinfo is not None:
                                # Convert timezone-aware to naive local time
                                timestamp = timestamp.replace(tzinfo=None)

                            if timestamp >= cutoff_time:
                                activity_data.append(
                                    {
                                        "timestamp": timestamp.isoformat(),
                                        "hardware_name": row["hardware_name"],
                                        "hardware_type": row["hardware_type"],
                                        "gpio_pin": int(row["gpio_pin"]),
                                        "state": int(row["state"]),
                                        "event": row["event"],
                                    }
                                )
                        except (ValueError, KeyError):
                            continue

                # Sort by timestamp (newest first)
                activity_data.sort(key=lambda x: x["timestamp"], reverse=True)
                return activity_data[-1000:]  # Return last 1000 entries

            # Use pandas if available
            df = pd.read_csv(self.log_file)
            # Convert timestamp to datetime
            df["timestamp"] = pd.to_datetime(df["timestamp"])

            # Filter by time range
            df = df[df["timestamp"] >= cutoff_time]

            # Convert timestamps to ISO strings for JSON serialization
            df["timestamp"] = df["timestamp"].dt.strftime("%Y-%m-%dT%H:%M:%S")

            # Convert to list of dictionaries for JSON serialization
            return df.to_dict("records")

        except Exception as e:
            logger.error(f"Error getting activity data: {e}")
            return []

    def monitor_hardwares(self):
        """Background thread to continuously monitor hardwares"""
        logger.info("Starting hardware monitoring thread...")

        while self.monitoring:
            try:
                self.read_hardwares()
                time.sleep(0.1)  # Check hardwares every 100ms
            except Exception as e:
                logger.error(f"Error in monitoring thread: {e}")
                time.sleep(1)

    def cleanup(self):
        """Clean up GPIO resources"""
        try:
            self.monitoring = False
            GPIO.cleanup()
            logger.info("GPIO cleanup completed")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")


# Create global instance
hardware_monitor = MotionSensorWebApp(socketio)
processor = hardwaresequenceProcessor("hardware_activity.csv")


@app.route("/")
def index():
    """Main page"""
    return render_template("index.html")


@app.route("/api/hardwares")
def api_hardwares():
    """API endpoint to get current hardware states"""
    return jsonify(
        {
            "hardwares": hardware_monitor.get_hardware_data(),
            "timestamp": datetime.now().isoformat(),
        }
    )


@app.route("/api/activity/<int:hours>")
def api_activity(hours):
    """API endpoint to get activity data for activity log"""
    activity_data = hardware_monitor.get_activity_data(hours)
    return jsonify(
        {
            "activity": activity_data,
            "timestamp": datetime.now().isoformat(),
            "hours": hours,
        }
    )


@app.route("/api/frequency/<int:hours>/<int:interval>")
def api_frequency(hours, interval):
    """API endpoint to get frequency data for graphs"""
    frequency_data = hardware_monitor.get_frequency_data(hours, interval)
    return jsonify(
        {
            "frequency": frequency_data,
            "timestamp": datetime.now().isoformat(),
            "hours": hours,
            "interval_minutes": interval,
        }
    )


@app.route("/download/activity")
def download_activity():
    """Download complete activity log as CSV"""
    if os.path.exists(hardware_monitor.log_file):
        return send_file(
            hardware_monitor.log_file,
            as_attachment=True,
            download_name=f"hardware_activity_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        )
    else:
        return jsonify({"error": "Activity log file not found"}), 404


# ============ SEQUENCE REVIEW ROUTES ============


@app.route("/api/sequences/process", methods=["POST"])
def process_sequences():
    """Process sequences (full or incremental)"""
    try:
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
                "message": f"{'Incremental' if incremental else 'Full'} processing completed",
                "timestamp": datetime.now().isoformat(),
            }
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/sequences/list")
def get_sequences_list():
    """Get paginated list of sequences"""
    try:
        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 20, type=int)

        # Load state if not already loaded
        try:
            processor.load_persistent_state()
        except:
            pass  # State might already be loaded

        result = processor.get_sequence_list(page=page, per_page=per_page)
        print(result)
        return jsonify({"success": True, **result, "timestamp": datetime.now().isoformat()})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/sequences/<int:sequence_id>")
def get_sequence_detail(sequence_id):
    """Get detailed information for a specific sequence"""
    try:
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
                jsonify({"success": False, "error": f"Sequence {sequence_id} not found"}),
                404,
            )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/sequences/<int:sequence_id>/label", methods=["PUT"])
def update_sequence_label(sequence_id):
    """Update label for a specific sequence"""
    try:
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


@app.route("/api/sequences/statistics")
def get_label_statistics():
    """Get label statistics"""
    try:
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


@app.route("/api/sequences/state/load", methods=["POST"])
def load_processor_state():
    """Load processor state"""
    try:
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


# ============ SOCKET.IO HANDLERS ============


@socketio.on("connect")
def handle_connect():
    """Handle client connection"""
    logger.info("Client connected")
    emit(
        "hardware_update",
        {
            "all_hardwares": hardware_monitor.get_hardware_data(),
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
    activity_data = hardware_monitor.get_activity_data(hours)
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
    frequency_data = hardware_monitor.get_frequency_data(hours, interval)
    emit(
        "frequency_data",
        {
            "frequency": frequency_data,
            "hours": hours,
            "interval": interval,
            "timestamp": datetime.now().isoformat(),
        },
    )


# HTML Template (embedded for simplicity)
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Motion Sensor Monitor</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.2/socket.io.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/3.9.1/chart.min.js"></script>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #1e3c72, #2a5298);
            color: white;
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            max-width: 1400px;
            margin: 0 auto;
        }
        .header {
            text-align: center;
            margin-bottom: 40px;
        }
        .header h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }
        .status-indicator {
            display: inline-block;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            margin-left: 10px;
            animation: pulse 2s infinite;
        }
        .status-indicator.connected {
            background-color: #4CAF50;
        }
        .status-indicator.disconnected {
            background-color: #f44336;
        }
        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.5; }
            100% { opacity: 1; }
        }
        .controls {
            text-align: center;
            margin-bottom: 30px;
        }
        .tab-buttons {
            display: inline-flex;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 25px;
            padding: 5px;
            margin-bottom: 20px;
        }
        .tab-button {
            padding: 10px 20px;
            background: none;
            border: none;
            color: white;
            border-radius: 20px;
            cursor: pointer;
            transition: all 0.3s ease;
            font-size: 14px;
            margin: 0 5px;
        }
        .tab-button.active {
            background: rgba(255, 255, 255, 0.2);
            box-shadow: 0 2px 10px rgba(0,0,0,0.3);
        }
        .download-btn, .action-btn {
            background: rgba(76, 175, 80, 0.2);
            border: 1px solid #4CAF50;
            color: white;
            padding: 10px 20px;
            border-radius: 20px;
            text-decoration: none;
            display: inline-block;
            margin-left: 20px;
            transition: all 0.3s ease;
            cursor: pointer;
            font-size: 14px;
        }
        .download-btn:hover, .action-btn:hover {
            background: rgba(76, 175, 80, 0.4);
            transform: translateY(-2px);
        }
        .action-btn.secondary {
            background: rgba(33, 150, 243, 0.2);
            border-color: #2196F3;
        }
        .action-btn.secondary:hover {
            background: rgba(33, 150, 243, 0.4);
        }
        .action-btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }
        .tab-content {
            display: none;
        }
        .tab-content.active {
            display: block;
        }
        .hardwares-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .hardware-card {
            background: rgba(255, 255, 255, 0.1);
            border-radius: 15px;
            padding: 25px;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.2);
            transition: all 0.3s ease;
            position: relative;
            overflow: hidden;
        }
        .hardware-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 10px 30px rgba(0,0,0,0.3);
        }
        .hardware-card.active {
            background: rgba(255, 87, 51, 0.2);
            border-color: #ff5733;
            animation: hardware-alert 1s ease-in-out infinite alternate;
        }
        .hardware-card.door.active {
            background: rgba(255, 193, 7, 0.2);
            border-color: #ffc107;
        }
        @keyframes hardware-alert {
            0% { box-shadow: 0 0 20px rgba(255, 87, 51, 0.5); }
            100% { box-shadow: 0 0 40px rgba(255, 87, 51, 0.8); }
        }
        .hardware-name {
            font-size: 1.3em;
            font-weight: bold;
            margin-bottom: 10px;
            display: flex;
            align-items: center;
        }
        .hardware-icon {
            font-size: 1.5em;
            margin-right: 10px;
        }
        .hardware-status {
            font-size: 1.1em;
            font-weight: 600;
            margin-bottom: 8px;
        }
        .hardware-status.active {
            color: #ff5733;
        }
        .hardware-status.inactive {
            color: #4CAF50;
        }
        .hardware-status.door-open {
            color: #ffc107;
        }
        .hardware-details {
            font-size: 0.9em;
            opacity: 0.8;
            line-height: 1.4;
        }
        .chart-container {
            background: rgba(255, 255, 255, 0.1);
            border-radius: 15px;
            padding: 30px;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.2);
            margin-bottom: 30px;
            height: auto;
        }
        .chart-controls {
            margin-bottom: 20px;
            text-align: center;
            display: flex;
            flex-wrap: wrap;
            justify-content: center;
            align-items: center;
            gap: 15px;
        }
        .control-group {
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .control-group label {
            font-weight: 600;
            font-size: 0.9em;
        }
        .time-selector, .interval-selector {
            background: rgba(255, 255, 255, 0.1);
            border: 1px solid rgba(255, 255, 255, 0.3);
            color: white;
            padding: 8px 15px;
            border-radius: 10px;
            cursor: pointer;
            font-size: 14px;
        }
        .activity-log {
            background: rgba(255, 255, 255, 0.1);
            border-radius: 15px;
            padding: 30px;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.2);
            max-height: 400px;
            overflow-y: auto;
        }
        .log-entry {
            padding: 12px;
            margin-bottom: 10px;
            background: rgba(255, 255, 255, 0.05);
            border-radius: 8px;
            border-left: 4px solid #4CAF50;
            animation: fadeIn 0.5s ease-in;
        }
        .log-entry.motion {
            border-left-color: #ff5733;
        }
        .log-entry.door {
            border-left-color: #ffc107;
        }
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        .timestamp {
            font-size: 0.8em;
            opacity: 0.7;
            float: right;
        }
        #frequencyChart {
            max-height: 500px;
        }
        .chart-info {
            background: rgba(255, 255, 255, 0.05);
            border-radius: 8px;
            padding: 15px;
            margin-top: 15px;
            font-size: 0.9em;
            text-align: center;
            opacity: 0.8;
        }
        /* Review Tab Styles */
        .review-container {
            background: rgba(255, 255, 255, 0.1);
            border-radius: 15px;
            padding: 30px;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.2);
        }
        
        .processing-controls {
            display: flex;
            gap: 15px;
            margin-bottom: 30px;
            flex-wrap: wrap;
            align-items: center;
        }
        
        .processing-controls input {
            background: rgba(255, 255, 255, 0.1);
            border: 1px solid rgba(255, 255, 255, 0.3);
            color: white;
            padding: 8px 15px;
            border-radius: 10px;
            width: 120px;
        }
        
        .stats-card {
            background: rgba(255, 255, 255, 0.05);
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 20px;
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
        }
        
        .stat-item {
            text-align: center;
        }
        
        .stat-value {
            font-size: 2em;
            font-weight: bold;
            color: #4CAF50;
        }
        
        .stat-label {
            font-size: 0.9em;
            opacity: 0.8;
            margin-top: 5px;
        }
        
        .sequence-list {
            margin-top: 20px;
        }
        
        .sequence-item {
            background: rgba(255, 255, 255, 0.05);
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 15px;
            cursor: pointer;
            transition: all 0.3s ease;
            border: 1px solid rgba(255, 255, 255, 0.1);
        }
        
        .sequence-item:hover {
            background: rgba(255, 255, 255, 0.1);
            transform: translateX(5px);
        }
        
        .sequence-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
        }
        
        .sequence-id {
            font-size: 1.2em;
            font-weight: bold;
        }
        
        .sequence-label {
            padding: 5px 15px;
            border-radius: 15px;
            font-size: 0.9em;
            font-weight: 600;
        }
        
        .sequence-label.unlabeled {
            background: rgba(158, 158, 158, 0.3);
        }
        
        .sequence-label.labeled {
            background: rgba(76, 175, 80, 0.3);
        }
        
        .sequence-info {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 10px;
            font-size: 0.9em;
            opacity: 0.9;
        }
        
        .pagination {
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 10px;
            margin-top: 20px;
        }
        
        .pagination button {
            background: rgba(255, 255, 255, 0.1);
            border: 1px solid rgba(255, 255, 255, 0.3);
            color: white;
            padding: 8px 15px;
            border-radius: 10px;
            cursor: pointer;
            transition: all 0.3s ease;
        }
        
        .pagination button:hover:not(:disabled) {
            background: rgba(255, 255, 255, 0.2);
        }
        
        .pagination button:disabled {
            opacity: 0.3;
            cursor: not-allowed;
        }
        
        /* Modal Styles */
        .modal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.8);
            z-index: 1000;
            overflow-y: auto;
        }
        
        .modal.active {
            display: flex;
            align-items: center;
            justify-content: center;
        }
        
        .modal-content {
            background: linear-gradient(135deg, #1e3c72, #2a5298);
            border-radius: 15px;
            padding: 30px;
            max-width: 900px;
            width: 90%;
            max-height: 90vh;
            overflow-y: auto;
            border: 1px solid rgba(255, 255, 255, 0.2);
        }
        
        .modal-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
        }
        
        .modal-close {
            background: rgba(255, 255, 255, 0.1);
            border: none;
            color: white;
            font-size: 1.5em;
            cursor: pointer;
            padding: 5px 15px;
            border-radius: 10px;
        }
        
        .label-selector {
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
            margin: 20px 0;
        }
        
        .label-btn {
            padding: 10px 20px;
            border: 1px solid rgba(255, 255, 255, 0.3);
            background: rgba(255, 255, 255, 0.1);
            color: white;
            border-radius: 10px;
            cursor: pointer;
            transition: all 0.3s ease;
        }
        
        .label-btn:hover {
            background: rgba(255, 255, 255, 0.2);
        }
        
        .label-btn.selected {
            background: rgba(76, 175, 80, 0.4);
            border-color: #4CAF50;
        }
        
        .event-list {
            background: rgba(0, 0, 0, 0.2);
            border-radius: 10px;
            padding: 15px;
            max-height: 300px;
            overflow-y: auto;
        }
        
        .event-item {
            padding: 8px;
            margin-bottom: 5px;
            background: rgba(255, 255, 255, 0.05);
            border-radius: 5px;
            font-size: 0.9em;
        }
        
        .loading {
            text-align: center;
            padding: 20px;
            opacity: 0.7;
        }
        
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
        
        .spinner {
            display: inline-block;
            width: 20px;
            height: 20px;
            border: 3px solid rgba(255, 255, 255, 0.3);
            border-top-color: white;
            border-radius: 50%;
            animation: spin 1s linear infinite;
        }
        @media (max-width: 768px) {
            .hardwares-grid {
                grid-template-columns: 1fr;
            }
            .chart-controls {
                flex-direction: column;
                gap: 10px;
            }
            .processing-controls {
                flex-direction: column;
            }
            .sequence-info {
                grid-template-columns: 1fr;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Smart Sensor Monitor</h1>
            <p>Real-time motion detection and door monitoring system</p>
            <p><small>Local Time (Perth) • Frequency-Based Analysis</small></p>
            <div>
                Connection Status: <span id="connection-status">Connecting...</span>
                <span id="status-indicator" class="status-indicator disconnected"></span>
            </div>
        </div>
        
        <div class="controls">
            <div class="tab-buttons">
                <button class="tab-button active" onclick="switchTab('live')">Live Status</button>
                <button class="tab-button" onclick="switchTab('graphs')">Activity Frequency</button>
                <button class="tab-button" onclick="switchTab('log')">Activity Log</button>
                <button class="tab-button" onclick="switchTab('review')">Sequence Review</button>
            </div>
            <a href="/download/activity" class="download-btn">Download Full Log</a>
        </div>

        <div id="live-tab" class="tab-content active">
            <div class="hardwares-grid" id="hardwares-grid">
                <!-- Sensor cards will be populated by JavaScript -->
            </div>
        </div>

        <div id="graphs-tab" class="tab-content">
            <div class="chart-container">
                <div class="chart-controls">
                    <h3>Sensor Activity Frequency Analysis</h3>
                    <div class="control-group">
                        <label>Time Range:</label>
                        <select class="time-selector" id="timeRange" onchange="handleIntervalChange()">
                            <option value="6">Last 6 Hours</option>
                            <option value="12">Last 12 Hours</option>
                            <option value="24" selected>Last 24 Hours</option>
                            <option value="48">Last 2 Days</option>
                            <option value="168">Last Week</option>
                        </select>
                    </div>
                    <div class="control-group">
                        <label>Interval:</label>
                        <select class="interval-selector" id="intervalRange" onchange="handleIntervalChange()">
                            <option value="15">15 Minutes</option>
                            <option value="30" selected>30 Minutes</option>
                            <option value="60">1 Hour</option>
                            <option value="120">2 Hours</option>
                            <option value="240">4 Hours</option>
                        </select>
                    </div>
                </div>
                
                <canvas id="frequencyChart"></canvas>
                <div class="chart-info" id="chartInfo">
                    Loading frequency data...
                </div>
            </div>
        </div>

        <div id="log-tab" class="tab-content">
            <div class="activity-log">
                <h3>Recent Activity</h3>
                <div id="activity-list">
                    <p style="opacity: 0.6; text-align: center;">Waiting for hardware activity...</p>
                </div>
            </div>
        </div>
        
        <div id="review-tab" class="tab-content">
            <div class="review-container">
                <h2>Sequence Review & Labeling</h2>
                
                <div class="processing-controls">
                    <div class="control-group">
                        <label>Window Size (sec):</label>
                        <input type="number" id="windowSize" value="60" min="30" max="300">
                    </div>
                    <div class="control-group">
                        <label>Gap Threshold (sec):</label>
                        <input type="number" id="gapThreshold" value="300" min="60" max="1800">
                    </div>
                    <button class="action-btn" onclick="processSequences(false)" id="fullProcessBtn">
                        Full Process
                    </button>
                    <button class="action-btn secondary" onclick="processSequences(true)" id="incrementalProcessBtn">
                        Incremental Process
                    </button>
                    <button class="action-btn secondary" onclick="loadProcessorState()" id="loadStateBtn">
                        Load State
                    </button>
                </div>
                
                <div class="stats-card" id="statscard">
                    <div class="stat-item">
                        <div class="stat-value" id="totalSequences">-</div>
                        <div class="stat-label">Total Sequences</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-value" id="labeledSequences">-</div>
                        <div class="stat-label">Labeled</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-value" id="unlabeledSequences">-</div>
                        <div class="stat-label">Unlabeled</div>
                    </div>
                </div>
                
                <div class="sequence-list" id="sequenceList">
                    <div class="loading">Click "Load State" or process sequences to begin</div>
                </div>
                
                <div class="pagination" id="pagination" style="display: none;">
                    <button onclick="changePage(-1)" id="prevBtn">Previous</button>
                    <span id="pageInfo">Page 1 of 1</span>
                    <button onclick="changePage(1)" id="nextBtn">Next</button>
                </div>
            </div>
        </div>
    </div>

    <!-- Sequence Detail Modal -->
    <div class="modal" id="sequenceModal">
        <div class="modal-content">
            <div class="modal-header">
                <h2>Sequence Details</h2>
                <button class="modal-close" onclick="closeModal()">&times;</button>
            </div>
            <div id="sequenceDetail">
                <div class="loading">
                    <div class="spinner"></div> Loading sequence details...
                </div>
            </div>
        </div>
    </div>

    <script>
        // Initialize Socket.IO connection
        const socket = io({
            path: '/sheoak/socket.io'
        });
        let activityLog = [];
        let frequencyChart = null;
        const maxLogEntries = 100;

        // Sensor type icons
        const hardwareIcons = {
            'motion': '👁️',
            'door': '🚪',
            'active': '🟢',
            'motion_active': '🚨',
            'door_active': '🟡'
        };

        // Sensor colors for frequency chart
        const hardwareColors = {
            'Living Room': {
                border: 'rgb(255, 99, 132)',
                background: 'rgba(255, 99, 132, 0.1)'
            },
            'Hallway': {
                border: 'rgb(54, 162, 235)',
                background: 'rgba(54, 162, 235, 0.1)'
            },
            'Door': {
                border: 'rgb(255, 205, 86)',
                background: 'rgba(255, 205, 86, 0.1)'
            },
            'Kitchen': {
                border: 'rgb(75, 192, 192)',
                background: 'rgba(75, 192, 192, 0.1)'
            }
        };

        // Connection status handling
        socket.on('connect', function() {
            document.getElementById('connection-status').textContent = 'Connected';
            document.getElementById('status-indicator').className = 'status-indicator connected';
            
            // Request initial activity data
            socket.emit('request_activity_data', {hours: 24});
            
            // Request initial frequency data if on graphs tab
            if (document.getElementById('graphs-tab').classList.contains('active')) {
                requestFrequencyData();
            }
        });

        socket.on('disconnect', function() {
            document.getElementById('connection-status').textContent = 'Disconnected';
            document.getElementById('status-indicator').className = 'status-indicator disconnected';
        });

        // Handle hardware updates
        socket.on('hardware_update', function(data) {
            if (data.all_hardwares) {
                updateSensorGrid(data.all_hardwares);
            }
            if (data.hardware_name) {
                addToActivityLog(data);
                
                // Update frequency chart if currently viewing graphs
                if (document.getElementById('graphs-tab').classList.contains('active')) {
                    // Debounce chart updates to avoid too frequent refreshes
                    clearTimeout(window.chartUpdateTimeout);
                    window.chartUpdateTimeout = setTimeout(() => {
                        requestFrequencyData();
                    }, 2000);
                }
            }
        });

        // Handle activity data for basic log
        socket.on('activity_data', function(data) {
            // This is used for the activity log tab
            if (data.activity && data.activity.length > 0) {
                // Convert to our format and update log
                data.activity.forEach(entry => {
                    if (entry.state === 1) { // Only show activations in the log
                        const timestamp = new Date(entry.timestamp).toLocaleString('en-AU', {
                            timeZone: 'Australia/Perth',
                            hour12: true
                        });
                        
                        const logEntry = {
                            hardware: entry.hardware_name,
                            type: entry.hardware_type,
                            event: entry.event,
                            timestamp: timestamp,
                            isActive: true
                        };
                        
                        // Avoid duplicates
                        if (!activityLog.some(existing => 
                            existing.hardware === logEntry.hardware && 
                            existing.timestamp === logEntry.timestamp &&
                            existing.event === logEntry.event)) {
                            activityLog.unshift(logEntry);
                        }
                    }
                });
                
                // Limit log size and update display
                if (activityLog.length > maxLogEntries) {
                    activityLog = activityLog.slice(0, maxLogEntries);
                }
                updateActivityLog();
            }
        });

        // Handle frequency data for charts
        socket.on('frequency_data', function(data) {
            updateFrequencyChart(data.frequency);
        });

        function updateSensorGrid(hardwares) {
            const grid = document.getElementById('hardwares-grid');
            grid.innerHTML = '';
            
            hardwares.forEach((hardware, index) => {
                const card = document.createElement('div');
                const isActive = hardware.value === 1;
                const hardwareClass = hardware.type === 'door' ? 'door' : 'motion';
                
                card.className = `hardware-card ${hardwareClass} ${isActive ? 'active' : ''}`;
                
                const lastActivity = hardware.last_activity
                    ? new Date(hardware.last_activity).toLocaleString('en-AU', {
                        hour12: true
                    })
                    : 'No activity yet';
                
                let icon = hardwareIcons[hardware.type];
                if (isActive) {
                    icon = hardware.type === 'door' ? hardwareIcons['door_active'] : hardwareIcons['motion_active'];
                }
                
                let statusClass = 'inactive';
                if (hardware.type === 'door' && isActive) {
                    statusClass = 'door-open';
                } else if (isActive) {
                    statusClass = 'active';
                }
                
                card.innerHTML = `
                    <div class="hardware-name">
                        <span class="hardware-icon">${icon}</span>
                        ${hardware.name}
                    </div>
                    <div class="hardware-status ${statusClass}">
                        ${hardware.status}
                    </div>
                    <div class="hardware-details">
                        <div><strong>Type:</strong> ${hardware.type.charAt(0).toUpperCase() + hardware.type.slice(1)}</div>
                        <div><strong>GPIO Pin:</strong> ${hardware.gpio_pin}</div>
                        <div><strong>Last Activity:</strong> ${lastActivity}</div>
                    </div>
                `;
                
                grid.appendChild(card);
            });
        }

        function addToActivityLog(data) {
            const timestamp = new Date(data.timestamp).toLocaleString('en-AU', {
                hour12: true
            });
            
            const logEntry = {
                hardware: data.hardware_name,
                type: data.hardware_type,
                event: data.event,
                timestamp: timestamp,
                isActive: data.value === 1
            };
            
            // Add to beginning of log
            activityLog.unshift(logEntry);
            
            // Limit log size
            if (activityLog.length > maxLogEntries) {
                activityLog = activityLog.slice(0, maxLogEntries);
            }
            
            updateActivityLog();
        }

        function updateActivityLog() {
            const activityList = document.getElementById('activity-list');
            
            if (activityLog.length === 0) {
                activityList.innerHTML = '<p style="opacity: 0.6; text-align: center;">Waiting for hardware activity...</p>';
                return;
            }
            
            activityList.innerHTML = activityLog.map(entry => `
                <div class="log-entry ${entry.type}">
                    <strong>${entry.hardware}</strong>: ${entry.event}
                    <span class="timestamp">${entry.timestamp}</span>
                </div>
            `).join('');
        }

        function switchTab(tabName) {
            // Hide all tabs
            document.querySelectorAll('.tab-content').forEach(tab => {
                tab.classList.remove('active');
            });
            document.querySelectorAll('.tab-button').forEach(btn => {
                btn.classList.remove('active');
            });
            
            // Show selected tab
            document.getElementById(tabName + '-tab').classList.add('active');
            event.target.classList.add('active');
            
            // Initialize chart if switching to graphs tab
            if (tabName === 'graphs') {
                if (!frequencyChart) {
                    initializeFrequencyChart();
                }
                requestFrequencyData();
            }
        }

        function initializeFrequencyChart() {
            const ctx = document.getElementById('frequencyChart').getContext('2d');
            
            frequencyChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: [],
                    datasets: []
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        title: {
                            display: true,
                            text: 'Sensor Activity Frequency (Activations per Time Interval)',
                            color: 'white',
                            font: {
                                size: 16
                            }
                        },
                        legend: {
                            labels: {
                                color: 'white',
                                usePointStyle: true,
                                pointStyle: 'circle'
                            }
                        },
                        tooltip: {
                            backgroundColor: 'rgba(0, 0, 0, 0.8)',
                            titleColor: 'white',
                            bodyColor: 'white',
                            borderColor: 'white',
                            borderWidth: 1,
                            callbacks: {
                                label: function(context) {
                                    const activations = context.parsed.y;
                                    const hardware = context.dataset.label;
                                    return `${hardware}: ${activations} activation${activations !== 1 ? 's' : ''}`;
                                }
                            }
                        }
                    },
                    scales: {
                        x: {
                            title: {
                                display: true,
                                text: 'Time (Local Perth Time - 12 Hour Format)',
                                color: 'white'
                            },
                            ticks: {
                                color: 'white',
                                maxTicksLimit: 12,
                                autoSkip: true
                            },
                            grid: {
                                color: 'rgba(255,255,255,0.1)'
                            }
                        },
                        y: {
                            beginAtZero: true,
                            title: {
                                display: true,
                                text: 'Number of Activations',
                                color: 'white'
                            },
                            ticks: {
                                color: 'white',
                                stepSize: 1,
                                callback: function(value) {
                                    if (Number.isInteger(value)) {
                                        return value;
                                    }
                                }
                            },
                            grid: {
                                color: 'rgba(255,255,255,0.1)'
                            }
                        }
                    },
                    interaction: {
                        intersect: false,
                        mode: 'index'
                    },
                    elements: {
                        line: {
                            tension: 0.4
                        },
                        point: {
                            radius: 4,
                            hoverRadius: 8
                        }
                    }
                }
            });
        }

        function requestFrequencyData() {
            const hours = parseInt(document.getElementById('timeRange').value);
            const interval = parseInt(document.getElementById('intervalRange').value);
            
            socket.emit('request_frequency_data', {
                hours: hours,
                interval: interval
            });
        }

        function handleIntervalChange() {
            requestFrequencyData();
        }

        function updateFrequencyChart(frequencyData) {
            if (!frequencyChart || !frequencyData) return;
            
            const { hardwares, timestamps, interval_minutes, total_intervals } = frequencyData;
            
            // Create datasets for each hardware
            const datasets = Object.keys(hardwares).map(hardwareName => {
                const colorConfig = hardwareColors[hardwareName] || {
                    border: 'rgb(255, 255, 255)',
                    background: 'rgba(255, 255, 255, 0.1)'
                };
                
                return {
                    label: hardwareName,
                    data: hardwares[hardwareName],
                    borderColor: colorConfig.border,
                    backgroundColor: colorConfig.background,
                    tension: 0.4,
                    fill: false,
                    pointBackgroundColor: colorConfig.border,
                    pointBorderColor: 'white',
                    pointBorderWidth: 2,
                    pointRadius: 4,
                    pointHoverRadius: 8
                };
            });
            
            // Update chart
            frequencyChart.data.labels = timestamps;
            frequencyChart.data.datasets = datasets;
            frequencyChart.update('none'); // Skip animation for real-time updates
            
            // Update info card
            const totalActivations = Object.values(hardwares).reduce((total, hardwareData) => 
                total + hardwareData.reduce((sum, count) => sum + count, 0), 0);
            
            const mostActiveTime = findMostActiveTime(hardwares, timestamps);
            const mostActiveSensor = findMostActiveSensor(hardwares);
            
            document.getElementById('chartInfo').innerHTML = `
                <strong>Analysis Summary:</strong><br>
                Time Range: ${interval_minutes} minute intervals over ${total_intervals} periods<br>
                Total Activations: ${totalActivations}<br>
                Most Active Time: ${mostActiveTime}<br>
                Most Active Sensor: ${mostActiveSensor}<br>
                <em>Times shown in local Perth time (12-hour format)</em>
            `;
        }

        function findMostActiveTime(hardwares, timestamps) {
            if (!timestamps.length) return 'No data';
            
            const timeActivitySums = timestamps.map((time, index) => {
                const totalActivity = Object.values(hardwares).reduce((sum, hardwareData) => 
                    sum + (hardwareData[index] || 0), 0);
                return { time, activity: totalActivity };
            });
            
            const mostActive = timeActivitySums.reduce((max, current) => 
                current.activity > max.activity ? current : max);
            
            return mostActive.activity > 0 ? 
                `${mostActive.time} (${mostActive.activity} activations)` : 
                'No activity recorded';
        }

        function findMostActiveSensor(hardwares) {
            if (!Object.keys(hardwares).length) return 'No data';
            
            const hardwareTotals = Object.entries(hardwares).map(([name, data]) => ({
                name,
                total: data.reduce((sum, count) => sum + count, 0)
            }));
            
            const mostActive = hardwareTotals.reduce((max, current) => 
                current.total > max.total ? current : max);
            
            return mostActive.total > 0 ? 
                `${mostActive.name} (${mostActive.total} activations)` : 
                'No activity recorded';
        }
        // ============ REVIEW TAB FUNCTIONS ============
        
        async function processSequences(incremental) {
            const windowSize = parseInt(document.getElementById('windowSize').value);
            const gapThreshold = parseInt(document.getElementById('gapThreshold').value);
            const btn = incremental ? document.getElementById('incrementalProcessBtn') : document.getElementById('fullProcessBtn');
            
            btn.disabled = true;
            btn.textContent = incremental ? 'Processing...' : 'Processing...';
            
            try {
                const response = await fetch('/api/sequences/process', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        window_size: windowSize,
                        sequence_gap_threshold: gapThreshold,
                        incremental: incremental
                    })
                });
                
                const data = await response.json();
                
                if (data.success) {
                    alert(`Processing completed! Result: ${JSON.stringify(data.result)}`);
                    await loadStatistics();
                    await loadSequences(1);
                } else {
                    alert(`Error: ${data.error}`);
                }
            } catch (error) {
                alert(`Error processing sequences: ${error.message}`);
            } finally {
                btn.disabled = false;
                btn.textContent = incremental ? 'Incremental Process' : 'Full Process';
            }
        }
        
        async function loadProcessorState() {
            const btn = document.getElementById('loadStateBtn');
            btn.disabled = true;
            btn.textContent = 'Loading...';
            
            try {
                await loadStatistics();
                await loadSequences(1);
                alert('State loaded successfully!');
            } catch (error) {
                alert(`Error loading state: ${error.message}`);
            } finally {
                btn.disabled = false;
                btn.textContent = 'Load State';
            }
        }
        
        async function loadStatistics() {
            try {
                const response = await fetch('/api/sequences/statistics');
                const data = await response.json();

                if (data.success) {
                    const stats = data.statistics;
                    document.getElementById('totalSequences').textContent = stats.total_sequences || 0;
                    document.getElementById('labeledSequences').textContent = stats.labeled_sequences || 0;
                    document.getElementById('unlabeledSequences').textContent = stats.unlabeled_sequences || 0;
                }
            } catch (error) {
                console.error('Error loading statistics:', error);
            }
        }
        
        async function loadSequences(page) {
            currentPage = page;
            const listEl = document.getElementById('sequenceList');
            listEl.innerHTML = '<div class="loading"><div class="spinner"></div> Loading sequences...</div>';
            
            try {
                const response = await fetch(`/api/sequences/list?page=${page}&per_page=20`);
                const data = await response.json();
                
                if (data.success) {
                    displaySequences(data.sequences);
                    updatePagination(data.pagination);
                } else {
                    listEl.innerHTML = `<div class="loading">Error: ${data.error}</div>`;
                }
            } catch (error) {
                listEl.innerHTML = `<div class="loading">Error loading sequences: ${error.message}</div>`;
            }
        }
        
        function displaySequences(sequences) {
            const listEl = document.getElementById('sequenceList');
            
            if (sequences.length === 0) {
                listEl.innerHTML = '<div class="loading">No sequences found. Process data to create sequences.</div>';
                return;
            }
            
            listEl.innerHTML = sequences.map(seq => {
                const startTime = new Date(seq.start_time).toLocaleString('en-AU', {
                    timeZone: 'Australia/Perth',
                    hour12: true
                });
                const endTime = new Date(seq.end_time).toLocaleString('en-AU', {
                    timeZone: 'Australia/Perth',
                    hour12: true
                });
                
                const labelClass = seq.label ? 'labeled' : 'unlabeled';
                const labelText = seq.label || 'Not Labeled';
                
                return `
                    <div class="sequence-item" onclick="openSequenceModal(${seq.sequence_id})">
                        <div class="sequence-header">
                            <div class="sequence-id">Sequence #${seq.sequence_id}</div>
                            <div class="sequence-label ${labelClass}">${labelText}</div>
                        </div>
                        <div class="sequence-info">
                            <div><strong>Start:</strong> ${startTime}</div>
                            <div><strong>End:</strong> ${endTime}</div>
                            <div><strong>Duration:</strong> ${seq.duration_minutes.toFixed(1)} min</div>
                            <div><strong>Windows:</strong> ${seq.window_count}</div>
                            <div><strong>Gap:</strong> ${seq.time_since_last_seq_hours.toFixed(1)} hrs</div>
                        </div>
                    </div>
                `;
            }).join('');
        }
        
        function updatePagination(pagination) {
            const paginationEl = document.getElementById('pagination');
            const pageInfo = document.getElementById('pageInfo');
            const prevBtn = document.getElementById('prevBtn');
            const nextBtn = document.getElementById('nextBtn');
            
            if (pagination.total_pages > 1) {
                paginationEl.style.display = 'flex';
                pageInfo.textContent = `Page ${pagination.page} of ${pagination.total_pages}`;
                prevBtn.disabled = !pagination.has_prev;
                nextBtn.disabled = !pagination.has_next;
                totalPages = pagination.total_pages;
            } else {
                paginationEl.style.display = 'none';
            }
        }
        
        function changePage(direction) {
            const newPage = currentPage + direction;
            if (newPage >= 1 && newPage <= totalPages) {
                loadSequences(newPage);
            }
        }
        
        async function openSequenceModal(sequenceId) {
            currentSequenceId = sequenceId;
            const modal = document.getElementById('sequenceModal');
            const detailEl = document.getElementById('sequenceDetail');
            
            modal.classList.add('active');
            detailEl.innerHTML = '<div class="loading"><div class="spinner"></div> Loading sequence details...</div>';
            
            try {
                const response = await fetch(`/api/sequences/${sequenceId}`);
                const data = await response.json();
                
                if (data.success) {
                    displaySequenceDetail(data.sequence);
                } else {
                    detailEl.innerHTML = `<div class="loading">Error: ${data.error}</div>`;
                }
            } catch (error) {
                detailEl.innerHTML = `<div class="loading">Error loading sequence: ${error.message}</div>`;
            }
        }
        
        function displaySequenceDetail(seq) {
            const detailEl = document.getElementById('sequenceDetail');
            const startTime = new Date(seq.start_time).toLocaleString('en-AU', {
                timeZone: 'Australia/Perth',
                hour12: true
            });
            const endTime = new Date(seq.end_time).toLocaleString('en-AU', {
                timeZone: 'Australia/Perth',
                hour12: true
            });
            
            const labels = ['Ignore', 'Activity', 'Bathroom', 'Kitchen', 'Sleeping', 'Away'];
            
            detailEl.innerHTML = `
                <div>
                    <h3>Sequence #${seq.sequence_id}</h3>
                    <div class="sequence-info" style="margin: 20px 0;">
                        <div><strong>Start Time:</strong> ${startTime}</div>
                        <div><strong>End Time:</strong> ${endTime}</div>
                        <div><strong>Duration:</strong> ${seq.duration_minutes.toFixed(1)} minutes</div>
                        <div><strong>Windows:</strong> ${seq.window_count}</div>
                        <div><strong>Gap from Previous:</strong> ${seq.time_since_last_seq_hours.toFixed(1)} hours</div>
                        <div><strong>Current Label:</strong> ${seq.label || 'Not Labeled'}</div>
                    </div>
                    
                    <h4>Assign Label:</h4>
                    <div class="label-selector">
                        ${labels.map(label => `
                            <button class="label-btn ${seq.label === label ? 'selected' : ''}" 
                                    onclick="selectLabel('${label}')" 
                                    data-label="${label}">
                                ${label}
                            </button>
                        `).join('')}
                    </div>
                    
                    <button class="action-btn" onclick="saveLabel()" style="margin: 20px 0;">
                        Save Label
                    </button>
                    
                    <h4>Raw Events (${seq.raw_events.length}):</h4>
                    <div class="event-list">
                        ${seq.raw_events.map(event => {
                            const eventTime = new Date(event.timestamp).toLocaleString('en-AU', {
                                timeZone: 'Australia/Perth',
                                hour12: true,
                                hour: '2-digit',
                                minute: '2-digit',
                                second: '2-digit'
                            });
                            return `
                                <div class="event-item">
                                    <strong>${eventTime}</strong> - ${event.hardware_name}: ${event.event}
                                </div>
                            `;
                        }).join('')}
                    </div>
                </div>
            `;
        }
        
        function selectLabel(label) {
            document.querySelectorAll('.label-btn').forEach(btn => {
                btn.classList.remove('selected');
            });
            event.target.classList.add('selected');
        }
        
        async function saveLabel() {
            const selectedBtn = document.querySelector('.label-btn.selected');
            if (!selectedBtn) {
                alert('Please select a label');
                return;
            }
            
            const label = selectedBtn.dataset.label;
            
            try {
                const response = await fetch(`/api/sequences/${currentSequenceId}/label`, {
                    method: 'PUT',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({label: label})
                });
                
                const data = await response.json();
                
                if (data.success) {
                    alert('Label saved successfully!');
                    closeModal();
                    await loadStatistics();
                    await loadSequences(currentPage);
                } else {
                    alert(`Error: ${data.error}`);
                }
            } catch (error) {
                alert(`Error saving label: ${error.message}`);
            }
        }
        
        function closeModal() {
            document.getElementById('sequenceModal').classList.remove('active');
            currentSequenceId = null;
        }

        // Initial load
        fetch('/api/hardwares')
            .then(response => response.json())
            .then(data => updateSensorGrid(data.hardwares))
            .catch(error => console.error('Error loading hardwares:', error));
    </script>
</body>
</html>
"""

# Create templates directory and save template

os.makedirs("templates", exist_ok=True)
with open("templates/index.html", "w") as f:
    f.write(HTML_TEMPLATE)

if __name__ == "__main__":
    try:
        logger.info("Starting  Motion Sensor Web App with Frequency Analysis...")
        logger.info("New Features:")
        logger.info("- Frequency-based activity analysis with configurable time intervals")
        logger.info("- Perth timezone support with 12-hour time format")
        logger.info("-  graphing with activity summaries")
        logger.info("- Real-time chart updates")
        logger.info("Access the web interface at: http://[pi-ip-address]:5000")

        # Install required packages if not present
        if not PANDAS_AVAILABLE:
            logger.warning("pandas not found. Install with: pip install pandas")
            logger.warning("Frequency analysis will use fallback mode")

        # Run the Flask-SocketIO app
        socketio.run(app, host="0.0.0.0", port=5000, debug=False, allow_unsafe_werkzeug=True)

    except KeyboardInterrupt:
        logger.info("Shutting down web app...")
    except Exception as e:
        logger.error(f"Error running web app: {e}")
    finally:
        hardware_monitor.cleanup()
