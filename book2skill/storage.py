from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any
from uuid import uuid4


class SQLiteStore:
    def __init__(self, db_path: str | Path = "book2skill.db") -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _initialize(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS projects (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    content TEXT NOT NULL,
                    FOREIGN KEY(project_id) REFERENCES projects(id)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    source_text TEXT NOT NULL,
                    status TEXT NOT NULL,
                    package TEXT,
                    error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    email TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    subscription_status TEXT NOT NULL DEFAULT 'free',
                    stripe_customer_id TEXT UNIQUE,
                    free_trial_expires_at TEXT
                )
                """
            )
            user_columns = {row["name"] for row in conn.execute("PRAGMA table_info(users)")}
            if "free_trial_expires_at" not in user_columns:
                conn.execute("ALTER TABLE users ADD COLUMN free_trial_expires_at TEXT")
                conn.execute(
                    "UPDATE users SET free_trial_expires_at = datetime(created_at, '+7 days') WHERE free_trial_expires_at IS NULL"
                )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    token_hash TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS usage_events (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS ip_trial_claims (
                    ip_hash TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    claimed_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS app_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )
            conn.execute("DROP TABLE IF EXISTS pending_email_verifications")
            conn.commit()

    def get_or_create_setting(self, key: str, value: str) -> str:
        with self._connect() as conn:
            conn.execute("INSERT OR IGNORE INTO app_settings (key, value) VALUES (?, ?)", (key, value))
            row = conn.execute("SELECT value FROM app_settings WHERE key = ?", (key,)).fetchone()
        return str(row["value"])

    def create_account(
        self,
        email: str,
        password_hash: str,
        ip_hash: str,
        now: str,
        trial_expires_at: str,
        ip_claim_expires_at: str,
    ) -> dict[str, Any]:
        user_id = uuid4().hex
        with self._connect() as conn:
            conn.execute("DELETE FROM ip_trial_claims WHERE expires_at <= ?", (now,))
            prior_claim = conn.execute(
                "SELECT user_id FROM ip_trial_claims WHERE ip_hash = ?",
                (ip_hash,),
            ).fetchone()
            account_trial_expiry = trial_expires_at if prior_claim is None else now
            conn.execute(
                "INSERT INTO users (id, email, password_hash, created_at, free_trial_expires_at) VALUES (?, ?, ?, ?, ?)",
                (user_id, email, password_hash, now, account_trial_expiry),
            )
            if prior_claim is None:
                conn.execute(
                    "INSERT INTO ip_trial_claims (ip_hash, user_id, claimed_at, expires_at) VALUES (?, ?, ?, ?)",
                    (ip_hash, user_id, now, ip_claim_expires_at),
                )
            row = conn.execute(
                "SELECT id, email, created_at, subscription_status, stripe_customer_id, free_trial_expires_at FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()
        return dict(row)

    def get_user_by_email(self, email: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id, email, password_hash, created_at, subscription_status, stripe_customer_id, free_trial_expires_at FROM users WHERE email = ?",
                (email,),
            ).fetchone()
        return dict(row) if row else None

    def get_user_by_id(self, user_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id, email, created_at, subscription_status, stripe_customer_id, free_trial_expires_at FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()
        return dict(row) if row else None

    def create_session(self, token_hash: str, user_id: str, expires_at: str, created_at: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM sessions WHERE expires_at <= ?", (created_at,))
            conn.execute(
                "INSERT INTO sessions (token_hash, user_id, expires_at, created_at) VALUES (?, ?, ?, ?)",
                (token_hash, user_id, expires_at, created_at),
            )

    def get_user_by_session(self, token_hash: str, now: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                  SELECT users.id, users.email, users.created_at, users.subscription_status,
                      users.stripe_customer_id, users.free_trial_expires_at
                FROM sessions JOIN users ON users.id = sessions.user_id
                WHERE sessions.token_hash = ? AND sessions.expires_at > ?
                """,
                (token_hash, now),
            ).fetchone()
        return dict(row) if row else None

    def delete_session(self, token_hash: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash,))

    def record_compile(self, user_id: str, created_at: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO usage_events (id, user_id, created_at) VALUES (?, ?, ?)",
                (uuid4().hex, user_id, created_at),
            )

    def monthly_compile_count(self, user_id: str, month_start: str) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS count FROM usage_events WHERE user_id = ? AND created_at >= ?",
                (user_id, month_start),
            ).fetchone()
        return int(row["count"])

    def set_billing_status(
        self,
        user_id: str,
        status: str,
        stripe_customer_id: str | None = None,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE users SET subscription_status = ?, stripe_customer_id = COALESCE(?, stripe_customer_id) WHERE id = ?",
                (status, stripe_customer_id, user_id),
            )

    def get_user_by_stripe_customer(self, stripe_customer_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id, email, created_at, subscription_status, stripe_customer_id, free_trial_expires_at FROM users WHERE stripe_customer_id = ?",
                (stripe_customer_id,),
            ).fetchone()
        return dict(row) if row else None

    def create_project(self, name: str) -> str:
        project_id = uuid4().hex
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO projects (id, name, created_at) VALUES (?, ?, datetime('now'))",
                (project_id, name),
            )
            conn.commit()
        return project_id

    def add_document(self, project_id: str, filename: str, content: str) -> dict[str, str]:
        document_id = uuid4().hex
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO documents (id, project_id, filename, content) VALUES (?, ?, ?, ?)",
                (document_id, project_id, filename, content),
            )
            conn.commit()
        return {"id": document_id, "project_id": project_id, "filename": filename, "content": content}

    def get_project(self, project_id: str) -> dict[str, Any]:
        with self._connect() as conn:
            project_row = conn.execute(
                "SELECT id, name, created_at FROM projects WHERE id = ?",
                (project_id,),
            ).fetchone()
            if project_row is None:
                raise KeyError(f"Project not found: {project_id}")

            documents = conn.execute(
                "SELECT id, filename, content FROM documents WHERE project_id = ? ORDER BY filename",
                (project_id,),
            ).fetchall()

            return {
                "id": project_row["id"],
                "name": project_row["name"],
                "created_at": project_row["created_at"],
                "documents": [
                    {
                        "id": doc["id"],
                        "filename": doc["filename"],
                        "content": doc["content"],
                    }
                    for doc in documents
                ],
            }

    def create_job(self, title: str, source_text: str) -> str:
        job_id = uuid4().hex
        now = __import__("datetime").datetime.now().isoformat()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO jobs (id, title, source_text, status, package, error, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (job_id, title, source_text, "queued", None, None, now, now),
            )
            conn.commit()
        return job_id

    def get_job(self, job_id: str) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id, title, source_text, status, package, error, created_at, updated_at FROM jobs WHERE id = ?",
                (job_id,),
            ).fetchone()
            if row is None:
                raise KeyError(f"Job not found: {job_id}")

            return {
                "job_id": row["id"],
                "title": row["title"],
                "source_text": row["source_text"],
                "status": row["status"],
                "package": json.loads(row["package"]) if row["package"] else None,
                "error": row["error"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }

    def update_job(self, job_id: str, status: str, package: dict[str, Any] | None = None, error: str | None = None) -> None:
        now = __import__("datetime").datetime.now().isoformat()
        with self._connect() as conn:
            conn.execute(
                "UPDATE jobs SET status = ?, package = ?, error = ?, updated_at = ? WHERE id = ?",
                (status, json.dumps(package) if package is not None else None, error, now, job_id),
            )
            conn.commit()
