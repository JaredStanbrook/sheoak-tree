"""
Hardware Strategies
Abstracts the physical interaction (GPIO, I2C, etc.) from the application logic.
"""

import logging
import random
from abc import ABC, abstractmethod
from datetime import datetime

logger = logging.getLogger(__name__)

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
        self.config = hw_model.configuration
        self.last_change = datetime.min
        self.current_value = None

    @abstractmethod
    def setup(self):
        """Configure pins/drivers"""
        pass

    @abstractmethod
    def read(self):
        """Return (value, formatted_string, unit) or None"""
        pass


# --- Concrete Strategies ---


class GpioBinaryStrategy(HardwareStrategy):
    """Input: Motion, Door, Button, Reed Switch"""

    def __init__(self, hw_model):
        super().__init__(hw_model)
        self.pin = self.config.get("pin")
        self.active_label = self.config.get("active_label", "Active")
        self.inactive_label = self.config.get("inactive_label", "Inactive")
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
                    label = self.active_label if is_active else self.inactive_label
                    return (new_val, label, "boolean")
        except Exception:
            pass
        return None


class GpioRelayStrategy(HardwareStrategy):
    """Output: Relays, Locks, Sirens"""

    def setup(self):
        pin = self.config.get("pin")
        if pin:
            GPIO.setup(pin, GPIO.OUT)
            # Default to OFF (Low) or ON (High) based on config
            initial = GPIO.HIGH if self.config.get("default_on") else GPIO.LOW
            GPIO.output(pin, initial)

    def read(self):
        # Output devices don't typically "read" unless we want status feedback
        return None

    def toggle(self):
        pin = self.config.get("pin")
        # In Mock/Sim, we can read the output state to toggle it
        curr = GPIO.input(pin)
        new_state = GPIO.LOW if curr == GPIO.HIGH else GPIO.HIGH
        GPIO.output(pin, new_state)
        return new_state


# --- Factory ---
class HardwareFactory:
    @staticmethod
    def create_strategy(hw_model):
        dt = hw_model.driver_type
        if dt == "gpio_binary" or dt == "dht_22" or dt == "i2c_generic":
            return GpioBinaryStrategy(hw_model)
        elif dt == "gpio_relay":
            return GpioRelayStrategy(hw_model)
        return None
