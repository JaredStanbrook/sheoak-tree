from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from sqlalchemy import select

from app.extensions import db
from app.models import HARDWARE_INTERFACES, HARDWARE_TYPES, Hardware

bp = Blueprint("hardwares", __name__, url_prefix="/hardwares")


# --- HELPER: Dynamic Form Parser ---
def _parse_hardware_form(form_data):
    """
    Extracts core fields and packages all 'config_' fields into a JSON dict.
    Returns: (name, driver_interface, enabled, configuration_dict)
    """
    name = form_data.get("name")
    type = form_data.get("type")
    driver_interface = form_data.get("driver_interface")  # Matches <select name="driver_interface">
    enabled = True if form_data.get("enabled") else False

    configuration = {}

    # The Magic Loop: Finds any input named 'config_...'
    for key, value in form_data.items():
        if key.startswith("config_"):
            # Strip prefix (e.g., "config_pin" -> "pin")
            clean_key = key[7:]

            # Handle empty strings (don't save them to keep JSON clean)
            if not value or not value.strip():
                continue

            value = value.strip()

            # auto-convert 'pin' to integer
            if clean_key == "pin":
                try:
                    configuration[clean_key] = int(value)
                except ValueError:
                    pass  # Keep as string or ignore if invalid
            else:
                configuration[clean_key] = value

    return name, type, driver_interface, enabled, configuration


# --- READ & CREATE ---
@bp.route("/manage", methods=["GET", "POST"])
def manage_hardwares():
    # Handle Creating New Hardware
    if request.method == "POST":
        name, type, driver_interface, enabled, config = _parse_hardware_form(request.form)

        if not name:
            flash("Name is required.", "error")
        elif driver_interface not in HARDWARE_INTERFACES:
            flash("Invalid hardware driver type selected.", "error")
        else:
            try:
                new_hw = Hardware(
                    name=name,
                    type=type,
                    driver_interface=driver_interface,
                    configuration=config,
                    enabled=enabled,
                )
                db.session.add(new_hw)
                db.session.commit()
                flash(f'Hardware "{name}" added successfully.', "success")
                return redirect(url_for("hardwares.manage_hardwares"))
            except Exception as e:
                db.session.rollback()
                flash(f"Error adding hardware: {str(e)}", "error")

    # Get all hardware for the list
    stmt = select(Hardware).order_by(Hardware.id)
    hardwares = db.session.execute(stmt).scalars().all()

    return render_template(
        "hardware_manage.html",
        hardwares=hardwares,
        edit_hardware=None,
        hardware_interfaces=HARDWARE_INTERFACES,
        hardware_types=HARDWARE_TYPES,
    )


# --- UPDATE ---
@bp.route("/edit/<int:hardware_id>", methods=["GET", "POST"])
def edit_hardware(hardware_id):
    # Retrieve Hardware
    hardware = db.session.get(Hardware, hardware_id)

    if not hardware:
        # Fallback if ID doesn't exist
        flash("Hardware ID not found.", "error")
        return redirect(url_for("hardwares.manage_hardwares"))

    if request.method == "POST":
        name, type, driver_interface, enabled, config = _parse_hardware_form(request.form)

        if not name:
            flash("Name is required.", "error")
        else:
            try:
                hardware.name = name
                hardware.type = type
                hardware.driver_interface = driver_interface
                hardware.enabled = enabled

                # We replace the entire configuration with the new form state
                # This ensures removed fields (cleared inputs) are removed from JSON
                hardware.configuration = config

                db.session.commit()
                flash(f'Hardware "{hardware.name}" updated.', "success")
                return redirect(url_for("hardwares.manage_hardwares"))
            except Exception as e:
                db.session.rollback()
                flash(f"Error updating: {str(e)}", "error")

    # Fetch list for table context (so the table still appears below the edit form)
    stmt = select(Hardware).order_by(Hardware.id)
    all_hardwares = db.session.execute(stmt).scalars().all()

    return render_template(
        "hardware_manage.html",
        hardwares=all_hardwares,
        edit_hardware=hardware,  # Triggers the "Edit Mode" in the template
        hardware_interfaces=HARDWARE_INTERFACES,
        hardware_types=HARDWARE_TYPES,
    )


# --- DELETE ---
@bp.route("/delete/<int:hardware_id>", methods=["POST"])
def delete_hardware(hardware_id):
    hardware = db.session.get(Hardware, hardware_id)

    if hardware:
        name = hardware.name
        try:
            db.session.delete(hardware)
            db.session.commit()
            flash(f'Deleted "{name}".', "success")
        except Exception as e:
            db.session.rollback()
            flash(f"Could not delete: {str(e)}", "error")
    else:
        flash("Hardware not found.", "error")

    return redirect(url_for("hardwares.manage_hardwares"))
