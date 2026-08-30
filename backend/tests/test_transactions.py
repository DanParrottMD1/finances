from datetime import date, timedelta

import pytest
from app.extensions import db
from app.models import Category, Transaction


def _assert_transaction(transaction: Transaction, data: dict):
    dict_transaction = transaction.to_dict()
    assert data["amount"] == str(dict_transaction["amount"])
    assert data["transaction_date"] == str(dict_transaction["transaction_date"])
    assert data["category_id"] == dict_transaction["category_id"]
    assert data["category"] == dict_transaction["category"]
    assert data["description"] == dict_transaction["description"]


def test_get_all_transactions(transactions: dict[str, Transaction], client):
    response = client.get("/api/transactions")

    assert response.status_code == 200
    data = response.json["data"]

    assert len(data) == 3

    _assert_transaction(transactions["rent"], data[0])
    _assert_transaction(transactions["meal"], data[1])
    _assert_transaction(transactions["income"], data[2])


def test_get_transactions_sorted_by_transaction_date(
    categories: dict[str, Category], client
):
    # First create two transactions
    response = client.post(
        "/api/transactions",
        json={
            "amount": "100.00",
            "transaction_date": "2026-08-01",
            "category_id": categories["food"].id,
            "description": "Test Transaction",
        },
    )
    assert response.status_code == 201
    response = client.post(
        "/api/transactions",
        json={
            "amount": "200.00",
            "transaction_date": "2026-08-02",
            "category_id": categories["income"].id,
            "description": "Test Transaction 2",
        },
    )
    assert response.status_code == 201

    response = client.get("/api/transactions")
    assert response.status_code == 200
    data = response.json["data"]
    assert len(data) == 2
    assert data[0]["transaction_date"] == "2026-08-02"
    assert data[1]["transaction_date"] == "2026-08-01"


def test_get_all_income_transactions(transactions: dict[str, Transaction], client):
    response = client.get("/api/transactions?type=income")

    assert response.status_code == 200
    data = response.json["data"]

    assert len(data) == 1

    _assert_transaction(transactions["income"], data[0])


def test_get_all_spending_transactions(transactions: dict[str, Transaction], client):
    response = client.get("/api/transactions?type=spending")

    assert response.status_code == 200
    data = response.json["data"]

    assert len(data) == 2

    _assert_transaction(transactions["rent"], data[0])
    _assert_transaction(transactions["meal"], data[1])


def test_get_invalid_transaction_type(client):
    response = client.get("/api/transactions?type=invalid")

    assert response.status_code == 400
    assert response.json == {"error": "category_type must be income or spending."}


def test_create_spending_transaction(categories: dict[str, Category], client):
    response = client.post(
        "/api/transactions",
        json={
            "amount": "100.00",
            "transaction_date": "2026-08-01",
            "category_id": categories["food"].id,
            "description": "Test Transaction",
        },
    )

    assert response.status_code == 201
    data = response.json["data"]

    assert data["amount"] == "100.00"
    assert data["transaction_date"] == "2026-08-01"
    assert data["category_id"] == categories["food"].id
    assert data["category"] == categories["food"].to_dict()
    assert data["description"] == "Test Transaction"


def test_create_income_transaction(categories: dict[str, Category], client):
    response = client.post(
        "/api/transactions",
        json={
            "amount": "100.00",
            "transaction_date": "2026-08-01",
            "category_id": categories["income"].id,
            "description": "Test Transaction",
        },
    )
    assert response.status_code == 201
    data = response.json["data"]

    assert data["amount"] == "100.00"
    assert data["transaction_date"] == "2026-08-01"
    assert data["category_id"] == categories["income"].id
    assert data["category"] == categories["income"].to_dict()
    assert data["description"] == "Test Transaction"


def test_create_transaction_with_missing_description(
    categories: dict[str, Category], client
):
    response = client.post(
        "/api/transactions",
        json={
            "amount": "100.00",
            "transaction_date": "2026-08-01",
            "category_id": categories["food"].id,
        },
    )
    assert response.status_code == 201
    data = response.json["data"]

    assert data["description"] is None


def test_create_transaction_with_empty_description(
    categories: dict[str, Category], client
):
    response = client.post(
        "/api/transactions",
        json={
            "amount": "100.00",
            "transaction_date": "2026-08-01",
            "category_id": categories["food"].id,
            "description": "   ",
        },
    )
    assert response.status_code == 201
    data = response.json["data"]

    assert data["description"] is None


def _valid_transaction() -> dict:
    return {
        "amount": "100.00",
        "transaction_date": "2026-08-01",
        "category_id": 1,
        "description": "Test Transaction",
    }


@pytest.mark.parametrize(
    ("payload", "expected_error"),
    [
        (None, "A JSON object is required."),
        (
            {k: v for k, v in _valid_transaction().items() if k != "amount"},
            "amount is required.",
        ),
        (
            _valid_transaction() | {"amount": "invalid"},
            "amount must be a valid decimal value.",
        ),
        (
            _valid_transaction() | {"amount": True},
            "amount must be a valid decimal value.",
        ),
        (
            _valid_transaction() | {"amount": "-100.00"},
            "amount must be greater than 0.",
        ),
        (_valid_transaction() | {"amount": "0"}, "amount must be greater than 0."),
        (
            _valid_transaction() | {"amount": "100.000"},
            "amount must have at most 2 decimal places.",
        ),
        (
            _valid_transaction() | {"amount": "100000000.00"},
            "amount too large.",
        ),
        (
            {k: v for k, v in _valid_transaction().items() if k != "transaction_date"},
            "transaction_date must have the format YYYY-MM-DD.",
        ),
        (
            _valid_transaction() | {"transaction_date": "not a date"},
            "transaction_date must have the format YYYY-MM-DD.",
        ),
        (
            _valid_transaction()
            | {"transaction_date": str(date.today() + timedelta(days=1))},
            "transaction_date cannot be in the future.",
        ),
        (
            {k: v for k, v in _valid_transaction().items() if k != "category_id"},
            "category_id is required.",
        ),
        (
            _valid_transaction() | {"category_id": True},
            "category_id must be a positive integer.",
        ),
        (
            _valid_transaction() | {"category_id": 0},
            "category_id must be a positive integer.",
        ),
        (
            _valid_transaction() | {"category_id": -1},
            "category_id must be a positive integer.",
        ),
        (_valid_transaction() | {"description": 99}, "description must be a string."),
        (
            _valid_transaction() | {"description": "x" * 256},
            "description cannot exceed 255 characters.",
        ),
    ],
)
def test_create_transaction_with_invalid_payload(
    categories: dict[str, Category], client, payload: dict, expected_error: str
):
    response = client.post(
        "/api/transactions",
        json=payload,
    )
    assert response.status_code == 400
    assert response.json == {"error": expected_error}


def test_create_transaction_with_invalid_category_id(
    categories: dict[str, Category], client
):
    response = client.post(
        "/api/transactions",
        json={**_valid_transaction(), "category_id": 99},
    )
    assert response.status_code == 404
    assert response.json == {"error": "The selected category does not exist."}


def test_update_transaction_description(client, transactions: dict[str, Transaction]):
    before = transactions["rent"]
    expected = Transaction(
        id=before.id,
        amount=before.amount,
        transaction_date=before.transaction_date,
        category_id=before.category_id,
        category=before.category,
        description="New Description",
    )

    response = client.patch(
        f"/api/transactions/{before.id}",
        json={"description": expected.description},
    )
    assert response.status_code == 200
    data = response.json["data"]

    _assert_transaction(expected, data)

    after = db.session.get(Transaction, before.id)
    _assert_transaction(expected, after.to_dict())


def test_update_transaction_with_empty_description(
    client, transactions: dict[str, Transaction]
):
    before = transactions["rent"]
    expected = Transaction(
        id=before.id,
        amount=before.amount,
        transaction_date=before.transaction_date,
        category_id=before.category_id,
        category=before.category,
        description=None,
    )

    response = client.patch(
        f"/api/transactions/{before.id}",
        json={"description": "   "},
    )
    assert response.status_code == 200
    data = response.json["data"]

    _assert_transaction(expected, data)

    after = db.session.get(Transaction, before.id)
    _assert_transaction(expected, after.to_dict())


def test_update_transaction_amount(client, transactions: dict[str, Transaction]):
    before = transactions["income"]
    expected = Transaction(
        id=before.id,
        amount="1500.00",
        transaction_date=before.transaction_date,
        category_id=before.category_id,
        category=before.category,
        description=before.description,
    )

    response = client.patch(
        f"/api/transactions/{before.id}",
        json={"amount": expected.amount},
    )
    assert response.status_code == 200
    data = response.json["data"]

    _assert_transaction(expected, data)

    after = db.session.get(Transaction, before.id)
    _assert_transaction(expected, after.to_dict())


def test_update_transaction_transaction_date(
    client, transactions: dict[str, Transaction]
):
    before = transactions["rent"]
    expected = Transaction(
        id=before.id,
        amount=before.amount,
        transaction_date=date(2026, 8, 4),
        category_id=before.category_id,
        category=before.category,
        description=before.description,
    )

    response = client.patch(
        f"/api/transactions/{before.id}",
        json={"transaction_date": "2026-08-04"},
    )
    assert response.status_code == 200
    data = response.json["data"]

    _assert_transaction(expected, data)

    after = db.session.get(Transaction, before.id)
    _assert_transaction(expected, after.to_dict())


def test_update_transaction_category(
    client, categories: dict[str, Category], transactions: dict[str, Transaction]
):
    before = transactions["meal"]
    expected = Transaction(
        id=before.id,
        amount=before.amount,
        transaction_date=before.transaction_date,
        category_id=categories["rent"].id,
        category=categories["rent"],
        description=before.description,
    )

    response = client.patch(
        f"/api/transactions/{before.id}",
        json={"category_id": expected.category_id},
    )
    assert response.status_code == 200
    data = response.json["data"]

    _assert_transaction(expected, data)

    after = db.session.get(Transaction, before.id)
    _assert_transaction(expected, after.to_dict())


def test_update_transaction_all_fields(
    client, categories: dict[str, Category], transactions: dict[str, Transaction]
):
    before = transactions["rent"]
    expected = Transaction(
        id=before.id,
        amount="1500.00",
        transaction_date=date(2026, 8, 4),
        category_id=categories["food"].id,
        category=categories["food"],
        description="New Description",
    )

    response = client.patch(
        f"/api/transactions/{before.id}",
        json={
            "amount": expected.amount,
            "transaction_date": "2026-08-04",
            "category_id": expected.category_id,
            "description": expected.description,
        },
    )
    assert response.status_code == 200
    data = response.json["data"]
    _assert_transaction(expected, data)

    after = db.session.get(Transaction, before.id)
    _assert_transaction(expected, after.to_dict())


def test_update_transaction_with_no_fields_to_update(
    client, transactions: dict[str, Transaction]
):
    before = transactions["rent"]
    response = client.patch(
        f"/api/transactions/{before.id}",
        json={},
    )
    assert response.status_code == 400
    assert response.json == {"error": "No fields to update."}


def test_update_transaction_with_invalid_field(
    client, transactions: dict[str, Transaction]
):
    before = transactions["rent"]
    response = client.patch(
        f"/api/transactions/{before.id}",
        json={"invalid": "value"},
    )
    assert response.status_code == 400
    assert response.json == {"error": "Invalid field: invalid"}


@pytest.mark.parametrize(
    ("payload", "expected_error"),
    [
        (None, "A JSON object is required."),
        ({"description": 99}, "description must be a string."),
        ({"description": "x" * 256}, "description cannot exceed 255 characters."),
        ({"amount": "invalid"}, "amount must be a valid decimal value."),
        ({"amount": True}, "amount must be a valid decimal value."),
        ({"amount": "-100.00"}, "amount must be greater than 0."),
        ({"amount": "0"}, "amount must be greater than 0."),
        ({"amount": "100.000"}, "amount must have at most 2 decimal places."),
        ({"amount": "100000000.00"}, "amount too large."),
        (
            {"transaction_date": "not a date"},
            "transaction_date must have the format YYYY-MM-DD.",
        ),
        (
            {"transaction_date": str(date.today() + timedelta(days=1))},
            "transaction_date cannot be in the future.",
        ),
        ({"category_id": True}, "category_id must be a positive integer."),
        ({"category_id": 0}, "category_id must be a positive integer."),
        ({"category_id": -1}, "category_id must be a positive integer."),
    ],
)
def test_update_transaction_with_invalid_payload(
    client, transactions: dict[str, Transaction], payload: dict, expected_error: str
):
    response = client.patch(
        f"/api/transactions/{transactions['rent'].id}",
        json=payload,
    )
    assert response.status_code == 400
    assert response.json == {"error": expected_error}


def test_update_transaction_with_invalid_category_id(
    client, categories: dict[str, Category], transactions: dict[str, Transaction]
):
    response = client.patch(
        f"/api/transactions/{transactions['rent'].id}",
        json={"category_id": 99},
    )
    assert response.status_code == 404
    assert response.json == {"error": "The selected category does not exist."}


def test_update_non_existent_transaction(client):
    response = client.patch(
        "/api/transactions/99",
        json={},
    )
    assert response.status_code == 404
    assert response.json == {"error": "The selected transaction does not exist."}


def test_update_failure_leaves_transaction_unchanged(
    client, transactions: dict[str, Transaction]
):
    before = transactions["rent"]

    response = client.patch(
        f"/api/transactions/{before.id}",
        json={"amount": "invalid"},
    )
    assert response.status_code == 400

    after = db.session.get(Transaction, before.id)
    _assert_transaction(before, after.to_dict())


def test_update_partially_valid_leaves_transaction_unchanged(
    client, transactions: dict[str, Transaction]
):
    before = transactions["rent"]
    response = client.patch(
        f"/api/transactions/{before.id}",
        json={
            "description": "x" * 256,
            "amount": "invalid",
            "transaction_date": "2026-08-04",
        },
    )
    assert response.status_code == 400
    after = db.session.get(Transaction, before.id)
    _assert_transaction(before, after.to_dict())


def test_delete_transaction(client, transactions: dict[str, Transaction]):
    response = client.delete(
        f"/api/transactions/{transactions['rent'].id}",
    )
    assert response.status_code == 204
    assert response.data == b""

    after = db.session.get(Transaction, transactions["rent"].id)
    assert after is None


def test_delete_non_existent_transaction(client):
    response = client.delete(
        "/api/transactions/99",
    )
    assert response.status_code == 404
    assert response.json == {"error": "The selected transaction does not exist."}
