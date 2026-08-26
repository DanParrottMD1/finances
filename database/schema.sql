CREATE TABLE finance_dev.categories
(
    id BIGINT UNSIGNED AUTO_INCREMENT NOT NULL,
    description varchar(100) NOT NULL,
    category_type ENUM('income', 'spending') NOT NULL,
    
    PRIMARY KEY (id),
    CONSTRAINT categories_unique
        UNIQUE (description, category_type)
);

CREATE TABLE finance_dev.transactions
(
    id BIGINT UNSIGNED AUTO_INCREMENT NOT NULL,
    amount DECIMAL(10, 2) NOT NULL,
    transaction_date DATE NOT NULL,
    description varchar(255),
    category_id BIGINT UNSIGNED NOT NULL,

    PRIMARY KEY (id),
    CONSTRAINT transactions_positive
        CHECK (amount > 0),
    CONSTRAINT transactions_category_id_fk
        FOREIGN KEY (category_id)
        REFERENCES finance_dev.categories(id)
);