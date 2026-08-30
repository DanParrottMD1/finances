from flask import jsonify, request
from sqlalchemy.exc import IntegrityError

from ..extensions import db
from ..models import Category
from . import api

CATEGORY_TYPES = ["income", "spending"]


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
