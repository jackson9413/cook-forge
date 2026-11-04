# -*- coding: utf-8 -*-
"""SQLite session store for cook-forge."""

import json
import os
import sqlite3
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("COOKFORGE_DB", os.path.join(BASE_DIR, "data", "cookforge.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at  TEXT    NOT NULL,
    title       TEXT,
    score       REAL,
    verdict     TEXT,
    recipe      TEXT,
    payload     TEXT,
    rating      INTEGER,
    notes       TEXT
);
"""


def _connect():
    folder = os.path.dirname(DB_PATH)
    if folder and not os.path.isdir(folder):
        os.makedirs(folder)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = _connect()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


def save_session(result, recipe_text):
    conn = _connect()
    try:
        cur = conn.execute(
            "INSERT INTO sessions (created_at, title, score, verdict, recipe, payload, rating, notes)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (
                datetime.now().isoformat(timespec="seconds"),
                result.get("title") or "Untitled recipe",
                result.get("score"),
                result.get("verdict"),
                recipe_text or "",
                json.dumps(result, default=str),
                None,
                None,
            ),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def list_sessions(limit=50):
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT id, created_at, title, score, verdict, rating, notes FROM sessions"
            " ORDER BY id DESC LIMIT ?", (int(limit),)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_session(session_id):
    conn = _connect()
    try:
        row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
        if not row:
            return None
        data = dict(row)
        try:
            data["result"] = json.loads(data.get("payload") or "{}")
        except (ValueError, TypeError):
            data["result"] = {}
        return data
    finally:
        conn.close()


def update_session(session_id, rating=None, notes=None):
    conn = _connect()
    try:
        row = conn.execute("SELECT id FROM sessions WHERE id = ?", (session_id,)).fetchone()
        if not row:
            return False
        if rating is not None:
            try:
                rating = int(rating)
            except (TypeError, ValueError):
                rating = None
            if rating is not None and not (1 <= rating <= 5):
                rating = None
        if rating is not None:
            conn.execute("UPDATE sessions SET rating = ? WHERE id = ?", (rating, session_id))
        if notes is not None:
            conn.execute("UPDATE sessions SET notes = ? WHERE id = ?", (str(notes)[:4000], session_id))
        conn.commit()
        return True
    finally:
        conn.close()


def delete_session(session_id):
    conn = _connect()
    try:
        conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        conn.commit()
        return True
    finally:
        conn.close()
