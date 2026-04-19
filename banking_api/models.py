"""Domain records for the simplified banking system."""

from __future__ import annotations

from dataclasses import dataclass

from banking_api.money import format_cents


@dataclass
class UserRecord:
    """Represents an authenticated banking user."""

    id: int
    name: str
    email: str
    balance_cents: int

    def to_public_dict(self) -> dict:
        """Convert the user record into a safe API response shape."""
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
        }


@dataclass
class TransactionRecord:
    """Represents a persisted balance-changing transaction."""

    id: int
    transaction_type: str
    amount_cents: int
    balance_after_cents: int
    created_at: str

    def to_public_dict(self) -> dict:
        """Convert the transaction record into a client-facing response shape."""
        return {
            "id": self.id,
            "type": self.transaction_type,
            "amount": format_cents(self.amount_cents),
            "balance_after": format_cents(self.balance_after_cents),
            "created_at": self.created_at,
        }

