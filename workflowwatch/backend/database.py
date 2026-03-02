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

-- WP-8: Declined pattern-based suggestions (day + workflow + block)
CREATE TABLE IF NOT EXISTS pattern_suggestion_dismissals (
    date           TEXT NOT NULL, -- YYYY-MM-DD
    workflow_id    TEXT NOT NULL REFERENCES workflows(id) ON DELETE CASCADE,
    block_key      TEXT NOT NULL,
    count          INTEGER DEFAULT 1,
    last_dismissed TEXT NOT NULL,
    PRIMARY KEY (date, workflow_id, block_key)
);

CREATE INDEX IF NOT EXISTS idx_pattern_suggestion_dismissals_date
    ON pattern_suggestion_dismissals(date);

-- WP-8: Excluded events within a pattern suggestion (for imperfect 9/10 matches)
CREATE TABLE IF NOT EXISTS pattern_suggestion_event_exclusions (
    date        TEXT NOT NULL, -- YYYY-MM-DD
    workflow_id TEXT NOT NULL REFERENCES workflows(id) ON DELETE CASCADE,
    aw_bucket_id TEXT NOT NULL,
    aw_event_id INTEGER NOT NULL,
    created_at  TEXT NOT NULL,
    PRIMARY KEY (date, workflow_id, aw_bucket_id, aw_event_id)
);

CREATE INDEX IF NOT EXISTS idx_pattern_suggestion_event_exclusions_date
    ON pattern_suggestion_event_exclusions(date);

-- WP-7: Tier 1 exact-match label cache
CREATE TABLE IF NOT EXISTS label_cache (
    signature   TEXT PRIMARY KEY,
    workflow_id TEXT NOT NULL REFERENCES workflows(id) ON DELETE CASCADE,
    hit_count   INTEGER DEFAULT 1,
    last_seen   TEXT NOT NULL,
    created_at  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_label_cache_workflow
    ON label_cache(workflow_id);

-- WP-7: Negative signals (dismissed suggestions)
CREATE TABLE IF NOT EXISTS label_dismissals (
    signature      TEXT NOT NULL,
    workflow_id    TEXT NOT NULL,
    count          INTEGER DEFAULT 1,
    last_dismissed TEXT NOT NULL,
    PRIMARY KEY (signature, workflow_id)
);

-- Composite workflow composition (process → child workflow steps)
CREATE TABLE IF NOT EXISTS workflow_composition (
    parent_id       TEXT NOT NULL REFERENCES workflows(id) ON DELETE CASCADE,
    child_id        TEXT NOT NULL REFERENCES workflows(id) ON DELETE CASCADE,
    typical_pct     REAL,       -- 0.0–1.0, advisory only
    display_order   INTEGER DEFAULT 0,
    PRIMARY KEY (parent_id, child_id)
);

CREATE INDEX IF NOT EXISTS idx_workflow_composition_parent
    ON workflow_composition(parent_id);

-- User-defined label rules (Tier 0: highest priority, applied before cache/embedding)
CREATE TABLE IF NOT EXISTS label_rules (
    id          TEXT PRIMARY KEY,
    workflow_id TEXT NOT NULL REFERENCES workflows(id) ON DELETE CASCADE,
    rule_type   TEXT NOT NULL CHECK(rule_type IN ('app', 'title_keyword')),
    match_value TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    UNIQUE(workflow_id, rule_type, match_value)
);

CREATE INDEX IF NOT EXISTS idx_label_rules_workflow
    ON label_rules(workflow_id);
"""


def _apply_migrations(conn: sqlite3.Connection) -> None:
    """Add columns that were introduced after the initial schema (safe for existing DBs)."""
    wf_cols = {row[1] for row in conn.execute("PRAGMA table_info(workflows)")}
    if "is_composite" not in wf_cols:
        conn.execute("ALTER TABLE workflows ADD COLUMN is_composite INTEGER DEFAULT 0")
        logger.info("Migration: added workflows.is_composite")

    sess_cols = {row[1] for row in conn.execute("PRAGMA table_info(sessions)")}
    if "context_workflow_id" not in sess_cols:
        conn.execute("ALTER TABLE sessions ADD COLUMN context_workflow_id TEXT REFERENCES workflows(id)")
        logger.info("Migration: added sessions.context_workflow_id")

    conn.commit()


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
    _apply_migrations(_connection)
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
