from .extensions import db


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


class Transaction(db.Model):
    __tablename__ = "transactions"

    id = db.Column(db.BigInteger, primary_key=True)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    transaction_date = db.Column(db.Date, nullable=False)
    description = db.Column(db.String(255), nullable=False)
    category_id = db.Column(
        db.BigInteger,
        db.ForeignKey('categories.id'),
        nullable=False,
    )
    category = db.relationship('Category')

    def to_dict(self):
        return {
            "id": self.id,
            "amount": self.amount,
            "transaction_date": self.transaction_date.isoformat(),
            "description": self.description,
            "category_id": self.category_id,
            "category": self.category.to_dict(),
        }
