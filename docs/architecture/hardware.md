# Hardware System Architecture

The hardware layer abstracts physical I/O (GPIO pins) into logical "Strategies." This allows the system to treat a Motion Sensor, a Door Contact, or a Relay identically from an architectural perspective.

## The Strategy Pattern

We do not write `GPIO.input(17)` directly in the business logic. Instead, we use **Strategies**.

### `HardwareStrategy` (Abstract Base)
Defines the contract:
* `setup()`: Configure the pin direction/pull-up.
* `read()`: Return the current normalized value (0.0 to 1.0) and unit.
* `get_snapshot()`: Return a UI-ready dictionary (icon, label, color).

### Concrete Implementations
1.  **`GpioBinaryStrategy`:** Handles inputs (Motion, Door). Includes software debouncing.
2.  **`GpioRelayStrategy`:** Handles outputs. Implements `toggle()`.

## The Hardware Manager

The `HardwareManager` is the conductor. It:
1.  Loads `Hardware` definitions from the database.
2.  Instantiates the correct `Strategy` for each hardware item.
3.  Runs a high-frequency polling loop (0.1s).
4.  Emits events (`hardware_event`) when values change.

## Configuration to UI Pipeline

1.  **DB Config:** `Hardware` table stores `active_icon`, `inactive_label`, etc.
2.  **Strategy:** Loads this config on instantiation.
3.  **Snapshot:** When polling, the Strategy merges the live value with the config.
4.  **UI:** The frontend receives a JSON object containing the resolved icon class and color. The frontend logic is "dumb"—it just renders what the backend tells it.

## Mock Mode
If `RPi.GPIO` is not found (e.g., developing on a Mac/PC), the system automatically falls back to `MockGPIO`. This simulated backend allows full end-to-end testing without physical hardware.