"""
backend/app/models/user.py
--------------------------
Database models for all system users.

Why one User table with a role field instead of four separate tables?
- Simplifies authentication (one login endpoint)
- Easier to add roles later
- Role-based access is handled by decorators, not separate tables

Password is NEVER stored in plain text.
bcrypt stores a hash that is computationally expensive to reverse.
"""

from flask_login import UserMixin
from app import db, bcrypt, login_manager


class User(UserMixin, db.Model):
    """
    Central user table for all roles.
    Flask-Login requires UserMixin for session management.
    """
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)

    # Role controls what pages/actions the user can access
    # Values: 'student', 'lecturer', 'hod', 'admin'
    role = db.Column(db.String(20), nullable=False)

    first_name = db.Column(db.String(80), nullable=False)
    last_name = db.Column(db.String(80), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    # ── Relationships ────────────────────────────────────────────────────────
    # One User can be linked to one Student profile (if role = 'student')
    student_profile = db.relationship("Student", back_populates="user", uselist=False)
    lecturer_profile = db.relationship("Lecturer", back_populates="user", uselist=False)

    def set_password(self, plain_password: str) -> None:
        """Hash and store a password. Never call with already-hashed text."""
        self.password_hash = bcrypt.generate_password_hash(plain_password).decode("utf-8")

    def check_password(self, plain_password: str) -> bool:
        """Return True if plain_password matches the stored hash."""
        return bcrypt.check_password_hash(self.password_hash, plain_password)

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    def __repr__(self):
        return f"<User {self.email} [{self.role}]>"


@login_manager.user_loader
def load_user(user_id: str) -> User | None:
    """
    Flask-Login callback: Given a user ID (stored in session cookie),
    return the User object. Called on every request automatically.
    """
    return User.query.get(int(user_id))


class Student(db.Model):
    """
    Student-specific profile.
    Linked 1-to-1 with User (role='student').
    Stores academic metadata like matric number, level, department.
    """
    __tablename__ = "students"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True, nullable=False)

    matric_number = db.Column(db.String(20), unique=True, nullable=False, index=True)
    level = db.Column(db.Integer, nullable=False)  # 100, 200, 300, 400, 500

    # Which grading scale applies: '4.0' or '5.0'
    grading_scale = db.Column(db.String(5), nullable=False, default="5.0")

    # FK to Department
    department_id = db.Column(db.Integer, db.ForeignKey("departments.id"), nullable=False)

    # ── Relationships ────────────────────────────────────────────────────────
    user = db.relationship("User", back_populates="student_profile")
    department = db.relationship("Department", back_populates="students")
    results = db.relationship("Result", back_populates="student", lazy="dynamic")
    gpa_records = db.relationship("GPARecord", back_populates="student", lazy="dynamic")

    def __repr__(self):
        return f"<Student {self.matric_number}>"


class Lecturer(db.Model):
    """
    Lecturer-specific profile.
    A lecturer belongs to a department and teaches assigned courses.
    """
    __tablename__ = "lecturers"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True, nullable=False)
    staff_id = db.Column(db.String(20), unique=True, nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey("departments.id"), nullable=False)

    # ── Relationships ────────────────────────────────────────────────────────
    user = db.relationship("User", back_populates="lecturer_profile")
    department = db.relationship("Department", back_populates="lecturers")

    # Courses this lecturer teaches (many-to-many via assignment table)
    courses = db.relationship(
        "Course",
        secondary="lecturer_courses",
        back_populates="lecturers"
    )

    def __repr__(self):
        return f"<Lecturer {self.staff_id}>"
