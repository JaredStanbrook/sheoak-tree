# Motion Sensor Web App

This project is a Raspberry Pi-based motion and contact sensor monitoring web application. It provides real-time sensor status, activity logs, frequency analysis, and sequence review/labeling via a modern web interface.

## Features
- Live display of motion and door sensors
- Activity log and frequency-based graphs
- Sequence review and labeling (Ignore, Log, Notify, Alarm)
- Persistent logging to CSV and JSON
- REST API and WebSocket support
- Beautiful, responsive UI

## Project Structure

```
motion_sensor_app/
  app/
	 static/
		js/app.js
		css/style.css
	 templates/
		index.html
		base.html
	 routes/
		main.py
		api.py
	 services/
		sensor_monitor.py
		label_advanced.py
		...
  run.py
  requirements.txt
sensor_activity.csv
sequence_labels_*.json
```

## Setup

1. **Clone the repository:**
	```bash
	git clone <your-repo-url>
	cd motion_sensor_app
	```

2. **Create and activate a Python virtual environment:**
	```bash
	python3 -m venv venv
	source venv/bin/activate
	```

3. **Install dependencies:**
	```bash
	pip install -r requirements.txt
	```

4. **Configure your sensors and wiring as described in the code comments.**

5. **Run the web app:**
	```bash
	python run.py
	```
	The app will be available at http://127.0.0.1:5000/

## Systemd Service (Optional)

To run the app as a service on boot:

1. Create `/etc/systemd/system/motion_sensor.service` with:
	```ini
	[Unit]
	Description=Motion Sensor Web App
	After=network.target

	[Service]
	Type=simple
	WorkingDirectory=/home/jaredstanbrook/sensor/motion_sensor_app
	ExecStart=/home/jaredstanbrook/sensor/motion_sensor_app/venv/bin/python /home/jaredstanbrook/sensor/motion_sensor_app/run.py
	Restart=always
	User=jaredstanbrook

	[Install]
	WantedBy=multi-user.target
	```

2. Reload and start the service:
	```bash
	sudo systemctl daemon-reload
	sudo systemctl start motion_sensor.service
	sudo systemctl enable motion_sensor.service
	```

## API Endpoints

- `/api/sensors` — Get current sensor states
- `/api/activity/<hours>` — Get activity log
- `/api/frequency/<hours>/<interval>` — Get frequency data
- `/api/sequences/list` — Paginated sequence summaries
- `/api/sequences/<id>` — Detailed sequence info
- `/api/sequences/<id>/label` — Update sequence label
- `/api/sequences/statistics` — Label statistics

## Frontend

The UI is served from `templates/index.html` and uses `static/js/app.js` and `static/css/style.css`. It supports live updates via WebSocket and interactive review/labeling of sensor sequences.

## Data Files
- `sensor_activity.csv` — Raw sensor event log
- `sequence_labels_*.json` — Sequence and label state

## License

MIT License
