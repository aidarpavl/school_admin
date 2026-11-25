"""Дерекқор қабаты: Supabase (PostgreSQL) немесе жергілікті SQLite.

DATABASE_URL секреті болса (postgresql://...) — Supabase қолданылады,
әйтпесе school.db (SQLite) файлы құрылады.
"""
import json
import sqlite3
import threading
from datetime import datetime

import pandas as pd

from core.config import get_secret

SCHEMA = [
    """CREATE TABLE IF NOT EXISTS users (
        id {PK}, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL,
        full_name TEXT, email TEXT, role TEXT DEFAULT 'teacher', position TEXT,
        subject TEXT, active INTEGER DEFAULT 1, created_at TEXT)""",
    """CREATE TABLE IF NOT EXISTS reset_codes (
        id {PK}, username TEXT, code TEXT, expires_at TEXT, used INTEGER DEFAULT 0)""",
    """CREATE TABLE IF NOT EXISTS tasks (
        id {PK}, title TEXT, description TEXT, assignee TEXT, created_by TEXT,
        due_date TEXT, priority TEXT, done INTEGER DEFAULT 0, done_at TEXT,
        report TEXT, created_at TEXT)""",
    """CREATE TABLE IF NOT EXISTS duties (
        id {PK}, duty TEXT, username TEXT, assigned_by TEXT, created_at TEXT)""",
    """CREATE TABLE IF NOT EXISTS documents (
        id {PK}, title TEXT, doc_type TEXT, channel TEXT, author TEXT,
        to_role TEXT, to_user TEXT, status TEXT, content TEXT, file_url TEXT,
        resolution TEXT, due_date TEXT, created_at TEXT, updated_at TEXT)""",
    """CREATE TABLE IF NOT EXISTS doc_history (
        id {PK}, doc_id INTEGER, actor TEXT, action TEXT, note TEXT, created_at TEXT)""",
    """CREATE TABLE IF NOT EXISTS feedback (
        id {PK}, author TEXT, anonymous INTEGER DEFAULT 0, target_role TEXT,
        source TEXT, category TEXT, text TEXT, sentiment REAL, topics TEXT,
        status TEXT DEFAULT 'Жаңа', response TEXT, created_at TEXT)""",
    """CREATE TABLE IF NOT EXISTS records (
        id {PK}, module TEXT, kind TEXT, author TEXT, data TEXT,
        private INTEGER DEFAULT 0, created_at TEXT)""",
]


def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class DB:
    def __init__(self, url: str | None = None, sqlite_path: str = "school.db"):
        self.url = url or get_secret("DATABASE_URL")
        self.lock = threading.Lock()
        if self.url and str(self.url).startswith("postgres"):
            self.kind = "pg"
        else:
            self.kind = "sqlite"
            self.sqlite_path = sqlite_path
        self.conn = None
        self._connect()
        self.init_schema()

    # --- қосылу ---
    def _connect(self):
        if self.kind == "pg":
            import psycopg2
            self.conn = psycopg2.connect(self.url, connect_timeout=10)
            self.conn.autocommit = True
        else:
            self.conn = sqlite3.connect(self.sqlite_path, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row

    def _sql(self, sql: str) -> str:
        if self.kind == "pg":
            return sql.replace("?", "%s")
        return sql

    def _cursor(self):
        if self.kind == "pg":
            try:
                if self.conn.closed:
                    self._connect()
            except Exception:
                self._connect()
        return self.conn.cursor()

    def init_schema(self):
        pk = "SERIAL PRIMARY KEY" if self.kind == "pg" else "INTEGER PRIMARY KEY AUTOINCREMENT"
        for s in SCHEMA:
            self.execute(s.replace("{PK}", pk))

    # --- негізгі әдістер ---
    def execute(self, sql: str, params=()):
        with self.lock:
            cur = self._cursor()
            try:
                cur.execute(self._sql(sql), tuple(params))
                if self.kind == "sqlite":
                    self.conn.commit()
                return cur.rowcount
            except Exception:
                if self.kind == "pg":
                    self._connect()
                raise
            finally:
                cur.close()

    def insert(self, table: str, data: dict) -> int:
        cols = list(data.keys())
        ph = ", ".join(["?"] * len(cols))
        sql = f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({ph})"
        with self.lock:
            cur = self._cursor()
            try:
                if self.kind == "pg":
                    cur.execute(self._sql(sql + " RETURNING id"), tuple(data.values()))
                    new_id = cur.fetchone()[0]
                else:
                    cur.execute(sql, tuple(data.values()))
                    self.conn.commit()
                    new_id = cur.lastrowid
                return int(new_id)
            finally:
                cur.close()

    def update(self, table: str, row_id: int, data: dict):
        sets = ", ".join(f"{k} = ?" for k in data)
        self.execute(f"UPDATE {table} SET {sets} WHERE id = ?", list(data.values()) + [row_id])

    def delete(self, table: str, row_id: int):
        self.execute(f"DELETE FROM {table} WHERE id = ?", (row_id,))

    def query(self, sql: str, params=()) -> list[dict]:
        with self.lock:
            cur = self._cursor()
            try:
                cur.execute(self._sql(sql), tuple(params))
                rows = cur.fetchall()
                if self.kind == "pg":
                    cols = [d[0] for d in cur.description]
                    return [dict(zip(cols, r)) for r in rows]
                return [dict(r) for r in rows]
            finally:
                cur.close()

    def df(self, sql: str, params=()) -> pd.DataFrame:
        return pd.DataFrame(self.query(sql, params))

    # --- әмбебап журнал (records) ---
    def add_record(self, module: str, kind: str, author: str, data: dict, private: bool = False) -> int:
        return self.insert("records", {
            "module": module, "kind": kind, "author": author,
            "data": json.dumps(data, ensure_ascii=False, default=str),
            "private": int(private), "created_at": now(),
        })

    def update_record(self, rec_id: int, data: dict):
        self.update("records", rec_id, {"data": json.dumps(data, ensure_ascii=False, default=str)})

    def records(self, module: str, kind: str | None = None, author: str | None = None) -> pd.DataFrame:
        sql = "SELECT * FROM records WHERE module = ?"
        params = [module]
        if kind:
            sql += " AND kind = ?"
            params.append(kind)
        if author:
            sql += " AND author = ?"
            params.append(author)
        sql += " ORDER BY id DESC"
        rows = self.query(sql, params)
        out = []
        for r in rows:
            try:
                d = json.loads(r["data"] or "{}")
            except Exception:
                d = {}
            d = {**d, "_id": r["id"], "_author": r["author"], "_created": r["created_at"]}
            out.append(d)
        return pd.DataFrame(out)


_db_instance = None

try:
    import streamlit as _st

    @_st.cache_resource(show_spinner=False)
    def _cached_db():
        return DB()
except ImportError:  # streamlit жоқ (тесттер)
    _cached_db = None


def get_db() -> DB:
    """Streamlit-те cache_resource арқылы бір рет құрылады."""
    global _db_instance
    if _cached_db is not None:
        return _cached_db()
    if _db_instance is None:
        _db_instance = DB()
    return _db_instance
