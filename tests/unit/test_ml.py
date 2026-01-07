from datetime import datetime, timedelta

import pandas as pd
import pytest

from app.services.ml.training.label_advanced import SensorSequenceProcessor


@pytest.fixture
def sample_csv(tmp_path):
    """Create a temporary CSV file with sample sensor data."""
    file_path = tmp_path / "test_activity.csv"

    # Generate 5 minutes of data
    base_time = datetime(2025, 1, 1, 12, 0, 0)
    data = []

    # Burst 1: 0-2 mins
    data.append([base_time, "Kitchen", "motion", 1, 1, "Motion Detected"])
    data.append([base_time + timedelta(seconds=30), "Kitchen", "motion", 1, 0, "Motion Cleared"])
    data.append([base_time + timedelta(seconds=60), "Kitchen", "motion", 1, 1, "Motion Detected"])

    # Gap: 5 mins silence

    # Burst 2: 7-8 mins
    burst2_time = base_time + timedelta(minutes=7)
    data.append([burst2_time, "Kitchen", "motion", 1, 1, "Motion Detected"])

    df = pd.DataFrame(
        data, columns=["timestamp", "sensor_name", "sensor_type", "gpio_pin", "state", "event"]
    )
    df.to_csv(file_path, index=False)
    return str(file_path)


def test_sequence_identification(sample_csv):
    """Test that the processor correctly groups events into sequences."""
    processor = SensorSequenceProcessor(csv_path=sample_csv)

    # Process with small window/gap for testing
    result = processor.process_sequences(
        window_size=60,
        sequence_gap_threshold=120,  # 2 min gap triggers new sequence
        min_sequence_length=1,  # Allow short sequences for this test
    )

    assert result["success"] is True
    # We expect 2 sequences because of the 5 minute gap between Burst 1 and Burst 2
    assert result["sequence_count"] == 2

    seq1 = processor.get_sequence(1)
    assert seq1["window_count"] > 0

    seq2 = processor.get_sequence(2)
    assert seq2 is not None
