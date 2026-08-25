from flask import Flask
from flask_cors import CORS

from .config import Config
from .extensions import db


def create_app():
    """Create and configure the Flask application."""
    app = Flask(__name__)
    app.config.from_object(Config)

    allowed_origins = [
        origin.strip()
        for origin in app.config["CORS_ORIGINS"].split(",")
        if origin.strip()
    ]
    CORS(app, resources={r"/api/*": {"origins": allowed_origins}})

    db.init_app(app)

    from .routes import api

    app.register_blueprint(api, url_prefix="/api")

    return app
