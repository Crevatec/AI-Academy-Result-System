"""
backend/app/routes/api.py
--------------------------
RESTful API endpoints.
Used by the frontend JavaScript for:
- AI performance prediction
- Chart data for dashboards

All API responses are JSON.
Authentication: Requires login (session-based for browser clients).
CSRF is exempt on GET endpoints; POST endpoints require CSRF token.

Base URL: /api/v1/
"""

from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user

from app.models.user import Student
from app.models.result import Result, GPARecord, CGPARecord, AcademicSession
from app.ai.predictor import predict_student_performance
from app.utils.decorators import student_required, hod_required

api_bp = Blueprint("api", __name__)


@api_bp.route("/predict/<int:student_id>", methods=["GET"])
@login_required
def predict_performance(student_id: int):
    """
    AI prediction endpoint.

    Returns predicted risk level and estimated GPA for a student.
    Used on student dashboard and HOD monitoring panel.

    Response:
        {
            "student_id": 1,
            "matric": "CSC/2021/001",
            "risk_level": "At Risk" | "Average" | "Excellent",
            "predicted_gpa": 2.45,
            "confidence": 0.83
        }
    """
    # Students can only view their own prediction
    # HOD and Admin can view any student
    if current_user.role == "student":
        student = Student.query.filter_by(user_id=current_user.id).first()
        if student.id != student_id:
            return jsonify({"error": "Unauthorized"}), 403
    elif current_user.role not in ("hod", "admin"):
        return jsonify({"error": "Unauthorized"}), 403

    student = Student.query.get_or_404(student_id)

    try:
        prediction = predict_student_performance(student_id)
        return jsonify({
            "student_id": student_id,
            "matric": student.matric_number,
            "name": student.user.full_name,
            **prediction
        })
    except Exception as e:
        return jsonify({"error": str(e), "risk_level": "Unknown", "predicted_gpa": None}), 500


@api_bp.route("/student/<int:student_id>/gpa-trend", methods=["GET"])
@login_required
def gpa_trend(student_id: int):
    """
    Return GPA history for a student as JSON (used by Chart.js).

    Response:
        {
            "labels": ["2023/2024 S1", "2023/2024 S2"],
            "data": [3.50, 3.75]
        }
    """
    if current_user.role == "student":
        student = Student.query.filter_by(user_id=current_user.id).first()
        if student.id != student_id:
            return jsonify({"error": "Unauthorized"}), 403

    gpa_records = (
        GPARecord.query
        .filter_by(student_id=student_id)
        .join(AcademicSession, GPARecord.session_id == AcademicSession.id)
        .order_by(AcademicSession.session_name, AcademicSession.semester)
        .all()
    )

    labels = []
    data = []
    for record in gpa_records:
        session = AcademicSession.query.get(record.session_id)
        if session:
            labels.append(f"{session.session_name} S{session.semester}")
            data.append(record.gpa)

    return jsonify({"labels": labels, "data": data})


@api_bp.route("/department/<int:dept_id>/stats", methods=["GET"])
@login_required
def department_stats(dept_id: int):
    """
    Summary statistics for HOD dashboard charts.

    Returns:
        - Classification distribution (First Class, Second Class Upper, etc.)
        - Average department CGPA
    """
    if current_user.role not in ("hod", "admin"):
        return jsonify({"error": "Unauthorized"}), 403

    from app.models.course import Department
    from sqlalchemy import func

    dept = Department.query.get_or_404(dept_id)
    students = Student.query.filter_by(department_id=dept_id).all()
    student_ids = [s.id for s in students]

    cgpa_records = CGPARecord.query.filter(CGPARecord.student_id.in_(student_ids)).all()

    # Count classifications
    classification_counts = {}
    for record in cgpa_records:
        c = record.classification or "No Results"
        classification_counts[c] = classification_counts.get(c, 0) + 1

    avg_cgpa = (
        sum(r.cgpa for r in cgpa_records) / len(cgpa_records)
        if cgpa_records else 0
    )

    return jsonify({
        "department": dept.name,
        "student_count": len(students),
        "with_results": len(cgpa_records),
        "average_cgpa": round(avg_cgpa, 2),
        "classification_distribution": classification_counts,
    })


@api_bp.route("/health", methods=["GET"])
def health_check():
    """
    Simple health check endpoint.
    Used by deployment monitoring (uptime checks, load balancers).
    """
    return jsonify({"status": "ok", "service": "AcadResult API"}), 200
