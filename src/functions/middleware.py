"""Middleware for request validation and rate limiting.

Provides decorators for Azure Functions HTTP triggers.
"""

import functools
import json
import logging
from collections.abc import Callable
from typing import Any, TypeVar

import azure.functions as func
from pydantic import BaseModel, ValidationError

from services.rate_limiter import get_rate_limiter

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


def validate_request(
    model: type[T],
    source: str = "body",
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator to validate request body against Pydantic model.

    Args:
        model: Pydantic model class for validation.
        source: Where to get data from ("body", "query", "route").

    Returns:
        Decorated function.

    Example:
        @validate_request(ProcessRequest)
        async def process_document(req: func.HttpRequest, validated: ProcessRequest):
            ...
    """

    def decorator(func_handler: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func_handler)
        async def wrapper(req: func.HttpRequest, *args: Any, **kwargs: Any) -> Any:
            try:
                if source == "body":
                    try:
                        data = req.get_json()
                    except ValueError:
                        return _error_response(
                            "Invalid JSON in request body",
                            status_code=400,
                        )
                elif source == "query":
                    data = dict(req.params)
                elif source == "route":
                    data = dict(req.route_params)
                else:
                    data = {}

                # Validate with Pydantic
                validated = model(**data)
                return await func_handler(req, validated, *args, **kwargs)

            except ValidationError as e:
                errors = []
                for error in e.errors():
                    field = ".".join(str(loc) for loc in error["loc"])
                    errors.append(
                        {
                            "field": field,
                            "message": error["msg"],
                            "type": error["type"],
                        }
                    )

                return _error_response(
                    "Validation failed",
                    status_code=400,
                    details={"validation_errors": errors},
                )

        return wrapper

    return decorator


def rate_limit(
    endpoint: str | None = None,
    client_header: str = "X-Client-ID",
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator to apply rate limiting to endpoint.

    Args:
        endpoint: Endpoint name for custom limits.
        client_header: Header to identify client (falls back to IP).

    Returns:
        Decorated function.

    Example:
        @rate_limit(endpoint="reprocess")
        async def reprocess_document(req: func.HttpRequest):
            ...
    """

    def decorator(func_handler: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func_handler)
        async def wrapper(req: func.HttpRequest, *args: Any, **kwargs: Any) -> Any:
            rate_limiter = get_rate_limiter()

            # Get client identifier
            client_id = req.headers.get(client_header)
            if not client_id:
                # Fall back to client IP
                client_id = req.headers.get(
                    "X-Forwarded-For",
                    req.headers.get("X-Real-IP", "unknown"),
                )
                # Take first IP if multiple
                if "," in client_id:
                    client_id = client_id.split(",")[0].strip()

            # Check rate limit
            allowed, headers = await rate_limiter.check_rate_limit(
                client_id=client_id,
                endpoint=endpoint,
            )

            if not allowed:
                return func.HttpResponse(
                    body=json.dumps(
                        {
                            "status": "error",
                            "error": "Rate limit exceeded",
                            "retry_after": headers.get("Retry-After", "60"),
                        }
                    ),
                    status_code=429,
                    mimetype="application/json",
                    headers=headers,
                )

            # Process request and add rate limit headers to response
            response = await func_handler(req, *args, **kwargs)

            # Add rate limit headers to response
            if isinstance(response, func.HttpResponse):
                for key, value in headers.items():
                    response.headers[key] = value

            return response

        return wrapper

    return decorator


def require_auth(
    api_key_header: str = "X-API-Key",
    api_key_env: str = "API_KEY",
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator to require API key authentication.

    Args:
        api_key_header: Header name for API key.
        api_key_env: Environment variable with valid API key.

    Returns:
        Decorated function.

    Example:
        @require_auth()
        async def admin_endpoint(req: func.HttpRequest):
            ...
    """
    import os

    def decorator(func_handler: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func_handler)
        async def wrapper(req: func.HttpRequest, *args: Any, **kwargs: Any) -> Any:
            expected_key = os.environ.get(api_key_env)

            # Skip auth if no key configured (development)
            if not expected_key:
                logger.warning(f"No {api_key_env} configured, skipping auth")
                return await func_handler(req, *args, **kwargs)

            provided_key = req.headers.get(api_key_header)

            if not provided_key:
                return _error_response(
                    f"Missing {api_key_header} header",
                    status_code=401,
                )

            if provided_key != expected_key:
                return _error_response(
                    "Invalid API key",
                    status_code=403,
                )

            return await func_handler(req, *args, **kwargs)

        return wrapper

    return decorator


def _error_response(
    error: str,
    status_code: int = 500,
    details: dict[str, Any] | None = None,
) -> func.HttpResponse:
    """Create error JSON response.

    Args:
        error: Error message.
        status_code: HTTP status code.
        details: Additional error details.

    Returns:
        HTTP response with JSON error.
    """
    body: dict[str, Any] = {
        "status": "error",
        "error": error,
    }
    if details:
        body["details"] = details

    return func.HttpResponse(
        body=json.dumps(body, default=str),
        status_code=status_code,
        mimetype="application/json",
    )
