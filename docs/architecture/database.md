# Database Usage & Safety

We use SQLite via SQLAlchemy. Because SQLite is a file-based database and we use threads, specific rules must be followed to avoid locking errors and context issues.

## Rule 1: No DB Access in Global Scope or `__init__`
Database tables are not guaranteed to exist when the application is imported. Accessing the DB during import or construction breaks `flask db` commands.

* **Illegal:** `User.query.all()` at module level.
* **Illegal:** `User.query.all()` in `__init__`.
* **Legal:** `User.query.all()` inside a route or `start()`.

## Rule 2: Application Context in Threads
Flask-SQLAlchemy requires an active **Application Context** to know which database to talk to. Background threads do not have this by default.

**Correct Usage in Services:**
```python
def run(self):
    # You MUST explicitly push the context
    with self.app.app_context():
        devices = Device.query.all()
        # ... logic ...
        db.session.commit()

```

## Rule 3: Short-Lived Sessions

Do not keep a `db.session` open across multiple loop iterations.

* **Anti-Pattern:** Opening a session in `start()` and reusing it in `run()`.
* **Pattern:** Open, query, commit/rollback, and close within a single unit of work (usually one `run()` execution).

## Rule 4: Handling Migrations

The system assumes the database schema is managed by Alembic (Flask-Migrate).

* Services must gracefully handle cases where data might be missing if running against a fresh DB (though `start()` is usually safe).
* Always generate migrations for model changes: `flask db migrate -m "message"`.
