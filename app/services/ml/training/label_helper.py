import json
import random
from datetime import datetime


class SequenceLabelingHelper:
    """
    Helper tool to efficiently label hardware sequences
    """

    def __init__(self, json_path):
        self.json_path = json_path
        with open(json_path, "r") as f:
            self.data = json.load(f)

        # Preserve metadata and config
        self.metadata = self.data.get("metadata", {})
        self.config = self.data.get("config", {})
        self.sequences = self.data["sequences"]

    def analyze_dataset(self):
        """Get overview of unlabeled sequences"""
        print("=" * 60)
        print("DATASET ANALYSIS")
        print("=" * 60)

        labeled = sum(1 for s in self.sequences if s.get("label") not in [None, ""])
        unlabeled = len(self.sequences) - labeled

        print(f"Total sequences: {len(self.sequences)}")
        print(f"Labeled: {labeled}")
        print(f"Unlabeled: {unlabeled}")

        if labeled > 0:
            label_dist = {}
            for s in self.sequences:
                if s.get("label"):
                    label_dist[s["label"]] = label_dist.get(s["label"], 0) + 1
            print("\nLabel distribution:")
            for label, count in sorted(label_dist.items()):
                print(f"  {label}: {count}")

        # Analyze characteristics
        print("\n" + "=" * 60)
        print("SEQUENCE CHARACTERISTICS")
        print("=" * 60)

        durations = [s["duration_minutes"] for s in self.sequences]
        events = [len(s["raw_events"]) for s in self.sequences]

        print(
            f"Duration (min) - Min: {min(durations):.1f}, Max: {max(durations):.1f}, Avg: {sum(durations) / len(durations):.1f}"
        )
        print(
            f"Events - Min: {min(events)}, Max: {max(events)}, Avg: {sum(events) / len(events):.1f}"
        )

        # Time distribution
        hours = [datetime.fromisoformat(s["start_time"]).hour for s in self.sequences]
        night_sequences = sum(1 for h in hours if h >= 22 or h <= 6)
        print(f"Night sequences (10pm-6am): {night_sequences}")

    def suggest_label_rule_based(self, sequence):
        """
        Suggest a label based on heuristics
        YOU SHOULD CUSTOMIZE THESE RULES FOR YOUR SPECIFIC USE CASE!
        """
        duration = sequence["duration_minutes"]
        events = len(sequence["raw_events"])
        hour = datetime.fromisoformat(sequence["start_time"]).hour

        # Count specific events
        door_events = sum(1 for e in sequence["raw_events"] if "Door" in e.get("event", ""))
        motion_events = sum(1 for e in sequence["raw_events"] if "Motion" in e.get("event", ""))

        first_event = sequence["raw_events"][0]["hardware_name"]
        last_event = sequence["raw_events"][-1]["hardware_name"]

        suggestions = []
        confidence = "LOW"

        # EXAMPLE RULES - CUSTOMIZE THESE!
        # Hallway, Living Room, Kitchen, Door

        # Rule 1: Very short sequences with minimal activity
        if duration < 2 and events < 5:
            suggestions.append("Ignore")
            confidence = "MEDIUM"
            reason = "Very brief activity, likely false trigger"

        # Rule 2: Night-time activity (midnight to 4am)
        elif hour >= 0 and hour <= 4:
            # Sequences that DON'T start with door opening
            if first_event != "Door":
                if first_event == "Kitchen" or first_event == "Living Room":
                    suggestions.append("Notify")
                    confidence = "HIGH"
                    reason = (
                        "Strange night activity starting in Kitchen/Living Room without door entry"
                    )
                else:
                    suggestions.append("Log")
                    confidence = "MEDIUM"
                    reason = "Night movement without door entry"

            # Sequences that start with door opening
            elif first_event == "Door":
                start_ts = datetime.fromisoformat(sequence["raw_events"][0]["timestamp"])
                end_ts = datetime.fromisoformat(sequence["raw_events"][-1]["timestamp"])
                door_open_duration = (end_ts - start_ts).total_seconds() / 60  # duration in minutes
                if door_open_duration > 10 or door_events > 5:
                    suggestions.append("Alarm")
                    confidence = "HIGH"
                    reason = f"Door open too long ({door_open_duration} units) or too frequently ({door_events} times) at night"
                else:
                    suggestions.append("Log")
                    confidence = "MEDIUM"
                    reason = "Normal door entry during night hours"
        # Rule 3: Day-time activity
        elif hour >= 9 and hour < 18:
            if first_event == "Kitchen" or first_event == "Living Room":
                suggestions.append("Notify")
                confidence = "HIGH"
                reason = "Daytime activity starting in Kitchen/Living Room without door entry - potential intrusion"
            elif first_event == "Hallway":
                if last_event == "Door":
                    suggestions.append("Log")
                    confidence = "MEDIUM"
                    reason = "Normal exit pattern - Hallway to Door during daytime"
                else:
                    suggestions.append("Ignore")
                    confidence = "MEDIUM"
                    reason = "Hallway movement without door exit - likely normal activity"
            else:
                suggestions.append("Notify")
                confidence = "MEDIUM"
                reason = "Daytime movement without door entry"

        # Rule 4: Night-time moderate activity
        elif (hour >= 23 or hour <= 5) and events > 10:
            suggestions.append("Notify")
            confidence = "MEDIUM"
            reason = "Moderate activity during night hours"

        # Rule 5: Extended normal activity
        elif duration > 30 and 20 < events < 150:
            suggestions.append("Log")
            confidence = "MEDIUM"
            reason = "Extended period of normal activity"

        # Rule 6: High intensity short burst
        elif duration < 10 and events > 60:
            suggestions.append("Notify")
            confidence = "MEDIUM"
            reason = "High intensity burst of activity"

        # Default
        else:
            suggestions.append("Ignore")
            confidence = "LOW"
            reason = "Default - needs manual review"

        return suggestions[0], confidence, reason

    def get_diverse_sample(self, n=100):
        """
        Get diverse sample of sequences for labeling
        Uses stratified sampling across characteristics
        """
        unlabeled = [s for s in self.sequences if not s.get("label") or s["label"] == ""]

        if len(unlabeled) < n:
            print(f"Only {len(unlabeled)} unlabeled sequences available")
            return unlabeled

        # Stratify by duration and time of day
        short = [s for s in unlabeled if s["duration_minutes"] < 5]
        medium = [s for s in unlabeled if 5 <= s["duration_minutes"] < 20]
        long = [s for s in unlabeled if s["duration_minutes"] >= 20]

        # Sample proportionally
        samples = []
        samples.extend(random.sample(short, min(n // 3, len(short))))
        samples.extend(random.sample(medium, min(n // 3, len(medium))))
        samples.extend(random.sample(long, min(n // 3, len(long))))

        # Fill remainder randomly
        if len(samples) < n:
            remaining = [s for s in unlabeled if s not in samples]
            samples.extend(random.sample(remaining, min(n - len(samples), len(remaining))))

        return samples[:n]

    def interactive_labeling_session(self, num_sequences=20):
        """
        Interactive labeling session with suggestions
        """
        print("\n" + "=" * 60)
        print("INTERACTIVE LABELING SESSION")
        print("=" * 60)
        print("Labels: (I)gnore, (L)og, (N)otify, (A)larm, (S)kip, (Q)uit")
        print("=" * 60 + "\n")

        to_label = self.get_diverse_sample(num_sequences)
        labeled_count = 0

        for i, seq in enumerate(to_label):
            print(f"\n--- Sequence {i + 1}/{len(to_label)} (ID: {seq['sequence_id']}) ---")
            print(f"Start: {seq['start_time']}")
            print(f"Duration: {seq['duration_minutes']:.1f} minutes")
            print(f"Events: {len(seq['raw_events'])}")
            print(f"Windows: {seq['window_count']}")

            # Show first few events
            print("\nFirst few events:")
            for event in seq["raw_events"][:5]:
                print(f"  {event['timestamp'][-12:]} - {event['hardware_name']}: {event['event']}")
            if len(seq["raw_events"]) > 5:
                print(f"  ... and {len(seq['raw_events']) - 5} more events")

            # Show suggestion
            suggested, confidence, reason = self.suggest_label_rule_based(seq)
            print(f"\n💡 SUGGESTED: {suggested} (Confidence: {confidence})")
            print(f"   Reason: {reason}")

            # Get user input
            choice = input("\nLabel this sequence [I/L/N/A/S/Q]: ").strip().upper()

            if choice == "Q":
                print("Quitting labeling session...")
                break
            elif choice == "S":
                print("Skipped")
                continue
            elif choice in ["I", "L", "N", "A"]:
                label_map = {"I": "Ignore", "L": "Log", "N": "Notify", "A": "Alarm"}
                seq["label"] = label_map[choice]
                labeled_count += 1
                print(f"✓ Labeled as: {label_map[choice]}")
            else:
                print("Invalid choice, skipping...")

        print(f"\n✓ Labeled {labeled_count} sequences in this session")

        # Offer to save
        save = input("\nSave labels to file? [y/n]: ").strip().lower()
        if save == "y":
            self.save_data()

    def auto_label_with_rules(self, confidence_threshold="MEDIUM", full=False):
        """
        Auto-label sequences using rule-based suggestions
        Only applies labels with sufficient confidence
        If full=True, relabels all sequences regardless of existing labels
        """
        print("\n" + "=" * 60)
        print("AUTO-LABELING WITH RULES")
        print("=" * 60)

        confidence_levels = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}
        threshold = confidence_levels[confidence_threshold]

        labeled_count = 0
        for seq in self.sequences:
            if full or not seq.get("label") or seq["label"] == "":
                suggested, confidence, reason = self.suggest_label_rule_based(seq)
                if confidence_levels[confidence] >= threshold:
                    seq["label"] = suggested
                    labeled_count += 1

        print(f"✓ Auto-labeled {labeled_count} sequences")
        print(f"  (Confidence threshold: {confidence_threshold})")

        self.save_data()

    def export_for_review(self, output_path="sequences_to_review.csv"):
        """
        Export unlabeled sequences to CSV for easy review
        """
        import csv

        unlabeled = [s for s in self.sequences if not s.get("label") or s["label"] == ""]

        with open(output_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "sequence_id",
                    "start_time",
                    "duration_min",
                    "events",
                    "suggested_label",
                    "confidence",
                    "reason",
                    "manual_label",
                ]
            )

            for seq in unlabeled:
                suggested, confidence, reason = self.suggest_label_rule_based(seq)
                writer.writerow(
                    [
                        seq["sequence_id"],
                        seq["start_time"],
                        seq["duration_minutes"],
                        len(seq["raw_events"]),
                        suggested,
                        confidence,
                        reason,
                        "",  # Empty column for manual labeling
                    ]
                )

        print(f"✓ Exported {len(unlabeled)} sequences to '{output_path}'")
        print("  Review in spreadsheet, fill 'manual_label' column, then re-import")

    def import_from_csv(self, csv_path="sequences_to_review.csv"):
        """
        Import labels from CSV back into JSON
        """
        import csv

        labels_dict = {}
        with open(csv_path, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row["manual_label"].strip():
                    labels_dict[int(row["sequence_id"])] = row["manual_label"].strip()

        updated = 0
        for seq in self.sequences:
            if seq["sequence_id"] in labels_dict:
                seq["label"] = labels_dict[seq["sequence_id"]]
                updated += 1

        print(f"✓ Updated {updated} labels from CSV")
        self.save_data()

    def save_data(self):
        """Save labeled data back to JSON, preserving metadata and config"""
        # Update the sequences in the original data structure
        self.data["sequences"] = self.sequences

        # Ensure metadata and config are preserved
        if self.metadata:
            self.data["metadata"] = self.metadata
        if self.config:
            self.data["config"] = self.config

        # Add labeling metadata
        if "metadata" not in self.data:
            self.data["metadata"] = {}

        import os
        from datetime import datetime

        self.data["metadata"]["last_labeled_at"] = datetime.now().isoformat()

        labeled_count = sum(1 for s in self.sequences if s.get("label") and s["label"].strip())
        self.data["metadata"]["labeled_sequences"] = labeled_count

        # Create backup with auto_ prefix
        base_name = os.path.basename(self.json_path)
        dir_name = os.path.dirname(self.json_path)
        new_path = os.path.join(dir_name, f"auto_{base_name}")

        with open(self.json_path, "w") as f:
            json.dump(self.data, f, indent=2)
        print(f"✓ Saved to '{self.json_path}'")
        print(f"  Labeled sequences: {labeled_count}/{len(self.sequences)}")


def main():
    """Example usage"""
    helper = SequenceLabelingHelper("../../sequence_labels_60_300_3.json")

    # Show dataset overview
    helper.analyze_dataset()

    print("\n" + "=" * 60)
    print("LABELING OPTIONS")
    print("=" * 60)
    print("1. Interactive labeling session (manually label with suggestions)")
    print("2. Auto-label with rules (high confidence only)")
    print("3. Export to CSV for batch labeling")
    print("4. Import labels from CSV")
    print("5. Exit")

    choice = input("\nSelect option [1-5]: ").strip()

    if choice == "1":
        num = int(input("How many sequences to label? [20]: ") or "20")
        helper.interactive_labeling_session(num)
    elif choice == "2":
        helper.auto_label_with_rules(confidence_threshold="LOW", full=True)
    elif choice == "3":
        helper.export_for_review()
    elif choice == "4":
        helper.import_from_csv()
    else:
        print("Exiting...")


if __name__ == "__main__":
    main()
