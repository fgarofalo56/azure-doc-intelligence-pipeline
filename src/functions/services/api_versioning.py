"""API versioning support for Azure Functions.

Implements URL path versioning with deprecation headers for backwards compatibility.
"""

import functools
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import azure.functions as func

logger = logging.getLogger(__name__)

# Current supported API versions
CURRENT_VERSION = "v1"
SUPPORTED_VERSIONS = ["v1"]
DEPRECATED_VERSIONS: dict[str, str] = {}  # version -> sunset_date


class APIVersion(Enum):
    """API version identifiers."""

    V1 = "v1"
    # V2 = "v2"  # Add when needed


@dataclass
class VersionInfo:
    """API version metadata."""

    version: str
    is_current: bool = False
    is_deprecated: bool = False
    sunset_date: str | None = None
    successor: str | None = None
    release_date: str = ""
    changelog: list[str] = field(default_factory=list)


# Version registry
VERSION_REGISTRY: dict[str, VersionInfo] = {
    "v1": VersionInfo(
        version="v1",
        is_current=True,
        is_deprecated=False,
        release_date="2025-01-01",
        changelog=[
            "Initial stable API release",
            "Document processing endpoints",
            "Batch processing support",
            "Multi-tenant isolation",
            "Profile-based processing",
            "Async job queue support",
        ],
    ),
}


def get_version_info(version: str) -> VersionInfo | None:
    """Get version information.

    Args:
        version: API version string (e.g., "v1").

    Returns:
        VersionInfo if version exists, None otherwise.
    """
    return VERSION_REGISTRY.get(version)


def is_version_supported(version: str) -> bool:
    """Check if version is supported.

    Args:
        version: API version string.

    Returns:
        True if version is supported.
    """
    return version in SUPPORTED_VERSIONS


def is_version_deprecated(version: str) -> bool:
    """Check if version is deprecated.

    Args:
        version: API version string.

    Returns:
        True if version is deprecated.
    """
    return version in DEPRECATED_VERSIONS


def get_deprecation_headers(version: str) -> dict[str, str]:
    """Get deprecation headers for a version.

    Args:
        version: API version string.

    Returns:
        Dictionary of deprecation headers.
    """
    headers: dict[str, str] = {}

    if version in DEPRECATED_VERSIONS:
        sunset_date = DEPRECATED_VERSIONS[version]
        headers["Deprecation"] = "true"
        headers["Sunset"] = sunset_date
        headers["X-API-Deprecation-Notice"] = (
            f"API version {version} is deprecated and will be removed on {sunset_date}. "
            f"Please migrate to {CURRENT_VERSION}."
        )

    # Always include current version info
    headers["X-API-Version"] = version
    headers["X-API-Current-Version"] = CURRENT_VERSION

    return headers


def add_version_headers(
    response: func.HttpResponse,
    version: str,
) -> func.HttpResponse:
    """Add version headers to response.

    Args:
        response: HTTP response to add headers to.
        version: API version used for the request.

    Returns:
        Response with version headers added.
    """
    headers = get_deprecation_headers(version)

    # Create new response with headers
    # Note: Azure Functions HttpResponse doesn't support modifying headers
    # after creation, so we need to create a new response
    existing_headers = dict(response.headers) if response.headers else {}
    all_headers = {**existing_headers, **headers}

    return func.HttpResponse(
        body=response.get_body(),
        status_code=response.status_code,
        headers=all_headers,
        mimetype=response.mimetype,
    )


def versioned_response(
    data: dict[str, Any],
    version: str,
    status_code: int = 200,
) -> func.HttpResponse:
    """Create a versioned JSON response with appropriate headers.

    Args:
        data: Response data dictionary.
        version: API version.
        status_code: HTTP status code.

    Returns:
        HTTP response with version headers.
    """
    import json

    headers = get_deprecation_headers(version)
    headers["Content-Type"] = "application/json"

    return func.HttpResponse(
        body=json.dumps(data, default=str),
        status_code=status_code,
        headers=headers,
        mimetype="application/json",
    )


def versioned_error_response(
    error: str,
    version: str,
    status_code: int = 500,
    details: dict[str, Any] | None = None,
) -> func.HttpResponse:
    """Create a versioned error response.

    Args:
        error: Error message.
        version: API version.
        status_code: HTTP status code.
        details: Optional error details.

    Returns:
        HTTP error response with version headers.
    """
    import json

    body: dict[str, Any] = {
        "status": "error",
        "error": error,
        "apiVersion": version,
    }
    if details:
        body["details"] = details

    headers = get_deprecation_headers(version)
    headers["Content-Type"] = "application/json"

    return func.HttpResponse(
        body=json.dumps(body, default=str),
        status_code=status_code,
        headers=headers,
        mimetype="application/json",
    )


def extract_version_from_route(route_params: dict[str, str]) -> str:
    """Extract API version from route parameters.

    Args:
        route_params: Route parameters dictionary.

    Returns:
        API version string, defaults to current version.
    """
    version = route_params.get("version", CURRENT_VERSION)
    if not version.startswith("v"):
        version = f"v{version}"
    return version


def version_gate(
    min_version: str | None = None,
    max_version: str | None = None,
    deprecated_in: str | None = None,
) -> Callable[..., Any]:
    """Decorator to enforce version constraints on endpoints.

    Args:
        min_version: Minimum API version required.
        max_version: Maximum API version supported.
        deprecated_in: Version where this endpoint is deprecated.

    Returns:
        Decorator function.
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        async def wrapper(req: func.HttpRequest, *args: Any, **kwargs: Any) -> func.HttpResponse:
            version = extract_version_from_route(req.route_params)

            # Check minimum version
            if min_version and version < min_version:
                return versioned_error_response(
                    f"This endpoint requires API version {min_version} or higher",
                    version=version,
                    status_code=400,
                )

            # Check maximum version
            if max_version and version > max_version:
                return versioned_error_response(
                    f"This endpoint is not available in API version {version}. Use {max_version} or lower.",
                    version=version,
                    status_code=400,
                )

            # Log deprecation warning
            if deprecated_in and version >= deprecated_in:
                logger.warning(
                    f"Deprecated endpoint called: {req.url} (deprecated in {deprecated_in})"
                )

            return await func(req, *args, **kwargs)

        return wrapper

    return decorator


def get_api_versions_info() -> dict[str, Any]:
    """Get information about all API versions.

    Returns:
        Dictionary with version information.
    """
    return {
        "currentVersion": CURRENT_VERSION,
        "supportedVersions": SUPPORTED_VERSIONS,
        "deprecatedVersions": DEPRECATED_VERSIONS,
        "versions": {
            k: {
                "version": v.version,
                "isCurrent": v.is_current,
                "isDeprecated": v.is_deprecated,
                "sunsetDate": v.sunset_date,
                "releaseDate": v.release_date,
                "changelog": v.changelog,
            }
            for k, v in VERSION_REGISTRY.items()
        },
    }


# Utility to mark a version as deprecated (for future use)
def deprecate_version(version: str, sunset_date: str, successor: str = CURRENT_VERSION) -> None:
    """Mark an API version as deprecated.

    Args:
        version: Version to deprecate.
        sunset_date: Date when version will be removed (ISO format).
        successor: Recommended replacement version.
    """
    DEPRECATED_VERSIONS[version] = sunset_date
    if version in VERSION_REGISTRY:
        VERSION_REGISTRY[version].is_deprecated = True
        VERSION_REGISTRY[version].sunset_date = sunset_date
        VERSION_REGISTRY[version].successor = successor


# Example: To deprecate v1 when v2 is released:
# deprecate_version("v1", "2026-01-01", "v2")
