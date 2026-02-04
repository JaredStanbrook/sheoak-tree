# Contributing

Thanks for contributing! Please keep changes focused and aligned with the project goals.

## Guidelines
- Keep the app Flask-based (no framework migrations).
- Preserve SSE for real-time updates.
- Non-invasive presence detection only (LAN scan, no GPS).
- Add tests where possible; keep changes minimal and well-scoped.

## Development
```bash
./setup.sh
source venv/bin/activate
```

## Lint & Format
```bash
ruff check . --fix
ruff format .
```

## Tests
```bash
pytest
```

## Hardware Invariants
1. No I/O in service constructors.
2. No asyncio (use threaded services).
3. GPIO pins are configured in DB only.
4. DB calls inside threads must use app context.
