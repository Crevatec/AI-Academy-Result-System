"""
backend/app/services/gpa_engine.py
------------------------------------
GPA and CGPA computation engine.

Called automatically when HOD approves results for a semester.

Formula:
    GPA  = Σ(grade_point × course_unit) / Σ(course_units)    [per semester]
    CGPA = Σ(all grade_points × course_units) / Σ(all units)  [cumulative]

Note: CGPA is NOT the average of GPAs.
It is recalculated from raw results every time, ensuring accuracy.
"""

from app import db
from app.models.result import Result, GPARecord, CGPARecord
from app.models.user import Student
from app.services.grading import classify_gpa


def compute_gpa_for_session(student_id: int, session_id: int) -> GPARecord:
    """
    Compute and store GPA for a specific student in a specific semester.

    Only APPROVED results are included in GPA computation.
    Rejected or pending results are excluded.

    Args:
        student_id: Primary key of Student
        session_id: Primary key of AcademicSession

    Returns:
        Updated or created GPARecord
    """
    # Fetch only approved results for this student + session
    results = (
        Result.query
        .filter_by(student_id=student_id, session_id=session_id, status="approved")
        .all()
    )

    if not results:
        return None

    # Fetch student grading scale
    student = Student.query.get(student_id)
    scale = student.grading_scale

    # GPA calculation
    total_points = sum(r.grade_point * r.course.unit for r in results)
    total_units = sum(r.course.unit for r in results)

    if total_units == 0:
        return None

    gpa = round(total_points / total_units, 2)
    classification = classify_gpa(gpa, scale)

    # Upsert: Update existing record or create new one
    gpa_record = GPARecord.query.filter_by(
        student_id=student_id,
        session_id=session_id
    ).first()

    if gpa_record:
        gpa_record.gpa = gpa
        gpa_record.total_units = total_units
        gpa_record.total_points = total_points
        gpa_record.classification = classification
    else:
        gpa_record = GPARecord(
            student_id=student_id,
            session_id=session_id,
            gpa=gpa,
            total_units=total_units,
            total_points=total_points,
            classification=classification,
        )
        db.session.add(gpa_record)

    db.session.commit()
    return gpa_record


def compute_cgpa(student_id: int) -> CGPARecord:
    """
    Compute and store the cumulative GPA (CGPA) for a student
    across ALL approved semesters in their academic history.

    This recalculates from scratch every time to ensure accuracy,
    especially important when results are corrected.

    Args:
        student_id: Primary key of Student

    Returns:
        Updated or created CGPARecord
    """
    # All approved results for this student, across all sessions
    all_results = (
        Result.query
        .filter_by(student_id=student_id, status="approved")
        .all()
    )

    if not all_results:
        return None

    student = Student.query.get(student_id)
    scale = student.grading_scale

    # Accumulate across all time
    total_points = sum(r.grade_point * r.course.unit for r in all_results)
    total_units = sum(r.course.unit for r in all_results)

    if total_units == 0:
        return None

    cgpa = round(total_points / total_units, 2)
    classification = classify_gpa(cgpa, scale)

    # Count unique sessions with results
    unique_sessions = len(set(r.session_id for r in all_results))

    # Upsert
    cgpa_record = CGPARecord.query.filter_by(student_id=student_id).first()

    if cgpa_record:
        cgpa_record.cgpa = cgpa
        cgpa_record.total_units_cumulative = total_units
        cgpa_record.total_points_cumulative = total_points
        cgpa_record.classification = classification
        cgpa_record.semesters_completed = unique_sessions
    else:
        cgpa_record = CGPARecord(
            student_id=student_id,
            cgpa=cgpa,
            total_units_cumulative=total_units,
            total_points_cumulative=total_points,
            classification=classification,
            semesters_completed=unique_sessions,
        )
        db.session.add(cgpa_record)

    db.session.commit()
    return cgpa_record


def recompute_all_for_student(student_id: int, session_id: int) -> dict:
    """
    Convenience: compute both GPA (semester) and CGPA (cumulative).
    Called after HOD approval.

    Returns:
        dict with 'gpa' and 'cgpa' float values
    """
    gpa_record = compute_gpa_for_session(student_id, session_id)
    cgpa_record = compute_cgpa(student_id)

    return {
        "gpa": gpa_record.gpa if gpa_record else None,
        "cgpa": cgpa_record.cgpa if cgpa_record else None,
        "gpa_classification": gpa_record.classification if gpa_record else None,
        "cgpa_classification": cgpa_record.classification if cgpa_record else None,
    }
