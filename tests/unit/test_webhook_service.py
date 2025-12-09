"""Unit tests for the webhook service."""

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


class TestWebhookService:
    """Tests for WebhookService class."""

    def test_init_without_url(self):
        """Test initialization without URL."""
        with patch.dict("os.environ", {}, clear=True):
            from src.functions.services.webhook_service import WebhookService

            service = WebhookService()
            assert service.default_webhook_url is None
            assert service.timeout == 30

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

    def test_init_with_explicit_url(self):
        """Test initialization with explicit URL."""
        from src.functions.services.webhook_service import WebhookService

        service = WebhookService(
            default_webhook_url="https://custom.com/hook",
            timeout=60,
        )

        assert service.default_webhook_url == "https://custom.com/hook"
        assert service.timeout == 60

    @pytest.mark.asyncio
    async def test_send_notification_no_url(self, caplog):
        """Test send_notification returns False when no URL configured."""
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

        service = WebhookService(default_webhook_url="https://example.com/webhook")

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
    async def test_send_notification_failure_with_retry(self):
        """Test notification failure with retry."""
        from src.functions.services.webhook_service import WebhookService

        service = WebhookService(default_webhook_url="https://example.com/webhook")

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
            # Should have retried 3 times
            assert mock_instance.post.call_count == 3

    @pytest.mark.asyncio
    async def test_send_notification_no_retry(self):
        """Test notification failure without retry."""
        from src.functions.services.webhook_service import WebhookService

        service = WebhookService(default_webhook_url="https://example.com/webhook")

        mock_response = MagicMock()
        mock_response.is_success = False
        mock_response.status_code = 400

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.return_value = mock_response
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            result = await service.send_notification({"event": "test"}, retry=False)

            assert result is False
            # Should only try once
            assert mock_instance.post.call_count == 1

    @pytest.mark.asyncio
    async def test_send_notification_timeout(self):
        """Test notification timeout handling."""
        from src.functions.services.webhook_service import WebhookService

        service = WebhookService(default_webhook_url="https://example.com/webhook")

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.side_effect = httpx.TimeoutException("Timeout")
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            with patch("asyncio.sleep", new_callable=AsyncMock):
                result = await service.send_notification({"event": "test"})

            assert result is False

    @pytest.mark.asyncio
    async def test_send_notification_request_error(self):
        """Test notification request error handling."""
        from src.functions.services.webhook_service import WebhookService

        service = WebhookService(default_webhook_url="https://example.com/webhook")

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.side_effect = httpx.RequestError("Connection failed")
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_client.return_value = mock_instance

            with patch("asyncio.sleep", new_callable=AsyncMock):
                result = await service.send_notification({"event": "test"})

            assert result is False

    @pytest.mark.asyncio
    async def test_notify_processing_complete(self):
        """Test notify_processing_complete builds correct payload."""
        from src.functions.services.webhook_service import WebhookService

        service = WebhookService(default_webhook_url="https://example.com/webhook")

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

        service = WebhookService(default_webhook_url="https://example.com/webhook")

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

        service = WebhookService(default_webhook_url="https://example.com/webhook")

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
