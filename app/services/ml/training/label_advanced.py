import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import pandas as pd


class hardwaresequenceProcessor:
    """
    Processes hardware activity data into sequences for labeling.
    Handles windowing, sequence identification, persistent storage, and incremental updates.
    """

    def __init__(self, csv_path: str = "hardware_activity.csv"):
        """
        Initialize the processor.

        Args:
            csv_path: Path to the hardware activity CSV file
        """
        self.csv_path = csv_path
        self.df = None
        self.pivoted_windowed = None
        self.sequences = []
        self.hardware_names = []

        # Current configuration
        self.window_size = 60
        self.sequence_gap_threshold = 300
        self.min_sequence_length = 3

        # Processing state
        self.last_processed_timestamp = None
        self.last_processed_row = 0

    def _get_config_filename(self) -> str:
        """Generate filename based on current configuration."""
        return f"sequence_labels_{self.window_size}_{self.sequence_gap_threshold}_{self.min_sequence_length}.json"

    def load_data(self, from_timestamp: Optional[pd.Timestamp] = None) -> Dict:
        """
        Load raw hardware data from CSV, optionally starting from a specific timestamp.

        Args:
            from_timestamp: Load only data after this timestamp (for incremental processing)

        Returns:
            Dictionary with loading stats
        """
        try:
            # Load all data
            self.df = pd.read_csv(self.csv_path, parse_dates=["timestamp"])
            self.df = self.df.sort_values("timestamp")

            # Filter by timestamp if specified
            if from_timestamp is not None:
                # Include a small buffer before the timestamp to catch events that might
                # belong to the last window
                buffer_time = from_timestamp - timedelta(seconds=self.window_size)
                self.df = self.df[self.df["timestamp"] > buffer_time]

            return {
                "success": True,
                "record_count": len(self.df),
                "date_range": {
                    "start": self.df.timestamp.min().isoformat() if len(self.df) > 0 else None,
                    "end": self.df.timestamp.max().isoformat() if len(self.df) > 0 else None,
                },
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def process_sequences(
        self,
        window_size: int = 60,
        sequence_gap_threshold: int = 300,
        min_sequence_length: int = 3,
        incremental: bool = False,
    ) -> Dict:
        """
        Process hardware data into sequences based on configuration.

        Args:
            window_size: Seconds per window (default 60)
            sequence_gap_threshold: Seconds gap to consider new sequence (default 300)
            min_sequence_length: Minimum windows per sequence (default 3)
            incremental: If True, append to existing sequences; if False, reprocess all

        Returns:
            Dictionary with processing results
        """
        # Update configuration
        self.window_size = window_size
        self.sequence_gap_threshold = sequence_gap_threshold
        self.min_sequence_length = min_sequence_length

        config_file = self._get_config_filename()

        # Try to load existing data if incremental
        if incremental and os.path.exists(config_file):
            # Load existing state from JSON
            load_result = self.load_persistent_state(config_file)
            if not load_result["success"]:
                return load_result

            # Check if there's new data to process
            initial_sequence_count = len(self.sequences)
            result = self._process_incremental()
            result["new_sequences"] = len(self.sequences) - initial_sequence_count
            return result

        # Full reprocessing
        load_result = self.load_data()
        if not load_result["success"]:
            return load_result

        try:
            # Pivot data to multivariate format
            pivoted = self.df.pivot_table(
                index="timestamp", columns="hardware_name", values="state", aggfunc="sum"
            )
            pivoted = pivoted.fillna(0)

            # Resample into fixed windows
            self.pivoted_windowed = pivoted.resample(f"{window_size}s").sum().fillna(0)
            self.hardware_names = list(self.pivoted_windowed.columns)

            # Identify sequences
            self.sequences = self._identify_sequences()

            # Update processing state
            if len(self.df) > 0:
                self.last_processed_timestamp = self.df.timestamp.max()
                # Get the actual row count from the CSV
                with open(self.csv_path, "r") as f:
                    self.last_processed_row = sum(1 for _ in f) - 1  # -1 for header

            return {
                "success": True,
                "window_count": len(self.pivoted_windowed),
                "sequence_count": len(self.sequences),
                "new_sequences": len(self.sequences),
                "hardware_names": self.hardware_names,
                "config": {
                    "window_size": window_size,
                    "sequence_gap_threshold": sequence_gap_threshold,
                    "min_sequence_length": min_sequence_length,
                },
                "last_processed_timestamp": self.last_processed_timestamp.isoformat()
                if self.last_processed_timestamp
                else None,
                "last_processed_row": self.last_processed_row,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _process_incremental(self) -> Dict:
        """Process new data and append to existing sequences."""
        try:
            # Load only new data from CSV
            load_result = self.load_data(from_timestamp=self.last_processed_timestamp)
            if not load_result["success"]:
                return load_result

            # Check if there's actually new data
            if len(self.df) == 0 or (
                self.last_processed_timestamp
                and self.df.timestamp.max() <= self.last_processed_timestamp
            ):
                return {
                    "success": True,
                    "message": "No new data to process",
                    "window_count": len(self.pivoted_windowed)
                    if self.pivoted_windowed is not None
                    else 0,
                    "sequence_count": len(self.sequences),
                    "new_sequences": 0,
                }

            # Only process the truly new data (after last_processed_timestamp)
            new_data = (
                self.df[self.df["timestamp"] > self.last_processed_timestamp]
                if self.last_processed_timestamp
                else self.df
            )

            if len(new_data) == 0:
                return {
                    "success": True,
                    "message": "No new data to process",
                    "window_count": len(self.pivoted_windowed)
                    if self.pivoted_windowed is not None
                    else 0,
                    "sequence_count": len(self.sequences),
                    "new_sequences": 0,
                }

            # Pivot new data
            pivoted_new = new_data.pivot_table(
                index="timestamp", columns="hardware_name", values="state", aggfunc="sum"
            )
            pivoted_new = pivoted_new.fillna(0)

            # Ensure all existing hardwares are present in new data
            for hardware in self.hardware_names:
                if hardware not in pivoted_new.columns:
                    pivoted_new[hardware] = 0

            # Also check for new hardwares
            for hardware in pivoted_new.columns:
                if hardware not in self.hardware_names:
                    # Add new hardware to existing data with zeros
                    self.pivoted_windowed[hardware] = 0
                    self.hardware_names.append(hardware)

            # Reorder columns to match
            pivoted_new = pivoted_new[self.hardware_names]

            # Resample new data into windows
            pivoted_windowed_new = pivoted_new.resample(f"{self.window_size}s").sum().fillna(0)

            # Check if we need to update the last window of existing data
            # This handles the case where new events fall into an already-existing window
            if self.pivoted_windowed is not None and len(self.pivoted_windowed) > 0:
                last_existing_window = self.pivoted_windowed.index[-1]

                # Find overlapping windows in new data
                overlapping = pivoted_windowed_new[
                    pivoted_windowed_new.index == last_existing_window
                ]
                if len(overlapping) > 0:
                    # Update the last window with new data
                    self.pivoted_windowed.loc[last_existing_window] += overlapping.iloc[0]
                    # Remove the overlapping window from new data
                    pivoted_windowed_new = pivoted_windowed_new[
                        pivoted_windowed_new.index > last_existing_window
                    ]

            # Append truly new windows
            if len(pivoted_windowed_new) > 0:
                if self.pivoted_windowed is None:
                    self.pivoted_windowed = pivoted_windowed_new
                else:
                    self.pivoted_windowed = pd.concat([self.pivoted_windowed, pivoted_windowed_new])
                    self.pivoted_windowed = self.pivoted_windowed.sort_index()

            # Update sequences (check if last sequence needs to be extended or if new sequences exist)
            self._update_sequences_incremental()

            # Update processing state
            self.last_processed_timestamp = new_data.timestamp.max()
            with open(self.csv_path, "r") as f:
                self.last_processed_row = sum(1 for _ in f) - 1  # -1 for header

            return {
                "success": True,
                "window_count": len(self.pivoted_windowed),
                "sequence_count": len(self.sequences),
                "hardware_names": self.hardware_names,
                "last_processed_timestamp": self.last_processed_timestamp.isoformat(),
                "last_processed_row": self.last_processed_row,
                "mode": "incremental",
            }
        except Exception as e:
            return {"success": False, "error": str(e), "mode": "incremental"}

    def _update_sequences_incremental(self):
        """Update sequences based on new windowed data, preserving existing labels."""
        if len(self.sequences) == 0:
            # No existing sequences, identify all
            self.sequences = self._identify_sequences()
            return

        # Store existing labels
        existing_labels = {}
        for seq in self.sequences:
            key = (seq["start_time"], seq["end_time"])
            existing_labels[key] = seq["label"]

        # Get the last sequence
        last_seq = self.sequences[-1]
        last_seq_end = last_seq["end_time"]

        # Check for new activity after the last sequence
        new_windows = self.pivoted_windowed[self.pivoted_windowed.index > last_seq_end]

        if len(new_windows) == 0:
            # Check if last sequence should be extended
            # Look at windows that might extend the last sequence
            check_from = last_seq["start_time"]
            recent_windows = self.pivoted_windowed[self.pivoted_windowed.index >= check_from]

            # Re-identify just the last sequence area
            current_windows = []
            last_activity_time = None

            for timestamp, row in recent_windows.iterrows():
                has_activity = row.sum() > 0
                if has_activity:
                    if (
                        last_activity_time is None
                        or (timestamp - last_activity_time).total_seconds()
                        <= self.sequence_gap_threshold
                    ):
                        current_windows.append(timestamp)
                        last_activity_time = timestamp

            if (
                len(current_windows) >= self.min_sequence_length
                and last_activity_time > last_seq["end_time"]
            ):
                # Extend the last sequence
                last_seq["end_time"] = last_activity_time
                last_seq["windows"] = current_windows
                last_seq["window_count"] = len(current_windows)
                last_seq["duration_minutes"] = (
                    last_activity_time - last_seq["start_time"]
                ).total_seconds() / 60
                # Update raw events for the extended sequence
                self._update_sequence_raw_events(last_seq)
        else:
            # Process new windows for potential new sequences
            current_sequence_start = None
            current_sequence_windows = []
            last_activity_time = last_seq_end

            for timestamp, row in new_windows.iterrows():
                has_activity = row.sum() > 0

                if has_activity:
                    gap_from_last = (timestamp - last_activity_time).total_seconds()

                    if current_sequence_start is None:
                        # Check gap from last sequence
                        if gap_from_last <= self.sequence_gap_threshold:
                            # Extend the last sequence
                            last_seq["windows"].append(timestamp)
                            last_seq["end_time"] = timestamp
                            last_seq["window_count"] = len(last_seq["windows"])
                            last_seq["duration_minutes"] = (
                                timestamp - last_seq["start_time"]
                            ).total_seconds() / 60
                            self._update_sequence_raw_events(last_seq)
                        else:
                            # Start new sequence
                            current_sequence_start = timestamp
                            current_sequence_windows = [timestamp]
                    else:
                        # Check if continuing current new sequence
                        if gap_from_last > self.sequence_gap_threshold:
                            # Save current sequence if long enough
                            if len(current_sequence_windows) >= self.min_sequence_length:
                                new_seq = self._create_sequence_dict(
                                    current_sequence_start,
                                    last_activity_time,
                                    current_sequence_windows,
                                    (
                                        current_sequence_start - self.sequences[-1]["end_time"]
                                    ).total_seconds(),
                                    len(self.sequences) + 1,
                                )
                                self.sequences.append(new_seq)
                            # Start new sequence
                            current_sequence_start = timestamp
                            current_sequence_windows = [timestamp]
                        else:
                            current_sequence_windows.append(timestamp)

                    last_activity_time = timestamp

            # Don't forget the last sequence being built
            if (
                current_sequence_start is not None
                and len(current_sequence_windows) >= self.min_sequence_length
            ):
                new_seq = self._create_sequence_dict(
                    current_sequence_start,
                    last_activity_time,
                    current_sequence_windows,
                    (current_sequence_start - self.sequences[-1]["end_time"]).total_seconds(),
                    len(self.sequences) + 1,
                )
                self.sequences.append(new_seq)

    def _update_sequence_raw_events(self, sequence: Dict):
        """Update raw events for a sequence."""
        # Reload the full CSV to get raw events (this is quick for just one sequence)
        df_full = pd.read_csv(self.csv_path, parse_dates=["timestamp"])
        mask = (df_full["timestamp"] >= sequence["start_time"]) & (
            df_full["timestamp"] <= sequence["end_time"]
        )
        sequence_events = df_full[mask]
        sequence["raw_events"] = sequence_events.to_dict("records")

    def _identify_sequences(self) -> List[Dict]:
        """
        Identify sequences of activity separated by gaps.
        Preserves existing labels when sequences are re-identified.

        Returns:
            List of sequence dictionaries
        """
        # Store existing labels by time range for preservation
        existing_labels = {}
        for seq in self.sequences:
            key = (seq["start_time"], seq["end_time"])
            existing_labels[key] = seq["label"]

        sequences = []
        current_sequence_start = None
        current_sequence_windows = []
        last_activity_time = None

        for timestamp, row in self.pivoted_windowed.iterrows():
            has_activity = row.sum() > 0

            if has_activity:
                if current_sequence_start is None:
                    # Start new sequence
                    current_sequence_start = timestamp
                    current_sequence_windows = [timestamp]
                else:
                    # Check if gap is too large
                    gap = (timestamp - last_activity_time).total_seconds()
                    if gap > self.sequence_gap_threshold:
                        # End current sequence and start new one
                        if len(current_sequence_windows) >= self.min_sequence_length:
                            time_since_last = 0 if not sequences else gap
                            new_seq = self._create_sequence_dict(
                                current_sequence_start,
                                last_activity_time,
                                current_sequence_windows,
                                time_since_last,
                                len(sequences) + 1,
                            )
                            # Restore label if it exists
                            key = (new_seq["start_time"], new_seq["end_time"])
                            if key in existing_labels:
                                new_seq["label"] = existing_labels[key]
                            sequences.append(new_seq)

                        current_sequence_start = timestamp
                        current_sequence_windows = [timestamp]
                    else:
                        # Continue current sequence
                        current_sequence_windows.append(timestamp)

                last_activity_time = timestamp

        # Don't forget the last sequence
        if (
            current_sequence_start is not None
            and len(current_sequence_windows) >= self.min_sequence_length
        ):
            gap_from_previous = 0
            if sequences:
                gap_from_previous = (
                    current_sequence_start - sequences[-1]["end_time"]
                ).total_seconds()

            new_seq = self._create_sequence_dict(
                current_sequence_start,
                last_activity_time,
                current_sequence_windows,
                gap_from_previous,
                len(sequences) + 1,
            )
            # Restore label if it exists
            key = (new_seq["start_time"], new_seq["end_time"])
            if key in existing_labels:
                new_seq["label"] = existing_labels[key]
            sequences.append(new_seq)

        return sequences

    def _create_sequence_dict(
        self,
        start_time: pd.Timestamp,
        end_time: pd.Timestamp,
        windows: List[pd.Timestamp],
        time_since_last: float,
        sequence_id: int,
    ) -> Dict:
        """Create a sequence dictionary with all necessary information."""
        # Get raw hardware events for this sequence from the original dataframe
        raw_events = []
        if self.df is not None:
            # Filter events that fall within this sequence's time range
            mask = (self.df["timestamp"] >= start_time) & (self.df["timestamp"] <= end_time)
            sequence_events = self.df[mask].copy()

            # Convert to list of dictionaries for easier serialization
            raw_events = sequence_events.to_dict("records")

        return {
            "sequence_id": sequence_id,
            "start_time": start_time,
            "end_time": end_time,
            "windows": windows,
            "raw_events": raw_events,  # Store the original hardware events
            "duration_minutes": (end_time - start_time).total_seconds() / 60,
            "time_since_last_seq_hours": time_since_last / 3600,
            "window_count": len(windows),
            "label": None,  # To be set during labeling
        }

    def get_sequence_count(self) -> int:
        """Get total number of sequences."""
        return len(self.sequences)

    def get_sequence(self, sequence_id: int) -> Optional[Dict]:
        """
        Get a specific sequence by ID (1-indexed).

        Args:
            sequence_id: Sequence ID (1 to sequence_count)

        Returns:
            Dictionary with sequence data or None if not found
        """
        if sequence_id < 1 or sequence_id > len(self.sequences):
            return None

        # Ensure windowed data is loaded
        self._ensure_windowed_data()

        seq = self.sequences[sequence_id - 1]
        sequence_data = self.pivoted_windowed.loc[seq["windows"]]

        # Calculate activity summary
        activity_summary = {}
        for hardware in sequence_data.columns:
            total_activity = sequence_data[hardware].sum()
            if total_activity > 0:
                activity_summary[hardware] = float(total_activity)

        # Get all windows for detailed view
        all_windows = []
        for timestamp, row in sequence_data.iterrows():
            all_windows.append(
                {
                    "timestamp": timestamp.isoformat(),
                    "data": {hardware: float(val) for hardware, val in row.items()},
                }
            )

        # Format raw events for output
        raw_events = []
        for event in seq.get("raw_events", []):
            raw_events.append(
                {
                    "timestamp": event["timestamp"],
                    "hardware_name": event["hardware_name"],
                    "hardware_type": event["hardware_type"],
                    "gpio_pin": event["gpio_pin"],
                    "state": event["state"],
                    "event": event["event"],
                }
            )

        return {
            "sequence_id": seq["sequence_id"],
            "start_time": seq["start_time"].isoformat(),
            "end_time": seq["end_time"].isoformat(),
            "duration_minutes": seq["duration_minutes"],
            "time_since_last_seq_hours": seq["time_since_last_seq_hours"],
            "window_count": seq["window_count"],
            "label": seq["label"],
            "activity_summary": activity_summary,
            "all_windows": all_windows,
            "raw_events": raw_events,
            "hardware_names": self.hardware_names,
        }

    def get_sequence_list(self, page: int = 1, per_page: int = 20) -> Dict:
        """
        Get paginated list of sequences (summary only).

        Args:
            page: Page number (1-indexed)
            per_page: Number of sequences per page

        Returns:
            Dictionary with paginated sequence summaries
        """
        total = len(self.sequences)
        total_pages = (total + per_page - 1) // per_page

        start_idx = (page - 1) * per_page
        end_idx = min(start_idx + per_page, total)

        sequences_page = []
        for seq in self.sequences[start_idx:end_idx]:
            sequences_page.append(
                {
                    "sequence_id": seq["sequence_id"],
                    "start_time": seq["start_time"].isoformat(),
                    "end_time": seq["end_time"].isoformat(),
                    "duration_minutes": seq["duration_minutes"],
                    "time_since_last_seq_hours": seq["time_since_last_seq_hours"],
                    "window_count": seq["window_count"],
                    "label": seq["label"],
                }
            )

        return {
            "sequences": sequences_page,
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": total,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1,
            },
        }

    def update_sequence_label(self, sequence_id: int, label: str) -> bool:
        """
        Update the label for a specific sequence.

        Args:
            sequence_id: Sequence ID (1-indexed)
            label: One of 'Ignore', 'Log', 'Notify', 'Alarm'

        Returns:
            True if successful, False otherwise
        """
        if sequence_id < 1 or sequence_id > len(self.sequences):
            return False

        if label not in ["Ignore", "Log", "Notify", "Alarm"]:
            return False

        self.sequences[sequence_id - 1]["label"] = label
        return True

    def get_label_statistics(self) -> Dict:
        """
        Get statistics about labeled sequences.

        Returns:
            Dictionary with label counts and percentages
        """
        total = len(self.sequences)
        labeled = sum(1 for seq in self.sequences if seq["label"] is not None)

        label_counts = {"Ignore": 0, "Log": 0, "Notify": 0, "Alarm": 0, "Unlabeled": 0}

        for seq in self.sequences:
            if seq["label"] is None:
                label_counts["Unlabeled"] += 1
            else:
                label_counts[seq["label"]] += 1

        return {
            "total_sequences": total,
            "labeled_sequences": labeled,
            "unlabeled_sequences": total - labeled,
            "label_counts": label_counts,
            "label_percentages": {
                label: (count / total * 100) if total > 0 else 0
                for label, count in label_counts.items()
            },
        }

    def save_persistent_state(self, output_path: Optional[str] = None) -> Dict:
        """
        Save complete processor state including sequences, labels, and processing metadata.
        Uses config-based filename if no path specified.

        Args:
            output_path: Custom path to save state (optional)

        Returns:
            Dictionary with save result
        """
        if output_path is None:
            output_path = self._get_config_filename()

        try:
            state_data = {
                "metadata": {
                    "created_at": datetime.now().isoformat(),
                    "last_processed_timestamp": self.last_processed_timestamp.isoformat()
                    if self.last_processed_timestamp
                    else None,
                    "last_processed_row": self.last_processed_row,
                    "csv_path": self.csv_path,
                    "hardware_names": self.hardware_names,
                },
                "config": {
                    "window_size": self.window_size,
                    "sequence_gap_threshold": self.sequence_gap_threshold,
                    "min_sequence_length": self.min_sequence_length,
                },
                "sequences": [
                    {
                        "sequence_id": seq["sequence_id"],
                        "start_time": seq["start_time"].isoformat(),
                        "end_time": seq["end_time"].isoformat(),
                        "duration_minutes": seq["duration_minutes"],
                        "time_since_last_seq_hours": seq["time_since_last_seq_hours"],
                        "window_count": seq["window_count"],
                        "label": seq["label"],
                        "windows": [w.isoformat() for w in seq["windows"]],
                        "raw_events": [
                            {
                                "timestamp": evt["timestamp"].isoformat()
                                if isinstance(evt["timestamp"], pd.Timestamp)
                                else evt["timestamp"],
                                "hardware_name": evt["hardware_name"],
                                "hardware_type": evt["hardware_type"],
                                "gpio_pin": evt["gpio_pin"],
                                "state": evt["state"],
                                "event": evt["event"],
                            }
                            for evt in seq.get("raw_events", [])
                        ],
                    }
                    for seq in self.sequences
                ],
            }

            with open(output_path, "w") as f:
                json.dump(state_data, f, indent=2)

            return {
                "success": True,
                "path": output_path,
                "sequence_count": len(self.sequences),
                "labeled_count": sum(1 for seq in self.sequences if seq["label"] is not None),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def load_persistent_state(self, input_path: Optional[str] = None) -> Dict:
        """
        Load processor state from JSON file. Simplified version that doesn't reconstruct
        the full windowed data unless needed for new processing.

        Args:
            input_path: Custom path to load state from (optional)

        Returns:
            Dictionary with load result
        """
        if input_path is None:
            input_path = self._get_config_filename()

        if not os.path.exists(input_path):
            return {"success": False, "error": f"File not found: {input_path}"}

        try:
            with open(input_path, "r") as f:
                state_data = json.load(f)

            # Restore metadata
            metadata = state_data["metadata"]
            self.last_processed_timestamp = (
                pd.to_datetime(metadata["last_processed_timestamp"])
                if metadata["last_processed_timestamp"]
                else None
            )
            self.last_processed_row = metadata["last_processed_row"]
            self.hardware_names = metadata["hardware_names"]
            self.csv_path = metadata.get("csv_path", self.csv_path)

            # Restore config
            config = state_data["config"]
            self.window_size = config["window_size"]
            self.sequence_gap_threshold = config["sequence_gap_threshold"]
            self.min_sequence_length = config["min_sequence_length"]

            # Restore sequences
            self.sequences = []
            for seq_data in state_data["sequences"]:
                # Reconstruct raw events with proper timestamps
                raw_events = []
                for evt in seq_data.get("raw_events", []):
                    raw_events.append(
                        {
                            "timestamp": evt["timestamp"].isoformat()
                            if isinstance(evt["timestamp"], pd.Timestamp)
                            else evt["timestamp"],
                            "hardware_name": evt.get("hardware_name"),
                            "hardware_type": evt.get("hardware_type"),
                            "gpio_pin": evt.get("gpio_pin"),
                            "state": evt.get("state"),
                            "event": evt.get("event"),
                        }
                    )

                self.sequences.append(
                    {
                        "sequence_id": seq_data["sequence_id"],
                        "start_time": pd.to_datetime(seq_data["start_time"]),
                        "end_time": pd.to_datetime(seq_data["end_time"]),
                        "duration_minutes": seq_data["duration_minutes"],
                        "time_since_last_seq_hours": seq_data["time_since_last_seq_hours"],
                        "window_count": seq_data["window_count"],
                        "label": seq_data["label"],
                        "windows": [pd.to_datetime(w) for w in seq_data["windows"]],
                        "raw_events": raw_events,
                    }
                )

            # Only reconstruct windowed data if we need it (will be done lazily when needed)
            self.pivoted_windowed = None

            return {
                "success": True,
                "path": input_path,
                "sequence_count": len(self.sequences),
                "labeled_count": sum(1 for seq in self.sequences if seq["label"] is not None),
                "last_processed_timestamp": self.last_processed_timestamp.isoformat()
                if self.last_processed_timestamp
                else None,
                "last_processed_row": self.last_processed_row,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _ensure_windowed_data(self):
        """
        Ensure windowed data is loaded. This is called when we need to access pivoted_windowed.
        Reconstructs it from the CSV if not already loaded.
        """
        if self.pivoted_windowed is not None:
            return

        try:
            # Load all data up to last processed timestamp
            df_full = pd.read_csv(self.csv_path, parse_dates=["timestamp"])

            if self.last_processed_timestamp:
                df_full = df_full[df_full["timestamp"] <= self.last_processed_timestamp]

            df_full = df_full.sort_values("timestamp")

            # Pivot and window the data
            pivoted = df_full.pivot_table(
                index="timestamp", columns="hardware_name", values="state", aggfunc="sum"
            )
            pivoted = pivoted.fillna(0)

            # Ensure all known hardwares are present
            for hardware in self.hardware_names:
                if hardware not in pivoted.columns:
                    pivoted[hardware] = 0

            self.pivoted_windowed = pivoted.resample(f"{self.window_size}s").sum().fillna(0)
        except Exception as e:
            print(f"Error reconstructing windowed data: {e}")
            self.pivoted_windowed = pd.DataFrame()  # Empty dataframe as fallback
