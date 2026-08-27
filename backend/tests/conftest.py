from datetime import date

import pytest
from app import create_app
from app.extensions import db
from app.models import Category, Transaction


@pytest.fixture
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


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def categories(app):
    income = Category(description="Salary", category_type="income")
    food = Category(description="Food", category_type="spending")
    rent = Category(description="Rent", category_type="spending")

    db.session.add_all([income, food, rent])
    db.session.commit()
    return {
        "income": income,
        "food": food,
        "rent": rent,
    }


@pytest.fixture
def transactions(categories):
    meal = Transaction(
        amount="100",
        transaction_date=date(2026, 8, 2),
        category_id=categories["food"].id,
        description="Dinner at the restaurant",
    )
    income = Transaction(
        amount="2000.00",
        transaction_date=date(2026, 8, 1),
        category_id=categories["income"].id,
        description="August Income",
    )
    rent = Transaction(
        amount="1000.00",
        transaction_date=date(2026, 8, 3),
        category_id=categories["rent"].id,
        description="Rent for August",
    )
    db.session.add_all([meal, income, rent])
    db.session.commit()
    return {
        "meal": meal,
        "income": income,
        "rent": rent,
    }
