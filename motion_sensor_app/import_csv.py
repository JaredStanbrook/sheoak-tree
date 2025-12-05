from app import create_app, db
from app.models import Sensor, Event
import pandas as pd
from datetime import datetime

app = create_app()

with app.app_context():
    # Load CSV
    df = pd.read_csv("sensor_activity.csv")
    sensors = {s.name: s.id for s in Sensor.query.all()}

    events = []
    print("Importing rows...")
    for _, row in df.iterrows():
        s_name = row['sensor_name']
        if s_name in sensors:
            # Parse time
            try:
                ts = datetime.fromisoformat(row['timestamp'])
                events.append(Event(
                    sensor_id=sensors[s_name],
                    value=int(row['state']),
                    event_type=row['event'],
                    timestamp=ts
                ))
            except:
                pass

    # Bulk save
    db.session.add_all(events)
    db.session.commit()
    print("Done!")
