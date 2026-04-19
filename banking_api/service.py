"""Business logic for the simplified banking API."""

from __future__ import annotations

from http import HTTPStatus
from typing import Any

from banking_api.contracts import BankingRepository
from banking_api.money import format_cents, parse_amount_to_cents


class ApiError(Exception):
    """Represents a client-safe API error with an HTTP status code."""

    def __init__(self, status_code: int, message: str):
        """Create a transport-friendly error that can be serialized as JSON."""
        super().__init__(message)
        self.status_code = status_code
        self.message = message


def extract_bearer_token(header_value: str) -> str:
    """Extract and validate a bearer token from the Authorization header."""
    if not header_value.startswith("Bearer "):
        raise ApiError(
            HTTPStatus.UNAUTHORIZED,
            "Missing or invalid Authorization header.",
        )

    token = header_value[len("Bearer ") :].strip()
    if not token:
        raise ApiError(HTTPStatus.UNAUTHORIZED, "Authentication token is required.")

    return token


class BankingService:
    """Implements the core banking use cases exposed by the API."""

    def __init__(self, repository: BankingRepository, currency: str = "USD"):
        """Create the service with the repository and response currency settings."""
        self.repository = repository
        self.currency = currency

    def login(self, email_raw: Any, pin_raw: Any) -> dict[str, Any]:
        """Validate login input, authenticate the user, and create a session token."""
        email = str(email_raw or "").strip().lower()
        pin = str(pin_raw or "").strip()

        if not email or not pin:
            raise ApiError(
                HTTPStatus.BAD_REQUEST,
                "Both email and PIN are required.",
            )

        user = self.repository.authenticate_user(email=email, pin=pin)
        if user is None:
            raise ApiError(HTTPStatus.UNAUTHORIZED, "Invalid email or PIN.")

        token = self.repository.create_session(user.id)
        return {
            "message": "Login successful.",
            "token": token,
            "user": user.to_public_dict(),
        }

    def get_balance(self, token: str) -> dict[str, Any]:
        """Return the current balance for the user behind the provided bearer token."""
        user = self._require_authenticated_user(token)
        balance_cents = self.repository.get_balance(user.id)
        return {
            "user": user.to_public_dict(),
            "balance": format_cents(balance_cents),
            "currency": self.currency,
        }

    def deposit(self, token: str, raw_amount: Any) -> dict[str, Any]:
        """Validate a deposit request, persist it, and return the updated balance."""
        user = self._require_authenticated_user(token)
        if raw_amount is None:
            raise ApiError(HTTPStatus.BAD_REQUEST, "Amount is required.")

        try:
            amount_cents = parse_amount_to_cents(raw_amount)
        except ValueError as error:
            raise ApiError(HTTPStatus.BAD_REQUEST, str(error))

        transaction = self.repository.deposit(user.id, amount_cents)
        return {
            "message": "Deposit successful.",
            "deposited": format_cents(amount_cents),
            "balance": format_cents(transaction.balance_after_cents),
            "currency": self.currency,
            "transaction": transaction.to_public_dict(),
        }

    def _require_authenticated_user(self, token: str):
        """Resolve the provided token into an authenticated user or raise an error."""
        normalized_token = str(token or "").strip()
        if not normalized_token:
            raise ApiError(HTTPStatus.UNAUTHORIZED, "Authentication token is required.")

        user = self.repository.get_user_by_token(normalized_token)
        if user is None:
            raise ApiError(HTTPStatus.UNAUTHORIZED, "Invalid or expired token.")

        return user
