"""
Crop Recommendation - Training & Testing Script
=================================================
Cleans the crop recommendation dataset, trains a RandomForestClassifier,
evaluates it on a held-out test set, and saves the trained model to disk.

Usage:
    python train_crop_model.py
    python train_crop_model.py --data Crop_recommendation.csv --model-out crop_recommendation_model.pkl
"""

import argparse
import sys

import pandas as pd
import joblib
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report

NUMERIC_COLS = ['N', 'P', 'K', 'temperature', 'humidity', 'ph', 'rainfall']
TARGET_COL = 'label'


def load_data(file_path: str) -> pd.DataFrame:
    """Load the raw CSV into a DataFrame."""
    try:
        df = pd.read_csv(file_path)
    except FileNotFoundError:
        print(f"Error: could not find '{file_path}'. Make sure the CSV is in this folder.")
        sys.exit(1)
    print(f"Loaded data with shape: {df.shape}")
    return df


def inspect_data(df: pd.DataFrame) -> None:
    """Print missing value and duplicate diagnostics."""
    print("\n--- Missing Values Per Column ---")
    print(df.isnull().sum())

    duplicate_count = df.duplicated().sum()
    print(f"\nTotal Duplicate Rows: {duplicate_count}")

    print("\n--- Summary Statistics ---")
    print(df.describe())


def clean_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean the dataset:
      - impute missing numeric values with the column median
      - replace negative numeric values with the column median
      - drop duplicate rows
    """
    df_cleaned = df.copy()

    # Impute missing values
    for col in NUMERIC_COLS:
        if df_cleaned[col].isnull().sum() > 0:
            median_val = df_cleaned[col].median()
            df_cleaned[col] = df_cleaned[col].fillna(median_val)
            print(f"Filled missing values in '{col}' with median: {median_val:.2f}")

    # Replace invalid (negative) values
    for col in NUMERIC_COLS:
        invalid_count = (df_cleaned[col] < 0).sum()
        if invalid_count > 0:
            median_val = df_cleaned[col].median()
            print(f"Found {invalid_count} negative values in '{col}'. Replacing with median.")
            df_cleaned.loc[df_cleaned[col] < 0, col] = median_val

    # Drop duplicates
    dup_count = df_cleaned.duplicated().sum()
    if dup_count > 0:
        df_cleaned = df_cleaned.drop_duplicates()
        print(f"Removed {dup_count} duplicate rows.")

    print(f"\nCleaned dataset shape: {df_cleaned.shape}")
    return df_cleaned


def save_cleaned_data(df: pd.DataFrame, out_path: str) -> None:
    df.to_csv(out_path, index=False)
    print(f"Cleaned dataset saved as '{out_path}'.")


def train_model(df: pd.DataFrame, test_size: float, random_state: int):
    """Split the data and train a RandomForestClassifier."""
    X = df[NUMERIC_COLS]
    y = df[TARGET_COL]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=random_state, stratify=y
    )

    model = RandomForestClassifier(n_estimators=100, random_state=random_state)
    model.fit(X_train, y_train)

    return model, X_test, y_test


def evaluate_model(model, X_test, y_test) -> float:
    """Evaluate the model on the test set and print a classification report."""
    y_pred = model.predict(X_test)
    acc = accuracy_score(y_test, y_pred)

    print(f"\nModel Accuracy: {acc * 100:.2f}%\n")
    print("Detailed Classification Report:\n")
    print(classification_report(y_test, y_pred))

    return acc


def main():
    parser = argparse.ArgumentParser(description="Train and test the crop recommendation model.")
    parser.add_argument('--data', default='dataset/Crop_recommendation.csv',
                         help="Path to the raw crop recommendation CSV (default: Crop_recommendation.csv)")
    parser.add_argument('--cleaned-out', default='Crop_recommendation_cleaned.csv',
                         help="Path to save the cleaned CSV (default: Crop_recommendation_cleaned.csv)")
    parser.add_argument('--model-out', default='models/crop_recommendation_model.pkl',
                         help="Path to save the trained model (default: crop_recommendation_model.pkl)")
    parser.add_argument('--test-size', type=float, default=0.2,
                         help="Fraction of data to hold out for testing (default: 0.2)")
    parser.add_argument('--random-state', type=int, default=42,
                         help="Random seed for reproducibility (default: 42)")
    parser.add_argument('--skip-inspect', action='store_true',
                         help="Skip printing missing-value/summary diagnostics")
    args = parser.parse_args()

    # 1. Load
    df = load_data(args.data)

    # 2. Inspect (optional)
    if not args.skip_inspect:
        inspect_data(df)

    # 3. Clean
    df_cleaned = clean_data(df)
    save_cleaned_data(df_cleaned, args.cleaned_out)

    # 4. Train
    model, X_test, y_test = train_model(df_cleaned, args.test_size, args.random_state)

    # 5. Evaluate
    evaluate_model(model, X_test, y_test)

    # 6. Save model
    joblib.dump(model, args.model_out)
    print(f"Model saved successfully as '{args.model_out}'")


if __name__ == '__main__':
    main()
