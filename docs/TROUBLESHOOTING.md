# Troubleshooting

## App Won't Start
- Ensure `python run.py` uses an activated venv.
- Check `.env` for missing `SECRET_KEY` or invalid `DATABASE_URL`.

## GPIO Errors
- If you see permission errors, run as root or add the user to the `gpio` group.
- For local demos, set `GPIO_MODE=mock`.

## Presence Scan Issues
- Ensure `ping` and `arp` are available on the host.
- Set `DISABLE_PRESENCE_MONITOR=1` to disable scanning.
- For SNMP, verify `SNMP_TARGET_IP` and community string.

## SocketIO Not Connecting
- Confirm `SOCKETIO_PATH` matches the client path.
- In production, use gevent-websocket worker or eventlet.

## Database Errors
- For local dev, delete `app.db` and re-run `./setup.sh`.
- Use `flask db upgrade` after migrations.
