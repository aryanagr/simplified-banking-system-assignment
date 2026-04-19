"""Helpers for validating and formatting money values."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any


def parse_amount_to_cents(raw_amount: Any) -> int:
    """Parse an API amount value into integer cents."""
    try:
        amount = Decimal(str(raw_amount))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError("Amount must be a valid number.") from exc

    if amount <= 0:
        raise ValueError("Deposit amount must be greater than zero.")

    normalized = amount.quantize(Decimal("0.01"))
    if normalized != amount:
        raise ValueError("Amount cannot have more than 2 decimal places.")

    return int(normalized * 100)


def format_cents(cents: int) -> str:
    """Format integer cents as a two-decimal currency string."""
    return format(Decimal(cents) / Decimal("100"), ".2f")

