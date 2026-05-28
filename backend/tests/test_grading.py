"""
backend/tests/test_grading.py
------------------------------
Unit tests for the grading service.

Run with:
    cd backend
    pytest tests/test_grading.py -v

Tests cover:
- Grade and grade point computation for both 4.0 and 5.0 scales
- Edge cases (boundary scores, invalid inputs)
- CGPA classification
- Carryover detection
"""

import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.grading import (
    compute_grade,
    classify_gpa,
    is_carryover,
    get_grading_system,
)


class TestGrading5Scale:
    """Tests for the 5.0 grading scale (University)."""

    def test_grade_A(self):
        grade, gp = compute_grade(75, "5.0")
        assert grade == "A"
        assert gp == 5.00

    def test_grade_A_boundary_lower(self):
        grade, gp = compute_grade(70, "5.0")
        assert grade == "A"

    def test_grade_A_boundary_upper(self):
        grade, gp = compute_grade(100, "5.0")
        assert grade == "A"

    def test_grade_B(self):
        grade, gp = compute_grade(65, "5.0")
        assert grade == "B"
        assert gp == 4.00

    def test_grade_B_boundary_lower(self):
        grade, gp = compute_grade(60, "5.0")
        assert grade == "B"

    def test_grade_B_boundary_upper(self):
        grade, gp = compute_grade(69, "5.0")
        assert grade == "B"

    def test_grade_C(self):
        grade, gp = compute_grade(55, "5.0")
        assert grade == "C"
        assert gp == 3.00

    def test_grade_D(self):
        grade, gp = compute_grade(47, "5.0")
        assert grade == "D"
        assert gp == 2.00

    def test_grade_E(self):
        grade, gp = compute_grade(42, "5.0")
        assert grade == "E"
        assert gp == 1.00

    def test_grade_F(self):
        grade, gp = compute_grade(30, "5.0")
        assert grade == "F"
        assert gp == 0.00

    def test_grade_F_zero(self):
        grade, gp = compute_grade(0, "5.0")
        assert grade == "F"

    def test_grade_F_boundary(self):
        grade, gp = compute_grade(39, "5.0")
        assert grade == "F"


class TestGrading4Scale:
    """Tests for the 4.0 grading scale (Polytechnic)."""

    def test_grade_A(self):
        grade, gp = compute_grade(85, "4.0")
        assert grade == "A"
        assert gp == 4.00

    def test_grade_A_boundary(self):
        grade, gp = compute_grade(80, "4.0")
        assert grade == "A"

    def test_grade_B(self):
        grade, gp = compute_grade(75, "4.0")
        assert grade == "B"
        assert gp == 3.50

    def test_grade_C(self):
        grade, gp = compute_grade(65, "4.0")
        assert grade == "C"
        assert gp == 3.00

    def test_grade_D(self):
        grade, gp = compute_grade(55, "4.0")
        assert grade == "D"
        assert gp == 2.50

    def test_grade_E(self):
        grade, gp = compute_grade(45, "4.0")
        assert grade == "E"
        assert gp == 2.00

    def test_grade_F(self):
        grade, gp = compute_grade(35, "4.0")
        assert grade == "F"
        assert gp == 0.00


class TestEdgeCases:
    """Edge case and error handling tests."""

    def test_invalid_scale(self):
        with pytest.raises(ValueError):
            compute_grade(70, "3.0")

    def test_score_above_100(self):
        with pytest.raises(ValueError):
            compute_grade(105, "5.0")

    def test_score_below_zero(self):
        with pytest.raises(ValueError):
            compute_grade(-5, "5.0")

    def test_unknown_scale_raises(self):
        with pytest.raises(ValueError):
            get_grading_system("6.0")


class TestClassification5Scale:
    """GPA classification for 5.0 scale."""

    def test_first_class(self):
        assert classify_gpa(4.75, "5.0") == "First Class"

    def test_first_class_boundary(self):
        assert classify_gpa(4.50, "5.0") == "First Class"

    def test_second_class_upper(self):
        assert classify_gpa(3.80, "5.0") == "Second Class Upper"

    def test_second_class_lower(self):
        assert classify_gpa(2.80, "5.0") == "Second Class Lower"

    def test_third_class(self):
        assert classify_gpa(1.80, "5.0") == "Third Class"

    def test_probation(self):
        assert classify_gpa(1.00, "5.0") == "Probation/Fail"

    def test_probation_zero(self):
        assert classify_gpa(0.00, "5.0") == "Probation/Fail"


class TestClassification4Scale:
    """GPA classification for 4.0 scale."""

    def test_distinction(self):
        assert classify_gpa(3.80, "4.0") == "Distinction"

    def test_upper_credit(self):
        assert classify_gpa(3.20, "4.0") == "Upper Credit"

    def test_lower_credit(self):
        assert classify_gpa(2.70, "4.0") == "Lower Credit"

    def test_pass(self):
        assert classify_gpa(2.10, "4.0") == "Pass"

    def test_fail(self):
        assert classify_gpa(1.50, "4.0") == "Fail"


class TestCarryover:
    """Carryover detection."""

    def test_F_is_carryover(self):
        assert is_carryover("F") is True

    def test_E_is_not_carryover(self):
        assert is_carryover("E") is False

    def test_A_is_not_carryover(self):
        assert is_carryover("A") is False
