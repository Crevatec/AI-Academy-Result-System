"""
backend/app/services/export_service.py
----------------------------------------
Generates Excel (.xlsx) exports of student results.

Used by HOD to export department result reports for submission
to school administration.

Exports:
1. Department full result sheet  — all students, all courses, GPA/CGPA
2. Individual student transcript  — one student's full academic history
3. Carryover report              — all students with pending carryovers

Why openpyxl instead of pandas for export?
- Full control over cell styling (colors, bold headers, borders)
- No extra pandas dependency just for writing
- Lighter for the server
"""

import io
from datetime import datetime

import openpyxl
from openpyxl.styles import (
    Font, PatternFill, Alignment, Border, Side, numbers
)

from app.models.user import Student
from app.models.result import Result, GPARecord, CGPARecord, CarryoverRecord, AcademicSession
from app.models.course import Department


# ── Style constants ────────────────────────────────────────────────────────────

HEADER_FILL = PatternFill("solid", fgColor="1A3C6B")
HEADER_FONT = Font(bold=True, color="FFFFFF", size=11)
SUBHEADER_FILL = PatternFill("solid", fgColor="D6E4F0")
SUBHEADER_FONT = Font(bold=True, color="1A3C6B", size=10)
BORDER = Border(
    left=Side(style="thin"),
    right=Side(style="thin"),
    top=Side(style="thin"),
    bottom=Side(style="thin"),
)
GRADE_COLORS = {
    "A": "C8E6C9",  # green
    "B": "DCEDC8",
    "C": "FFF9C4",  # yellow
    "D": "FFE0B2",
    "E": "FFCCBC",
    "F": "FFCDD2",  # red
}
CENTER = Alignment(horizontal="center", vertical="center")
LEFT = Alignment(horizontal="left", vertical="center")


def _apply_header(ws, row: int, col: int, value: str, width: int = 15):
    cell = ws.cell(row=row, column=col, value=value)
    cell.font = HEADER_FONT
    cell.fill = HEADER_FILL
    cell.border = BORDER
    cell.alignment = CENTER
    ws.column_dimensions[cell.column_letter].width = width
    return cell


def _apply_subheader(ws, row: int, col: int, value: str):
    cell = ws.cell(row=row, column=col, value=value)
    cell.font = SUBHEADER_FONT
    cell.fill = SUBHEADER_FILL
    cell.border = BORDER
    cell.alignment = CENTER
    return cell


def export_department_results(department_id: int, session_id: int) -> bytes:
    """
    Export full department result sheet for a given academic session.

    Sheet layout:
        Row 1:    Institution + export info title
        Row 2:    Department name + session
        Row 3-4:  Column headers
        Row 5+:   One row per student per course

    A second sheet summarises GPA/CGPA per student.

    Args:
        department_id: Department PK
        session_id:    AcademicSession PK

    Returns:
        bytes — Excel file content (write to response or disk)
    """
    dept = Department.query.get(department_id)
    session = AcademicSession.query.get(session_id)

    if not dept or not session:
        raise ValueError("Invalid department or session ID.")

    wb = openpyxl.Workbook()

    # ── Sheet 1: Detailed Results ──────────────────────────────────────────────
    ws1 = wb.active
    ws1.title = "Detailed Results"
    ws1.sheet_view.showGridLines = False

    # Title banner
    ws1.merge_cells("A1:L1")
    title_cell = ws1["A1"]
    title_cell.value = f"DEPARTMENT OF {dept.name.upper()} — RESULT SHEET"
    title_cell.font = Font(bold=True, size=14, color="1A3C6B")
    title_cell.alignment = CENTER
    ws1.row_dimensions[1].height = 30

    ws1.merge_cells("A2:L2")
    sub_cell = ws1["A2"]
    sub_cell.value = (
        f"Academic Session: {session.session_name}  |  "
        f"Semester: {session.semester}  |  "
        f"Grading Scale: {dept.grading_scale}  |  "
        f"Exported: {datetime.now().strftime('%d %B %Y %H:%M')}"
    )
    sub_cell.font = Font(italic=True, size=10, color="555555")
    sub_cell.alignment = CENTER
    ws1.row_dimensions[2].height = 20

    # Column headers (row 3)
    headers = [
        ("S/N", 5), ("Matric No", 16), ("Student Name", 24),
        ("Level", 8), ("Course Code", 14), ("Course Title", 30),
        ("Units", 7), ("CA", 7), ("Practical", 10), ("Exam", 7),
        ("Total", 8), ("Grade", 8), ("GP", 7),
    ]
    for col_idx, (header, width) in enumerate(headers, start=1):
        _apply_header(ws1, 3, col_idx, header, width)

    # Data rows
    students = Student.query.filter_by(department_id=department_id).all()
    row_num = 4
    sn = 1

    for student in sorted(students, key=lambda s: s.matric_number):
        results = Result.query.filter_by(
            student_id=student.id,
            session_id=session_id,
            status="approved"
        ).all()

        if not results:
            continue

        for result in results:
            detail = result.detail
            row_fill = PatternFill("solid", fgColor=GRADE_COLORS.get(result.grade, "FFFFFF"))

            def _cell(col, value, align=CENTER):
                c = ws1.cell(row=row_num, column=col, value=value)
                c.border = BORDER
                c.alignment = align
                c.fill = row_fill
                return c

            _cell(1, sn)
            _cell(2, student.matric_number)
            _cell(3, student.user.full_name, LEFT)
            _cell(4, student.level)
            _cell(5, result.course.code)
            _cell(6, result.course.title, LEFT)
            _cell(7, result.course.unit)
            _cell(8, detail.ca_score if detail else "—")
            _cell(9, detail.practical_score if detail else "—")
            _cell(10, detail.exam_score if detail else "—")
            _cell(11, round(result.score, 1))

            grade_cell = ws1.cell(row=row_num, column=12, value=result.grade)
            grade_cell.font = Font(bold=True)
            grade_cell.border = BORDER
            grade_cell.alignment = CENTER
            grade_cell.fill = row_fill

            _cell(13, result.grade_point)
            row_num += 1

        sn += 1

    # Freeze pane at row 4
    ws1.freeze_panes = "A4"

    # ── Sheet 2: GPA/CGPA Summary ──────────────────────────────────────────────
    ws2 = wb.create_sheet(title="GPA Summary")
    ws2.sheet_view.showGridLines = False

    ws2.merge_cells("A1:H1")
    t2 = ws2["A1"]
    t2.value = f"GPA/CGPA SUMMARY — {dept.name.upper()} — {session.session_name} SEM {session.semester}"
    t2.font = Font(bold=True, size=13, color="1A3C6B")
    t2.alignment = CENTER
    ws2.row_dimensions[1].height = 28

    sum_headers = [
        ("S/N", 5), ("Matric No", 16), ("Student Name", 24), ("Level", 8),
        ("Semester GPA", 15), ("Cumulative CGPA", 17),
        ("Classification", 22), ("Status", 14),
    ]
    for col_idx, (header, width) in enumerate(sum_headers, start=1):
        _apply_header(ws2, 2, col_idx, header, width)

    sn2 = 1
    for student in sorted(students, key=lambda s: s.matric_number):
        gpa_record = GPARecord.query.filter_by(
            student_id=student.id,
            session_id=session_id
        ).first()
        cgpa_record = CGPARecord.query.filter_by(student_id=student.id).first()

        if not gpa_record:
            continue

        # Color row by classification
        cls = cgpa_record.classification if cgpa_record else ""
        row_color = (
            "C8E6C9" if "First" in cls or "Distinction" in cls
            else "DCEDC8" if "Upper" in cls
            else "FFF9C4" if "Lower" in cls or "Second Lower" in cls
            else "FFE0B2" if "Third" in cls or "Pass" in cls
            else "FFCDD2" if "Fail" in cls or "Probation" in cls
            else "FFFFFF"
        )
        rfill = PatternFill("solid", fgColor=row_color)

        row = sn2 + 2
        data = [
            sn2,
            student.matric_number,
            student.user.full_name,
            student.level,
            round(gpa_record.gpa, 2) if gpa_record else "—",
            round(cgpa_record.cgpa, 2) if cgpa_record else "—",
            cgpa_record.classification if cgpa_record else "No Results",
            "Approved",
        ]
        for col_idx, val in enumerate(data, start=1):
            c = ws2.cell(row=row, column=col_idx, value=val)
            c.border = BORDER
            c.fill = rfill
            c.alignment = CENTER if col_idx != 3 else LEFT

        sn2 += 1

    ws2.freeze_panes = "A3"

    # ── Output to bytes ────────────────────────────────────────────────────────
    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer.getvalue()


def export_student_transcript(student_id: int) -> bytes:
    """
    Generate a full academic transcript for one student across ALL sessions.

    Layout:
        Student bio data header
        One section per session (table of courses + GPA)
        Final CGPA + Classification row
        Carryover section (if any)

    Args:
        student_id: Student PK

    Returns:
        bytes — Excel file content
    """
    student = Student.query.get(student_id)
    if not student:
        raise ValueError("Student not found.")

    cgpa_record = CGPARecord.query.filter_by(student_id=student_id).first()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Academic Transcript"
    ws.sheet_view.showGridLines = False
    ws.column_dimensions["A"].width = 5
    ws.column_dimensions["B"].width = 16
    ws.column_dimensions["C"].width = 30
    ws.column_dimensions["D"].width = 8
    ws.column_dimensions["E"].width = 8
    ws.column_dimensions["F"].width = 8
    ws.column_dimensions["G"].width = 10
    ws.column_dimensions["H"].width = 8
    ws.column_dimensions["I"].width = 8
    ws.column_dimensions["J"].width = 8

    # ── Student Header ────────────────────────────────────────────────────────
    ws.merge_cells("A1:J1")
    ws["A1"].value = "OFFICIAL ACADEMIC TRANSCRIPT"
    ws["A1"].font = Font(bold=True, size=14, color="FFFFFF")
    ws["A1"].fill = PatternFill("solid", fgColor="1A3C6B")
    ws["A1"].alignment = CENTER
    ws.row_dimensions[1].height = 30

    bio_data = [
        ("Name:", student.user.full_name),
        ("Matric No:", student.matric_number),
        ("Department:", student.department.name),
        ("Level:", f"{student.level}00"),
        ("Grading Scale:", student.grading_scale),
        ("Date Printed:", datetime.now().strftime("%d %B %Y")),
    ]
    for i, (label, value) in enumerate(bio_data, start=2):
        ws.cell(row=i, column=1, value=label).font = Font(bold=True)
        ws.merge_cells(f"B{i}:D{i}")
        ws.cell(row=i, column=2, value=value)

    current_row = 2 + len(bio_data) + 1

    # ── Results by Session ────────────────────────────────────────────────────
    sessions = (
        AcademicSession.query
        .join(Result, Result.session_id == AcademicSession.id)
        .filter(Result.student_id == student_id, Result.status == "approved")
        .distinct()
        .order_by(AcademicSession.session_name, AcademicSession.semester)
        .all()
    )

    for session in sessions:
        # Session sub-header
        ws.merge_cells(f"A{current_row}:J{current_row}")
        sh = ws.cell(row=current_row, column=1,
                     value=f"Session: {session.session_name}  —  Semester {session.semester}")
        sh.font = Font(bold=True, color="1A3C6B", size=11)
        sh.fill = PatternFill("solid", fgColor="D6E4F0")
        sh.alignment = LEFT
        ws.row_dimensions[current_row].height = 22
        current_row += 1

        # Column headers
        col_headers = ["#", "Course Code", "Course Title",
                       "Units", "CA", "Practical", "Exam", "Total", "Grade", "GP"]
        for ci, ch in enumerate(col_headers, start=1):
            _apply_subheader(ws, current_row, ci, ch)
        current_row += 1

        # Course rows
        results = Result.query.filter_by(
            student_id=student_id,
            session_id=session.id,
            status="approved"
        ).all()

        for idx, result in enumerate(results, start=1):
            detail = result.detail
            rfill = PatternFill("solid", fgColor=GRADE_COLORS.get(result.grade, "FFFFFF"))
            row_vals = [
                idx,
                result.course.code,
                result.course.title,
                result.course.unit,
                detail.ca_score if detail else "—",
                detail.practical_score if detail else "—",
                detail.exam_score if detail else "—",
                round(result.score, 1),
                result.grade,
                result.grade_point,
            ]
            for ci, val in enumerate(row_vals, start=1):
                c = ws.cell(row=current_row, column=ci, value=val)
                c.border = BORDER
                c.fill = rfill
                c.alignment = CENTER if ci != 3 else LEFT
            current_row += 1

        # GPA row for this session
        gpa_rec = GPARecord.query.filter_by(
            student_id=student_id, session_id=session.id
        ).first()
        if gpa_rec:
            ws.merge_cells(f"A{current_row}:G{current_row}")
            gpa_label = ws.cell(row=current_row, column=1,
                                value=f"Semester GPA: {gpa_rec.gpa:.2f}   |   Total Units: {gpa_rec.total_units}")
            gpa_label.font = Font(bold=True, color="1A3C6B")
            gpa_label.alignment = LEFT

        current_row += 2  # gap between sessions

    # ── Final CGPA summary ───────────────────────────────────────────────────
    ws.merge_cells(f"A{current_row}:J{current_row}")
    final_cell = ws.cell(row=current_row, column=1)
    if cgpa_record:
        final_cell.value = (
            f"CUMULATIVE GPA (CGPA): {cgpa_record.cgpa:.2f} / {student.grading_scale}   "
            f"|   CLASSIFICATION: {cgpa_record.classification}   "
            f"|   TOTAL UNITS: {cgpa_record.total_units_cumulative}"
        )
    else:
        final_cell.value = "CGPA: Not yet computed"
    final_cell.font = Font(bold=True, size=12, color="FFFFFF")
    final_cell.fill = PatternFill("solid", fgColor="1A3C6B")
    final_cell.alignment = CENTER
    ws.row_dimensions[current_row].height = 26
    current_row += 2

    # ── Carryover section ────────────────────────────────────────────────────
    pending_carryovers = CarryoverRecord.query.filter_by(
        student_id=student_id, status="pending"
    ).all()

    if pending_carryovers:
        ws.merge_cells(f"A{current_row}:J{current_row}")
        co_header = ws.cell(row=current_row, column=1,
                            value="OUTSTANDING CARRYOVER COURSES")
        co_header.font = Font(bold=True, color="FFFFFF")
        co_header.fill = PatternFill("solid", fgColor="C0392B")
        co_header.alignment = CENTER
        current_row += 1

        for co in pending_carryovers:
            row_vals = [
                co.course.code,
                co.course.title,
                f"Failed ({co.failed_score:.0f}%)",
                f"Retake Level {co.recommended_retake_level} Sem {co.recommended_retake_semester}",
                f"Session: {co.recommended_retake_session}",
            ]
            for ci, val in enumerate(row_vals, start=1):
                c = ws.cell(row=current_row, column=ci, value=val)
                c.border = BORDER
                c.fill = PatternFill("solid", fgColor="FFCDD2")
                c.alignment = LEFT
            current_row += 1

    # Output
    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer.getvalue()


def export_carryover_report(department_id: int) -> bytes:
    """
    Export a department-wide carryover report for HOD.
    Lists all students with pending carryover courses.
    """
    dept = Department.query.get(department_id)
    students = Student.query.filter_by(department_id=department_id).all()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Carryover Report"
    ws.sheet_view.showGridLines = False

    ws.merge_cells("A1:H1")
    ws["A1"].value = f"CARRYOVER REPORT — {dept.name.upper()} — {datetime.now().strftime('%d %B %Y')}"
    ws["A1"].font = Font(bold=True, size=13, color="FFFFFF")
    ws["A1"].fill = PatternFill("solid", fgColor="C0392B")
    ws["A1"].alignment = CENTER
    ws.row_dimensions[1].height = 28

    headers = [
        ("S/N", 5), ("Matric No", 16), ("Student Name", 24), ("Level", 8),
        ("Course Code", 14), ("Course Title", 28),
        ("Score Failed", 12), ("Recommended Retake", 22),
    ]
    for ci, (h, w) in enumerate(headers, start=1):
        _apply_header(ws, 2, ci, h, w)

    sn = 1
    row_num = 3
    for student in students:
        carryovers = CarryoverRecord.query.filter_by(
            student_id=student.id, status="pending"
        ).all()
        for co in carryovers:
            rfill = PatternFill("solid", fgColor="FFEBEE")
            data = [
                sn,
                student.matric_number,
                student.user.full_name,
                student.level,
                co.course.code,
                co.course.title,
                f"{co.failed_score:.0f}%",
                (f"Level {co.recommended_retake_level} Sem {co.recommended_retake_semester} "
                 f"({co.recommended_retake_session})")
            ]
            for ci, val in enumerate(data, start=1):
                c = ws.cell(row=row_num, column=ci, value=val)
                c.border = BORDER
                c.fill = rfill
                c.alignment = CENTER if ci not in (3, 6, 8) else LEFT
            row_num += 1
            sn += 1

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer.getvalue()
