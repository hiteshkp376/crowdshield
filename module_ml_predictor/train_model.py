"""
train_model.py — trains the early-warning classifier on the generated
dataset, with a proper train/test split and honestly-reported metrics
(not just a claimed accuracy number).

Run:
    python train_model.py --data training_data.csv --output model.joblib
"""

import argparse
import csv

import numpy as np
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    confusion_matrix, classification_report,
)
import joblib

from feature_extraction import FEATURE_COLUMNS


def load_dataset(path: str):
    with open(path) as f:
        reader = csv.reader(f)
        header = next(reader)
        rows = [[float(v) for v in row] for row in reader]
    X = np.array([row[:-1] for row in rows])
    y = np.array([int(row[-1]) for row in rows])
    return X, y, header


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default="training_data.csv")
    parser.add_argument("--output", default="model.joblib")
    parser.add_argument("--test-size", type=float, default=0.25)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    X, y, header = load_dataset(args.data)
    print(f"Loaded {len(X)} rows, {len(FEATURE_COLUMNS)} features.")
    print(f"Class balance: {sum(y)} danger / {len(y) - sum(y)} safe")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=args.test_size, random_state=args.seed, stratify=y,
    )
    print(f"\nTrain set: {len(X_train)} rows | Test set: {len(X_test)} rows")

    model = GradientBoostingClassifier(
        n_estimators=150, max_depth=3, learning_rate=0.1, random_state=args.seed,
    )
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]

    print("\n" + "=" * 50)
    print("HONEST EVALUATION ON HELD-OUT TEST SET")
    print("=" * 50)
    print(f"Accuracy:  {accuracy_score(y_test, y_pred):.3f}")
    print(f"Precision: {precision_score(y_test, y_pred):.3f}  "
          f"(of predicted-danger, how many were really danger later)")
    print(f"Recall:    {recall_score(y_test, y_pred):.3f}  "
          f"(of actual-danger cases, how many did we catch)")
    print(f"F1:        {f1_score(y_test, y_pred):.3f}")

    cm = confusion_matrix(y_test, y_pred)
    print(f"\nConfusion matrix:")
    print(f"                 predicted safe   predicted danger")
    print(f"  actual safe    {cm[0][0]:>13}   {cm[0][1]:>15}")
    print(f"  actual danger  {cm[1][0]:>13}   {cm[1][1]:>15}")

    print("\nFull classification report:")
    print(classification_report(y_test, y_pred, target_names=["safe", "danger"]))

    print("Feature importances (what the model actually learned to rely on):")
    importances = sorted(zip(FEATURE_COLUMNS, model.feature_importances_),
                          key=lambda x: -x[1])
    for name, importance in importances:
        print(f"  {name:24s} {importance:.3f}")

    joblib.dump(model, args.output)
    print(f"\nSaved trained model to {args.output}")


if __name__ == "__main__":
    main()
