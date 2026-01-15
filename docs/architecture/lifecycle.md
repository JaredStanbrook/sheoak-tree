# Application Lifecycle & Startup Phases

The `sheoak-tree` system strictly separates **Application Construction** from **Runtime Execution**. This separation is critical for stability, testing, and compatibility with Flask CLI tools.

## The "Golden Rule"
> **`create_app()` must be side-effect free.**

Invoking the application factory must never:
1.  Connect to the database.
2.  Start threads.
3.  Access hardware (GPIO).
4.  Perform network calls.

## Lifecycle Phases

### Phase 1: Construction (The Factory)
* **Trigger:** `flask run`, `flask db upgrade`, or `python run.py`.
* **Action:** `create_app()` is called.
* **Allowed:** Loading config, registering Blueprints, initializing extensions (SQLAlchemy), instantiating `ServiceManager`, registering services.
* **Forbidden:** Querying the DB (tables may not exist), starting threads (reloader may kill them).

### Phase 2: Registration
* **Trigger:** Inside `create_app`.
* **Action:** Services are instantiated (e.g., `HardwareManager(app)`).
* **State:** Services are in `STOPPED` state. They hold a reference to `app`, but do nothing.

### Phase 3: Runtime Execution
* **Trigger:** Explicit call in `run.py` (guarded by `if __name__ == "__main__"`).
* **Action:** `app.service_manager.start_all()` is called.
* **Logic:**
    1.  Service `start()` methods are invoked.
    2.  Database connections are opened.
    3.  Hardware/GPIO is initialized.
    4.  Background threads are spawned.

### Phase 4: Graceful Shutdown
* **Trigger:** SIGINT, SIGTERM, or process exit.
* **Action:** `atexit` handler calls `app.service_manager.stop_all()`.
* **Logic:** Threads act on `stop_event`, resources are released, GPIO is cleaned up.

## Common Failure Modes

### ❌ The "Init-Query" Anti-Pattern
**Bad Code:**
```python
class BadService:
    def __init__(self, app):
        # CRITICAL ERROR: Queries DB during construction
        self.config = Hardware.query.all() 

```

**Consequence:** Running `flask db upgrade` crashes because it tries to query a table that doesn't exist yet.

### ✅ The Correct Pattern

**Good Code:**

```python
class GoodService:
    def __init__(self, app):
        self.app = app # Store reference only

    def start(self):
        # Correct: Query DB only when explicitly started
        with self.app.app_context():
            self.config = Hardware.query.all()
        super().start()

```