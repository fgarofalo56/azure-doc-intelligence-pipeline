"""Unit tests for api_versioning module."""

import json
from unittest.mock import MagicMock

import azure.functions as func
import pytest

from services.api_versioning import (
    CURRENT_VERSION,
    SUPPORTED_VERSIONS,
    VERSION_REGISTRY,
    APIVersion,
    VersionInfo,
    add_version_headers,
    deprecate_version,
    extract_version_from_route,
    get_api_versions_info,
    get_deprecation_headers,
    get_version_info,
    is_version_deprecated,
    is_version_supported,
    versioned_error_response,
    versioned_response,
)


class TestVersionInfo:
    """Tests for VersionInfo dataclass."""

    def test_version_info_creation(self):
        """Test creating VersionInfo."""
        info = VersionInfo(
            version="v1",
            is_current=True,
            is_deprecated=False,
            release_date="2025-01-01",
            changelog=["Initial release"],
        )
        assert info.version == "v1"
        assert info.is_current is True
        assert info.is_deprecated is False
        assert info.release_date == "2025-01-01"
        assert "Initial release" in info.changelog

    def test_version_info_deprecated(self):
        """Test deprecated version info."""
        info = VersionInfo(
            version="v0",
            is_current=False,
            is_deprecated=True,
            sunset_date="2025-06-01",
            successor="v1",
        )
        assert info.is_deprecated is True
        assert info.sunset_date == "2025-06-01"
        assert info.successor == "v1"


class TestAPIVersionEnum:
    """Tests for APIVersion enum."""

    def test_api_version_v1(self):
        """Test v1 enum value."""
        assert APIVersion.V1.value == "v1"


class TestVersionChecks:
    """Tests for version checking functions."""

    def test_is_version_supported_v1(self):
        """Test v1 is supported."""
        assert is_version_supported("v1") is True

    def test_is_version_supported_unknown(self):
        """Test unknown version is not supported."""
        assert is_version_supported("v99") is False

    def test_is_version_deprecated_current(self):
        """Test current version is not deprecated."""
        assert is_version_deprecated(CURRENT_VERSION) is False

    def test_get_version_info_v1(self):
        """Test getting v1 version info."""
        info = get_version_info("v1")
        assert info is not None
        assert info.version == "v1"
        assert info.is_current is True

    def test_get_version_info_unknown(self):
        """Test getting unknown version info."""
        info = get_version_info("v99")
        assert info is None


class TestGetDeprecationHeaders:
    """Tests for get_deprecation_headers function."""

    def test_headers_for_current_version(self):
        """Test headers for current version."""
        headers = get_deprecation_headers("v1")
        assert headers["X-API-Version"] == "v1"
        assert headers["X-API-Current-Version"] == CURRENT_VERSION
        assert "Deprecation" not in headers

    def test_headers_for_deprecated_version(self):
        """Test headers include deprecation info."""
        # Temporarily deprecate v1 for testing
        original_deprecated = dict(__import__("services.api_versioning", fromlist=["DEPRECATED_VERSIONS"]).DEPRECATED_VERSIONS)

        import services.api_versioning as mod
        mod.DEPRECATED_VERSIONS["v0"] = "2025-06-01"

        try:
            headers = get_deprecation_headers("v0")
            assert headers["Deprecation"] == "true"
            assert headers["Sunset"] == "2025-06-01"
            assert "X-API-Deprecation-Notice" in headers
        finally:
            mod.DEPRECATED_VERSIONS.clear()
            mod.DEPRECATED_VERSIONS.update(original_deprecated)


class TestVersionedResponse:
    """Tests for versioned_response function."""

    def test_versioned_response_success(self):
        """Test creating versioned success response."""
        data = {"status": "success", "documentId": "doc123"}
        response = versioned_response(data, version="v1", status_code=200)

        assert response.status_code == 200
        assert response.mimetype == "application/json"

        body = json.loads(response.get_body())
        assert body["status"] == "success"
        assert body["documentId"] == "doc123"

        # Check headers
        assert response.headers["X-API-Version"] == "v1"
        assert response.headers["X-API-Current-Version"] == CURRENT_VERSION

    def test_versioned_response_with_datetime(self):
        """Test versioned response serializes datetime."""
        from datetime import datetime

        data = {"timestamp": datetime(2025, 1, 15, 10, 30, 0)}
        response = versioned_response(data, version="v1")

        body = json.loads(response.get_body())
        assert "2025-01-15" in body["timestamp"]


class TestVersionedErrorResponse:
    """Tests for versioned_error_response function."""

    def test_error_response_basic(self):
        """Test basic error response."""
        response = versioned_error_response(
            "Something went wrong",
            version="v1",
            status_code=500,
        )

        assert response.status_code == 500
        body = json.loads(response.get_body())
        assert body["status"] == "error"
        assert body["error"] == "Something went wrong"
        assert body["apiVersion"] == "v1"

    def test_error_response_with_details(self):
        """Test error response with details."""
        response = versioned_error_response(
            "Not found",
            version="v1",
            status_code=404,
            details={"blobName": "test.pdf"},
        )

        body = json.loads(response.get_body())
        assert body["details"]["blobName"] == "test.pdf"

    def test_error_response_headers(self):
        """Test error response includes version headers."""
        response = versioned_error_response("Error", version="v1", status_code=500)

        assert response.headers["X-API-Version"] == "v1"


class TestExtractVersionFromRoute:
    """Tests for extract_version_from_route function."""

    def test_extract_version_from_params(self):
        """Test extracting version from route params."""
        params = {"version": "v1"}
        version = extract_version_from_route(params)
        assert version == "v1"

    def test_extract_version_without_prefix(self):
        """Test extracting version without v prefix."""
        params = {"version": "1"}
        version = extract_version_from_route(params)
        assert version == "v1"

    def test_extract_version_missing(self):
        """Test default version when missing."""
        params = {}
        version = extract_version_from_route(params)
        assert version == CURRENT_VERSION


class TestAddVersionHeaders:
    """Tests for add_version_headers function."""

    def test_add_headers_to_response(self):
        """Test adding version headers to existing response."""
        original = func.HttpResponse(
            body=json.dumps({"test": "data"}),
            status_code=200,
            mimetype="application/json",
        )

        updated = add_version_headers(original, version="v1")

        assert updated.status_code == 200
        assert updated.headers["X-API-Version"] == "v1"
        body = json.loads(updated.get_body())
        assert body["test"] == "data"


class TestGetAPIVersionsInfo:
    """Tests for get_api_versions_info function."""

    def test_get_versions_info(self):
        """Test getting all version information."""
        info = get_api_versions_info()

        assert info["currentVersion"] == CURRENT_VERSION
        assert "v1" in info["supportedVersions"]
        assert "versions" in info
        assert "v1" in info["versions"]

        v1_info = info["versions"]["v1"]
        assert v1_info["isCurrent"] is True
        assert v1_info["isDeprecated"] is False


class TestDeprecateVersion:
    """Tests for deprecate_version function."""

    def test_deprecate_version(self):
        """Test deprecating a version."""
        import services.api_versioning as mod

        # Save original state
        original_deprecated = dict(mod.DEPRECATED_VERSIONS)
        original_registry = {k: VersionInfo(
            version=v.version,
            is_current=v.is_current,
            is_deprecated=v.is_deprecated,
            sunset_date=v.sunset_date,
            successor=v.successor,
            release_date=v.release_date,
            changelog=list(v.changelog),
        ) for k, v in mod.VERSION_REGISTRY.items()}

        try:
            # Add a test version to registry
            mod.VERSION_REGISTRY["v0"] = VersionInfo(
                version="v0",
                is_current=False,
                release_date="2024-01-01",
            )

            deprecate_version("v0", "2025-06-01", "v1")

            assert mod.DEPRECATED_VERSIONS["v0"] == "2025-06-01"
            assert mod.VERSION_REGISTRY["v0"].is_deprecated is True
            assert mod.VERSION_REGISTRY["v0"].sunset_date == "2025-06-01"
            assert mod.VERSION_REGISTRY["v0"].successor == "v1"

        finally:
            # Restore original state
            mod.DEPRECATED_VERSIONS.clear()
            mod.DEPRECATED_VERSIONS.update(original_deprecated)
            if "v0" in mod.VERSION_REGISTRY:
                del mod.VERSION_REGISTRY["v0"]


class TestCurrentVersionConstants:
    """Tests for version constants."""

    def test_current_version_is_v1(self):
        """Test current version is v1."""
        assert CURRENT_VERSION == "v1"

    def test_v1_in_supported(self):
        """Test v1 is in supported versions."""
        assert "v1" in SUPPORTED_VERSIONS

    def test_v1_in_registry(self):
        """Test v1 is in version registry."""
        assert "v1" in VERSION_REGISTRY
        assert VERSION_REGISTRY["v1"].is_current is True
