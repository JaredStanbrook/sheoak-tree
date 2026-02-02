from datetime import datetime, timedelta

import click
from flask import current_app

from app.extensions import db
from app.models import DevicePresenceSnapshot


def register_commands(app):
    @app.cli.command("purge-presence-snapshots")
    @click.option("--days", default=None, type=int)
    def purge_presence_snapshots(days):
        """Delete device presence snapshots older than N days."""
        if days is None:
            days = current_app.config.get("PRESENCE_SNAPSHOT_RETENTION_DAYS", 30)
        cutoff = datetime.now() - timedelta(days=days)
        deleted = DevicePresenceSnapshot.query.filter(
            DevicePresenceSnapshot.timestamp < cutoff
        ).delete()
        db.session.commit()
        click.echo(f"Deleted {deleted} device presence snapshots older than {days} days")
