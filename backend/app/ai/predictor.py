"""
backend/app/ai/predictor.py
-----------------------------
Loads trained models and generates predictions for individual students.

Two models (Chapter 3, Section 3.8.2):
    risk_classifier.pkl  — Random Forest (best classifier)
                           Output: "Excellent", "Average", or "At Risk"
    gpa_regressor.pkl    — Linear Regression
                           Output: predicted numerical GPA value

Called by:  /api/v1/predict/<student_id>

Falls back to rule-based prediction if models not yet trained.
"""

import os
import joblib
import numpy as np

# ── Model file paths ───────────────────────────────────────────────────────────
_BASE       = os.path.dirname(os.path.abspath(__file__))
_MODELS_DIR = os.path.join(_BASE, "..", "..", "..", "ai_module", "models")

CLASSIFIER_PATH = os.path.join(_MODELS_DIR, "risk_classifier.pkl")
REGRESSOR_PATH  = os.path.join(_MODELS_DIR, "gpa_regressor.pkl")

# Cached in memory after first load
_classifier_bundle = None
_regressor_bundle  = None


# ── Model Loaders ──────────────────────────────────────────────────────────────

def _load_classifier():
    """Load risk classification model (lazy, cached)."""
    global _classifier_bundle
    if _classifier_bundle is not None:
        return _classifier_bundle
    try:
        if os.path.exists(CLASSIFIER_PATH):
            _classifier_bundle = joblib.load(CLASSIFIER_PATH)
    except Exception as e:
        print(f"[AI] Failed to load classifier: {e}")
    return _classifier_bundle


def _load_regressor():
    """Load GPA regression model (lazy, cached)."""
    global _regressor_bundle
    if _regressor_bundle is not None:
        return _regressor_bundle
    try:
        if os.path.exists(REGRESSOR_PATH):
            _regressor_bundle = joblib.load(REGRESSOR_PATH)
    except Exception as e:
        print(f"[AI] Failed to load regressor: {e}")
    return _regressor_bundle


# ── Rule-Based Fallback ────────────────────────────────────────────────────────

def _rule_based_prediction(cgpa: float, scale: str) -> dict:
    """
    Fallback when ML models are not yet trained.
    Uses CGPA thresholds. Risk labels match Chapter 3, Section 3.8.3.
    """
    if scale == "5.0":
        if cgpa >= 3.50:
            risk_level, predicted_gpa = "Excellent", round(min(cgpa + 0.10, 5.0), 2)
        elif cgpa >= 2.40:
            risk_level, predicted_gpa = "Average",   round(cgpa, 2)
        else:
            risk_level, predicted_gpa = "At Risk",   round(max(cgpa - 0.10, 0.0), 2)
    else:
        if cgpa >= 3.00:
            risk_level, predicted_gpa = "Excellent", round(min(cgpa + 0.10, 4.0), 2)
        elif cgpa >= 2.00:
            risk_level, predicted_gpa = "Average",   round(cgpa, 2)
        else:
            risk_level, predicted_gpa = "At Risk",   round(max(cgpa - 0.10, 0.0), 2)

    return {
        "risk_level":    risk_level,
        "predicted_gpa": predicted_gpa,
        "confidence":    0.65,
        "method":        "rule_based (models not yet trained)",
        "mse":           None,
    }


# ── Main Prediction Function ───────────────────────────────────────────────────

def predict_student_performance(student_id: int) -> dict:
    """
    Generate a full performance prediction for one student.

    Steps:
        1. Load student's approved results from database
        2. Extract features used during training
        3. Run risk classifier  → risk level label
        4. Run GPA regressor    → predicted numerical GPA
        5. Save result to PredictionRecord table (Chapter 3, Section 3.6)
        6. Return combined output

    Args:
        student_id: Primary key of Student

    Returns:
        dict: risk_level, predicted_gpa, confidence, method, metrics
    """
    from flask import current_app
    from app.models.user import Student
    from app.models.result import Result, CGPARecord

    student = Student.query.get(student_id)
    if not student:
        return {
            "risk_level":    "Unknown",
            "predicted_gpa": None,
            "confidence":    0,
            "method":        "error: student not found",
        }

    # Fetch all approved results
    results = Result.query.filter_by(
        student_id=student_id, status="approved"
    ).all()

    if not results:
        return {
            "risk_level":    "Unknown",
            "predicted_gpa": None,
            "confidence":    0,
            "method":        "no_data: no approved results yet",
        }

    # Get current CGPA
    cgpa_record = CGPARecord.query.filter_by(student_id=student_id).first()
    cgpa  = cgpa_record.cgpa if cgpa_record else 0.0
    scale = student.grading_scale

    # Try ML models
    clf_bundle = _load_classifier()
    reg_bundle = _load_regressor()

    if clf_bundle is None or reg_bundle is None:
        return _rule_based_prediction(cgpa, scale)

    try:
        # ── Build feature vector ─────────────────────────────────────────────
        scores       = [r.score for r in results]
        grade_points = [r.grade_point for r in results]
        units        = [r.course.unit for r in results]
        grades       = [r.grade for r in results]

        feature_vector = np.array([[
            np.mean(scores),            # avg_score
            np.mean(grade_points),      # avg_grade_point
            sum(units),                 # total_units
            min(scores),                # min_score
            max(scores),                # max_score
            grades.count("F"),          # fail_count
            np.std(scores),             # score_std
            1 if scale == "5.0" else 0, # grading_scale_enc
        ]])

        # ── Risk Classification ──────────────────────────────────────────────
        clf_model   = clf_bundle["model"]
        clf_name    = clf_bundle["model_name"]
        clf_scaler  = clf_bundle.get("scaler")
        clf_metrics = clf_bundle.get("metrics", {})

        X_clf      = clf_scaler.transform(feature_vector) if clf_scaler else feature_vector
        risk_level = clf_model.predict(X_clf)[0]
        probas     = clf_model.predict_proba(X_clf)[0]
        confidence = float(max(probas))

        # ── GPA Prediction (Linear Regression) ───────────────────────────────
        reg_model   = reg_bundle["model"]
        reg_metrics = reg_bundle.get("metrics", {})

        predicted_gpa_raw = float(reg_model.predict(feature_vector)[0])
        max_gpa           = float(scale)
        predicted_gpa     = round(max(0.0, min(predicted_gpa_raw, max_gpa)), 2)

        # ── Save to Predictions Table (Chapter 3, Section 3.6) ───────────────
        # This block is INSIDE the function — safe to use current_app here
        try:
            from app.models.result import PredictionRecord
            from app import db

            record = PredictionRecord(
                student_id    = student_id,
                risk_level    = risk_level,
                predicted_gpa = predicted_gpa,
                confidence    = round(confidence, 3),
                method        = f"{clf_name} + Linear Regression",
                accuracy      = clf_metrics.get("accuracy"),
                precision     = clf_metrics.get("precision"),
                recall        = clf_metrics.get("recall"),
                f1_score      = clf_metrics.get("f1_score"),
                mse           = reg_metrics.get("mse"),
            )
            db.session.add(record)
            db.session.commit()
        except Exception as save_error:
            # Log but do not crash — prediction still returns to the user
            current_app.logger.warning(
                f"Could not save prediction record: {save_error}"
            )

        # ── Return result ─────────────────────────────────────────────────────
        return {
            "risk_level":    risk_level,
            "predicted_gpa": predicted_gpa,
            "confidence":    round(confidence, 3),
            "current_cgpa":  cgpa,
            "method":        f"ml_model ({clf_name} + Linear Regression)",
            "classifier_metrics": {
                "accuracy":  clf_metrics.get("accuracy"),
                "precision": clf_metrics.get("precision"),
                "recall":    clf_metrics.get("recall"),
                "f1_score":  clf_metrics.get("f1_score"),
            },
            "regressor_metrics": {
                "mse":  reg_metrics.get("mse"),
                "rmse": reg_metrics.get("rmse"),
            },
        }

    except Exception as e:
        try:
            from flask import current_app
            current_app.logger.error(
                f"ML prediction failed for student {student_id}: {e}"
            )
        except RuntimeError:
            print(f"[AI] Prediction error for student {student_id}: {e}")

        return _rule_based_prediction(cgpa, scale)