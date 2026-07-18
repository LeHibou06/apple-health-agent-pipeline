from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS raw_payloads (
    id TEXT PRIMARY KEY,
    received_at TEXT NOT NULL,
    body TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS processed_payloads (
    payload_id TEXT PRIMARY KEY,
    processed_at TEXT NOT NULL,
    status TEXT NOT NULL,
    error TEXT,
    FOREIGN KEY (payload_id) REFERENCES raw_payloads(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS health_samples (
    id TEXT PRIMARY KEY,
    payload_id TEXT NOT NULL,
    metric TEXT NOT NULL,
    sample_at TEXT NOT NULL,
    sample_date TEXT NOT NULL,
    unit TEXT,
    qty REAL,
    avg_value REAL,
    min_value REAL,
    max_value REAL,
    source TEXT,
    raw_json TEXT NOT NULL,
    FOREIGN KEY (payload_id) REFERENCES raw_payloads(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_samples_date_metric ON health_samples(sample_date, metric);

CREATE TABLE IF NOT EXISTS daily_metrics (
    sample_date TEXT NOT NULL,
    metric TEXT NOT NULL,
    unit TEXT NOT NULL DEFAULT '',
    sample_count INTEGER NOT NULL,
    total_value REAL,
    average_value REAL,
    minimum_value REAL,
    maximum_value REAL,
    last_value REAL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (sample_date, metric, unit)
);

CREATE TABLE IF NOT EXISTS sleep_segments (
    id TEXT PRIMARY KEY,
    payload_id TEXT NOT NULL,
    start_at TEXT NOT NULL,
    end_at TEXT NOT NULL,
    duration_minutes REAL NOT NULL,
    source TEXT,
    stage_raw TEXT,
    stage_normalized TEXT NOT NULL,
    FOREIGN KEY (payload_id) REFERENCES raw_payloads(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_sleep_segments_start ON sleep_segments(start_at);

CREATE TABLE IF NOT EXISTS sleep_episodes (
    id TEXT PRIMARY KEY,
    episode_date TEXT NOT NULL,
    episode_type TEXT NOT NULL,
    start_at TEXT NOT NULL,
    end_at TEXT NOT NULL,
    total_sleep_minutes REAL NOT NULL,
    awake_minutes REAL NOT NULL,
    core_minutes REAL NOT NULL,
    deep_minutes REAL NOT NULL,
    rem_minutes REAL NOT NULL,
    unspecified_minutes REAL NOT NULL,
    efficiency REAL,
    awakenings INTEGER NOT NULL,
    awakenings_5m INTEGER NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sleep_episodes_date ON sleep_episodes(episode_date);

CREATE TABLE IF NOT EXISTS workouts (
    id TEXT PRIMARY KEY,
    payload_id TEXT NOT NULL,
    workout_type TEXT,
    name TEXT,
    start_at TEXT NOT NULL,
    end_at TEXT,
    duration_seconds REAL,
    distance REAL,
    distance_unit TEXT,
    energy REAL,
    energy_unit TEXT,
    heart_rate_average REAL,
    heart_rate_minimum REAL,
    heart_rate_maximum REAL,
    elevation_up REAL,
    is_indoor INTEGER,
    raw_json TEXT NOT NULL,
    FOREIGN KEY (payload_id) REFERENCES raw_payloads(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_workouts_start ON workouts(start_at);
"""


def connect(path: str, *, read_only: bool = False) -> sqlite3.Connection:
    if read_only:
        uri = f"file:{Path(path).resolve()}?mode=ro"
        con = sqlite3.connect(uri, uri=True, timeout=30)
    else:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(path, timeout=30)
    con.row_factory = sqlite3.Row
    return con


def init_db(path: str) -> None:
    with connect(path) as con:
        con.executescript(SCHEMA)
        con.commit()
