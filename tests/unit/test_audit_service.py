"""Unit tests for audit logging service."""

import os
import sys
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add src/functions to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src/functions"))


class TestAuditAction:
    """Tests for AuditAction enum."""

    def test_document_action_values(self):
        """Test document action enum values."""
        from services.audit_service import AuditAction

        assert AuditAction.DOCUMENT_SUBMIT.value == "document.submit"
        assert AuditAction.DOCUMENT_PROCESS.value == "document.process"
        assert AuditAction.DOCUMENT_DELETE.value == "document.delete"
        assert AuditAction.DOCUMENT_QUERY.value == "document.query"
        assert AuditAction.DOCUMENT_EXPORT.value == "document.export"

    def test_job_action_values(self):
        """Test job action enum values."""
        from services.audit_service import AuditAction

        assert AuditAction.JOB_CREATE.value == "job.create"
        assert AuditAction.JOB_CANCEL.value == "job.cancel"
        assert AuditAction.JOB_QUERY.value == "job.query"

    def test_config_action_values(self):
        """Test configuration action enum values."""
        from services.audit_service import AuditAction

        assert AuditAction.CONFIG_UPDATE.value == "config.update"
        assert AuditAction.PROFILE_CREATE.value == "profile.create"
        assert AuditAction.PROFILE_UPDATE.value == "profile.update"
        assert AuditAction.PROFILE_DELETE.value == "profile.delete"

    def test_health_action_values(self):
        """Test health/admin action enum values."""
        from services.audit_service import AuditAction

        assert AuditAction.HEALTH_CHECK.value == "health.check"
        assert AuditAction.DLQ_RETRY.value == "dlq.retry"
        assert AuditAction.DLQ_ABANDON.value == "dlq.abandon"
        assert AuditAction.CIRCUIT_BREAKER_RESET.value == "circuit_breaker.reset"

    def test_auth_action_values(self):
        """Test authentication action enum values."""
        from services.audit_service import AuditAction

        assert AuditAction.AUTH_SUCCESS.value == "auth.success"
        assert AuditAction.AUTH_FAILURE.value == "auth.failure"
        assert AuditAction.ACCESS_DENIED.value == "access.denied"


class TestAuditStatus:
    """Tests for AuditStatus enum."""

    def test_status_values(self):
        """Test status enum values."""
        from services.audit_service import AuditStatus

        assert AuditStatus.SUCCESS.value == "success"
        assert AuditStatus.FAILURE.value == "failure"
        assert AuditStatus.PARTIAL.value == "partial"
        assert AuditStatus.DENIED.value == "denied"


class TestAuditEntry:
    """Tests for AuditEntry dataclass."""

    def test_create_entry(self):
        """Test creating an audit entry."""
        from services.audit_service import AuditAction, AuditEntry, AuditStatus

        entry = AuditEntry(
            id="audit_test_1",
            action=AuditAction.DOCUMENT_SUBMIT,
            status=AuditStatus.SUCCESS,
            user_id="user-123",
        )

        assert entry.id == "audit_test_1"
        assert entry.action == AuditAction.DOCUMENT_SUBMIT
        assert entry.status == AuditStatus.SUCCESS
        assert entry.user_id == "user-123"
        assert entry.timestamp is not None

    def test_create_entry_with_all_fields(self):
        """Test creating entry with all optional fields."""
        from services.audit_service import AuditAction, AuditEntry, AuditStatus

        timestamp = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)

        entry = AuditEntry(
            id="audit_test_1",
            action=AuditAction.DOCUMENT_PROCESS,
            status=AuditStatus.SUCCESS,
            user_id="user-123",
            tenant_id="tenant-456",
            resource_type="document",
            resource_id="doc-789",
            correlation_id="corr-abc",
            timestamp=timestamp,
            duration_ms=1500,
            ip_address="192.168.1.1",
            user_agent="TestClient/1.0",
            details={"pages": 5, "model": "custom-v1"},
            error_message=None,
        )

        assert entry.tenant_id == "tenant-456"
        assert entry.resource_type == "document"
        assert entry.resource_id == "doc-789"
        assert entry.correlation_id == "corr-abc"
        assert entry.duration_ms == 1500
        assert entry.ip_address == "192.168.1.1"
        assert entry.user_agent == "TestClient/1.0"
        assert entry.details["pages"] == 5

    def test_to_cosmos_document(self):
        """Test conversion to Cosmos DB document."""
        from services.audit_service import AuditAction, AuditEntry, AuditStatus

        entry = AuditEntry(
            id="audit_test_1",
            action=AuditAction.DOCUMENT_SUBMIT,
            status=AuditStatus.SUCCESS,
            user_id="user-123",
            tenant_id="tenant-456",
            resource_type="document",
            resource_id="doc-789",
        )

        doc = entry.to_cosmos_document()

        assert doc["id"] == "audit_test_1"
        assert doc["partitionKey"] == "document.submit"
        assert doc["documentType"] == "audit_log"
        assert doc["action"] == "document.submit"
        assert doc["status"] == "success"
        assert doc["userId"] == "user-123"
        assert doc["tenantId"] == "tenant-456"
        assert doc["resourceType"] == "document"
        assert doc["resourceId"] == "doc-789"

    def test_from_cosmos_document(self):
        """Test creation from Cosmos DB document."""
        from services.audit_service import AuditAction, AuditEntry, AuditStatus

        doc = {
            "id": "audit_test_1",
            "action": "document.process",
            "status": "failure",
            "userId": "user-123",
            "tenantId": "tenant-456",
            "resourceType": "document",
            "resourceId": "doc-789",
            "correlationId": "corr-abc",
            "timestamp": "2024-01-15T10:30:00+00:00",
            "durationMs": 2500,
            "ipAddress": "10.0.0.1",
            "userAgent": "Client/2.0",
            "details": {"error_code": "E001"},
            "errorMessage": "Processing failed",
        }

        entry = AuditEntry.from_cosmos_document(doc)

        assert entry.id == "audit_test_1"
        assert entry.action == AuditAction.DOCUMENT_PROCESS
        assert entry.status == AuditStatus.FAILURE
        assert entry.user_id == "user-123"
        assert entry.duration_ms == 2500
        assert entry.error_message == "Processing failed"
        assert entry.details["error_code"] == "E001"


class TestRedactSensitiveData:
    """Tests for sensitive data redaction."""

    def test_redact_password(self):
        """Test password field is redacted."""
        from services.audit_service import redact_sensitive_data

        data = {"username": "john", "password": "secret123"}
        result = redact_sensitive_data(data)

        assert result["username"] == "john"
        assert result["password"] == "[REDACTED]"

    def test_redact_api_key(self):
        """Test API key fields are redacted."""
        from services.audit_service import redact_sensitive_data

        data = {"service": "test", "api_key": "abc123", "apiKey": "xyz789"}
        result = redact_sensitive_data(data)

        assert result["service"] == "test"
        assert result["api_key"] == "[REDACTED]"
        assert result["apiKey"] == "[REDACTED]"

    def test_redact_connection_string(self):
        """Test connection string is redacted."""
        from services.audit_service import redact_sensitive_data

        data = {"connection_string": "Server=...", "connectionString": "Data Source=..."}
        result = redact_sensitive_data(data)

        assert result["connection_string"] == "[REDACTED]"
        assert result["connectionString"] == "[REDACTED]"

    def test_redact_nested_data(self):
        """Test nested sensitive data is redacted."""
        from services.audit_service import redact_sensitive_data

        data = {
            "config": {
                "endpoint": "https://api.test.com",
                "auth": {
                    "token": "secret-token",
                    "username": "admin",
                },
            }
        }
        result = redact_sensitive_data(data)

        assert result["config"]["endpoint"] == "https://api.test.com"
        assert result["config"]["auth"]["token"] == "[REDACTED]"
        assert result["config"]["auth"]["username"] == "admin"

    def test_redact_list_with_dicts(self):
        """Test lists containing dicts with sensitive data."""
        from services.audit_service import redact_sensitive_data

        data = {
            "services": [
                {"name": "svc1", "secret": "secret1"},
                {"name": "svc2", "secret": "secret2"},
            ]
        }
        result = redact_sensitive_data(data)

        assert result["services"][0]["name"] == "svc1"
        assert result["services"][0]["secret"] == "[REDACTED]"
        assert result["services"][1]["name"] == "svc2"
        assert result["services"][1]["secret"] == "[REDACTED]"

    def test_non_dict_passthrough(self):
        """Test non-dict values pass through unchanged."""
        from services.audit_service import redact_sensitive_data

        assert redact_sensitive_data("string") == "string"
        assert redact_sensitive_data(123) == 123
        assert redact_sensitive_data(None) is None


class TestAuditService:
    """Tests for AuditService."""

    @pytest.fixture
    def mock_cosmos(self):
        """Create mock Cosmos service."""
        cosmos = AsyncMock()
        cosmos.save_document_result = AsyncMock()
        cosmos.query_documents = AsyncMock(return_value=[])
        cosmos.delete_document = AsyncMock(return_value=True)
        return cosmos

    @pytest.fixture
    def audit_service(self, mock_cosmos):
        """Create audit service with mock Cosmos."""
        from services.audit_service import AuditService

        return AuditService(mock_cosmos)

    @pytest.mark.asyncio
    async def test_log_entry(self, audit_service, mock_cosmos):
        """Test logging an audit entry."""
        from services.audit_service import AuditAction, AuditStatus

        entry = await audit_service.log(
            action=AuditAction.DOCUMENT_SUBMIT,
            status=AuditStatus.SUCCESS,
            user_id="user-123",
            resource_type="document",
            resource_id="doc-456",
        )

        assert entry.action == AuditAction.DOCUMENT_SUBMIT
        assert entry.status == AuditStatus.SUCCESS
        assert entry.user_id == "user-123"
        mock_cosmos.save_document_result.assert_called_once()

    @pytest.mark.asyncio
    async def test_log_entry_with_details(self, audit_service, mock_cosmos):
        """Test logging entry with details."""
        from services.audit_service import AuditAction, AuditStatus

        entry = await audit_service.log(
            action=AuditAction.DOCUMENT_PROCESS,
            status=AuditStatus.SUCCESS,
            user_id="user-123",
            details={"pages": 10, "model": "custom-v1", "apiKey": "secret"},
        )

        # Verify sensitive data was redacted
        assert entry.details["pages"] == 10
        assert entry.details["model"] == "custom-v1"
        assert entry.details["apiKey"] == "[REDACTED]"

    @pytest.mark.asyncio
    async def test_log_success(self, audit_service, mock_cosmos):
        """Test log_success convenience method."""
        from services.audit_service import AuditAction, AuditStatus

        entry = await audit_service.log_success(
            AuditAction.DOCUMENT_QUERY,
            user_id="user-123",
        )

        assert entry.status == AuditStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_log_failure(self, audit_service, mock_cosmos):
        """Test log_failure convenience method."""
        from services.audit_service import AuditAction, AuditStatus

        entry = await audit_service.log_failure(
            AuditAction.DOCUMENT_PROCESS,
            error_message="Processing timeout",
            user_id="user-123",
        )

        assert entry.status == AuditStatus.FAILURE
        assert entry.error_message == "Processing timeout"

    @pytest.mark.asyncio
    async def test_log_handles_cosmos_error(self, audit_service, mock_cosmos):
        """Test logging handles Cosmos errors gracefully."""
        from services.audit_service import AuditAction, AuditStatus

        mock_cosmos.save_document_result.side_effect = Exception("Connection failed")

        # Should not raise, just log the error
        entry = await audit_service.log(
            action=AuditAction.DOCUMENT_SUBMIT,
            status=AuditStatus.SUCCESS,
        )

        assert entry is not None  # Entry still returned

    @pytest.mark.asyncio
    async def test_query_by_user(self, audit_service, mock_cosmos):
        """Test querying entries by user."""
        from services.audit_service import AuditAction, AuditStatus

        mock_cosmos.query_documents.return_value = [
            {
                "id": "audit_1",
                "action": "document.submit",
                "status": "success",
                "userId": "user-123",
                "timestamp": "2024-01-15T10:30:00+00:00",
            },
        ]

        entries = await audit_service.query_by_user("user-123", limit=50)

        assert len(entries) == 1
        assert entries[0].user_id == "user-123"
        mock_cosmos.query_documents.assert_called_once()

    @pytest.mark.asyncio
    async def test_query_by_user_with_time_range(self, audit_service, mock_cosmos):
        """Test querying by user with time range."""
        from services.audit_service import AuditAction

        start_time = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end_time = datetime(2024, 1, 31, tzinfo=timezone.utc)

        mock_cosmos.query_documents.return_value = []

        await audit_service.query_by_user(
            "user-123",
            start_time=start_time,
            end_time=end_time,
        )

        call_args = mock_cosmos.query_documents.call_args
        query = call_args.kwargs.get("query", "")
        assert "@startTime" in query
        assert "@endTime" in query

    @pytest.mark.asyncio
    async def test_query_by_action(self, audit_service, mock_cosmos):
        """Test querying entries by action."""
        from services.audit_service import AuditAction

        mock_cosmos.query_documents.return_value = []

        await audit_service.query_by_action(AuditAction.DOCUMENT_PROCESS)

        call_args = mock_cosmos.query_documents.call_args
        assert call_args.kwargs.get("partition_key") == "document.process"

    @pytest.mark.asyncio
    async def test_query_by_resource(self, audit_service, mock_cosmos):
        """Test querying entries by resource."""
        mock_cosmos.query_documents.return_value = []

        await audit_service.query_by_resource("document", resource_id="doc-123")

        call_args = mock_cosmos.query_documents.call_args
        parameters = call_args.kwargs.get("parameters", [])
        param_names = {p["name"] for p in parameters}
        assert "@resourceType" in param_names
        assert "@resourceId" in param_names

    @pytest.mark.asyncio
    async def test_query_by_correlation_id(self, audit_service, mock_cosmos):
        """Test querying entries by correlation ID."""
        mock_cosmos.query_documents.return_value = [
            {
                "id": "audit_1",
                "action": "document.submit",
                "status": "success",
                "correlationId": "corr-123",
                "timestamp": "2024-01-15T10:30:00+00:00",
            },
            {
                "id": "audit_2",
                "action": "document.process",
                "status": "success",
                "correlationId": "corr-123",
                "timestamp": "2024-01-15T10:30:05+00:00",
            },
        ]

        entries = await audit_service.query_by_correlation_id("corr-123")

        assert len(entries) == 2
        assert all(e.correlation_id == "corr-123" for e in entries)

    @pytest.mark.asyncio
    async def test_query_by_tenant(self, audit_service, mock_cosmos):
        """Test querying entries by tenant."""
        mock_cosmos.query_documents.return_value = []

        await audit_service.query_by_tenant("tenant-456")

        call_args = mock_cosmos.query_documents.call_args
        parameters = call_args.kwargs.get("parameters", [])
        tenant_param = next((p for p in parameters if p["name"] == "@tenantId"), None)
        assert tenant_param is not None
        assert tenant_param["value"] == "tenant-456"

    @pytest.mark.asyncio
    async def test_query_failures(self, audit_service, mock_cosmos):
        """Test querying failed entries."""
        mock_cosmos.query_documents.return_value = [
            {
                "id": "audit_1",
                "action": "document.process",
                "status": "failure",
                "errorMessage": "Timeout",
                "timestamp": "2024-01-15T10:30:00+00:00",
            },
        ]

        entries = await audit_service.query_failures()

        assert len(entries) == 1
        mock_cosmos.query_documents.assert_called_once()
        query = mock_cosmos.query_documents.call_args.kwargs.get("query", "")
        assert "failure" in query
        assert "denied" in query

    @pytest.mark.asyncio
    async def test_get_statistics(self, audit_service, mock_cosmos):
        """Test getting audit statistics."""
        mock_cosmos.query_documents.return_value = [
            {"action": "document.submit", "status": "success", "count": 100},
            {"action": "document.submit", "status": "failure", "count": 5},
            {"action": "document.process", "status": "success", "count": 95},
        ]

        stats = await audit_service.get_statistics()

        assert stats["total"] == 200
        assert stats["byAction"]["document.submit"] == 105
        assert stats["byAction"]["document.process"] == 95
        assert stats["byStatus"]["success"] == 195
        assert stats["byStatus"]["failure"] == 5
        assert "timestamp" in stats

    @pytest.mark.asyncio
    async def test_delete_old_entries(self, audit_service, mock_cosmos):
        """Test deleting old audit entries."""
        mock_cosmos.query_documents.return_value = [
            {"id": "audit_old_1", "partitionKey": "document.submit"},
            {"id": "audit_old_2", "partitionKey": "document.process"},
        ]

        deleted = await audit_service.delete_old_entries(older_than_days=90)

        assert deleted == 2
        assert mock_cosmos.delete_document.call_count == 2

    @pytest.mark.asyncio
    async def test_delete_old_entries_handles_errors(self, audit_service, mock_cosmos):
        """Test delete handles individual errors."""
        mock_cosmos.query_documents.return_value = [
            {"id": "audit_1", "partitionKey": "document.submit"},
            {"id": "audit_2", "partitionKey": "document.process"},
        ]
        # First delete succeeds, second fails
        mock_cosmos.delete_document.side_effect = [True, Exception("Delete failed")]

        deleted = await audit_service.delete_old_entries(older_than_days=90)

        assert deleted == 1  # Only first one counted


class TestAuditServiceSingleton:
    """Tests for audit service singleton."""

    @pytest.fixture(autouse=True)
    def reset_service(self):
        """Reset service before each test."""
        from services.audit_service import reset_audit_service

        reset_audit_service()
        yield
        reset_audit_service()

    def test_get_service_with_cosmos(self):
        """Test getting audit service when Cosmos is configured."""
        from services.audit_service import get_audit_service

        with patch("services.get_cosmos_service") as mock_get_cosmos:
            mock_cosmos = MagicMock()
            mock_get_cosmos.return_value = mock_cosmos

            service = get_audit_service()

            assert service is not None
            assert service.cosmos == mock_cosmos

    def test_get_service_returns_same_instance(self):
        """Test singleton returns same instance."""
        from services.audit_service import get_audit_service

        with patch("services.get_cosmos_service") as mock_get_cosmos:
            mock_cosmos = MagicMock()
            mock_get_cosmos.return_value = mock_cosmos

            service1 = get_audit_service()
            service2 = get_audit_service()

            assert service1 is service2

    def test_get_service_without_cosmos(self):
        """Test getting service when Cosmos not configured."""
        from services.audit_service import get_audit_service

        with patch("services.get_cosmos_service") as mock_get_cosmos:
            mock_get_cosmos.return_value = None

            service = get_audit_service()

            assert service is None
