from flask import Blueprint, current_app, jsonify
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from ..extensions import db

api = Blueprint("api", __name__)


@api.get("/health")
def health_check():
    try:
        db.session.execute(text("SELECT 1"))
    except SQLAlchemyError:
        current_app.logger.error("Database health check failed")
        return jsonify({"status": "unavailable"}), 503

    return jsonify({"status": "ok"})


from . import categories, transactions  # noqa: E402, F401
