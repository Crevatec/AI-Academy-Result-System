"""
backend/run.py
---------------
Application entry point.

For development:
    python run.py

For production (gunicorn):
    gunicorn "run:app" --workers 4 --bind 0.0.0.0:8000

The FLASK_ENV environment variable controls which config is loaded:
    development (default) → DevelopmentConfig → SQLite
    production            → ProductionConfig   → PostgreSQL
"""

import os
from app import create_app

# Read environment from .env or system environment
env = os.environ.get("FLASK_ENV", "development")

app = create_app(env)

if __name__ == "__main__":
    print(f"\n{'='*55}")
    print(f"  AcadResult System starting in [{env.upper()}] mode")
    print(f"  URL: http://localhost:5000")
    print(f"{'='*55}\n")
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=(env == "development"),
    )
