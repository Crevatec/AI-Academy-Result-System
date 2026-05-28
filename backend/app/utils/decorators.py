"""
backend/app/utils/decorators.py
---------------------------------
Role-based access control decorators.

Usage in routes:
    @lecturer_required
    def my_route():
        ...

Why decorators instead of checking roles inline?
- DRY: Write the check once, apply everywhere
- Clean routes: business logic isn't cluttered with auth checks
- Easy to audit: grep for @hod_required to find all HOD-only endpoints

These decorators work WITH Flask-Login's @login_required.
Always apply @login_required first (or it's implicitly included below).
"""

from functools import wraps
from flask import abort, flash, redirect, url_for
from flask_login import current_user


def role_required(*roles):
    """
    Generic role-checking decorator factory.

    Args:
        *roles: One or more allowed role strings

    Example:
        @role_required('admin', 'hod')
        def admin_or_hod_only():
            ...
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for("auth.login"))
            if current_user.role not in roles:
                flash("You do not have permission to access this page.", "danger")
                abort(403)
            return f(*args, **kwargs)
        return decorated_function
    return decorator


# ── Convenience decorators for each role ──────────────────────────────────────

def student_required(f):
    """Allow only students."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for("auth.login"))
        if current_user.role != "student":
            abort(403)
        return f(*args, **kwargs)
    return decorated


def lecturer_required(f):
    """Allow only lecturers."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for("auth.login"))
        if current_user.role != "lecturer":
            abort(403)
        return f(*args, **kwargs)
    return decorated


def hod_required(f):
    """Allow only HODs."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for("auth.login"))
        if current_user.role != "hod":
            abort(403)
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    """Allow only admins."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for("auth.login"))
        if current_user.role != "admin":
            abort(403)
        return f(*args, **kwargs)
    return decorated


def hod_or_admin_required(f):
    """Allow HODs and admins (for shared management functions)."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for("auth.login"))
        if current_user.role not in ("hod", "admin"):
            abort(403)
        return f(*args, **kwargs)
    return decorated
