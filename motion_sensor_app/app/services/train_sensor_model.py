import json
import numpy as np
import pandas as pd
from datetime import datetime
from sklearn.model_selection import train_test_split, cross_val_score, GridSearchCV
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score
import xgboost as xgb
import joblib
import matplotlib.pyplot as plt
import seaborn as sns

class SensorSequenceTrainer:
    """
    Train ML models to classify sensor event sequences into:
    Ignore, Log, Notify, or Alarm categories
    """

    def __init__(self, json_path):
        """
        Initialize trainer with data path

        Args:
            json_path: Path to the JSON file containing sequences
        """
        self.json_path = json_path
        self.data = None
        self.X = None
        self.y = None
        self.label_encoder = LabelEncoder()
        self.rf_model = None
        self.xgb_model = None
        self.feature_names = None

    def load_data(self):
        """Load and parse JSON data"""
        print("Loading data from JSON...")
        with open(self.json_path, 'r') as f:
            self.data = json.load(f)
        print(f"Loaded {len(self.data['sequences'])} sequences")

    def extract_features(self, sequence):
        """
        Extract meaningful features from a sequence

        Args:
            sequence: Single sequence dictionary

        Returns:
            Dictionary of features
        """
        features = {}

        # Basic sequence features
        features['duration_minutes'] = sequence['duration_minutes']
        features['time_since_last_seq_hours'] = sequence['time_since_last_seq_hours']
        features['window_count'] = sequence['window_count']
        features['total_events'] = len(sequence['raw_events'])

        # Time-based features
        start_time = datetime.fromisoformat(sequence['start_time'])
        features['hour_of_day'] = start_time.hour
        features['day_of_week'] = start_time.weekday()
        features['is_night'] = 1 if (start_time.hour >= 22 or start_time.hour <= 6) else 0
        features['is_weekend'] = 1 if start_time.weekday() >= 5 else 0

        # Event-based features
        if sequence['raw_events']:
            # Sensor activity counts
            sensor_counts = {}
            sensor_types = {}
            motion_detected = 0
            motion_cleared = 0
            door_opened = 0
            door_closed = 0

            for event in sequence['raw_events']:
                sensor = event['sensor_name']
                sensor_type = event['sensor_type']

                sensor_counts[sensor] = sensor_counts.get(sensor, 0) + 1
                sensor_types[sensor_type] = sensor_types.get(sensor_type, 0) + 1

                if event['event'] == 'Motion Detected':
                    motion_detected += 1
                elif event['event'] == 'Motion Cleared':
                    motion_cleared += 1
                elif event['event'] == 'Door Opened':
                    door_opened += 1
                elif event['event'] == 'Door Closed':
                    door_closed += 1

            features['motion_detected_count'] = motion_detected
            features['motion_cleared_count'] = motion_cleared
            features['door_opened_count'] = door_opened
            features['door_closed_count'] = door_closed

            # Unique sensor counts
            features['unique_sensors'] = len(sensor_counts)
            features['unique_sensor_types'] = len(sensor_types)

            # Most active sensor
            features['max_sensor_activations'] = max(sensor_counts.values()) if sensor_counts else 0

            # Event rate (events per minute)
            features['event_rate'] = len(sequence['raw_events']) / max(sequence['duration_minutes'], 0.1)

            # Time gaps between events
            timestamps = [datetime.fromisoformat(e['timestamp']) for e in sequence['raw_events']]
            if len(timestamps) > 1:
                time_diffs = [(timestamps[i+1] - timestamps[i]).total_seconds()
                             for i in range(len(timestamps)-1)]
                features['avg_time_between_events'] = np.mean(time_diffs)
                features['max_time_between_events'] = np.max(time_diffs)
                features['min_time_between_events'] = np.min(time_diffs)
                features['std_time_between_events'] = np.std(time_diffs)
            else:
                features['avg_time_between_events'] = 0
                features['max_time_between_events'] = 0
                features['min_time_between_events'] = 0
                features['std_time_between_events'] = 0

            # State transition patterns
            state_changes = sum(1 for i in range(len(sequence['raw_events'])-1)
                              if sequence['raw_events'][i]['state'] != sequence['raw_events'][i+1]['state'])
            features['state_transitions'] = state_changes

            # Sensor diversity (entropy-like measure)
            sensor_probs = np.array(list(sensor_counts.values())) / len(sequence['raw_events'])
            features['sensor_diversity'] = -np.sum(sensor_probs * np.log2(sensor_probs + 1e-10))

        else:
            # Default values for empty sequences
            features['motion_detected_count'] = 0
            features['motion_cleared_count'] = 0
            features['door_opened_count'] = 0
            features['door_closed_count'] = 0
            features['unique_sensors'] = 0
            features['unique_sensor_types'] = 0
            features['max_sensor_activations'] = 0
            features['event_rate'] = 0
            features['avg_time_between_events'] = 0
            features['max_time_between_events'] = 0
            features['min_time_between_events'] = 0
            features['std_time_between_events'] = 0
            features['state_transitions'] = 0
            features['sensor_diversity'] = 0

        return features

    def prepare_features(self):
        """Extract features from all sequences and prepare for training"""
        print("Extracting features from sequences...")

        feature_list = []
        labels = []

        for seq in self.data['sequences']:
            # Skip sequences without valid labels
            label = seq.get('label')
            if not label or label.strip() == '':
                continue

            features = self.extract_features(seq)
            feature_list.append(features)
            labels.append(label)

        if len(labels) == 0:
            raise ValueError("No labeled sequences found! Please label your data first.")

        # Check for minimum samples per class
        label_counts = pd.Series(labels).value_counts()
        min_samples = label_counts.min()
        if min_samples < 2:
            print("\nWARNING: Some classes have fewer than 2 samples!")
            print("This will cause issues with cross-validation.")
            print(f"Minimum samples per class: {min_samples}")
            print("\nRecommendation: Label at least 10-20 examples per class")

        # Convert to DataFrame
        self.X = pd.DataFrame(feature_list)
        self.feature_names = self.X.columns.tolist()

        # Encode labels
        self.y = self.label_encoder.fit_transform(labels)

        print(f"\nExtracted {len(self.feature_names)} features from {len(labels)} labeled sequences")
        print(f"Feature names: {self.feature_names}")
        print(f"\nLabel distribution:")
        print(label_counts)

        # Check class balance
        max_ratio = label_counts.max() / label_counts.min()
        if max_ratio > 10:
            print(f"\nWARNING: Classes are imbalanced (ratio: {max_ratio:.1f}:1)")
            print("Consider balancing your dataset for better performance")

    def train_random_forest(self, test_size=0.2, random_state=42):
        """
        Train Random Forest classifier with hyperparameter tuning

        Args:
            test_size: Proportion of data for testing
            random_state: Random seed for reproducibility
        """
        print("\n" + "="*60)
        print("Training Random Forest Classifier")
        print("="*60)

        # Check if we have enough data
        unique_classes = len(np.unique(self.y))
        if unique_classes < 2:
            raise ValueError(f"Need at least 2 classes to train. Found only {unique_classes}")

        # Check samples per class for cross-validation
        min_samples = min(np.bincount(self.y))
        n_splits = min(5, min_samples)  # Adjust CV folds based on smallest class

        if n_splits < 2:
            print(f"\n⚠️  WARNING: Only {min_samples} samples in smallest class.")
            print("Cannot perform cross-validation. Training without hyperparameter tuning.")
            use_grid_search = False
        else:
            use_grid_search = True
            if n_splits < 5:
                print(f"\n⚠️  Using {n_splits}-fold CV instead of 5-fold due to small class sizes")

        # Split data
        try:
            X_train, X_test, y_train, y_test = train_test_split(
                self.X, self.y, test_size=test_size, random_state=random_state, stratify=self.y
            )
        except ValueError:
            print("⚠️  Cannot stratify split (too few samples). Using random split.")
            X_train, X_test, y_train, y_test = train_test_split(
                self.X, self.y, test_size=test_size, random_state=random_state
            )

        print(f"Training set: {len(X_train)} samples")
        print(f"Test set: {len(X_test)} samples")

        if use_grid_search:
            # Hyperparameter tuning
            param_grid = {
                'n_estimators': [100, 200, 300],
                'max_depth': [10, 20, 30, None],
                'min_samples_split': [2, 5, 10],
                'min_samples_leaf': [1, 2, 4],
                'max_features': ['sqrt', 'log2']
            }

            print(f"\nPerforming grid search with {n_splits}-fold cross-validation...")
            rf = RandomForestClassifier(random_state=random_state)
            grid_search = GridSearchCV(rf, param_grid, cv=n_splits, scoring='accuracy',
                                      n_jobs=-1, verbose=1)
            grid_search.fit(X_train, y_train)

            print(f"Best parameters: {grid_search.best_params_}")
            print(f"Best cross-validation score: {grid_search.best_score_:.4f}")

            self.rf_model = grid_search.best_estimator_
        else:
            # Train with default parameters
            print("\nTraining with default parameters...")
            self.rf_model = RandomForestClassifier(n_estimators=100, random_state=random_state)
            self.rf_model.fit(X_train, y_train)

        # Evaluate on test set
        y_pred = self.rf_model.predict(X_test)
        accuracy = accuracy_score(y_test, y_pred)

        print(f"\nTest Set Accuracy: {accuracy:.4f}")
        print("\nClassification Report:")

        # Get class names, handling None values
        target_names = [str(name) if name is not None else 'Unknown'
                       for name in self.label_encoder.classes_]

        print(classification_report(y_test, y_pred,
                                   target_names=target_names,
                                   zero_division=0))

        # Confusion matrix
        cm = confusion_matrix(y_test, y_pred)
        self._plot_confusion_matrix(cm, target_names, "Random Forest")

        # Feature importance
        self._plot_feature_importance(self.rf_model.feature_importances_, "Random Forest")

        return accuracy

    def train_xgboost(self, test_size=0.2, random_state=42):
        """
        Train XGBoost classifier with hyperparameter tuning

        Args:
            test_size: Proportion of data for testing
            random_state: Random seed for reproducibility
        """
        print("\n" + "="*60)
        print("Training XGBoost Classifier")
        print("="*60)

        # Check if we have enough data
        unique_classes = len(np.unique(self.y))
        if unique_classes < 2:
            raise ValueError(f"Need at least 2 classes to train. Found only {unique_classes}")

        # Check samples per class for cross-validation
        min_samples = min(np.bincount(self.y))
        n_splits = min(5, min_samples)

        if n_splits < 2:
            print(f"\n⚠️  WARNING: Only {min_samples} samples in smallest class.")
            print("Cannot perform cross-validation. Training without hyperparameter tuning.")
            use_grid_search = False
        else:
            use_grid_search = True
            if n_splits < 5:
                print(f"\n⚠️  Using {n_splits}-fold CV instead of 5-fold due to small class sizes")

        # Split data
        try:
            X_train, X_test, y_train, y_test = train_test_split(
                self.X, self.y, test_size=test_size, random_state=random_state, stratify=self.y
            )
        except ValueError:
            print("⚠️  Cannot stratify split (too few samples). Using random split.")
            X_train, X_test, y_train, y_test = train_test_split(
                self.X, self.y, test_size=test_size, random_state=random_state
            )

        print(f"Training set: {len(X_train)} samples")
        print(f"Test set: {len(X_test)} samples")

        if use_grid_search:
            # Hyperparameter tuning
            param_grid = {
                'n_estimators': [100, 200, 300],
                'max_depth': [3, 5, 7, 10],
                'learning_rate': [0.01, 0.1, 0.3],
                'subsample': [0.8, 1.0],
                'colsample_bytree': [0.8, 1.0]
            }

            print(f"\nPerforming grid search with {n_splits}-fold cross-validation...")
            xgb_clf = xgb.XGBClassifier(random_state=random_state, eval_metric='mlogloss')
            grid_search = GridSearchCV(xgb_clf, param_grid, cv=n_splits, scoring='accuracy',
                                      n_jobs=-1, verbose=1)
            grid_search.fit(X_train, y_train)

            print(f"Best parameters: {grid_search.best_params_}")
            print(f"Best cross-validation score: {grid_search.best_score_:.4f}")

            self.xgb_model = grid_search.best_estimator_
        else:
            # Train with default parameters
            print("\nTraining with default parameters...")
            self.xgb_model = xgb.XGBClassifier(n_estimators=100, random_state=random_state,
                                              eval_metric='mlogloss')
            self.xgb_model.fit(X_train, y_train)

        # Evaluate on test set
        y_pred = self.xgb_model.predict(X_test)
        accuracy = accuracy_score(y_test, y_pred)

        print(f"\nTest Set Accuracy: {accuracy:.4f}")
        print("\nClassification Report:")

        # Get class names, handling None values
        target_names = [str(name) if name is not None else 'Unknown'
                       for name in self.label_encoder.classes_]

        print(classification_report(y_test, y_pred,
                                   target_names=target_names,
                                   zero_division=0))

        # Confusion matrix
        cm = confusion_matrix(y_test, y_pred)
        self._plot_confusion_matrix(cm, target_names, "XGBoost")

        # Feature importance
        self._plot_feature_importance(self.xgb_model.feature_importances_, "XGBoost")

        return accuracy

    def _plot_confusion_matrix(self, cm, classes, model_name):
        """Plot confusion matrix"""
        plt.figure(figsize=(10, 8))
        sns.heatmap(cm, annot=True, fmt='d', cmap='Blues',
                   xticklabels=classes, yticklabels=classes)
        plt.title(f'Confusion Matrix - {model_name}')
        plt.ylabel('True Label')
        plt.xlabel('Predicted Label')
        plt.tight_layout()
        plt.savefig(f'confusion_matrix_{model_name.lower().replace(" ", "_")}.png')
        print(f"Confusion matrix saved as 'confusion_matrix_{model_name.lower().replace(' ', '_')}.png'")
        plt.close()

    def _plot_feature_importance(self, importances, model_name):
        """Plot feature importance"""
        feature_importance_df = pd.DataFrame({
            'feature': self.feature_names,
            'importance': importances
        }).sort_values('importance', ascending=False)

        plt.figure(figsize=(12, 8))
        plt.barh(range(len(feature_importance_df)), feature_importance_df['importance'])
        plt.yticks(range(len(feature_importance_df)), feature_importance_df['feature'])
        plt.xlabel('Importance')
        plt.title(f'Feature Importance - {model_name}')
        plt.tight_layout()
        plt.savefig(f'feature_importance_{model_name.lower().replace(" ", "_")}.png')
        print(f"Feature importance plot saved as 'feature_importance_{model_name.lower().replace(' ', '_')}.png'")
        plt.close()

        print(f"\nTop 10 Most Important Features ({model_name}):")
        print(feature_importance_df.head(10).to_string(index=False))

    def save_models(self, rf_path='random_forest_model.pkl',
                   xgb_path='xgboost_model.pkl',
                   encoder_path='label_encoder.pkl'):
        """Save trained models and label encoder"""
        if self.rf_model:
            joblib.dump(self.rf_model, rf_path)
            print(f"\nRandom Forest model saved to '{rf_path}'")

        if self.xgb_model:
            joblib.dump(self.xgb_model, xgb_path)
            print(f"XGBoost model saved to '{xgb_path}'")

        joblib.dump(self.label_encoder, encoder_path)
        print(f"Label encoder saved to '{encoder_path}'")

    def predict_sequence(self, sequence, model='rf'):
        """
        Predict label for a new sequence

        Args:
            sequence: Sequence dictionary
            model: 'rf' for Random Forest or 'xgb' for XGBoost

        Returns:
            Predicted label and probability distribution
        """
        features = self.extract_features(sequence)
        X_new = pd.DataFrame([features])

        # Ensure all expected features are present
        for col in self.feature_names:
            if col not in X_new.columns:
                X_new[col] = 0
        X_new = X_new[self.feature_names]

        if model == 'rf' and self.rf_model:
            pred = self.rf_model.predict(X_new)[0]
            proba = self.rf_model.predict_proba(X_new)[0]
        elif model == 'xgb' and self.xgb_model:
            pred = self.xgb_model.predict(X_new)[0]
            proba = self.xgb_model.predict_proba(X_new)[0]
        else:
            raise ValueError("Model not trained or invalid model type")

        label = self.label_encoder.inverse_transform([pred])[0]
        proba_dict = {self.label_encoder.classes_[i]: prob
                     for i, prob in enumerate(proba)}

        return label, proba_dict


def main():
    """Main training pipeline"""
    # Initialize trainer
    trainer = SensorSequenceTrainer('../../sequence_labels_60_300_3.json')

    # Load and prepare data
    trainer.load_data()
    trainer.prepare_features()

    # Train both models
    print("\n" + "="*60)
    print("TRAINING PIPELINE")
    print("="*60)

    rf_accuracy = trainer.train_random_forest()
    xgb_accuracy = trainer.train_xgboost()

    # Compare models
    print("\n" + "="*60)
    print("MODEL COMPARISON")
    print("="*60)
    print(f"Random Forest Test Accuracy: {rf_accuracy:.4f}")
    print(f"XGBoost Test Accuracy: {xgb_accuracy:.4f}")

    if rf_accuracy > xgb_accuracy:
        print("\nRandom Forest performed better!")
    elif xgb_accuracy > rf_accuracy:
        print("\nXGBoost performed better!")
    else:
        print("\nBoth models performed equally!")

    # Save models
    trainer.save_models()

    print("\n" + "="*60)
    print("Training complete! Models and visualizations saved.")
    print("="*60)


if __name__ == "__main__":
    main()
