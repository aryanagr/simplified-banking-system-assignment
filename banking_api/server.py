"""HTTP server for the simplified banking system."""

from __future__ import annotations

import json
import logging
import secrets
import sqlite3
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

from banking_api.contracts import BankingUseCases
from banking_api.service import ApiError, extract_bearer_token

LOGGER = logging.getLogger(__name__)


class BankingHTTPServer(ThreadingHTTPServer):
    """Threaded HTTP server configured for API-style request handling."""

    allow_reuse_address = True
    request_queue_size = 128
    daemon_threads = True


def build_handler(
    service: BankingUseCases,
    max_request_body_bytes: int = 16_384,
):
    """Build a request handler class bound to the provided runtime dependencies."""

    class BankingRequestHandler(BaseHTTPRequestHandler):
        """Handle the REST endpoints exposed by the banking API."""

        server_version = "BankingAPI"
        sys_version = ""
        protocol_version = "HTTP/1.1"

        def do_GET(self) -> None:
            """Handle incoming GET requests."""
            self._dispatch_request()

        def do_POST(self) -> None:
            """Handle incoming POST requests."""
            self._dispatch_request()

        def do_PUT(self) -> None:
            """Handle unsupported PUT requests using the shared router."""
            self._dispatch_request()

        def do_PATCH(self) -> None:
            """Handle unsupported PATCH requests using the shared router."""
            self._dispatch_request()

        def do_DELETE(self) -> None:
            """Handle unsupported DELETE requests using the shared router."""
            self._dispatch_request()

        def log_message(self, format_string: str, *args: Any) -> None:
            """Write structured access logs through the application logger."""
            request_id = getattr(self, "request_id", "-")
            LOGGER.info(
                "request_id=%s client=%s %s",
                request_id,
                self.client_address[0],
                format_string % args,
            )

        def _dispatch_request(self) -> None:
            """Route the request to the matching endpoint and serialize failures safely."""
            self.request_id = secrets.token_hex(8)
            try:
                parsed_url = urlparse(self.path)
                route = parsed_url.path
                handler = self._resolve_route(route)
                handler()
            except ApiError as error:
                self._send_json(error.status_code, {"error": error.message})
            except sqlite3.Error:
                LOGGER.exception("request_id=%s database error while processing request.", self.request_id)
                self._send_json(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    {"error": "A database error occurred."},
                )
            except Exception:
                LOGGER.exception("request_id=%s unexpected error while processing request.", self.request_id)
                self._send_json(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    {"error": "An unexpected error occurred."},
                )

        def _resolve_route(self, route: str):
            """Resolve the current method and path into a request handler."""
            routes = {
                "/health": {"GET": self._handle_health},
                "/login": {"POST": self._handle_login},
                "/balance": {"GET": self._handle_balance},
                "/deposit": {"POST": self._handle_deposit},
            }

            route_handlers = routes.get(route)
            if route_handlers is None:
                raise ApiError(HTTPStatus.NOT_FOUND, "Route not found.")

            handler = route_handlers.get(self.command)
            if handler is None:
                raise ApiError(HTTPStatus.METHOD_NOT_ALLOWED, "Method not allowed.")

            return handler

        def _handle_health(self) -> None:
            """Return a lightweight health response for uptime checks."""
            self._send_json(HTTPStatus.OK, {"status": "ok"})

        def _handle_login(self) -> None:
            """Authenticate a user and return a session token."""
            payload = self._read_json_body()
            response_payload = service.login(payload.get("email"), payload.get("pin"))
            self._send_json(HTTPStatus.OK, response_payload)

        def _handle_balance(self) -> None:
            """Return the current balance for the authenticated user."""
            token = extract_bearer_token(self.headers.get("Authorization", ""))
            response_payload = service.get_balance(token)
            self._send_json(HTTPStatus.OK, response_payload)

        def _handle_deposit(self) -> None:
            """Apply a deposit to the authenticated user account."""
            token = extract_bearer_token(self.headers.get("Authorization", ""))
            payload = self._read_json_body()
            response_payload = service.deposit(token, payload.get("amount"))
            self._send_json(HTTPStatus.OK, response_payload)

        def _read_json_body(self) -> dict:
            """Read and validate a JSON request body within the configured size limit."""
            content_length_header = self.headers.get("Content-Length", "0")
            try:
                content_length = int(content_length_header)
            except ValueError as exc:
                raise ApiError(
                    HTTPStatus.BAD_REQUEST,
                    "Content-Length must be a valid integer.",
                ) from exc

            if content_length < 0:
                raise ApiError(HTTPStatus.BAD_REQUEST, "Content-Length cannot be negative.")

            if content_length > max_request_body_bytes:
                raise ApiError(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "Request body is too large.")

            if content_length > 0 and "application/json" not in self.headers.get("Content-Type", ""):
                raise ApiError(
                    HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
                    "Content-Type must be application/json.",
                )

            raw_body = self.rfile.read(content_length) if content_length else b""
            if not raw_body:
                return {}

            try:
                payload = json.loads(raw_body.decode("utf-8"))
            except json.JSONDecodeError:
                raise ApiError(
                    HTTPStatus.BAD_REQUEST,
                    "Request body must be valid JSON.",
                )

            if not isinstance(payload, dict):
                raise ApiError(
                    HTTPStatus.BAD_REQUEST,
                    "Request body must be a JSON object.",
                )

            return payload

        def _send_json(self, status_code: int, payload: dict) -> None:
            """Serialize a JSON response with API-friendly headers."""
            response_body = json.dumps(payload).encode("utf-8")
            self.send_response(status_code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(response_body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Request-ID", getattr(self, "request_id", "-"))
            self.end_headers()
            self.wfile.write(response_body)

    return BankingRequestHandler


def create_server(
    host: str,
    port: int,
    service: BankingUseCases,
    max_request_body_bytes: int = 16_384,
) -> BankingHTTPServer:
    """Create a configured HTTP server instance for the banking API."""
    handler_class = build_handler(
        service,
        max_request_body_bytes=max_request_body_bytes,
    )
    return BankingHTTPServer((host, port), handler_class)
