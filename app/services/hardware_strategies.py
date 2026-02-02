"""
Hardware Strategies
Abstracts the physical interaction (GPIO, I2C, etc.) from the application logic.
Supports: Binary sensors, Relays, Environmental sensors, Audio, and Cameras
"""

import logging
import os
import random
from abc import ABC, abstractmethod
from datetime import datetime

logger = logging.getLogger(__name__)

# ============================================================
# UI CONFIGURATION DEFAULTS
# ============================================================
HARDWARE_UI_DEFAULTS = {
    "relay": {
        "inactive_icon": "power-off",
        "active_icon": "power",
        "inactive_label": "Off",
        "active_label": "On",
        "color_on": "status-active",
        "color_off": "status-inactive",
    },
    "contact_sensor": {
        "inactive_icon": "rows-2",
        "active_icon": "rectangle-horizontal",
        "inactive_label": "Secure",
        "active_label": "Open",
        "color_on": "status-warning",
        "color_off": "status-safe",
    },
    "motion_sensor": {
        "inactive_icon": "eye-off",
        "active_icon": "eye",
        "inactive_label": "No Motion",
        "active_label": "Motion Detected",
        "color_on": "status-danger",
        "color_off": "status-safe",
    },
    "temperature_sensor": {
        "inactive_icon": "thermometer",
        "active_icon": "thermometer",
        "inactive_label": "Normal",
        "active_label": "Reading",
        "color_on": "status-info",
        "color_off": "status-inactive",
    },
    "humidity_sensor": {
        "inactive_icon": "droplets",
        "active_icon": "droplets",
        "inactive_label": "Normal",
        "active_label": "Reading",
        "color_on": "status-info",
        "color_off": "status-inactive",
    },
    "microphone": {
        "inactive_icon": "mic-off",
        "active_icon": "mic",
        "inactive_label": "Quiet",
        "active_label": "Audio Detected",
        "color_on": "status-warning",
        "color_off": "status-safe",
    },
    "speaker": {
        "inactive_icon": "volume-x",
        "active_icon": "volume-2",
        "inactive_label": "Silent",
        "active_label": "Playing",
        "color_on": "status-active",
        "color_off": "status-inactive",
    },
    "camera": {
        "inactive_icon": "camera-off",
        "active_icon": "camera",
        "inactive_label": "Idle",
        "active_label": "Recording",
        "color_on": "status-danger",
        "color_off": "status-inactive",
    },
    "__unknown__": {
        "inactive_icon": "help-circle",
        "active_icon": "help-circle",
        "inactive_label": "Unknown",
        "active_label": "Unknown",
        "color_on": "status-warning",
        "color_off": "status-inactive",
    },
}

# ============================================================
# GPIO WRAPPER
# ============================================================


class MockGPIO:
    BCM = "BCM"
    IN = "IN"
    OUT = "OUT"
    HIGH = 1
    LOW = 0
    PUD_UP = "PUD_UP"
    _pin_states = {}
    _active_pins = []

    @staticmethod
    def setmode(mode):
        pass

    @staticmethod
    def setwarnings(flag):
        pass

    @staticmethod
    def cleanup():
        pass

    @classmethod
    def setup(cls, pin, mode, pull_up_down=None):
        if pin not in cls._active_pins:
            cls._active_pins.append(pin)
            cls._pin_states[pin] = 0

    @classmethod
    def input(cls, pin):
        # Randomly toggle inputs for simulation
        if pin in cls._active_pins:
            if random.random() < 0.01:  # 1% chance to toggle
                cls._pin_states[pin] = 1 if cls._pin_states.get(pin, 0) == 0 else 0
        return cls._pin_states.get(pin, 0)

    @classmethod
    def output(cls, pin, state):
        cls._pin_states[pin] = state


gpio_mode = os.environ.get("GPIO_MODE", "mock").lower()

try:
    if gpio_mode == "mock":
        raise ImportError("GPIO_MODE=mock")
    import RPi.GPIO as GPIO
except (ImportError, RuntimeError) as exc:
    if gpio_mode == "real":
        logger.error("GPIO_MODE=real but GPIO init failed: %s", exc)
    else:
        logger.warning("RPi.GPIO not available (%s). Using Mock GPIO.", exc)
    GPIO = MockGPIO


# ============================================================
# ABSTRACT BASE STRATEGY
# ============================================================
class HardwareStrategy(ABC):
    def __init__(self, hw_model):
        self.id = hw_model.id
        self.name = hw_model.name
        self.type = hw_model.type
        self.driver_interface = hw_model.driver_interface
        self.config = hw_model.configuration or {}
        self.last_change = datetime.min
        self.current_value = None

    @abstractmethod
    def setup(self):
        """Configure pins/drivers"""
        pass

    @abstractmethod
    def read(self):
        """Return (value, unit) or None"""
        pass

    def get_snapshot(self, value=None):
        """
        Generates the full UI payload for this hardware.
        If value is not provided, uses the last known current_value.
        """
        current_val = value if value is not None else (self.current_value or 0.0)
        is_active = bool(current_val)

        defaults = HARDWARE_UI_DEFAULTS.get(self.type, HARDWARE_UI_DEFAULTS["__unknown__"])

        def resolve(key):
            return self.config.get(key, defaults.get(key))

        if is_active:
            ui_props = {
                "text": resolve("active_label"),
                "color": resolve("color_on"),
                "icon": resolve("active_icon"),
                "active": True,
            }
        else:
            ui_props = {
                "text": resolve("inactive_label"),
                "color": resolve("color_off"),
                "icon": resolve("inactive_icon"),
                "active": False,
            }

        return {
            "hardware_id": self.id,
            "name": self.name,
            "type": self.type,
            "value": current_val,
            "ui": ui_props,
            "timestamp": datetime.now().isoformat(),
        }


# ============================================================
# CONCRETE STRATEGIES
# ============================================================


class GpioBinaryStrategy(HardwareStrategy):
    """Input: Motion, Door, Button, Reed Switch"""

    def __init__(self, hw_model):
        super().__init__(hw_model)
        self.pin = self.config.get("pin")
        self.debounce_ms = self.config.get("debounce_ms", 300)
        self.current_value = 0.0

    def setup(self):
        if self.pin:
            GPIO.setup(self.pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

    def read(self):
        try:
            raw = GPIO.input(self.pin)
            is_active = raw == GPIO.HIGH
            new_val = 1.0 if is_active else 0.0

            if new_val != self.current_value:
                now = datetime.now()
                elapsed = (now - self.last_change).total_seconds() * 1000

                if elapsed > self.debounce_ms:
                    self.current_value = new_val
                    self.last_change = now
                    return (new_val, "boolean")
        except Exception:
            pass
        return None


class GpioRelayStrategy(HardwareStrategy):
    """Output: Relays, Locks, Sirens"""

    def __init__(self, hw_model):
        super().__init__(hw_model)
        self.pin = self.config.get("pin")

    def setup(self):
        if self.pin:
            GPIO.setup(self.pin, GPIO.OUT)
            initial = GPIO.HIGH if self.config.get("default_on") else GPIO.LOW
            GPIO.output(self.pin, initial)

    def read(self):
        return None

    def toggle(self):
        curr = GPIO.input(self.pin)
        new_state = GPIO.LOW if curr == GPIO.HIGH else GPIO.HIGH
        GPIO.output(self.pin, new_state)
        return new_state


class DHT22Strategy(HardwareStrategy):
    """DHT22 Temperature & Humidity Sensor"""

    def __init__(self, hw_model):
        super().__init__(hw_model)
        self.pin = self.config.get("pin")
        self.sensor_mode = self.config.get("mode", "temperature")  # "temperature" or "humidity"
        self.last_read = datetime.min
        self.read_interval = 2.0  # DHT22 needs 2s between reads

        # Try to import Adafruit DHT library
        try:
            import Adafruit_DHT

            self.dht_sensor = Adafruit_DHT.DHT22
            self.dht_lib = Adafruit_DHT
        except ImportError:
            logger.warning("Adafruit_DHT not found. Using mock data.")
            self.dht_sensor = None
            self.dht_lib = None

    def setup(self):
        # DHT22 doesn't need GPIO setup (library handles it)
        pass

    def read(self):
        now = datetime.now()
        elapsed = (now - self.last_read).total_seconds()

        if elapsed < self.read_interval:
            return None

        self.last_read = now

        if self.dht_lib:
            try:
                humidity, temperature = self.dht_lib.read_retry(self.dht_sensor, self.pin)

                if self.sensor_mode == "humidity" and humidity is not None:
                    self.current_value = humidity
                    return (humidity, "humidity")
                elif temperature is not None:
                    self.current_value = temperature
                    return (temperature, "celsius")
            except Exception as e:
                logger.error(f"DHT22 read error: {e}")
        else:
            # Mock data for testing
            if self.sensor_mode == "humidity":
                mock_value = 45.0 + random.uniform(-5, 5)
                self.current_value = mock_value
                return (mock_value, "humidity")
            else:
                mock_value = 22.0 + random.uniform(-2, 2)
                self.current_value = mock_value
                return (mock_value, "celsius")

        return None


class I2CGenericStrategy(HardwareStrategy):
    """Generic I2C Sensor (BMP280, BME280, etc.)"""

    def __init__(self, hw_model):
        super().__init__(hw_model)
        self.i2c_address = self.config.get("i2c_address", 0x76)
        self.sensor_type = self.config.get("sensor_type", "bmp280")
        self.read_mode = self.config.get("mode", "temperature")  # temperature, pressure, altitude
        self.last_read = datetime.min
        self.read_interval = 1.0

        # Try to import appropriate library
        try:
            if self.sensor_type == "bmp280":
                import adafruit_bmp280
                import board

                i2c = board.I2C()
                self.sensor = adafruit_bmp280.Adafruit_BMP280_I2C(i2c, address=self.i2c_address)
            elif self.sensor_type == "bme280":
                import adafruit_bme280
                import board

                i2c = board.I2C()
                self.sensor = adafruit_bme280.Adafruit_BME280_I2C(i2c, address=self.i2c_address)
            else:
                self.sensor = None
        except ImportError:
            logger.warning(f"I2C library for {self.sensor_type} not found. Using mock.")
            self.sensor = None

    def setup(self):
        pass

    def read(self):
        now = datetime.now()
        elapsed = (now - self.last_read).total_seconds()

        if elapsed < self.read_interval:
            return None

        self.last_read = now

        if self.sensor:
            try:
                if self.read_mode == "pressure":
                    value = self.sensor.pressure
                    unit = "pressure"
                elif self.read_mode == "altitude":
                    value = self.sensor.altitude
                    unit = "meters"
                else:  # temperature
                    value = self.sensor.temperature
                    unit = "celsius"

                self.current_value = value
                return (value, unit)
            except Exception as e:
                logger.error(f"I2C read error: {e}")
        else:
            # Mock data
            if self.read_mode == "pressure":
                mock_value = 1013.0 + random.uniform(-10, 10)
                self.current_value = mock_value
                return (mock_value, "pressure")
            elif self.read_mode == "altitude":
                mock_value = 100.0 + random.uniform(-5, 5)
                self.current_value = mock_value
                return (mock_value, "meters")
            else:
                mock_value = 22.0 + random.uniform(-2, 2)
                self.current_value = mock_value
                return (mock_value, "celsius")

        return None


class MicrophoneStrategy(HardwareStrategy):
    """USB Microphone or Analog Sound Sensor"""

    def __init__(self, hw_model):
        super().__init__(hw_model)
        self.device_index = self.config.get("device_index", 0)
        self.threshold_db = self.config.get("threshold_db", 50)
        self.last_read = datetime.min
        self.read_interval = 0.1

        # Try to import audio library
        try:
            import pyaudio

            self.pyaudio = pyaudio
            self.audio = pyaudio.PyAudio()
        except ImportError:
            logger.warning("PyAudio not found. Using mock audio data.")
            self.pyaudio = None
            self.audio = None

    def setup(self):
        pass

    def read(self):
        now = datetime.now()
        elapsed = (now - self.last_read).total_seconds()

        if elapsed < self.read_interval:
            return None

        self.last_read = now

        if self.audio:
            # TODO: Implement actual audio level detection
            # This would involve reading from the audio stream and calculating RMS
            pass

        # Mock data: simulate audio levels with occasional spikes
        base_level = 30.0
        if random.random() < 0.05:  # 5% chance of audio spike
            mock_value = base_level + random.uniform(20, 40)
        else:
            mock_value = base_level + random.uniform(-5, 5)

        self.current_value = mock_value
        is_above_threshold = mock_value > self.threshold_db

        # Only return when crossing threshold to avoid spam
        if is_above_threshold:
            return (mock_value, "decibels")

        return None


class SpeakerStrategy(HardwareStrategy):
    """Push-to-Talk Speaker or Audio Output"""

    def __init__(self, hw_model):
        super().__init__(hw_model)
        self.device_index = self.config.get("device_index", 0)
        self.current_value = 0.0

    def setup(self):
        pass

    def read(self):
        # Speakers don't read, they output
        return None

    def play_audio(self, audio_file_path):
        """Play an audio file through the speaker"""
        try:
            # TODO: Implement actual audio playback
            logger.info(f"Playing audio: {audio_file_path}")
            self.current_value = 1.0
            return True
        except Exception as e:
            logger.error(f"Audio playback error: {e}")
            return False


class CameraStrategy(HardwareStrategy):
    """USB Camera or Pi Camera Module"""

    def __init__(self, hw_model):
        super().__init__(hw_model)
        self.device_index = self.config.get("device_index", 0)
        self.resolution = self.config.get("resolution", "1920x1080")
        self.fps = self.config.get("fps", 30)
        self.camera = None

        # Try to import camera library
        try:
            from picamera2 import Picamera2

            self.camera_lib = Picamera2
        except ImportError:
            try:
                import cv2

                self.camera_lib = cv2
            except ImportError:
                logger.warning("No camera library found. Using mock.")
                self.camera_lib = None

    def setup(self):
        if self.camera_lib:
            try:
                # Initialize camera
                # Actual implementation would depend on which library is available
                pass
            except Exception as e:
                logger.error(f"Camera initialization error: {e}")

    def read(self):
        # Cameras don't continuously "read" like sensors
        # They capture on-demand
        return None

    def capture_frame(self):
        """Capture a single frame from the camera"""
        try:
            # TODO: Implement actual frame capture
            logger.info(f"Capturing frame from camera {self.name}")
            self.current_value = 1.0
            return True
        except Exception as e:
            logger.error(f"Frame capture error: {e}")
            return False


# ============================================================
# FACTORY
# ============================================================
class HardwareFactory:
    @staticmethod
    def create_strategy(hw_model):
        """
        Maps driver_interface to appropriate strategy class.
        """
        strategy_map = {
            "gpio_binary": GpioBinaryStrategy,
            "gpio_relay": GpioRelayStrategy,
            "dht_22": DHT22Strategy,
            "i2c_generic": I2CGenericStrategy,
            "microphone": MicrophoneStrategy,
            "speaker": SpeakerStrategy,
            "camera": CameraStrategy,
        }

        strategy_class = strategy_map.get(hw_model.driver_interface)

        if strategy_class:
            return strategy_class(hw_model)

        logger.warning(f"Unknown driver interface: {hw_model.driver_interface}")
        return None
