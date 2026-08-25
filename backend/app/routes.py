from flask import Blueprint, current_app, jsonify, request
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from .extensions import db
from .models import IncomeCategory, SpendingCategory


api = Blueprint("api", __name__)

def create_category(model):
    """Validate a category request and save an instance of the supplied model."""
    data = request.get_json(silent=True)
    
    if not isinstance(data, dict):
        return jsonify({"error": "A JSON object is required."}), 400
    
    description = data.get("description")
    if not isinstance(description, str):
        return jsonify({"error": "The description must be a string."}), 400
    
    description = description.strip()
    if not description:
        return jsonify({"error": "The description cannot be blank."}), 400
    
    if len(description) > 100:
        return jsonify({"error": "The description cannot be longer than 100 characters."}), 400
    
    category = model(description=description)
    db.session.add(category)
    
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "A category with that description already exists."}), 409
    
    return jsonify({"data": category.to_dict()}), 201

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

@api.post("/income-categories")
def create_income_category():
    return create_category(IncomeCategory)


@api.get("/spending-categories")
def list_spending_categories():
    categories = SpendingCategory.query.order_by(SpendingCategory.description).all()
    return jsonify({"data": [category.to_dict() for category in categories]})

@api.post("/spending-categories")
def create_spending_category():
    return create_category(SpendingCategory)