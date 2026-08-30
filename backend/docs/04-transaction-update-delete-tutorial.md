# Tutorial 4: update and delete transactions with tests

Tutorial 3 introduced automated API tests. In this tutorial you will use those
tests while adding the remaining transaction operations:

```text
PATCH  /api/transactions/<id>
DELETE /api/transactions/<id>
```

Categories remain deliberately limited to `GET` and `POST`. They are stable
reference data for transactions, so this application does not provide category
update or delete endpoints.

Allow about one hour:

| Activity | Time |
| --- | ---: |
| Understand the API decisions | 10 minutes |
| Write the first failing tests | 10 minutes |
| Reuse transaction validation | 20 minutes |
| Implement and test both endpoints | 15 minutes |
| Run the complete suite and review | 5 minutes |

## What we are building

Suppose transaction 12 currently contains:

```json
{
  "id": 12,
  "amount": "42.75",
  "transaction_date": "2026-08-20",
  "description": "Weekly shop",
  "category_id": 2
}
```

A client can change only its description:

```http
PATCH /api/transactions/12
Content-Type: application/json

{
  "description": "Groceries and toiletries"
}
```

The response is `200 OK` and contains the complete updated transaction. Fields
that were not sent retain their old values.

A client can remove the transaction with:

```http
DELETE /api/transactions/12
```

A successful deletion returns `204 No Content`. There is no JSON body because
the resource no longer exists.

Both endpoints return `404 Not Found` when the transaction ID does not exist.

## Why PATCH rather than PUT?

`PUT` normally represents replacing an entire resource. It would require the
caller to send the amount, date, category, and description even when changing
only one field.

`PATCH` represents a partial change. This request changes the amount while
preserving every other field:

```json
{
  "amount": "45.20"
}
```

The validation rules from transaction creation still apply. For example, a
patched amount must be positive and have no more than two decimal places.

## The red-green-refactor rhythm

For each behaviour in this tutorial:

```text
red:      write a test and see the expected failure
green:    add the smallest implementation that passes
refactor: remove duplication while keeping the tests green
```

Seeing the test fail first matters. It proves the test can detect the absence of
the new behaviour rather than passing accidentally.

## Before you start

Complete Tutorial 3 and make sure its test suite passes. Then create a branch:

```sh
cd ~/finance-app
git switch -c add-transaction-update-delete
cd backend
source .venv/bin/activate
pytest
```

Do not continue until the existing tests are green. You do not need to start
Flask or MariaDB: these tests use Flask's test client and SQLite database.

## Part 1: write two successful-path tests

Open `backend/tests/test_transactions.py` and add these tests. The existing
`transactions` fixture gives each test three saved transactions.

```python
def test_updates_one_transaction(client, transactions):
    transaction = transactions["meal"]

    response = client.patch(
        f"/api/transactions/{transaction.id}",
        json={"description": "Dinner with friends"},
    )

    assert response.status_code == 200
    data = response.json["data"]
    assert data["id"] == transaction.id
    assert data["description"] == "Dinner with friends"
    assert data["amount"] == "100.00"
    assert data["transaction_date"] == "2026-08-02"
    assert data["category_id"] == transaction.category_id


def test_deletes_one_transaction(client, transactions):
    transaction = transactions["meal"]

    response = client.delete(f"/api/transactions/{transaction.id}")

    assert response.status_code == 204
    assert response.data == b""

    response = client.get("/api/transactions")
    remaining_ids = [item["id"] for item in response.json["data"]]
    assert transaction.id not in remaining_ids
```

Important syntax:

- An f-string replaces `{transaction.id}` with the actual fixture ID.
- `client.patch` sends an HTTP PATCH request.
- `b""` is an empty byte string, which is Flask's representation of an empty
  response body.
- The final GET proves that the deletion was persisted, not merely reported.

Run only these two tests:

```sh
pytest -v tests/test_transactions.py -k 'updates_one or deletes_one'
```

Both should fail with `404 Not Found` because no route with a transaction ID
exists yet. This is the red stage.

## Part 2: make transaction validation reusable

Creation and updating must enforce the same rules. Copying all the validation
into a second route would allow the two endpoints to drift apart later. Instead,
extract it into one helper that supports two modes:

- creation requires amount, date, and category;
- partial updating validates only the fields present in the request.

In `backend/app/routes.py`, below `CATEGORY_TYPES`, add the allowed transaction
fields:

```python
TRANSACTION_FIELDS = {
    "amount",
    "transaction_date",
    "description",
    "category_id",
}
```

Replace the existing `create_transaction` helper with the following validation
helper and revised creation helper:

```python
def validate_transaction_payload(data, partial=False):
    """Return validated model values and an optional Flask error response."""
    if not isinstance(data, dict):
        return None, (jsonify({"error": "A JSON object is required."}), 400)

    if partial:
        if not data:
            return None, (
                jsonify({"error": "At least one transaction field is required."}),
                400,
            )

        if set(data) - TRANSACTION_FIELDS:
            return None, (
                jsonify(
                    {
                        "error": (
                            "Only amount, transaction_date, description, and "
                            "category_id can be updated."
                        )
                    }
                ),
                400,
            )

    values = {}

    if "amount" not in data:
        if not partial:
            return None, (jsonify({"error": "amount is required."}), 400)
    else:
        raw_amount = data["amount"]
        if raw_amount is None:
            return None, (jsonify({"error": "amount is required."}), 400)

        if isinstance(raw_amount, bool):
            return None, (
                jsonify({"error": "amount must be a valid decimal value."}),
                400,
            )

        try:
            amount = Decimal(str(raw_amount))
        except (InvalidOperation, ValueError):
            return None, (
                jsonify({"error": "amount must be a valid decimal value."}),
                400,
            )

        if not amount.is_finite() or amount <= 0:
            return None, (jsonify({"error": "amount must be greater than 0."}), 400)

        if amount.as_tuple().exponent < -2:
            return None, (
                jsonify({"error": "amount must have at most 2 decimal places."}),
                400,
            )

        if amount > Decimal("99999999.99"):
            return None, (jsonify({"error": "amount too large."}), 400)

        values["amount"] = amount

    if "transaction_date" not in data:
        if not partial:
            return None, (
                jsonify(
                    {"error": "transaction_date must have the format YYYY-MM-DD."}
                ),
                400,
            )
    else:
        raw_date = data["transaction_date"]
        if not isinstance(raw_date, str):
            return None, (
                jsonify(
                    {"error": "transaction_date must have the format YYYY-MM-DD."}
                ),
                400,
            )

        try:
            transaction_date = date.fromisoformat(raw_date)
        except ValueError:
            return None, (
                jsonify(
                    {"error": "transaction_date must have the format YYYY-MM-DD."}
                ),
                400,
            )

        if transaction_date > date.today():
            return None, (
                jsonify({"error": "transaction_date cannot be in the future."}),
                400,
            )

        values["transaction_date"] = transaction_date

    if "category_id" not in data:
        if not partial:
            return None, (
                jsonify({"error": "category_id must be a positive integer."}),
                400,
            )
    else:
        category_id = data["category_id"]
        if (
            isinstance(category_id, bool)
            or not isinstance(category_id, int)
            or category_id <= 0
        ):
            return None, (
                jsonify({"error": "category_id must be a positive integer."}),
                400,
            )

        category = db.session.get(Category, category_id)
        if category is None:
            return None, (
                jsonify({"error": "The selected category does not exist."}),
                404,
            )

        values["category_id"] = category_id

    if "description" in data:
        description = data["description"]
        if description is not None:
            if not isinstance(description, str):
                return None, (
                    jsonify({"error": "description must be a string."}),
                    400,
                )

            description = description.strip()
            if len(description) > 255:
                return None, (
                    jsonify(
                        {"error": "description cannot exceed 255 characters."}
                    ),
                    400,
                )

            if not description:
                description = None

        values["description"] = description

    return values, None


def create_transaction():
    data = request.get_json(silent=True)
    values, error = validate_transaction_payload(data)
    if error is not None:
        return error

    transaction = Transaction(**values)
    db.session.add(transaction)

    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        return jsonify(
            {"error": "An error occurred while creating the transaction."}
        ), 400

    return jsonify({"data": transaction.to_dict()}), 201
```

`values` contains only data that is safe to assign to the model. For a PATCH,
an omitted field is absent from `values`, so its old model value remains intact.

The helper returns two values:

```text
valid request   -> ({"amount": Decimal("45.20")}, None)
invalid request -> (None, (JSON response, status code))
```

The `partial` default is `False`, so the existing POST endpoint still requires
all mandatory fields. Run the complete existing suite after the refactor:

```sh
pytest
```

Fix the refactor if any existing test fails. A refactor changes the structure of
code, not its externally visible behaviour.

## Part 3: implement PATCH

In `backend/app/routes.py`, add this route below the existing transaction routes:

```python
@api.patch("/transactions/<int:transaction_id>")
def update_transaction(transaction_id):
    transaction = db.session.get(Transaction, transaction_id)
    if transaction is None:
        return jsonify({"error": "Transaction not found."}), 404

    data = request.get_json(silent=True)
    values, error = validate_transaction_payload(data, partial=True)
    if error is not None:
        return error

    for field, value in values.items():
        setattr(transaction, field, value)

    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({"error": "The transaction could not be updated."}), 500

    return jsonify({"data": transaction.to_dict()}), 200
```

The route variable `<int:transaction_id>` turns that part of the URL into an
integer and passes it to the function.

`setattr` assigns an attribute whose name is held in a variable. This loop:

```python
for field, value in values.items():
    setattr(transaction, field, value)
```

has the same effect as writing assignments such as
`transaction.amount = value`, but it works for any validated field. It is safe
here because the helper rejects names outside `TRANSACTION_FIELDS`.

Run the update test again:

```sh
pytest -v tests/test_transactions.py::test_updates_one_transaction
```

It should now pass: the first green stage.

## Part 4: implement DELETE

Add the delete route:

```python
@api.delete("/transactions/<int:transaction_id>")
def delete_transaction(transaction_id):
    transaction = db.session.get(Transaction, transaction_id)
    if transaction is None:
        return jsonify({"error": "Transaction not found."}), 404

    db.session.delete(transaction)

    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({"error": "The transaction could not be deleted."}), 500

    return "", 204
```

`db.session.delete` marks the model for deletion. The change reaches the
database when `commit` succeeds. A failed database operation is rolled back so
the SQLAlchemy session remains usable.

Run the focused test:

```sh
pytest -v tests/test_transactions.py::test_deletes_one_transaction
```

## Part 5: your validation exercise

The successful paths are not enough. Spend about 15 minutes adding tests for
these behaviours before viewing the reference solution:

1. PATCH can change amount, date, description, and category.
2. A field omitted from PATCH is not changed.
3. A description containing only spaces clears the optional description to
   JSON `null`.
4. An empty object is rejected with `400`.
5. A non-object JSON body is rejected with `400`.
6. An unknown field such as `category_type` is rejected with `400`.
7. Invalid values follow the same rules and error messages as POST.
8. An unknown category ID returns `404`.
9. PATCH and DELETE both return `404` for an unknown transaction ID.

Use parameterisation for related invalid cases. You can reuse the existing
`_valid_transaction` helper when it is useful, but remember that a PATCH payload
does not need to contain every field.

Run the transaction tests frequently:

```sh
pytest -v tests/test_transactions.py
```

### Check atomic behaviour

Validation finishes before the route assigns any values to the transaction. A
request containing one valid field and one invalid field must change nothing:

```python
def test_invalid_patch_does_not_partially_update(client, transactions):
    transaction = transactions["meal"]

    response = client.patch(
        f"/api/transactions/{transaction.id}",
        json={"description": "Changed", "amount": "0"},
    )

    assert response.status_code == 400

    response = client.get("/api/transactions")
    saved = next(
        item
        for item in response.json["data"]
        if item["id"] == transaction.id
    )
    assert saved["description"] == "Dinner at the restaurant"
```

`next` takes the first item produced by the expression. This test finds the
transaction by ID rather than relying on its position in the sorted list.

## Part 6: reference test solution

Compare your tests with this solution. Equivalent tests with different names or
arrangement are fine.

```python
def test_updates_all_transaction_fields(client, transactions, categories):
    transaction = transactions["meal"]

    response = client.patch(
        f"/api/transactions/{transaction.id}",
        json={
            "amount": "125.50",
            "transaction_date": "2026-08-04",
            "description": "Corrected transaction",
            "category_id": categories["rent"].id,
        },
    )

    assert response.status_code == 200
    data = response.json["data"]
    assert data["amount"] == "125.50"
    assert data["transaction_date"] == "2026-08-04"
    assert data["description"] == "Corrected transaction"
    assert data["category_id"] == categories["rent"].id
    assert data["category"] == categories["rent"].to_dict()


def test_clears_transaction_description(client, transactions):
    transaction = transactions["meal"]

    response = client.patch(
        f"/api/transactions/{transaction.id}",
        json={"description": "   "},
    )

    assert response.status_code == 200
    assert response.json["data"]["description"] is None


@pytest.mark.parametrize(
    ("payload", "expected_error"),
    [
        (None, "A JSON object is required."),
        ({}, "At least one transaction field is required."),
        (
            {"category_type": "income"},
            (
                "Only amount, transaction_date, description, and "
                "category_id can be updated."
            ),
        ),
        ({"amount": True}, "amount must be a valid decimal value."),
        ({"amount": "0"}, "amount must be greater than 0."),
        (
            {"transaction_date": "not a date"},
            "transaction_date must have the format YYYY-MM-DD.",
        ),
        ({"category_id": 0}, "category_id must be a positive integer."),
        ({"description": 7}, "description must be a string."),
    ],
)
def test_rejects_invalid_transaction_updates(
    client, transactions, payload, expected_error
):
    transaction = transactions["meal"]

    response = client.patch(
        f"/api/transactions/{transaction.id}",
        json=payload,
    )

    assert response.status_code == 400
    assert response.json == {"error": expected_error}


def test_rejects_unknown_category_when_updating(
    client, transactions, categories
):
    transaction = transactions["meal"]

    response = client.patch(
        f"/api/transactions/{transaction.id}",
        json={"category_id": 999999},
    )

    assert response.status_code == 404
    assert response.json == {
        "error": "The selected category does not exist."
    }


@pytest.mark.parametrize("method", ["patch", "delete"])
def test_returns_not_found_for_unknown_transaction(client, method):
    request_method = getattr(client, method)

    response = request_method(
        "/api/transactions/999999",
        json={} if method == "patch" else None,
    )

    assert response.status_code == 404
    assert response.json == {"error": "Transaction not found."}
```

The final parameterised test uses `getattr` to select either `client.patch` or
`client.delete`. The route looks up the transaction before reading a PATCH body,
so an unknown ID consistently produces `404`.

Add the atomic-behaviour test from Part 5 as well. Then run every test:

```sh
pytest
pytest --cov=app --cov-report=term-missing --cov-fail-under=90
```

## Part 7: manually try the endpoints

Automated tests are the main verification, but one manual request helps connect
the code to the running service. Start Flask and list the existing transactions:

```sh
cd ~/finance-app/backend
source .venv/bin/activate
FLASK_DEBUG=0 flask --app run run --host 0.0.0.0 --port 5001
```

In another terminal, find an ID and update it:

```sh
curl http://127.0.0.1:5001/api/transactions

curl -i -X PATCH http://127.0.0.1:5001/api/transactions/1 \
  -H 'Content-Type: application/json' \
  -d '{"description":"Corrected description"}'
```

Use an ID that you are happy to remove when trying DELETE against your
development database:

```sh
curl -i -X DELETE http://127.0.0.1:5001/api/transactions/1
```

Unlike the test database, this deletion is permanent. Check the ID carefully
before running the command.

## Categories remain immutable

Do not add either of these routes:

```text
PATCH  /api/categories/<id>
DELETE /api/categories/<id>
```

Transactions refer to categories through a foreign key. Renaming, changing the
type of, or deleting a category could silently alter the meaning of historical
transactions. This project's API therefore treats categories as stable
reference data.

New categories can still be created when required. If the application later
needs to hide an obsolete category, adding an `active` flag would preserve
historical meaning more safely than changing or deleting it. That is outside
this tutorial.

## Commit the milestone

Review the changes and run the suite one final time:

```sh
cd ~/finance-app/backend
pytest

cd ~/finance-app
git status --short
git diff
git add backend/app/routes.py backend/tests/test_transactions.py \
  backend/docs/04-transaction-update-delete-tutorial.md
git commit -m "Add transaction update and delete endpoints"
git push -u origin add-transaction-update-delete
```

You now have a transaction API that can create, list, update, and delete records,
while categories remain stable reference data. More importantly, each new
behaviour is protected by an automated test.
