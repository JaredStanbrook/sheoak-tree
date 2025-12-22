#!/usr/bin/env python3
"""
Sensor Activity CSV Cleanup Script

This script cleans up sensor activity logs by:
1. Removing duplicate events within milliseconds of each other
2. Removing "Motion Cleared" events
3. Keeping all door events (open/close)
"""

import pandas as pd
import sys
from datetime import datetime, timedelta
import argparse


def clean_sensor_csv(input_file, output_file=None, duplicate_threshold_ms=100, backup=True):
    """
    Clean sensor activity CSV file

    Args:
        input_file: Path to input CSV file
        output_file: Path to output CSV file (defaults to input_file if None)
        duplicate_threshold_ms: Time threshold in milliseconds for duplicate detection
        backup: Whether to create a backup of the original file
    """

    print(f"Reading {input_file}...")

    # Read the CSV
    df = pd.read_csv(input_file)

    original_count = len(df)
    print(f"Original record count: {original_count}")

    # Convert timestamp to datetime
    df['timestamp'] = pd.to_datetime(df['timestamp'], format='ISO8601')

    # Sort by timestamp to ensure chronological order
    df = df.sort_values('timestamp').reset_index(drop=True)

    # Step 1: Remove "Motion Cleared" events
    print("\nStep 1: Removing 'Motion Cleared' events...")
    motion_cleared_count = len(df[df['event'] == 'Motion Cleared'])
    df = df[df['event'] != 'Motion Cleared']
    print(f"  Removed {motion_cleared_count} 'Motion Cleared' events")

    # Step 2: Remove duplicate events
    print(f"\nStep 2: Removing duplicate events within {duplicate_threshold_ms}ms...")

    # Group by sensor and process each sensor separately
    cleaned_dfs = []
    duplicate_count = 0

    for sensor_name in df['sensor_name'].unique():
        sensor_df = df[df['sensor_name'] == sensor_name].copy()

        if len(sensor_df) == 0:
            continue

        # Track which rows to keep
        keep_mask = [True]  # Always keep first row

        for i in range(1, len(sensor_df)):
            current_row = sensor_df.iloc[i]
            previous_row = sensor_df.iloc[i-1]

            # Calculate time difference
            time_diff = (current_row['timestamp'] - previous_row['timestamp']).total_seconds() * 1000

            # Check if it's a duplicate (same event, same state, within threshold)
            is_duplicate = (
                time_diff <= duplicate_threshold_ms and
                current_row['event'] == previous_row['event'] and
                current_row['state'] == previous_row['state']
            )

            keep_mask.append(not is_duplicate)
            if is_duplicate:
                duplicate_count += 1

        sensor_df = sensor_df[keep_mask].copy()
        cleaned_dfs.append(sensor_df)

    print(f"  Removed {duplicate_count} duplicate events")

    # Combine all sensors back together
    df_cleaned = pd.concat(cleaned_dfs, ignore_index=True)

    # Sort by timestamp again
    df_cleaned = df_cleaned.sort_values('timestamp').reset_index(drop=True)

    # Convert timestamp back to ISO format string
    df_cleaned['timestamp'] = df_cleaned['timestamp'].dt.strftime('%Y-%m-%dT%H:%M:%S.%f')

    final_count = len(df_cleaned)
    print(f"\nFinal record count: {final_count}")
    print(f"Total records removed: {original_count - final_count}")
    print(f"Reduction: {((original_count - final_count) / original_count * 100):.1f}%")

    # Create backup if requested
    if backup and output_file != input_file:
        backup_file = input_file.replace('.csv', f'_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv')
        print(f"\nCreating backup: {backup_file}")
        df.to_csv(backup_file, index=False)

    # Determine output file
    if output_file is None:
        output_file = input_file

    # Save cleaned data
    print(f"\nSaving cleaned data to: {output_file}")
    df_cleaned.to_csv(output_file, index=False)

    # Print summary statistics
    print("\n" + "="*50)
    print("CLEANUP SUMMARY")
    print("="*50)
    print(f"\nEvents by sensor:")
    for sensor_name in df_cleaned['sensor_name'].unique():
        count = len(df_cleaned[df_cleaned['sensor_name'] == sensor_name])
        print(f"  {sensor_name}: {count} events")

    print(f"\nEvents by type:")
    for event_type in df_cleaned['event'].unique():
        count = len(df_cleaned[df_cleaned['event'] == event_type])
        print(f"  {event_type}: {count} events")

    print("\n✓ Cleanup complete!")


def main():
    parser = argparse.ArgumentParser(
        description='Clean up sensor activity CSV file',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Clean file in-place (creates backup)
  python cleanup_csv.py sensor_activity.csv

  # Clean to new file
  python cleanup_csv.py sensor_activity.csv -o sensor_activity_clean.csv

  # Adjust duplicate detection threshold
  python cleanup_csv.py sensor_activity.csv -t 50

  # Clean without backup
  python cleanup_csv.py sensor_activity.csv --no-backup
        """
    )

    parser.add_argument('input_file', help='Input CSV file to clean')
    parser.add_argument('-o', '--output', help='Output CSV file (default: overwrites input)', default=None)
    parser.add_argument('-t', '--threshold', type=int, default=100,
                        help='Duplicate detection threshold in milliseconds (default: 100)')
    parser.add_argument('--no-backup', action='store_true',
                        help='Do not create backup file')

    args = parser.parse_args()

    try:
        clean_sensor_csv(
            args.input_file,
            args.output,
            args.threshold,
            backup=not args.no_backup
        )
    except FileNotFoundError:
        print(f"Error: File '{args.input_file}' not found")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
