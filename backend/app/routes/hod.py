"""
backend/app/routes/hod.py
--------------------------------------
Features:
- Batch approval: approve all pending results for a course in one click
- Individual student approval: approve a single student's result
- Result access control: grant/restrict per-student result access
- Export: department results + carryover report as downloadable Excel
- Carryover dashboard: view all students with pending carryovers
"""

from datetime import datetime
from flask import (Blueprint, render_template, redirect, url_for,
                   flash, request, send_file, current_app)
from flask_login import current_user
import io

from app import db
from app.models.user import User, Student
from app.models.course import Department, Course
from app.models.result import (Result, GPARecord, CGPARecord, AcademicSession,
                                ResultAccessControl, CarryoverRecord)
from app.services.gpa_engine import recompute_all_for_student
from app.services.email_service import send_bulk_result_notifications
from app.services.carryover_service import (process_carryovers_for_session,
                                             get_department_carryover_summary)
from app.services.export_service import (export_department_results,
                                          export_student_transcript,
                                          export_carryover_report)
from app.utils.decorators import hod_required

hod_bp = Blueprint("hod", __name__)


def get_hod_department() -> Department:
    return Department.query.filter_by(hod_user_id=current_user.id).first()


def get_current_session() -> AcademicSession:
    return AcademicSession.query.filter_by(is_current=True).first()


# ── Dashboard ────────────────────────────────────────────────────────────────

@hod_bp.route("/dashboard")
@hod_required
def dashboard():
    department = get_hod_department()
    current_session = get_current_session()

    if not department:
        flash("No department assigned to your account. Contact Admin.", "warning")
        return render_template("hod/dashboard.html", department=None)

    pending_results = []
    if current_session:
        pending_results = (
            Result.query
            .join(Result.course)
            .filter(
                Course.department_id == department.id,
                Result.session_id == current_session.id,
                Result.status == "pending"
            ).all()
        )

    # Group by course
    pending_by_course = {}
    for result in pending_results:
        cid = result.course_id
        if cid not in pending_by_course:
            pending_by_course[cid] = {
                "course": result.course,
                "results": [],
                "lecturer": User.query.get(result.submitted_by),
            }
        pending_by_course[cid]["results"].append(result)

    student_count = Student.query.filter_by(department_id=department.id).count()

    # Count at-risk students
    dept_student_ids = [s.id for s in Student.query.filter_by(department_id=department.id).all()]
    at_risk_count = CGPARecord.query.filter(
        CGPARecord.student_id.in_(dept_student_ids),
        CGPARecord.classification.in_(["Probation/Fail", "Fail"])
    ).count()

    # Carryover count
    co_count = CarryoverRecord.query.filter(
        CarryoverRecord.student_id.in_(dept_student_ids),
        CarryoverRecord.status == "pending"
    ).count()

    return render_template(
        "hod/dashboard.html",
        department=department,
        pending_by_course=list(pending_by_course.values()),
        pending_count=len(pending_results),
        student_count=student_count,
        current_session=current_session,
        at_risk_count=at_risk_count,
        co_count=co_count,
    )


# ── Course Review ────────────────────────────────────────────────────────────

@hod_bp.route("/course/<int:course_id>/review")
@hod_required
def review_course(course_id: int):
    department = get_hod_department()
    course = Course.query.get_or_404(course_id)
    current_session = get_current_session()

    if course.department_id != department.id:
        flash("This course does not belong to your department.", "danger")
        return redirect(url_for("hod.dashboard"))

    pending_results = (
        Result.query
        .filter_by(course_id=course_id, session_id=current_session.id, status="pending")
        .all()
    )
    lecturer = User.query.get(pending_results[0].submitted_by) if pending_results else None

    return render_template(
        "hod/review_course.html",
        course=course,
        results=pending_results,
        lecturer=lecturer,
        current_session=current_session,
    )


# ── Batch Approval (all pending results for a course) ───────────────────────

@hod_bp.route("/course/<int:course_id>/approve-all", methods=["POST"])
@hod_required
def approve_all_results(course_id: int):
    """Approve ALL pending results for a course at once."""
    department = get_hod_department()
    current_session = get_current_session()
    course = Course.query.get_or_404(course_id)

    if course.department_id != department.id:
        flash("Unauthorized.", "danger")
        return redirect(url_for("hod.dashboard"))

    pending = Result.query.filter_by(
        course_id=course_id,
        session_id=current_session.id,
        status="pending"
    ).all()

    if not pending:
        flash("No pending results found.", "info")
        return redirect(url_for("hod.dashboard"))

    _approve_and_notify(pending, current_session)

    flash(
        f"✓ Batch approved {len(pending)} results for {course.code}. "
        f"GPA/CGPA updated and carryovers scheduled.",
        "success"
    )
    return redirect(url_for("hod.dashboard"))


# ── Single Student Approval ──────────────────────────────────────────────────

@hod_bp.route("/result/<int:result_id>/approve", methods=["POST"])
@hod_required
def approve_single_result(result_id: int):
    """Approve one specific student's result independently."""
    result = Result.query.get_or_404(result_id)
    department = get_hod_department()
    current_session = get_current_session()

    if result.course.department_id != department.id:
        flash("Unauthorized.", "danger")
        return redirect(url_for("hod.dashboard"))

    if result.status != "pending":
        flash(f"Result is already '{result.status}'.", "warning")
        return redirect(url_for("hod.review_course", course_id=result.course_id))

    _approve_and_notify([result], current_session)

    flash(
        f"✓ Result for {result.student.user.full_name} ({result.course.code}) approved.",
        "success"
    )
    return redirect(url_for("hod.review_course", course_id=result.course_id))


def _approve_and_notify(results: list, current_session):
    """
    Internal helper: approve a list of Result objects,
    recompute GPA/CGPA, process carryovers, send emails.

    Builds a student_list and passes it to send_bulk_result_notifications,
    which handles both result release emails and low GPA warnings in one call.
    """
    affected_students = set()

    for result in results:
        result.status      = "approved"
        result.approved_at = datetime.utcnow()
        affected_students.add(result.student_id)

    db.session.commit()

    # Build the student list for bulk email notification
    student_list = []

    for student_id in affected_students:
        gpa_data = recompute_all_for_student(student_id, current_session.id)
        process_carryovers_for_session(student_id, current_session.id)

        student = Student.query.get(student_id)

        # Only queue email if results are released and access is granted
        if gpa_data["gpa"] and current_session.is_results_released:
            access = ResultAccessControl.query.filter_by(student_id=student_id).first()
            if not access or access.access_granted:
                student_list.append({
                    "student":        student,
                    "gpa":            gpa_data["gpa"],
                    "cgpa":           gpa_data["cgpa"],
                    "classification": gpa_data["cgpa_classification"],
                })

    # Send all emails in one call.
    # send_bulk_result_notifications also fires low GPA warnings automatically
    # for any student classified as Probation/Fail, Fail, or Third Class.
    if student_list:
        email_result = send_bulk_result_notifications(
            student_list=student_list,
            session_name=current_session.session_name,
            semester=current_session.semester,
        )
        current_app.logger.info(
            f"Bulk emails — sent: {email_result['sent']}, "
            f"failed: {email_result['failed']} | "
            f"{current_session.session_name} Sem {current_session.semester}"
        )


# ── Reject Results ───────────────────────────────────────────────────────────

@hod_bp.route("/course/<int:course_id>/reject", methods=["POST"])
@hod_required
def reject_results(course_id: int):
    department = get_hod_department()
    current_session = get_current_session()
    course = Course.query.get_or_404(course_id)

    if course.department_id != department.id:
        flash("Unauthorized.", "danger")
        return redirect(url_for("hod.dashboard"))

    comment = request.form.get("comment", "").strip()
    if not comment:
        flash("Provide a reason for rejection.", "warning")
        return redirect(url_for("hod.review_course", course_id=course_id))

    pending = Result.query.filter_by(
        course_id=course_id,
        session_id=current_session.id,
        status="pending"
    ).all()

    for result in pending:
        result.status      = "rejected"
        result.hod_comment = comment

    db.session.commit()
    flash(f"Results for {course.code} rejected and returned to lecturer.", "info")
    return redirect(url_for("hod.dashboard"))


# ── Result Access Control ────────────────────────────────────────────────────

@hod_bp.route("/students/access")
@hod_required
def manage_access():
    """List all students with their current result access status."""
    department = get_hod_department()
    students = Student.query.filter_by(department_id=department.id).all()

    access_data = []
    for student in students:
        access = ResultAccessControl.query.filter_by(student_id=student.id).first()
        access_data.append({
            "student":        student,
            "access_granted": access.access_granted if access else True,
            "reason":         access.restriction_reason if access else None,
        })

    return render_template(
        "hod/manage_access.html",
        access_data=access_data,
        department=department,
    )


@hod_bp.route("/students/<int:student_id>/restrict-access", methods=["POST"])
@hod_required
def restrict_access(student_id: int):
    """Block a student from viewing their results."""
    department = get_hod_department()
    student = Student.query.get_or_404(student_id)

    if student.department_id != department.id:
        flash("Unauthorized.", "danger")
        return redirect(url_for("hod.manage_access"))

    reason = request.form.get("reason", "").strip()
    if not reason:
        flash("Please provide a restriction reason.", "warning")
        return redirect(url_for("hod.manage_access"))

    access = ResultAccessControl.query.filter_by(student_id=student_id).first()
    if not access:
        access = ResultAccessControl(student_id=student_id)
        db.session.add(access)

    access.access_granted      = False
    access.restriction_reason  = reason
    access.restricted_by       = current_user.id
    access.restricted_at       = datetime.utcnow()

    db.session.commit()
    flash(f"Result access restricted for {student.user.full_name}.", "warning")
    return redirect(url_for("hod.manage_access"))


@hod_bp.route("/students/<int:student_id>/grant-access", methods=["POST"])
@hod_required
def grant_access(student_id: int):
    """Restore a student's result viewing access."""
    department = get_hod_department()
    student = Student.query.get_or_404(student_id)

    if student.department_id != department.id:
        flash("Unauthorized.", "danger")
        return redirect(url_for("hod.manage_access"))

    access = ResultAccessControl.query.filter_by(student_id=student_id).first()
    if access:
        access.access_granted     = True
        access.restriction_reason = None
        access.restricted_at      = None
        db.session.commit()

    flash(f"Result access restored for {student.user.full_name}.", "success")
    return redirect(url_for("hod.manage_access"))


# ── Carryover Management ─────────────────────────────────────────────────────

@hod_bp.route("/carryovers")
@hod_required
def carryovers():
    """List all students with pending carryover courses."""
    department = get_hod_department()
    summary = get_department_carryover_summary(department.id)

    return render_template(
        "hod/carryovers.html",
        summary=summary,
        department=department,
    )


# ── Reports ──────────────────────────────────────────────────────────────────

@hod_bp.route("/reports")
@hod_required
def reports():
    department = get_hod_department()
    students = Student.query.filter_by(department_id=department.id).all()
    sessions = AcademicSession.query.order_by(
        AcademicSession.session_name.desc(), AcademicSession.semester
    ).all()

    report_data = []
    for student in students:
        cgpa_record = CGPARecord.query.filter_by(student_id=student.id).first()
        co_count = CarryoverRecord.query.filter_by(
            student_id=student.id, status="pending"
        ).count()
        report_data.append({
            "student":        student,
            "cgpa":           cgpa_record.cgpa if cgpa_record else None,
            "classification": cgpa_record.classification if cgpa_record else "No results",
            "carryovers":     co_count,
        })

    report_data.sort(key=lambda x: x["cgpa"] or 0, reverse=True)

    return render_template(
        "hod/reports.html",
        report_data=report_data,
        department=department,
        sessions=sessions,
    )


# ── Excel Exports ────────────────────────────────────────────────────────────

@hod_bp.route("/export/department-results/<int:session_id>")
@hod_required
def export_dept_results(session_id: int):
    """Download full department result sheet as Excel."""
    department = get_hod_department()
    session = AcademicSession.query.get_or_404(session_id)

    try:
        excel_bytes = export_department_results(department.id, session_id)
    except Exception as e:
        flash(f"Export failed: {e}", "danger")
        return redirect(url_for("hod.reports"))

    filename = (
        f"{department.code}_Results_"
        f"{session.session_name.replace('/', '-')}_Sem{session.semester}.xlsx"
    )
    return send_file(
        io.BytesIO(excel_bytes),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=filename,
    )


@hod_bp.route("/export/carryovers")
@hod_required
def export_carryovers_xlsx():
    """Download carryover report as Excel."""
    department = get_hod_department()
    try:
        excel_bytes = export_carryover_report(department.id)
    except Exception as e:
        flash(f"Export failed: {e}", "danger")
        return redirect(url_for("hod.carryovers"))

    filename = f"{department.code}_Carryover_Report_{datetime.now().strftime('%Y%m%d')}.xlsx"
    return send_file(
        io.BytesIO(excel_bytes),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=filename,
    )


@hod_bp.route("/export/transcript/<int:student_id>")
@hod_required
def export_transcript(student_id: int):
    """Download a student's full academic transcript as Excel."""
    department = get_hod_department()
    student = Student.query.get_or_404(student_id)

    if student.department_id != department.id:
        flash("Unauthorized.", "danger")
        return redirect(url_for("hod.reports"))

    try:
        excel_bytes = export_student_transcript(student_id)
    except Exception as e:
        flash(f"Export failed: {e}", "danger")
        return redirect(url_for("hod.reports"))

    filename = f"Transcript_{student.matric_number.replace('/', '-')}.xlsx"
    return send_file(
        io.BytesIO(excel_bytes),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=filename,
    )