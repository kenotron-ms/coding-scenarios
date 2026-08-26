"""
app.py — FastAPI routes and validation for the URL shortener service.
"""

import json
import logging
import random
import re
import time
from datetime import timezone
from typing import Optional
from urllib.parse import urlparse

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware

from solution.codec import generate_code
from solution.storage import (
    create_link,
    delete_link,
    find_by_url,
    get_link,
    health_check,
    increment_clicks,
)

logger = logging.getLogger(__name__)

# Characters allowed in a short code (URL-safe, no traversal)
_CODE_RE = re.compile(r'^[0-9A-Za-z_-]+$')

# Maximum sizes
_MAX_URL_BYTES = 2048
_MAX_BODY_BYTES = 8192

# Forbidden characters in URLs
_FORBIDDEN_URL_CHARS = re.compile(r'[\r\n\x00]')


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log each request as a JSON line to stdout."""

    async def dispatch(self, request: Request, call_next):
        start = time.time()
        response = await call_next(request)
        duration_ms = (time.time() - start) * 1000
        log_entry = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": round(duration_ms, 2),
        }
        print(json.dumps(log_entry), flush=True)
        return response


def _validate_url(url: str) -> Optional[str]:
    """
    Validate a URL string.

    Returns an error message string if invalid, or None if valid.
    """
    if not isinstance(url, str):
        return "url must be a string"
    if not url or not url.strip():
        return "url must not be empty or whitespace"
    if len(url.encode("utf-8")) > _MAX_URL_BYTES:
        return f"url must not exceed {_MAX_URL_BYTES} bytes"
    if _FORBIDDEN_URL_CHARS.search(url):
        return "url must not contain CR, LF, or NUL characters"

    parsed = urlparse(url)
    if parsed.scheme.lower() not in ("http", "https"):
        return "url scheme must be http or https"
    if not parsed.netloc:
        return "url must have a host"

    return None


def _validate_code(code: str) -> bool:
    """Return True if the code contains only URL-safe characters."""
    return bool(_CODE_RE.match(code))


def create_app(db_path: str, base_url: Optional[str] = None, rng: Optional[random.Random] = None) -> FastAPI:
    """
    Factory function to create the FastAPI application.

    Args:
        db_path: Path to the SQLite database file.
        base_url: Optional base URL for constructing short URLs.
        rng: Optional random.Random instance for code generation.

    Returns:
        A configured FastAPI application instance.
    """
    if rng is None:
        rng = random.Random()

    app = FastAPI(
        title="URL Shortener",
        description="A simple URL shortener service",
        version="1.0.0",
    )

    # Add request logging middleware
    app.add_middleware(RequestLoggingMiddleware)

    # Override FastAPI's default 422 validation error handler → return 400
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=400,
            content={"detail": str(exc)},
        )

    @app.post("/api/shorten", status_code=201)
    async def shorten(request: Request):
        """
        POST /api/shorten — Create a short URL.

        Accepts JSON body: {"url": "<destination>"}
        Returns 201: {"code": "<code>", "short_url": "<base_url>/<code>"}
        """
        # Check body size
        body = await request.body()
        if len(body) > _MAX_BODY_BYTES:
            return JSONResponse(
                status_code=400,
                content={"detail": f"Request body exceeds {_MAX_BODY_BYTES} bytes"},
            )

        # Parse JSON
        try:
            data = json.loads(body)
        except (json.JSONDecodeError, ValueError):
            return JSONResponse(
                status_code=400,
                content={"detail": "Request body must be valid JSON"},
            )

        if not isinstance(data, dict):
            return JSONResponse(
                status_code=400,
                content={"detail": "Request body must be a JSON object"},
            )

        if "url" not in data:
            return JSONResponse(
                status_code=400,
                content={"detail": "Missing required field: url"},
            )

        url = data["url"]

        # Validate URL
        error = _validate_url(url)
        if error:
            return JSONResponse(
                status_code=400,
                content={"detail": error},
            )

        # A-1: Check for existing URL (idempotent dedupe)
        existing = find_by_url(db_path, url)
        if existing:
            short_url = f"{base_url}/{existing['code']}" if base_url else f"/{existing['code']}"
            return JSONResponse(
                status_code=201,
                content={"code": existing["code"], "short_url": short_url},
            )

        # Generate a unique code (up to 10 attempts)
        import sqlite3
        for _ in range(10):
            code = generate_code(rng)
            try:
                create_link(db_path, code, url)
                short_url = f"{base_url}/{code}" if base_url else f"/{code}"
                return JSONResponse(
                    status_code=201,
                    content={"code": code, "short_url": short_url},
                )
            except sqlite3.IntegrityError:
                # UNIQUE constraint violation — retry with a new code
                continue

        return JSONResponse(
            status_code=500,
            content={"detail": "Failed to generate a unique code after 10 attempts"},
        )

    @app.get("/health")
    async def health():
        """GET /health — Health check endpoint."""
        ok = health_check(db_path)
        if ok:
            return JSONResponse(status_code=200, content={"status": "ok"})
        return JSONResponse(status_code=503, content={"status": "error"})

    @app.get("/api/stats/{code}")
    async def stats(code: str):
        """GET /api/stats/{code} — Return stats for a short code."""
        if not _validate_code(code):
            return JSONResponse(
                status_code=404,
                content={"detail": f"Code not found: {code}"},
            )

        link = get_link(db_path, code)
        if link is None:
            return JSONResponse(
                status_code=404,
                content={"detail": f"Code not found: {code}"},
            )

        # Format created_at as ISO-8601 UTC string
        created_at = link["created_at"]
        if hasattr(created_at, "isoformat"):
            created_at = created_at.replace(tzinfo=timezone.utc).isoformat()
        else:
            # It's a string from SQLite — ensure it ends with Z
            created_at = str(created_at)
            if not created_at.endswith("Z") and "+" not in created_at:
                created_at = created_at + "Z"

        return JSONResponse(
            status_code=200,
            content={
                "code": link["code"],
                "url": link["url"],
                "clicks": link["clicks"],
                "created_at": created_at,
            },
        )

    @app.delete("/api/{code}", status_code=204)
    async def delete(code: str):
        """DELETE /api/{code} — Delete a short URL."""
        if not _validate_code(code):
            return JSONResponse(
                status_code=404,
                content={"detail": f"Code not found: {code}"},
            )

        deleted = delete_link(db_path, code)
        if not deleted:
            return JSONResponse(
                status_code=404,
                content={"detail": f"Code not found: {code}"},
            )

        return Response(status_code=204)

    @app.get("/{code}")
    async def redirect(code: str):
        """GET /{code} — Redirect to the stored URL."""
        # Validate code is URL-safe (no path traversal or special chars)
        if not _validate_code(code):
            return JSONResponse(
                status_code=404,
                content={"detail": f"Code not found: {code}"},
            )

        link = increment_clicks(db_path, code)
        if link is None:
            return JSONResponse(
                status_code=404,
                content={"detail": f"Code not found: {code}"},
            )

        # A-3: Location header is byte-identical to the stored URL
        return RedirectResponse(url=link["url"], status_code=302)

    return app
