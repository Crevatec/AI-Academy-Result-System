"""
backend/app/models/course.py
-----------------------------
Course, Department, and their relationship tables.

Normalization:
- Department is its own table (not a string in Student)
  → Changing a department name updates everywhere
- Course is separate from Result
  → One course record, many result records referencing it
- lecturer_courses is a many-to-many association table
  → One lecturer can teach many courses, one course can have multiple lecturers
"""

from app import db


# ── Association table: Lecturer ↔ Course (many-to-many) ─────────────────────
# This is a simple join table with no extra columns.
# SQLAlchemy handles it automatically via the `secondary` argument.
lecturer_courses = db.Table(
    "lecturer_courses",
    db.Column("lecturer_id", db.Integer, db.ForeignKey("lecturers.id"), primary_key=True),
    db.Column("course_id", db.Integer, db.ForeignKey("courses.id"), primary_key=True),
)


class Department(db.Model):
    """
    Academic department (e.g., Computer Science, Accounting).
    Every student and lecturer belongs to exactly one department.
    HOD approval of results is scoped per department.
    """
    __tablename__ = "departments"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    code = db.Column(db.String(10), unique=True, nullable=False)  # e.g., "CS", "ACC"

    # Which grading scale this department uses: '4.0' or '5.0'
    grading_scale = db.Column(db.String(5), nullable=False, default="5.0")

    # HOD user ID (one user with role='hod' manages this department)
    hod_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    # ── Relationships ────────────────────────────────────────────────────────
    students = db.relationship("Student", back_populates="department")
    lecturers = db.relationship("Lecturer", back_populates="department")
    courses = db.relationship("Course", back_populates="department")

    def __repr__(self):
        return f"<Department {self.code}: {self.name}>"


class Course(db.Model):
    """
    A course offered by a department.
    course_unit (credit hours) is used in GPA = Σ(GP × unit) / Σ(units)

    Example:
        code = "CSC101"
        title = "Introduction to Programming"
        unit = 3
        level = 100
        semester = 1  (first semester)
    """
    __tablename__ = "courses"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(15), unique=True, nullable=False)
    title = db.Column(db.String(200), nullable=False)
    unit = db.Column(db.Integer, nullable=False)   # Credit units (1–6 typically)
    level = db.Column(db.Integer, nullable=False)  # 100, 200, 300, 400
    semester = db.Column(db.Integer, nullable=False)  # 1 (first) or 2 (second)
    is_active = db.Column(db.Boolean, default=True)

    department_id = db.Column(db.Integer, db.ForeignKey("departments.id"), nullable=False)

    # ── Relationships ────────────────────────────────────────────────────────
    department = db.relationship("Department", back_populates="courses")
    results = db.relationship("Result", back_populates="course", lazy="dynamic")

    # Which lecturers teach this course
    lecturers = db.relationship(
        "Lecturer",
        secondary="lecturer_courses",
        back_populates="courses"
    )

    def __repr__(self):
        return f"<Course {self.code}: {self.title} ({self.unit} units)>"
