from datetime import date
from decimal import Decimal, InvalidOperation

from flask import Blueprint, current_app, request, jsonify
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from .extensions import db
from .models import Category, Transaction

api = Blueprint('api', __name__)

CATEGORY_TYPES = ['income', 'spending']

@api.get("/health")
def health_check():
    try:
        db.session.execute(text("SELECT 1"))
    except SQLAlchemyError:
        current_app.logger.error("Database health check failed")
        return jsonify({"status": "unavailable"}), 503
    
    return jsonify({"status": "ok"})

def create_category():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "A JSON object is required."}), 400

    description = data.get("description")
    if not isinstance(description, str):
        return jsonify({"error": "description must be a string."}), 400

    description = description.strip()
    if not description:
        return jsonify({"error": "description cannot be blank."}), 400

    if len(description) > 100:
        return jsonify({"error": "description cannot exceed 100 characters."}), 400

    category_type = data.get("category_type")
    if category_type not in CATEGORY_TYPES:
        return jsonify({"error": "category_type must be income or spending."}), 400

    category = Category(
        description=description,
        category_type=category_type,
    )
    db.session.add(category)

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "A category with that description already exists."}), 409

    return jsonify({"data": category.to_dict()}), 201

def create_transaction():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "A JSON object is required."}), 400
    
    # Validate amount
    raw_amount = data.get("amount")
    if isinstance(raw_amount, bool) or raw_amount is None:
        return jsonify({"error": "amount is required."}), 400

    try:
        amount = Decimal(str(raw_amount))
    except (InvalidOperation, ValueError):
        return jsonify({"error": "amount must be a valid decimal value."}), 400

    if not amount.is_finite() or amount <= 0:
        return jsonify({"error": "amount must be greater than 0."}), 400
    
    if amount.as_tuple().exponent < -2:
        return jsonify({"error": "amount must have at most 2 decimal places."}), 400
    
    if amount > Decimal("9999999999.99"):
        return jsonify({"error": "amount must be less than 10 billion."}), 400

    # Validate transaction_date
    raw_date = data.get("transaction_date")
    if not isinstance(raw_date, str):
        return jsonify({"error": "transaction_date must have the format YYYY-MM-DD."}), 400

    try:
        transaction_date = date.fromisoformat(raw_date)
    except ValueError:
        return jsonify({"error": "transaction_date must have the format YYYY-MM-DD."}), 400

    if transaction_date > date.today():
        return jsonify({"error": "transaction_date cannot be in the future."}), 400
    
    # Validate category_id
    category_id = data.get("category_id")
    if not isinstance(category_id, int) or category_id <= 0:
        return jsonify({"error": "category_id must be a positive integer."}), 400

    category = db.session.get(Category, category_id)
    if category is None:
        return jsonify({"error": "The selected category does not exist."}), 404

    # Validate description
    description = data.get("description")
    if description is not None:
        if not isinstance(description, str):
            return jsonify({"error": "description must be a string."}), 400

        description = description.strip()
        if len(description) > 255:
            return jsonify({"error": "description cannot exceed 255 characters."}), 400
        
        if not description:
            description = None

    transaction = Transaction(
        amount=amount,
        transaction_date=transaction_date,
        description=description,
        category_id=category_id,
    )
    db.session.add(transaction)

    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({"error": "An error occurred while creating the transaction."}), 400

    return jsonify({"data": transaction.to_dict()}), 201
    
@api.get("/categories")
def list_categories():
    category_type = request.args.get("type")
    
    query = Category.query.order_by(Category.category_type, Category.description)
    if category_type is not None:
        if category_type not in CATEGORY_TYPES:
            return jsonify({"error": "category_type must be income or spending."}), 400
        query = query.filter(Category.category_type == category_type)

    categories = query.all()
    return jsonify({"data": [category.to_dict() for category in categories]}), 200

@api.post("/categories")
def create_category_route():
    return create_category()

@api.get("/transactions")
def list_transactions():
    category_type = request.args.get("type")
    
    query = Transaction.query.order_by(
        Transaction.transaction_date.desc(),
        Transaction.id.desc(),
    )
    if category_type is not None:
        if category_type not in CATEGORY_TYPES:
            return jsonify({"error": "category_type must be income or spending."}), 400
        query = query.join(Category).filter(Category.category_type == category_type)

    transactions = query.all()
    return jsonify({"data": [transaction.to_dict() for transaction in transactions]}), 200

@api.post("/transactions")
def create_transaction_route():
    return create_transaction()

