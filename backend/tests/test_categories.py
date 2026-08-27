import pytest
from app.models import Category


def test_health_check(client):
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json == {"status": "ok"}


def test_get_all_categories(categories: dict[str, Category], client):
    response = client.get("/api/categories")

    assert response.status_code == 200
    data = response.json["data"]

    assert len(data) == 3

    assert data[0]["description"] == categories["income"].description
    assert data[0]["category_type"] == "income"
    assert data[1]["description"] == categories["food"].description
    assert data[1]["category_type"] == "spending"
    assert data[2]["description"] == categories["rent"].description
    assert data[2]["category_type"] == "spending"


def test_get_income_categories(categories: dict[str, Category], client):
    response = client.get("/api/categories?type=income")

    assert response.status_code == 200
    data = response.json["data"]

    assert len(data) == 1
    assert data[0]["description"] == categories["income"].description
    assert data[0]["category_type"] == "income"


def test_get_spending_categories(categories: dict[str, Category], client):
    response = client.get("/api/categories?type=spending")

    assert response.status_code == 200
    data = response.json["data"]

    assert len(data) == 2
    assert data[0]["description"] == categories["food"].description
    assert data[0]["category_type"] == "spending"
    assert data[1]["description"] == categories["rent"].description
    assert data[1]["category_type"] == "spending"


def test_get_invalid_category_type(client):
    response = client.get("/api/categories?type=invalid")

    assert response.status_code == 400
    assert response.json == {"error": "category_type must be income or spending."}


def test_create_income_category(client):
    response = client.post(
        "/api/categories", json={"description": "  Salary  ", "category_type": "income"}
    )

    assert response.status_code == 201
    data = response.json["data"]

    assert data["description"] == "Salary"
    assert data["category_type"] == "income"


def test_create_spending_category(client):
    response = client.post(
        "/api/categories", json={"description": "  Food  ", "category_type": "spending"}
    )

    assert response.status_code == 201
    data = response.json["data"]

    assert data["description"] == "Food"
    assert data["category_type"] == "spending"


@pytest.mark.parametrize(
    ("payload", "expected_error"),
    [
        (None, "A JSON object is required."),
        (
            {"description": 1, "category_type": "income"},
            "description must be a string.",
        ),
        (
            {"description": "   ", "category_type": "income"},
            "description cannot be blank.",
        ),
        (
            {
                "description": "x" * 101,
                "category_type": "income",
            },
            "description cannot exceed 100 characters.",
        ),
        (
            {"description": "Salary", "category_type": "invalid"},
            "category_type must be income or spending.",
        ),
    ],
)
def test_create_category_with_invalid_data(client, payload: dict, expected_error: str):
    response = client.post("/api/categories", json=payload)

    assert response.status_code == 400
    assert response.json == {"error": expected_error}


def test_create_category_that_already_exists(client):
    response = client.post(
        "/api/categories", json={"description": "Salary", "category_type": "income"}
    )

    assert response.status_code == 201
    data = response.json["data"]

    assert data["description"] == "Salary"
    assert data["category_type"] == "income"
