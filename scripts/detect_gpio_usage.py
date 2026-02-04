import argparse
import os
import sys
from collections import defaultdict
from typing import Dict, Iterable, List, Tuple

from dotenv import load_dotenv

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def _is_pin_key(key: str) -> bool:
    lowered = key.lower()
    return "pin" in lowered or "gpio" in lowered


def _extract_pins(value, path: str = "configuration") -> List[Tuple[str, int]]:
    pins: List[Tuple[str, int]] = []

    if isinstance(value, dict):
        for key, nested in value.items():
            nested_path = f"{path}.{key}"
            if _is_pin_key(key) and isinstance(nested, int):
                pins.append((nested_path, nested))
            pins.extend(_extract_pins(nested, nested_path))
    elif isinstance(value, list):
        for idx, nested in enumerate(value):
            nested_path = f"{path}[{idx}]"
            if isinstance(nested, int) and "pins" in path.lower():
                pins.append((nested_path, nested))
            pins.extend(_extract_pins(nested, nested_path))

    return pins


def _format_row(cols: Iterable[str], widths: List[int]) -> str:
    return "  ".join(str(col).ljust(width) for col, width in zip(cols, widths))


def main():
    from app import create_app
    from app.models import Hardware
    from config import get_config

    parser = argparse.ArgumentParser(
        description="Detect GPIO pin usage from hardware config records."
    )
    parser.add_argument(
        "--include-disabled",
        action="store_true",
        help="Include disabled hardware records in the report.",
    )
    args = parser.parse_args()

    load_dotenv()
    app = create_app(get_config())

    with app.app_context():
        query = Hardware.query
        if not args.include_disabled:
            query = query.filter_by(enabled=True)

        hardware_rows = query.order_by(Hardware.id.asc()).all()

    pin_usage: Dict[int, List[Dict[str, str]]] = defaultdict(list)
    extracted_rows: List[Tuple[str, str, str, str, str]] = []

    for hw in hardware_rows:
        config = hw.configuration or {}
        pins = _extract_pins(config)
        if not pins:
            continue

        for path, pin in pins:
            record = {
                "hardware_id": str(hw.id),
                "name": hw.name,
                "driver": hw.driver_interface,
                "path": path,
            }
            pin_usage[pin].append(record)
            extracted_rows.append(
                (
                    str(pin),
                    str(hw.id),
                    hw.name,
                    hw.driver_interface,
                    path,
                )
            )

    if not extracted_rows:
        scope = "enabled" if not args.include_disabled else "all"
        print(f"No GPIO pins found in {scope} hardware configuration.")
        return

    extracted_rows.sort(key=lambda row: (int(row[0]), int(row[1])))
    headers = ["PIN", "HW_ID", "NAME", "DRIVER", "CONFIG_PATH"]
    widths = [max(len(h), *(len(row[i]) for row in extracted_rows)) for i, h in enumerate(headers)]

    print(_format_row(headers, widths))
    print(_format_row(["-" * len(h) for h in headers], widths))
    for row in extracted_rows:
        print(_format_row(row, widths))

    conflicts = {pin: refs for pin, refs in pin_usage.items() if len(refs) > 1}
    print("")
    print(f"Total configured pins: {len(pin_usage)}")
    print(f"Total pin references: {len(extracted_rows)}")
    print(f"Pin conflicts (shared pins): {len(conflicts)}")

    if conflicts:
        print("")
        print("Conflicts:")
        for pin in sorted(conflicts):
            print(f"- GPIO {pin}")
            for ref in conflicts[pin]:
                print(
                    f"  • hw_id={ref['hardware_id']} name={ref['name']} "
                    f"driver={ref['driver']} path={ref['path']}"
                )


if __name__ == "__main__":
    main()
