import json
import os
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Tuple

from flask import Blueprint, current_app, jsonify, request

bp = Blueprint("api", __name__)
logger = current_app.logger if current_app else None

_CACHE: Dict[Tuple[Any, ...], Dict[str, Any]] = {}
_CACHE_TTL_SECONDS = 30
_CACHE_FILE = Path(os.getenv("LOG_DIR", "./logs")) / "summary_cache.json"
_CACHE_FILE_LIMIT = 200


@bp.route("/events", methods=["GET"])
def dev_get_all_events():
    """
    Development endpoint to load all events with hardware relationships.
    """
    # Check if we are in development mode for safety
    if current_app.config.get("ENV") != "development":
        return jsonify(
            {"success": False, "error": "Endpoint only available in development mode"}
        ), 403

    try:
        from app.models import Event

        # Query all events, joining the hardware table to ensure relationships are loaded
        all_events = Event.query.all()

        return jsonify(
            {
                "success": True,
                "count": len(all_events),
                "events": [e.to_dict() for e in all_events],
                "timestamp": datetime.now().isoformat(),
            }
        )
    except Exception as e:
        current_app.logger.error(f"Dev API Error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@bp.route("/hardwares", methods=["GET"])
def get_hardwares():
    """
    Returns the current state of all hardware devices.
    Used for the initial dashboard render.
    """
    try:
        hardware = current_app.service_manager.get_service("HardwareManager")

        if not hardware:
            return jsonify({"success": False, "error": "Hardware service not running"}), 503

        response_data = []
        for _, strategy in hardware.strategies.items():
            snapshot = strategy.get_snapshot()
            response_data.append(snapshot)

        return jsonify({"success": True, "hardwares": response_data}), 200

    except Exception as e:
        current_app.logger.error(f"API Error fetching hardwares: {e}")
        return jsonify({"success": False, "error": "Failed to fetch hardware data"}), 500


@bp.route("/activity/<int:hours>")
def api_activity(hours):
    """Get raw event logs."""
    hardware = current_app.service_manager.get_service("HardwareManager")
    if not hardware:
        return jsonify({"success": False, "error": "Hardware service unavailable"}), 503

    return jsonify(
        {
            "success": True,
            "activity": hardware.get_activity_data(hours),
            "timestamp": datetime.now().isoformat(),
            "hours": hours,
        }
    )


@bp.route("/frequency/<int:hours>/<int:interval>")
def api_frequency(hours, interval):
    """Get aggregated frequency data for graphs."""
    hardware = current_app.service_manager.get_service("HardwareManager")
    if not hardware:
        return jsonify({"success": False, "error": "Hardware service unavailable"}), 503

    cache_key = ("frequency", hours, interval)
    cached = _cache_get(cache_key)
    if cached:
        return jsonify(cached)

    data = hardware.get_frequency_data(hours, interval)
    summary, summary_totals, hardware_index = _build_frequency_summary(hours, interval)

    payload = {
        "success": True,
        "frequency": data,
        "summary": summary,
        "summary_totals": summary_totals,
        "hardware_index": hardware_index,
        "timestamp": datetime.now().isoformat(),
        "hours": hours,
        "interval_minutes": interval,
    }
    _cache_set(cache_key, payload)
    return jsonify(payload)


@bp.route("/hardwares/<int:hardware_id>/history", methods=["GET"])
def api_hardware_history(hardware_id):
    """Return detailed history for a specific hardware device."""
    from app.models import Event, Hardware

    hours = int(request.args.get("hours", 24))
    interval = int(request.args.get("interval", 30))
    cutoff = datetime.now() - timedelta(hours=hours)

    hardware = Hardware.query.get(hardware_id)
    if not hardware:
        return jsonify({"success": False, "error": "Hardware not found"}), 404

    cache_key = ("hardware_history", hardware_id, hours, interval)
    cached = _cache_get(cache_key)
    if cached:
        return jsonify(cached)

    events = (
        Event.query.filter(Event.hardware_id == hardware_id)
        .filter(Event.timestamp >= cutoff)
        .order_by(Event.timestamp.asc())
        .all()
    )

    summary = _build_hardware_summary(hardware, events, cutoff, interval, hours)
    series = _build_hardware_series(hardware, events, cutoff, interval)
    recent_events = [e.to_dict() for e in events[-20:][::-1]]

    payload = {
        "success": True,
        "hardware": {
            "id": hardware.id,
            "name": hardware.name,
            "type": hardware.type,
            "driver_interface": hardware.driver_interface,
            "config_type": hardware.configuration.get("type", "generic"),
        },
        "summary": summary,
        "series": series,
        "recent_events": recent_events,
        "hours": hours,
        "interval_minutes": interval,
    }
    _cache_set(cache_key, payload)
    return jsonify(payload)


@bp.route("/analysis", methods=["GET"])
def api_analysis():
    from app.models import Event, Hardware

    start_raw = request.args.get("from")
    end_raw = request.args.get("to")
    bucket_raw = request.args.get("bucket", "auto")

    end_time = datetime.now()
    if end_raw:
        end_time = datetime.fromisoformat(end_raw)
    start_time = end_time - timedelta(hours=24)
    if start_raw:
        start_time = datetime.fromisoformat(start_raw)

    if start_time >= end_time:
        return jsonify({"success": False, "error": "Invalid range"}), 400

    interval = _resolve_bucket_minutes(start_time, end_time, bucket_raw)
    hours = max(1, int((end_time - start_time).total_seconds() / 3600))

    events = (
        Event.query.filter(Event.timestamp >= start_time)
        .filter(Event.timestamp <= end_time)
        .order_by(Event.timestamp.asc())
        .all()
    )
    hardware_list = Hardware.query.all()

    frequency, totals_series, bucket_table = _build_frequency_series(
        hardware_list, events, start_time, end_time, interval
    )
    summary, summary_totals, hardware_index = _build_frequency_summary_range(
        hardware_list, events, hours, interval, start_time
    )

    stats = _build_overall_stats(
        totals_series,
        start_time,
        end_time,
        interval,
        summary_totals.get("active_events", 0),
    )
    distribution = _build_distribution(totals_series)
    hourly_distribution = _build_hourly_distribution(events)
    top_contributors = _build_top_contributors(summary)

    return jsonify(
        {
            "success": True,
            "frequency": frequency,
            "total_counts": totals_series,
            "summary": summary,
            "summary_totals": summary_totals,
            "hardware_index": hardware_index,
            "stats": stats,
            "distribution": distribution,
            "hourly_distribution": hourly_distribution,
            "top_contributors": top_contributors,
            "bucket_table": bucket_table,
            "interval_minutes": interval,
        }
    )


@bp.route("/demo/replay", methods=["POST"])
def api_demo_replay():
    if not current_app.config.get("DEMO_MODE", False):
        return jsonify({"success": False, "error": "Demo mode is disabled"}), 403

    payload = request.get_json(silent=True) or {}
    limit = int(payload.get("limit", 60))
    delay_ms = int(payload.get("delay_ms", current_app.config.get("DEMO_REPLAY_DELAY_MS", 800)))

    from app.models import Event, Hardware
    from app.services.event_service import bus

    hardware_manager = current_app.service_manager.get_service("HardwareManager")

    events = (
        Event.query.order_by(Event.timestamp.desc()).limit(limit).all()[::-1] if limit > 0 else []
    )
    hardware_map = {h.id: h for h in Hardware.query.all()}

    def replay():
        for event in events:
            if hardware_manager and event.hardware_id in hardware_manager.strategies:
                strategy = hardware_manager.strategies[event.hardware_id]
                snapshot = strategy.get_snapshot(event.value)
                snapshot["unit"] = event.unit
                snapshot["timestamp"] = event.timestamp.isoformat()
            else:
                hardware = hardware_map.get(event.hardware_id)
                snapshot = {
                    "hardware_id": event.hardware_id,
                    "name": hardware.name if hardware else "Unknown",
                    "type": hardware.type if hardware else "unknown",
                    "value": event.value,
                    "unit": event.unit,
                    "timestamp": event.timestamp.isoformat(),
                    "ui": {
                        "text": "Demo",
                        "color": "status-info",
                        "icon": "activity",
                        "active": bool(event.value),
                    },
                }

            bus.emit("hardware_event", snapshot)
            time.sleep(max(0.05, delay_ms / 1000.0))

    threading.Thread(target=replay, name="DemoReplay", daemon=True).start()
    return jsonify({"success": True, "replayed": len(events)})


def _build_frequency_summary(hours, interval):
    from app.models import Event, Hardware

    cutoff = datetime.now() - timedelta(hours=hours)
    events = Event.query.filter(Event.timestamp >= cutoff).order_by(Event.timestamp.asc()).all()
    hardware_list = Hardware.query.all()
    events_by_hw = {}
    for evt in events:
        events_by_hw.setdefault(evt.hardware_id, []).append(evt)

    summary = []
    total_events = 0
    total_active = 0

    for hw in hardware_list:
        hw_events = events_by_hw.get(hw.id, [])
        config_type = _resolve_hardware_type(hw)
        active_events = sum(1 for e in hw_events if e.value and e.value > 0)
        door_stats = _build_door_stats(hw_events) if config_type == "door" else {}
        motion_stats = (
            _build_motion_stats(hw_events, cutoff, interval, hours)
            if config_type == "motion"
            else {}
        )
        total_events += len(hw_events)
        total_active += active_events

        summary.append(
            {
                "id": hw.id,
                "name": hw.name,
                "config_type": config_type,
                "total_events": len(hw_events),
                "active_events": active_events,
                "last_seen": hw_events[-1].timestamp.isoformat() if hw_events else None,
                **door_stats,
                **motion_stats,
            }
        )

    hardware_index = [
        {
            "id": hw.id,
            "name": hw.name,
            "type": hw.type,
            "driver_interface": hw.driver_interface,
            "config_type": _resolve_hardware_type(hw),
        }
        for hw in hardware_list
    ]

    summary_totals = {
        "hardware_count": len(hardware_list),
        "total_events": total_events,
        "active_events": total_active,
    }

    return summary, summary_totals, hardware_index


def _build_frequency_summary_range(hardware_list, events, hours, interval, start_time):
    events_by_hw = {}
    for evt in events:
        events_by_hw.setdefault(evt.hardware_id, []).append(evt)

    summary = []
    total_events = 0
    total_active = 0

    for hw in hardware_list:
        hw_events = events_by_hw.get(hw.id, [])
        config_type = _resolve_hardware_type(hw)
        active_events = sum(1 for e in hw_events if e.value and e.value > 0)
        door_stats = _build_door_stats(hw_events) if config_type == "door" else {}
        motion_stats = (
            _build_motion_stats(hw_events, start_time, interval, hours)
            if config_type == "motion"
            else {}
        )
        total_events += len(hw_events)
        total_active += active_events

        summary.append(
            {
                "id": hw.id,
                "name": hw.name,
                "config_type": config_type,
                "total_events": len(hw_events),
                "active_events": active_events,
                "last_seen": hw_events[-1].timestamp.isoformat() if hw_events else None,
                **door_stats,
                **motion_stats,
            }
        )

    hardware_index = [
        {
            "id": hw.id,
            "name": hw.name,
            "type": hw.type,
            "driver_interface": hw.driver_interface,
            "config_type": _resolve_hardware_type(hw),
        }
        for hw in hardware_list
    ]

    summary_totals = {
        "hardware_count": len(hardware_list),
        "total_events": total_events,
        "active_events": total_active,
    }

    return summary, summary_totals, hardware_index


def _build_hardware_summary(hardware, events, cutoff, interval, hours):
    config_type = _resolve_hardware_type(hardware)
    summary = {
        "config_type": config_type,
        "total_events": len(events),
        "active_events": sum(1 for e in events if e.value and e.value > 0),
        "last_seen": events[-1].timestamp.isoformat() if events else None,
        "window_start": cutoff.isoformat(),
    }

    values = [e.value for e in events if e.value is not None]
    if values:
        summary.update(
            {
                "min_value": min(values),
                "max_value": max(values),
                "avg_value": round(sum(values) / len(values), 2),
            }
        )

    if config_type == "door":
        summary.update(_build_door_stats(events))

    if config_type == "motion":
        summary.update(_build_motion_stats(events, cutoff, interval, hours))

    return summary


def _build_hardware_series(hardware, events, cutoff, interval):
    config_type = _resolve_hardware_type(hardware)
    end_time = datetime.now()
    delta_min = end_time.minute % interval
    end_time = end_time - timedelta(
        minutes=delta_min, seconds=end_time.second, microseconds=end_time.microsecond
    )
    start_time = cutoff.replace(second=0, microsecond=0)
    start_delta = start_time.minute % interval
    start_time = start_time - timedelta(minutes=start_delta)

    timestamps = []
    current = start_time
    while current <= end_time:
        timestamps.append(current)
        current += timedelta(minutes=interval)

    start_ts = start_time.timestamp()
    interval_seconds = interval * 60

    if config_type == "door":
        blocks = []
        open_time = None
        for evt in events:
            if evt.value and evt.value > 0:
                open_time = evt.timestamp
            elif open_time:
                blocks.append({"x": [open_time.isoformat(), evt.timestamp.isoformat()], "y": 1})
                open_time = None
        if open_time:
            blocks.append({"x": [open_time.isoformat(), datetime.now().isoformat()], "y": 1})

        return {
            "mode": "state_blocks",
            "timestamps": [t.isoformat() for t in timestamps],
            "data": blocks,
        }

    bucket_counts = [0] * len(timestamps)
    bucket_sums = [0.0] * len(timestamps)
    bucket_hits = [0] * len(timestamps)

    for evt in events:
        if evt.value is None:
            continue
        evt_ts = evt.timestamp.timestamp()
        index = int((evt_ts - start_ts) / interval_seconds)
        if 0 <= index < len(timestamps):
            bucket_counts[index] += 1 if evt.value > 0 else 0
            bucket_sums[index] += evt.value
            bucket_hits[index] += 1

    avg_values = [
        round(bucket_sums[i] / bucket_hits[i], 2) if bucket_hits[i] else None
        for i in range(len(timestamps))
    ]

    return {
        "mode": "count",
        "timestamps": [t.isoformat() for t in timestamps],
        "counts": bucket_counts,
        "avg_values": avg_values,
    }


def _build_door_stats(events):
    opens = 0
    closes = 0
    open_durations = []
    open_time = None
    open_by_hour = {}
    open_by_day = {}
    for evt in events:
        if evt.value and evt.value > 0:
            if open_time is None:
                open_time = evt.timestamp
            opens += 1
        else:
            if open_time:
                duration = (evt.timestamp - open_time).total_seconds()
                open_durations.append(duration)
                _accumulate_open_time(open_by_hour, open_by_day, open_time, evt.timestamp)
                open_time = None
            closes += 1
    if open_time:
        duration = (datetime.now() - open_time).total_seconds()
        open_durations.append(duration)
        _accumulate_open_time(open_by_hour, open_by_day, open_time, datetime.now())

    top_hour = max(open_by_hour, key=open_by_hour.get) if open_by_hour else None
    top_day = max(open_by_day, key=open_by_day.get) if open_by_day else None

    return {
        "open_count": opens,
        "close_count": closes,
        "total_open_minutes": round(sum(open_durations) / 60, 2) if open_durations else 0,
        "avg_open_seconds": round(sum(open_durations) / len(open_durations), 2)
        if open_durations
        else 0,
        "longest_open_seconds": round(max(open_durations), 2) if open_durations else 0,
        "open_minutes_by_hour": _sorted_minutes(open_by_hour),
        "open_minutes_by_day": _sorted_minutes(open_by_day),
        "peak_open_hour": top_hour,
        "peak_open_day": top_day,
    }


def _build_motion_stats(events, cutoff, interval, hours):
    if not events:
        return {
            "peak_interval_events": 0,
            "avg_events_per_hour": 0,
            "avg_events_per_interval": 0,
            "p50_interval_events": 0,
            "p90_interval_events": 0,
            "p95_interval_events": 0,
        }

    start_ts = cutoff.timestamp()
    interval_seconds = interval * 60
    buckets = {}
    for evt in events:
        if evt.value and evt.value > 0:
            index = int((evt.timestamp.timestamp() - start_ts) / interval_seconds)
            buckets[index] = buckets.get(index, 0) + 1

    counts = sorted(buckets.values())
    peak = max(counts) if counts else 0
    total_active = sum(counts)
    interval_count = max(1, int((hours * 60) / interval))

    return {
        "peak_interval_events": peak,
        "avg_events_per_hour": round(total_active / max(hours, 1), 2),
        "avg_events_per_interval": round(total_active / interval_count, 2),
        "p50_interval_events": _percentile(counts, 50),
        "p90_interval_events": _percentile(counts, 90),
        "p95_interval_events": _percentile(counts, 95),
    }


def _resolve_bucket_minutes(start, end, bucket_raw):
    if bucket_raw and bucket_raw != "auto":
        try:
            return max(1, int(bucket_raw))
        except ValueError:
            return 30
    minutes = (end - start).total_seconds() / 60
    if minutes <= 60:
        return 1
    if minutes <= 6 * 60:
        return 5
    if minutes <= 24 * 60:
        return 15
    if minutes <= 7 * 24 * 60:
        return 60
    if minutes <= 30 * 24 * 60:
        return 360
    return 1440


def _build_frequency_series(hardware_list, events, start_time, end_time, interval):
    timestamps = []
    current = start_time
    while current <= end_time:
        timestamps.append(current)
        current += timedelta(minutes=interval)

    interval_seconds = interval * 60
    start_ts = start_time.timestamp()

    results = {}
    total_counts = [0] * len(timestamps)
    bucket_sums = [0.0] * len(timestamps)
    bucket_hits = [0] * len(timestamps)
    events_by_hw = {}
    for evt in events:
        events_by_hw.setdefault(evt.hardware_id, []).append(evt)

    for hw in hardware_list:
        config_type = _resolve_hardware_type(hw)
        hw_events = events_by_hw.get(hw.id, [])
        if config_type == "door":
            blocks = []
            open_time = None
            for evt in hw_events:
                if evt.value and evt.value > 0:
                    open_time = evt.timestamp
                elif open_time:
                    blocks.append({"x": [open_time.isoformat(), evt.timestamp.isoformat()], "y": 1})
                    open_time = None
            if open_time:
                blocks.append({"x": [open_time.isoformat(), datetime.now().isoformat()], "y": 1})
            results[hw.name] = blocks
        else:
            counts = [0] * len(timestamps)
            for evt in hw_events:
                if evt.value is None:
                    continue
                evt_ts = evt.timestamp.timestamp()
                index = int((evt_ts - start_ts) / interval_seconds)
                if 0 <= index < len(timestamps):
                    if evt.value > 0:
                        counts[index] += 1
                        total_counts[index] += 1
                    bucket_sums[index] += evt.value
                    bucket_hits[index] += 1
            results[hw.name] = counts

    bucket_table = []
    for idx, ts in enumerate(timestamps):
        bucket_table.append(
            {
                "timestamp": ts.isoformat(),
                "count": total_counts[idx],
                "avg_value": round(bucket_sums[idx] / bucket_hits[idx], 2)
                if bucket_hits[idx]
                else None,
            }
        )

    return (
        {
            "hardwares": results,
            "timestamps": [t.isoformat() for t in timestamps],
            "interval_minutes": interval,
        },
        total_counts,
        bucket_table,
    )


def _build_overall_stats(total_counts, start, end, interval, active_events):
    if not total_counts:
        return {
            "current": 0,
            "average": 0,
            "peak": 0,
            "change": "—",
            "anomalies": 0,
            "active_events": active_events,
        }
    current = total_counts[-1]
    average = round(sum(total_counts) / len(total_counts), 2)
    peak = max(total_counts)
    p95 = _percentile(sorted(total_counts), 95)
    anomalies = sum(1 for c in total_counts if c > p95)

    previous_start = start - (end - start)
    previous_end = start
    change = "—"
    try:
        from app.models import Event

        prev_events = (
            Event.query.filter(Event.timestamp >= previous_start)
            .filter(Event.timestamp <= previous_end)
            .all()
        )
        prev_active = sum(1 for e in prev_events if e.value and e.value > 0)
        if prev_active > 0:
            change = f"{round(((active_events - prev_active) / prev_active) * 100, 1)}%"
    except Exception:
        change = "—"

    return {
        "current": current,
        "average": average,
        "peak": peak,
        "change": change,
        "anomalies": anomalies,
        "active_events": active_events,
    }


def _build_distribution(total_counts):
    buckets = {"0": 0, "1-2": 0, "3-5": 0, "6-10": 0, ">10": 0}
    for count in total_counts:
        if count == 0:
            buckets["0"] += 1
        elif count <= 2:
            buckets["1-2"] += 1
        elif count <= 5:
            buckets["3-5"] += 1
        elif count <= 10:
            buckets["6-10"] += 1
        else:
            buckets[">10"] += 1
    return [{"bucket": key, "count": buckets[key]} for key in buckets]


def _build_hourly_distribution(events):
    counts = {f"{h:02d}": 0 for h in range(24)}
    for evt in events:
        if evt.value and evt.value > 0:
            counts[f"{evt.timestamp.hour:02d}"] += 1
    return [{"hour": key, "count": counts[key]} for key in counts]


def _build_top_contributors(summary, limit=6):
    sorted_items = sorted(summary, key=lambda x: x.get("active_events", 0), reverse=True)
    return [
        {"name": item["name"], "active_events": item.get("active_events", 0)}
        for item in sorted_items[:limit]
    ]


def _cache_get(key):
    entry = _CACHE.get(key)
    if not entry:
        _load_cache_file()
        entry = _CACHE.get(key)
        if not entry:
            return None
    if datetime.now().timestamp() - entry["ts"] > _CACHE_TTL_SECONDS:
        _CACHE.pop(key, None)
        return None
    return entry["payload"]


def _cache_set(key, payload):
    _CACHE[key] = {"ts": datetime.now().timestamp(), "payload": payload}
    _persist_cache_file()


def _percentile(values, percentile):
    if not values:
        return 0
    k = (len(values) - 1) * (percentile / 100)
    f = int(k)
    c = min(f + 1, len(values) - 1)
    if f == c:
        return values[int(k)]
    d0 = values[f] * (c - k)
    d1 = values[c] * (k - f)
    return round(d0 + d1, 2)


def _accumulate_open_time(open_by_hour, open_by_day, start, end):
    current = start
    while current < end:
        next_point = min(
            end,
            current.replace(minute=59, second=59, microsecond=999999),
        )
        seconds = (next_point - current).total_seconds()
        hour_key = current.strftime("%H:00")
        day_key = current.strftime("%Y-%m-%d")
        open_by_hour[hour_key] = open_by_hour.get(hour_key, 0) + seconds
        open_by_day[day_key] = open_by_day.get(day_key, 0) + seconds
        current = next_point + timedelta(microseconds=1)


def _sorted_minutes(data):
    return [
        {"bucket": key, "minutes": round(seconds / 60, 2)} for key, seconds in sorted(data.items())
    ]


def _resolve_hardware_type(hardware):
    raw_type = (hardware.type or "").lower()
    if raw_type in {"motion_sensor", "motion"}:
        return "motion"
    if raw_type in {"door", "contact_sensor", "reed_switch", "reed", "door_sensor"}:
        return "door"
    if raw_type in {"relay", "switch"}:
        return "relay"
    if raw_type in {"thermostat", "temperature_sensor"}:
        return "temperature"
    if raw_type in {"humidity_sensor"}:
        return "humidity"
    if raw_type in {"microphone"}:
        return "microphone"
    return raw_type or "generic"


def _load_cache_file():
    if not _CACHE_FILE.exists():
        return
    try:
        raw = json.loads(_CACHE_FILE.read_text())
        if isinstance(raw, dict):
            _CACHE.update(raw)
    except Exception:
        return


def _persist_cache_file():
    try:
        _CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        if len(_CACHE) > _CACHE_FILE_LIMIT:
            keys = sorted(_CACHE.keys(), key=lambda k: _CACHE[k]["ts"], reverse=True)
            for key in keys[_CACHE_FILE_LIMIT:]:
                _CACHE.pop(key, None)
        _CACHE_FILE.write_text(json.dumps(_CACHE))
    except Exception:
        return


@bp.route("/health", methods=["GET"])
def health_check():
    """
    Returns the health status of all registered services.
    """
    service_manager = current_app.service_manager

    # Get health data from all services
    health_data = service_manager.health_check()

    # Calculate summary statistics
    total = len(health_data)
    running = sum(1 for svc in health_data.values() if svc.get("running", False))
    stopped = total - running

    # Determine overall status
    if running == total:
        status = "healthy"
    elif running > 0:
        status = "degraded"
    else:
        status = "unhealthy"

    return jsonify(
        {
            "status": status,
            "timestamp": datetime.now().isoformat(),
            "services": health_data,
            "summary": {"total": total, "running": running, "stopped": stopped},
        }
    )


# ================================
# SEQUENCE PROCESSING ROUTES
# ================================
"""

@bp.route("/sequences/process", methods=["POST"])
def process_sequences():
    try:
        processor = get_services().get_processor()
        data = request.json or {}

        result = processor.process_sequences(
            window_size=data.get("window_size", 60),
            sequence_gap_threshold=data.get("sequence_gap_threshold", 300),
            incremental=data.get("incremental", False),
        )
        processor.save_persistent_state()

        return jsonify(
            {
                "success": True,
                "result": result,
                "message": "Processing completed",
                "timestamp": datetime.now().isoformat(),
            }
        )
    except Exception as e:
        current_app.logger.error(f"Sequence processing error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@bp.route("/sequences/list")
def get_sequences_list():
    try:
        processor = get_services().get_processor()
        result = processor.get_sequence_list(
            page=request.args.get("page", 1, type=int),
            per_page=request.args.get("per_page", 20, type=int),
        )
        return jsonify({"success": True, **result, "timestamp": datetime.now().isoformat()})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@bp.route("/sequences/<int:sequence_id>")
def get_sequence_detail(sequence_id):
    try:
        processor = get_services().get_processor()
        sequence = processor.get_sequence(sequence_id)
        if not sequence:
            return jsonify({"success": False, "error": "Sequence not found"}), 404

        return jsonify(
            {
                "success": True,
                "sequence": sequence,
                "timestamp": datetime.now().isoformat(),
            }
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@bp.route("/sequences/<int:sequence_id>/label", methods=["PUT"])
def update_sequence_label(sequence_id):
    try:
        processor = get_services().get_processor()
        label = request.json.get("label")
        if not label:
            return jsonify({"success": False, "error": "Label is required"}), 400

        if processor.update_sequence_label(sequence_id, label):
            processor.save_persistent_state()
            return jsonify(
                {
                    "success": True,
                    "message": f"Label updated to {label}",
                    "timestamp": datetime.now().isoformat(),
                }
            )
        return jsonify({"success": False, "error": "Update failed"}), 400
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@bp.route("/sequences/statistics")
def get_label_statistics():
    try:
        processor = get_services().get_processor()
        return jsonify(
            {
                "success": True,
                "statistics": processor.get_label_statistics(),
                "timestamp": datetime.now().isoformat(),
            }
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
"""
