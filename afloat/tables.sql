--
CREATE TABLE banktxn (
    id VARCHAR PRIMARY KEY,
    account VARCHAR NOT NULL,
    type VARCHAR NOT NULL,
    amount INTEGER NOT NULL,
    userDate DATETIME,
    ledgerDate DATETIME NOT NULL,
    memo VARCHAR NOT NULL,
    checkNumber INTEGER,
    ledgerBalance INTEGER
);

CREATE TABLE hold (
    id INTEGER PRIMARY KEY,
    account VARCHAR NOT NULL,
    amount INTEGER NOT NULL,
    description VARCHAR NOT NULL,
    dateApplied DATETIME
);

CREATE TABLE scheduledtxn (
    href VARCHAR PRIMARY KEY,
    bankId VARCHAR,
    amount INTEGER NOT NULL,
    checkNumber INTEGER,
    title VARCHAR NOT NULL,
    expectedDate DATETIME NOT NULL,
    originalDate DATETIME,
    fromAccount VARCHAR NOT NULL,
    toAccount VARCHAR,
    paidDate DATETIME
);

CREATE TABLE networklog (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    eventDateTime DATETIME,
    service VARCHAR,
    description VARCHAR,
    severity VARCHAR
);

CREATE TABLE account (
    id VARCHAR PRIMARY KEY,
    type VARCHAR,
    ledgerBalance INTEGER NOT NULL,
    ledgerAsOfDate DATETIME,
    availableBalance INTEGER,
    availableAsOfDate DATETIME,
    regulationDCount INTEGER,
    regulationDMax INTEGER -- maybe always == 6?
);
