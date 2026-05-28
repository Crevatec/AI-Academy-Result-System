"""
backend/app/ai/train.py
------------------------
AI Model Training Script — matches Chapter 3 (Section 3.8) exactly.

Algorithms implemented (Section 3.8.2):
    1. Linear Regression       → Predicts numerical GPA value (regression)
    2. Logistic Regression     → Classifies risk level (classification)
    3. Decision Tree           → Classifies risk level (classification)
    4. Random Forest           → Classifies risk level (classification) — primary model

Risk labels (Section 3.8.3):
    Excellent  → Strong performance, no intervention needed
    Average    → Inconsistent, may need guidance
    At Risk    → High probability of poor standing, needs immediate intervention

Evaluation metrics (Section 3.10):
    Linear Regression:           MSE (Mean Squared Error)
    Logistic/DTree/RandomForest: Accuracy, Precision, Recall, F1-Score

Run this script once before starting the server:
    cd backend
    python app/ai/train.py

Outputs:
    ai_module/models/risk_classifier.pkl   — best classification model (Random Forest)
    ai_module/models/gpa_regressor.pkl     — Linear Regression GPA predictor
"""

import os
import sys
import joblib
import numpy as np
import pandas as pd

from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression, LinearRegression
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier

# Classification metrics (Logistic Regression, Decision Tree, Random Forest)
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    classification_report,
)

# Regression metric (Linear Regression)
from sklearn.metrics import mean_squared_error

# ── Output paths ───────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR = os.path.join(BASE_DIR, "..", "..", "..", "ai_module", "models")
CLASSIFIER_PATH = os.path.join(MODELS_DIR, "risk_classifier.pkl")
REGRESSOR_PATH  = os.path.join(MODELS_DIR, "gpa_regressor.pkl")
DATA_PATH = os.path.join(BASE_DIR, "..", "..", "..", "ai_module", "data", "results.csv")


# ── Risk Label Mapping (Section 3.8.3) ────────────────────────────────────────

def cgpa_to_risk_label(cgpa: float) -> str:
    """
    Convert CGPA to one of three risk classification labels.

    Excellent  — CGPA >= 3.50: Strong consistent performance
    Average    — CGPA 2.40–3.49: Satisfactory but needs monitoring
    At Risk    — CGPA < 2.40: High probability of poor academic standing
    """
    if cgpa >= 3.50:
        return "Excellent"
    elif cgpa >= 2.40:
        return "Average"
    else:
        return "At Risk"


# ── Feature Engineering (Section 3.8.3 — Input Features) ─────────────────────

def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Transform raw result records into ML features.

    Input columns expected from results.csv:
        student_id, course_unit, score, grade_point, CGPA, grading_scale, grade

    Output features (matching Section 3.8.3):
        avg_score           — Average score across all courses (individual course scores)
        avg_grade_point     — Average grade point (reflects GPA trend)
        total_units         — Total credit units attempted (credit unit load)
        min_score           — Worst course score
        max_score           — Best course score
        fail_count          — Number of F grades
        score_std           — Score consistency / variability
        grading_scale_enc   — 1 for 5.0 scale, 0 for 4.0 scale

    Target variable:
        risk_label          — "Excellent", "Average", or "At Risk"
        cgpa                — Raw CGPA (used for regression target)
    """
    agg = df.groupby("student_id").agg(
        avg_score=("score", "mean"),
        avg_grade_point=("grade_point", "mean"),
        total_units=("course_unit", "sum"),
        min_score=("score", "min"),
        max_score=("score", "max"),
        fail_count=("grade", lambda x: (x == "F").sum()),
        score_std=("score", "std"),
        cgpa=("CGPA", "first"),
        grading_scale=("grading_scale", "first"),
    ).reset_index()

    # Fill NaN std (student took only 1 course)
    agg["score_std"] = agg["score_std"].fillna(0)

    # Encode grading scale: 5.0 → 1, 4.0 → 0
    agg["grading_scale_enc"] = (agg["grading_scale"] == 5.0).astype(int)

    # Risk classification label (used by classifiers)
    agg["risk_label"] = agg["cgpa"].apply(cgpa_to_risk_label)

    return agg


FEATURE_COLUMNS = [
    "avg_score",
    "avg_grade_point",
    "total_units",
    "min_score",
    "max_score",
    "fail_count",
    "score_std",
    "grading_scale_enc",
]


# ── Main Training Pipeline ─────────────────────────────────────────────────────

def train():
    print()
    print("=" * 60)
    print("  AcadResult — AI Model Training")
    print("  Algorithms: Linear Regression, Logistic Regression,")
    print("               Decision Tree, Random Forest")
    print("=" * 60)

    # ── Step 1: Load dataset ───────────────────────────────────────────────────
    if not os.path.exists(DATA_PATH):
        print(f"\n[ERROR] Dataset not found at:\n  {DATA_PATH}")
        print("\nRun first:\n  python ai_module/data/generate_dataset.py\n")
        sys.exit(1)

    df = pd.read_csv(DATA_PATH)
    print(f"\n[1] Dataset loaded: {len(df)} records, {df['student_id'].nunique()} students")

    # ── Step 2: Feature engineering ───────────────────────────────────────────
    features_df = build_features(df)
    print(f"[2] Features built: {len(features_df)} student records")

    X = features_df[FEATURE_COLUMNS]
    y_class = features_df["risk_label"]       # Target for classifiers
    y_regress = features_df["cgpa"]           # Target for Linear Regression

    print(f"\n[3] Risk label distribution:")
    for label, count in y_class.value_counts().items():
        print(f"      {label:<12}: {count} ({count/len(y_class)*100:.1f}%)")

    # ── Step 3: Train / test split ─────────────────────────────────────────────
    X_train, X_test, yc_train, yc_test, yr_train, yr_test = train_test_split(
        X, y_class, y_regress,
        test_size=0.2,
        random_state=42,
        stratify=y_class,
    )
    print(f"\n[4] Train: {len(X_train)} | Test: {len(X_test)}")

    # ── Step 4: StandardScaler for Logistic Regression ────────────────────────
    # (Decision Tree and Random Forest don't need scaling)
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled  = scaler.transform(X_test)

    # =========================================================================
    # PART A — CLASSIFICATION MODELS (Section 3.8.2)
    # Evaluate: Accuracy, Precision, Recall, F1-Score (Section 3.10)
    # =========================================================================

    print("\n" + "=" * 60)
    print("  PART A — CLASSIFICATION MODELS")
    print("  Metrics: Accuracy, Precision, Recall, F1-Score")
    print("=" * 60)

    classifiers = {
        "Logistic Regression": (
            LogisticRegression(max_iter=1000, random_state=42),
            X_train_scaled,
            X_test_scaled,
        ),
        "Decision Tree": (
            DecisionTreeClassifier(max_depth=5, random_state=42),
            X_train,
            X_test,
        ),
        "Random Forest": (
            RandomForestClassifier(n_estimators=100, random_state=42),
            X_train,
            X_test,
        ),
    }

    classifier_results = {}
    best_classifier_name = None
    best_f1 = 0.0

    for name, (model, X_tr, X_te) in classifiers.items():
        model.fit(X_tr, yc_train)
        y_pred = model.predict(X_te)

        acc  = accuracy_score(yc_test, y_pred)
        prec = precision_score(yc_test, y_pred, average="weighted", zero_division=0)
        rec  = recall_score(yc_test, y_pred, average="weighted", zero_division=0)
        f1   = f1_score(yc_test, y_pred, average="weighted", zero_division=0)

        classifier_results[name] = {
            "model": model,
            "accuracy":  round(acc,  4),
            "precision": round(prec, 4),
            "recall":    round(rec,  4),
            "f1_score":  round(f1,   4),
        }

        print(f"\n  {name}:")
        print(f"    Accuracy  : {acc:.4f}  ({acc*100:.1f}%)")
        print(f"    Precision : {prec:.4f}")
        print(f"    Recall    : {rec:.4f}")
        print(f"    F1-Score  : {f1:.4f}")

        if f1 > best_f1:
            best_f1 = f1
            best_classifier_name = name

    # Best classifier — full report
    best_clf = classifier_results[best_classifier_name]
    print(f"\n  ★ Best classifier: {best_classifier_name}")
    print(f"    (selected by highest F1-Score: {best_f1:.4f})")

    # Full classification report for the best model
    best_clf_model = best_clf["model"]
    X_te_best = (
        X_test_scaled
        if best_classifier_name == "Logistic Regression"
        else X_test
    )
    y_pred_best = best_clf_model.predict(X_te_best)
    print(f"\n  Detailed classification report ({best_classifier_name}):")
    print(classification_report(yc_test, y_pred_best, zero_division=0))

    # Feature importances (Random Forest only)
    if best_classifier_name == "Random Forest":
        importances = best_clf_model.feature_importances_
        print("  Feature importances:")
        for feat, imp in sorted(
            zip(FEATURE_COLUMNS, importances), key=lambda x: -x[1]
        ):
            bar = "█" * int(imp * 40)
            print(f"    {feat:<25} {bar} {imp:.4f}")

    # =========================================================================
    # PART B — LINEAR REGRESSION (Section 3.8.2)
    # Evaluate: Mean Squared Error — MSE (Section 3.10)
    # =========================================================================

    print("\n" + "=" * 60)
    print("  PART B — LINEAR REGRESSION (GPA Prediction)")
    print("  Metric: Mean Squared Error (MSE)")
    print("=" * 60)

    lr_model = LinearRegression()
    lr_model.fit(X_train, yr_train)
    yr_pred = lr_model.predict(X_test)

    mse  = mean_squared_error(yr_test, yr_pred)
    rmse = np.sqrt(mse)

    print(f"\n  Linear Regression — GPA Prediction:")
    print(f"    MSE  (Mean Squared Error)  : {mse:.4f}")
    print(f"    RMSE (Root MSE)            : {rmse:.4f}")
    print(f"    Interpretation: On average, predicted GPA deviates by ±{rmse:.2f} points")
    print(f"    Lower MSE = more accurate GPA prediction")

    # Sample predictions vs actual
    print(f"\n  Sample predictions (first 5 test records):")
    print(f"    {'Actual CGPA':<15} {'Predicted GPA':<15} {'Error'}")
    print(f"    {'-'*45}")
    for actual, predicted in list(zip(yr_test[:5], yr_pred[:5])):
        error = abs(actual - predicted)
        print(f"    {actual:<15.2f} {predicted:<15.2f} ±{error:.2f}")

    # =========================================================================
    # SAVE MODELS
    # =========================================================================

    print("\n" + "=" * 60)
    print("  SAVING MODELS")
    print("=" * 60)

    os.makedirs(MODELS_DIR, exist_ok=True)

    # Save risk classifier (best classification model)
    classifier_bundle = {
        "model":           best_clf_model,
        "model_name":      best_classifier_name,
        "scaler":          scaler if best_classifier_name == "Logistic Regression" else None,
        "feature_columns": FEATURE_COLUMNS,
        "label_classes":   ["At Risk", "Average", "Excellent"],
        "label_map":       {"At Risk": 0, "Average": 1, "Excellent": 2},
        "metrics": {
            "accuracy":  best_clf["accuracy"],
            "precision": best_clf["precision"],
            "recall":    best_clf["recall"],
            "f1_score":  best_clf["f1_score"],
        },
    }
    joblib.dump(classifier_bundle, CLASSIFIER_PATH)
    print(f"\n  [✓] Risk classifier saved:")
    print(f"      {CLASSIFIER_PATH}")
    print(f"      Model: {best_classifier_name}")
    print(f"      F1-Score: {best_f1:.4f}")

    # Save GPA regressor (Linear Regression)
    regressor_bundle = {
        "model":           lr_model,
        "model_name":      "Linear Regression",
        "feature_columns": FEATURE_COLUMNS,
        "metrics": {
            "mse":  round(mse,  4),
            "rmse": round(rmse, 4),
        },
    }
    joblib.dump(regressor_bundle, REGRESSOR_PATH)
    print(f"\n  [✓] GPA regressor saved:")
    print(f"      {REGRESSOR_PATH}")
    print(f"      Model: Linear Regression")
    print(f"      MSE: {mse:.4f}")

    # =========================================================================
    # FINAL SUMMARY
    # =========================================================================

    print("\n" + "=" * 60)
    print("  TRAINING COMPLETE — SUMMARY")
    print("=" * 60)
    print()
    print("  Classification Models (Risk Level Prediction)")
    print(f"  {'Model':<25} {'Accuracy':>10} {'Precision':>10} {'Recall':>10} {'F1-Score':>10}")
    print(f"  {'-'*65}")
    for name, res in classifier_results.items():
        star = " ★" if name == best_classifier_name else ""
        print(
            f"  {name:<25} {res['accuracy']:>10.4f} {res['precision']:>10.4f} "
            f"{res['recall']:>10.4f} {res['f1_score']:>10.4f}{star}"
        )
    print()
    print("  Regression Model (GPA Numerical Prediction)")
    print(f"  {'Model':<25} {'MSE':>10} {'RMSE':>10}")
    print(f"  {'-'*45}")
    print(f"  {'Linear Regression':<25} {mse:>10.4f} {rmse:>10.4f}")
    print()
    print("  Models ready. Start the server with:  python run.py")
    print()


if __name__ == "__main__":
    train()
