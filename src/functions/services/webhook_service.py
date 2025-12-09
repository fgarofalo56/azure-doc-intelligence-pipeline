"""Webhook notification service for processing completion callbacks.

Sends HTTP POST notifications to configured webhook URLs when document
processing completes.
"""

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# Default timeout for webhook requests (seconds)
DEFAULT_TIMEOUT = 30

# Maximum retry attempts for failed webhooks
MAX_RETRIES = 3

# Delay between retries (seconds)
RETRY_DELAY = 2


class WebhookError(Exception):
    """Exception raised when webhook delivery fails."""

    def __init__(self, url: str, reason: str, status_code: int | None = None):
        self.url = url
        self.reason = reason
        self.status_code = status_code
        super().__init__(f"Webhook failed for {url}: {reason}")


class WebhookService:
    """Service for sending webhook notifications."""

    def __init__(
        self,
        default_webhook_url: str | None = None,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> None:
        """Initialize webhook service.

        Args:
            default_webhook_url: Default URL for webhooks if not specified per-request.
            timeout: Request timeout in seconds.
        """
        self.default_webhook_url = default_webhook_url or os.environ.get("WEBHOOK_URL")
        self.timeout = timeout

    async def send_notification(
        self,
        payload: dict[str, Any],
        webhook_url: str | None = None,
        retry: bool = True,
    ) -> bool:
        """Send a webhook notification.

        Args:
            payload: JSON payload to send.
            webhook_url: Target URL (uses default if not specified).
            retry: Whether to retry on failure.

        Returns:
            True if notification sent successfully, False otherwise.

        Raises:
            WebhookError: If delivery fails after all retries.
        """
        url = webhook_url or self.default_webhook_url

        if not url:
            logger.debug("No webhook URL configured, skipping notification")
            return False

        attempts = MAX_RETRIES if retry else 1
        _last_error: Exception | None = None  # Track error for potential future use

        for attempt in range(1, attempts + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(
                        url,
                        json=payload,
                        headers={
                            "Content-Type": "application/json",
                            "User-Agent": "Azure-DocIntel-Pipeline/1.0",
                        },
                    )

                    if response.is_success:
                        logger.info(
                            f"Webhook delivered successfully to {url} "
                            f"(status={response.status_code})"
                        )
                        return True

                    logger.warning(
                        f"Webhook returned non-success status: {response.status_code} "
                        f"(attempt {attempt}/{attempts})"
                    )
                    _last_error = WebhookError(
                        url=url,
                        reason=f"HTTP {response.status_code}",
                        status_code=response.status_code,
                    )

            except httpx.TimeoutException as e:
                logger.warning(f"Webhook timeout (attempt {attempt}/{attempts}): {e}")
                _last_error = WebhookError(url=url, reason="Request timeout")

            except httpx.RequestError as e:
                logger.warning(f"Webhook request failed (attempt {attempt}/{attempts}): {e}")
                _last_error = WebhookError(url=url, reason=str(e))

            except Exception as e:
                logger.error(f"Unexpected webhook error: {e}")
                _last_error = WebhookError(url=url, reason=str(e))

            # Wait before retry
            if attempt < attempts:
                await asyncio.sleep(RETRY_DELAY * attempt)

        # All attempts failed
        logger.error(f"Webhook delivery failed after {attempts} attempts to {url}")
        return False

    async def notify_processing_complete(
        self,
        source_file: str,
        status: str,
        forms_processed: int,
        total_forms: int,
        document_ids: list[str],
        error: str | None = None,
        webhook_url: str | None = None,
    ) -> bool:
        """Send notification when document processing completes.

        Args:
            source_file: Original PDF file path.
            status: Processing status (completed, failed, partial).
            forms_processed: Number of forms successfully processed.
            total_forms: Total number of forms in the document.
            document_ids: List of Cosmos DB document IDs created.
            error: Error message if processing failed.
            webhook_url: Target URL (uses default if not specified).

        Returns:
            True if notification sent successfully.
        """
        payload = {
            "event": "document.processed",
            "sourceFile": source_file,
            "status": status,
            "processedAt": datetime.now(timezone.utc).isoformat(),
            "formsProcessed": forms_processed,
            "totalForms": total_forms,
            "documentIds": document_ids,
        }

        if error:
            payload["error"] = error

        return await self.send_notification(
            payload=payload,
            webhook_url=webhook_url,
        )

    async def notify_dead_letter(
        self,
        source_file: str,
        reason: str,
        retry_count: int,
        webhook_url: str | None = None,
    ) -> bool:
        """Send notification when document is moved to dead letter queue.

        Args:
            source_file: Original PDF file path.
            reason: Reason for moving to dead letter.
            retry_count: Number of processing attempts.
            webhook_url: Target URL (uses default if not specified).

        Returns:
            True if notification sent successfully.
        """
        payload = {
            "event": "document.dead_letter",
            "sourceFile": source_file,
            "reason": reason,
            "retryCount": retry_count,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        return await self.send_notification(
            payload=payload,
            webhook_url=webhook_url,
        )


# Singleton instance
_webhook_service: WebhookService | None = None


def get_webhook_service() -> WebhookService:
    """Get or create the webhook service singleton.

    Returns:
        WebhookService instance.
    """
    global _webhook_service
    if _webhook_service is None:
        _webhook_service = WebhookService()
    return _webhook_service
