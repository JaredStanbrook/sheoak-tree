# Dynamic Configuration & Hot Reloading

A critical requirement is the ability to change hardware configuration (pins, names, types) without restarting the entire Python process.

## The Problem
Standard startup logic loads configuration once. If a user edits a pin number in the UI, the running thread is still polling the old pin. Restarting the service is disruptive and causes downtime.

## The Solution: Explicit `reload_config()`

We implement a thread-safe hot-swap mechanism in `HardwareManager`.

### Mechanism Flow
1.  **User Action:** User edits a hardware device via the Web UI.
2.  **DB Update:** The view updates the `Hardware` row in the database.
3.  **Trigger:** The view calls `current_app.service_manager.get_service("HardwareManager").reload_config()`.

### Reload Logic
Inside `reload_config()`:
1.  **Prepare:** Load all enabled hardware from DB.
2.  **Diff:** Compare the new config against the running strategies.
    * **Unchanged:** Keep the running strategy instance (preserves debounce state/timers).
    * **New/Changed:** Instantiate a new strategy, call `setup()`.
    * **Removed:** Drop the old strategy.
3.  **Swap:** Acquire the thread lock (`RLock`) and atomically swap the active strategy list.

### Thread Safety
* The `run()` loop holds the lock while iterating strategies.
* The `reload_config()` method acquires the lock before swapping the list.
* This ensures we never encounter a half-initialized state or a race condition during polling.

### Constraints
* **Pin Reuse:** The system relies on `GPIO.setup` being idempotent. It does not explicitly `cleanup()` individual pins during a reload, as this can disrupt other running pins in the `RPi.GPIO` library. Global `GPIO.cleanup()` is only called on process exit.