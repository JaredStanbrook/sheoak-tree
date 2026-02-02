# Release Notes - v1.0.0

## Highlights
- Flask-SocketIO enabled real-time dashboard
- Mock GPIO mode for portable demos
- Presence detection via ARP/MDNS with optional SNMP
- Demo seeding and replay scripts
- Portfolio-grade documentation and CI

## Upgrade Notes
- Copy `.env.example` to `.env` and set `SECRET_KEY`
- For Raspberry Pi: set `GPIO_MODE=real`
- For SocketIO in production: use gevent-websocket worker
