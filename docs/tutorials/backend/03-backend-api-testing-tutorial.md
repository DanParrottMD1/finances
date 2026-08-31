# Tutorial 3: unit test the backend API with pytest

In the first two tutorials you tested the API manually with `curl`. In this tutorial Python will make those requests and check the results automatically.

You will learn the concepts, study two small examples, and then write a scoped set of tests yourself. A complete reference solution appears only after the exercise, so resist scrolling to it until you have made a genuine attempt.

Allow about one hour:

| Activity | Time |
| --- | ---: |
| Learn the core concepts | 10 minutes |
| Prepare the isolated test environment | 10 minutes |
| Study the examples | 5 minutes |
| Complete the exercise | 25 minutes |
| Compare, fix, and measure coverage | 10 minutes |

## What kind of tests are these?

The tests call a real Flask route, run its validation, use SQLAlchemy, and inspect the JSON response. They are often called API unit tests, though *small integration tests* is more precise because several backend pieces work together.

They still run quickly and locally:

```text
pytest -> Flask test client -> route -> temporary SQLite database
```

The development server and MariaDB are not involved. This prevents tests from changing your real finance data and makes the result repeatable.

## Part 1: understand the core concepts

### A test is a small story

Most tests have three stages:

```text
Arrange -> Act -> Assert
```

- **Arrange:** prepare the data and conditions the behaviour needs.
- **Act:** perform the behaviour, such as sending an HTTP request.
- **Assert:** state what result you expect.

Here is a deliberately simple example:

```python
def test_addition():
    first_number = 2
    second_number = 3

    result = first_number + second_number

    assert result == 5
```

What the syntax means:

- `def` defines a function.
- Pytest discovers functions whose names start with `test_`.
- `()` contains function inputs. This example has none.
- `:` begins the indented body of the function.
- `=` assigns a value to a name.
- `assert` requires the following expression to be true.
- `==` compares two values. A single `=` assigns; a double `==` compares.

Good tests check one behaviour or one closely related story. Their names should say what ought to happen, not how the code happens to work.

### Flask's test client

Flask provides a test client that behaves like an API caller without opening a network connection:

```python
response = client.get("/api/health")
```

Useful response properties are:

```python
response.status_code
response.get_json()
```

The first is the HTTP status number. The second converts JSON into ordinary Python dictionaries and lists. For POST requests, the `json` keyword converts a Python value to JSON and supplies the correct content type:

```python
response = client.post(
    "/api/categories",
    json={"description": "Salary", "category_type": "income"},
)
```

`{...}` creates a dictionary. Each entry is a `key: value` pair. Commas separate arguments or entries, and the closing parenthesis ends the method call.

### Fixtures remove repeated setup

A *fixture* prepares something that several tests need. A test requests one by using its name as a function parameter:

```python
def test_something(client):
    # pytest supplies the client fixture
```

The fixture itself uses a decorator:

```python
@pytest.fixture()
def client(app):
    return app.test_client()
```

- `@pytest.fixture()` tells pytest that the next function is a fixture.
- `client(app)` means the client fixture depends on the app fixture.
- `return` sends the created value back to the test.
- The dot in `app.test_client()` accesses a method belonging to `app`.

### Parameterisation checks several related cases

Validation has many inputs that should produce the same status. Copying a whole test for each input makes the suite hard to read. Pytest can run one function with several sets of values:

```python
@pytest.mark.parametrize(
    ("value", "expected"),
    [(1, True), (0, False), (-1, False)],
)
def test_positive_number(value, expected):
    assert (value > 0) == expected
```

The outer list `[...]` holds three cases. Each inner tuple `(...)` supplies the `value` and `expected` parameters for one run. Pytest reports each separately.

### Isolation and coverage

Tests must not depend on their execution order. Our application fixture creates a new in-memory database before every test and drops it afterwards, so data cannot leak from one test into another.

Statement coverage measures which application lines ran. It helps find forgotten branches, but 100% coverage does not prove the assertions are useful. For this small backend, aim for at least 90% while checking status codes, response fields, filtering, ordering, and validation errors.

## Part 2: prepare the test environment

This section is test infrastructure rather than the exercise. Copy this setup so you can spend your time designing tests.

```sh
cd ~/finance-app
git switch -c add-backend-api-tests
cd backend
source .venv/bin/activate
```

Create `backend/requirements-dev.txt`:

```text
-r requirements.txt
pytest>=8.0,<9.0
pytest-cov>=7.0,<8.0
```

Install it with `python -m pip install -r requirements-dev.txt`. Pytest 8 is used because this project's virtual environment currently uses Python 3.9.

Add the generated coverage files to the `# Python` section of `.gitignore`:

```text
.coverage
htmlcov/
```

### Allow test configuration

Tests need to replace the MariaDB address with an in-memory SQLite address. In `backend/app/__init__.py`, let the application factory accept optional settings:

```python
def create_app(test_config=None):
    """Create and configure the Flask application."""
    app = Flask(__name__)
    app.config.from_object(Config)

    if test_config is not None:
        app.config.update(test_config)
```

Keep the remainder of `create_app` unchanged. `=None` makes the argument optional, so normal use is unaffected. `is not None` checks whether settings were supplied.

### Make the model portable to SQLite

MariaDB auto-increments `BIGINT`, while SQLite needs the type name `INTEGER` for this behaviour. Near the top of `backend/app/models.py`, add:

```python
id_type = db.BigInteger().with_variant(db.Integer, "sqlite")
```

Use `id_type` instead of `db.BigInteger` for both model IDs and for `Transaction.category_id`. MariaDB still uses `BIGINT`; only SQLite gets the variant.

Represent the schema's category uniqueness rule inside `Category`, directly below `__tablename__`:

```python
__table_args__ = (
    db.UniqueConstraint("description", "category_type"),
)
```

The trailing comma makes this a one-item tuple. SQLAlchemy can now recreate the real constraint in the temporary database.

### Add the fixtures

From `backend`, run `mkdir tests`, then create `backend/tests/conftest.py`:

```python
import pytest

from app import create_app
from app.extensions import db
from app.models import Category


@pytest.fixture()
def app():
    test_app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        }
    )

    with test_app.app_context():
        db.create_all()
        yield test_app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def categories(app):
    income = Category(description="Salary", category_type="income")
    spending = Category(description="Groceries", category_type="spending")
    db.session.add_all([income, spending])
    db.session.commit()
    return {"income": income, "spending": spending}
```

Important syntax:

- `with test_app.app_context():` makes this Flask application active.
- `yield test_app` supplies the app and pauses the fixture. After the test, execution resumes with the cleanup lines.
- `db.create_all()` builds the SQLite tables; `db.drop_all()` removes them.
- `[income, spending]` is a list passed to `add_all`.
- The final dictionary allows readable expressions such as `categories["income"].id`.

### Tell pytest where the app lives

Pytest 8 does not put the current directory on Python's import path by default. Without extra configuration, `from app import create_app` in `conftest.py` fails with `ModuleNotFoundError: No module named 'app'`.

Create `backend/pytest.ini`:

```ini
[pytest]
pythonpath = .
testpaths = tests
```

- `pythonpath = .` adds the `backend` directory to the import path, so `app` can be imported.
- `testpaths = tests` limits collection to the tests directory.
- `.` means the directory that contains `pytest.ini`.

Run pytest from `backend` so this file is found.

## How to run pytest

From the `backend` directory:

```sh
cd ~/finance-app/backend
source .venv/bin/activate
pytest
```

You do not need to start Flask or MariaDB first. The Flask test client and temporary SQLite database are created by the fixtures.

The `pytest` command searches for files named `test_*.py`, then runs functions inside them whose names begin with `test_`. A successful run ends with output similar to:

```text
========================= 29 passed in 0.20s =========================
```

A dot represents a passing test and `F` represents a failure. When a test fails, pytest shows its name, the failed assertion, and the actual and expected values.

These commands are useful while working through the tutorial:

```sh
# Show the name and result of every test case
pytest -v

# Run one test file
pytest -v tests/test_categories.py

# Run one test function from one file
pytest -v tests/test_categories.py::test_health_check

# Stop as soon as the first test fails
pytest -x

# Run the suite and measure application coverage
pytest --cov=app --cov-report=term-missing
```

Text after `#` is a shell comment explaining a command; the shell does not execute it. The `::` syntax selects one test function. `-v` means verbose and `-x` means exit on the first failure.

After changing application or test code, save the file and run the relevant command again. There is no test process to restart: each command starts a fresh run and then exits. Use a single-file command for quick feedback during the exercise, then run plain `pytest` before finishing to ensure the complete suite still passes.

## Part 3: study two small examples

Create `backend/tests/test_categories.py`. First, test the health endpoint:

```python
def test_health_check(client):
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}
```

The fixture does the arrangement, the GET is the action, and the two assertions check the response.

The second example creates one category:

```python
def test_creates_a_category(client):
    response = client.post(
        "/api/categories",
        json={"description": "  Salary  ", "category_type": "income"},
    )

    assert response.status_code == 201
    data = response.get_json()["data"]
    assert data["description"] == "Salary"
    assert data["category_type"] == "income"
```

This verifies that surrounding spaces are removed as well as checking that the request worked. Run both examples with `pytest -v tests/test_categories.py`.

## Part 4: your exercise

Spend up to 25 minutes here before reading the solution. You do not need to test database outages or mock any objects.

### Exercise A: categories

Continue in `test_categories.py`:

1. Create income and spending categories through the API.
2. GET all categories and assert both descriptions are in documented order.
3. Filter with `?type=spending` and assert only the spending row remains.
4. Write one parameterised test for non-object JSON, missing or numeric descriptions, a blank description, a 101-character description, and an unknown category type. Check both the `400` and exact error message.
5. Check that the second creation of an identical category returns `409`.
6. Check that `?type=unknown` returns `400`.

Hint—a list comprehension can extract descriptions:

```python
descriptions = [item["description"] for item in data]
```

### Exercise B: transaction behaviour

Create `backend/tests/test_transactions.py`:

1. Request the `client` and `categories` fixtures.
2. POST a spending transaction dated `2024-02-20` and an income transaction dated `2024-02-01`.
3. Assert the successful status, exact string amount, and nested category type.
4. GET all transactions and prove the newest appears first.
5. Filter with `?type=income` and prove only the income row remains.

Fixed past dates keep the tests valid next year.

### Exercise C: transaction validation

Write one parameterised test. Begin with a valid transaction dictionary, replace one field per case, then assert the `400` and error message.

| Field | Invalid values |
| --- | --- |
| amount | `None`, `True`, `"lots"`, `"0"`, `"1.234"`, `"100000000"` |
| transaction_date | `None`, `"20-02-2024"`, `"2999-01-01"` |
| category_id | `True`, `0` |
| description | `7`, a 256-character string |

Also test a non-object body, an unknown category ID, a blank optional description becoming JSON `null`, and an unknown transaction type filter.

Hint:

```python
payload = {
    # valid fields
}
payload.update(changes)
```

`update` replaces only the field supplied by the current case, allowing the request to reach the intended validation branch.

### Exercise D: interpret the failures

Run `pytest -v`. If your tests represent the schema and API rules correctly, expect three transaction failures. Investigate before changing the application:

- Why might Python accept `True` where an integer is required?
- What is the greatest value a `DECIMAL(10, 2)` can hold?
- Does the model agree with the schema that descriptions are optional?

Make the smallest application fix for each behaviour, then rerun the suite.

Before viewing the solution, check that you used descriptive names, asserted response content as well as statuses, parameterised repeated cases, saw the three expected failures, and attempted focused fixes.

## Part 5: ideal solution

This is one good solution, not the only valid one. Compare behaviour and clarity rather than trying to make every variable name identical.

### Category exercise solution

Keep the two worked examples and add this import and these tests:

```python
import pytest


def test_lists_and_filters_categories(client):
    client.post(
        "/api/categories",
        json={"description": "Salary", "category_type": "income"},
    )
    client.post(
        "/api/categories",
        json={"description": "Groceries", "category_type": "spending"},
    )

    response = client.get("/api/categories")
    data = response.get_json()["data"]
    assert [item["description"] for item in data] == ["Salary", "Groceries"]

    response = client.get("/api/categories?type=spending")
    data = response.get_json()["data"]
    assert len(data) == 1
    assert data[0]["category_type"] == "spending"


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        (None, "A JSON object is required."),
        ({}, "description must be a string."),
        ({"description": 7}, "description must be a string."),
        ({"description": "   "}, "description cannot be blank."),
        (
            {"description": "x" * 101, "category_type": "income"},
            "description cannot exceed 100 characters.",
        ),
        (
            {"description": "Other", "category_type": "unknown"},
            "category_type must be income or spending.",
        ),
    ],
)
def test_rejects_invalid_categories(client, payload, message):
    response = client.post("/api/categories", json=payload)
    assert response.status_code == 400
    assert response.get_json() == {"error": message}


def test_rejects_duplicate_category(client):
    payload = {"description": "Salary", "category_type": "income"}
    assert client.post("/api/categories", json=payload).status_code == 201

    response = client.post("/api/categories", json=payload)
    assert response.status_code == 409


def test_rejects_invalid_category_filter(client):
    response = client.get("/api/categories?type=unknown")
    assert response.status_code == 400
```

### Transaction exercise solution

```python
import pytest


def test_creates_lists_and_filters_transactions(client, categories):
    spending_response = client.post(
        "/api/transactions",
        json={
            "amount": "42.75",
            "transaction_date": "2024-02-20",
            "description": "Weekly shop",
            "category_id": categories["spending"].id,
        },
    )
    income_response = client.post(
        "/api/transactions",
        json={
            "amount": "2500.00",
            "transaction_date": "2024-02-01",
            "description": "February salary",
            "category_id": categories["income"].id,
        },
    )

    assert spending_response.status_code == 201
    spending_data = spending_response.get_json()["data"]
    assert spending_data["amount"] == "42.75"
    assert spending_data["category"]["category_type"] == "spending"
    assert income_response.status_code == 201

    response = client.get("/api/transactions")
    data = response.get_json()["data"]
    assert [item["description"] for item in data] == [
        "Weekly shop",
        "February salary",
    ]

    response = client.get("/api/transactions?type=income")
    data = response.get_json()["data"]
    assert len(data) == 1
    assert data[0]["category"]["category_type"] == "income"


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"amount": None}, "amount is required."),
        ({"amount": True}, "amount is required."),
        ({"amount": "lots"}, "amount must be a valid decimal value."),
        ({"amount": "0"}, "amount must be greater than 0."),
        ({"amount": "1.234"}, "amount must have at most 2 decimal places."),
        ({"amount": "100000000"}, "amount is too large."),
        ({"transaction_date": None}, "transaction_date must have the format YYYY-MM-DD."),
        ({"transaction_date": "20-02-2024"}, "transaction_date must have the format YYYY-MM-DD."),
        ({"transaction_date": "2999-01-01"}, "transaction_date cannot be in the future."),
        ({"category_id": True}, "category_id must be a positive integer."),
        ({"category_id": 0}, "category_id must be a positive integer."),
        ({"description": 7}, "description must be a string."),
        ({"description": "x" * 256}, "description cannot exceed 255 characters."),
    ],
)
def test_rejects_invalid_transactions(client, categories, changes, message):
    payload = {
        "amount": "10.00",
        "transaction_date": "2024-02-20",
        "description": "Test transaction",
        "category_id": categories["income"].id,
    }
    payload.update(changes)

    response = client.post("/api/transactions", json=payload)
    assert response.status_code == 400
    assert response.get_json() == {"error": message}


def test_accepts_a_blank_optional_description(client, categories):
    response = client.post(
        "/api/transactions",
        json={
            "amount": "10.00",
            "transaction_date": "2024-02-20",
            "description": "   ",
            "category_id": categories["income"].id,
        },
    )
    assert response.status_code == 201
    assert response.get_json()["data"]["description"] is None


def test_rejects_a_non_object_transaction(client):
    response = client.post("/api/transactions", json=None)
    assert response.status_code == 400
    assert response.get_json() == {"error": "A JSON object is required."}


def test_rejects_an_unknown_category(client, categories):
    response = client.post(
        "/api/transactions",
        json={
            "amount": "10.00",
            "transaction_date": "2024-02-20",
            "category_id": 999999,
        },
    )
    assert response.status_code == 404


def test_rejects_invalid_transaction_filter(client):
    response = client.get("/api/transactions?type=unknown")
    assert response.status_code == 400
```

### Application fixes revealed by the tests

Make the optional model field agree with `database/schema.sql`:

```python
description = db.Column(db.String(255))
```

Serialise money explicitly in `Transaction.to_dict`:

```python
"amount": str(self.amount),
```

Reject a Boolean category ID. Python's `bool` is a subclass of `int`, so the explicit first check matters:

```python
if isinstance(category_id, bool) or not isinstance(category_id, int) or category_id <= 0:
    return jsonify({"error": "category_id must be a positive integer."}), 400
```

Finally, align the limit with `DECIMAL(10, 2)`. Ten total digits minus two decimal digits leaves eight before the decimal point:

```python
if amount > Decimal("99999999.99"):
    return jsonify({"error": "amount is too large."}), 400
```

Run the suite again. Moving from failing to passing tests is the red–green part of the common cycle:

```text
red (fail) -> green (pass) -> refactor (improve safely)
```

## Part 6: measure coverage

From `backend`, run:

```sh
pytest --cov=app --cov-report=term-missing --cov-fail-under=90
```

- `--cov=app` measures the application package rather than the tests.
- `--cov-report=term-missing` prints application lines that did not run.
- `--cov-fail-under=90` makes the command fail below 90% total coverage.

The reference solution contains 29 cases after parameterisation and reaches about 96% statement coverage. The main uncovered paths simulate database outages; mocking those failures is useful later but outside this one-hour lesson.

## Commit the milestone

```sh
cd ~/finance-app
git status --short
git diff
git add .gitignore backend/app/__init__.py backend/app/models.py \
  backend/app/routes.py backend/requirements-dev.txt backend/tests \
  backend/docs/03-backend-api-testing-tutorial.md
git commit -m "Add backend API tests"
git push -u origin add-backend-api-tests
```

For each future endpoint, identify its successful story, boundaries, and expected failures; arrange only the data it needs; make the request; and assert the response that callers rely on.
