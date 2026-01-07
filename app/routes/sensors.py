from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from sqlalchemy import select

from app.extensions import db
from app.models import Sensor

bp = Blueprint("sensors", __name__)
logger = current_app.logger if current_app else None


# --- READ & CREATE ---
@bp.route("/manage", methods=["GET", "POST"])
def manage_sensors():
    # Handle Creating a New Sensor
    if request.method == "POST":
        name = request.form.get("name")
        pin = request.form.get("pin")
        s_type = request.form.get("type")
        enabled = True if request.form.get("enabled") else False

        if not name or not pin:
            flash("Name and Pin are required.", "error")
        else:
            try:
                new_sensor = Sensor(name=name, pin=int(pin), type=s_type, enabled=enabled)
                db.session.add(new_sensor)
                db.session.commit()
                flash(f'Sensor "{name}" added successfully.', "success")
                return redirect(url_for("sensors.manage_sensors"))
            except Exception as e:
                db.session.rollback()
                flash(f"Error adding sensor: {str(e)}", "error")

    # Get all sensors (Modern Syntax)
    # 1. db.select(Sensor) prepares the statement
    # 2. db.session.execute(...) runs it
    # 3. .scalars() extracts the ORM objects from the rows
    # 4. .all() returns a list
    stmt = select(Sensor).order_by(Sensor.id)
    sensors = db.session.execute(stmt).scalars().all()

    return render_template("sensors_manage.html", sensors=sensors, edit_sensor=None)


# --- UPDATE ---
@bp.route("/edit/<int:sensor_id>", methods=["GET", "POST"])
def edit_sensor(sensor_id):
    # Modern "get_or_404" equivalent
    sensor = db.session.get(Sensor, sensor_id)
    if not sensor:
        return render_template("500.html", error="Sensor not found"), 404

    if request.method == "POST":
        try:
            sensor.name = request.form.get("name")
            sensor.pin = int(request.form.get("pin"))
            sensor.type = request.form.get("type")
            sensor.enabled = True if request.form.get("enabled") else False

            db.session.commit()
            flash(f'Sensor "{sensor.name}" updated.', "success")
            return redirect(url_for("sensors.manage_sensors"))
        except Exception as e:
            db.session.rollback()
            flash(f"Error updating sensor: {str(e)}", "error")

    # Fetch list for the table below the form
    stmt = select(Sensor).order_by(Sensor.id)
    all_sensors = db.session.execute(stmt).scalars().all()

    return render_template("sensors_manage.html", sensors=all_sensors, edit_sensor=sensor)


# --- DELETE ---
@bp.route("/delete/<int:sensor_id>", methods=["POST"])
def delete_sensor(sensor_id):
    sensor = db.session.get(Sensor, sensor_id)

    if sensor:
        name = sensor.name
        try:
            db.session.delete(sensor)
            db.session.commit()
            flash(f'Sensor "{name}" deleted.', "success")
        except Exception as e:
            db.session.rollback()
            flash(f"Could not delete sensor: {str(e)}", "error")
    else:
        flash("Sensor not found.", "error")

    return redirect(url_for("sensors.manage_sensors"))
