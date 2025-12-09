"""Unit tests for middleware decorators."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import azure.functions as func
import pytest
from pydantic import BaseModel, Field


class SampleRequest(BaseModel):
    """Sample request model for testing."""

    name: str = Field(min_length=1)
    value: int = Field(ge=0)


def create_mock_request(body=None, params=None, route_params=None, headers=None, method="POST"):
    """Create a mock HTTP request."""
    if body is None:
        body = {}

    return func.HttpRequest(
        method=method,
        body=json.dumps(body).encode("utf-8") if isinstance(body, dict) else body,
        url="/api/test",
        headers=headers or {"Content-Type": "application/json"},
        params=params or {},
        route_params=route_params or {},
    )


class TestValidateRequest:
    """Tests for validate_request decorator."""

    @pytest.mark.asyncio
    async def test_valid_body(self):
        """Test validation passes with valid body."""
        from src.functions.middleware import validate_request

        @validate_request(SampleRequest)
        async def handler(req, validated):
            return func.HttpResponse(
                body=json.dumps({"name": validated.name, "value": validated.value}),
                status_code=200,
            )

        req = create_mock_request(body={"name": "test", "value": 42})
        response = await handler(req)

        assert response.status_code == 200
        body = json.loads(response.get_body().decode())
        assert body["name"] == "test"
        assert body["value"] == 42

    @pytest.mark.asyncio
    async def test_invalid_json(self):
        """Test error on invalid JSON."""
        from src.functions.middleware import validate_request

        @validate_request(SampleRequest)
        async def handler(req, validated):
            return func.HttpResponse(status_code=200)

        req = create_mock_request(body=b"not valid json")
        response = await handler(req)

        assert response.status_code == 400
        body = json.loads(response.get_body().decode())
        assert "Invalid JSON" in body["error"]

    @pytest.mark.asyncio
    async def test_validation_error(self):
        """Test error on validation failure."""
        from src.functions.middleware import validate_request

        @validate_request(SampleRequest)
        async def handler(req, validated):
            return func.HttpResponse(status_code=200)

        req = create_mock_request(body={"name": "", "value": -1})  # Invalid: empty name, negative value
        response = await handler(req)

        assert response.status_code == 400
        body = json.loads(response.get_body().decode())
        assert "Validation failed" in body["error"]
        assert "validation_errors" in body.get("details", {})

    @pytest.mark.asyncio
    async def test_query_source(self):
        """Test validation from query params."""
        from src.functions.middleware import validate_request

        @validate_request(SampleRequest, source="query")
        async def handler(req, validated):
            return func.HttpResponse(
                body=json.dumps({"name": validated.name}),
                status_code=200,
            )

        req = create_mock_request(body={}, params={"name": "query_test", "value": "10"})
        response = await handler(req)

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_route_source(self):
        """Test validation from route params."""
        from src.functions.middleware import validate_request

        @validate_request(SampleRequest, source="route")
        async def handler(req, validated):
            return func.HttpResponse(
                body=json.dumps({"name": validated.name}),
                status_code=200,
            )

        req = create_mock_request(body={}, route_params={"name": "route_test", "value": "5"})
        response = await handler(req)

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_unknown_source(self):
        """Test with unknown source defaults to empty data."""
        from src.functions.middleware import validate_request

        @validate_request(SampleRequest, source="unknown")
        async def handler(req, validated):
            return func.HttpResponse(status_code=200)

        req = create_mock_request(body={"name": "test", "value": 1})
        response = await handler(req)

        # Should fail validation because data is empty dict
        assert response.status_code == 400


class TestRateLimit:
    """Tests for rate_limit decorator."""

    @pytest.mark.asyncio
    async def test_allowed_request(self):
        """Test request passes when under rate limit."""
        from src.functions.middleware import rate_limit

        with patch("src.functions.middleware.get_rate_limiter") as mock_get_limiter:
            mock_limiter = AsyncMock()
            mock_limiter.check_rate_limit = AsyncMock(
                return_value=(True, {"X-RateLimit-Remaining": "99"})
            )
            mock_get_limiter.return_value = mock_limiter

            @rate_limit(endpoint="test")
            async def handler(req):
                return func.HttpResponse(
                    body=json.dumps({"status": "ok"}),
                    status_code=200,
                    mimetype="application/json",
                )

            req = create_mock_request(headers={"X-Client-ID": "client-123"})
            response = await handler(req)

            assert response.status_code == 200
            assert response.headers.get("X-RateLimit-Remaining") == "99"

    @pytest.mark.asyncio
    async def test_rate_limited_request(self):
        """Test request blocked when rate limit exceeded."""
        from src.functions.middleware import rate_limit

        with patch("src.functions.middleware.get_rate_limiter") as mock_get_limiter:
            mock_limiter = AsyncMock()
            mock_limiter.check_rate_limit = AsyncMock(
                return_value=(False, {"Retry-After": "30"})
            )
            mock_get_limiter.return_value = mock_limiter

            @rate_limit(endpoint="test")
            async def handler(req):
                return func.HttpResponse(status_code=200)

            req = create_mock_request(headers={"X-Client-ID": "client-123"})
            response = await handler(req)

            assert response.status_code == 429
            body = json.loads(response.get_body().decode())
            assert "Rate limit exceeded" in body["error"]
            assert body["retry_after"] == "30"

    @pytest.mark.asyncio
    async def test_fallback_to_ip(self):
        """Test falls back to IP when no client header."""
        from src.functions.middleware import rate_limit

        with patch("src.functions.middleware.get_rate_limiter") as mock_get_limiter:
            mock_limiter = AsyncMock()
            mock_limiter.check_rate_limit = AsyncMock(
                return_value=(True, {})
            )
            mock_get_limiter.return_value = mock_limiter

            @rate_limit()
            async def handler(req):
                return func.HttpResponse(status_code=200, mimetype="application/json")

            req = create_mock_request(headers={"X-Forwarded-For": "192.168.1.1, 10.0.0.1"})
            response = await handler(req)

            assert response.status_code == 200
            # Verify the first IP was used
            mock_limiter.check_rate_limit.assert_called_once()
            call_args = mock_limiter.check_rate_limit.call_args
            assert call_args.kwargs["client_id"] == "192.168.1.1"

    @pytest.mark.asyncio
    async def test_fallback_to_real_ip(self):
        """Test falls back to X-Real-IP header."""
        from src.functions.middleware import rate_limit

        with patch("src.functions.middleware.get_rate_limiter") as mock_get_limiter:
            mock_limiter = AsyncMock()
            mock_limiter.check_rate_limit = AsyncMock(
                return_value=(True, {})
            )
            mock_get_limiter.return_value = mock_limiter

            @rate_limit()
            async def handler(req):
                return func.HttpResponse(status_code=200, mimetype="application/json")

            req = create_mock_request(headers={"X-Real-IP": "10.0.0.5"})
            response = await handler(req)

            assert response.status_code == 200


class TestRequireAuth:
    """Tests for require_auth decorator."""

    @pytest.mark.asyncio
    async def test_valid_api_key(self):
        """Test request passes with valid API key."""
        from src.functions.middleware import require_auth

        with patch.dict("os.environ", {"API_KEY": "secret-key-123"}):
            @require_auth()
            async def handler(req):
                return func.HttpResponse(
                    body=json.dumps({"status": "authenticated"}),
                    status_code=200,
                )

            req = create_mock_request(headers={"X-API-Key": "secret-key-123"})
            response = await handler(req)

            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_missing_api_key(self):
        """Test error when API key header missing."""
        from src.functions.middleware import require_auth

        with patch.dict("os.environ", {"API_KEY": "secret-key-123"}):
            @require_auth()
            async def handler(req):
                return func.HttpResponse(status_code=200)

            req = create_mock_request(headers={})
            response = await handler(req)

            assert response.status_code == 401
            body = json.loads(response.get_body().decode())
            assert "Missing" in body["error"]

    @pytest.mark.asyncio
    async def test_invalid_api_key(self):
        """Test error when API key is wrong."""
        from src.functions.middleware import require_auth

        with patch.dict("os.environ", {"API_KEY": "secret-key-123"}):
            @require_auth()
            async def handler(req):
                return func.HttpResponse(status_code=200)

            req = create_mock_request(headers={"X-API-Key": "wrong-key"})
            response = await handler(req)

            assert response.status_code == 403
            body = json.loads(response.get_body().decode())
            assert "Invalid" in body["error"]

    @pytest.mark.asyncio
    async def test_no_key_configured_skips_auth(self):
        """Test auth is skipped when no key configured."""
        from src.functions.middleware import require_auth

        with patch.dict("os.environ", {}, clear=True):
            @require_auth()
            async def handler(req):
                return func.HttpResponse(
                    body=json.dumps({"status": "ok"}),
                    status_code=200,
                )

            req = create_mock_request(headers={})
            response = await handler(req)

            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_custom_header_and_env(self):
        """Test with custom header and env var names."""
        from src.functions.middleware import require_auth

        with patch.dict("os.environ", {"CUSTOM_KEY": "my-secret"}):
            @require_auth(api_key_header="X-Custom-Auth", api_key_env="CUSTOM_KEY")
            async def handler(req):
                return func.HttpResponse(status_code=200)

            req = create_mock_request(headers={"X-Custom-Auth": "my-secret"})
            response = await handler(req)

            assert response.status_code == 200


class TestErrorResponse:
    """Tests for _error_response helper."""

    def test_basic_error(self):
        """Test basic error response."""
        from src.functions.middleware import _error_response

        response = _error_response("Something went wrong", status_code=500)

        assert response.status_code == 500
        body = json.loads(response.get_body().decode())
        assert body["status"] == "error"
        assert body["error"] == "Something went wrong"
        assert "details" not in body

    def test_error_with_details(self):
        """Test error response with details."""
        from src.functions.middleware import _error_response

        response = _error_response(
            "Validation failed",
            status_code=400,
            details={"field": "name", "reason": "too short"},
        )

        assert response.status_code == 400
        body = json.loads(response.get_body().decode())
        assert body["details"]["field"] == "name"
