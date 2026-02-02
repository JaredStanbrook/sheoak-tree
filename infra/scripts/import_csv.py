from datetime import datetime

import pandas as pd

from app import create_app, db
from app.models import Event, Sensor

app = create_app()

with app.app_context():
    # Load CSV
    df = pd.read_csv("hardware_activity.csv")
    hardwares = {s.name: s.id for s in Sensor.query.all()}

    events = []
    print("Importing rows...")
    for _, row in df.iterrows():
        s_name = row["hardware_name"]
        if s_name in hardwares:
            # Parse time
            try:
                ts = datetime.fromisoformat(row["timestamp"])
                events.append(
                    Event(
                        hardware_id=hardwares[s_name],
                        value=int(row["state"]),
                        event_type=row["event"],
                        timestamp=ts,
                    )
                )
            except Exception:
                pass

    # Bulk save
    db.session.add_all(events)
    db.session.commit()
    print("Done!")
