import pandas as pd
import numpy as np
from datetime import timedelta

# --- CONFIG ---
WINDOW_SIZE = 60          # seconds per window (1 minute as requested)
SEQUENCE_GAP_THRESHOLD = 60*5  #5mins (seconds) gap to consider new sequence
MIN_SEQUENCE_LENGTH = 3   # minimum windows per sequence for labeling

# --- LOAD RAW SENSOR DATA ---
df = pd.read_csv("sensor_activity.csv", parse_dates=["timestamp"])
df = df.sort_values("timestamp")

print(f"Loaded {len(df)} sensor events from {df.timestamp.min()} to {df.timestamp.max()}")

# --- PIVOT DATA TO MULTIVARIATE FORMAT ---
pivoted = df.pivot_table(index="timestamp",
                        columns="sensor_name", 
                        values="state",
                        aggfunc="sum")
pivoted = pivoted.fillna(0)

# --- RESAMPLE INTO FIXED WINDOWS ---
pivoted_windowed = pivoted.resample(f"{WINDOW_SIZE}S").sum().fillna(0)

print(f"Created {len(pivoted_windowed)} windows of {WINDOW_SIZE}s each")

# --- IDENTIFY EVENT SEQUENCES BASED ON TEMPORAL GAPS ---
def identify_sequences(windowed_data, gap_threshold_seconds):
    """
    Identify sequences of activity separated by gaps longer than threshold
    """
    sequences = []
    current_sequence_start = None
    current_sequence_windows = []
    last_activity_time = None
    
    for timestamp, row in windowed_data.iterrows():
        has_activity = row.sum() > 0
        
        if has_activity:
            if current_sequence_start is None:
                # Start new sequence
                current_sequence_start = timestamp
                current_sequence_windows = [timestamp]
                print(f"Starting new sequence at {timestamp}")
            else:
                # Check if gap is too large
                gap = (timestamp - last_activity_time).total_seconds()
                if gap > gap_threshold_seconds:
                    # End current sequence and start new one
                    if len(current_sequence_windows) >= MIN_SEQUENCE_LENGTH:
                        time_since_last = 0 if not sequences else gap
                        sequences.append({
                            'start_time': current_sequence_start,
                            'end_time': last_activity_time,
                            'windows': current_sequence_windows.copy(),
                            'duration_minutes': (last_activity_time - current_sequence_start).total_seconds() / 60,
                            'time_since_last_seq_hours': time_since_last / 3600,
                            'window_count': len(current_sequence_windows)
                        })
                        print(f"Completed sequence: {current_sequence_start} to {last_activity_time} ({len(current_sequence_windows)} windows)")
                    
                    current_sequence_start = timestamp
                    current_sequence_windows = [timestamp]
                    print(f"Starting new sequence at {timestamp} (gap of {gap/3600:.1f} hours)")
                else:
                    # Continue current sequence
                    current_sequence_windows.append(timestamp)
            
            last_activity_time = timestamp
    
    # Don't forget the last sequence
    if current_sequence_start is not None and len(current_sequence_windows) >= MIN_SEQUENCE_LENGTH:
        gap_from_previous = 0
        if sequences:
            gap_from_previous = (current_sequence_start - sequences[-1]['end_time']).total_seconds()
        
        sequences.append({
            'start_time': current_sequence_start,
            'end_time': last_activity_time,
            'windows': current_sequence_windows.copy(),
            'duration_minutes': (last_activity_time - current_sequence_start).total_seconds() / 60,
            'time_since_last_seq_hours': gap_from_previous / 3600,
            'window_count': len(current_sequence_windows)
        })
        print(f"Completed final sequence: {current_sequence_start} to {last_activity_time} ({len(current_sequence_windows)} windows)")
    
    return sequences

sequences = identify_sequences(pivoted_windowed, SEQUENCE_GAP_THRESHOLD)

print(f"\nIdentified {len(sequences)} event sequences:")
for i, seq in enumerate(sequences):
    print(f"Sequence {i+1}: {seq['start_time']} to {seq['end_time']}")
    print(f"  Duration: {seq['duration_minutes']:.1f} minutes")
    print(f"  Windows: {seq['window_count']}")
    print(f"  Time since last sequence: {seq['time_since_last_seq_hours']:.1f} hours")

# --- INTERACTIVE LABELING PER SEQUENCE ---
labeled_sequences = []

for seq_idx, sequence in enumerate(sequences):
    print(f"\n{'='*60}")
    print(f"SEQUENCE {seq_idx + 1} of {len(sequences)}")
    print(f"Time range: {sequence['start_time']} to {sequence['end_time']}")
    print(f"Duration: {sequence['duration_minutes']:.1f} minutes")
    print(f"Time since last sequence: {sequence['time_since_last_seq_hours']:.1f} hours")
    print(f"Number of windows: {sequence['window_count']}")
    print(f"{'='*60}")
    
    # Show sample of activity in this sequence
    sequence_data = pivoted_windowed.loc[sequence['windows']]
    print("\nSample windows from this sequence:")
    print(sequence_data.head(3))
    if len(sequence_data) > 3:
        print("...")
        print(sequence_data.tail(2))
    
    print(f"\nActivity summary:")
    for sensor in sequence_data.columns:
        total_activity = sequence_data[sensor].sum()
        if total_activity > 0:
            print(f"  {sensor}: {total_activity} total activations")
    
    label = "Ignore" #input("\nEnter label for this ENTIRE SEQUENCE (Ignore, Log, Notify, Alarm): ").strip()
    
    labeled_sequences.append({
        **sequence,
        'label': label,
        'sequence_id': seq_idx + 1
    })

# --- CREATE TRAINING DATA FROM LABELED SEQUENCES ---
X, y, sequence_info = [], [], []

for seq in labeled_sequences:
    # Get the windowed data for this sequence
    sequence_windows = pivoted_windowed.loc[seq['windows']]
    
    # Convert to numpy array (each window becomes a feature vector)
    sequence_array = sequence_windows.values  # Shape: (n_windows, n_sensors)
    
    # Add metadata as additional features (optional)
    n_windows, n_sensors = sequence_array.shape
    
    # Create metadata features
    time_since_last = np.full(n_windows, seq['time_since_last_seq_hours'])
    sequence_position = np.arange(n_windows) / max(1, n_windows - 1)  # 0 to 1
    
    # Combine sensor data with metadata
    metadata = np.column_stack([time_since_last, sequence_position])
    enhanced_sequence = np.column_stack([sequence_array, metadata])
    
    X.append(enhanced_sequence)
    y.append(seq['label'])
    sequence_info.append({
        'sequence_id': seq['sequence_id'],
        'start_time': seq['start_time'],
        'end_time': seq['end_time'],
        'window_count': seq['window_count'],
        'time_since_last_seq_hours': seq['time_since_last_seq_hours']
    })

# Convert to numpy arrays (note: sequences may have different lengths)
print(f"\nCreated {len(X)} labeled sequences:")
for i, (seq_data, label) in enumerate(zip(X, y)):
    print(f"Sequence {i+1}: {seq_data.shape} -> '{label}'")

# --- SAVE DATA ---
# Save sequences and labels
output_data = {
    'sequences': X,
    'labels': y,
    'sequence_info': sequence_info,
    'sensor_names': list(pivoted_windowed.columns),
    'config': {
        'window_size_seconds': WINDOW_SIZE,
        'sequence_gap_threshold_seconds': SEQUENCE_GAP_THRESHOLD,
        'min_sequence_length': MIN_SEQUENCE_LENGTH
    }
}

#np.save("labeled_sequences.npy", output_data, allow_pickle=True)
print(f"\nSaved labeled sequences to 'labeled_sequences.npy'")

# Also save a summary CSV
summary_df = pd.DataFrame([
    {
        'sequence_id': info['sequence_id'],
        'start_time': info['start_time'],
        'end_time': info['end_time'], 
        'window_count': info['window_count'],
        'time_since_last_seq_hours': info['time_since_last_seq_hours'],
        'label': label
    }
    for info, label in zip(sequence_info, y)
])

#summary_df.to_csv("sequence_summary.csv", index=False)
print("Saved sequence summary to 'sequence_summary.csv'")

print(f"\n{'='*60}")
print("PROCESSING COMPLETE")
print(f"Total sequences created: {len(X)}")
print("Label distribution:")
for label in set(y):
    count = y.count(label)
    print(f"  {label}: {count} sequences")
