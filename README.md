# Simplified Banking System

This project is a small REST API that implements the three required assignment features:

1. `POST /login` authenticates a user with email and PIN.
2. `GET /balance` returns the authenticated user's current balance.
3. `POST /deposit` adds funds to the authenticated user's account.

The application uses a real SQLite database and automatically seeds the required users on first run:

- Alice: `alice@example.com` / `1234` / starting balance `1000.00`
- Bob: `bob@example.com` / `5678` / starting balance `500.00`

## Design Thought Process

I tried to optimize for three things:

- **Clarity**: the code should be easy to explain in an interview.
- **Correctness for the assignment scope**: real persistence, basic authentication, safe money handling, and clear errors.
- **Small surface area**: enough structure to show good design, but not so much that the assignment becomes over-engineered.

That led to a simple layered design:

- **HTTP layer**: parses requests and returns JSON responses.
- **Service layer**: holds the business rules for login, balance lookup, and deposit.
- **Database layer**: owns SQLite queries, transactions, and seed data.

I also treated maintainability as part of the design. Each method in the codebase now has a short docstring explaining its responsibility, so the implementation is easier to review and discuss during the interview.

## Why I Chose This Approach

- **Language**: Python 3 because it is quick to read, easy to run locally, and lets me keep the code focused on the API behavior instead of framework boilerplate.
- **Database**: SQLite because the assignment asked for a real database and SQLite keeps setup simple for a local take-home exercise.
- **Structure**: I separated the code into a database layer, a service layer, security helpers, and the HTTP server so the responsibilities stay clear and the code is easier to explain in a follow-up interview.
- **Authentication choice**: Login returns a bearer token stored in the database, which keeps the authenticated endpoints simple to test from `curl` or Postman.
- **Session management**: Sessions have an expiration time and expired sessions are cleaned up from the database.
- **Money handling**: Balances are stored as integer cents in the database to avoid floating-point rounding issues.
- **Auditability**: Every seeded opening balance and every deposit is written to a `transactions` table, so balance changes are not just updates to a single number.
- **Operational hardening**: The server validates configuration from environment variables, enforces JSON request bodies, limits request size, and applies SQLite settings for better concurrency and reliability.
- **Dependencies**: The runtime uses only the Python standard library, so the project can be started immediately without installing extra packages.

## Data Model

The database has three tables:

- `users`: stores the customer identity, hashed PIN, and current balance in cents.
- `sessions`: stores bearer tokens created after login along with an expiration timestamp.
- `transactions`: stores opening balances and deposits as an audit trail.

I kept the current balance on the `users` table for quick reads from `/balance`, while also writing each deposit to `transactions` so the system still has a simple history of balance-changing events. For a take-home assignment, this is a good middle ground between simplicity and traceability.

## Project Structure

```text
test website/
├── app.py
├── bank.db                # created automatically on first run
├── banking_api/
│   ├── database.py
│   ├── security.py
│   ├── service.py
│   └── server.py
├── tests/
│   └── test_api.py
└── README.md
```

## Setup And Run

### Prerequisites

- Python 3.9+

### Start the API

From the `test website` folder:

```bash
cd "test website"
python3 app.py
```

The server starts on `http://127.0.0.1:8000` by default.

Optional environment variables:

```bash
BANK_API_HOST=127.0.0.1
BANK_API_PORT=8000
BANK_API_DB_PATH=./bank.db
BANK_API_SESSION_TTL_SECONDS=3600
BANK_API_SQLITE_TIMEOUT_SECONDS=5
BANK_API_MAX_BODY_BYTES=16384
BANK_API_LOG_LEVEL=INFO
```

## How To Test The APIs

### 1. Login

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

### 2. Balance

Use the token returned by `/login`:

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

### 3. Deposit

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

## Automated Tests

Run the included tests with:

```bash
cd "test website"
python3 -m unittest discover -s tests -v
```

The tests cover the main login, balance, and deposit flows through the shared service layer that powers the REST API, and also verify that seeded balances are recorded as transaction entries.
They also verify that expired sessions are rejected.

## Error Handling

The API returns clear JSON errors for the required cases:

- Invalid email or PIN: `401 Unauthorized`
- Missing or invalid bearer token: `401 Unauthorized`
- Expired bearer token: `401 Unauthorized`
- Depositing a non-positive amount: `400 Bad Request`
- Invalid JSON body or missing required fields: `400 Bad Request`
- Unsupported content type: `415 Unsupported Media Type`
- Oversized request body: `413 Request Entity Too Large`
- Database errors: `500 Internal Server Error`
- Unexpected errors: `500 Internal Server Error`

Example error response:

```json
{
  "error": "Invalid email or PIN."
}
```

## Assumptions

- This implementation is production-oriented for the requested scope, but the business scope remains intentionally limited to login, balance, and deposit.
- A successful login creates a bearer token and the protected endpoints use that token.
- Sessions expire after `BANK_API_SESSION_TTL_SECONDS` seconds.
- Seed users are inserted only if they do not already exist, so rerunning the app does not overwrite balances.
- To reset the database back to the original seeded balances, delete `bank.db` and start the server again.
- Deposit supports amounts with up to two decimal places.
- SQLite timestamps are generated by the database and stored in UTC-style text format.

## Scope Boundaries

- No signup, withdrawal, transfer, or logout endpoints because they were outside the assignment scope.
- The API does not include authorization roles, rate limiting, or advanced validation rules.
- There is no ORM; direct SQL keeps the project compact and transparent.

## Possible Future Enhancements

- Move to PostgreSQL and add database migrations.
- Add logout, session revocation, and stronger authentication controls.
- Use a ledger-style model for all balance changes, including withdrawals and transfers.
- Add request logging, structured monitoring, and rate limiting.
- Add API-level integration tests that hit the running HTTP server outside the sandbox.
