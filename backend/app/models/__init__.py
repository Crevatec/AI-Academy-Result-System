"""
backend/app/models/__init__.py
-------------------------------
Import all models here so Flask-Migrate can detect them
when running `flask db migrate`.

If a model is not imported here, Alembic won't see it
and won't generate a migration for it.
"""

from app.models.user import User, Student, Lecturer
from app.models.course import Department, Course, lecturer_courses
from app.models.result import AcademicSession, Result, GPARecord, CGPARecord

__all__ = [
    "User", "Student", "Lecturer",
    "Department", "Course", "lecturer_courses",
    "AcademicSession", "Result", "GPARecord", "CGPARecord",
]
