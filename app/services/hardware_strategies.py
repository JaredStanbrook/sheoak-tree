"""
Hardware Strategies
Abstracts the physical interaction (GPIO, I2C, etc.) from the application logic.
"""

import logging
import random
from abc import ABC, abstractmethod
from datetime import datetime

logger = logging.getLogger(__name__)

# ============================================================
# UI CONFIGURATION DEFAULTS
# ============================================================
HARDWARE_UI_DEFAULTS = {
    "relay": {
        "inactiveIcon": "power-off",
        "activeIcon": "power",
        "inactiveLabel": "Off",
        "activeLabel": "On",
        "colorOn": "status-active",
        "colorOff": "status-inactive",
    },
    "contact_sensor": {
        "inactiveIcon": "rows-2",
        "activeIcon": "rectangle-horizontal",
        "inactiveLabel": "Secure",
        "activeLabel": "Open",
        "colorOn": "status-warning",
        "colorOff": "status-safe",
    },
    "motion_sensor": {
        "inactiveIcon": "eye-off",
        "activeIcon": "eye",
        "inactiveLabel": "No Motion",
        "activeLabel": "Motion Detected",
        "colorOn": "status-danger",
        "colorOff": "status-safe",
    },
    "__unknown__": {
        "inactiveIcon": "help-circle",
        "activeIcon": "help-circle",
        "inactiveLabel": "Unknown",
        "activeLabel": "Unknown",
        "colorOn": "status-warning",
        "colorOff": "status-inactive",
    },
}
# --- Universal GPIO Wrapper ---
try:
    import RPi.GPIO as GPIO
except (ImportError, RuntimeError):
    logger.warning("RPi.GPIO not found. Using Mock Hardware.")

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

    GPIO = MockGPIO


# --- Abstract Base Strategy ---
class HardwareStrategy(ABC):
    def __init__(self, hw_model):
        self.id = hw_model.id
        self.name = hw_model.name
        self.type = hw_model.type
        self.driver_interface = hw_model.driver_interface
        self.config = hw_model.configuration or {}  # Ensure dict
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
        # 1. Determine Value
        current_val = value if value is not None else (self.current_value or 0.0)
        is_active = bool(current_val)

        # 2. Get Type Defaults
        defaults = HARDWARE_UI_DEFAULTS.get(self.type, HARDWARE_UI_DEFAULTS["__unknown__"])

        # 3. Helper to resolve Config > Default
        def resolve(key):
            # Check hw.config first, then fallback to defaults
            return self.config.get(key, defaults.get(key))

        # 4. Build UI Properties
        if is_active:
            ui_props = {
                "text": resolve("activeLabel"),
                "color": resolve("colorOn"),
                "icon": resolve("activeIcon"),
                "active": True,
            }
        else:
            ui_props = {
                "text": resolve("inactiveLabel"),
                "color": resolve("colorOff"),
                "icon": resolve("inactiveIcon"),
                "active": False,
            }

        # 5. Return Unified Object
        return {
            "hardware_id": self.id,
            "name": self.name,
            "type": self.type,
            "value": current_val,
            "ui": ui_props,  # <--- The frontend just renders this directly
            "timestamp": datetime.now().isoformat(),
        }


# --- Concrete Strategies ---


class GpioBinaryStrategy(HardwareStrategy):
    """Input: Motion, Door, Button, Reed Switch"""

    def __init__(self, hw_model):
        super().__init__(hw_model)
        self.pin = self.config.get("pin")
        self.debounce_ms = self.config.get("debounce_ms", 300)
        self.current_value = 0.0  # Default to inactive

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
            # Default to OFF (Low) or ON (High) based on config
            initial = GPIO.HIGH if self.config.get("default_on") else GPIO.LOW
            GPIO.output(self.pin, initial)

    def read(self):
        # Output devices don't typically "read" unless we want status feedback
        return None

    def toggle(self):
        # In Mock/Sim, we can read the output state to toggle it
        curr = GPIO.input(self.pin)
        new_state = GPIO.LOW if curr == GPIO.HIGH else GPIO.HIGH
        GPIO.output(self.pin, new_state)
        return new_state


# --- Factory ---
class HardwareFactory:
    @staticmethod
    def create_strategy(hw_model):
        dt = hw_model.driver_interface
        if dt == "gpio_binary" or dt == "dht_22" or dt == "i2c_generic":
            return GpioBinaryStrategy(hw_model)
        elif dt == "gpio_relay":
            return GpioRelayStrategy(hw_model)
        return None
