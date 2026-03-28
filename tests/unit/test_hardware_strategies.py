from app.services.hardware_strategies import parse_serial_line


def test_parse_serial_line_json_readings():
    updates = parse_serial_line(
        '{"readings":[{"sensor":"front_door","value":"1"},{"sensor":"hall_temp","value":"22.5","unit":"celsius"}]}'
    )

    assert len(updates) == 2
    assert updates[0]["key"] == "front_door"
    assert updates[0]["value"] == 1.0
    assert updates[1]["key"] == "hall_temp"
    assert updates[1]["value"] == 22.5
    assert updates[1]["unit"] == "celsius"


def test_parse_serial_line_csv_and_mapping_key():
    updates = parse_serial_line("garage_motion,ON")

    assert updates == [
        {
            "key": "garage_motion",
            "value": 1.0,
            "unit": None,
            "payload": {
                "source_key": "garage_motion",
                "value": "ON",
                "unit": None,
            },
        }
    ]
