# Raspberry Pi Deployment

## Prereqs
- Raspberry Pi OS Lite or similar
- Python 3.8+
- GPIO permissions (run as root or add to gpio group)

## Install
```bash
sudo apt-get update
sudo apt-get install -y python3-venv
cd /opt
sudo git clone <repo-url> sheoak-tree
cd sheoak-tree
./setup.sh
cp .env.example .env
# Edit .env: set GPIO_MODE=real, TIMEZONE, SNMP config, etc.
```

## Run with Gunicorn
```bash
gunicorn -c gunicorn.conf.py wsgi:app
```

## Systemd Service
Copy `infra/systemd/sheoak-tree.service` to `/etc/systemd/system/` and enable:
```bash
sudo systemctl daemon-reload
sudo systemctl enable sheoak-tree
sudo systemctl start sheoak-tree
```

## Presence Snapshot Cleanup
The timer `infra/systemd/presence-snapshot-purge.timer` runs periodic cleanup.
