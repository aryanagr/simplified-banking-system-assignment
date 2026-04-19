"""Protocols that define the core banking dependencies."""

from __future__ import annotations

from typing import Any, Optional, Protocol

from banking_api.models import TransactionRecord, UserRecord


class BankingRepository(Protocol):
    """Persistence contract required by the banking service."""

    def authenticate_user(self, email: str, pin: str) -> Optional[UserRecord]:
        """Return the user for valid credentials or `None` when authentication fails."""

    def create_session(self, user_id: int) -> str:
        """Create and persist a bearer session for the given user."""

    def get_user_by_token(self, token: str) -> Optional[UserRecord]:
        """Resolve a bearer token into the current authenticated user."""

    def deposit(self, user_id: int, amount_cents: int) -> TransactionRecord:
        """Apply a deposit and return the persisted transaction record."""

    def get_balance(self, user_id: int) -> int:
        """Return the current balance for the supplied user."""


class BankingUseCases(Protocol):
    """Application use-case contract consumed by the HTTP layer."""

    def login(self, email_raw: Any, pin_raw: Any) -> dict[str, Any]:
        """Authenticate a user and return the login response payload."""

    def get_balance(self, token: str) -> dict[str, Any]:
        """Return the balance response payload for the authenticated user."""

    def deposit(self, token: str, raw_amount: Any) -> dict[str, Any]:
        """Perform a deposit and return the deposit response payload."""

