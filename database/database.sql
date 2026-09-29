CREATE TABLE author(
    id                              SERIAL PRIMARY KEY,
    author_key                      CHAR(36) NOT NULL,
    name                            VARCHAR(255) NOT NULL,
    nationality                     VARCHAR(100) NOT NULL,
    document_number                 CHAR(14) NOT NULL,
    created_at                      TIMESTAMP NOT NULL DEFAULT(NOW()),
    UNIQUE(author_key),
    UNIQUE(document_number)
);

CREATE TABLE shelf(
    id                              SERIAL PRIMARY KEY,
    shelf_key                       CHAR(36) NOT NULL,
    code                            VARCHAR(20) NOT NULL,
    location                        VARCHAR(255) NOT NULL,
    capacity                        INTEGER NOT NULL CHECK (capacity > 0),
    created_at                      TIMESTAMP NOT NULL DEFAULT(NOW()),
    UNIQUE(shelf_key),
    UNIQUE(code)
);

CREATE TABLE member(
    id                              SERIAL PRIMARY KEY,
    member_key                      CHAR(36) NOT NULL,
    name                            VARCHAR(255) NOT NULL,
    email                           VARCHAR(255) NOT NULL,
    document_number                 CHAR(14) NOT NULL,
    created_at                      TIMESTAMP NOT NULL DEFAULT(NOW()),
    UNIQUE(member_key),
    UNIQUE(email),
    UNIQUE(document_number)
);

CREATE TABLE book_status(
    id                              SERIAL PRIMARY KEY,
    enumerator                      VARCHAR(50) NOT NULL,
    created_at                      TIMESTAMP NOT NULL DEFAULT(NOW()),
    UNIQUE(enumerator)
);

INSERT INTO book_status (enumerator) VALUES
('AVAILABLE'),
('BORROWED');

CREATE TABLE book(
    id                              SERIAL PRIMARY KEY,
    book_key                        CHAR(36) NOT NULL,
    status_id                       INTEGER NOT NULL REFERENCES book_status(id),
    author_id                       INTEGER NOT NULL REFERENCES author(id),
    shelf_id                        INTEGER REFERENCES shelf(id),
    member_id                       INTEGER REFERENCES member(id),
    title                           VARCHAR(255) NOT NULL,
    isbn                            CHAR(13) NOT NULL,
    year                            INTEGER NOT NULL,
    pages                           INTEGER NOT NULL,
    created_at                      TIMESTAMP NOT NULL DEFAULT(NOW()),
    UNIQUE(book_key),
    UNIQUE(isbn)
);

CREATE TABLE book_status_event(
    id                              SERIAL PRIMARY KEY,
    book_id                         INTEGER NOT NULL REFERENCES book(id),
    status_id                       INTEGER NOT NULL REFERENCES book_status(id),
    event_datetime                  TIMESTAMP NOT NULL,
    created_at                      TIMESTAMP NOT NULL DEFAULT(NOW())
);
