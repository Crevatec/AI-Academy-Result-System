"""
backend/app/routes/auth.py
---------------------------
Authentication routes: login, logout.

After successful login, each role is redirected to their own dashboard.
Password comparison uses bcrypt's check_password_hash — never plain text.

CSRF protection is active on all POST forms via Flask-WTF.
"""

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app.models.user import User

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/")
@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """
    GET:  Show login form
    POST: Validate credentials, start session, redirect by role
    """
    # Already logged in → redirect to their dashboard
    if current_user.is_authenticated:
        return redirect(url_for(f"{current_user.role}.dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        remember = request.form.get("remember") == "on"

        # Look up user by email
        user = User.query.filter_by(email=email).first()

        if user and user.is_active and user.check_password(password):
            login_user(user, remember=remember)
            flash(f"Welcome back, {user.first_name}!", "success")

            # Redirect to the page they were trying to access (if any)
            next_page = request.args.get("next")
            if next_page:
                return redirect(next_page)

            # Otherwise go to role-appropriate dashboard
            role_dashboards = {
                "student": "student.dashboard",
                "lecturer": "lecturer.dashboard",
                "hod": "hod.dashboard",
                "admin": "admin.dashboard",
            }
            destination = role_dashboards.get(user.role, "auth.login")
            return redirect(url_for(destination))

        else:
            flash("Invalid email or password. Please try again.", "danger")

    return render_template("auth/login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    """End the user's session and redirect to login."""
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))
