from flask import Blueprint, current_app, jsonify
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from .extensions import db
from .models import IncomeCategory, SpendingCategory


api = Blueprint("api", __name__)


@api.get("/health")
def health_check():
    """Confirm that the API can reach MariaDB without exposing connection details."""
    try:
        db.session.execute(text("SELECT 1"))
    except SQLAlchemyError:
        current_app.logger.exception("Database health check failed")
        return jsonify({"status": "unavailable"}), 503

    return jsonify({"status": "ok"})


@api.get("/income-categories")
def list_income_categories():
    categories = IncomeCategory.query.order_by(IncomeCategory.description).all()
    return jsonify({"data": [category.to_dict() for category in categories]})


@api.get("/spending-categories")
def list_spending_categories():
    categories = SpendingCategory.query.order_by(SpendingCategory.description).all()
    return jsonify({"data": [category.to_dict() for category in categories]})
