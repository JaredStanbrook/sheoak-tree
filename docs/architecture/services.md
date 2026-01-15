# Service Architecture & Concurrency Model

## The Concurrency Decision
We utilize a **Thread-Based** concurrency model.

### Why Threads?
1.  **Gevent Compatibility:** The application uses `Flask-SocketIO` with `async_mode='gevent'`. Gevent monkey-patches standard threading to be cooperative. Using standard `threading` primitives ensures our background tasks play nicely with the web server's worker model.
2.  **IO Bound:** Network scanning and GPIO polling are IO-bound operations suitable for threading.
3.  **Simplicity:** Synchronous logic is easier to reason about, debug, and test than mixing `asyncio` loops with WSGI applications.

### 🚫 Forbidden Patterns
* **No `asyncio`:** Do not introduce an `asyncio` event loop. It conflicts with Gevent and adds unnecessary complexity.
* **No Multiprocessing:** Unless strictly isolated (e.g., heavy CPU tasks), avoid spawning child processes to prevent orphan processes and shared memory complexity.

## The `ThreadedService` Interface

All background services must inherit from `ThreadedService` (defined in `app.services.core`).

### Key Responsibilities

1.  **`__init__(self, name, interval)`**
    * Set up configuration.
    * **Do not** start execution.

2.  **`start(self)`**
    * Initialize resources (DB, Hardware).
    * Call `super().start()` to spawn the thread.

3.  **`run(self)`**
    * This is the payload loop.
    * It is called repeatedly every `interval` seconds.
    * If it crashes, the wrapper logs the error and retries (it does not kill the app).

4.  **`stop(self)`**
    * Signal the thread to exit.
    * Clean up resources (close sockets, release GPIO).

## Error Handling
The `ThreadedService` wrapper provides a safety net. If a `run()` iteration raises an exception:
1.  The error is logged with a full traceback.
2.  The thread waits 5 seconds (backoff).
3.  The loop restarts.

This ensures a transient error (e.g., network blip) does not kill the monitoring service.