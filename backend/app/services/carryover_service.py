"""
backend/app/services/carryover_service.py
------------------------------------------
Automatically identifies, records, and schedules carryover courses.

Called after HOD approval. Any result with grade='F' triggers this.

Scheduling rule (standard Nigerian polytechnic/university convention):
    Failed Level 100 Sem 1  → Retake Level 200 Sem 1
    Failed Level 100 Sem 2  → Retake Level 200 Sem 2
    Failed Level 200 Sem 1  → Retake Level 300 Sem 1
    Failed Level 200 Sem 2  → Retake Level 300 Sem 2
    ...up to Level 400/500

For session scheduling, we project the next academic year:
    e.g., Failed in 2024/2025 → Recommended retake 2025/2026

A carryover is automatically cleared when the student passes
the same course in a later semester (grade != 'F').
"""

from app import db
from app.models.result import Result, CarryoverRecord, AcademicSession
from app.models.user import Student


def _next_level(current_level: int) -> int:
    """
    Return the level one step above.
    Caps at 500 for 5-year programmes, 400 for 4-year.
    """
    next_l = current_level + 100
    return min(next_l, 500)


def _next_session_name(session_name: str) -> str:
    """
    Compute the next academic year string.
    '2024/2025' → '2025/2026'
    """
    try:
        parts = session_name.split("/")
        start = int(parts[0]) + 1
        end = int(parts[1]) + 1
        return f"{start}/{end}"
    except Exception:
        return session_name  # fallback: return same session


def process_carryovers_for_session(student_id: int, session_id: int) -> list:
    """
    After HOD approves results for a session, scan for any F grades
    and create or update CarryoverRecord entries.

    Also clears any existing carryovers if the student passed the
    course this time around.

    Args:
        student_id: Primary key of Student
        session_id: Primary key of AcademicSession

    Returns:
        List of CarryoverRecord objects created or updated.
    """
    student = Student.query.get(student_id)
    session = AcademicSession.query.get(session_id)

    if not student or not session:
        return []

    approved_results = Result.query.filter_by(
        student_id=student_id,
        session_id=session_id,
        status="approved"
    ).all()

    processed = []
    next_session_str = _next_session_name(session.session_name)

    for result in approved_results:
        course = result.course

        if result.grade == "F":
            # ── Create carryover record ───────────────────────────────────
            # Check if one already exists (e.g., student failed again)
            existing = CarryoverRecord.query.filter_by(
                student_id=student_id,
                course_id=course.id,
                failed_session_id=session_id,
            ).first()

            if not existing:
                retake_level = _next_level(course.level)

                carryover = CarryoverRecord(
                    student_id=student_id,
                    course_id=course.id,
                    failed_session_id=session_id,
                    failed_score=result.score,
                    recommended_retake_level=retake_level,
                    recommended_retake_semester=course.semester,
                    recommended_retake_session=next_session_str,
                    status="pending",
                )
                db.session.add(carryover)
                processed.append(carryover)

        else:
            # ── Clear carryover if student has now passed ─────────────────
            # Find any pending carryover for this course from a previous session
            pending_carryover = CarryoverRecord.query.filter_by(
                student_id=student_id,
                course_id=course.id,
                status="pending",
            ).first()

            if pending_carryover:
                pending_carryover.status = "cleared"
                pending_carryover.cleared_session_id = session_id
                pending_carryover.cleared_score = result.score
                processed.append(pending_carryover)

    db.session.commit()
    return processed


def get_student_carryovers(student_id: int) -> dict:
    """
    Return a structured summary of a student's carryover situation.

    Returns:
        {
            "pending": [...CarryoverRecord...],
            "cleared": [...CarryoverRecord...],
            "total_pending": int,
        }
    """
    all_carryovers = CarryoverRecord.query.filter_by(student_id=student_id).all()

    pending = [c for c in all_carryovers if c.status == "pending"]
    cleared = [c for c in all_carryovers if c.status == "cleared"]

    return {
        "pending": pending,
        "cleared": cleared,
        "total_pending": len(pending),
    }


def get_department_carryover_summary(department_id: int) -> list:
    """
    For HOD: all students in a department with pending carryovers.

    Returns list of dicts with student info and pending carryover count.
    """
    from app.models.user import Student

    students = Student.query.filter_by(department_id=department_id).all()
    summary = []

    for student in students:
        pending = CarryoverRecord.query.filter_by(
            student_id=student.id,
            status="pending"
        ).count()

        if pending > 0:
            summary.append({
                "student": student,
                "pending_count": pending,
                "carryovers": CarryoverRecord.query.filter_by(
                    student_id=student.id, status="pending"
                ).all(),
            })

    # Sort by most carryovers first
    summary.sort(key=lambda x: x["pending_count"], reverse=True)
    return summary
