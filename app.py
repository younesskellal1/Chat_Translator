"""Main Flask application entry point."""

import os
from flask import Flask
from models import init_db
from routes import register_routes


def create_app():
    """Create and configure the Flask application."""
    app = Flask(__name__, template_folder="templates", static_folder="static")
    
    # Configuration
    app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-key")
    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax',
        SESSION_COOKIE_SECURE=bool(os.environ.get('SESSION_COOKIE_SECURE', '0') == '1'),
        MAX_CONTENT_LENGTH=5 * 1024 * 1024,  # 5 MB upload limit
    )
    # Initialize database
    init_db()

    # Register routes
    register_routes(app)
    
    return app

if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5000, debug=True)
