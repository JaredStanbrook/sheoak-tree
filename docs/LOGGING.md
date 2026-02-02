# Logging Guide

Sheoak Tree uses a centralized logging setup in `app/logging_config.py` with:

- Console output (colored text by default)
- Rotating log files (`logs/app.log`, `logs/error.log`, `logs/scheduler.log`)
- Optional JSON output for Docker and log aggregation

---

## Quick Start

### Text logs (default)
```bash
LOG_LEVEL=INFO
LOG_FORMAT=text
LOG_DIR=/opt/sheoak-tree/logs
```

### JSON logs (Docker/log collectors)
```bash
LOG_LEVEL=INFO
LOG_FORMAT=json
LOG_DIR=/var/log/sheoak-tree
```

---

## Environment Variables

| Variable | Default | Description |
| --- | --- | --- |
| `LOG_LEVEL` | `INFO` | Log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `LOG_FORMAT` | `text` | `text` for colored console, `json` for structured logs |
| `LOG_DIR` | `./logs` | Directory for log files |
| `LOG_MAX_BYTES` | `10485760` | Max size before rotation (bytes) |
| `LOG_BACKUP_COUNT` | `5` | Rotated file count for `app.log` |
| `LOG_ERROR_BACKUP_COUNT` | `5` | Rotated file count for `error.log` |
| `LOG_SCHEDULER_BACKUP_COUNT` | `3` | Rotated file count for `scheduler.log` |

---

## Output Files

- `app.log` — main application logs
- `error.log` — errors and exceptions only
- `scheduler.log` — background scheduler/system tasks

---

## Raspberry Pi Recommendations

- Use text logs for local debugging:

```bash
LOG_LEVEL=INFO
LOG_FORMAT=text
LOG_DIR=/opt/sheoak-tree/logs
LOG_MAX_BYTES=5242880
LOG_BACKUP_COUNT=5
```

- If disk space is limited, reduce `LOG_MAX_BYTES` and backup counts.

---

## Docker Recommendations

- Use JSON logs for parsing/aggregation:

```bash
LOG_LEVEL=INFO
LOG_FORMAT=json
LOG_DIR=/var/log/sheoak-tree
```

- Let Docker handle log rotation if preferred (set to `stdout` only).

---

## Troubleshooting

- **No log files:** ensure `LOG_DIR` exists and is writable by the service user.
- **Duplicate logs:** confirm other modules are not adding handlers manually.
- **Too verbose:** raise `LOG_LEVEL` to `WARNING` or `ERROR`.
