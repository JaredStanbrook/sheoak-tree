# Contributor Guide

Welcome! Please follow these architectural guardrails to maintain system stability.

## 🚨 The Invariants (Never Break These)

1.  **Never put IO in `__init__`.** Services must instantiate silently and instantly.
2.  **Never mix concurrency models.** Do not use `asyncio`. Use the provided `ThreadedService`.
3.  **Never hardcode GPIO pins.** All pin mappings must come from the Database configuration.
4.  **Always use `app_context`.** If you touch the DB in a thread, you need a context.

## 🛠 How To...

### Add a New Service
1.  Create a class in `app/services/` inheriting from `ThreadedService`.
2.  Implement `run(self)` for your logic.
3.  Implement `start(self)` to load initial state (remember `super().start()`).
4.  Register it in `app/__init__.py` inside `create_app`:
    ```python
    app.service_manager.register(MyNewService(app))
    ```

### Add a New Hardware Type
1.  Define the logic in `app/services/hardware_strategies.py`.
2.  Implement `setup()` and `read()`.
3.  Add the mapping to `HardwareFactory`.
4.  Add the type key to `HARDWARE_DEFAULTS` for UI styling.

### Modify the Database
1.  Edit `app/models.py`.
2.  Run `flask db migrate -m "description"`.
3.  Run `flask db upgrade`.
4.  **Verify:** Run `flask db upgrade` *before* starting the app to ensure your `__init__` logic isn't broken.

## 🧪 Testing
* **Unit Tests:** `pytest tests/unit`
* **Mocking:** Use `tests/conftest.py` fixtures. The `GPIO` library is automatically mocked in the test environment.