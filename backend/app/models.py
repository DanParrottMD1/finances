from .extensions import db


class IncomeCategory(db.Model):
    __tablename__ = "income_categories"

    id = db.Column(db.BigInteger, primary_key=True)
    description = db.Column(db.String(100), nullable=False)

    def to_dict(self):
        return {"id": self.id, "description": self.description}


class SpendingCategory(db.Model):
    __tablename__ = "spending_categories"

    id = db.Column(db.BigInteger, primary_key=True)
    description = db.Column(db.String(100), nullable=False)

    def to_dict(self):
        return {"id": self.id, "description": self.description}
