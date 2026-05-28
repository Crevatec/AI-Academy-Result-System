"""
backend/app/services/grading.py
--------------------------------
All grading logic lives here — separate from routes and models.

Why a service layer?
- Routes handle HTTP (request/response)
- Models handle data storage
- Services handle BUSINESS LOGIC
- Keeps each layer thin and testable

Both grading systems are defined as data structures.
Switching a department from 5.0 to 4.0 only requires changing
the `grading_scale` field in Department — no code changes needed.
"""

from typing import Tuple


# ── Grading System Definitions ────────────────────────────────────────────────
# Each entry: (min_score, max_score, grade_letter, grade_point)

GRADING_5_0 = {
    "scale": 5.0,
    "grade_map": [
        (70, 100, "A", 5.00),
        (60, 69,  "B", 4.00),
        (50, 59,  "C", 3.00),
        (45, 49,  "D", 2.00),
        (40, 44,  "E", 1.00),
        (0,  39,  "F", 0.00),
    ],
    "classification": [
        (4.50, 5.00, "First Class"),
        (3.50, 4.49, "Second Class Upper"),
        (2.40, 3.49, "Second Class Lower"),
        (1.50, 2.39, "Third Class"),
        (0.00, 1.49, "Probation/Fail"),
    ]
}

GRADING_4_0 = {
    "scale": 4.0,
    "grade_map": [
        (80, 100, "A", 4.00),
        (70, 79,  "B", 3.50),
        (60, 69,  "C", 3.00),
        (50, 59,  "D", 2.50),
        (40, 49,  "E", 2.00),
        (0,  39,  "F", 0.00),
    ],
    "classification": [
        (3.50, 4.00, "Distinction"),
        (3.00, 3.49, "Upper Credit"),
        (2.50, 2.99, "Lower Credit"),
        (2.00, 2.49, "Pass"),
        (0.00, 1.99, "Fail"),
    ]
}

# Lookup by string key to make config-driven selection easy
GRADING_SYSTEMS = {
    "5.0": GRADING_5_0,
    "4.0": GRADING_4_0,
}


def get_grading_system(scale: str) -> dict:
    """
    Return grading system config by scale string.
    Raises ValueError for unknown scales.
    """
    if scale not in GRADING_SYSTEMS:
        raise ValueError(f"Unknown grading scale: '{scale}'. Use '4.0' or '5.0'.")
    return GRADING_SYSTEMS[scale]


def compute_grade(score: float, scale: str) -> Tuple[str, float]:
    """
    Given a raw score (0-100) and a grading scale,
    return the (grade_letter, grade_point) tuple.

    Example:
        compute_grade(72, "5.0") → ("A", 5.00)
        compute_grade(65, "4.0") → ("C", 3.00)
        compute_grade(35, "5.0") → ("F", 0.00)

    Args:
        score: Student's percentage score (0–100)
        scale: '4.0' or '5.0'

    Returns:
        (grade_letter: str, grade_point: float)

    Raises:
        ValueError: If score is outside 0–100 range
    """
    if not (0 <= score <= 100):
        raise ValueError(f"Score must be between 0 and 100. Got: {score}")

    system = get_grading_system(scale)

    for min_s, max_s, grade, gp in system["grade_map"]:
        if min_s <= score <= max_s:
            return grade, gp

    # Should never reach here given the 0-100 validation above
    return "F", 0.00


def classify_gpa(gpa: float, scale: str) -> str:
    """
    Given a GPA or CGPA and grading scale, return the academic classification.

    Example:
        classify_gpa(4.6, "5.0") → "First Class"
        classify_gpa(3.1, "4.0") → "Upper Credit"
        classify_gpa(0.5, "5.0") → "Probation/Fail"

    Args:
        gpa: GPA value to classify
        scale: '4.0' or '5.0'

    Returns:
        Classification string
    """
    system = get_grading_system(scale)

    for min_c, max_c, label in system["classification"]:
        if min_c <= gpa <= max_c:
            return label

    return "Unknown"


def is_carryover(grade: str) -> bool:
    """
    A student has a carryover if they scored F in a course.
    Used to flag courses that must be retaken.
    """
    return grade == "F"
