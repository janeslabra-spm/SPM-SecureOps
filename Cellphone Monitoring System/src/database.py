from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd


SCHEMA = """
CREATE TABLE IF NOT EXISTS incidents (
    incident_id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    incident_type TEXT NOT NULL,
    confidence REAL NOT NULL,
    camera_name TEXT NOT NULL,
    location TEXT NOT NULL,
    screenshot_path TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'Pending Review',
    notes TEXT NOT NULL DEFAULT ''
);
"""


def init_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute(SCHEMA)
        conn.commit()


def add_incident(
    db_path: Path,
    timestamp: str,
    incident_type: str,
    confidence: float,
    camera_name: str,
    location: str,
    screenshot_path: str,
    status: str = "Pending Review",
    notes: str = "",
) -> int:
    with sqlite3.connect(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO incidents (
                timestamp, incident_type, confidence, camera_name, location,
                screenshot_path, status, notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                timestamp,
                incident_type,
                confidence,
                camera_name,
                location,
                screenshot_path,
                status,
                notes,
            ),
        )
        conn.commit()
        return int(cursor.lastrowid)


def load_incidents(
    db_path: Path,
    start_date: str | None = None,
    end_date: str | None = None,
    incident_type: str | None = None,
    status: str | None = None,
) -> pd.DataFrame:
    query = "SELECT * FROM incidents WHERE 1=1"
    params: list[str] = []

    if start_date:
        query += " AND date(timestamp) >= date(?)"
        params.append(start_date)
    if end_date:
        query += " AND date(timestamp) <= date(?)"
        params.append(end_date)
    if incident_type and incident_type != "All":
        query += " AND incident_type = ?"
        params.append(incident_type)
    if status and status != "All":
        query += " AND status = ?"
        params.append(status)

    query += " ORDER BY datetime(timestamp) DESC, incident_id DESC"
    with sqlite3.connect(db_path) as conn:
        return pd.read_sql_query(query, conn, params=params)


def update_status(db_path: Path, incident_id: int, status: str) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE incidents SET status = ? WHERE incident_id = ?",
            (status, incident_id),
        )
        conn.commit()
