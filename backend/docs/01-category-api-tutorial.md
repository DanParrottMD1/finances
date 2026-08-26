# Tutorial: create unified category API endpoints

This tutorial matches the current database schema:

```text
categories
  id
  description
  category_type     income | spending

transactions
  id
  amount
  transaction_date
  description
  category_id       references categories.id
```

You will build two category endpoints:

```text
GET  /api/categories
POST /api/categories
```

A category has a description and a type. The type belongs to the category, not
to an individual transaction. A transaction's type is determined by the category
it references.

## What we are building

A client can create a category by sending:

```json
{
  "description": "Salary",
  "category_type": "income"
}
```

A successful request returns HTTP status 201 Created:

```json
{
  "data": {
    "id": 1,
    "description": "Salary",
    "category_type": "income"
  }
}
```

## Before you start

Make sure the new two-table schema has been applied to MariaDB. Create a branch:

```sh
cd ~/finance-app
git switch -c add-category-endpoints
```

Start Flask from the backend directory:

```sh
cd backend
source .venv/bin/activate
FLASK_DEBUG=0 flask --app run run --host 0.0.0.0 --port 5001
```

Restart Flask after every Python change because debug mode is off.

## Step 1: create the Category model

Open backend/app/models.py. The old IncomeCategory and SpendingCategory classes
should be replaced by one Category class. Add this class:

```python
class Category(db.Model):
    __tablename__ = "categories"

    id = db.Column(db.BigInteger, primary_key=True)
    description = db.Column(db.String(100), nullable=False)
    category_type = db.Column(db.String(20), nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "description": self.description,
            "category_type": self.category_type,
        }
```

The model maps directly to the categories table:

- __tablename__ selects the database table.
- each db.Column maps to a table column.
- to_dict converts the model into JSON-ready Python data.

The database uses ENUM for category_type. A string column in SQLAlchemy works
well here because it reads and writes the ENUM values as ordinary Python strings.

## Step 2: import the tools used by POST routes

Open backend/app/routes.py. At the top, use these imports:

```python
from flask import Blueprint, current_app, jsonify, request
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from .extensions import db
from .models import Category
```

Why:

- request reads the JSON sent to Flask;
- IntegrityError lets the API handle the database UNIQUE constraint cleanly;
- Category is the one model used by these routes.

## Step 3: add a category creation helper

Below api = Blueprint("api", __name__), add:

```python
CATEGORY_TYPES = {"income", "spending"}


def create_category():
    """Validate and create one category."""
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
```

### Why validate twice?

The API validation gives callers helpful errors. The database constraint remains
the final authority. It prevents duplicate descriptions even if two requests
arrive at nearly the same time.

After a failed commit, db.session.rollback() is required. Without it, the session
is left in an error state and later database work in the request can fail.

## Step 4: add the list and create routes

Add these routes below the health check:

```python
@api.get("/categories")
def list_categories():
    category_type = request.args.get("type")

    query = Category.query.order_by(Category.category_type, Category.description)
    if category_type is not None:
        if category_type not in CATEGORY_TYPES:
            return jsonify({"error": "type must be income or spending."}), 400
        query = query.filter_by(category_type=category_type)

    categories = query.all()
    return jsonify({"data": [category.to_dict() for category in categories]})


@api.post("/categories")
def create_category_route():
    return create_category()
```

The optional query parameter lets one endpoint serve both use cases:

```text
GET /api/categories
GET /api/categories?type=income
GET /api/categories?type=spending
```

This is simpler than maintaining separate income and spending endpoints.

## Step 5: restart and test

Restart Flask, then create categories:

```sh
curl -i -X POST http://127.0.0.1:5001/api/categories \
  -H 'Content-Type: application/json' \
  -d '{"description":"Salary","category_type":"income"}'

curl -i -X POST http://127.0.0.1:5001/api/categories \
  -H 'Content-Type: application/json' \
  -d '{"description":"Groceries","category_type":"spending"}'
```

List all categories:

```sh
curl http://127.0.0.1:5001/api/categories
```

List one type:

```sh
curl 'http://127.0.0.1:5001/api/categories?type=income'
```

## Step 6: test error cases

Try an invalid type:

```sh
curl -i -X POST http://127.0.0.1:5001/api/categories \
  -H 'Content-Type: application/json' \
  -d '{"description":"Test","category_type":"other"}'
```

Try a duplicate description:

```sh
curl -i -X POST http://127.0.0.1:5001/api/categories \
  -H 'Content-Type: application/json' \
  -d '{"description":"Salary","category_type":"income"}'
```

Expected results:

| Situation | Expected status |
| --- | --- |
| Valid category | 201 Created |
| Missing or invalid fields | 400 Bad Request |
| Duplicate description | 409 Conflict |

## Step 7: inspect the data in DBeaver

```sql
SELECT id, description, category_type
FROM finance_dev.categories
ORDER BY category_type, description;
```

## Step 8: commit the milestone

```sh
cd ~/finance-app
git add backend/app/models.py backend/app/routes.py \
  backend/docs/01-category-api-tutorial.md
git commit -m "Add unified category endpoints"
git push -u origin add-category-endpoints
```

## What comes next

The next tutorial adds one transactions endpoint. It will validate Decimal money
and dates, confirm that a category exists, and derive the transaction type from
the joined category.

