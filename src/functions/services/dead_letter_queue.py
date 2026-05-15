"""Dead Letter Queue service for failed message handling.

Provides storage and management of failed processing items that exceeded
retry limits or encountered unrecoverable errors.

Features:
- Persistent storage to Cosmos DB
- Queryable by status, error type, source file
- Manual retry mechanism
- Monitoring and alerting integration
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class DeadLetterReason(Enum):
    """Reasons for dead lettering a message."""

    MAX_RETRIES_EXCEEDED = "max_retries_exceeded"
    UNRECOVERABLE_ERROR = "unrecoverable_error"
    INVALID_FORMAT = "invalid_format"
    POISON_MESSAGE = "poison_message"
    TIMEOUT = "timeout"
    DEPENDENCY_FAILURE = "dependency_failure"


class DeadLetterStatus(Enum):
    """Status of dead letter items."""

    PENDING = "pending"  # Waiting for investigation
    INVESTIGATING = "investigating"  # Being looked at
    RETRY_SCHEDULED = "retry_scheduled"  # Scheduled for retry
    RESOLVED = "resolved"  # Issue fixed
    ABANDONED = "abandoned"  # Will not be retried


@dataclass
class DeadLetterItem:
    """Represents a dead-lettered message."""

    id: str
    source_file: str
    blob_url: str
    model_id: str
    reason: DeadLetterReason
    status: DeadLetterStatus = DeadLetterStatus.PENDING
    error_message: str = ""
    error_details: dict[str, Any] = field(default_factory=dict)
    retry_count: int = 0
    max_retries: int = 3
    original_timestamp: datetime | None = None
    dead_lettered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_retry_at: datetime | None = None
    resolved_at: datetime | None = None
    notes: list[str] = field(default_factory=list)
    tenant_id: str | None = None

    def to_cosmos_document(self) -> dict[str, Any]:
        """Convert to Cosmos DB document format."""
        return {
            "id": self.id,
            "sourceFile": self.source_file,  # Partition key
            "documentType": "dead_letter",
            "blobUrl": self.blob_url,
            "modelId": self.model_id,
            "reason": self.reason.value,
            "status": self.status.value,
            "errorMessage": self.error_message,
            "errorDetails": self.error_details,
            "retryCount": self.retry_count,
            "maxRetries": self.max_retries,
            "originalTimestamp": (
                self.original_timestamp.isoformat() if self.original_timestamp else None
            ),
            "deadLetteredAt": self.dead_lettered_at.isoformat(),
            "lastRetryAt": self.last_retry_at.isoformat() if self.last_retry_at else None,
            "resolvedAt": self.resolved_at.isoformat() if self.resolved_at else None,
            "notes": self.notes,
            "tenantId": self.tenant_id,
        }

    @classmethod
    def from_cosmos_document(cls, doc: dict[str, Any]) -> "DeadLetterItem":
        """Create from Cosmos DB document."""
        return cls(
            id=doc["id"],
            source_file=doc["sourceFile"],
            blob_url=doc.get("blobUrl", ""),
            model_id=doc.get("modelId", ""),
            reason=DeadLetterReason(doc["reason"]),
            status=DeadLetterStatus(doc.get("status", "pending")),
            error_message=doc.get("errorMessage", ""),
            error_details=doc.get("errorDetails", {}),
            retry_count=doc.get("retryCount", 0),
            max_retries=doc.get("maxRetries", 3),
            original_timestamp=(
                datetime.fromisoformat(doc["originalTimestamp"])
                if doc.get("originalTimestamp")
                else None
            ),
            dead_lettered_at=datetime.fromisoformat(doc["deadLetteredAt"]),
            last_retry_at=(
                datetime.fromisoformat(doc["lastRetryAt"]) if doc.get("lastRetryAt") else None
            ),
            resolved_at=(
                datetime.fromisoformat(doc["resolvedAt"]) if doc.get("resolvedAt") else None
            ),
            notes=doc.get("notes", []),
            tenant_id=doc.get("tenantId"),
        )


class DeadLetterQueueError(Exception):
    """Base exception for dead letter queue errors."""

    pass


class DeadLetterQueueService:
    """Service for managing dead letter queue.

    Uses Cosmos DB for persistent storage of dead-lettered messages.
    Supports querying, manual retry, and status updates.
    """

    def __init__(self, cosmos_service: Any) -> None:
        """Initialize DLQ service.

        Args:
            cosmos_service: CosmosService instance for persistence
        """
        self.cosmos = cosmos_service

    async def add_item(
        self,
        source_file: str,
        blob_url: str,
        model_id: str,
        reason: DeadLetterReason,
        error_message: str,
        error_details: dict[str, Any] | None = None,
        retry_count: int = 0,
        tenant_id: str | None = None,
        original_timestamp: datetime | None = None,
    ) -> DeadLetterItem:
        """Add an item to the dead letter queue.

        Args:
            source_file: Source file path (partition key)
            blob_url: URL of the blob that failed
            model_id: Document Intelligence model used
            reason: Reason for dead lettering
            error_message: Human-readable error message
            error_details: Additional error details
            retry_count: Number of retries attempted
            tenant_id: Optional tenant identifier
            original_timestamp: When the original request was made

        Returns:
            DeadLetterItem: The created dead letter item
        """
        # Generate unique ID
        item_id = f"dlq_{source_file.replace('/', '_').replace('.', '_')}_{int(datetime.now(timezone.utc).timestamp() * 1000)}"

        item = DeadLetterItem(
            id=item_id,
            source_file=source_file,
            blob_url=blob_url,
            model_id=model_id,
            reason=reason,
            error_message=error_message,
            error_details=error_details or {},
            retry_count=retry_count,
            tenant_id=tenant_id,
            original_timestamp=original_timestamp,
        )

        await self.cosmos.save_document_result(item.to_cosmos_document())

        logger.warning(
            f"Added item to dead letter queue: {source_file} "
            f"(reason: {reason.value}, retries: {retry_count})"
        )

        return item

    async def get_item(self, item_id: str, source_file: str) -> DeadLetterItem | None:
        """Get a dead letter item by ID.

        Args:
            item_id: Dead letter item ID
            source_file: Source file (partition key)

        Returns:
            DeadLetterItem if found, None otherwise
        """
        doc = await self.cosmos.get_document(item_id, source_file)
        if doc and doc.get("documentType") == "dead_letter":
            return DeadLetterItem.from_cosmos_document(doc)
        return None

    async def update_status(
        self,
        item_id: str,
        source_file: str,
        status: DeadLetterStatus,
        note: str | None = None,
    ) -> DeadLetterItem | None:
        """Update the status of a dead letter item.

        Args:
            item_id: Dead letter item ID
            source_file: Source file (partition key)
            status: New status
            note: Optional note about the status change

        Returns:
            Updated DeadLetterItem if found, None otherwise
        """
        doc = await self.cosmos.get_document(item_id, source_file)
        if not doc or doc.get("documentType") != "dead_letter":
            return None

        item = DeadLetterItem.from_cosmos_document(doc)
        item.status = status

        if note:
            timestamp = datetime.now(timezone.utc).isoformat()
            item.notes.append(f"[{timestamp}] {note}")

        if status == DeadLetterStatus.RESOLVED:
            item.resolved_at = datetime.now(timezone.utc)

        await self.cosmos.save_document_result(item.to_cosmos_document())

        logger.info(f"Updated dead letter item {item_id} status to {status.value}")
        return item

    async def schedule_retry(
        self,
        item_id: str,
        source_file: str,
        note: str | None = None,
    ) -> DeadLetterItem | None:
        """Schedule a dead letter item for retry.

        Args:
            item_id: Dead letter item ID
            source_file: Source file (partition key)
            note: Optional note about the retry

        Returns:
            Updated DeadLetterItem if found, None otherwise
        """
        doc = await self.cosmos.get_document(item_id, source_file)
        if not doc or doc.get("documentType") != "dead_letter":
            return None

        item = DeadLetterItem.from_cosmos_document(doc)

        if item.retry_count >= item.max_retries:
            logger.warning(f"Cannot retry {item_id}: max retries ({item.max_retries}) exceeded")
            return None

        item.status = DeadLetterStatus.RETRY_SCHEDULED
        item.last_retry_at = datetime.now(timezone.utc)
        item.retry_count += 1

        if note:
            timestamp = datetime.now(timezone.utc).isoformat()
            item.notes.append(f"[{timestamp}] Retry scheduled: {note}")
        else:
            timestamp = datetime.now(timezone.utc).isoformat()
            item.notes.append(f"[{timestamp}] Retry #{item.retry_count} scheduled")

        await self.cosmos.save_document_result(item.to_cosmos_document())

        logger.info(f"Scheduled retry for dead letter item {item_id}")
        return item

    async def query_by_status(
        self,
        status: DeadLetterStatus,
        limit: int = 100,
    ) -> list[DeadLetterItem]:
        """Query dead letter items by status.

        Args:
            status: Status to filter by
            limit: Maximum items to return

        Returns:
            List of matching DeadLetterItems
        """
        query = """
            SELECT TOP @limit * FROM c
            WHERE c.documentType = 'dead_letter' AND c.status = @status
            ORDER BY c.deadLetteredAt DESC
        """
        parameters = [
            {"name": "@status", "value": status.value},
            {"name": "@limit", "value": limit},
        ]

        docs = await self.cosmos.query_documents(query=query, parameters=parameters)
        return [DeadLetterItem.from_cosmos_document(doc) for doc in docs]

    async def query_by_reason(
        self,
        reason: DeadLetterReason,
        limit: int = 100,
    ) -> list[DeadLetterItem]:
        """Query dead letter items by reason.

        Args:
            reason: Reason to filter by
            limit: Maximum items to return

        Returns:
            List of matching DeadLetterItems
        """
        query = """
            SELECT TOP @limit * FROM c
            WHERE c.documentType = 'dead_letter' AND c.reason = @reason
            ORDER BY c.deadLetteredAt DESC
        """
        parameters = [
            {"name": "@reason", "value": reason.value},
            {"name": "@limit", "value": limit},
        ]

        docs = await self.cosmos.query_documents(query=query, parameters=parameters)
        return [DeadLetterItem.from_cosmos_document(doc) for doc in docs]

    async def query_by_source_file(
        self,
        source_file: str,
    ) -> list[DeadLetterItem]:
        """Query dead letter items for a source file.

        Args:
            source_file: Source file to filter by (partition key)

        Returns:
            List of matching DeadLetterItems
        """
        query = """
            SELECT * FROM c
            WHERE c.documentType = 'dead_letter' AND c.sourceFile = @sourceFile
            ORDER BY c.deadLetteredAt DESC
        """
        parameters = [{"name": "@sourceFile", "value": source_file}]

        docs = await self.cosmos.query_documents(
            query=query,
            parameters=parameters,
            partition_key=source_file,
        )
        return [DeadLetterItem.from_cosmos_document(doc) for doc in docs]

    async def get_statistics(self) -> dict[str, Any]:
        """Get dead letter queue statistics.

        Returns:
            Dictionary with DLQ statistics
        """
        query = """
            SELECT
                c.status,
                c.reason,
                COUNT(1) as count
            FROM c
            WHERE c.documentType = 'dead_letter'
            GROUP BY c.status, c.reason
        """

        docs = await self.cosmos.query_documents(query=query)

        # Aggregate results
        by_status: dict[str, int] = {}
        by_reason: dict[str, int] = {}
        total = 0

        for doc in docs:
            status = doc.get("status", "unknown")
            reason = doc.get("reason", "unknown")
            count = doc.get("count", 0)

            by_status[status] = by_status.get(status, 0) + count
            by_reason[reason] = by_reason.get(reason, 0) + count
            total += count

        return {
            "total": total,
            "byStatus": by_status,
            "byReason": by_reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def query_ready_for_retry(
        self,
        limit: int = 50,
    ) -> list[DeadLetterItem]:
        """Query dead letter items that are ready for automatic retry.

        Returns items that:
        - Have status PENDING or RETRY_SCHEDULED
        - Have retry_count < max_retries
        - Are not ABANDONED, RESOLVED, or permanently failed

        Args:
            limit: Maximum items to return

        Returns:
            List of DeadLetterItems ready for retry
        """
        query = """
            SELECT TOP @limit * FROM c
            WHERE c.documentType = 'dead_letter'
            AND c.status IN ('pending', 'retry_scheduled')
            AND c.retryCount < c.maxRetries
            ORDER BY c.deadLetteredAt ASC
        """
        parameters = [{"name": "@limit", "value": limit}]

        docs = await self.cosmos.query_documents(query=query, parameters=parameters)
        return [DeadLetterItem.from_cosmos_document(doc) for doc in docs]

    async def mark_retry_in_progress(
        self,
        item_id: str,
        source_file: str,
    ) -> DeadLetterItem | None:
        """Mark a dead letter item as being retried.

        Args:
            item_id: Dead letter item ID
            source_file: Source file (partition key)

        Returns:
            Updated DeadLetterItem if found, None otherwise
        """
        doc = await self.cosmos.get_document(item_id, source_file)
        if not doc or doc.get("documentType") != "dead_letter":
            return None

        item = DeadLetterItem.from_cosmos_document(doc)
        item.status = DeadLetterStatus.INVESTIGATING
        item.last_retry_at = datetime.now(timezone.utc)

        timestamp = datetime.now(timezone.utc).isoformat()
        item.notes.append(f"[{timestamp}] Auto-retry started (attempt {item.retry_count + 1})")

        await self.cosmos.save_document_result(item.to_cosmos_document())
        return item

    async def mark_retry_success(
        self,
        item_id: str,
        source_file: str,
        note: str | None = None,
    ) -> DeadLetterItem | None:
        """Mark a dead letter item as successfully retried.

        Args:
            item_id: Dead letter item ID
            source_file: Source file (partition key)
            note: Optional note about the resolution

        Returns:
            Updated DeadLetterItem if found, None otherwise
        """
        doc = await self.cosmos.get_document(item_id, source_file)
        if not doc or doc.get("documentType") != "dead_letter":
            return None

        item = DeadLetterItem.from_cosmos_document(doc)
        item.status = DeadLetterStatus.RESOLVED
        item.resolved_at = datetime.now(timezone.utc)
        item.retry_count += 1

        timestamp = datetime.now(timezone.utc).isoformat()
        resolution_note = note or "Successfully processed on auto-retry"
        item.notes.append(f"[{timestamp}] Resolved: {resolution_note}")

        await self.cosmos.save_document_result(item.to_cosmos_document())
        logger.info(f"Dead letter item {item_id} resolved after retry")
        return item

    async def mark_retry_failed(
        self,
        item_id: str,
        source_file: str,
        error_message: str,
        permanent: bool = False,
    ) -> DeadLetterItem | None:
        """Mark a dead letter retry as failed.

        Args:
            item_id: Dead letter item ID
            source_file: Source file (partition key)
            error_message: Error that occurred during retry
            permanent: If True, marks as ABANDONED (no more retries)

        Returns:
            Updated DeadLetterItem if found, None otherwise
        """
        doc = await self.cosmos.get_document(item_id, source_file)
        if not doc or doc.get("documentType") != "dead_letter":
            return None

        item = DeadLetterItem.from_cosmos_document(doc)
        item.retry_count += 1
        item.last_retry_at = datetime.now(timezone.utc)
        item.error_message = error_message

        timestamp = datetime.now(timezone.utc).isoformat()

        if permanent or item.retry_count >= item.max_retries:
            item.status = DeadLetterStatus.ABANDONED
            item.notes.append(
                f"[{timestamp}] Permanently failed: {error_message} "
                f"(retry {item.retry_count}/{item.max_retries})"
            )
            logger.warning(
                f"Dead letter item {item_id} permanently failed after {item.retry_count} retries"
            )
        else:
            item.status = DeadLetterStatus.PENDING
            item.notes.append(
                f"[{timestamp}] Retry failed: {error_message} "
                f"(retry {item.retry_count}/{item.max_retries})"
            )

        await self.cosmos.save_document_result(item.to_cosmos_document())
        return item

    async def delete_resolved(self, older_than_days: int = 30) -> int:
        """Delete resolved dead letter items older than specified days.

        Args:
            older_than_days: Delete items resolved more than this many days ago

        Returns:
            Number of items deleted
        """
        cutoff = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        # Subtract days manually to avoid timedelta import
        cutoff = cutoff.replace(day=cutoff.day - older_than_days)

        query = """
            SELECT c.id, c.sourceFile FROM c
            WHERE c.documentType = 'dead_letter'
            AND c.status = 'resolved'
            AND c.resolvedAt < @cutoff
        """
        parameters = [{"name": "@cutoff", "value": cutoff.isoformat()}]

        docs = await self.cosmos.query_documents(query=query, parameters=parameters)

        deleted = 0
        for doc in docs:
            if await self.cosmos.delete_document(doc["id"], doc["sourceFile"]):
                deleted += 1

        logger.info(f"Deleted {deleted} resolved dead letter items")
        return deleted


# Global service instance
_dlq_service: DeadLetterQueueService | None = None


def get_dead_letter_queue_service() -> DeadLetterQueueService | None:
    """Get or create DeadLetterQueueService singleton.

    Returns:
        DeadLetterQueueService instance or None if Cosmos not configured
    """
    global _dlq_service
    if _dlq_service is None:
        # Import here to avoid circular dependency
        from . import get_cosmos_service

        cosmos = get_cosmos_service()
        if cosmos:
            _dlq_service = DeadLetterQueueService(cosmos)
            logger.info("Dead letter queue service initialized")
    return _dlq_service


def reset_dead_letter_queue_service() -> None:
    """Reset service instance (for testing)."""
    global _dlq_service
    _dlq_service = None
