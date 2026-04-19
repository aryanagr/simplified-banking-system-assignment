"""End-to-end tests for the simplified banking API."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from banking_api.database import BankingDatabase
from banking_api.service import ApiError, BankingService, extract_bearer_token


class BankingAPITestCase(unittest.TestCase):
    def setUp(self):
        """Create an isolated temporary database for each test case."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_dir.name) / "test-bank.db"
        self.database = BankingDatabase(self.database_path)
        self.database.initialize()
        self.service = BankingService(self.database)

    def tearDown(self):
        """Dispose of the temporary database created for the test."""
        self.temp_dir.cleanup()

    def test_login_returns_token(self):
        """Login should succeed for a valid seeded user and return a token."""
        response = self.service.login("alice@example.com", "1234")
        self.assertIn("token", response)
        self.assertEqual(response["user"]["email"], "alice@example.com")

    def test_invalid_login_is_rejected(self):
        """Login should fail when the provided PIN does not match the user."""
        with self.assertRaises(ApiError) as context:
            self.service.login("alice@example.com", "9999")

        self.assertEqual(context.exception.status_code, 401)
        self.assertEqual(context.exception.message, "Invalid email or PIN.")

    def test_balance_requires_valid_token(self):
        """Protected operations should reject missing bearer tokens."""
        with self.assertRaises(ApiError) as context:
            extract_bearer_token("")

        self.assertEqual(context.exception.status_code, 401)
        self.assertEqual(
            context.exception.message,
            "Missing or invalid Authorization header.",
        )

    def test_balance_and_deposit_flow(self):
        """A valid session should be able to read balance and perform a deposit."""
        login_response = self.service.login("bob@example.com", "5678")
        token = login_response["token"]

        balance_response = self.service.get_balance(token)
        self.assertEqual(balance_response["balance"], "500.00")

        deposit_response = self.service.deposit(token, "25.50")
        self.assertEqual(deposit_response["deposited"], "25.50")
        self.assertEqual(deposit_response["balance"], "525.50")
        self.assertEqual(deposit_response["transaction"]["type"], "deposit")
        self.assertEqual(deposit_response["transaction"]["amount"], "25.50")
        self.assertEqual(deposit_response["transaction"]["balance_after"], "525.50")

    def test_deposit_rejects_non_positive_amounts(self):
        """Deposits should reject zero or negative values."""
        login_response = self.service.login("alice@example.com", "1234")

        with self.assertRaises(ApiError) as context:
            self.service.deposit(login_response["token"], 0)

        self.assertEqual(context.exception.status_code, 400)
        self.assertEqual(
            context.exception.message,
            "Deposit amount must be greater than zero.",
        )

    def test_seed_data_creates_opening_balance_transactions(self):
        """The initial seeded balances should also be recorded as transactions."""
        with self.database._connect() as connection:
            rows = connection.execute(
                """
                SELECT transaction_type, amount_cents
                FROM transactions
                ORDER BY id
                """
            ).fetchall()

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["transaction_type"], "opening_balance")
        self.assertEqual(rows[0]["amount_cents"], 1000_00)
        self.assertEqual(rows[1]["transaction_type"], "opening_balance")
        self.assertEqual(rows[1]["amount_cents"], 500_00)

    def test_expired_session_is_rejected(self):
        """Expired sessions should not authorize any protected action."""
        login_response = self.service.login("alice@example.com", "1234")
        token = login_response["token"]

        with self.database._connect() as connection:
            connection.execute(
                "UPDATE sessions SET expires_at = 0 WHERE token = ?",
                (token,),
            )

        with self.assertRaises(ApiError) as context:
            self.service.get_balance(token)

        self.assertEqual(context.exception.status_code, 401)
        self.assertEqual(context.exception.message, "Invalid or expired token.")


if __name__ == "__main__":
    unittest.main()
