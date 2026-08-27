from datetime import date
from decimal import Decimal, InvalidOperation

from flask import Blueprint, current_app, jsonify, request
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from .extensions import db
from .models import Category, Transaction

api = Blueprint("api", __name__)

CATEGORY_TYPES = ["income", "spending"]


@api.get("/health")
def health_check():
    try:
        db.session.execute(text("SELECT 1"))
    except SQLAlchemyError:
        current_app.logger.error("Database health check failed")
        return jsonify({"status": "unavailable"}), 503

    return jsonify({"status": "ok"})


def extract_category_description(data: dict) -> str:
    description = data.get("description")
    if not isinstance(description, str):
        raise TypeError("description must be a string.")

    description = description.strip()
    if not description:
        raise ValueError("description cannot be blank.")
    if len(description) > 100:
        raise ValueError("description cannot exceed 100 characters.")

    return description


def extract_category_type(data: dict) -> str:
    category_type = data.get("category_type")

    if not isinstance(category_type, str):
        raise TypeError("category_type must be a string.")
    if category_type not in CATEGORY_TYPES:
        raise ValueError("category_type must be income or spending.")

    return category_type


def create_category():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "A JSON object is required."}), 400

    try:
        description = extract_category_description(data)
        category_type = extract_category_type(data)
    except (TypeError, ValueError) as e:
        return jsonify({"error": str(e)}), 400

    category = Category(
        description=description,
        category_type=category_type,
    )
    db.session.add(category)

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify(
            {"error": "A category with that description already exists."}
        ), 409

    return jsonify({"data": category.to_dict()}), 201


def extract_transaction_amount(data: dict) -> Decimal:
    amount = data.get("amount")

    if amount is None:
        raise TypeError("amount is required.")
    if isinstance(amount, bool):
        raise TypeError("amount must be a valid decimal value.")
    try:
        amount = Decimal(str(amount))
    except (InvalidOperation, ValueError):
        raise ValueError("amount must be a valid decimal value.")
    if not amount.is_finite() or amount <= 0:
        raise ValueError("amount must be greater than 0.")
    if amount.as_tuple().exponent < -2:
        raise ValueError("amount must have at most 2 decimal places.")
    if amount > Decimal("99999999.99"):
        raise ValueError("amount too large.")

    return amount


def extract_transaction_date(data: dict) -> date:
    raw_date = data.get("transaction_date")
    if not isinstance(raw_date, str):
        raise TypeError("transaction_date must have the format YYYY-MM-DD.")

    try:
        transaction_date = date.fromisoformat(raw_date)
    except ValueError:
        raise ValueError("transaction_date must have the format YYYY-MM-DD.")
    if transaction_date > date.today():
        raise ValueError("transaction_date cannot be in the future.")

    return transaction_date


def extract_transaction_category_id(data: dict) -> int:
    category_id = data.get("category_id")

    if category_id is None:
        raise TypeError("category_id is required.")
    if isinstance(category_id, bool):
        raise TypeError("category_id must be a positive integer.")
    if not isinstance(category_id, int):
        raise TypeError("category_id must be a positive integer.")
    if category_id <= 0:
        raise ValueError("category_id must be a positive integer.")

    return category_id


def extract_transaction_description(data: dict) -> str:
    description = data.get("description")
    if description is None:
        return None

    if not isinstance(description, str):
        raise TypeError("description must be a string.")

    description = description.strip()
    if not description:
        return None
    if len(description) > 255:
        raise ValueError("description cannot exceed 255 characters.")

    return description


def create_transaction():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "A JSON object is required."}), 400

    try:
        amount = extract_transaction_amount(data)
        transaction_date = extract_transaction_date(data)
        description = extract_transaction_description(data)
        category_id = extract_transaction_category_id(data)
    except (TypeError, ValueError) as e:
        return jsonify({"error": str(e)}), 400

    category = db.session.get(Category, category_id)
    if category is None:
        return jsonify({"error": "The selected category does not exist."}), 404

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
        return jsonify(
            {"error": "An error occurred while creating the transaction."}
        ), 400

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
    return jsonify(
        {"data": [transaction.to_dict() for transaction in transactions]}
    ), 200


@api.post("/transactions")
def create_transaction_route():
    return create_transaction()
