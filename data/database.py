"""SQLite database with versioned schema and automatic migration."""

import sqlite3
import json
import os
import logging
from contextlib import contextmanager
from datetime import datetime

logger = logging.getLogger(__name__)

DB_PATH = os.environ.get(
    "AICROCHET_DB",
    os.path.join(os.path.dirname(__file__), "..", "data", "aicrochet.db"),
)

# Each entry is a (version, sql) pair applied in order.
_MIGRATIONS = [
    (1, """
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER NOT NULL
        );
        INSERT INTO schema_version VALUES (1);

        CREATE TABLE IF NOT EXISTS training_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_type TEXT NOT NULL,
            source_url TEXT,
            pattern_id TEXT,
            part_name TEXT NOT NULL,
            primitive_type TEXT,
            scale REAL,
            diameter_profile TEXT NOT NULL,
            stitch_counts TEXT NOT NULL,
            terminology TEXT,
            quality_score REAL DEFAULT 0.5,
            is_synthetic INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS feedback_corrections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            part_name TEXT NOT NULL,
            primitive_type TEXT,
            original_diameters TEXT NOT NULL,
            corrected_diameters TEXT NOT NULL,
            notes TEXT,
            incorporated INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        );
    """),
]


def _apply_migrations(conn: sqlite3.Connection) -> None:
    cursor = conn.cursor()
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'"
    )
    if not cursor.fetchone():
        current_version = 0
    else:
        row = cursor.execute("SELECT MAX(version) FROM schema_version").fetchone()
        current_version = row[0] if row and row[0] else 0

    for version, sql in _MIGRATIONS:
        if version > current_version:
            logger.info("Applying DB migration version %d", version)
            conn.executescript(sql)
            conn.commit()


@contextmanager
def get_db():
    os.makedirs(os.path.dirname(os.path.abspath(DB_PATH)), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        _apply_migrations(conn)
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def insert_training_record(conn: sqlite3.Connection, record: dict) -> int:
    cur = conn.execute(
        """INSERT INTO training_records
           (source_type, source_url, pattern_id, part_name, primitive_type, scale,
            diameter_profile, stitch_counts, terminology, quality_score, is_synthetic)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (
            record["source_type"],
            record.get("source_url"),
            record.get("pattern_id"),
            record["part_name"],
            record.get("primitive_type"),
            record.get("scale"),
            json.dumps(record["diameter_profile"]),
            json.dumps(record["stitch_counts"]),
            record.get("terminology"),
            record.get("quality_score", 0.5),
            int(record.get("is_synthetic", False)),
        ),
    )
    return cur.lastrowid


def insert_feedback(conn: sqlite3.Connection, feedback: dict) -> int:
    cur = conn.execute(
        """INSERT INTO feedback_corrections
           (session_id, part_name, primitive_type, original_diameters, corrected_diameters, notes)
           VALUES (?,?,?,?,?,?)""",
        (
            feedback["session_id"],
            feedback["part_name"],
            feedback.get("primitive_type"),
            json.dumps(feedback["original_diameters"]),
            json.dumps(feedback["corrected_diameters"]),
            feedback.get("notes"),
        ),
    )
    return cur.lastrowid


def get_unincorporated_count(conn: sqlite3.Connection) -> int:
    row = conn.execute(
        "SELECT COUNT(*) FROM feedback_corrections WHERE incorporated=0"
    ).fetchone()
    return row[0] if row else 0


def get_feedback_stats(conn: sqlite3.Connection) -> dict:
    total = conn.execute("SELECT COUNT(*) FROM feedback_corrections").fetchone()[0]
    unincorporated = get_unincorporated_count(conn)
    last_row = conn.execute(
        "SELECT created_at FROM feedback_corrections WHERE incorporated=1 ORDER BY created_at DESC LIMIT 1"
    ).fetchone()
    last_retrain = last_row[0] if last_row else None
    return {
        "total_corrections": total,
        "unincorporated": unincorporated,
        "last_retraining_date": last_retrain,
    }


def mark_corrections_incorporated(conn: sqlite3.Connection, ids: list) -> None:
    placeholders = ",".join("?" * len(ids))
    conn.execute(
        f"UPDATE feedback_corrections SET incorporated=1 WHERE id IN ({placeholders})", ids
    )


def get_training_records(conn: sqlite3.Connection, min_quality: float = 0.5) -> list:
    rows = conn.execute(
        "SELECT * FROM training_records WHERE quality_score >= ?", (min_quality,)
    ).fetchall()
    records = []
    for row in rows:
        r = dict(row)
        r["diameter_profile"] = json.loads(r["diameter_profile"])
        r["stitch_counts"] = json.loads(r["stitch_counts"])
        records.append(r)
    return records


def update_training_record_label(conn: sqlite3.Connection, record_id: int, primitive_type: str, scale: float) -> None:
    conn.execute(
        "UPDATE training_records SET primitive_type=?, scale=? WHERE id=?",
        (primitive_type, scale, record_id),
    )


def get_unlabeled_records(conn: sqlite3.Connection) -> list:
    rows = conn.execute(
        "SELECT * FROM training_records WHERE primitive_type IS NULL AND is_synthetic=0"
    ).fetchall()
    records = []
    for row in rows:
        r = dict(row)
        r["diameter_profile"] = json.loads(r["diameter_profile"])
        r["stitch_counts"] = json.loads(r["stitch_counts"])
        records.append(r)
    return records


def get_feedback_records(conn: sqlite3.Connection) -> list:
    rows = conn.execute("SELECT * FROM feedback_corrections").fetchall()
    records = []
    for row in rows:
        r = dict(row)
        r["original_diameters"] = json.loads(r["original_diameters"])
        r["corrected_diameters"] = json.loads(r["corrected_diameters"])
        records.append(r)
    return records
