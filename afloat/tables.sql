--
CREATE TABLE banktxn (
    id VARCHAR PRIMARY KEY,
    account VARCHAR NOT NULL,
    type VARCHAR NOT NULL,
    amount INT NOT NULL,
    userDate DATETIME,
    ledgerDate DATETIME NOT NULL,
    memo VARCHAR NOT NULL,
    checkNumber INT,
    ledgerBalance INT
);

CREATE TABLE hold (
    id INT PRIMARY KEY,
    account VARCHAR NOT NULL,
    amount INT NOT NULL,
    description VARCHAR NOT NULL,
    dateApplied DATETIME
);

CREATE TABLE scheduledtxn (
    id INT PRIMARY KEY,
    amount INT NOT NULL,
    title VARCHAR NOT NULL,
    expectedDate DATETIME NOT NULL,
    originalDate DATETIME,
    fromAccount VARCHAR NOT NULL,
    toAccount VARCHAR,
    paidDate DATETIME
);

CREATE TABLE networklog (
    id INT PRIMARY KEY,
    eventDateTime DATETIME,
    service VARCHAR,
    description VARCHAR,
    severity VARCHAR
);

CREATE TABLE account (
    id VARCHAR PRIMARY KEY,
    type VARCHAR,
    ledgerBalance INT NOT NULL,
    ledgerAsOfDate DATETIME,
    availableBalance INT,
    availableAsOfDate DATETIME,
    regulationDCount INT,
    regulationDMax INT -- maybe always == 6?
);
