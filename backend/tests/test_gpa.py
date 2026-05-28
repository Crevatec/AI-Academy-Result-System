"""
backend/tests/test_gpa.py
--------------------------
Tests for GPA/CGPA computation engine and carryover scheduling.

Run:
    cd backend
    pytest tests/test_gpa.py -v
"""

import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import create_app, db
from app.models.user import User, Student
from app.models.course import Department, Course
from app.models.result import Result, AcademicSession, GPARecord, CGPARecord
from app.services.gpa_engine import compute_gpa_for_session, compute_cgpa
from app.services.carryover_service import process_carryovers_for_session
from app.services.grading import compute_grade


@pytest.fixture(scope="module")
def app():
    """Create test app with in-memory SQLite."""
    _app = create_app("testing")
    with _app.app_context():
        db.create_all()
        yield _app
        db.drop_all()


@pytest.fixture(scope="module")
def seeded_data(app):
    """
    Create minimal DB records for testing:
    1 department, 1 student, 3 courses, 1 session, 3 results.
    """
    with app.app_context():
        dept = Department(name="Test Dept", code="TEST", grading_scale="5.0")
        db.session.add(dept)
        db.session.flush()

        user = User(
            email="teststudent@test.ng",
            role="student",
            first_name="Test",
            last_name="Student",
        )
        user.set_password("Test1234!")
        db.session.add(user)
        db.session.flush()

        student = Student(
            user_id=user.id,
            matric_number="TEST/2024/001",
            level=100,
            grading_scale="5.0",
            department_id=dept.id,
        )
        db.session.add(student)
        db.session.flush()

        courses = [
            Course(code="TEST101", title="Course A", unit=3, level=100, semester=1, department_id=dept.id),
            Course(code="TEST102", title="Course B", unit=2, level=100, semester=1, department_id=dept.id),
            Course(code="TEST103", title="Course C", unit=3, level=100, semester=1, department_id=dept.id),
        ]
        db.session.add_all(courses)
        db.session.flush()

        session = AcademicSession(
            session_name="2024/2025", semester=1, is_current=True
        )
        db.session.add(session)
        db.session.flush()

        # Lecturer user (needed as submitted_by FK)
        lec_user = User(email="testlec@test.ng", role="lecturer", first_name="L", last_name="L")
        lec_user.set_password("x")
        db.session.add(lec_user)
        db.session.flush()

        # Scores: 70 (A=5), 60 (B=4), 50 (C=3)
        scores = [70, 60, 50]
        results = []
        for course, score in zip(courses, scores):
            grade, gp = compute_grade(score, "5.0")
            r = Result(
                student_id=student.id,
                course_id=course.id,
                session_id=session.id,
                submitted_by=lec_user.id,
                score=score,
                grade=grade,
                grade_point=gp,
                status="approved",
            )
            db.session.add(r)
            results.append(r)

        db.session.commit()

        return {
            "student": student,
            "session": session,
            "courses": courses,
            "results": results,
        }


class TestGPAComputation:
    """
    Manual verification:
        Course A: GP=5.0 × 3 units = 15.0
        Course B: GP=4.0 × 2 units =  8.0
        Course C: GP=3.0 × 3 units =  9.0
        Total GP points = 32.0
        Total units     =  8
        GPA = 32.0 / 8 = 4.00
    """

    def test_gpa_computed_correctly(self, app, seeded_data):
        with app.app_context():
            student = Student.query.filter_by(matric_number="TEST/2024/001").first()
            session = AcademicSession.query.filter_by(session_name="2024/2025").first()

            gpa_record = compute_gpa_for_session(student.id, session.id)

            assert gpa_record is not None
            assert gpa_record.gpa == pytest.approx(4.00, abs=0.01)

    def test_gpa_total_units(self, app, seeded_data):
        with app.app_context():
            student = Student.query.filter_by(matric_number="TEST/2024/001").first()
            session = AcademicSession.query.filter_by(session_name="2024/2025").first()
            gpa_record = GPARecord.query.filter_by(
                student_id=student.id, session_id=session.id
            ).first()
            assert gpa_record.total_units == 8

    def test_gpa_classification(self, app, seeded_data):
        with app.app_context():
            student = Student.query.filter_by(matric_number="TEST/2024/001").first()
            session = AcademicSession.query.filter_by(session_name="2024/2025").first()
            gpa_record = GPARecord.query.filter_by(
                student_id=student.id, session_id=session.id
            ).first()
            # GPA 4.00 → Second Class Upper (3.50–4.49)
            assert gpa_record.classification == "Second Class Upper"


class TestCGPAComputation:

    def test_cgpa_matches_gpa_for_single_session(self, app, seeded_data):
        with app.app_context():
            student = Student.query.filter_by(matric_number="TEST/2024/001").first()
            cgpa_record = compute_cgpa(student.id)

            assert cgpa_record is not None
            # With only 1 session, CGPA == GPA
            assert cgpa_record.cgpa == pytest.approx(4.00, abs=0.01)

    def test_cgpa_semesters_completed(self, app, seeded_data):
        with app.app_context():
            student = Student.query.filter_by(matric_number="TEST/2024/001").first()
            cgpa_record = CGPARecord.query.filter_by(student_id=student.id).first()
            assert cgpa_record.semesters_completed == 1


class TestCarryoverScheduling:

    def test_no_carryover_for_passing_grades(self, app, seeded_data):
        """Scores 70, 60, 50 all pass on 5.0 scale — no carryovers expected."""
        with app.app_context():
            from app.models.result import CarryoverRecord
            student = Student.query.filter_by(matric_number="TEST/2024/001").first()
            session = AcademicSession.query.filter_by(session_name="2024/2025").first()

            process_carryovers_for_session(student.id, session.id)

            pending = CarryoverRecord.query.filter_by(
                student_id=student.id, status="pending"
            ).count()
            assert pending == 0

    def test_carryover_created_for_F_grade(self, app, seeded_data):
        """Add a failing result and verify carryover is scheduled."""
        with app.app_context():
            from app.models.result import CarryoverRecord
            student = Student.query.filter_by(matric_number="TEST/2024/001").first()
            session = AcademicSession.query.filter_by(session_name="2024/2025").first()

            # Create a new course and failing result
            dept = Department.query.filter_by(code="TEST").first()
            lec_user = User.query.filter_by(email="testlec@test.ng").first()

            fail_course = Course(
                code="FAIL101", title="Fail Course", unit=2,
                level=100, semester=1, department_id=dept.id
            )
            db.session.add(fail_course)
            db.session.flush()

            fail_result = Result(
                student_id=student.id,
                course_id=fail_course.id,
                session_id=session.id,
                submitted_by=lec_user.id,
                score=25.0,
                grade="F",
                grade_point=0.0,
                status="approved",
            )
            db.session.add(fail_result)
            db.session.commit()

            process_carryovers_for_session(student.id, session.id)

            carryover = CarryoverRecord.query.filter_by(
                student_id=student.id,
                course_id=fail_course.id,
                status="pending",
            ).first()

            assert carryover is not None
            # Level 100 Sem 1 → retake Level 200 Sem 1
            assert carryover.recommended_retake_level == 200
            assert carryover.recommended_retake_semester == 1
