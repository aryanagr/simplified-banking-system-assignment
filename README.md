# Simplified Banking System

This project is a small REST API for a simplified banking system. It supports:

1. `POST /login` to authenticate a user using email and PIN
2. `GET /balance` to fetch the current account balance
3. `POST /deposit` to add funds to an account

The application uses a real SQLite database and seeds two demo users on first run:

- Alice: `alice@example.com` / `1234` / starting balance `1000.00`
- Bob: `bob@example.com` / `5678` / starting balance `500.00`

## Tech Stack

- Python 3.9+
- SQLite
- Standard library HTTP server

## Architecture

The application is organized into small layers:

- `server.py`: HTTP transport and request/response handling
- `service.py`: business use cases
- `database.py`: SQLite persistence
- `models.py`: domain records
- `money.py`: money parsing and formatting helpers
- `contracts.py`: abstraction boundaries between layers

Key implementation choices:

- PINs are stored as salted PBKDF2 hashes, not plain text
- balances are stored as integer cents to avoid floating-point errors
- sessions are token-based and time-bound
- deposits are recorded in a `transactions` table for basic auditability

## Project Structure

```text
test website/
├── app.py
├── bank.db                # created automatically on first run
├── banking_api/
│   ├── contracts.py
│   ├── database.py
│   ├── models.py
│   ├── money.py
│   ├── security.py
│   ├── service.py
│   └── server.py
├── tests/
│   └── test_api.py
└── README.md
```

## Getting Started

### Prerequisites

- Python 3.9 or newer
- `curl` for testing the endpoints from the terminal

No third-party Python packages are required.

### Run locally

If you are starting from a fresh clone:

```bash
git clone git@github.com-personal:aryanagr/simplified-banking-system-assignment.git
cd simplified-banking-system-assignment
```

If you already have the project locally, just open the project directory and run:

```bash
python3 app.py
```

The API starts at `http://127.0.0.1:8000`.

### Verify that it is running

Open a new terminal and call the health endpoint:

```bash
curl http://127.0.0.1:8000/health
```

Expected response:

```json
{"status": "ok"}
```

### Stop the server

Press `Ctrl + C` in the terminal where `python3 app.py` is running.

### Configuration

Optional environment variables:

```bash
BANK_API_HOST=127.0.0.1
BANK_API_PORT=8000
BANK_API_DB_PATH=./bank.db
BANK_API_CURRENCY=USD
BANK_API_SESSION_TTL_SECONDS=3600
BANK_API_SQLITE_TIMEOUT_SECONDS=5
BANK_API_MAX_BODY_BYTES=16384
BANK_API_LOG_LEVEL=INFO
```

## API Endpoints

### Health check

```bash
curl http://127.0.0.1:8000/health
```

### Login

```bash
curl -X POST http://127.0.0.1:8000/login \
  -H "Content-Type: application/json" \
  -d '{"email":"alice@example.com","pin":"1234"}'
```

Example success response:

```json
{
  "message": "Login successful.",
  "token": "your_token_here",
  "user": {
    "id": 1,
    "name": "Alice",
    "email": "alice@example.com"
  }
}
```

### Balance

```bash
curl http://127.0.0.1:8000/balance \
  -H "Authorization: Bearer your_token_here"
```

Example response:

```json
{
  "user": {
    "id": 1,
    "name": "Alice",
    "email": "alice@example.com"
  },
  "balance": "1000.00",
  "currency": "USD"
}
```

### Deposit

```bash
curl -X POST http://127.0.0.1:8000/deposit \
  -H "Authorization: Bearer your_token_here" \
  -H "Content-Type: application/json" \
  -d '{"amount":"250.00"}'
```

Example response:

```json
{
  "message": "Deposit successful.",
  "deposited": "250.00",
  "balance": "1250.00",
  "currency": "USD",
  "transaction": {
    "id": 3,
    "type": "deposit",
    "amount": "250.00",
    "balance_after": "1250.00",
    "created_at": "2026-04-18 14:30:00"
  }
}
```

## Error Handling

The API returns JSON errors with appropriate HTTP status codes for:

- invalid email or PIN
- missing or invalid bearer token
- expired bearer token
- non-positive deposit amounts
- invalid JSON or missing required fields
- unsupported content type
- oversized request bodies
- database or unexpected server errors

Example:

```json
{
  "error": "Invalid email or PIN."
}
```

## Running Tests

Run the automated tests with:

```bash
cd "test website"
python3 -m unittest discover -s tests -v
```

## Notes

- Seed users are inserted only if they do not already exist
- rerunning the app does not reset balances automatically
- deleting `bank.db` will recreate the database with the original seeded values
- deposit amounts support up to 2 decimal places

## Future Enhancements

- Move to PostgreSQL and add database migrations.
- Add logout, session revocation, and stronger authentication controls.
- Use a ledger-style model for all balance changes, including withdrawals and transfers.
- Add request logging, structured monitoring, and rate limiting.
- Add API-level integration tests that hit the running HTTP server outside the sandbox.
