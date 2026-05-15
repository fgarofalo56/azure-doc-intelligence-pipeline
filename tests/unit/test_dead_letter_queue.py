"""Unit tests for dead letter queue service."""

import os
import sys
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add src/functions to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src/functions"))


class TestDeadLetterReason:
    """Tests for DeadLetterReason enum."""

    def test_reason_values(self):
        """Test reason enum values."""
        from services.dead_letter_queue import DeadLetterReason

        assert DeadLetterReason.MAX_RETRIES_EXCEEDED.value == "max_retries_exceeded"
        assert DeadLetterReason.UNRECOVERABLE_ERROR.value == "unrecoverable_error"
        assert DeadLetterReason.INVALID_FORMAT.value == "invalid_format"
        assert DeadLetterReason.POISON_MESSAGE.value == "poison_message"
        assert DeadLetterReason.TIMEOUT.value == "timeout"
        assert DeadLetterReason.DEPENDENCY_FAILURE.value == "dependency_failure"


class TestDeadLetterStatus:
    """Tests for DeadLetterStatus enum."""

    def test_status_values(self):
        """Test status enum values."""
        from services.dead_letter_queue import DeadLetterStatus

        assert DeadLetterStatus.PENDING.value == "pending"
        assert DeadLetterStatus.INVESTIGATING.value == "investigating"
        assert DeadLetterStatus.RETRY_SCHEDULED.value == "retry_scheduled"
        assert DeadLetterStatus.RESOLVED.value == "resolved"
        assert DeadLetterStatus.ABANDONED.value == "abandoned"


class TestDeadLetterItem:
    """Tests for DeadLetterItem dataclass."""

    def test_create_item(self):
        """Test creating a dead letter item."""
        from services.dead_letter_queue import (
            DeadLetterItem,
            DeadLetterReason,
            DeadLetterStatus,
        )

        item = DeadLetterItem(
            id="dlq_test_1",
            source_file="folder/test.pdf",
            blob_url="https://storage.blob/test.pdf",
            model_id="custom-model",
            reason=DeadLetterReason.MAX_RETRIES_EXCEEDED,
        )

        assert item.id == "dlq_test_1"
        assert item.source_file == "folder/test.pdf"
        assert item.status == DeadLetterStatus.PENDING
        assert item.retry_count == 0

    def test_to_cosmos_document(self):
        """Test conversion to Cosmos DB document."""
        from services.dead_letter_queue import DeadLetterItem, DeadLetterReason

        item = DeadLetterItem(
            id="dlq_test_1",
            source_file="folder/test.pdf",
            blob_url="https://storage.blob/test.pdf",
            model_id="custom-model",
            reason=DeadLetterReason.TIMEOUT,
            error_message="Request timed out",
            retry_count=3,
            tenant_id="tenant-123",
        )

        doc = item.to_cosmos_document()

        assert doc["id"] == "dlq_test_1"
        assert doc["sourceFile"] == "folder/test.pdf"
        assert doc["documentType"] == "dead_letter"
        assert doc["reason"] == "timeout"
        assert doc["status"] == "pending"
        assert doc["errorMessage"] == "Request timed out"
        assert doc["retryCount"] == 3
        assert doc["tenantId"] == "tenant-123"

    def test_from_cosmos_document(self):
        """Test creation from Cosmos DB document."""
        from services.dead_letter_queue import (
            DeadLetterItem,
            DeadLetterReason,
            DeadLetterStatus,
        )

        doc = {
            "id": "dlq_test_1",
            "sourceFile": "folder/test.pdf",
            "blobUrl": "https://storage.blob/test.pdf",
            "modelId": "custom-model",
            "reason": "unrecoverable_error",
            "status": "investigating",
            "errorMessage": "Model not found",
            "errorDetails": {"modelId": "invalid"},
            "retryCount": 2,
            "maxRetries": 5,
            "deadLetteredAt": "2024-01-15T10:30:00+00:00",
            "notes": ["First note"],
        }

        item = DeadLetterItem.from_cosmos_document(doc)

        assert item.id == "dlq_test_1"
        assert item.reason == DeadLetterReason.UNRECOVERABLE_ERROR
        assert item.status == DeadLetterStatus.INVESTIGATING
        assert item.retry_count == 2
        assert item.max_retries == 5
        assert len(item.notes) == 1


class TestDeadLetterQueueService:
    """Tests for DeadLetterQueueService."""

    @pytest.fixture
    def mock_cosmos(self):
        """Create mock Cosmos service."""
        cosmos = AsyncMock()
        cosmos.save_document_result = AsyncMock()
        cosmos.get_document = AsyncMock()
        cosmos.query_documents = AsyncMock(return_value=[])
        cosmos.delete_document = AsyncMock(return_value=True)
        return cosmos

    @pytest.fixture
    def dlq_service(self, mock_cosmos):
        """Create DLQ service with mock Cosmos."""
        from services.dead_letter_queue import DeadLetterQueueService

        return DeadLetterQueueService(mock_cosmos)

    @pytest.mark.asyncio
    async def test_add_item(self, dlq_service, mock_cosmos):
        """Test adding item to DLQ."""
        from services.dead_letter_queue import DeadLetterReason

        item = await dlq_service.add_item(
            source_file="folder/test.pdf",
            blob_url="https://storage.blob/test.pdf",
            model_id="custom-model",
            reason=DeadLetterReason.MAX_RETRIES_EXCEEDED,
            error_message="Max retries exceeded",
            retry_count=5,
        )

        assert item.source_file == "folder/test.pdf"
        assert item.reason == DeadLetterReason.MAX_RETRIES_EXCEEDED
        assert item.retry_count == 5
        mock_cosmos.save_document_result.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_item_with_details(self, dlq_service, mock_cosmos):
        """Test adding item with error details."""
        from services.dead_letter_queue import DeadLetterReason

        item = await dlq_service.add_item(
            source_file="folder/test.pdf",
            blob_url="https://storage.blob/test.pdf",
            model_id="custom-model",
            reason=DeadLetterReason.UNRECOVERABLE_ERROR,
            error_message="Model not found",
            error_details={"modelId": "invalid-model", "errorCode": "MODEL_NOT_FOUND"},
            tenant_id="tenant-123",
            original_timestamp=datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc),
        )

        assert item.error_details["modelId"] == "invalid-model"
        assert item.tenant_id == "tenant-123"
        assert item.original_timestamp is not None

    @pytest.mark.asyncio
    async def test_get_item_found(self, dlq_service, mock_cosmos):
        """Test getting existing DLQ item."""
        mock_cosmos.get_document.return_value = {
            "id": "dlq_test_1",
            "sourceFile": "folder/test.pdf",
            "documentType": "dead_letter",
            "blobUrl": "https://storage.blob/test.pdf",
            "modelId": "custom-model",
            "reason": "max_retries_exceeded",
            "status": "pending",
            "deadLetteredAt": "2024-01-15T10:30:00+00:00",
        }

        item = await dlq_service.get_item("dlq_test_1", "folder/test.pdf")

        assert item is not None
        assert item.id == "dlq_test_1"
        mock_cosmos.get_document.assert_called_once_with("dlq_test_1", "folder/test.pdf")

    @pytest.mark.asyncio
    async def test_get_item_not_found(self, dlq_service, mock_cosmos):
        """Test getting non-existent DLQ item."""
        mock_cosmos.get_document.return_value = None

        item = await dlq_service.get_item("nonexistent", "folder/test.pdf")

        assert item is None

    @pytest.mark.asyncio
    async def test_get_item_wrong_type(self, dlq_service, mock_cosmos):
        """Test getting item that's not a dead letter."""
        mock_cosmos.get_document.return_value = {
            "id": "doc_1",
            "sourceFile": "folder/test.pdf",
            "documentType": "processing_result",  # Not a dead letter
        }

        item = await dlq_service.get_item("doc_1", "folder/test.pdf")

        assert item is None

    @pytest.mark.asyncio
    async def test_update_status(self, dlq_service, mock_cosmos):
        """Test updating DLQ item status."""
        from services.dead_letter_queue import DeadLetterStatus

        mock_cosmos.get_document.return_value = {
            "id": "dlq_test_1",
            "sourceFile": "folder/test.pdf",
            "documentType": "dead_letter",
            "blobUrl": "https://storage.blob/test.pdf",
            "modelId": "custom-model",
            "reason": "max_retries_exceeded",
            "status": "pending",
            "deadLetteredAt": "2024-01-15T10:30:00+00:00",
            "notes": [],
        }

        item = await dlq_service.update_status(
            "dlq_test_1",
            "folder/test.pdf",
            DeadLetterStatus.INVESTIGATING,
            note="Starting investigation",
        )

        assert item is not None
        assert item.status == DeadLetterStatus.INVESTIGATING
        assert len(item.notes) == 1
        assert "Starting investigation" in item.notes[0]

    @pytest.mark.asyncio
    async def test_update_status_resolved(self, dlq_service, mock_cosmos):
        """Test updating status to resolved sets timestamp."""
        from services.dead_letter_queue import DeadLetterStatus

        mock_cosmos.get_document.return_value = {
            "id": "dlq_test_1",
            "sourceFile": "folder/test.pdf",
            "documentType": "dead_letter",
            "blobUrl": "https://storage.blob/test.pdf",
            "modelId": "custom-model",
            "reason": "max_retries_exceeded",
            "status": "investigating",
            "deadLetteredAt": "2024-01-15T10:30:00+00:00",
            "notes": [],
        }

        item = await dlq_service.update_status(
            "dlq_test_1",
            "folder/test.pdf",
            DeadLetterStatus.RESOLVED,
        )

        assert item.resolved_at is not None

    @pytest.mark.asyncio
    async def test_schedule_retry(self, dlq_service, mock_cosmos):
        """Test scheduling retry for DLQ item."""
        mock_cosmos.get_document.return_value = {
            "id": "dlq_test_1",
            "sourceFile": "folder/test.pdf",
            "documentType": "dead_letter",
            "blobUrl": "https://storage.blob/test.pdf",
            "modelId": "custom-model",
            "reason": "timeout",
            "status": "pending",
            "retryCount": 0,
            "maxRetries": 3,
            "deadLetteredAt": "2024-01-15T10:30:00+00:00",
            "notes": [],
        }

        item = await dlq_service.schedule_retry(
            "dlq_test_1",
            "folder/test.pdf",
            note="Manual retry requested",
        )

        assert item is not None
        assert item.retry_count == 1
        assert item.last_retry_at is not None
        assert "retry" in item.notes[-1].lower()

    @pytest.mark.asyncio
    async def test_schedule_retry_max_exceeded(self, dlq_service, mock_cosmos):
        """Test scheduling retry when max retries exceeded."""
        mock_cosmos.get_document.return_value = {
            "id": "dlq_test_1",
            "sourceFile": "folder/test.pdf",
            "documentType": "dead_letter",
            "blobUrl": "https://storage.blob/test.pdf",
            "modelId": "custom-model",
            "reason": "timeout",
            "status": "pending",
            "retryCount": 3,
            "maxRetries": 3,
            "deadLetteredAt": "2024-01-15T10:30:00+00:00",
            "notes": [],
        }

        item = await dlq_service.schedule_retry(
            "dlq_test_1",
            "folder/test.pdf",
        )

        assert item is None

    @pytest.mark.asyncio
    async def test_query_by_status(self, dlq_service, mock_cosmos):
        """Test querying DLQ items by status."""
        from services.dead_letter_queue import DeadLetterStatus

        mock_cosmos.query_documents.return_value = [
            {
                "id": "dlq_1",
                "sourceFile": "a.pdf",
                "documentType": "dead_letter",
                "blobUrl": "https://test/a.pdf",
                "modelId": "model",
                "reason": "timeout",
                "status": "pending",
                "deadLetteredAt": "2024-01-15T10:30:00+00:00",
            },
            {
                "id": "dlq_2",
                "sourceFile": "b.pdf",
                "documentType": "dead_letter",
                "blobUrl": "https://test/b.pdf",
                "modelId": "model",
                "reason": "timeout",
                "status": "pending",
                "deadLetteredAt": "2024-01-15T11:30:00+00:00",
            },
        ]

        items = await dlq_service.query_by_status(DeadLetterStatus.PENDING, limit=50)

        assert len(items) == 2
        mock_cosmos.query_documents.assert_called_once()

    @pytest.mark.asyncio
    async def test_query_by_reason(self, dlq_service, mock_cosmos):
        """Test querying DLQ items by reason."""
        from services.dead_letter_queue import DeadLetterReason

        mock_cosmos.query_documents.return_value = []

        items = await dlq_service.query_by_reason(DeadLetterReason.TIMEOUT)

        assert len(items) == 0
        mock_cosmos.query_documents.assert_called_once()

    @pytest.mark.asyncio
    async def test_query_by_source_file(self, dlq_service, mock_cosmos):
        """Test querying DLQ items by source file."""
        mock_cosmos.query_documents.return_value = [
            {
                "id": "dlq_1",
                "sourceFile": "folder/test.pdf",
                "documentType": "dead_letter",
                "blobUrl": "https://test/test.pdf",
                "modelId": "model",
                "reason": "timeout",
                "status": "pending",
                "deadLetteredAt": "2024-01-15T10:30:00+00:00",
            },
        ]

        items = await dlq_service.query_by_source_file("folder/test.pdf")

        assert len(items) == 1
        # Should use partition key
        mock_cosmos.query_documents.assert_called_once()
        call_args = mock_cosmos.query_documents.call_args
        assert call_args.kwargs.get("partition_key") == "folder/test.pdf"

    @pytest.mark.asyncio
    async def test_get_statistics(self, dlq_service, mock_cosmos):
        """Test getting DLQ statistics."""
        mock_cosmos.query_documents.return_value = [
            {"status": "pending", "reason": "timeout", "count": 5},
            {"status": "pending", "reason": "max_retries_exceeded", "count": 3},
            {"status": "resolved", "reason": "timeout", "count": 10},
        ]

        stats = await dlq_service.get_statistics()

        assert stats["total"] == 18
        assert stats["byStatus"]["pending"] == 8
        assert stats["byStatus"]["resolved"] == 10
        assert stats["byReason"]["timeout"] == 15
        assert "timestamp" in stats


class TestDeadLetterQueueRetryMethods:
    """Tests for DLQ retry-related methods."""

    @pytest.fixture
    def mock_cosmos(self):
        """Create mock Cosmos service."""
        cosmos = AsyncMock()
        cosmos.save_document_result = AsyncMock()
        cosmos.get_document = AsyncMock()
        cosmos.query_documents = AsyncMock(return_value=[])
        cosmos.delete_document = AsyncMock(return_value=True)
        return cosmos

    @pytest.fixture
    def dlq_service(self, mock_cosmos):
        """Create DLQ service with mock Cosmos."""
        from services.dead_letter_queue import DeadLetterQueueService

        return DeadLetterQueueService(mock_cosmos)

    @pytest.mark.asyncio
    async def test_query_ready_for_retry(self, dlq_service, mock_cosmos):
        """Test querying items ready for automatic retry."""
        mock_cosmos.query_documents.return_value = [
            {
                "id": "dlq_1",
                "sourceFile": "a.pdf",
                "documentType": "dead_letter",
                "blobUrl": "https://test/a.pdf",
                "modelId": "model",
                "reason": "timeout",
                "status": "pending",
                "retryCount": 1,
                "maxRetries": 3,
                "deadLetteredAt": "2024-01-15T10:30:00+00:00",
            },
            {
                "id": "dlq_2",
                "sourceFile": "b.pdf",
                "documentType": "dead_letter",
                "blobUrl": "https://test/b.pdf",
                "modelId": "model",
                "reason": "dependency_failure",
                "status": "retry_scheduled",
                "retryCount": 0,
                "maxRetries": 3,
                "deadLetteredAt": "2024-01-15T11:30:00+00:00",
            },
        ]

        items = await dlq_service.query_ready_for_retry(limit=10)

        assert len(items) == 2
        assert items[0].id == "dlq_1"
        assert items[1].id == "dlq_2"
        mock_cosmos.query_documents.assert_called_once()

    @pytest.mark.asyncio
    async def test_query_ready_for_retry_empty(self, dlq_service, mock_cosmos):
        """Test querying when no items ready for retry."""
        mock_cosmos.query_documents.return_value = []

        items = await dlq_service.query_ready_for_retry()

        assert len(items) == 0

    @pytest.mark.asyncio
    async def test_mark_retry_in_progress(self, dlq_service, mock_cosmos):
        """Test marking item as retry in progress."""
        from services.dead_letter_queue import DeadLetterStatus

        mock_cosmos.get_document.return_value = {
            "id": "dlq_test_1",
            "sourceFile": "folder/test.pdf",
            "documentType": "dead_letter",
            "blobUrl": "https://storage.blob/test.pdf",
            "modelId": "custom-model",
            "reason": "timeout",
            "status": "pending",
            "retryCount": 1,
            "maxRetries": 3,
            "deadLetteredAt": "2024-01-15T10:30:00+00:00",
            "notes": [],
        }

        item = await dlq_service.mark_retry_in_progress("dlq_test_1", "folder/test.pdf")

        assert item is not None
        assert item.status == DeadLetterStatus.INVESTIGATING
        assert item.last_retry_at is not None
        assert "Auto-retry started" in item.notes[-1]

    @pytest.mark.asyncio
    async def test_mark_retry_success(self, dlq_service, mock_cosmos):
        """Test marking retry as successful."""
        from services.dead_letter_queue import DeadLetterStatus

        mock_cosmos.get_document.return_value = {
            "id": "dlq_test_1",
            "sourceFile": "folder/test.pdf",
            "documentType": "dead_letter",
            "blobUrl": "https://storage.blob/test.pdf",
            "modelId": "custom-model",
            "reason": "timeout",
            "status": "investigating",
            "retryCount": 1,
            "maxRetries": 3,
            "deadLetteredAt": "2024-01-15T10:30:00+00:00",
            "notes": [],
        }

        item = await dlq_service.mark_retry_success(
            "dlq_test_1",
            "folder/test.pdf",
            note="Successfully reprocessed",
        )

        assert item is not None
        assert item.status == DeadLetterStatus.RESOLVED
        assert item.resolved_at is not None
        assert item.retry_count == 2  # Incremented
        assert "Resolved: Successfully reprocessed" in item.notes[-1]

    @pytest.mark.asyncio
    async def test_mark_retry_success_default_note(self, dlq_service, mock_cosmos):
        """Test marking retry as successful with default note."""
        mock_cosmos.get_document.return_value = {
            "id": "dlq_test_1",
            "sourceFile": "folder/test.pdf",
            "documentType": "dead_letter",
            "blobUrl": "https://storage.blob/test.pdf",
            "modelId": "custom-model",
            "reason": "timeout",
            "status": "investigating",
            "retryCount": 0,
            "maxRetries": 3,
            "deadLetteredAt": "2024-01-15T10:30:00+00:00",
            "notes": [],
        }

        item = await dlq_service.mark_retry_success("dlq_test_1", "folder/test.pdf")

        assert item is not None
        assert "Successfully processed on auto-retry" in item.notes[-1]

    @pytest.mark.asyncio
    async def test_mark_retry_failed_transient(self, dlq_service, mock_cosmos):
        """Test marking retry as failed (transient, will retry again)."""
        from services.dead_letter_queue import DeadLetterStatus

        mock_cosmos.get_document.return_value = {
            "id": "dlq_test_1",
            "sourceFile": "folder/test.pdf",
            "documentType": "dead_letter",
            "blobUrl": "https://storage.blob/test.pdf",
            "modelId": "custom-model",
            "reason": "timeout",
            "status": "investigating",
            "retryCount": 1,
            "maxRetries": 3,
            "deadLetteredAt": "2024-01-15T10:30:00+00:00",
            "notes": [],
        }

        item = await dlq_service.mark_retry_failed(
            "dlq_test_1",
            "folder/test.pdf",
            error_message="Service temporarily unavailable",
        )

        assert item is not None
        assert item.status == DeadLetterStatus.PENDING  # Will retry again
        assert item.retry_count == 2
        assert item.error_message == "Service temporarily unavailable"
        assert "Retry failed" in item.notes[-1]

    @pytest.mark.asyncio
    async def test_mark_retry_failed_max_retries_reached(self, dlq_service, mock_cosmos):
        """Test marking retry as failed when max retries reached."""
        from services.dead_letter_queue import DeadLetterStatus

        mock_cosmos.get_document.return_value = {
            "id": "dlq_test_1",
            "sourceFile": "folder/test.pdf",
            "documentType": "dead_letter",
            "blobUrl": "https://storage.blob/test.pdf",
            "modelId": "custom-model",
            "reason": "timeout",
            "status": "investigating",
            "retryCount": 2,  # Will become 3 after this
            "maxRetries": 3,
            "deadLetteredAt": "2024-01-15T10:30:00+00:00",
            "notes": [],
        }

        item = await dlq_service.mark_retry_failed(
            "dlq_test_1",
            "folder/test.pdf",
            error_message="Still failing",
        )

        assert item is not None
        assert item.status == DeadLetterStatus.ABANDONED
        assert item.retry_count == 3
        assert "Permanently failed" in item.notes[-1]

    @pytest.mark.asyncio
    async def test_mark_retry_failed_permanent(self, dlq_service, mock_cosmos):
        """Test marking retry as permanently failed."""
        from services.dead_letter_queue import DeadLetterStatus

        mock_cosmos.get_document.return_value = {
            "id": "dlq_test_1",
            "sourceFile": "folder/test.pdf",
            "documentType": "dead_letter",
            "blobUrl": "https://storage.blob/test.pdf",
            "modelId": "custom-model",
            "reason": "timeout",
            "status": "investigating",
            "retryCount": 0,
            "maxRetries": 3,
            "deadLetteredAt": "2024-01-15T10:30:00+00:00",
            "notes": [],
        }

        item = await dlq_service.mark_retry_failed(
            "dlq_test_1",
            "folder/test.pdf",
            error_message="Blob deleted",
            permanent=True,
        )

        assert item is not None
        assert item.status == DeadLetterStatus.ABANDONED
        assert "Permanently failed" in item.notes[-1]

    @pytest.mark.asyncio
    async def test_mark_retry_in_progress_not_found(self, dlq_service, mock_cosmos):
        """Test marking non-existent item returns None."""
        mock_cosmos.get_document.return_value = None

        item = await dlq_service.mark_retry_in_progress("nonexistent", "test.pdf")

        assert item is None

    @pytest.mark.asyncio
    async def test_mark_retry_success_not_found(self, dlq_service, mock_cosmos):
        """Test marking non-existent item returns None."""
        mock_cosmos.get_document.return_value = None

        item = await dlq_service.mark_retry_success("nonexistent", "test.pdf")

        assert item is None

    @pytest.mark.asyncio
    async def test_mark_retry_failed_not_found(self, dlq_service, mock_cosmos):
        """Test marking non-existent item returns None."""
        mock_cosmos.get_document.return_value = None

        item = await dlq_service.mark_retry_failed("nonexistent", "test.pdf", "error")

        assert item is None


class TestDeadLetterQueueServiceSingleton:
    """Tests for DLQ service singleton."""

    @pytest.fixture(autouse=True)
    def reset_service(self):
        """Reset service before each test."""
        from services.dead_letter_queue import reset_dead_letter_queue_service

        reset_dead_letter_queue_service()
        yield
        reset_dead_letter_queue_service()

    def test_get_service_with_cosmos(self):
        """Test getting DLQ service when Cosmos is configured."""
        from services.dead_letter_queue import get_dead_letter_queue_service

        with patch("services.get_cosmos_service") as mock_get_cosmos:
            mock_cosmos = MagicMock()
            mock_get_cosmos.return_value = mock_cosmos

            service = get_dead_letter_queue_service()

            assert service is not None
            assert service.cosmos == mock_cosmos

    def test_get_service_returns_same_instance(self):
        """Test singleton returns same instance."""
        from services.dead_letter_queue import get_dead_letter_queue_service

        with patch("services.get_cosmos_service") as mock_get_cosmos:
            mock_cosmos = MagicMock()
            mock_get_cosmos.return_value = mock_cosmos

            service1 = get_dead_letter_queue_service()
            service2 = get_dead_letter_queue_service()

            assert service1 is service2
