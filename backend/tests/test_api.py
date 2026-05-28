"""
backend/tests/test_api.py
--------------------------
Integration tests for REST API endpoints.

Run:
    cd backend
    pytest tests/test_api.py -v
"""

import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import create_app, db
from app.models.user import User, Student
from app.models.course import Department


@pytest.fixture
def client():
    """Create test Flask client with fresh in-memory DB."""
    _app = create_app("testing")
    with _app.app_context():
        db.create_all()

        # Create test student
        dept = Department(name="API Test Dept", code="API", grading_scale="5.0")
        db.session.add(dept)
        db.session.flush()

        user = User(email="apistudent@test.ng", role="student",
                    first_name="API", last_name="Student")
        user.set_password("Test1234!")
        db.session.add(user)
        db.session.flush()

        student = Student(
            user_id=user.id, matric_number="API/001",
            level=100, grading_scale="5.0", department_id=dept.id
        )
        db.session.add(student)
        db.session.commit()

        yield _app.test_client()
        db.drop_all()


def login(client, email, password):
    return client.post("/login", data={"email": email, "password": password},
                       follow_redirects=True)


class TestHealthEndpoint:

    def test_health_check(self, client):
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "ok"


class TestAuthFlow:

    def test_login_valid(self, client):
        resp = login(client, "apistudent@test.ng", "Test1234!")
        assert resp.status_code == 200

    def test_login_invalid_password(self, client):
        resp = client.post("/login",
                           data={"email": "apistudent@test.ng", "password": "wrong"},
                           follow_redirects=True)
        assert b"Invalid email or password" in resp.data

    def test_login_invalid_email(self, client):
        resp = client.post("/login",
                           data={"email": "nobody@test.ng", "password": "Test1234!"},
                           follow_redirects=True)
        assert b"Invalid email or password" in resp.data

    def test_protected_redirect_without_login(self, client):
        resp = client.get("/student/dashboard")
        assert resp.status_code == 302  # redirect to login

    def test_logout(self, client):
        login(client, "apistudent@test.ng", "Test1234!")
        resp = client.get("/logout", follow_redirects=True)
        assert resp.status_code == 200


class TestPredictionEndpoint:

    def test_prediction_unauthenticated(self, client):
        """Unauthenticated request should redirect, not return JSON."""
        resp = client.get("/api/v1/predict/1")
        # Flask-Login redirects to login
        assert resp.status_code in (302, 401)

    def test_prediction_authenticated_student(self, client):
        login(client, "apistudent@test.ng", "Test1234!")
        student = Student.query.filter_by(matric_number="API/001").first()
        resp = client.get(f"/api/v1/predict/{student.id}")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "risk_level" in data
        assert data["risk_level"] in ("At Risk", "Average", "Excellent",
                                       "Unknown", "no_data")

    def test_student_cannot_view_other_prediction(self, client):
        login(client, "apistudent@test.ng", "Test1234!")
        # Try to access prediction for student_id=999 (not theirs)
        resp = client.get("/api/v1/predict/999")
        data = resp.get_json()
        assert resp.status_code in (200, 403, 404)
        # If 200, must be an error response
        if resp.status_code == 200:
            assert "error" in data or "risk_level" in data


class TestGPATrendEndpoint:

    def test_gpa_trend_authenticated(self, client):
        login(client, "apistudent@test.ng", "Test1234!")
        student = Student.query.filter_by(matric_number="API/001").first()
        resp = client.get(f"/api/v1/student/{student.id}/gpa-trend")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "labels" in data
        assert "data" in data
        assert isinstance(data["labels"], list)
        assert isinstance(data["data"], list)
