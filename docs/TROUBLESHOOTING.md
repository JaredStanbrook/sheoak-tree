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

## Live Stream Not Connecting
- Confirm the browser can reach `/stream`.
- Check reverse proxy settings allow long-lived HTTP connections.

## Database Errors
- For local dev, delete `app.db` and re-run `./setup.sh`.
- Use `flask db upgrade` after migrations.
