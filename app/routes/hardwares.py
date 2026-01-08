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
from app.models import HARDWARE_INTERFACES, Hardware

bp = Blueprint("hardwares", __name__)
logger = current_app.logger if current_app else None


# --- READ & CREATE ---
@bp.route("/manage", methods=["GET", "POST"])
def manage_hardwares():
    # Handle Creating New Hardware
    if request.method == "POST":
        name = request.form.get("name")
        pin = request.form.get("pin")
        driver_type = request.form.get("type")
        enabled = True if request.form.get("enabled") else False

        if not name or not pin:
            flash("Name and Pin are required.", "error")
        else:
            if driver_type not in HARDWARE_INTERFACES:
                flash("Invalid hardware type", "error")
            try:
                new_hw = Hardware(
                    name=name,
                    driver_type=driver_type,
                    configuration={
                        "pin": request.form.get("pin")
                        # You might add specific config defaults here based on type if needed
                    },
                    enabled=enabled,
                )
                db.session.add(new_hw)
                db.session.commit()
                flash(f'Hardware "{name}" added successfully.', "success")
                return redirect(url_for("hardwares.manage_hardwares"))
            except Exception as e:
                db.session.rollback()
                flash(f"Error adding hardware: {str(e)}", "error")

    # Get all hardware
    stmt = select(Hardware).order_by(Hardware.id)
    hardwares = db.session.execute(stmt).scalars().all()

    return render_template(
        "hardwares_manage.html",
        hardwares=hardwares,
        edit_hardware=None,
        hardware_interfaces=HARDWARE_INTERFACES,
    )


# --- UPDATE ---
@bp.route("/edit/<int:hardware_id>", methods=["GET", "POST"])
def edit_hardware(hardware_id):
    # Retrieve Hardware
    hardware = db.session.get(Hardware, hardware_id)
    if not hardware:
        return render_template("500.html", error="Hardware not found"), 404

    if request.method == "POST":
        try:
            hardware.name = request.form.get("name")
            pin = int(request.form.get("pin"))
            s_type = request.form.get("type")
            hardware.enabled = True if request.form.get("enabled") else False

            # Update Configuration based on Type
            if s_type == "relay":
                hardware.driver_type = "gpio_relay"
                hardware.configuration = {"pin": pin}
            else:
                hardware.driver_type = "gpio_binary"
                hardware.configuration = {"pin": pin, "type": s_type}

            db.session.commit()
            flash(f'Hardware "{hardware.name}" updated.', "success")
            return redirect(url_for("hardwares.manage_hardwares"))
        except Exception as e:
            db.session.rollback()
            flash(f"Error updating: {str(e)}", "error")

    # Fetch list for table
    stmt = select(Hardware).order_by(Hardware.id)
    all_hardwares = db.session.execute(stmt).scalars().all()

    return render_template(
        "hardwares_manage.html",
        hardwares=all_hardwares,
        edit_hardware=hardware,
        hardware_interfaces=HARDWARE_INTERFACES,
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
