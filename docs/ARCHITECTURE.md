# Architecture

## Components
- Flask app factory (`app/__init__.py`)
- Service manager (`app/services/core.py`) orchestrates background services
- Hardware manager (`app/services/hardware_manager.py`) polls strategies
- Presence monitor (`app/services/presence_monitor.py`) spawns network scan worker
- SNMP scanner (`app/services/snmp_presence_scanner.py`) enriches presence via SNMP
- System monitor (`app/services/system_monitor.py`) emits connectivity events
- Event bus (`app/services/event_service.py`) fans out events to SocketIO/SSE

## Data Flow
1. GPIO or presence scan detects activity
2. Event bus broadcasts to SocketIO/SSE clients
3. Events are persisted to SQLite
4. Frontend renders live cards and analytics

## Key Modules
- `app/routes/`: HTML and JSON endpoints
- `app/models.py`: SQLAlchemy models
- `app/static/`: glassmorphism UI assets
- `app/services/`: runtime background services

## Runtime Modes
- Mock GPIO (`GPIO_MODE=mock`) for local demos
- Real GPIO (`GPIO_MODE=real`) on Raspberry Pi
- SocketIO async mode set via `SOCKETIO_ASYNC_MODE`
