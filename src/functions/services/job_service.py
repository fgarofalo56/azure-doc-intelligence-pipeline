"""Job service for async document processing.

Manages processing jobs with queue-based execution and status tracking.
Jobs are stored in Cosmos DB for persistence and status polling.
"""

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from azure.storage.queue import QueueClient

logger = logging.getLogger(__name__)


class JobStatus(str, Enum):
    """Job processing status."""

    PENDING = "pending"
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"


@dataclass
class ProcessingJob:
    """Represents a document processing job."""

    job_id: str
    blob_url: str
    blob_name: str
    model_id: str
    status: JobStatus = JobStatus.PENDING
    profile_name: str | None = None
    pages_per_form: int | None = None
    webhook_url: str | None = None
    tenant_id: str | None = None  # Multi-tenant isolation
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    started_at: str | None = None
    completed_at: str | None = None
    progress: dict[str, Any] = field(default_factory=dict)
    result: dict[str, Any] | None = None
    error: str | None = None
    retry_count: int = 0
    max_retries: int = 3

    def to_dict(self) -> dict[str, Any]:
        """Convert job to dictionary for storage."""
        data = {
            "id": self.job_id,
            "jobId": self.job_id,
            "blobUrl": self.blob_url,
            "blobName": self.blob_name,
            "modelId": self.model_id,
            "status": self.status.value,
            "profileName": self.profile_name,
            "pagesPerForm": self.pages_per_form,
            "webhookUrl": self.webhook_url,
            "createdAt": self.created_at,
            "updatedAt": self.updated_at,
            "startedAt": self.started_at,
            "completedAt": self.completed_at,
            "progress": self.progress,
            "result": self.result,
            "error": self.error,
            "retryCount": self.retry_count,
            "maxRetries": self.max_retries,
            "documentType": "job",  # Distinguishes from extracted documents
        }
        # Add tenant ID if set
        if self.tenant_id:
            data["tenantId"] = self.tenant_id
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProcessingJob":
        """Create job from dictionary."""
        return cls(
            job_id=data.get("jobId") or data.get("id", ""),
            blob_url=data.get("blobUrl", ""),
            blob_name=data.get("blobName", ""),
            model_id=data.get("modelId", ""),
            status=JobStatus(data.get("status", "pending")),
            profile_name=data.get("profileName"),
            pages_per_form=data.get("pagesPerForm"),
            webhook_url=data.get("webhookUrl"),
            tenant_id=data.get("tenantId"),
            created_at=data.get("createdAt", ""),
            updated_at=data.get("updatedAt", ""),
            started_at=data.get("startedAt"),
            completed_at=data.get("completedAt"),
            progress=data.get("progress", {}),
            result=data.get("result"),
            error=data.get("error"),
            retry_count=data.get("retryCount", 0),
            max_retries=data.get("maxRetries", 3),
        )

    def to_queue_message(self) -> str:
        """Create queue message for job."""
        data = {
            "jobId": self.job_id,
            "blobUrl": self.blob_url,
            "blobName": self.blob_name,
            "modelId": self.model_id,
            "profileName": self.profile_name,
            "pagesPerForm": self.pages_per_form,
            "webhookUrl": self.webhook_url,
        }
        if self.tenant_id:
            data["tenantId"] = self.tenant_id
        return json.dumps(data)


class JobService:
    """Service for managing processing jobs."""

    def __init__(
        self,
        cosmos_service: Any,
        queue_connection_string: str | None = None,
        queue_name: str = "document-processing",
    ) -> None:
        """Initialize job service.

        Args:
            cosmos_service: CosmosService instance for job storage.
            queue_connection_string: Azure Storage connection string for queue.
            queue_name: Name of the processing queue.
        """
        self.cosmos = cosmos_service
        self.queue_name = queue_name
        self._queue_client: QueueClient | None = None

        if queue_connection_string:
            try:
                self._queue_client = QueueClient.from_connection_string(
                    queue_connection_string,
                    queue_name=queue_name,
                )
                # Ensure queue exists
                self._queue_client.create_queue()
            except Exception as e:
                logger.warning(f"Queue client initialization failed: {e}")
                # Queue might already exist
                try:
                    self._queue_client = QueueClient.from_connection_string(
                        queue_connection_string,
                        queue_name=queue_name,
                    )
                except Exception:
                    self._queue_client = None

    def generate_job_id(self) -> str:
        """Generate a unique job ID."""
        return f"job_{uuid.uuid4().hex[:12]}"

    async def create_job(
        self,
        blob_url: str,
        blob_name: str,
        model_id: str,
        profile_name: str | None = None,
        pages_per_form: int | None = None,
        webhook_url: str | None = None,
        tenant_id: str | None = None,
    ) -> ProcessingJob:
        """Create a new processing job.

        Args:
            blob_url: URL to the PDF blob.
            blob_name: Blob path within container.
            model_id: Document Intelligence model ID.
            profile_name: Optional processing profile name.
            pages_per_form: Optional pages per form override.
            webhook_url: Optional webhook URL for completion notification.
            tenant_id: Optional tenant ID for multi-tenant isolation.

        Returns:
            ProcessingJob: The created job.
        """
        job = ProcessingJob(
            job_id=self.generate_job_id(),
            blob_url=blob_url,
            blob_name=blob_name,
            model_id=model_id,
            profile_name=profile_name,
            pages_per_form=pages_per_form,
            webhook_url=webhook_url,
            tenant_id=tenant_id,
        )

        # Save to Cosmos DB
        await self.cosmos.save_document_result(job.to_dict())

        logger.info(f"Created job {job.job_id} for {blob_name}")
        return job

    async def queue_job(self, job: ProcessingJob) -> bool:
        """Add job to processing queue.

        Args:
            job: Job to queue.

        Returns:
            bool: True if queued successfully.
        """
        if not self._queue_client:
            logger.error("Queue client not available")
            return False

        try:
            # Send message to queue
            message = job.to_queue_message()
            self._queue_client.send_message(message)

            # Update job status
            job.status = JobStatus.QUEUED
            job.updated_at = datetime.now(timezone.utc).isoformat()
            await self.update_job(job)

            logger.info(f"Queued job {job.job_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to queue job {job.job_id}: {e}")
            return False

    async def get_job(self, job_id: str) -> ProcessingJob | None:
        """Get job by ID.

        Args:
            job_id: Job ID to retrieve.

        Returns:
            ProcessingJob or None if not found.
        """
        try:
            # Jobs use job_id as partition key
            doc = await self.cosmos.get_document(job_id, job_id)
            if doc and doc.get("documentType") == "job":
                return ProcessingJob.from_dict(doc)
            return None
        except Exception as e:
            logger.error(f"Failed to get job {job_id}: {e}")
            return None

    async def update_job(self, job: ProcessingJob) -> bool:
        """Update job in storage.

        Args:
            job: Job to update.

        Returns:
            bool: True if updated successfully.
        """
        try:
            job.updated_at = datetime.now(timezone.utc).isoformat()
            await self.cosmos.save_document_result(job.to_dict())
            return True
        except Exception as e:
            logger.error(f"Failed to update job {job.job_id}: {e}")
            return False

    async def start_job(self, job_id: str) -> ProcessingJob | None:
        """Mark job as processing.

        Args:
            job_id: Job ID to start.

        Returns:
            ProcessingJob or None if not found.
        """
        job = await self.get_job(job_id)
        if job:
            job.status = JobStatus.PROCESSING
            job.started_at = datetime.now(timezone.utc).isoformat()
            await self.update_job(job)
            logger.info(f"Started job {job_id}")
        return job

    async def complete_job(
        self,
        job_id: str,
        result: dict[str, Any],
        status: JobStatus = JobStatus.COMPLETED,
    ) -> ProcessingJob | None:
        """Mark job as completed.

        Args:
            job_id: Job ID to complete.
            result: Processing result.
            status: Final status (COMPLETED or PARTIAL).

        Returns:
            ProcessingJob or None if not found.
        """
        job = await self.get_job(job_id)
        if job:
            job.status = status
            job.result = result
            job.completed_at = datetime.now(timezone.utc).isoformat()
            await self.update_job(job)
            logger.info(f"Completed job {job_id} with status {status.value}")
        return job

    async def fail_job(self, job_id: str, error: str) -> ProcessingJob | None:
        """Mark job as failed.

        Args:
            job_id: Job ID to fail.
            error: Error message.

        Returns:
            ProcessingJob or None if not found.
        """
        job = await self.get_job(job_id)
        if job:
            job.status = JobStatus.FAILED
            job.error = error
            job.completed_at = datetime.now(timezone.utc).isoformat()
            job.retry_count += 1
            await self.update_job(job)
            logger.info(f"Failed job {job_id}: {error}")
        return job

    async def update_progress(
        self,
        job_id: str,
        forms_processed: int,
        total_forms: int,
        current_form: int | None = None,
    ) -> bool:
        """Update job progress.

        Args:
            job_id: Job ID to update.
            forms_processed: Number of forms completed.
            total_forms: Total forms to process.
            current_form: Currently processing form number.

        Returns:
            bool: True if updated successfully.
        """
        job = await self.get_job(job_id)
        if job:
            job.progress = {
                "formsProcessed": forms_processed,
                "totalForms": total_forms,
                "currentForm": current_form,
                "percentComplete": round((forms_processed / total_forms) * 100, 1)
                if total_forms > 0
                else 0,
            }
            return await self.update_job(job)
        return False

    async def list_jobs(
        self,
        status: JobStatus | None = None,
        limit: int = 50,
    ) -> list[ProcessingJob]:
        """List jobs, optionally filtered by status.

        Args:
            status: Filter by status (optional).
            limit: Maximum jobs to return.

        Returns:
            List of ProcessingJob instances.
        """
        try:
            query = "SELECT * FROM c WHERE c.documentType = 'job'"
            if status:
                query += f" AND c.status = '{status.value}'"
            query += f" ORDER BY c.createdAt DESC OFFSET 0 LIMIT {limit}"

            # Use raw query method if available
            docs = await self.cosmos.query_documents(query)
            return [ProcessingJob.from_dict(doc) for doc in docs]
        except Exception as e:
            logger.error(f"Failed to list jobs: {e}")
            return []


# Global job service instance
_job_service: JobService | None = None


def get_job_service() -> JobService | None:
    """Get or create JobService singleton.

    Returns:
        JobService or None if not configured.
    """
    global _job_service
    if _job_service is None:
        from config import get_config

        from . import get_cosmos_service

        config = get_config()
        cosmos_service = get_cosmos_service()

        _job_service = JobService(
            cosmos_service=cosmos_service,
            queue_connection_string=config.storage_connection_string,
            queue_name="document-processing",
        )
    return _job_service


def reset_job_service() -> None:
    """Reset job service (for testing)."""
    global _job_service
    _job_service = None
