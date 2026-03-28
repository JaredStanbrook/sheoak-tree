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
3.  **`SerialInputStrategy`:** Handles read-only serial feeds and maps incoming serial keys onto local hardware definitions.

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

## Serial Adapter Mode
Serial-backed hardware uses the same `HardwareManager` polling loop as GPIO-backed devices. Each serial hardware definition stores:
* `serial_port`: physical adapter path, such as `/dev/ttyACM0`
* `baud_rate`: serial speed
* `source_key`: the identifier expected from the serial payload

A shared serial reader listens on the configured port, parses incoming lines, and caches the latest reading by `source_key`. Strategies then read from that cache. This keeps local hardware names and IDs authoritative in the Flask app, so Arduino-side labels can be remapped instead of written directly into the database.

## Mock Mode
If `RPi.GPIO` is not found (e.g., developing on a Mac/PC), the system automatically falls back to `MockGPIO`. This simulated backend allows full end-to-end testing without physical hardware.
