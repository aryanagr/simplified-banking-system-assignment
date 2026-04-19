"""Configuration helpers for the banking API."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path


def _read_int_env(name: str, default: int) -> int:
    """Read an integer environment variable and validate that it is numeric."""
    raw_value = os.getenv(name)
    if raw_value is None:
        return default

    try:
        return int(raw_value)
    except ValueError as exc:
        raise ValueError(f"{name} must be a valid integer.") from exc


def _read_positive_int_env(name: str, default: int) -> int:
    """Read a positive integer environment variable."""
    value = _read_int_env(name, default)
    if value <= 0:
        raise ValueError(f"{name} must be greater than zero.")
    return value


def _read_positive_float_env(name: str, default: float) -> float:
    """Read a positive float environment variable."""
    raw_value = os.getenv(name)
    if raw_value is None:
        return default

    try:
        value = float(raw_value)
    except ValueError as exc:
        raise ValueError(f"{name} must be a valid number.") from exc

    if value <= 0:
        raise ValueError(f"{name} must be greater than zero.")

    return value


@dataclass(frozen=True)
class AppConfig:
    """Stores validated runtime configuration for the API process."""

    host: str
    port: int
    database_path: Path
    session_ttl_seconds: int
    sqlite_timeout_seconds: float
    max_request_body_bytes: int
    currency: str
    log_level: str

    @classmethod
    def from_env(cls, base_dir: Path) -> "AppConfig":
        """Build the application configuration from environment variables."""
        host = os.getenv("BANK_API_HOST", "127.0.0.1").strip() or "127.0.0.1"
        port = _read_positive_int_env("BANK_API_PORT", 8000)
        if port > 65535:
            raise ValueError("BANK_API_PORT must be between 1 and 65535.")

        database_path = Path(os.getenv("BANK_API_DB_PATH", str(base_dir / "bank.db")))
        session_ttl_seconds = _read_positive_int_env("BANK_API_SESSION_TTL_SECONDS", 3600)
        sqlite_timeout_seconds = _read_positive_float_env("BANK_API_SQLITE_TIMEOUT_SECONDS", 5.0)
        max_request_body_bytes = _read_positive_int_env("BANK_API_MAX_BODY_BYTES", 16_384)
        currency = os.getenv("BANK_API_CURRENCY", "USD").strip().upper() or "USD"
        log_level = os.getenv("BANK_API_LOG_LEVEL", "INFO").strip().upper() or "INFO"

        if log_level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ValueError("BANK_API_LOG_LEVEL must be a valid Python logging level.")

        return cls(
            host=host,
            port=port,
            database_path=database_path,
            session_ttl_seconds=session_ttl_seconds,
            sqlite_timeout_seconds=sqlite_timeout_seconds,
            max_request_body_bytes=max_request_body_bytes,
            currency=currency,
            log_level=log_level,
        )

    def configure_logging(self) -> None:
        """Configure application logging using the validated log level."""
        logging.basicConfig(
            level=getattr(logging, self.log_level),
            format="%(asctime)s %(levelname)s %(message)s",
        )

