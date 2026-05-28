"""
backend/app/routes/student.py  (UPDATED)
-----------------------------------------
New features:
- Access control enforcement (HOD can block result viewing)
- Carryover summary on dashboard
- Download own transcript as Excel
- View both current and previous session results
"""

import io
from flask import Blueprint, render_template, jsonify, request, send_file, flash, redirect, url_for
from flask_login import current_user

from app.models.user import Student
from app.models.result import (Result, GPARecord, CGPARecord, AcademicSession,
                                ResultAccessControl)
from app.services.carryover_service import get_student_carryovers
from app.services.export_service import export_student_transcript
from app.utils.decorators import student_required

student_bp = Blueprint("student", __name__)


def get_current_student() -> Student:
    return Student.query.filter_by(user_id=current_user.id).first()


def check_access(student_id: int):
    """
    Returns (access_granted: bool, reason: str | None).
    If HOD has blocked this student, access_granted = False.
    """
    access = ResultAccessControl.query.filter_by(student_id=student_id).first()
    if access and not access.access_granted:
        return False, access.restriction_reason
    return True, None


@student_bp.route("/dashboard")
@student_required
def dashboard():
    student = get_current_student()

    # ── Access gate ───────────────────────────────────────────────────────────
    access_ok, restriction_reason = check_access(student.id)
    if not access_ok:
        return render_template(
            "student/access_blocked.html",
            reason=restriction_reason,
            student=student,
        )

    cgpa_record = CGPARecord.query.filter_by(student_id=student.id).first()

    # GPA trend for Chart.js
    gpa_records = (
        GPARecord.query
        .filter_by(student_id=student.id)
        .join(AcademicSession, GPARecord.session_id == AcademicSession.id)
        .order_by(AcademicSession.session_name, AcademicSession.semester)
        .all()
    )

    chart_labels = []
    chart_data = []
    for gpr in gpa_records:
        sess = AcademicSession.query.get(gpr.session_id)
        if sess:
            chart_labels.append(f"{sess.session_name} S{sess.semester}")
            chart_data.append(gpr.gpa)

    # Current session results
    current_session = AcademicSession.query.filter_by(is_current=True).first()
    current_results = []
    if current_session and current_session.is_results_released:
        current_results = Result.query.filter_by(
            student_id=student.id,
            session_id=current_session.id,
            status="approved"
        ).all()

    # Carryover summary
    carryover_data = get_student_carryovers(student.id)

    return render_template(
        "student/dashboard.html",
        student=student,
        cgpa_record=cgpa_record,
        gpa_records=gpa_records,
        chart_labels=chart_labels,
        chart_data=chart_data,
        current_results=current_results,
        current_session=current_session,
        carryover_data=carryover_data,
    )


@student_bp.route("/results/<int:session_id>")
@student_required
def results_by_session(session_id: int):
    """View full result slip for a specific semester. Enforces access control."""
    student = get_current_student()

    access_ok, restriction_reason = check_access(student.id)
    if not access_ok:
        return render_template(
            "student/access_blocked.html",
            reason=restriction_reason,
            student=student,
        )

    session = AcademicSession.query.get_or_404(session_id)

    if not session.is_results_released:
        return render_template("student/results_pending.html", session=session)

    results = Result.query.filter_by(
        student_id=student.id, session_id=session_id, status="approved"
    ).all()

    gpa_record = GPARecord.query.filter_by(
        student_id=student.id, session_id=session_id
    ).first()

    return render_template(
        "student/result_slip.html",
        results=results,
        session=session,
        student=student,
        gpa_record=gpa_record,
    )


@student_bp.route("/all-sessions")
@student_required
def all_sessions():
    """List all sessions with approved results (current + previous)."""
    student = get_current_student()

    access_ok, restriction_reason = check_access(student.id)
    if not access_ok:
        return render_template(
            "student/access_blocked.html",
            reason=restriction_reason,
            student=student,
        )

    sessions_with_results = (
        AcademicSession.query
        .join(Result, Result.session_id == AcademicSession.id)
        .filter(
            Result.student_id == student.id,
            Result.status == "approved",
            AcademicSession.is_results_released == True,
        )
        .distinct()
        .order_by(AcademicSession.session_name.desc(), AcademicSession.semester.desc())
        .all()
    )

    # Attach GPA per session
    sessions_data = []
    for sess in sessions_with_results:
        gpa_rec = GPARecord.query.filter_by(
            student_id=student.id, session_id=sess.id
        ).first()
        sessions_data.append({"session": sess, "gpa": gpa_rec})

    cgpa_record = CGPARecord.query.filter_by(student_id=student.id).first()

    return render_template(
        "student/sessions.html",
        sessions_data=sessions_data,
        student=student,
        cgpa_record=cgpa_record,
    )


@student_bp.route("/carryovers")
@student_required
def carryovers():
    """Student views their pending and cleared carryover courses."""
    student = get_current_student()

    access_ok, restriction_reason = check_access(student.id)
    if not access_ok:
        return render_template(
            "student/access_blocked.html",
            reason=restriction_reason,
            student=student,
        )

    carryover_data = get_student_carryovers(student.id)

    return render_template(
        "student/carryovers.html",
        carryover_data=carryover_data,
        student=student,
    )


@student_bp.route("/download-transcript")
@student_required
def download_transcript():
    """Student downloads their own full academic transcript as Excel."""
    student = get_current_student()

    access_ok, restriction_reason = check_access(student.id)
    if not access_ok:
        flash("Your result access is currently restricted. Contact your department.", "danger")
        return redirect(url_for("student.dashboard"))

    try:
        excel_bytes = export_student_transcript(student.id)
    except Exception as e:
        flash(f"Could not generate transcript: {e}", "danger")
        return redirect(url_for("student.dashboard"))

    filename = f"Transcript_{student.matric_number.replace('/', '-')}.xlsx"
    return send_file(
        io.BytesIO(excel_bytes),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=filename,
    )
