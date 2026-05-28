"""
config.py
---------
Configuration classes for different environments.
Flask loads the right class based on FLASK_ENV environment variable.

Why separate classes:
- Development: SQLite (no server needed), debug mode on, fake email
- Testing: In-memory SQLite (fast, disposable), CSRF disabled
- Production: PostgreSQL, real email, debug off, secret key from env
"""

import os
from dotenv import load_dotenv

load_dotenv()


class BaseConfig:
    """Settings shared by all environments."""

    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-insecure-key-change-me")

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Flask-Mail
    MAIL_SERVER          = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT            = int(os.environ.get("MAIL_PORT", 587))
    MAIL_USE_TLS         = True
    MAIL_USERNAME        = os.environ.get("MAIL_USERNAME")
    MAIL_PASSWORD        = os.environ.get("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER  = os.environ.get("MAIL_DEFAULT_SENDER", "noreply@acadresult.ng")

    # Application
    INSTITUTION_NAME      = os.environ.get("INSTITUTION_NAME", "Temple Gate Polytechnic. Aba")
    PORTAL_URL            = os.environ.get("PORTAL_URL", "http://localhost:5000")
    DEFAULT_GRADING_SCALE = os.environ.get("DEFAULT_GRADING_SCALE", "5.0")

    # File uploads
    UPLOAD_FOLDER      = os.path.join(os.path.dirname(__file__), "uploads")
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5 MB
    ALLOWED_EXTENSIONS = {"xlsx", "xls"}

    # AI model
    AI_MODEL_PATH = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "ai_module", "models", "performance_model.pkl"
    )


class DevelopmentConfig(BaseConfig):
    """
    Local development — SQLite, debug on, emails suppressed (printed to console).
    """
    DEBUG   = True
    TESTING = False

    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DEV_DATABASE_URL",
        "sqlite:///acadresult_dev.db"
    )

    MAIL_SUPPRESS_SEND = True   # Emails print to console instead of sending


class TestingConfig(BaseConfig):
    """
    Automated tests — in-memory SQLite, CSRF off, emails suppressed.
    """
    DEBUG   = False
    TESTING = True

    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"

    WTF_CSRF_ENABLED   = False
    MAIL_SUPPRESS_SEND = True


class ProductionConfig(BaseConfig):
    """
    Live server — PostgreSQL, real emails, debug off.
    All secrets must come from Render environment variables.
    """
    DEBUG   = False
    TESTING = False

    # ── Render fix: Render gives DATABASE_URL starting with "postgres://"
    # but SQLAlchemy 2.x requires "postgresql://" — this corrects it automatically
    _db_url = os.environ.get("DATABASE_URL", "")
    SQLALCHEMY_DATABASE_URI = (
        _db_url.replace("postgres://", "postgresql://", 1)
        if _db_url else None
    )

    SECRET_KEY         = os.environ.get("SECRET_KEY")
    MAIL_SUPPRESS_SEND = False  # Real emails enabled

    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,   # Test connection before using
        "pool_recycle": 300,     # Recycle connections every 5 mins
    }


config_map = {
    "development": DevelopmentConfig,
    "testing":     TestingConfig,
    "production":  ProductionConfig,
    "default":     DevelopmentConfig,
}