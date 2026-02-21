-- NoQ Bus Pass: database, table with activationCode, and 5 sample rows

CREATE DATABASE IF NOT EXISTS noq_bus_pass;
USE noq_bus_pass;

CREATE TABLE IF NOT EXISTS cards (
    cardNumber     VARCHAR(64)  PRIMARY KEY,
    holderName     VARCHAR(100),
    mobileNumber   VARCHAR(20),
    passStatus     VARCHAR(20),
    planType       VARCHAR(20),
    tripsUsed      INT DEFAULT 0,
    remainingTrips INT DEFAULT 0,
    activationCode VARCHAR(32) DEFAULT NULL
);

-- If you already had the table without activationCode, run once:
-- ALTER TABLE cards ADD COLUMN activationCode VARCHAR(32) DEFAULT NULL;

-- 4-digit activation codes stored in database (used for top-up validation)
INSERT INTO cards (cardNumber, holderName, mobileNumber, passStatus, planType, tripsUsed, remainingTrips, activationCode) VALUES
('1234 5678 9012 345', 'Piyush Mahalle', '9876543210', 'ACTIVE', 'MONTHLY', 24, 36, '4582'),
('1111 2222 3333 4444', 'Rahul Sharma', '9123456789', 'ACTIVE', 'WEEKLY', 5, 9, '1234'),
('5555 6666 7777 8888', 'Priya Patel', '9988776655', 'ACTIVE', 'MONTHLY', 0, 60, '5678'),
('9999 0000 1111 2222', 'Amit Kumar', '9876512345', 'DISCONTINUED', 'WEEKLY', 14, 0, '9012'),
('3333 4444 5555 6666', 'Sneha Singh', '9765432109', 'ACTIVE', 'WEEKLY', 2, 12, '3456');
