"""Unit tests for the webhook service."""

import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest


class TestWebhookError:
    """Tests for WebhookError exception."""

    def test_webhook_error_creation(self):
        """Test WebhookError creation."""
        from src.functions.services.webhook_service import WebhookError

        error = WebhookError(
            url="https://example.com/webhook",
            reason="Connection failed",
            status_code=500,
        )

        assert error.url == "https://example.com/webhook"
        assert error.reason == "Connection failed"
        assert error.status_code == 500
        assert "example.com" in str(error)

    def test_webhook_error_without_status_code(self):
        """Test WebhookError without status code."""
        from src.functions.services.webhook_service import WebhookError

        error = WebhookError(
            url="https://example.com/webhook",
            reason="Timeout",
        )

        assert error.status_code is None


class TestWebhookDeliveryRecord:
    """Tests for WebhookDeliveryRecord dataclass."""

    def test_record_creation_defaults(self):
        """Test record creation with defaults."""
        from src.functions.services.webhook_service import WebhookDeliveryRecord

        record = WebhookDeliveryRecord()

        assert record.id  # Should have a UUID
        assert record.webhook_url == ""
        assert record.payload == {}
        assert record.status_code is None
        assert record.error_message == ""
        assert record.attempt_count == 0
        assert record.resolved is False

    def test_record_creation_with_values(self):
        """Test record creation with values."""
        from src.functions.services.webhook_service import WebhookDeliveryRecord

        record = WebhookDeliveryRecord(
            id="test-id",
            webhook_url="https://example.com/hook",
            payload={"event": "test"},
            status_code=500,
            error_message="Server error",
            attempt_count=3,
            first_attempt_at="2025-01-01T00:00:00Z",
            last_attempt_at="2025-01-01T00:05:00Z",
            resolved=False,
        )

        assert record.id == "test-id"
        assert record.webhook_url == "https://example.com/hook"
        assert record.payload == {"event": "test"}
        assert record.status_code == 500
        assert record.attempt_count == 3

    def test_to_cosmos_document(self):
        """Test conversion to Cosmos DB document."""
        from src.functions.services.webhook_service import WebhookDeliveryRecord

        record = WebhookDeliveryRecord(
            id="test-id",
            webhook_url="https://example.com/hook",
            payload={"event": "test"},
            error_message="Failed",
        )

        doc = record.to_cosmos_document()

        assert doc["id"] == "test-id"
        assert doc["webhookUrl"] == "https://example.com/hook"
        assert doc["payload"] == {"event": "test"}
        assert doc["error_message"] == "Failed"


class TestHmacSignature:
    """Tests for HMAC signature computation."""

    def test_compute_hmac_signature(self):
        """Test HMAC signature computation."""
        from src.functions.services.webhook_service import compute_hmac_signature

        payload = {"event": "test", "data": "value"}
        secret = "test-secret"

        signature = compute_hmac_signature(payload, secret)

        # Verify it's a valid hex string
        assert len(signature) == 64
        assert all(c in "0123456789abcdef" for c in signature)

    def test_hmac_signature_deterministic(self):
        """Test that HMAC signature is deterministic."""
        from src.functions.services.webhook_service import compute_hmac_signature

        payload = {"event": "test", "data": "value"}
        secret = "test-secret"

        sig1 = compute_hmac_signature(payload, secret)
        sig2 = compute_hmac_signature(payload, secret)

        assert sig1 == sig2

    def test_hmac_signature_different_for_different_payloads(self):
        """Test that different payloads produce different signatures."""
        from src.functions.services.webhook_service import compute_hmac_signature

        secret = "test-secret"
        sig1 = compute_hmac_signature({"event": "test1"}, secret)
        sig2 = compute_hmac_signature({"event": "test2"}, secret)

        assert sig1 != sig2

    def test_hmac_signature_different_for_different_secrets(self):
        """Test that different secrets produce different signatures."""
        from src.functions.services.webhook_service import compute_hmac_signature

        payload = {"event": "test"}
        sig1 = compute_hmac_signature(payload, "secret1")
        sig2 = compute_hmac_signature(payload, "secret2")

        assert sig1 != sig2

    def test_hmac_signature_manual_verification(self):
        """Test HMAC signature matches manual computation."""
        from src.functions.services.webhook_service import compute_hmac_signature

        payload = {"b": "2", "a": "1"}  # Will be sorted
        secret = "test-secret"

        signature = compute_hmac_signature(payload, secret)

        # Manual computation with sorted keys
        expected_payload = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        expected_sig = hmac.new(secret.encode("utf-8"), expected_payload, hashlib.sha256).hexdigest()

        assert signature == expected_sig


class TestRetryDelay:
    """Tests for retry delay calculation."""

    def test_calculate_retry_delay_includes_base(self):
        """Test that retry delay includes base delay."""
        from src.functions.services.webhook_service import calculate_retry_delay

        with patch("random.uniform", return_value=0):
            delay = calculate_retry_delay(attempt=1, base_delay=2.0, jitter_max=0)

        assert delay == 2.0

    def test_calculate_retry_delay_exponential(self):
        """Test that retry delay scales with attempt."""
        from src.functions.services.webhook_service import calculate_retry_delay

        with patch("random.uniform", return_value=0):
            delay1 = calculate_retry_delay(attempt=1, base_delay=2.0, jitter_max=0)
            delay2 = calculate_retry_delay(attempt=2, base_delay=2.0, jitter_max=0)
            delay3 = calculate_retry_delay(attempt=3, base_delay=2.0, jitter_max=0)

        assert delay1 == 2.0
        assert delay2 == 4.0
        assert delay3 == 6.0

    def test_calculate_retry_delay_includes_jitter(self):
        """Test that retry delay includes jitter."""
        from src.functions.services.webhook_service import calculate_retry_delay

        with patch("random.uniform", return_value=0.5):
            delay = calculate_retry_delay(attempt=1, base_delay=2.0, jitter_max=1.0)

        assert delay == 2.5

    def test_calculate_retry_delay_jitter_range(self):
        """Test that jitter stays within range."""
        from src.functions.services.webhook_service import calculate_retry_delay

        delays = []
        for _ in range(100):
            delay = calculate_retry_delay(attempt=1, base_delay=2.0, jitter_max=1.0)
            delays.append(delay)

        assert all(2.0 <= d <= 3.0 for d in delays)


class TestWebhookService:
    """Tests for WebhookService class."""

    def test_init_without_url(self):
        """Test initialization without URL."""
        with patch.dict("os.environ", {}, clear=True):
            from src.functions.services.webhook_service import WebhookService

            service = WebhookService()
            assert service.default_webhook_url is None
            assert service.timeout == 30
            assert service.signing_secret is None

    def test_init_with_url_from_env(self):
        """Test initialization with URL from environment."""
        with patch.dict(
            "os.environ",
            {"WEBHOOK_URL": "https://example.com/webhook"},
            clear=True,
        ):
            from src.functions.services.webhook_service import WebhookService

            service = WebhookService()
            assert service.default_webhook_url == "https://example.com/webhook"

    def test_init_with_signing_secret_from_env(self):
        """Test initialization with signing secret from environment."""
        with patch.dict(
            "os.environ",
            {"WEBHOOK_SIGNING_SECRET": "my-secret"},
            clear=True,
        ):
            from src.functions.services.webhook_service import WebhookService

            service = WebhookService()
            assert service.signing_secret == "my-secret"

    def test_init_with_explicit_values(self):
        """Test initialization with explicit values."""
        from src.functions.services.webhook_service import WebhookService

        service = WebhookService(
            default_webhook_url="https://custom.com/hook",
            timeout=60,
            signing_secret="explicit-secret",
            persist_failures=False,
        )

        assert service.default_webhook_url == "https://custom.com/hook"
        assert service.timeout == 60
        assert service.signing_secret == "explicit-secret"
        assert service.persist_failures is False

    def test_build_headers_without_signing(self):
        """Test header building without signing secret."""
        from src.functions.services.webhook_service import WebhookService

        service = WebhookService(signing_secret=None)
        headers = service._build_headers({"event": "test"})

        assert headers["Content-Type"] == "application/json"
        assert headers["User-Agent"] == "Azure-DocIntel-Pipeline/1.0"
        assert "X-Webhook-Signature" not in headers

    def test_build_headers_with_signing(self):
        """Test header building with signing secret."""
        from src.functions.services.webhook_service import WebhookService, compute_hmac_signature

        service = WebhookService(signing_secret="test-secret")
        payload = {"event": "test"}
        headers = service._build_headers(payload)

        assert "X-Webhook-Signature" in headers
        expected_sig = compute_hmac_signature(payload, "test-secret")
        assert headers["X-Webhook-Signature"] == f"sha256={expected_sig}"

    @pytest.mark.asyncio
    async def test_send_notification_no_url(self, caplog):
        """Test send_notification returns False when no URL configured."""
        caplog.set_level(logging.DEBUG)
        with patch.dict("os.environ", {}, clear=True):
            from src.functions.services.webhook_service import WebhookService

            service = WebhookService()
            result = await service.send_notification({"test": "data"})

            assert result is False
            assert "No webhook URL configured" in caplog.text

    @pytest.mark.asyncio
    async def test_send_notification_success(self):
        """Test successful notification delivery."""
        from src.functions.services.webhook_service import WebhookService

        service = WebhookService(
            default_webhook_url="https://example.com/webhook",
            persist_failures=False,
        )

        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.status_code = 200

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            result = await service.send_notification({"event": "test"})

            assert result is True
            mock_instance.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_notification_includes_signature_header(self):
        """Test that notification includes signature header."""
        from src.functions.services.webhook_service import WebhookService

        service = WebhookService(
            default_webhook_url="https://example.com/webhook",
            signing_secret="test-secret",
            persist_failures=False,
        )

        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.status_code = 200

        captured_headers = None

        async def capture_post(url, json, headers):
            nonlocal captured_headers
            captured_headers = headers
            return mock_response

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post = capture_post
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            await service.send_notification({"event": "test"})

        assert captured_headers is not None
        assert "X-Webhook-Signature" in captured_headers
        assert captured_headers["X-Webhook-Signature"].startswith("sha256=")

    @pytest.mark.asyncio
    async def test_send_notification_failure_with_retry_jitter(self):
        """Test notification failure uses jitter in retry delay."""
        from src.functions.services.webhook_service import WebhookService

        service = WebhookService(
            default_webhook_url="https://example.com/webhook",
            persist_failures=False,
        )

        mock_response = MagicMock()
        mock_response.is_success = False
        mock_response.status_code = 500

        sleep_calls = []

        async def capture_sleep(delay):
            sleep_calls.append(delay)

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            with patch("asyncio.sleep", side_effect=capture_sleep):
                result = await service.send_notification({"event": "test"})

            assert result is False
            # Should have 2 sleeps (between 3 attempts)
            assert len(sleep_calls) == 2
            # Delays should be different due to jitter (with high probability)
            # and should be in reasonable range
            assert all(d >= 2.0 for d in sleep_calls)  # Base delay is 2

    @pytest.mark.asyncio
    async def test_send_notification_no_retry(self):
        """Test notification failure without retry."""
        from src.functions.services.webhook_service import WebhookService

        service = WebhookService(
            default_webhook_url="https://example.com/webhook",
            persist_failures=False,
        )

        mock_response = MagicMock()
        mock_response.is_success = False
        mock_response.status_code = 400

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            result = await service.send_notification(
                {"event": "test"},
                retry=False,
                persist_on_failure=False,
            )

            assert result is False
            # Should only try once
            assert mock_instance.post.call_count == 1

    @pytest.mark.asyncio
    async def test_send_notification_timeout(self):
        """Test notification timeout handling."""
        from src.functions.services.webhook_service import WebhookService

        service = WebhookService(
            default_webhook_url="https://example.com/webhook",
            persist_failures=False,
        )

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.side_effect = httpx.TimeoutException("Timeout")
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            with patch("asyncio.sleep", new_callable=AsyncMock):
                result = await service.send_notification(
                    {"event": "test"},
                    persist_on_failure=False,
                )

            assert result is False

    @pytest.mark.asyncio
    async def test_send_notification_request_error(self):
        """Test notification request error handling."""
        from src.functions.services.webhook_service import WebhookService

        service = WebhookService(
            default_webhook_url="https://example.com/webhook",
            persist_failures=False,
        )

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.side_effect = httpx.RequestError("Connection failed")
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            with patch("asyncio.sleep", new_callable=AsyncMock):
                result = await service.send_notification(
                    {"event": "test"},
                    persist_on_failure=False,
                )

            assert result is False

    @pytest.mark.asyncio
    async def test_send_notification_unexpected_error(self):
        """Test notification handles unexpected exceptions."""
        from src.functions.services.webhook_service import WebhookService

        service = WebhookService(
            default_webhook_url="https://example.com/webhook",
            persist_failures=False,
        )

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.side_effect = RuntimeError("Unexpected error")
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            with patch("asyncio.sleep", new_callable=AsyncMock):
                result = await service.send_notification(
                    {"event": "test"},
                    persist_on_failure=False,
                )

            assert result is False

    @pytest.mark.asyncio
    async def test_send_notification_persists_failure(self):
        """Test that failed notification is persisted to Cosmos DB."""
        from src.functions.services.webhook_service import WebhookService

        mock_cosmos = AsyncMock()
        service = WebhookService(
            default_webhook_url="https://example.com/webhook",
            cosmos_service=mock_cosmos,
            persist_failures=True,
        )

        mock_response = MagicMock()
        mock_response.is_success = False
        mock_response.status_code = 500

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            with patch("asyncio.sleep", new_callable=AsyncMock):
                result = await service.send_notification({"event": "test"})

            assert result is False
            mock_cosmos.save_document.assert_called_once()

            # Verify the saved document structure
            call_args = mock_cosmos.save_document.call_args
            saved_doc = call_args.kwargs["document"]
            assert "id" in saved_doc
            assert saved_doc["webhookUrl"] == "https://example.com/webhook"
            assert saved_doc["payload"] == {"event": "test"}
            assert saved_doc["status_code"] == 500
            assert saved_doc["error_message"] == "HTTP 500"
            assert saved_doc["attempt_count"] == 3
            assert saved_doc["resolved"] is False

    @pytest.mark.asyncio
    async def test_send_notification_does_not_persist_when_disabled(self):
        """Test that failures are not persisted when disabled."""
        from src.functions.services.webhook_service import WebhookService

        mock_cosmos = AsyncMock()
        service = WebhookService(
            default_webhook_url="https://example.com/webhook",
            cosmos_service=mock_cosmos,
            persist_failures=False,
        )

        mock_response = MagicMock()
        mock_response.is_success = False
        mock_response.status_code = 500

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            with patch("asyncio.sleep", new_callable=AsyncMock):
                await service.send_notification({"event": "test"})

            mock_cosmos.save_document.assert_not_called()

    @pytest.mark.asyncio
    async def test_persist_failure_handles_cosmos_error(self, caplog):
        """Test that Cosmos errors during persistence are handled gracefully."""
        from src.functions.services.webhook_service import WebhookService

        mock_cosmos = AsyncMock()
        mock_cosmos.save_document.side_effect = Exception("Cosmos error")

        service = WebhookService(
            default_webhook_url="https://example.com/webhook",
            cosmos_service=mock_cosmos,
            persist_failures=True,
        )

        mock_response = MagicMock()
        mock_response.is_success = False
        mock_response.status_code = 500

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            with patch("asyncio.sleep", new_callable=AsyncMock):
                # Should not raise, just log error
                result = await service.send_notification({"event": "test"})

            assert result is False
            assert "Failed to persist webhook failure record" in caplog.text

    @pytest.mark.asyncio
    async def test_notify_processing_complete(self):
        """Test notify_processing_complete builds correct payload."""
        from src.functions.services.webhook_service import WebhookService

        service = WebhookService(
            default_webhook_url="https://example.com/webhook",
            persist_failures=False,
        )

        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.status_code = 200

        captured_payload = None

        async def capture_post(url, json, headers):
            nonlocal captured_payload
            captured_payload = json
            return mock_response

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post = capture_post
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            await service.notify_processing_complete(
                source_file="incoming/test.pdf",
                status="completed",
                forms_processed=3,
                total_forms=3,
                document_ids=["doc1", "doc2", "doc3"],
            )

        assert captured_payload is not None
        assert captured_payload["event"] == "document.processed"
        assert captured_payload["sourceFile"] == "incoming/test.pdf"
        assert captured_payload["status"] == "completed"
        assert captured_payload["formsProcessed"] == 3
        assert captured_payload["totalForms"] == 3
        assert captured_payload["documentIds"] == ["doc1", "doc2", "doc3"]
        assert "processedAt" in captured_payload

    @pytest.mark.asyncio
    async def test_notify_processing_complete_with_error(self):
        """Test notify_processing_complete includes error when provided."""
        from src.functions.services.webhook_service import WebhookService

        service = WebhookService(
            default_webhook_url="https://example.com/webhook",
            persist_failures=False,
        )

        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.status_code = 200

        captured_payload = None

        async def capture_post(url, json, headers):
            nonlocal captured_payload
            captured_payload = json
            return mock_response

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post = capture_post
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            await service.notify_processing_complete(
                source_file="incoming/test.pdf",
                status="failed",
                forms_processed=0,
                total_forms=3,
                document_ids=[],
                error="Document Intelligence rate limit exceeded",
            )

        assert captured_payload["error"] == "Document Intelligence rate limit exceeded"

    @pytest.mark.asyncio
    async def test_notify_dead_letter(self):
        """Test notify_dead_letter builds correct payload."""
        from src.functions.services.webhook_service import WebhookService

        service = WebhookService(
            default_webhook_url="https://example.com/webhook",
            persist_failures=False,
        )

        mock_response = MagicMock()
        mock_response.is_success = True
        mock_response.status_code = 200

        captured_payload = None

        async def capture_post(url, json, headers):
            nonlocal captured_payload
            captured_payload = json
            return mock_response

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post = capture_post
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            await service.notify_dead_letter(
                source_file="incoming/failed.pdf",
                reason="Max retries exceeded",
                retry_count=3,
            )

        assert captured_payload is not None
        assert captured_payload["event"] == "document.dead_letter"
        assert captured_payload["sourceFile"] == "incoming/failed.pdf"
        assert captured_payload["reason"] == "Max retries exceeded"
        assert captured_payload["retryCount"] == 3
        assert "timestamp" in captured_payload


class TestWebhookServiceSingleton:
    """Tests for webhook service singleton."""

    def test_get_webhook_service_singleton(self):
        """Test get_webhook_service returns singleton."""
        # Reset singleton
        import src.functions.services.webhook_service as ws_module

        ws_module._webhook_service = None

        from src.functions.services.webhook_service import get_webhook_service

        service1 = get_webhook_service()
        service2 = get_webhook_service()

        assert service1 is service2

    def test_reset_webhook_service(self):
        """Test reset_webhook_service clears singleton."""
        import src.functions.services.webhook_service as ws_module

        ws_module._webhook_service = None

        from src.functions.services.webhook_service import (
            get_webhook_service,
            reset_webhook_service,
        )

        service1 = get_webhook_service()
        reset_webhook_service()
        service2 = get_webhook_service()

        assert service1 is not service2
