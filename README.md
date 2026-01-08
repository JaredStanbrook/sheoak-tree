# Sheoak Tree Smart Monitor

**Sheoak Tree** is a comprehensive smart home monitoring solution designed for shared living spaces. It combines real-time hardware data (motion/door), network presence detection, and machine learning to analyze household activity patterns. Built to run on a Raspberry Pi, it features a modern glassmorphism UI and a robust backend.

## About

Life in a sharehouse requires coordination. **Sheoak Tree** (named after the residence at Sheoak Ct) was built to help housemates manage shared spaces and security without being invasive.

Unlike generic smart home hubs, this system is tailored to:

* **Real-time Visualization:** See which rooms are active instantly via WebSockets.
* **Presence Detection:** unobtrusively checks who is home via Network/SNMP scanning (no GPS tracking required).
* **Smart Analysis:** Uses Random Forest and XGBoost models to classify hardware sequences (e.g., distinguishing a "Kitchen Raid" from a "False Alarm").
* **House Intelligence:** Includes a digitized "Survival Guide" for parking, bin days, and house etiquette.

## Key Features

* **Live Dashboard:** Real-time status of Motion PIRs, Door Contacts, and Relays using `Flask-SocketIO`.
* **Presence Monitoring:** Scans the local network (ARP/SNMP) to detect housemates' devices and determine who is home.
* **AI/ML Analytics:**
* Captures temporal sequences of hardware events.
* Interactive labeling tool to categorize behavior.
* Trainable ML models (Random Forest/XGBoost) to predict event significance.


* **Frequency Analysis:** Visual graphs showing activity hotspots throughout the day (Perth Timezone).
* **Glassmorphism UI:** A refined, mobile-responsive interface.
* **Hardware Control:** Direct GPIO interaction for hardwares and relays (with Mock mode for local dev).

## Tech Stack

* **Hardware:** Raspberry Pi (GPIO), PIR hardwares, Magnetic Door Contacts, 5V Relays.
* **Backend:** Python 3, Flask, SQLAlchemy (SQLite), Flask-SocketIO.
* **Frontend:** HTML5, CSS3 (Custom Glass Theme), JavaScript (ES6 Modules), Chart.js.
* **Machine Learning:** Pandas, Scikit-Learn, XGBoost.
* **DevOps:** GitHub Actions (Self-Hosted Runner), Systemd.

## 🚀 Getting Started

### Prerequisites

* Python 3.8 or higher.
* `pip` and `virtualenv`.
* (Optional) Raspberry Pi for hardware access.

### Installation

1. **Clone the repository**
```bash
git clone https://github.com/jaredstanbrook/sheoak-tree.git
cd sheoak-tree

```


2. **Run the Setup Script**
This script handles venv creation, dependency installation, and DB migration.
```bash
chmod +x setup.sh
./setup.sh

```


3. **Configuration**
Create a `.env` file in the root directory (or rely on `config.py` defaults):
```ini
FLASK_APP=run.py
FLASK_ENV=development
SECRET_KEY=your-secret-key
SNMP_TARGET_IP=192.168.1.1
SNMP_COMMUNITY=public

```


4. **Run the Application**
```bash
source venv/bin/activate
python run.py

```


Access the dashboard at `http://localhost:5000`.
*Note: If running on a non-Pi device, the system will automatically default to `MockGPIO` mode for development.*

## Machine Learning Workflow

Sheoak Tree uses a custom pipeline to analyze hardware behavior:

1. **Data Collection:** Raw events are logged to `hardware_activity.csv` and SQLite.
2. **Sequence Generation:** The system groups events into "Sequences" based on time gaps (default 5 mins).
3. **Labeling:** Use the web interface (`/ai`) or the CLI tool (`app/services/ml/training/label_helper.py`) to label sequences (e.g., "Ignore", "Alarm").
4. **Training:**
```bash
python app/services/ml/training/train_hardware_model.py

```


This generates `random_forest_model.pkl` and visualization artifacts.

## CI/CD & Deployment

This project utilizes **GitHub Actions** for continuous deployment.

* **Workflow:** `.github/workflows/deploy.yml`
* **Runner:** Self-hosted runner on the production Raspberry Pi.
* **Process:**
1. Checks out code on the Pi.
2. Updates the virtual environment.
3. Runs database migrations (`flask db upgrade`) against the production DB.
4. Restarts the `sheoak-tree.service`.



## Project Structure

```
sheoak-tree/
├── app/
│   ├── routes/          # Flask Blueprints (Main, API, hardwares)
│   ├── services/        # Core Logic (Motion, Presence, ML Manager)
│   ├── static/          # CSS, JS, PDF Assets
│   ├── templates/       # HTML Templates
│   └── models.py        # SQLAlchemy Database Models
├── infra/               # Infrastructure scripts
├── migrations/          # Alembic DB Migrations
├── tests/               # Hardware and Unit tests
├── config.py            # App Configuration
├── run.py               # Application Entry Point
└── setup.sh             # Installation Helper

```

## Contributing

1. Fork the repository.
2. Create a feature branch (`git checkout -b feature/AmazingFeature`).
3. Commit your changes (Signed commits preferred, see `infra/scripts/git-setup.sh`).
4. Push to the branch.
5. Open a Pull Request.

## License

Distributed under the MIT License. See `LICENSE` for more information.

## Authors

* **Jared Stanbrook** - *Initial Work* - [@jaredstanbrook](https://www.google.com/search?q=https://github.com/jaredstanbrook)

---

*Built with ❤️ and too much coffee at Sheoak Ct.*