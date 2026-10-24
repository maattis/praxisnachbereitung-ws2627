-- Inventar-Schema für Tag 3
--
-- Reihenfolge:
--   1. Stammdaten-Tabellen (department, person, device_type, location)
--   2. device
--   3. assignment
-- Seed-Daten für den lokalen Testbetrieb.

-- 1. Stammdaten 

CREATE TABLE department (
    id   SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE person (
    id            SERIAL PRIMARY KEY,
    first_name    TEXT NOT NULL,
    last_name     TEXT NOT NULL,
    email         TEXT NOT NULL UNIQUE,
    department_id INTEGER REFERENCES department(id)
);

CREATE TABLE device_type (
    id   SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE location (
    id   SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

-- 2. Devices 

CREATE TABLE device (
    id              SERIAL PRIMARY KEY,
    serial_number   TEXT NOT NULL UNIQUE,
    device_type_id  INTEGER NOT NULL REFERENCES device_type(id),
    location_id     INTEGER NOT NULL REFERENCES location(id),
    note            TEXT
);

-- 3. Zuweisungen 

CREATE TABLE assignment (
    id          SERIAL PRIMARY KEY,
    device_id   INTEGER NOT NULL REFERENCES device(id),
    person_id   INTEGER NOT NULL REFERENCES person(id),
    issued_at   TIMESTAMP NOT NULL DEFAULT now(),
    returned_at TIMESTAMP
);

-- Seed-Daten 

INSERT INTO department (name) VALUES
    ('IT'),
    ('Logistik'),
    ('Verwaltung');

INSERT INTO device_type (name) VALUES
    ('Laptop'),
    ('Monitor'),
    ('Handscanner');

INSERT INTO location (name) VALUES
    ('Gebäude E'),
    ('Gebäude F'),
    ('Gebäude H');

INSERT INTO person (first_name, last_name, email, department_id) VALUES
    ('Anna',   'Keller',   'anna.keller@example.com',   (SELECT id FROM department WHERE name = 'IT')),
    ('Jonas',  'Richter',  'jonas.richter@example.com', (SELECT id FROM department WHERE name = 'Logistik')),
    ('Mara',   'Vogel',    'mara.vogel@example.com',    (SELECT id FROM department WHERE name = 'Verwaltung')),
    ('Tobias', 'Brandt',   'tobias.brandt@example.com', (SELECT id FROM department WHERE name = 'IT'));

INSERT INTO device (serial_number, device_type_id, location_id, note) VALUES
    ('LT-1001', (SELECT id FROM device_type WHERE name = 'Laptop'),      (SELECT id FROM location WHERE name = 'Gebäude E'), NULL),
    ('LT-1002', (SELECT id FROM device_type WHERE name = 'Laptop'),      (SELECT id FROM location WHERE name = 'Gebäude F'), NULL),
    ('MN-2001', (SELECT id FROM device_type WHERE name = 'Monitor'),     (SELECT id FROM location WHERE name = 'Gebäude E'), NULL),
    ('HS-3001', (SELECT id FROM device_type WHERE name = 'Handscanner'), (SELECT id FROM location WHERE name = 'Gebäude H'), 'Ersatzgerät');

INSERT INTO assignment (device_id, person_id, issued_at, returned_at) VALUES
    ((SELECT id FROM device WHERE serial_number = 'LT-1001'), (SELECT id FROM person WHERE email = 'anna.keller@example.com'),   now() - interval '30 days', NULL),
    ((SELECT id FROM device WHERE serial_number = 'LT-1002'), (SELECT id FROM person WHERE email = 'jonas.richter@example.com'), now() - interval '20 days', NULL),
    ((SELECT id FROM device WHERE serial_number = 'MN-2001'), (SELECT id FROM person WHERE email = 'anna.keller@example.com'),   now() - interval '60 days', now() - interval '5 days');
