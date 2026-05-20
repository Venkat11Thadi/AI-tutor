"""SQLite persistence layer for users, sessions, messages, and OTP codes."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from fastapi import HTTPException, status

from .models import SessionMessage, SessionState


DEFAULT_DB_PATH = Path(__file__).resolve().parents[2] / "socraticcs.sqlite3"
DB_PATH = Path(os.getenv("SQLITE_DB_PATH", DEFAULT_DB_PATH))
JWT_SECRET = os.getenv("JWT_SECRET", "dev-only-change-me")
TOKEN_TTL_SECONDS = int(timedelta(days=7).total_seconds())
PASSWORD_ITERATIONS = 210_000


def utc_now() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


def connect() -> sqlite3.Connection:
    """Open a connection to the SQLite database.

    Creates parent directories if needed, enables WAL-compatible row
    factory and foreign-key enforcement.

    Returns:
        A ``sqlite3.Connection`` with ``Row`` row factory.
    """
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    """Initialize the SQLite database schema with migration support.

    Creates the ``users``, ``sessions``, ``messages``, and ``otps``
    tables if they do not exist, along with performance indexes.
    Performs lightweight column migrations for ``learning_state``
    and ``strategy`` on the ``messages`` table.
    """
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                title TEXT NOT NULL,
                topic TEXT NOT NULL,
                hint_count INTEGER NOT NULL DEFAULT 0,
                understanding_score INTEGER NOT NULL DEFAULT 0,
                jailbreak_threshold INTEGER NOT NULL DEFAULT 70,
                status TEXT NOT NULL DEFAULT 'active',
                struggle_areas TEXT NOT NULL DEFAULT '[]',
                concepts_mastered TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                hint_level INTEGER,
                intent TEXT,
                learning_state TEXT,
                strategy TEXT,
                timestamp TEXT,
                position INTEGER NOT NULL,
                FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS otps (
                email TEXT PRIMARY KEY,
                otp TEXT NOT NULL,
                expires_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_sessions_user_updated
                ON sessions(user_id, updated_at DESC);
            CREATE INDEX IF NOT EXISTS idx_messages_session_position
                ON messages(session_id, position);
            """
        )
        columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(messages)").fetchall()
        }
        if "learning_state" not in columns:
            conn.execute("ALTER TABLE messages ADD COLUMN learning_state TEXT")
        if "strategy" not in columns:
            conn.execute("ALTER TABLE messages ADD COLUMN strategy TEXT")


def normalize_email(email: str) -> str:
    """Normalize an email address for case-insensitive lookups.

    Args:
        email: Raw email string.

    Returns:
        Lowered, whitespace-stripped email.
    """
    return email.strip().lower()


def save_otp(email: str, otp: str, expires_in_seconds: int = 600) -> None:
    """Persist an OTP code for email verification.

    Inserts or replaces any existing OTP for the given email with a
    new code and expiration timestamp.

    Args:
        email: Recipient email address.
        otp: The six-digit OTP string.
        expires_in_seconds: TTL in seconds (default 600 / 10 minutes).
    """
    init_db()
    expires_at = (datetime.now(timezone.utc) + timedelta(seconds=expires_in_seconds)).isoformat()
    with connect() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO otps (email, otp, expires_at)
            VALUES (?, ?, ?)
            """,
            (normalize_email(email), otp, expires_at),
        )


def verify_otp(email: str, otp: str) -> bool:
    """Verify an OTP code and consume it on success.

    Checks that the stored OTP matches and has not expired. On a
    successful match the OTP row is deleted to prevent reuse.

    Args:
        email: The email address the OTP was sent to.
        otp: The six-digit code submitted by the user.

    Returns:
        ``True`` if the OTP is valid and not expired, ``False`` otherwise.
    """
    init_db()
    with connect() as conn:
        row = conn.execute(
            "SELECT otp, expires_at FROM otps WHERE email = ?",
            (normalize_email(email),),
        ).fetchone()
        if not row:
            return False
        
        if utc_now() > row["expires_at"]:
            return False
            
        if str(row["otp"]) != str(otp):
            return False
            
        conn.execute("DELETE FROM otps WHERE email = ?", (normalize_email(email),))
        return True


def hash_password(password: str) -> str:
    """Hash a password using PBKDF2-HMAC-SHA256.

    Generates a random salt and returns a formatted string containing
    the algorithm, iteration count, salt, and derived key.

    Args:
        password: The plaintext password.

    Returns:
        A string in the format ``pbkdf2_sha256$iterations$salt$hash``.
    """
    salt = secrets.token_urlsafe(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        PASSWORD_ITERATIONS,
    )
    encoded = base64.urlsafe_b64encode(digest).decode("ascii")
    return f"pbkdf2_sha256${PASSWORD_ITERATIONS}${salt}${encoded}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Verify a plaintext password against a stored PBKDF2 hash.

    Uses constant-time comparison to prevent timing attacks.

    Args:
        password: The plaintext password to check.
        stored_hash: The hash string produced by :func:`hash_password`.

    Returns:
        ``True`` if the password matches, ``False`` otherwise.
    """
    try:
        algorithm, iterations, salt, encoded_digest = stored_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            int(iterations),
        )
        expected = base64.urlsafe_b64encode(digest).decode("ascii")
        return hmac.compare_digest(expected, encoded_digest)
    except ValueError:
        return False


def b64url_encode(data: bytes) -> str:
    """Base64url-encode bytes without padding.

    Args:
        data: Raw bytes to encode.

    Returns:
        An unpadded base64url string.
    """
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def b64url_decode(data: str) -> bytes:
    """Decode a base64url string, restoring any stripped padding.

    Args:
        data: A base64url-encoded string (padding optional).

    Returns:
        The decoded bytes.
    """
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def create_access_token(user_id: str) -> str:
    """Create a minimal HS256 JWT access token for the given user.

    The token embeds the user ID as the ``sub`` claim and an expiration
    timestamp based on :data:`TOKEN_TTL_SECONDS`.

    Args:
        user_id: The unique user identifier to embed.

    Returns:
        A signed JWT string.
    """
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {"sub": user_id, "exp": int(time.time()) + TOKEN_TTL_SECONDS}
    signing_input = ".".join(
        [
            b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8")),
            b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8")),
        ]
    )
    signature = hmac.new(
        JWT_SECRET.encode("utf-8"),
        signing_input.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return f"{signing_input}.{b64url_encode(signature)}"


def decode_access_token(token: str) -> str:
    """Decode and verify an HS256 JWT, returning the user ID.

    Validates the signature and expiration claim. Raises an HTTP 401
    error if the token is invalid or expired.

    Args:
        token: The raw JWT string from the ``Authorization`` header.

    Returns:
        The ``sub`` (user ID) claim from the token payload.

    Raises:
        HTTPException: If the token is malformed, expired, or has an
            invalid signature.
    """
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        header, payload, signature = token.split(".", 2)
        signing_input = f"{header}.{payload}"
        expected_signature = hmac.new(
            JWT_SECRET.encode("utf-8"),
            signing_input.encode("ascii"),
            hashlib.sha256,
        ).digest()
        if not hmac.compare_digest(b64url_decode(signature), expected_signature):
            raise credentials_error
        body = json.loads(b64url_decode(payload))
        if int(body.get("exp", 0)) < int(time.time()):
            raise credentials_error
        user_id = body.get("sub")
        if not user_id:
            raise credentials_error
        return user_id
    except Exception as exc:
        if isinstance(exc, HTTPException):
            raise exc
        raise credentials_error from exc


def create_user(email: str, password: str) -> dict[str, Any]:
    """Create a new user account.

    Args:
        email: The user's email address.
        password: The plaintext password (will be hashed).

    Returns:
        A dict with ``id``, ``email``, and ``created_at`` keys.

    Raises:
        HTTPException: 409 if an account with the email already exists.
    """
    init_db()
    user = {
        "id": str(uuid.uuid4()),
        "email": normalize_email(email),
        "password_hash": hash_password(password),
        "created_at": utc_now(),
    }
    try:
        with connect() as conn:
            conn.execute(
                """
                INSERT INTO users (id, email, password_hash, created_at)
                VALUES (:id, :email, :password_hash, :created_at)
                """,
                user,
            )
    except sqlite3.IntegrityError as exc:
        raise HTTPException(status_code=409, detail="account exists with this email") from exc
    return {"id": user["id"], "email": user["email"], "created_at": user["created_at"]}


def get_user_by_email(email: str) -> sqlite3.Row | None:
    """Look up a user row by normalized email.

    Args:
        email: The email address to search for.

    Returns:
        A ``sqlite3.Row`` for the user, or ``None`` if not found.
    """
    init_db()
    with connect() as conn:
        return conn.execute(
            "SELECT * FROM users WHERE email = ?",
            (normalize_email(email),),
        ).fetchone()


def get_user_by_id(user_id: str) -> sqlite3.Row | None:
    """Look up a user row by primary key.

    Args:
        user_id: The UUID of the user.

    Returns:
        A ``sqlite3.Row`` for the user, or ``None`` if not found.
    """
    init_db()
    with connect() as conn:
        return conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


def public_user(row: sqlite3.Row) -> dict[str, Any]:
    """Project a user row into a public-safe dict (no password hash).

    Args:
        row: A full user ``sqlite3.Row``.

    Returns:
        A dict containing ``id``, ``email``, and ``created_at``.
    """
    return {"id": row["id"], "email": row["email"], "created_at": row["created_at"]}


def json_list(value: str | None) -> list[str]:
    """Safely parse a JSON string expected to be an array of strings.

    Returns an empty list on ``None``, empty string, or invalid JSON.

    Args:
        value: A JSON-encoded string or ``None``.

    Returns:
        The parsed list, or ``[]`` on any failure.
    """
    if not value:
        return []
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, list) else []
    except json.JSONDecodeError:
        return []


def session_state_from_record(row: sqlite3.Row, messages: list[SessionMessage]) -> SessionState:
    """Reconstruct a ``SessionState`` from a database row and its messages.

    Args:
        row: A ``sessions`` table row.
        messages: Ordered list of ``SessionMessage`` objects for this session.

    Returns:
        A fully populated ``SessionState`` instance.
    """
    return SessionState(
        title=row["title"],
        topic=row["topic"],
        messages=messages,
        hint_count=row["hint_count"],
        understanding_score=row["understanding_score"],
        jailbreak_threshold=row["jailbreak_threshold"],
        status=row["status"],
        struggle_areas=json_list(row["struggle_areas"]),
        concepts_mastered=json_list(row["concepts_mastered"]),
    )


def record_from_session(row: sqlite3.Row, messages: list[SessionMessage]) -> dict[str, Any]:
    """Build a full session dict from a database row and its messages.

    Combines the ``SessionState`` fields with database metadata
    (``id``, ``created_at``, ``updated_at``).

    Args:
        row: A ``sessions`` table row.
        messages: Ordered list of ``SessionMessage`` objects.

    Returns:
        A dict suitable for API responses.
    """
    state = session_state_from_record(row, messages)
    data = state.model_dump()
    data.update(
        {
            "id": row["id"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
    )
    return data


def load_messages(conn: sqlite3.Connection, session_id: str) -> list[SessionMessage]:
    """Load all messages for a session ordered by position.

    Args:
        conn: An open database connection.
        session_id: The session UUID to load messages for.

    Returns:
        A list of ``SessionMessage`` objects in chronological order.
    """
    rows = conn.execute(
        """
        SELECT role, content, hint_level, intent, learning_state, strategy, timestamp
        FROM messages
        WHERE session_id = ?
        ORDER BY position ASC
        """,
        (session_id,),
    ).fetchall()
    return [SessionMessage(**dict(row)) for row in rows]


def create_session(user_id: str) -> dict[str, Any]:
    """Create a new empty tutoring session for the given user.

    Args:
        user_id: The owning user's UUID.

    Returns:
        A full session dict including metadata.
    """
    init_db()
    now = utc_now()
    session_id = str(uuid.uuid4())
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO sessions (
                id, user_id, title, topic, hint_count, understanding_score,
                jailbreak_threshold, status, struggle_areas, concepts_mastered,
                created_at, updated_at
            )
            VALUES (?, ?, 'New Session', 'CS/Programming', 0, 0, 70, 'active', '[]', '[]', ?, ?)
            """,
            (session_id, user_id, now, now),
        )
        row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
        return record_from_session(row, [])


def list_sessions(user_id: str) -> list[dict[str, Any]]:
    """List all sessions for a user, most recently updated first.

    Args:
        user_id: The owning user's UUID.

    Returns:
        A list of session dicts, each including its messages.
    """
    init_db()
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT * FROM sessions
            WHERE user_id = ?
            ORDER BY updated_at DESC
            """,
            (user_id,),
        ).fetchall()
        return [record_from_session(row, load_messages(conn, row["id"])) for row in rows]


def get_session(user_id: str, session_id: str) -> dict[str, Any]:
    """Retrieve a single session by ID, scoped to the user.

    Args:
        user_id: The owning user's UUID.
        session_id: The session UUID.

    Returns:
        A full session dict.

    Raises:
        HTTPException: 404 if the session does not exist or belongs
            to a different user.
    """
    init_db()
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM sessions WHERE id = ? AND user_id = ?",
            (session_id, user_id),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Session not found.")
        return record_from_session(row, load_messages(conn, session_id))


def save_session_state(user_id: str, session_id: str, state: SessionState) -> dict[str, Any]:
    """Persist an updated session state and its messages.

    Replaces all session columns and re-inserts messages in order.

    Args:
        user_id: The owning user's UUID.
        session_id: The session UUID.
        state: The new ``SessionState`` to persist.

    Returns:
        The refreshed session dict after saving.

    Raises:
        HTTPException: 404 if the session does not exist or belongs
            to a different user.
    """
    init_db()
    now = utc_now()
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM sessions WHERE id = ? AND user_id = ?",
            (session_id, user_id),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Session not found.")

        conn.execute(
            """
            UPDATE sessions
            SET title = ?, topic = ?, hint_count = ?, understanding_score = ?,
                jailbreak_threshold = ?, status = ?, struggle_areas = ?,
                concepts_mastered = ?, updated_at = ?
            WHERE id = ? AND user_id = ?
            """,
            (
                state.title,
                state.topic,
                state.hint_count,
                state.understanding_score,
                state.jailbreak_threshold,
                state.status,
                json.dumps(state.struggle_areas),
                json.dumps(state.concepts_mastered),
                now,
                session_id,
                user_id,
            ),
        )
        conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        conn.executemany(
            """
            INSERT INTO messages (
                id, session_id, role, content, hint_level, intent,
                learning_state, strategy, timestamp, position
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    str(uuid.uuid4()),
                    session_id,
                    message.role,
                    message.content,
                    message.hint_level,
                    message.intent,
                    message.learning_state,
                    message.strategy,
                    message.timestamp,
                    index,
                )
                for index, message in enumerate(state.messages)
            ],
        )
        updated = conn.execute(
            "SELECT * FROM sessions WHERE id = ? AND user_id = ?",
            (session_id, user_id),
        ).fetchone()
        return record_from_session(updated, load_messages(conn, session_id))


def delete_session(user_id: str, session_id: str) -> None:
    """Delete a session and its messages (via CASCADE).

    Args:
        user_id: The owning user's UUID.
        session_id: The session UUID to delete.

    Raises:
        HTTPException: 404 if the session does not exist or belongs
            to a different user.
    """
    init_db()
    with connect() as conn:
        cursor = conn.execute(
            "DELETE FROM sessions WHERE id = ? AND user_id = ?",
            (session_id, user_id),
        )
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Session not found.")
