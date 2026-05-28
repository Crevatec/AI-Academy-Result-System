"""
backend/app/routes/admin.py
-----------------------------
Admin routes:
- Manage users (create, activate/deactivate)
- Manage courses and departments
- Configure academic sessions
- Set grading scale per department
"""

from flask import Blueprint, render_template, redirect, url_for, flash, request
from app import db, bcrypt
from app.models.user import User, Student, Lecturer
from app.models.course import Department, Course
from app.models.result import AcademicSession
from app.utils.decorators import admin_required

admin_bp = Blueprint("admin", __name__)


@admin_bp.route("/dashboard")
@admin_required
def dashboard():
    """Admin home: system statistics."""
    stats = {
        "total_students": Student.query.count(),
        "total_lecturers": Lecturer.query.count(),
        "total_departments": Department.query.count(),
        "total_courses": Course.query.count(),
    }
    current_session = AcademicSession.query.filter_by(is_current=True).first()
    departments = Department.query.all()
    recent_users = User.query.order_by(User.created_at.desc()).limit(10).all()

    return render_template(
        "admin/dashboard.html",
        stats=stats,
        current_session=current_session,
        departments=departments,
        recent_users=recent_users,
    )


# ── User Management ───────────────────────────────────────────────────────────

@admin_bp.route("/users")
@admin_required
def list_users():
    """List all system users with filtering."""
    role_filter = request.args.get("role", "")
    query = User.query
    if role_filter:
        query = query.filter_by(role=role_filter)
    users = query.order_by(User.created_at.desc()).all()
    return render_template("admin/users.html", users=users, role_filter=role_filter)


@admin_bp.route("/users/create", methods=["GET", "POST"])
@admin_required
def create_user():
    """Create a new user for any role."""
    departments = Department.query.all()

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        role = request.form.get("role", "")
        first_name = request.form.get("first_name", "").strip()
        last_name = request.form.get("last_name", "").strip()
        department_id = request.form.get("department_id", type=int)

        # Basic validation
        if User.query.filter_by(email=email).first():
            flash("Email already in use.", "danger")
            return redirect(url_for("admin.create_user"))

        if role not in ("student", "lecturer", "hod", "admin"):
            flash("Invalid role selected.", "danger")
            return redirect(url_for("admin.create_user"))

        # Create User
        user = User(
            email=email,
            role=role,
            first_name=first_name,
            last_name=last_name,
        )
        user.set_password(password)
        db.session.add(user)
        db.session.flush()  # Get user.id before creating profile

        # Create role-specific profile
        if role == "student":
            matric = request.form.get("matric_number", "").strip().upper()
            level = request.form.get("level", type=int)
            grading_scale = request.form.get("grading_scale", "5.0")

            student = Student(
                user_id=user.id,
                matric_number=matric,
                level=level,
                grading_scale=grading_scale,
                department_id=department_id,
            )
            db.session.add(student)

        elif role == "lecturer":
            staff_id = request.form.get("staff_id", "").strip().upper()
            lecturer = Lecturer(
                user_id=user.id,
                staff_id=staff_id,
                department_id=department_id,
            )
            db.session.add(lecturer)

        elif role == "hod":
            # Assign this user as HOD of the selected department
            dept = Department.query.get(department_id)
            if dept:
                dept.hod_user_id = user.id

        db.session.commit()
        flash(f"User {email} created successfully as {role}.", "success")
        return redirect(url_for("admin.list_users"))

    return render_template("admin/create_user.html", departments=departments)


@admin_bp.route("/users/<int:user_id>/toggle-active", methods=["POST"])
@admin_required
def toggle_user_active(user_id: int):
    """Activate or deactivate a user account."""
    user = User.query.get_or_404(user_id)
    user.is_active = not user.is_active
    db.session.commit()
    status = "activated" if user.is_active else "deactivated"
    flash(f"User {user.email} has been {status}.", "info")
    return redirect(url_for("admin.list_users"))


# ── Academic Session Management ───────────────────────────────────────────────

@admin_bp.route("/sessions")
@admin_required
def list_sessions():
    sessions = AcademicSession.query.order_by(
        AcademicSession.session_name.desc(),
        AcademicSession.semester
    ).all()
    return render_template("admin/sessions.html", sessions=sessions)


@admin_bp.route("/sessions/create", methods=["POST"])
@admin_required
def create_session():
    session_name = request.form.get("session_name", "").strip()  # e.g., "2024/2025"
    semester = request.form.get("semester", type=int)

    if not session_name or semester not in (1, 2):
        flash("Invalid session data.", "danger")
        return redirect(url_for("admin.list_sessions"))

    existing = AcademicSession.query.filter_by(
        session_name=session_name,
        semester=semester
    ).first()

    if existing:
        flash("This session already exists.", "warning")
        return redirect(url_for("admin.list_sessions"))

    session = AcademicSession(session_name=session_name, semester=semester)
    db.session.add(session)
    db.session.commit()
    flash(f"Session {session_name} Semester {semester} created.", "success")
    return redirect(url_for("admin.list_sessions"))


@admin_bp.route("/sessions/<int:session_id>/set-current", methods=["POST"])
@admin_required
def set_current_session(session_id: int):
    """Mark a session as current. Only one can be current at a time."""
    # Deactivate all
    AcademicSession.query.update({"is_current": False})
    # Activate chosen one
    session = AcademicSession.query.get_or_404(session_id)
    session.is_current = True
    db.session.commit()
    flash(f"Active session set to {session.session_name} Semester {session.semester}.", "success")
    return redirect(url_for("admin.list_sessions"))


@admin_bp.route("/sessions/<int:session_id>/release-results", methods=["POST"])
@admin_required
def release_results(session_id: int):
    """Make approved results visible to students."""
    session = AcademicSession.query.get_or_404(session_id)
    session.is_results_released = True
    db.session.commit()
    flash(f"Results released for {session.session_name} Semester {session.semester}.", "success")
    return redirect(url_for("admin.list_sessions"))


# ── Department Management ─────────────────────────────────────────────────────

@admin_bp.route("/departments")
@admin_required
def list_departments():
    departments = Department.query.all()
    return render_template("admin/departments.html", departments=departments)


@admin_bp.route("/departments/create", methods=["POST"])
@admin_required
def create_department():
    name = request.form.get("name", "").strip()
    code = request.form.get("code", "").strip().upper()
    scale = request.form.get("grading_scale", "5.0")

    if Department.query.filter_by(code=code).first():
        flash("Department code already exists.", "danger")
        return redirect(url_for("admin.list_departments"))

    dept = Department(name=name, code=code, grading_scale=scale)
    db.session.add(dept)
    db.session.commit()
    flash(f"Department {name} created.", "success")
    return redirect(url_for("admin.list_departments"))


# ── Course Management ─────────────────────────────────────────────────────────

@admin_bp.route("/courses")
@admin_required
def list_courses():
    courses = Course.query.join(Department).order_by(Department.name, Course.level).all()
    departments = Department.query.all()
    return render_template("admin/courses.html", courses=courses, departments=departments)


@admin_bp.route("/courses/create", methods=["POST"])
@admin_required
def create_course():
    code = request.form.get("code", "").strip().upper()
    title = request.form.get("title", "").strip()
    unit = request.form.get("unit", type=int)
    level = request.form.get("level", type=int)
    semester = request.form.get("semester", type=int)
    department_id = request.form.get("department_id", type=int)

    if Course.query.filter_by(code=code).first():
        flash("Course code already exists.", "danger")
        return redirect(url_for("admin.list_courses"))

    course = Course(
        code=code, title=title, unit=unit,
        level=level, semester=semester,
        department_id=department_id,
    )
    db.session.add(course)
    db.session.commit()
    flash(f"Course {code} created.", "success")
    return redirect(url_for("admin.list_courses"))
