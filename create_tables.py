import sqlite3

conn = sqlite3.connect('vec.sqlite')
cur = conn.cursor()

cur.executescript('''
DROP TABLE IF EXISTS drivers;
DROP TABLE IF EXISTS events;
DROP TABLE IF EXISTS results;
DROP TABLE IF EXISTS stints;
DROP TABLE IF EXISTS timing;

CREATE TABLE drivers (
    id     INTEGER PRIMARY KEY,
    name   TEXT UNIQUE
);

CREATE TABLE events (
    id          INTEGER PRIMARY KEY,
    season      INTEGER,
    division    INTEGER,
    race        INTEGER,
    date        TEXT UNIQUE,
    track       TEXT
);

CREATE TABLE results (
    id          INTEGER PRIMARY KEY,
    event_id    INTEGER REFERENCES events,
    driver_id   INTEGER REFERENCES drivers,
    class_pos   INTEGER,
    car_num     INTEGER,
    class       TEXT,
    team        TEXT,
    car         TEXT,
    UNIQUE (event_id, driver_id)
);

CREATE TABLE stints (
    id          INTEGER PRIMARY KEY,
    event_id    INTEGER REFERENCES events,
    driver_id   INTEGER REFERENCES drivers,
    lap_start   INTEGER,
    lap_end     INTEGER
);

CREATE TABLE timing (
    id          INTEGER PRIMARY KEY,    
    event_id    INTEGER REFERENCES events,
    driver_id   INTEGER REFERENCES drivers,
    lap         INTEGER,
    lap_time    REAL,
    fuel        REAL
);
''')