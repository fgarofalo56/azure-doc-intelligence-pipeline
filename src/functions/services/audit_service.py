"""Audit logging service for tracking user actions.

Provides comprehensive audit logging for security and compliance:
- Document processing submissions
- Query operations
- Configuration changes
- Deletions and modifications

Features:
- Persistent storage to Cosmos DB
- Queryable by user, action, resource, time range
- Correlation ID support for request tracing
- Sensitive data redaction
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class AuditAction(Enum):
    """Types of auditable actions."""

    # Document operations
    DOCUMENT_SUBMIT = "document.submit"
    DOCUMENT_PROCESS = "document.process"
    DOCUMENT_DELETE = "document.delete"
    DOCUMENT_QUERY = "document.query"
    DOCUMENT_EXPORT = "document.export"

    # Job operations
    JOB_CREATE = "job.create"
    JOB_CANCEL = "job.cancel"
    JOB_QUERY = "job.query"

    # Configuration operations
    CONFIG_UPDATE = "config.update"
    PROFILE_CREATE = "profile.create"
    PROFILE_UPDATE = "profile.update"
    PROFILE_DELETE = "profile.delete"

    # Health/Admin operations
    HEALTH_CHECK = "health.check"
    DLQ_RETRY = "dlq.retry"
    DLQ_ABANDON = "dlq.abandon"
    CIRCUIT_BREAKER_RESET = "circuit_breaker.reset"

    # Authentication/Authorization
    AUTH_SUCCESS = "auth.success"
    AUTH_FAILURE = "auth.failure"
    ACCESS_DENIED = "access.denied"


class AuditStatus(Enum):
    """Status of the audited action."""

    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL = "partial"
    DENIED = "denied"


@dataclass
class AuditEntry:
    """Represents an audit log entry."""

    id: str
    action: AuditAction
    status: AuditStatus
    user_id: str | None = None
    tenant_id: str | None = None
    resource_type: str | None = None
    resource_id: str | None = None
    correlation_id: str | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    duration_ms: int | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    details: dict[str, Any] = field(default_factory=dict)
    error_message: str | None = None

    def to_cosmos_document(self) -> dict[str, Any]:
        """Convert to Cosmos DB document format."""
        # Use action as partition key for efficient querying by action type
        return {
            "id": self.id,
            "partitionKey": self.action.value,  # Partition by action type
            "documentType": "audit_log",
            "action": self.action.value,
            "status": self.status.value,
            "userId": self.user_id,
            "tenantId": self.tenant_id,
            "resourceType": self.resource_type,
            "resourceId": self.resource_id,
            "correlationId": self.correlation_id,
            "timestamp": self.timestamp.isoformat(),
            "durationMs": self.duration_ms,
            "ipAddress": self.ip_address,
            "userAgent": self.user_agent,
            "details": self.details,
            "errorMessage": self.error_message,
        }

    @classmethod
    def from_cosmos_document(cls, doc: dict[str, Any]) -> "AuditEntry":
        """Create from Cosmos DB document."""
        return cls(
            id=doc["id"],
            action=AuditAction(doc["action"]),
            status=AuditStatus(doc["status"]),
            user_id=doc.get("userId"),
            tenant_id=doc.get("tenantId"),
            resource_type=doc.get("resourceType"),
            resource_id=doc.get("resourceId"),
            correlation_id=doc.get("correlationId"),
            timestamp=datetime.fromisoformat(doc["timestamp"]),
            duration_ms=doc.get("durationMs"),
            ip_address=doc.get("ipAddress"),
            user_agent=doc.get("userAgent"),
            details=doc.get("details", {}),
            error_message=doc.get("errorMessage"),
        )


# Patterns that indicate sensitive fields (checked as substrings in lowercase keys)
SENSITIVE_PATTERNS = {
    "password",
    "secret",
    "token",
    "authorization",
    "credential",
    "apikey",        # Matches apiKey, api_key, etc.
    "api_key",
    "privatekey",    # Matches privateKey, private_key
    "private_key",
    "connectionstring",  # Matches connectionString, connection_string
    "connection_string",
}


def redact_sensitive_data(data: dict[str, Any]) -> dict[str, Any]:
    """Redact sensitive fields from audit data.

    Args:
        data: Dictionary potentially containing sensitive data

    Returns:
        Dictionary with sensitive fields redacted
    """
    if not isinstance(data, dict):
        return data

    redacted = {}
    for key, value in data.items():
        key_lower = key.lower().replace("_", "")  # Normalize: "api_key" -> "apikey"
        if any(pattern in key_lower or pattern.replace("_", "") in key_lower for pattern in SENSITIVE_PATTERNS):
            redacted[key] = "[REDACTED]"
        elif isinstance(value, dict):
            redacted[key] = redact_sensitive_data(value)
        elif isinstance(value, list):
            redacted[key] = [
                redact_sensitive_data(item) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            redacted[key] = value
    return redacted


class AuditServiceError(Exception):
    """Base exception for audit service errors."""

    pass


class AuditService:
    """Service for audit logging.

    Uses Cosmos DB for persistent storage of audit entries.
    Supports querying by various criteria and automatic sensitive data redaction.
    """

    def __init__(self, cosmos_service: Any) -> None:
        """Initialize audit service.

        Args:
            cosmos_service: CosmosService instance for persistence
        """
        self.cosmos = cosmos_service

    async def log(
        self,
        action: AuditAction,
        status: AuditStatus,
        *,
        user_id: str | None = None,
        tenant_id: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        correlation_id: str | None = None,
        duration_ms: int | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        details: dict[str, Any] | None = None,
        error_message: str | None = None,
    ) -> AuditEntry:
        """Log an audit entry.

        Args:
            action: The action being audited
            status: Result status of the action
            user_id: User performing the action
            tenant_id: Tenant context
            resource_type: Type of resource affected
            resource_id: ID of resource affected
            correlation_id: Request correlation ID
            duration_ms: Duration of operation in milliseconds
            ip_address: Client IP address
            user_agent: Client user agent
            details: Additional details (sensitive data will be redacted)
            error_message: Error message if status is failure

        Returns:
            AuditEntry: The created audit entry
        """
        # Generate unique ID
        timestamp = datetime.now(timezone.utc)
        entry_id = f"audit_{action.value.replace('.', '_')}_{int(timestamp.timestamp() * 1000)}"

        # Redact sensitive data from details
        safe_details = redact_sensitive_data(details or {})

        entry = AuditEntry(
            id=entry_id,
            action=action,
            status=status,
            user_id=user_id,
            tenant_id=tenant_id,
            resource_type=resource_type,
            resource_id=resource_id,
            correlation_id=correlation_id,
            timestamp=timestamp,
            duration_ms=duration_ms,
            ip_address=ip_address,
            user_agent=user_agent,
            details=safe_details,
            error_message=error_message,
        )

        try:
            await self.cosmos.save_document_result(entry.to_cosmos_document())
            logger.debug(
                f"Audit logged: {action.value} by {user_id or 'anonymous'} - {status.value}"
            )
        except Exception as e:
            # Log but don't fail the main operation
            logger.error(f"Failed to persist audit entry: {e}")

        return entry

    async def log_success(
        self,
        action: AuditAction,
        **kwargs: Any,
    ) -> AuditEntry:
        """Convenience method to log a successful action.

        Args:
            action: The action being audited
            **kwargs: Additional audit entry fields

        Returns:
            AuditEntry: The created audit entry
        """
        return await self.log(action, AuditStatus.SUCCESS, **kwargs)

    async def log_failure(
        self,
        action: AuditAction,
        error_message: str,
        **kwargs: Any,
    ) -> AuditEntry:
        """Convenience method to log a failed action.

        Args:
            action: The action being audited
            error_message: Description of the failure
            **kwargs: Additional audit entry fields

        Returns:
            AuditEntry: The created audit entry
        """
        return await self.log(
            action, AuditStatus.FAILURE, error_message=error_message, **kwargs
        )

    async def query_by_user(
        self,
        user_id: str,
        limit: int = 100,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> list[AuditEntry]:
        """Query audit entries by user.

        Args:
            user_id: User ID to filter by
            limit: Maximum entries to return
            start_time: Optional start time filter
            end_time: Optional end time filter

        Returns:
            List of matching AuditEntries
        """
        query = """
            SELECT TOP @limit * FROM c
            WHERE c.documentType = 'audit_log' AND c.userId = @userId
        """
        parameters = [
            {"name": "@limit", "value": limit},
            {"name": "@userId", "value": user_id},
        ]

        if start_time:
            query += " AND c.timestamp >= @startTime"
            parameters.append({"name": "@startTime", "value": start_time.isoformat()})

        if end_time:
            query += " AND c.timestamp <= @endTime"
            parameters.append({"name": "@endTime", "value": end_time.isoformat()})

        query += " ORDER BY c.timestamp DESC"

        docs = await self.cosmos.query_documents(query=query, parameters=parameters)
        return [AuditEntry.from_cosmos_document(doc) for doc in docs]

    async def query_by_action(
        self,
        action: AuditAction,
        limit: int = 100,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> list[AuditEntry]:
        """Query audit entries by action type.

        Args:
            action: Action type to filter by
            limit: Maximum entries to return
            start_time: Optional start time filter
            end_time: Optional end time filter

        Returns:
            List of matching AuditEntries
        """
        query = """
            SELECT TOP @limit * FROM c
            WHERE c.documentType = 'audit_log' AND c.action = @action
        """
        parameters = [
            {"name": "@limit", "value": limit},
            {"name": "@action", "value": action.value},
        ]

        if start_time:
            query += " AND c.timestamp >= @startTime"
            parameters.append({"name": "@startTime", "value": start_time.isoformat()})

        if end_time:
            query += " AND c.timestamp <= @endTime"
            parameters.append({"name": "@endTime", "value": end_time.isoformat()})

        query += " ORDER BY c.timestamp DESC"

        docs = await self.cosmos.query_documents(
            query=query,
            parameters=parameters,
            partition_key=action.value,
        )
        return [AuditEntry.from_cosmos_document(doc) for doc in docs]

    async def query_by_resource(
        self,
        resource_type: str,
        resource_id: str | None = None,
        limit: int = 100,
    ) -> list[AuditEntry]:
        """Query audit entries by resource.

        Args:
            resource_type: Resource type to filter by
            resource_id: Optional specific resource ID
            limit: Maximum entries to return

        Returns:
            List of matching AuditEntries
        """
        query = """
            SELECT TOP @limit * FROM c
            WHERE c.documentType = 'audit_log' AND c.resourceType = @resourceType
        """
        parameters = [
            {"name": "@limit", "value": limit},
            {"name": "@resourceType", "value": resource_type},
        ]

        if resource_id:
            query += " AND c.resourceId = @resourceId"
            parameters.append({"name": "@resourceId", "value": resource_id})

        query += " ORDER BY c.timestamp DESC"

        docs = await self.cosmos.query_documents(query=query, parameters=parameters)
        return [AuditEntry.from_cosmos_document(doc) for doc in docs]

    async def query_by_correlation_id(
        self,
        correlation_id: str,
    ) -> list[AuditEntry]:
        """Query all audit entries for a request correlation ID.

        Args:
            correlation_id: Correlation ID to search for

        Returns:
            List of matching AuditEntries (ordered by timestamp)
        """
        query = """
            SELECT * FROM c
            WHERE c.documentType = 'audit_log' AND c.correlationId = @correlationId
            ORDER BY c.timestamp ASC
        """
        parameters = [{"name": "@correlationId", "value": correlation_id}]

        docs = await self.cosmos.query_documents(query=query, parameters=parameters)
        return [AuditEntry.from_cosmos_document(doc) for doc in docs]

    async def query_by_tenant(
        self,
        tenant_id: str,
        limit: int = 100,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> list[AuditEntry]:
        """Query audit entries by tenant.

        Args:
            tenant_id: Tenant ID to filter by
            limit: Maximum entries to return
            start_time: Optional start time filter
            end_time: Optional end time filter

        Returns:
            List of matching AuditEntries
        """
        query = """
            SELECT TOP @limit * FROM c
            WHERE c.documentType = 'audit_log' AND c.tenantId = @tenantId
        """
        parameters = [
            {"name": "@limit", "value": limit},
            {"name": "@tenantId", "value": tenant_id},
        ]

        if start_time:
            query += " AND c.timestamp >= @startTime"
            parameters.append({"name": "@startTime", "value": start_time.isoformat()})

        if end_time:
            query += " AND c.timestamp <= @endTime"
            parameters.append({"name": "@endTime", "value": end_time.isoformat()})

        query += " ORDER BY c.timestamp DESC"

        docs = await self.cosmos.query_documents(query=query, parameters=parameters)
        return [AuditEntry.from_cosmos_document(doc) for doc in docs]

    async def query_failures(
        self,
        limit: int = 100,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> list[AuditEntry]:
        """Query failed actions for investigation.

        Args:
            limit: Maximum entries to return
            start_time: Optional start time filter
            end_time: Optional end time filter

        Returns:
            List of failed AuditEntries
        """
        query = """
            SELECT TOP @limit * FROM c
            WHERE c.documentType = 'audit_log'
            AND (c.status = 'failure' OR c.status = 'denied')
        """
        parameters = [{"name": "@limit", "value": limit}]

        if start_time:
            query += " AND c.timestamp >= @startTime"
            parameters.append({"name": "@startTime", "value": start_time.isoformat()})

        if end_time:
            query += " AND c.timestamp <= @endTime"
            parameters.append({"name": "@endTime", "value": end_time.isoformat()})

        query += " ORDER BY c.timestamp DESC"

        docs = await self.cosmos.query_documents(query=query, parameters=parameters)
        return [AuditEntry.from_cosmos_document(doc) for doc in docs]

    async def get_statistics(
        self,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> dict[str, Any]:
        """Get audit statistics.

        Args:
            start_time: Optional start time filter
            end_time: Optional end time filter

        Returns:
            Dictionary with audit statistics
        """
        query = """
            SELECT
                c.action,
                c.status,
                COUNT(1) as count
            FROM c
            WHERE c.documentType = 'audit_log'
        """
        parameters = []

        if start_time:
            query += " AND c.timestamp >= @startTime"
            parameters.append({"name": "@startTime", "value": start_time.isoformat()})

        if end_time:
            query += " AND c.timestamp <= @endTime"
            parameters.append({"name": "@endTime", "value": end_time.isoformat()})

        query += " GROUP BY c.action, c.status"

        docs = await self.cosmos.query_documents(query=query, parameters=parameters)

        # Aggregate results
        by_action: dict[str, int] = {}
        by_status: dict[str, int] = {}
        total = 0

        for doc in docs:
            action = doc.get("action", "unknown")
            status = doc.get("status", "unknown")
            count = doc.get("count", 0)

            by_action[action] = by_action.get(action, 0) + count
            by_status[status] = by_status.get(status, 0) + count
            total += count

        return {
            "total": total,
            "byAction": by_action,
            "byStatus": by_status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def delete_old_entries(self, older_than_days: int = 90) -> int:
        """Delete audit entries older than specified days.

        Args:
            older_than_days: Delete entries older than this many days

        Returns:
            Number of entries deleted
        """
        cutoff = datetime.now(timezone.utc)
        # Calculate cutoff date
        days_in_seconds = older_than_days * 24 * 60 * 60
        cutoff_timestamp = cutoff.timestamp() - days_in_seconds
        cutoff = datetime.fromtimestamp(cutoff_timestamp, tz=timezone.utc)

        query = """
            SELECT c.id, c.partitionKey FROM c
            WHERE c.documentType = 'audit_log'
            AND c.timestamp < @cutoff
        """
        parameters = [{"name": "@cutoff", "value": cutoff.isoformat()}]

        docs = await self.cosmos.query_documents(query=query, parameters=parameters)

        deleted = 0
        for doc in docs:
            try:
                if await self.cosmos.delete_document(doc["id"], doc["partitionKey"]):
                    deleted += 1
            except Exception as e:
                logger.warning(f"Failed to delete audit entry {doc['id']}: {e}")

        logger.info(f"Deleted {deleted} old audit entries")
        return deleted


# Global service instance
_audit_service: AuditService | None = None


def get_audit_service() -> AuditService | None:
    """Get or create AuditService singleton.

    Returns:
        AuditService instance or None if Cosmos not configured
    """
    global _audit_service
    if _audit_service is None:
        # Import here to avoid circular dependency
        from . import get_cosmos_service

        cosmos = get_cosmos_service()
        if cosmos:
            _audit_service = AuditService(cosmos)
            logger.info("Audit service initialized")
    return _audit_service


def reset_audit_service() -> None:
    """Reset service instance (for testing)."""
    global _audit_service
    _audit_service = None
