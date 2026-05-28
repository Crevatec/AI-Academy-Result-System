"""
backend/app/__init__.py
-----------------------
Application Factory Pattern.

Why a factory function instead of a global `app = Flask(__name__)`?
- Allows creating multiple app instances (e.g., one for dev, one for testing)
- Prevents circular imports
- Makes testing much cleaner

All extensions are initialized here and passed the app instance.
All blueprints (routes) are registered here.
"""

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_bcrypt import Bcrypt
from flask_migrate import Migrate
from flask_mail import Mail
from flask_wtf.csrf import CSRFProtect

from config import config_map

# ─── Extension instances (not yet bound to any app) ───────────────────────────
db = SQLAlchemy()
login_manager = LoginManager()
bcrypt = Bcrypt()
migrate = Migrate()
mail = Mail()
csrf = CSRFProtect()


def create_app(config_name: str = "default") -> Flask:
    """
    Create and configure the Flask application.

    Args:
        config_name: One of 'development', 'testing', 'production', 'default'

    Returns:
        Configured Flask app instance
    """
    app = Flask(
        __name__,
        template_folder="../../frontend/templates",
        static_folder="../../frontend/static",
    )

    # ── Load configuration ─────────────────────────────────────────────────────
    app.config.from_object(config_map[config_name])

    # ── Initialize extensions with this app ────────────────────────────────────
    db.init_app(app)
    login_manager.init_app(app)
    bcrypt.init_app(app)
    migrate.init_app(app, db)
    mail.init_app(app)
    csrf.init_app(app)

    # ── Login manager configuration ────────────────────────────────────────────
    login_manager.login_view = "auth.login"          # Redirect here if not logged in
    login_manager.login_message = "Please log in to access this page."
    login_manager.login_message_category = "warning"

    # ── Register blueprints (route groups) ─────────────────────────────────────
    from app.routes.auth import auth_bp
    from app.routes.student import student_bp
    from app.routes.lecturer import lecturer_bp
    from app.routes.hod import hod_bp
    from app.routes.admin import admin_bp
    from app.routes.api import api_bp

    app.register_blueprint(auth_bp)                      # /login, /logout
    app.register_blueprint(student_bp, url_prefix="/student")
    app.register_blueprint(lecturer_bp, url_prefix="/lecturer")
    app.register_blueprint(hod_bp, url_prefix="/hod")
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(api_bp, url_prefix="/api/v1")  # REST API

    # ── Import models so Flask-Migrate can detect them ─────────────────────────
    with app.app_context():
        from app.models import user, course, result  # noqa: F401

    return app
"""
backend/app/__init__.py
-----------------------
Application Factory Pattern.

Why a factory function instead of a global `app = Flask(__name__)`?
- Allows creating multiple app instances (e.g., one for dev, one for testing)
- Prevents circular imports
- Makes testing much cleaner

All extensions are initialized here and passed the app instance.
All blueprints (routes) are registered here.
"""

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_bcrypt import Bcrypt
from flask_migrate import Migrate
from flask_mail import Mail
from flask_wtf.csrf import CSRFProtect

from config import config_map

# ─── Extension instances (not yet bound to any app) ───────────────────────────
db = SQLAlchemy()
login_manager = LoginManager()
bcrypt = Bcrypt()
migrate = Migrate()
mail = Mail()
csrf = CSRFProtect()


def create_app(config_name: str = "default") -> Flask:
    """
    Create and configure the Flask application.

    Args:
        config_name: One of 'development', 'testing', 'production', 'default'

    Returns:
        Configured Flask app instance
    """
    app = Flask(
        __name__,
        template_folder="../../frontend/templates",
        static_folder="../../frontend/static",
    )

    # ── Load configuration ─────────────────────────────────────────────────────
    app.config.from_object(config_map[config_name])

    # ── Initialize extensions with this app ────────────────────────────────────
    db.init_app(app)
    login_manager.init_app(app)
    bcrypt.init_app(app)
    migrate.init_app(app, db)
    mail.init_app(app)
    csrf.init_app(app)

    # ── Login manager configuration ────────────────────────────────────────────
    login_manager.login_view = "auth.login"          # Redirect here if not logged in
    login_manager.login_message = "Please log in to access this page."
    login_manager.login_message_category = "warning"

    # ── Register blueprints (route groups) ─────────────────────────────────────
    from app.routes.auth import auth_bp
    from app.routes.student import student_bp
    from app.routes.lecturer import lecturer_bp
    from app.routes.hod import hod_bp
    from app.routes.admin import admin_bp
    from app.routes.api import api_bp

    app.register_blueprint(auth_bp)                      # /login, /logout
    app.register_blueprint(student_bp, url_prefix="/student")
    app.register_blueprint(lecturer_bp, url_prefix="/lecturer")
    app.register_blueprint(hod_bp, url_prefix="/hod")
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(api_bp, url_prefix="/api/v1")  # REST API

    # ── Import models so Flask-Migrate can detect them ─────────────────────────
    with app.app_context():
        from app.models import user, course, result  # noqa: F401

    return app
