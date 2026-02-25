import logging
import sqlite3
from pathlib import Path

from .config import settings

logger = logging.getLogger(__name__)

_connection: sqlite3.Connection | None = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS workflows (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    description TEXT,
    color       TEXT,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    archived    INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS sessions (
    id           TEXT PRIMARY KEY,
    workflow_id  TEXT NOT NULL,
    title        TEXT,
    started_at   TEXT NOT NULL,
    ended_at     TEXT NOT NULL,
    duration     REAL NOT NULL,
    notes        TEXT,
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL,
    FOREIGN KEY (workflow_id) REFERENCES workflows(id)
);

CREATE TABLE IF NOT EXISTS session_events (
    id              TEXT PRIMARY KEY,
    session_id      TEXT NOT NULL,
    aw_bucket_id    TEXT NOT NULL,
    aw_event_id     INTEGER NOT NULL,
    event_timestamp TEXT NOT NULL,
    event_duration  REAL NOT NULL,
    event_data      TEXT,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_session_events_session
    ON session_events(session_id);

CREATE INDEX IF NOT EXISTS idx_session_events_timestamp
    ON session_events(event_timestamp);

CREATE UNIQUE INDEX IF NOT EXISTS idx_session_events_aw_ref
    ON session_events(aw_bucket_id, aw_event_id);

CREATE TABLE IF NOT EXISTS workflow_patterns (
    workflow_id       TEXT NOT NULL,
    indicator_type   TEXT NOT NULL,
    value1           TEXT NOT NULL,
    value2           TEXT,
    session_count    INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (workflow_id, indicator_type, value1, value2),
    FOREIGN KEY (workflow_id) REFERENCES workflows(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_workflow_patterns_workflow
    ON workflow_patterns(workflow_id);
"""


def init_db() -> None:
    """Create the data directory and initialize the database schema."""
    global _connection

    db_path = Path(settings.ww_db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    _connection = sqlite3.connect(str(db_path), check_same_thread=False)
    _connection.row_factory = sqlite3.Row
    _connection.execute("PRAGMA journal_mode=WAL")
    _connection.execute("PRAGMA foreign_keys=ON")
    _connection.executescript(SCHEMA)
    _connection.commit()

    logger.info("Database initialized at %s", db_path)


def get_db() -> sqlite3.Connection:
    """Return the active database connection."""
    if _connection is None:
        raise RuntimeError("Database not initialized — call init_db() first")
    return _connection


def close_db() -> None:
    """Close the database connection."""
    global _connection
    if _connection is not None:
        _connection.close()
        _connection = None
        logger.info("Database connection closed")
