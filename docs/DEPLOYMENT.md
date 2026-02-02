# Production Deployment (Raspberry Pi)

This guide covers two supported production setups for Sheoak Tree on Raspberry Pi:

1) Bare‑metal with systemd + virtualenv
2) Docker + Docker Compose

Use whichever fits your environment. Both paths assume you are on Raspberry Pi OS.

---

## Prerequisites

- Python 3.8+ (system package or pyenv)
- Git
- (Optional) Docker + docker‑compose plugin if using containers

Repository location used below: `/opt/sheoak-tree`

---

## Option A: Bare‑metal (systemd + venv)

### 1) Install and set up

```bash
sudo mkdir -p /opt/sheoak-tree
sudo chown $USER:$USER /opt/sheoak-tree
cd /opt/sheoak-tree

git clone https://github.com/jaredstanbrook/sheoak-tree.git .
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2) Configure environment

Create `/opt/sheoak-tree/.env` (example):

```ini
FLASK_ENV=production
PORT=5173
SECRET_KEY=your-prod-secret
DATABASE_URL=sqlite:///app.db
SNMP_TARGET_IP=192.168.1.1
SNMP_COMMUNITY=public
PRESENCE_SCAN_INTERVAL=60
PRESENCE_SNAPSHOT_RETENTION_DAYS=30
```

### 3) Initialize DB

```bash
source venv/bin/activate
FLASK_APP=run.py flask db upgrade
```

### 4) Run with systemd

Create `/etc/systemd/system/sheoak-tree.service`:

```ini
[Unit]
Description=Sheoak Tree Smart Monitor
After=network.target

[Service]
User=pi
WorkingDirectory=/opt/sheoak-tree
EnvironmentFile=/opt/sheoak-tree/.env
ExecStart=/opt/sheoak-tree/venv/bin/gunicorn -c /opt/sheoak-tree/gunicorn.conf.py wsgi:app
Restart=always
RestartSec=2

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now sheoak-tree
```

### 5) Schedule snapshot cleanup (recommended)

Use the included timer/service:

```bash
sudo cp /opt/sheoak-tree/infra/systemd/presence-snapshot-purge.* /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now presence-snapshot-purge.timer
```

---

## Option B: Docker + Compose

### 1) Build and run

```bash
docker compose up --build -d
```

This uses `docker-compose.yml` (dev‑friendly) and exposes `5173:8000`.

### 2) Production compose

Use `docker-compose.prod.yml` for restart policy, healthcheck, and log rotation:

```bash
docker compose -f docker-compose.prod.yml up --build -d
```

### 3) Environment

Create `.env` in the repo root (same as Option A). Docker uses it via `env_file`.

---

## Health and Maintenance

- Health endpoint: `GET /api/health`
- Snapshot cleanup (manual):

```bash
FLASK_APP=run.py flask purge-presence-snapshots --days 30
```

---

## Updating the Deployment

```bash
cd /opt/sheoak-tree
git pull
source venv/bin/activate
pip install -r requirements.txt
FLASK_APP=run.py flask db upgrade
sudo systemctl restart sheoak-tree
```

For Docker:

```bash
docker compose -f docker-compose.prod.yml up --build -d
```

---

## Troubleshooting

### Service not starting

Check logs:

```bash
sudo journalctl -u sheoak-tree -n 200 --no-pager
```

Common issues:
- Missing `.env` values (SECRET_KEY, DATABASE_URL)
- Wrong working directory or venv path in systemd service
- Port already in use (change `PORT` or stop conflicting service)

### Socket bind permission errors

If you see `PermissionError: [Errno 1] Operation not permitted`:
- Ensure the service runs as a normal user (not root with restricted sandbox)
- Try binding on a different port (e.g., `PORT=5000`)
- On Docker, check container port mapping

### mDNS / Zeroconf errors

If multicast sockets fail (common in containers):
- Disable mDNS via `DISABLE_MDNS=1`
- If needed, disable the presence monitor entirely: `DISABLE_PRESENCE_MONITOR=1`

### Database migrations

Run migrations manually:

```bash
source venv/bin/activate
FLASK_APP=run.py flask db upgrade
```

### Health endpoint fails

Verify the app is up:

```bash
curl -s http://localhost:5173/api/health
```

If health returns `unhealthy`, confirm services are running and the DB is writable.

---

## Reverse Proxy (Optional)

If exposing to LAN or the internet, use a reverse proxy.

Example Nginx site:

```nginx
server {
    listen 80;
    server_name sheoak.local;

    location / {
        proxy_pass http://127.0.0.1:5173;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_buffering off;
    }
}
```

If you use Caddy, the equivalent is:

```
sheoak.local {
    reverse_proxy 127.0.0.1:5173
}
```

---

## Backups (Recommended)

- SQLite DB file: `/opt/sheoak-tree/app/data/app.db`
- Schedule periodic backups (rsync or cron) and keep at least 7 days.

