CREATE TABLE finance_dev.income_categories
(
    id BIGINT UNSIGNED AUTO_INCREMENT NOT NULL,
    description varchar(100) NOT NULL,
    
    PRIMARY KEY (id),
    CONSTRAINT income_categories_unique
        UNIQUE (description)
);

CREATE TABLE finance_dev.spending_categories
(
    id BIGINT UNSIGNED AUTO_INCREMENT NOT NULL,
    description varchar(100) NOT NULL,
    
    PRIMARY KEY (id),
    CONSTRAINT spending_categories_unique
        UNIQUE (description)
);

CREATE TABLE finance_dev.income_transactions
(
    id BIGINT UNSIGNED AUTO_INCREMENT NOT NULL,
    amount DECIMAL(10, 2) NOT NULL,
    transaction_date DATE NOT NULL,
    description varchar(255),
    income_category_id BIGINT UNSIGNED NOT NULL,

    PRIMARY KEY (id),
    CONSTRAINT income_transactions_positive
        CHECK (amount > 0),
    CONSTRAINT income_transactions_income_category_id_fk
        FOREIGN KEY (income_category_id)
        REFERENCES finance_dev.income_categories(id)
);

CREATE TABLE finance_dev.spending_transactions
(
    id BIGINT UNSIGNED AUTO_INCREMENT NOT NULL,
    amount DECIMAL(10, 2) NOT NULL,
    transaction_date DATE NOT NULL,
    description varchar(255),
    spending_category_id BIGINT UNSIGNED NOT NULL,

    PRIMARY KEY (id),
    CONSTRAINT spending_transactions_positive
        CHECK (amount > 0),
    CONSTRAINT spending_transactions_spending_category_id_fk
        FOREIGN KEY (spending_category_id)
        REFERENCES finance_dev.spending_categories(id)
);