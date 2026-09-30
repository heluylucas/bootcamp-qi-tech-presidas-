CREATE TABLE customer(
    id                              SERIAL PRIMARY KEY,
    customer_key                    CHAR(36) NOT NULL UNIQUE,
    name                            TEXT NOT NULL,
    document_number                 CHAR(14) NOT NULL UNIQUE,
    birth_date                      DATE NOT NULL,
    created_at                      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE account_status(
    id                              SERIAL PRIMARY KEY,
    enumerator                      VARCHAR(50) NOT NULL UNIQUE,
    created_at                      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO account_status (enumerator) VALUES
('ACTIVE'),
('BLOCKED'),
('CLOSED');

CREATE TABLE account(
    id                              SERIAL PRIMARY KEY,
    account_key                     CHAR(36) NOT NULL UNIQUE,
    customer_id                     INTEGER NOT NULL REFERENCES customer(id),
    status_id                       INTEGER NOT NULL REFERENCES account_status(id),
    balance                         BIGINT NOT NULL DEFAULT 0 CHECK (balance >= 0),
    created_at                      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at                      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE account_status_event(
    id                              SERIAL PRIMARY KEY,
    account_id                      INTEGER NOT NULL REFERENCES account(id),
    from_status_id                  INTEGER REFERENCES account_status(id),
    to_status_id                    INTEGER NOT NULL REFERENCES account_status(id),
    reason                          VARCHAR(255),
    created_at                      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE transaction_type(
    id                              SERIAL PRIMARY KEY,
    enumerator                      VARCHAR(50) NOT NULL UNIQUE,
    created_at                      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO transaction_type (enumerator) VALUES
('DEPOSIT'),
('WITHDRAWAL'),
('TRANSFER'),
('INVESTMENT_APPLY'),
('INVESTMENT_REDEEM');

CREATE TABLE transaction(
    id                              SERIAL PRIMARY KEY,
    transaction_key                 CHAR(36) NOT NULL UNIQUE,
    type_id                         INTEGER NOT NULL REFERENCES transaction_type(id),
    requester_account_id            INTEGER NOT NULL REFERENCES account(id),
    origin_account_id               INTEGER REFERENCES account(id),
    destination_account_id          INTEGER REFERENCES account(id),
    amount                          BIGINT NOT NULL CHECK (amount > 0),
    fee_amount                      BIGINT NOT NULL DEFAULT 0 CHECK (fee_amount >= 0),
    description                     VARCHAR(140),
    idempotency_key                 CHAR(36) NOT NULL,
    request_hash                    CHAR(64) NOT NULL,
    created_at                      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(requester_account_id, idempotency_key)
);

CREATE TABLE ledger_entry(
    id                              SERIAL PRIMARY KEY,
    entry_key                       CHAR(36) NOT NULL UNIQUE,
    transaction_id                  INTEGER NOT NULL REFERENCES transaction(id),
    account_id                      INTEGER NOT NULL REFERENCES account(id),
    direction                       VARCHAR(6) NOT NULL CHECK (direction IN ('DEBIT', 'CREDIT')),
    category                        VARCHAR(9) NOT NULL CHECK (category IN ('PRINCIPAL', 'FEE')),
    amount                          BIGINT NOT NULL CHECK (amount > 0),
    balance_after                   BIGINT NOT NULL CHECK (balance_after >= 0),
    created_at                      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX ledger_entry_account_created_idx ON ledger_entry (account_id, created_at);
