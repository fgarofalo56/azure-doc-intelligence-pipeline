"""Webhook notification service for processing completion callbacks.

Sends HTTP POST notifications to configured webhook URLs when document
processing completes. Supports HMAC-SHA256 signing for payload verification.
"""

import asyncio
import hashlib
import hmac
import json
import logging
import os
import random
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# Default timeout for webhook requests (seconds)
DEFAULT_TIMEOUT = 30

# Maximum retry attempts for failed webhooks
MAX_RETRIES = 3

# Base delay between retries (seconds)
RETRY_DELAY = 2

# Maximum jitter to add to retry delay (seconds)
RETRY_JITTER_MAX = 1.0

# Container for failed webhook deliveries
WEBHOOK_FAILURES_CONTAINER = "WebhookFailures"


@dataclass
class WebhookDeliveryRecord:
    """Record of a failed webhook delivery attempt for persistence."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    webhook_url: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    status_code: int | None = None
    error_message: str = ""
    attempt_count: int = 0
    first_attempt_at: str = ""
    last_attempt_at: str = ""
    next_retry_at: str | None = None
    resolved: bool = False
    resolved_at: str | None = None

    def to_cosmos_document(self) -> dict[str, Any]:
        """Convert to Cosmos DB document format."""
        doc = asdict(self)
        # Use webhook URL as partition key for grouping
        doc["webhookUrl"] = self.webhook_url
        return doc


class WebhookError(Exception):
    """Exception raised when webhook delivery fails."""

    def __init__(self, url: str, reason: str, status_code: int | None = None):
        self.url = url
        self.reason = reason
        self.status_code = status_code
        super().__init__(f"Webhook failed for {url}: {reason}")


def compute_hmac_signature(payload: dict[str, Any], secret: str) -> str:
    """Compute HMAC-SHA256 signature for a webhook payload.

    Args:
        payload: The JSON payload to sign.
        secret: The shared secret key.

    Returns:
        Hex-encoded HMAC-SHA256 signature.
    """
    payload_bytes = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    signature = hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256)
    return signature.hexdigest()


def calculate_retry_delay(attempt: int, base_delay: float = RETRY_DELAY, jitter_max: float = RETRY_JITTER_MAX) -> float:
    """Calculate retry delay with exponential backoff and jitter.

    Args:
        attempt: Current attempt number (1-indexed).
        base_delay: Base delay in seconds.
        jitter_max: Maximum jitter to add in seconds.

    Returns:
        Delay in seconds with jitter applied.
    """
    # Exponential backoff: base_delay * attempt
    delay = base_delay * attempt
    # Add random jitter to prevent thundering herd
    jitter = random.uniform(0, jitter_max)
    return delay + jitter


class WebhookService:
    """Service for sending webhook notifications with HMAC signing and retry jitter."""

    def __init__(
        self,
        default_webhook_url: str | None = None,
        timeout: int = DEFAULT_TIMEOUT,
        signing_secret: str | None = None,
        cosmos_service: Any | None = None,
        persist_failures: bool = True,
    ) -> None:
        """Initialize webhook service.

        Args:
            default_webhook_url: Default URL for webhooks if not specified per-request.
            timeout: Request timeout in seconds.
            signing_secret: HMAC signing secret for payload verification.
            cosmos_service: Optional Cosmos DB service for persisting failed deliveries.
            persist_failures: Whether to persist failed deliveries to Cosmos DB.
        """
        self.default_webhook_url = default_webhook_url or os.environ.get("WEBHOOK_URL")
        self.timeout = timeout
        self.signing_secret = signing_secret or os.environ.get("WEBHOOK_SIGNING_SECRET")
        self._cosmos_service = cosmos_service
        self.persist_failures = persist_failures

    def _build_headers(self, payload: dict[str, Any]) -> dict[str, str]:
        """Build request headers including optional HMAC signature.

        Args:
            payload: The JSON payload being sent.

        Returns:
            Dictionary of HTTP headers.
        """
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Azure-DocIntel-Pipeline/1.0",
        }

        if self.signing_secret:
            signature = compute_hmac_signature(payload, self.signing_secret)
            headers["X-Webhook-Signature"] = f"sha256={signature}"

        return headers

    async def _persist_failure(
        self,
        url: str,
        payload: dict[str, Any],
        error_message: str,
        status_code: int | None,
        attempt_count: int,
        first_attempt_at: str,
    ) -> None:
        """Persist a failed webhook delivery to Cosmos DB.

        Args:
            url: Webhook URL that failed.
            payload: The payload that failed to deliver.
            error_message: Error description.
            status_code: HTTP status code if available.
            attempt_count: Total number of attempts made.
            first_attempt_at: ISO timestamp of first attempt.
        """
        if not self.persist_failures:
            return

        try:
            # Lazy import to avoid circular dependency
            if self._cosmos_service is None:
                from . import get_cosmos_service
                self._cosmos_service = get_cosmos_service()

            now = datetime.now(timezone.utc).isoformat()

            # Calculate next retry time (exponential backoff from last attempt)
            next_delay = calculate_retry_delay(attempt_count + 1)
            next_retry = datetime.now(timezone.utc).timestamp() + next_delay * 60  # minutes
            next_retry_at = datetime.fromtimestamp(next_retry, tz=timezone.utc).isoformat()

            record = WebhookDeliveryRecord(
                webhook_url=url,
                payload=payload,
                status_code=status_code,
                error_message=error_message,
                attempt_count=attempt_count,
                first_attempt_at=first_attempt_at,
                last_attempt_at=now,
                next_retry_at=next_retry_at,
                resolved=False,
            )

            await self._cosmos_service.save_document(
                document=record.to_cosmos_document(),
                partition_key=url,
                container_name=WEBHOOK_FAILURES_CONTAINER,
            )
            logger.info(f"Persisted failed webhook delivery: {record.id}")

        except Exception as e:
            # Don't fail the whole operation if persistence fails
            logger.error(f"Failed to persist webhook failure record: {e}")

    async def send_notification(
        self,
        payload: dict[str, Any],
        webhook_url: str | None = None,
        retry: bool = True,
        persist_on_failure: bool = True,
    ) -> bool:
        """Send a webhook notification with HMAC signing.

        Args:
            payload: JSON payload to send.
            webhook_url: Target URL (uses default if not specified).
            retry: Whether to retry on failure.
            persist_on_failure: Whether to persist failed delivery to Cosmos DB.

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
        last_error_message: str = ""
        last_status_code: int | None = None
        first_attempt_at = datetime.now(timezone.utc).isoformat()

        headers = self._build_headers(payload)

        for attempt in range(1, attempts + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(
                        url,
                        json=payload,
                        headers=headers,
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
                    last_error_message = f"HTTP {response.status_code}"
                    last_status_code = response.status_code

            except httpx.TimeoutException as e:
                logger.warning(f"Webhook timeout (attempt {attempt}/{attempts}): {e}")
                last_error_message = "Request timeout"
                last_status_code = None

            except httpx.RequestError as e:
                logger.warning(f"Webhook request failed (attempt {attempt}/{attempts}): {e}")
                last_error_message = str(e)
                last_status_code = None

            except Exception as e:
                logger.error(f"Unexpected webhook error: {e}")
                last_error_message = str(e)
                last_status_code = None

            # Wait before retry with jitter
            if attempt < attempts:
                delay = calculate_retry_delay(attempt)
                await asyncio.sleep(delay)

        # All attempts failed
        logger.error(f"Webhook delivery failed after {attempts} attempts to {url}")

        # Persist failure for later retry
        if persist_on_failure:
            await self._persist_failure(
                url=url,
                payload=payload,
                error_message=last_error_message,
                status_code=last_status_code,
                attempt_count=attempts,
                first_attempt_at=first_attempt_at,
            )

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


def reset_webhook_service() -> None:
    """Reset the webhook service singleton for testing."""
    global _webhook_service
    _webhook_service = None
