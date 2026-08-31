# Tutorial 5: filter and paginate transactions

The transaction API can now create, list, update, and delete transactions. In
this tutorial you will make the list endpoint more useful by adding composable
filters and pagination:

```text
GET /api/transactions
    ?type=spending
    &category_id=2
    &start_date=2026-08-01
    &end_date=2026-08-31
    &search=rent
    &page=1
    &per_page=20
```

The API will perform the filtering in the database and return only one page of
matching transactions. This gives callers the raw records they need without
introducing a separate reporting endpoint.

Allow about one hour:

| Activity | Time |
| --- | ---: |
| Understand filtering and pagination | 10 minutes |
| Write filtering tests | 15 minutes |
| Implement composable filters | 15 minutes |
| Write and implement pagination | 15 minutes |
| Validate edge cases and run coverage | 5 minutes |

## What we are building

The existing `type` filter remains supported. The complete list of query
parameters will be:

| Parameter | Meaning | Example |
| --- | --- | --- |
| `type` | Category type | `spending` |
| `category_id` | One exact category | `2` |
| `start_date` | Earliest date, inclusive | `2026-08-01` |
| `end_date` | Latest date, inclusive | `2026-08-31` |
| `search` | Text within the description | `rent` |
| `page` | Page number, starting at 1 | `1` |
| `per_page` | Results per page, from 1 to 100 | `20` |

All filters are optional and can be combined. For example, this asks for Food
transactions in August whose descriptions contain `restaurant`:

```text
GET /api/transactions?category_id=2&start_date=2026-08-01&end_date=2026-08-31&search=restaurant
```

Filters use AND logic: a transaction must satisfy every supplied filter.

## The response shape

The endpoint currently returns only `data`. It will now return `data` plus
pagination metadata:

```json
{
  "data": [
    {
      "id": 3,
      "amount": "1000.00",
      "transaction_date": "2026-08-03",
      "description": "Rent for August",
      "category_id": 3,
      "category": {
        "id": 3,
        "description": "Rent",
        "category_type": "spending"
      }
    }
  ],
  "pagination": {
    "page": 1,
    "per_page": 20,
    "total_items": 1,
    "total_pages": 1,
    "has_next": false,
    "has_previous": false
  }
}
```

`total_items` counts records after filtering, not all transactions in the
database. A frontend can use the other values to enable and disable its Previous
and Next buttons.

Adding the `pagination` member is backward-compatible for callers that read the
existing `data` member. However, the endpoint will now return at most 20 records
unless the caller requests a different `per_page` value.

## Before you start

Complete Tutorial 4 and make sure its full test suite passes. Then create a
branch:

```sh
cd ~/finance-app
git switch -c add-transaction-filtering-pagination
cd backend
source .venv/bin/activate
pytest
```

The examples in this tutorial match the route modules created during Tutorial
4. You will work in:

```text
backend/app/routes/transactions.py
backend/tests/test_transactions.py
```

You do not need to start Flask or MariaDB while running the automated tests.

## Part 1: filtering happens before `.all()`

SQLAlchemy builds a query one step at a time. No rows are fetched by these
statements:

```python
query = Transaction.query
query = query.filter(Transaction.category_id == category_id)
query = query.filter(Transaction.transaction_date >= start_date)
```

The query runs only when an operation such as `.all()` or `.paginate()` asks for
results. This means optional filters can be added independently before one final
database query is executed.

The transaction ordering remains:

```text
newest transaction date first
then highest ID first when dates are equal
```

A stable order is essential for pagination. Without a deterministic order, a
record could appear on two pages or move between pages unpredictably.

## Part 2: write the first filtering tests

The existing `transactions` fixture contains:

| Fixture key | Date | Type | Category | Description |
| --- | --- | --- | --- | --- |
| `rent` | 2026-08-03 | spending | Rent | Rent for August |
| `meal` | 2026-08-02 | spending | Food | Dinner at the restaurant |
| `income` | 2026-08-01 | income | Salary | August Income |

Add these tests to `backend/tests/test_transactions.py`:

```python
def test_filters_transactions_by_category(client, categories, transactions):
    response = client.get(
        f"/api/transactions?category_id={categories['food'].id}"
    )

    assert response.status_code == 200
    data = response.json["data"]
    assert [item["id"] for item in data] == [transactions["meal"].id]


def test_filters_transactions_by_inclusive_date_range(client, transactions):
    response = client.get(
        "/api/transactions?start_date=2026-08-02&end_date=2026-08-03"
    )

    assert response.status_code == 200
    data = response.json["data"]
    assert [item["id"] for item in data] == [
        transactions["rent"].id,
        transactions["meal"].id,
    ]


def test_searches_transaction_descriptions(client, transactions):
    response = client.get("/api/transactions?search=RESTAURANT")

    assert response.status_code == 200
    data = response.json["data"]
    assert [item["id"] for item in data] == [transactions["meal"].id]
```

The uppercase search proves that matching is case-insensitive. The date test
proves that both boundaries are included.

Run only the new tests:

```sh
pytest -v tests/test_transactions.py \
  -k 'filters_transactions or searches_transaction'
```

They should fail because the current endpoint ignores these parameters and
returns all three transactions. This is the red stage.

## Part 3: parse query parameters safely

Values from a URL query string are always strings. Even this request supplies
the characters `2`, not a Python integer:

```text
GET /api/transactions?category_id=2
```

Add these constants below the imports in
`backend/app/routes/transactions.py`:

```python
TRANSACTION_QUERY_PARAMETERS = {
    "type",
    "category_id",
    "start_date",
    "end_date",
    "search",
    "page",
    "per_page",
}

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100
```

Then add two parsing helpers above `list_transactions`:

```python
def extract_positive_query_integer(name, default=None):
    raw_value = request.args.get(name)
    if raw_value is None:
        return default

    try:
        value = int(raw_value)
    except ValueError:
        raise ValueError(f"{name} must be a positive integer.")

    if value <= 0:
        raise ValueError(f"{name} must be a positive integer.")

    return value


def extract_query_date(name):
    raw_value = request.args.get(name)
    if raw_value is None:
        return None

    try:
        return date.fromisoformat(raw_value)
    except ValueError:
        raise ValueError(f"{name} must have the format YYYY-MM-DD.")
```

These helpers raise `ValueError` with a caller-friendly message. The route will
catch the error and turn it into a `400 Bad Request` response.

Unlike transaction creation, a filter date may be in the future. A caller may
legitimately ask for an empty future range, and doing so does not save invalid
data.

## Part 4: implement the filters

Replace the existing `list_transactions` function with this version. Pagination
is added in Part 6; for now the final query still uses `.all()`.

```python
@api.get("/transactions")
def list_transactions():
    unknown_parameters = set(request.args) - TRANSACTION_QUERY_PARAMETERS
    if unknown_parameters:
        name = sorted(unknown_parameters)[0]
        return jsonify({"error": f"Unknown query parameter: {name}."}), 400

    category_type = request.args.get("type")
    if category_type is not None and category_type not in CATEGORY_TYPES:
        return jsonify(
            {"error": "category_type must be income or spending."}
        ), 400

    try:
        category_id = extract_positive_query_integer("category_id")
        start_date = extract_query_date("start_date")
        end_date = extract_query_date("end_date")
    except ValueError as error:
        return jsonify({"error": str(error)}), 400

    if start_date is not None and end_date is not None and start_date > end_date:
        return jsonify(
            {"error": "start_date cannot be after end_date."}
        ), 400

    search = request.args.get("search")
    if search is not None:
        search = search.strip()
        if not search:
            return jsonify({"error": "search cannot be blank."}), 400

    query = Transaction.query

    if category_type is not None:
        query = query.join(Category).filter(
            Category.category_type == category_type
        )

    if category_id is not None:
        query = query.filter(Transaction.category_id == category_id)

    if start_date is not None:
        query = query.filter(Transaction.transaction_date >= start_date)

    if end_date is not None:
        query = query.filter(Transaction.transaction_date <= end_date)

    if search is not None:
        query = query.filter(Transaction.description.ilike(f"%{search}%"))

    query = query.order_by(
        Transaction.transaction_date.desc(),
        Transaction.id.desc(),
    )

    transactions = query.all()
    return jsonify(
        {"data": [transaction.to_dict() for transaction in transactions]}
    ), 200
```

Important details:

- Subtracting the allowed set from `set(request.args)` finds misspelled or
  unsupported parameters. Sorting makes the reported error deterministic.
- `>=` and `<=` make the date boundaries inclusive.
- `ilike` performs a case-insensitive text match.
- A transaction with a `NULL` description simply does not match a search.
- Filtering by a valid but unused `category_id` returns an empty list. The
  category itself does not need to exist for a list filter.
- The `%` characters mean “any text before or after this value” in SQL pattern
  matching. SQLAlchemy passes the value to the database as a parameter rather
  than constructing raw SQL.

Run the new tests and then the entire suite:

```sh
pytest -v tests/test_transactions.py \
  -k 'filters_transactions or searches_transaction'
pytest
```

## Part 5: prove that filters compose

A separate endpoint for every combination would quickly become unmanageable.
Because the route adds filters to one query, the existing parameters naturally
compose.

Add this test:

```python
def test_combines_transaction_filters(client, transactions):
    response = client.get(
        "/api/transactions"
        "?type=spending"
        "&start_date=2026-08-02"
        "&end_date=2026-08-03"
        "&search=rent"
    )

    assert response.status_code == 200
    data = response.json["data"]
    assert [item["id"] for item in data] == [transactions["rent"].id]
```

Python joins adjacent string literals, so the four short strings form one URL.
The request starts with two spending transactions, and the search reduces the
result to the Rent transaction.

## Part 6: write the pagination test

Use a small page size against the existing three records:

```python
def test_paginates_transactions(client, transactions):
    first_response = client.get("/api/transactions?page=1&per_page=2")

    assert first_response.status_code == 200
    assert [item["id"] for item in first_response.json["data"]] == [
        transactions["rent"].id,
        transactions["meal"].id,
    ]
    assert first_response.json["pagination"] == {
        "page": 1,
        "per_page": 2,
        "total_items": 3,
        "total_pages": 2,
        "has_next": True,
        "has_previous": False,
    }

    second_response = client.get("/api/transactions?page=2&per_page=2")

    assert second_response.status_code == 200
    assert [item["id"] for item in second_response.json["data"]] == [
        transactions["income"].id,
    ]
    assert second_response.json["pagination"]["has_next"] is False
    assert second_response.json["pagination"]["has_previous"] is True
```

Run it and see it fail:

```sh
pytest -v tests/test_transactions.py::test_paginates_transactions
```

## Part 7: implement pagination

Inside `list_transactions`, extend the existing parsing `try` block:

```python
    try:
        category_id = extract_positive_query_integer("category_id")
        start_date = extract_query_date("start_date")
        end_date = extract_query_date("end_date")
        page = extract_positive_query_integer("page", default=1)
        per_page = extract_positive_query_integer(
            "per_page",
            default=DEFAULT_PAGE_SIZE,
        )
    except ValueError as error:
        return jsonify({"error": str(error)}), 400

    if per_page > MAX_PAGE_SIZE:
        return jsonify(
            {"error": f"per_page cannot exceed {MAX_PAGE_SIZE}."}
        ), 400
```

At the end of the route, replace `.all()` and the existing return statement:

```python
    pagination = query.paginate(
        page=page,
        per_page=per_page,
        error_out=False,
    )

    return jsonify(
        {
            "data": [transaction.to_dict() for transaction in pagination.items],
            "pagination": {
                "page": pagination.page,
                "per_page": pagination.per_page,
                "total_items": pagination.total,
                "total_pages": pagination.pages,
                "has_next": pagination.has_next,
                "has_previous": pagination.has_prev,
            },
        }
    ), 200
```

`paginate` runs two database queries: one obtains the requested rows using
`LIMIT` and `OFFSET`, and one counts all matching rows for the metadata. It does
not load every matching transaction into Python.

`error_out=False` means that requesting a page beyond the last page returns
`200 OK` with an empty `data` list. This is convenient when records might be
deleted while a user is paging through them.

Run the focused test and then all transaction tests:

```sh
pytest -v tests/test_transactions.py::test_paginates_transactions
pytest -v tests/test_transactions.py
```

Existing tests access `response.json["data"]`, so the additional `pagination`
member should not break them.

## Part 8: your validation exercise

Add parameterised tests for these invalid requests. Check both the `400` status
and the exact JSON error.

| Query string | Expected error |
| --- | --- |
| `category_id=abc` | `category_id must be a positive integer.` |
| `category_id=0` | `category_id must be a positive integer.` |
| `start_date=01-08-2026` | `start_date must have the format YYYY-MM-DD.` |
| `end_date=tomorrow` | `end_date must have the format YYYY-MM-DD.` |
| `start_date=2026-08-03&end_date=2026-08-01` | `start_date cannot be after end_date.` |
| `search=` | `search cannot be blank.` |
| `page=0` | `page must be a positive integer.` |
| `page=one` | `page must be a positive integer.` |
| `per_page=0` | `per_page must be a positive integer.` |
| `per_page=101` | `per_page cannot exceed 100.` |
| `sort=date` | `Unknown query parameter: sort.` |

Also test these successful edge cases:

1. With no pagination parameters, the response reports page 1 and 20 per page.
2. A page after the final page returns `200` and an empty `data` list.
3. Filters affect `total_items` and `total_pages`.
4. A valid but nonexistent category ID returns `200` and no results.

Try the exercise before comparing your work with the reference solution below.

## Part 9: reference validation tests

```python
@pytest.mark.parametrize(
    ("query_string", "expected_error"),
    [
        ("category_id=abc", "category_id must be a positive integer."),
        ("category_id=0", "category_id must be a positive integer."),
        (
            "start_date=01-08-2026",
            "start_date must have the format YYYY-MM-DD.",
        ),
        (
            "end_date=tomorrow",
            "end_date must have the format YYYY-MM-DD.",
        ),
        (
            "start_date=2026-08-03&end_date=2026-08-01",
            "start_date cannot be after end_date.",
        ),
        ("search=", "search cannot be blank."),
        ("page=0", "page must be a positive integer."),
        ("page=one", "page must be a positive integer."),
        ("per_page=0", "per_page must be a positive integer."),
        ("per_page=101", "per_page cannot exceed 100."),
        ("sort=date", "Unknown query parameter: sort."),
    ],
)
def test_rejects_invalid_transaction_query_parameters(
    client, query_string, expected_error
):
    response = client.get(f"/api/transactions?{query_string}")

    assert response.status_code == 400
    assert response.json == {"error": expected_error}


def test_uses_default_pagination(client, transactions):
    response = client.get("/api/transactions")

    assert response.status_code == 200
    assert len(response.json["data"]) == 3
    assert response.json["pagination"] == {
        "page": 1,
        "per_page": 20,
        "total_items": 3,
        "total_pages": 1,
        "has_next": False,
        "has_previous": False,
    }


def test_returns_empty_data_for_page_after_last(client, transactions):
    response = client.get("/api/transactions?page=2")

    assert response.status_code == 200
    assert response.json["data"] == []
    assert response.json["pagination"]["page"] == 2
    assert response.json["pagination"]["total_items"] == 3


def test_paginates_filtered_transactions(client, transactions):
    response = client.get("/api/transactions?type=spending&per_page=1")

    assert response.status_code == 200
    assert [item["id"] for item in response.json["data"]] == [
        transactions["rent"].id
    ]
    assert response.json["pagination"]["total_items"] == 2
    assert response.json["pagination"]["total_pages"] == 2


def test_returns_empty_data_for_unused_category_id(client, transactions):
    response = client.get("/api/transactions?category_id=999999")

    assert response.status_code == 200
    assert response.json["data"] == []
    assert response.json["pagination"]["total_items"] == 0
```

Why does an unused category filter return `200`, while POST and PATCH return
`404` for an unknown category? Creating or changing a transaction requires a
real category. Filtering merely asks which transactions match a condition; zero
matches is a valid answer.

## Part 10: manually explore the endpoint

Run the complete automated suite first:

```sh
cd ~/finance-app/backend
source .venv/bin/activate
pytest
pytest --cov=app --cov-report=term-missing --cov-fail-under=90
```

Then start Flask if you want to try the development database:

```sh
FLASK_DEBUG=0 flask --app run run --host 0.0.0.0 --port 5001
```

In another terminal, try one parameter at a time:

```sh
curl 'http://127.0.0.1:5001/api/transactions?type=spending'

curl 'http://127.0.0.1:5001/api/transactions?start_date=2026-08-01&end_date=2026-08-31'

curl 'http://127.0.0.1:5001/api/transactions?search=rent'

curl 'http://127.0.0.1:5001/api/transactions?page=1&per_page=5'
```

Then combine them:

```sh
curl 'http://127.0.0.1:5001/api/transactions?type=spending&start_date=2026-08-01&end_date=2026-08-31&page=1&per_page=5'
```

Quotes around the URL prevent the shell from interpreting `&` as a command
separator.

## Optional challenge: inspect the generated SQL

The point of server-side filtering and pagination is to avoid loading every row.
To see the SQLAlchemy queries during development, temporarily enable SQL output
in Flask's configuration:

```python
SQLALCHEMY_ECHO = True
```

Make one filtered request and look for SQL containing `WHERE`, `ORDER BY`,
`LIMIT`, and `OFFSET`. Remove or disable the setting afterwards because SQL logs
become noisy and may reveal application data.

## Commit the milestone

Review the changes and run the suite one final time:

```sh
cd ~/finance-app/backend
pytest

cd ~/finance-app
git status --short
git diff
git add backend/app/routes/transactions.py \
  backend/tests/test_transactions.py \
  backend/docs/05-transaction-filtering-pagination-tutorial.md
git commit -m "Add transaction filtering and pagination"
git push -u origin add-transaction-filtering-pagination
```

The list endpoint can now answer focused questions by category, type, date, and
description while returning predictable, bounded pages. The same filters can be
combined without creating specialised reporting routes.
