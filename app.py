"""Entrypoint for the simplified banking system assignment."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from banking_api.config import AppConfig
from banking_api.database import BankingDatabase
from banking_api.service import BankingService
from banking_api.server import create_server

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DATABASE_PATH = BASE_DIR / "bank.db"


def build_server(
    config: Optional[AppConfig] = None,
    host: str = "127.0.0.1",
    port: int = 8000,
    database_path: Optional[Path] = None,
):
    """Create a fully configured server instance for local execution or tests."""
    runtime_config = config or AppConfig(
        host=host,
        port=port,
        database_path=database_path or DEFAULT_DATABASE_PATH,
        session_ttl_seconds=3600,
        sqlite_timeout_seconds=5.0,
        max_request_body_bytes=16_384,
        currency="USD",
        log_level="INFO",
    )

    database = BankingDatabase(
        runtime_config.database_path,
        session_ttl_seconds=runtime_config.session_ttl_seconds,
        sqlite_timeout_seconds=runtime_config.sqlite_timeout_seconds,
    )
    database.initialize()
    service = BankingService(database, currency=runtime_config.currency)
    return create_server(
        host=runtime_config.host,
        port=runtime_config.port,
        service=service,
        max_request_body_bytes=runtime_config.max_request_body_bytes,
    )


def main() -> None:
    """Load runtime configuration, start the API server, and handle shutdown."""
    config = AppConfig.from_env(BASE_DIR)
    config.configure_logging()

    server = build_server(config=config)
    print(f"Banking API running on http://{config.host}:{config.port}")
    print(f"SQLite database: {config.database_path}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
