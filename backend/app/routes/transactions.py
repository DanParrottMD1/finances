from datetime import date
from decimal import Decimal, InvalidOperation

from flask import jsonify, request
from sqlalchemy.exc import SQLAlchemyError

from ..extensions import db
from ..models import Category, Transaction
from . import api
from .categories import CATEGORY_TYPES


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
        ), 500

    return jsonify({"data": transaction.to_dict()}), 201


def extract_query_positive_integer(name: str, default=None) -> int:
    raw_value = request.args.get(name)
    if raw_value is None:
        return default

    try:
        value = int(raw_value)
    except (ValueError, TypeError):
        raise TypeError(f"{name} must be a positive integer.")
    if value <= 0:
        raise ValueError(f"{name} must be a positive integer.")

    return value


def extract_query_date(name: str) -> date:
    raw_value = request.args.get(name)
    if raw_value is None:
        return None

    try:
        return date.fromisoformat(raw_value)
    except (ValueError, TypeError):
        raise TypeError(f"{name} must have the format YYYY-MM-DD.")


@api.get("/transactions")
def list_transactions():
    QUERY_PARAMETERS = set[str](
        [
            "type",
            "category_id",
            "start_date",
            "end_date",
            "search",
            "page",
            "per_page",
        ]
    )

    DEFAULT_PAGE_SIZE = 20
    MAX_PAGE_SIZE = 100

    unknown_parameters = set(request.args) - QUERY_PARAMETERS
    if unknown_parameters:
        return jsonify(
            {"error": f"Unknown query parameters: {', '.join(unknown_parameters)}"}
        ), 400

    category_type = request.args.get("type")
    if category_type is not None and category_type not in CATEGORY_TYPES:
        return jsonify({"error": "category_type must be income or spending."}), 400

    try:
        category_id = extract_query_positive_integer("category_id")
        start_date = extract_query_date("start_date")
        end_date = extract_query_date("end_date")
        page = extract_query_positive_integer("page", 1)
        per_page = extract_query_positive_integer("per_page", DEFAULT_PAGE_SIZE)
    except (TypeError, ValueError) as e:
        return jsonify({"error": str(e)}), 400

    if start_date is not None and end_date is not None and start_date > end_date:
        return jsonify({"error": "start_date must be before end_date."}), 400

    if per_page > MAX_PAGE_SIZE:
        return jsonify({"error": f"per_page must be at most {MAX_PAGE_SIZE}."}), 400

    search = request.args.get("search")
    if search is not None:
        search = search.strip()
        if not search:
            return jsonify({"error": "search cannot be blank."}), 400

    query = Transaction.query

    if category_type is not None:
        query = query.join(Category).filter(Category.category_type == category_type)
    if category_id is not None:
        query = query.filter(Transaction.category_id == category_id)
    if start_date is not None:
        query = query.filter(Transaction.transaction_date >= start_date)
    if end_date is not None:
        query = query.filter(Transaction.transaction_date <= end_date)
    if search is not None:
        query = query.filter(Transaction.description.ilike(f"%{search}%"))

    query = query.order_by(Transaction.transaction_date.desc(), Transaction.id.desc())

    transactions = query.paginate(page=page, per_page=per_page, error_out=False)
    return jsonify(
        {
            "data": [transaction.to_dict() for transaction in transactions],
            "pagination": {
                "page": transactions.page,
                "per_page": transactions.per_page,
                "total_items": transactions.total,
                "total_pages": transactions.pages,
                "has_next": transactions.has_next,
                "has_previous": transactions.has_prev,
            },
        }
    ), 200


@api.post("/transactions")
def create_transaction_route():
    return create_transaction()


@api.patch("/transactions/<int:transaction_id>")
def update_transaction(transaction_id: int):
    data = request.get_json(silent=True)

    transaction = db.session.get(Transaction, transaction_id)
    if transaction is None:
        return jsonify({"error": "The selected transaction does not exist."}), 404

    if not isinstance(data, dict):
        return jsonify({"error": "A JSON object is required."}), 400
    if not data:
        return jsonify({"error": "No fields to update."}), 400

    ALLOWED_FIELDS = ["amount", "transaction_date", "description", "category_id"]
    unknown_fields = set(data) - set(ALLOWED_FIELDS)
    if unknown_fields:
        return jsonify({"error": f"Invalid fields: {', '.join(unknown_fields)}"}), 400

    values = {}
    try:
        if "amount" in data:
            values["amount"] = extract_transaction_amount(data)
        if "transaction_date" in data:
            values["transaction_date"] = extract_transaction_date(data)
        if "description" in data:
            values["description"] = extract_transaction_description(data)
        if "category_id" in data:
            values["category_id"] = extract_transaction_category_id(data)
            category = db.session.get(Category, values["category_id"])
            if category is None:
                return jsonify({"error": "The selected category does not exist."}), 404
    except (TypeError, ValueError) as e:
        return jsonify({"error": str(e)}), 400

    for field, value in values.items():
        setattr(transaction, field, value)

    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        return jsonify(
            {"error": "An error occurred while updating the transaction."}
        ), 500

    return jsonify({"data": transaction.to_dict()}), 200


@api.delete("/transactions/<int:transaction_id>")
def delete_transaction(transaction_id: int):
    transaction = db.session.get(Transaction, transaction_id)
    if transaction is None:
        return jsonify({"error": "The selected transaction does not exist."}), 404

    db.session.delete(transaction)

    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        return jsonify(
            {"error": "An error occurred while deleting the transaction."}
        ), 500

    return "", 204
