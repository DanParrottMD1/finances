# Tutorial: create category API endpoints

This tutorial adds the first write operations to the Flask API:

```text
GET  /api/income-categories
POST /api/income-categories

GET  /api/spending-categories
POST /api/spending-categories
```

The GET endpoints already exist. You will add the two POST endpoints yourself.
Do not move on until you have tested each step.

## What we are building

An API client will send JSON such as:

```json
{
  "description": "Salary"
}
```

Flask will validate it, create an IncomeCategory or SpendingCategory object,
save it to MariaDB, and return the new record as JSON.

For example, a successful request to POST /api/income-categories will return
HTTP status 201 Created:

```json
{
  "data": {
    "id": 1,
    "description": "Salary"
  }
}
```

## Before you start

From the project root, make a branch for this small piece of work:

```sh
git switch -c add-category-endpoints
```

Start the Flask app if it is not already running. This project is exposed to the
LAN, so leave debug mode off:

```sh
cd backend
source .venv/bin/activate
FLASK_DEBUG=0 flask --app run run --host 0.0.0.0 --port 5001
```

Because debug mode is disabled, stop the server with Ctrl+C and start it again
after each Python change.

## Step 1: understand the existing pieces

Open backend/app/models.py. The existing classes map Python objects to your
database tables:

```python
class IncomeCategory(db.Model):
    __tablename__ = "income_categories"
```

IncomeCategory(description="Salary") represents one row in income_categories.
Flask-SQLAlchemy tracks it in a database session. Calling db.session.commit()
writes the row to MariaDB.

Open backend/app/routes.py. It already contains the api blueprint and the two
read-only category routes. This is where the new routes belong.

## Step 2: import what a POST route needs

At the top of backend/app/routes.py, change the imports to:

```python
from flask import Blueprint, current_app, jsonify, request
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
```

Why:

- request gives a route access to the incoming JSON body.
- IntegrityError is raised when MariaDB rejects an insert, including when a
  category description violates your UNIQUE constraint.
- SQLAlchemyError is still used by the health check.

## Step 3: write one reusable validation-and-save helper

Add this function below api = Blueprint("api", __name__) and above the route
functions:

```python
def create_category(model):
    """Validate a category request and save an instance of the supplied model."""
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

    category = model(description=description)
    db.session.add(category)

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "A category with that description already exists."}), 409

    return jsonify({"data": category.to_dict()}), 201
```

### Why validate in the API and database?

The API validation gives the caller a helpful message before attempting a bad
write. The database UNIQUE constraint is still essential: it is the final
authority and prevents duplicates even if two requests arrive at the same time.

db.session.rollback() is important. A failed commit leaves a SQLAlchemy session
in an error state; rolling it back makes it safe to use for the next request.

The helper accepts model so the same logic can create either type of category
without copying the validation code.

## Step 4: add the income category POST route

Add this route below list_income_categories:

```python
@api.post("/income-categories")
def create_income_category():
    return create_category(IncomeCategory)
```

@api.post(...) means this function only handles HTTP POST requests. Passing
IncomeCategory to the helper tells it which MariaDB table to use.

## Step 5: add the spending category POST route

Add this route below list_spending_categories:

```python
@api.post("/spending-categories")
def create_spending_category():
    return create_category(SpendingCategory)
```

This is intentionally almost identical to the income route. The shared helper
keeps the behavior consistent while the route makes the API explicit and easy to
read.

## Step 6: restart Flask and test with curl

If Flask is running, stop it with Ctrl+C, then run:

```sh
FLASK_DEBUG=0 flask --app run run --host 0.0.0.0 --port 5001
```

In a second terminal, create an income category:

```sh
curl -i -X POST http://127.0.0.1:5001/api/income-categories \
  -H 'Content-Type: application/json' \
  -d '{"description":"Salary"}'
```

You should see HTTP/1.1 201 CREATED and the new category in the response.

Create a spending category:

```sh
curl -i -X POST http://127.0.0.1:5001/api/spending-categories \
  -H 'Content-Type: application/json' \
  -d '{"description":"Groceries"}'
```

List the saved records:

```sh
curl http://127.0.0.1:5001/api/income-categories
curl http://127.0.0.1:5001/api/spending-categories
```

## Step 7: deliberately test failure cases

These checks confirm that your validation is behaving as intended.

No JSON body:

```sh
curl -i -X POST http://127.0.0.1:5001/api/income-categories
```

Blank description:

```sh
curl -i -X POST http://127.0.0.1:5001/api/income-categories \
  -H 'Content-Type: application/json' \
  -d '{"description":"   "}'
```

Duplicate description:

```sh
curl -i -X POST http://127.0.0.1:5001/api/income-categories \
  -H 'Content-Type: application/json' \
  -d '{"description":"Salary"}'
```

| Situation | Expected status |
| --- | --- |
| Valid new category | 201 Created |
| No JSON, wrong type, blank text, or text over 100 characters | 400 Bad Request |
| Duplicate category | 409 Conflict |

## Step 8: inspect the result in DBeaver

In DBeaver, run:

```sql
SELECT * FROM finance_dev.income_categories;
SELECT * FROM finance_dev.spending_categories;
```

You should see the categories created through the API. This is a useful way to
connect what Flask did in Python with the rows stored in MariaDB.

## Step 9: commit the completed milestone

When every test passes:

```sh
cd ~/finance-app
git status
git add backend/app/routes.py backend/docs/01-category-api-tutorial.md
git commit -m "Add category creation endpoints"
git push -u origin add-category-endpoints
```

If you prefer to keep the work directly on main, switch back to main before
starting and use git push instead. For learning Git, the short-lived branch is
worth practising.

## What comes next

The next feature is POST /api/income-transactions, then its spending equivalent.
It will build on the same flow but introduces three useful ideas:

1. validating money with Python's Decimal type;
2. parsing an ISO date such as 2026-08-25;
3. checking that the referenced category exists before inserting the transaction.

