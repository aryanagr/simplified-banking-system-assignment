"""SQLite-backed persistence helpers for the banking API."""

from __future__ import annotations

import secrets
import sqlite3
import time
from pathlib import Path
from typing import Optional

from banking_api.models import TransactionRecord, UserRecord
from banking_api.security import hash_pin, verify_pin
 
SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    pin_salt TEXT NOT NULL,
    pin_hash TEXT NOT NULL,
    balance_cents INTEGER NOT NULL CHECK (balance_cents >= 0),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sessions (
    token TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at INTEGER,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    transaction_type TEXT NOT NULL CHECK (transaction_type IN ('opening_balance', 'deposit')),
    amount_cents INTEGER NOT NULL CHECK (amount_cents > 0),
    balance_after_cents INTEGER NOT NULL CHECK (balance_after_cents >= 0),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_transactions_user_id ON transactions(user_id);
"""


class BankingDatabase:
    """Encapsulates all SQLite access for users, sessions, and transactions."""

    def __init__(
        self,
        database_path: Path,
        session_ttl_seconds: int = 3600,
        sqlite_timeout_seconds: float = 5.0,
    ):
        """Create a database helper with runtime persistence settings."""
        self.database_path = Path(database_path)
        self.session_ttl_seconds = session_ttl_seconds
        self.sqlite_timeout_seconds = sqlite_timeout_seconds

    def initialize(self) -> None:
        """Create the schema, apply lightweight migrations, and seed base data."""
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(SCHEMA)
            self._migrate_schema(connection)
            self._create_indexes(connection)
            self._seed_users(connection)
            self.purge_expired_sessions(connection)

    def authenticate_user(self, email: str, pin: str) -> Optional[UserRecord]:
        """Authenticate a user by email and PIN and return the matching user record."""
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT id, name, email, pin_salt, pin_hash, balance_cents
                FROM users
                WHERE email = ?
                """,
                (email,),
            ).fetchone()

        if row is None:
            return None

        if not verify_pin(pin, row["pin_salt"], row["pin_hash"]):
            return None

        return self._build_user_record(row)

    def create_session(self, user_id: int) -> str:
        """Create a time-bound bearer session for an authenticated user."""
        token = secrets.token_urlsafe(32)
        expires_at = int(time.time()) + self.session_ttl_seconds
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO sessions (token, user_id, expires_at)
                VALUES (?, ?, ?)
                """,
                (token, user_id, expires_at),
            )
        return token

    def get_user_by_token(self, token: str) -> Optional[UserRecord]:
        """Resolve a bearer token into an authenticated user if the session is active."""
        current_epoch = int(time.time())
        with self._connect() as connection:
            self.purge_expired_sessions(connection)
            row = connection.execute(
                """
                SELECT users.id, users.name, users.email, users.balance_cents
                FROM sessions
                JOIN users ON users.id = sessions.user_id
                WHERE sessions.token = ?
                  AND sessions.expires_at > ?
                """,
                (token, current_epoch),
            ).fetchone()

        if row is None:
            return None

        return self._build_user_record(row)

    def deposit(self, user_id: int, amount_cents: int) -> TransactionRecord:
        """Atomically deposit funds and record the operation in the transaction log."""
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            cursor = connection.execute(
                """
                UPDATE users
                SET balance_cents = balance_cents + ?
                WHERE id = ?
                """,
                (amount_cents, user_id),
            )

            if cursor.rowcount != 1:
                raise LookupError("User not found.")

            row = connection.execute(
                "SELECT balance_cents FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()

            if row is None:
                raise LookupError("User not found.")

            transaction_cursor = connection.execute(
                """
                INSERT INTO transactions (
                    user_id,
                    transaction_type,
                    amount_cents,
                    balance_after_cents
                )
                VALUES (?, 'deposit', ?, ?)
                """,
                (user_id, amount_cents, row["balance_cents"]),
            )

            transaction_row = connection.execute(
                """
                SELECT id, transaction_type, amount_cents, balance_after_cents, created_at
                FROM transactions
                WHERE id = ?
                """,
                (transaction_cursor.lastrowid,),
            ).fetchone()

        if transaction_row is None:
            raise LookupError("Transaction not found.")

        return self._build_transaction_record(transaction_row)

    def get_balance(self, user_id: int) -> int:
        """Return the current account balance for a specific user."""
        with self._connect() as connection:
            row = connection.execute(
                "SELECT balance_cents FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()

        if row is None:
            raise LookupError("User not found.")

        return row["balance_cents"]

    def purge_expired_sessions(self, connection: Optional[sqlite3.Connection] = None) -> int:
        """Delete expired sessions and return the number of removed rows."""
        current_epoch = int(time.time())

        if connection is not None:
            cursor = connection.execute(
                "DELETE FROM sessions WHERE expires_at IS NOT NULL AND expires_at <= ?",
                (current_epoch,),
            )
            return cursor.rowcount

        with self._connect() as managed_connection:
            cursor = managed_connection.execute(
                "DELETE FROM sessions WHERE expires_at IS NOT NULL AND expires_at <= ?",
                (current_epoch,),
            )
            return cursor.rowcount

    def _connect(self) -> sqlite3.Connection:
        """Create a SQLite connection with the pragmas needed by the service."""
        connection = sqlite3.connect(
            self.database_path,
            timeout=self.sqlite_timeout_seconds,
        )
        connection.row_factory = sqlite3.Row
        self._apply_pragmas(connection)
        return connection

    def _apply_pragmas(self, connection: sqlite3.Connection) -> None:
        """Apply SQLite runtime settings that improve durability and concurrency."""
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA synchronous = NORMAL")
        connection.execute(f"PRAGMA busy_timeout = {int(self.sqlite_timeout_seconds * 1000)}")

    def _migrate_schema(self, connection: sqlite3.Connection) -> None:
        """Apply lightweight schema migrations required for backward compatibility."""
        session_columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(sessions)").fetchall()
        }
        if "expires_at" not in session_columns:
            connection.execute("ALTER TABLE sessions ADD COLUMN expires_at INTEGER")
            connection.execute(
                """
                UPDATE sessions
                SET expires_at = ?
                WHERE expires_at IS NULL
                """,
                (int(time.time()) + self.session_ttl_seconds,),
            )

    def _create_indexes(self, connection: sqlite3.Connection) -> None:
        """Create indexes after migrations so they match the final schema."""
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_sessions_expires_at ON sessions(expires_at)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_transactions_user_id ON transactions(user_id)"
        )

    def _seed_users(self, connection: sqlite3.Connection) -> None:
        """Insert the required assignment users if they are not already present."""
        seeded_users = (
            ("Alice", "alice@example.com", "1234", 1000_00),
            ("Bob", "bob@example.com", "5678", 500_00),
        )

        for name, email, pin, balance_cents in seeded_users:
            existing_user = connection.execute(
                "SELECT id FROM users WHERE email = ?",
                (email,),
            ).fetchone()
            if existing_user is not None:
                continue

            salt_hex, pin_hash_hex = hash_pin(pin)
            cursor = connection.execute(
                """
                INSERT INTO users (name, email, pin_salt, pin_hash, balance_cents)
                VALUES (?, ?, ?, ?, ?)
                """,
                (name, email, salt_hex, pin_hash_hex, balance_cents),
            )
            self._create_opening_balance_transaction(
                connection=connection,
                user_id=cursor.lastrowid,
                balance_cents=balance_cents,
            )

    def _create_opening_balance_transaction(
        self,
        connection: sqlite3.Connection,
        user_id: int,
        balance_cents: int,
    ) -> None:
        """Record the initial seeded balance for a newly inserted user."""
        connection.execute(
            """
            INSERT INTO transactions (
                user_id,
                transaction_type,
                amount_cents,
                balance_after_cents
            )
            VALUES (?, 'opening_balance', ?, ?)
            """,
            (user_id, balance_cents, balance_cents),
        )

    def _build_user_record(self, row: sqlite3.Row) -> UserRecord:
        """Hydrate a database row into a user record object."""
        return UserRecord(
            id=row["id"],
            name=row["name"],
            email=row["email"],
            balance_cents=row["balance_cents"],
        )

    def _build_transaction_record(self, row: sqlite3.Row) -> TransactionRecord:
        """Hydrate a database row into a transaction record object."""
        return TransactionRecord(
            id=row["id"],
            transaction_type=row["transaction_type"],
            amount_cents=row["amount_cents"],
            balance_after_cents=row["balance_after_cents"],
            created_at=row["created_at"],
        )
