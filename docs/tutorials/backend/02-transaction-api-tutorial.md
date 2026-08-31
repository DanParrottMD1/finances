# Tutorial: add unified transaction API endpoints

This tutorial uses the current schema: one categories table and one transactions
table. It adds these endpoints:

```text
GET  /api/transactions
POST /api/transactions
```

The list endpoint also accepts an optional type query parameter, the same pattern
used by GET /api/categories.

Every transaction references a category. Income or spending is determined by that
category's category_type value, so transactions do not store a duplicate type.

## What we are building

A client will create a transaction with JSON such as:

```json
{
  "amount": "42.75",
  "transaction_date": "2026-08-25",
  "description": "Weekly shop",
  "category_id": 2
}
```

The category with ID 2 must already exist. If it is a spending category, this is
a spending transaction; if it is an income category, it is income.

## Before you start

Complete the unified category API tutorial first. You need at least one income
category and one spending category in MariaDB so the type filter can be tested.

Create a branch:

```sh
cd ~/finance-app
git switch -c add-transaction-endpoints
```

## Step 1: add the Transaction model

Open backend/app/models.py. Below Category, add:

```python
class Transaction(db.Model):
    __tablename__ = "transactions"

    id = db.Column(db.BigInteger, primary_key=True)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    transaction_date = db.Column(db.Date, nullable=False)
    description = db.Column(db.String(255))
    category_id = db.Column(
        db.BigInteger,
        db.ForeignKey("categories.id"),
        nullable=False,
    )

    category = db.relationship("Category")

    def to_dict(self):
        return {
            "id": self.id,
            "amount": str(self.amount),
            "transaction_date": self.transaction_date.isoformat(),
            "description": self.description,
            "category_id": self.category_id,
            "category": self.category.to_dict(),
        }
```

### Why does the model have a relationship?

category_id is the actual foreign-key column stored in MariaDB. The category
relationship is a convenient SQLAlchemy link. It lets you access:

```python
transaction.category.description
transaction.category.category_type
```

The type appears in the response inside category, rather than being copied into
the transaction row.

### Why is amount converted to a string?

Decimal values should not be converted to float. Serializing them as strings
preserves exact values such as "42.75".

## Step 2: add parsing imports

Open backend/app/routes.py. Add these imports above the Flask imports:

```python
from datetime import date
from decimal import Decimal, InvalidOperation
```

Extend the models import so it includes both classes:

```python
from .models import Category, Transaction
```

## Step 3: add a transaction creation helper

Below the category helper, add:

```python
def create_transaction():
    """Validate and persist one transaction."""
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "A JSON object is required."}), 400

    raw_amount = data.get("amount")
    if isinstance(raw_amount, bool) or raw_amount is None:
        return jsonify({"error": "amount is required."}), 400

    try:
        amount = Decimal(str(raw_amount))
    except (InvalidOperation, ValueError):
        return jsonify({"error": "amount must be a decimal value."}), 400

    if not amount.is_finite() or amount <= 0:
        return jsonify({"error": "amount must be greater than zero."}), 400

    if amount.as_tuple().exponent < -2:
        return jsonify({"error": "amount cannot have more than 2 decimal places."}), 400

    if amount > Decimal("99999999.99"):
        return jsonify({"error": "amount is too large."}), 400

    raw_date = data.get("transaction_date")
    if not isinstance(raw_date, str):
        return jsonify({"error": "transaction_date must be YYYY-MM-DD."}), 400

    try:
        transaction_date = date.fromisoformat(raw_date)
    except ValueError:
        return jsonify({"error": "transaction_date must be YYYY-MM-DD."}), 400

    category_id = data.get("category_id")
    if isinstance(category_id, bool) or not isinstance(category_id, int) or category_id < 1:
        return jsonify({"error": "category_id must be a positive integer."}), 400

    category = db.session.get(Category, category_id)
    if category is None:
        return jsonify({"error": "The selected category does not exist."}), 404

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
    db.session.commit()

    return jsonify({"data": transaction.to_dict()}), 201
```

### What the helper protects against

- Decimal avoids floating-point money errors.
- The amount checks match DECIMAL(10, 2): at most two decimal places and a
  maximum of 99,999,999.99.
- date.fromisoformat accepts the ISO date format used by the API.
- A category lookup produces a clear 404 response before the foreign-key
  constraint would reject the insert.
- An empty optional description is saved as NULL.

## Step 4: add transaction routes

Below your category routes, add:

```python
@api.get("/transactions")
def list_transactions():
    category_type = request.args.get("type")

    query = Transaction.query.order_by(
        Transaction.transaction_date.desc(),
        Transaction.id.desc(),
    )
    if category_type is not None:
        if category_type not in CATEGORY_TYPES:
            return jsonify({"error": "type must be income or spending."}), 400
        query = query.join(Category).filter(
            Category.category_type == category_type,
        )

    transactions = query.all()
    return jsonify({"data": [transaction.to_dict() for transaction in transactions]})


@api.post("/transactions")
def create_transaction_route():
    return create_transaction()
```

The list is ordered with the newest date first. The ID gives a consistent order
when multiple transactions have the same date.

The optional query parameter lets one endpoint serve both use cases:

```text
GET /api/transactions
GET /api/transactions?type=income
GET /api/transactions?type=spending
```

Reuse CATEGORY_TYPES from the category tutorial. An invalid type such as
`?type=other` should return 400, not an empty list.

### Why join Category?

Transactions do not store income or spending. That value lives on
categories.category_type. The list route therefore joins Category and filters
Category.category_type. MariaDB then returns only the matching rows, instead of
sending every transaction and leaving the split to the client.

## Step 5: restart and test

Restart Flask:

```sh
cd ~/finance-app/backend
source .venv/bin/activate
FLASK_DEBUG=0 flask --app run run --host 0.0.0.0 --port 5001
```

Check category IDs:

```sh
curl http://127.0.0.1:5001/api/categories
```

Then use actual category IDs to create one income transaction and one spending
transaction:

```sh
curl -i -X POST http://127.0.0.1:5001/api/transactions \
  -H 'Content-Type: application/json' \
  -d '{
    "amount": "2500.00",
    "transaction_date": "2026-08-25",
    "description": "August salary",
    "category_id": 1
  }'

curl -i -X POST http://127.0.0.1:5001/api/transactions \
  -H 'Content-Type: application/json' \
  -d '{
    "amount": "42.75",
    "transaction_date": "2026-08-25",
    "description": "Weekly shop",
    "category_id": 2
  }'
```

List every transaction, then filter by type:

```sh
curl http://127.0.0.1:5001/api/transactions
curl 'http://127.0.0.1:5001/api/transactions?type=income'
curl 'http://127.0.0.1:5001/api/transactions?type=spending'
```

Each transaction in the response should include the linked category. The income
filter should return only the salary row; the spending filter should return only
the shop row.

## Step 6: test invalid requests

Too many decimal places:

```sh
curl -i -X POST http://127.0.0.1:5001/api/transactions \
  -H 'Content-Type: application/json' \
  -d '{"amount":"4.999","transaction_date":"2026-08-25","category_id":1}'
```

Invalid date:

```sh
curl -i -X POST http://127.0.0.1:5001/api/transactions \
  -H 'Content-Type: application/json' \
  -d '{"amount":"4.99","transaction_date":"25-08-2026","category_id":1}'
```

Unknown category:

```sh
curl -i -X POST http://127.0.0.1:5001/api/transactions \
  -H 'Content-Type: application/json' \
  -d '{"amount":"4.99","transaction_date":"2026-08-25","category_id":999999}'
```

Invalid list type:

```sh
curl -i 'http://127.0.0.1:5001/api/transactions?type=other'
```

Expected results:

| Situation | Expected status |
| --- | --- |
| Valid transaction | 201 Created |
| Missing or invalid fields | 400 Bad Request |
| Amount is zero, negative, too large, or has over two decimal places | 400 Bad Request |
| Invalid date | 400 Bad Request |
| Category does not exist | 404 Not Found |
| GET /api/transactions?type=other | 400 Bad Request |

## Step 7: inspect the joined data in DBeaver

```sql
SELECT
    t.id,
    t.transaction_date,
    t.amount,
    t.description,
    c.description AS category_description,
    c.category_type
FROM finance_dev.transactions AS t
JOIN finance_dev.categories AS c ON c.id = t.category_id
ORDER BY t.transaction_date DESC, t.id DESC;
```

## Step 8: commit the milestone

```sh
cd ~/finance-app
git add backend/app/models.py backend/app/routes.py \
  backend/docs/02-transaction-api-tutorial.md
git commit -m "Add unified transaction endpoints"
git push -u origin add-transaction-endpoints
```

## What comes next

The API now supports the core data entry flow. Next, add automated tests before
React starts depending on these endpoints.

