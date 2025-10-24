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
import pandas as pd
from app import socketio

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@dataclass
class MotionSensor:
    """Class to hold sensor information"""

    pin: int
    name: str
    sensor_type: str = "motion"  # "motion" or "door"


class MotionSensorApp:
    def __init__(self, debounce_ms=100):

        self.socketio = socketio
        # Define sensors with GPIO pins, names, and types
        # 23,4,5 GPIO are broken
        self.sensors = [
            MotionSensor(2, "Living Room", "motion"),
            MotionSensor(6, "Hallway", "motion"),
            MotionSensor(18, "Door", "door"),
            MotionSensor(3, "Kitchen", "motion"),
        ]

        # Sensor states
        self.sensor_states = [False] * len(self.sensors)
        self.previous_states = [False] * len(self.sensors)
        self.last_activity = {}

        # Debounce tracking
        self.debounce_ms = debounce_ms
        self.last_change_time = {sensor.name: datetime.min for sensor in self.sensors}

        # Activity logging
        self.log_file = "sensor_activity.csv"
        self.setup_logging()

        # Setup GPIO
        self.setup_gpio()

        # Start monitoring thread
        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self.monitor_sensors, daemon=True)
        self.monitor_thread.start()

    def setup_logging(self):
        """Initialize CSV logging file with headers if it doesn't exist"""
        if not os.path.exists(self.log_file):
            with open(self.log_file, "w", newline="") as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(
                    [
                        "timestamp",
                        "sensor_name",
                        "sensor_type",
                        "gpio_pin",
                        "state",
                        "event",
                    ]
                )
            logger.info(f"Created new activity log file: {self.log_file}")

    def log_activity(self, sensor: MotionSensor, state: bool, event: str):
        """Log sensor activity to CSV file using system local time (Perth)"""
        try:
            # Use system local time (should be set to Perth timezone)
            local_time = datetime.now()

            with open(self.log_file, "a", newline="") as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(
                    [
                        local_time.isoformat(),
                        sensor.name,
                        sensor.sensor_type,
                        sensor.pin,
                        1 if state else 0,
                        event,
                    ]
                )
        except Exception as e:
            logger.error(f"Error logging activity: {e}")

    def setup_gpio(self):
        """Initialize GPIO pins for sensors"""
        try:
            # Set GPIO mode
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)

            # Initialize sensor pins based on sensor type
            for sensor in self.sensors:
                GPIO.setup(sensor.pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
                logger.info(
                    f"Initialized {sensor.name} ({sensor.sensor_type}) on GPIO pin {sensor.pin}"
                )

        except Exception as e:
            logger.error(f"Failed to setup GPIO: {e}")
            raise

    def read_sensors(self) -> bool:
        """Read all sensors with debounce and return True if any state changed"""
        state_changed = False

        for i, sensor in enumerate(self.sensors):
            try:
                raw_reading = GPIO.input(sensor.pin)

                # Convert raw GPIO reading into logical state
                if sensor.sensor_type == "door":
                    new_state = raw_reading == GPIO.HIGH  # HIGH = door open
                else:
                    new_state = raw_reading == GPIO.HIGH  # HIGH = motion detected

                # Debounce check
                if new_state != self.previous_states[i]:
                    now = datetime.now()
                    elapsed_ms = (
                        now - self.last_change_time[sensor.name]
                    ).total_seconds() * 1000
                    if elapsed_ms >= self.debounce_ms:
                        # Accept state change
                        self.previous_states[i] = new_state
                        self.sensor_states[i] = new_state
                        self.last_change_time[sensor.name] = now
                        state_changed = True
                        # Update last activity time (using system local time)
                        self.last_activity[sensor.name] = datetime.now()

                        # Determine event and whether to log
                        should_log = False

                        if sensor.sensor_type == "motion":
                            if new_state:  # Only log motion detection, not clearing
                                event = "Motion Detected"
                                should_log = True
                            else:
                                event = (
                                    "Motion Cleared"  # For socketio only, not logged
                                )
                        elif sensor.sensor_type == "door":
                            # Log both door open and close
                            event = "Door Opened" if new_state else "Door Closed"
                            should_log = True
                        else:
                            # For any other sensor types
                            event = "Active" if new_state else "Inactive"
                            should_log = True

                        logger.info(f"{event} - {sensor.name}")

                        # Only log to CSV if should_log is True
                        if should_log:
                            self.log_activity(sensor, new_state, event)

                        # Always emit real-time update via WebSocket
                        self.socketio.emit(
                            "sensor_update",
                            {
                                "sensor_name": sensor.name,
                                "sensor_index": i,
                                "sensor_type": sensor.sensor_type,
                                "value": 1 if new_state else 0,
                                "event": event,
                                "timestamp": datetime.now().isoformat(),
                                "all_sensors": self.get_sensor_data(),
                            },
                        )

            except Exception as e:
                logger.error(f"Error reading sensor {sensor.name}: {e}")

        return state_changed

    def get_sensor_data(self) -> List[Dict[str, Any]]:
        """Get current sensor data"""
        data = []

        for i, sensor in enumerate(self.sensors):
            last_activity = self.last_activity.get(sensor.name)

            # Determine status based on sensor type
            if sensor.sensor_type == "motion":
                status = "Motion Detected" if self.sensor_states[i] else "No Motion"
            elif sensor.sensor_type == "door":
                status = "Door Open" if self.sensor_states[i] else "Door Closed"
            else:
                status = "Active" if self.sensor_states[i] else "Inactive"

            data.append(
                {
                    "name": sensor.name,
                    "type": sensor.sensor_type,
                    "value": 1 if self.sensor_states[i] else 0,
                    "gpio_pin": sensor.pin,
                    "status": status,
                    "last_activity": (
                        last_activity.isoformat() if last_activity else None
                    ),
                }
            )

        return data

    def get_frequency_data(self, hours: int = 24, interval_minutes: int = 30) -> Dict[str, Any]:
        """Get frequency-based activity data for graphing using ISO timestamps"""
        try:
            if not os.path.exists(self.log_file):
                return {
                    "sensors": {},
                    "timestamps": [],
                    "interval_minutes": interval_minutes,
                    "total_intervals": 0,
                }

            local_now = datetime.now().astimezone()  # include timezone info
            cutoff_time = local_now - timedelta(hours=hours)

            df = pd.read_csv(self.log_file)
            df["timestamp"] = pd.to_datetime(
                df["timestamp"], format="ISO8601", errors="coerce", utc=True
            )

            # Convert to local timezone for consistency
            df["timestamp"] = df["timestamp"].dt.tz_convert(local_now.tzinfo)

            # Convert Python datetime to pandas Timestamp for comparison
            cutoff_time_pd = pd.Timestamp(cutoff_time)
            local_now_pd = pd.Timestamp(local_now)

            # Filter valid and recent entries
            df = df.dropna(subset=["timestamp"])
            df = df[df["timestamp"] >= cutoff_time_pd]
            df = df[df["state"] == 1]  # only activations

            # Define intervals
            current_time = cutoff_time
            time_intervals = []
            timestamps = []

            while current_time < local_now:
                interval_end = current_time + timedelta(minutes=interval_minutes)
                time_intervals.append(
                    {"start": current_time, "end": min(interval_end, local_now)}
                )
                # Use interval start time as the timestamp for this data point
                timestamps.append(current_time.isoformat())
                current_time = interval_end

            # Prepare output
            sensor_names = [sensor.name for sensor in self.sensors]
            frequency_data = {sensor: [] for sensor in sensor_names}

            for interval in time_intervals:
                for sensor_name in sensor_names:
                    # Convert interval times to pandas Timestamp for comparison
                    interval_start_pd = pd.Timestamp(interval["start"])
                    interval_end_pd = pd.Timestamp(interval["end"])

                    count = df[
                        (df["sensor_name"] == sensor_name)
                        & (df["timestamp"] >= interval_start_pd)
                        & (df["timestamp"] < interval_end_pd)
                    ].shape[0]

                    # Store just the count - timestamps are separate
                    frequency_data[sensor_name].append(count)

            return {
                "sensors": frequency_data,
                "timestamps": timestamps,  # Array of ISO timestamp strings
                "interval_minutes": interval_minutes,
                "total_intervals": len(time_intervals),
                "timezone": str(local_now.tzinfo),
            }

        except Exception as e:
            logger.error(f"Error getting frequency data: {e}")
            return {
                "sensors": {},
                "timestamps": [],
                "interval_minutes": interval_minutes,
                "total_intervals": 0,
            }

    def get_activity_data(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get activity data for basic activity log using system local time"""
        try:
            if not os.path.exists(self.log_file):
                return []

            # Calculate cutoff time using system local time
            local_now = datetime.now()
            cutoff_time = local_now - timedelta(hours=hours)

            df = pd.read_csv(self.log_file)
            # Convert timestamp to datetime
            df["timestamp"] = pd.to_datetime(df["timestamp"], format="ISO8601")

            # Filter by time range
            df = df[df["timestamp"] >= cutoff_time]

            # Convert timestamps to ISO strings for JSON serialization
            df["timestamp"] = df["timestamp"].dt.strftime("%Y-%m-%dT%H:%M:%S")

            # Convert to list of dictionaries for JSON serialization
            return df.to_dict("records")

        except Exception as e:
            logger.error(f"Error getting activity data: {e}")
            return []

    def monitor_sensors(self):
        """Background thread to continuously monitor sensors"""
        logger.info("Starting sensor monitoring thread...")

        while self.monitoring:
            try:
                self.read_sensors()
                time.sleep(0.1)  # Check sensors every 100ms
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
