"""Unit tests for job_service module."""

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.job_service import (
    JobService,
    JobStatus,
    ProcessingJob,
    get_job_service,
    reset_job_service,
)


class TestJobStatus:
    """Test JobStatus enum."""

    def test_all_statuses_exist(self):
        """Test all expected statuses are defined."""
        assert JobStatus.PENDING == "pending"
        assert JobStatus.QUEUED == "queued"
        assert JobStatus.PROCESSING == "processing"
        assert JobStatus.COMPLETED == "completed"
        assert JobStatus.FAILED == "failed"
        assert JobStatus.PARTIAL == "partial"


class TestProcessingJob:
    """Tests for ProcessingJob dataclass."""

    def test_create_job_with_required_fields(self):
        """Test creating job with required fields."""
        job = ProcessingJob(
            job_id="job_123",
            blob_url="https://storage/container/file.pdf",
            blob_name="folder/file.pdf",
            model_id="prebuilt-invoice",
        )
        assert job.job_id == "job_123"
        assert job.blob_url == "https://storage/container/file.pdf"
        assert job.blob_name == "folder/file.pdf"
        assert job.model_id == "prebuilt-invoice"
        assert job.status == JobStatus.PENDING
        assert job.tenant_id is None

    def test_create_job_with_all_fields(self):
        """Test creating job with all optional fields."""
        job = ProcessingJob(
            job_id="job_123",
            blob_url="https://storage/container/file.pdf",
            blob_name="folder/file.pdf",
            model_id="custom-model",
            status=JobStatus.PROCESSING,
            profile_name="invoice",
            pages_per_form=2,
            webhook_url="https://webhook.example.com",
            tenant_id="tenant-abc",
            retry_count=1,
            max_retries=5,
        )
        assert job.status == JobStatus.PROCESSING
        assert job.profile_name == "invoice"
        assert job.pages_per_form == 2
        assert job.webhook_url == "https://webhook.example.com"
        assert job.tenant_id == "tenant-abc"
        assert job.retry_count == 1
        assert job.max_retries == 5

    def test_to_dict(self):
        """Test converting job to dictionary."""
        job = ProcessingJob(
            job_id="job_123",
            blob_url="https://storage/file.pdf",
            blob_name="file.pdf",
            model_id="model-v1",
            profile_name="invoice",
        )
        data = job.to_dict()

        assert data["id"] == "job_123"
        assert data["jobId"] == "job_123"
        assert data["blobUrl"] == "https://storage/file.pdf"
        assert data["blobName"] == "file.pdf"
        assert data["modelId"] == "model-v1"
        assert data["status"] == "pending"
        assert data["profileName"] == "invoice"
        assert data["documentType"] == "job"
        assert "tenantId" not in data  # Not set

    def test_to_dict_with_tenant_id(self):
        """Test to_dict includes tenantId when set."""
        job = ProcessingJob(
            job_id="job_123",
            blob_url="https://storage/file.pdf",
            blob_name="file.pdf",
            model_id="model-v1",
            tenant_id="tenant-xyz",
        )
        data = job.to_dict()
        assert data["tenantId"] == "tenant-xyz"

    def test_from_dict(self):
        """Test creating job from dictionary."""
        data = {
            "id": "job_456",
            "jobId": "job_456",
            "blobUrl": "https://storage/test.pdf",
            "blobName": "test.pdf",
            "modelId": "prebuilt-layout",
            "status": "completed",
            "profileName": "receipt",
            "pagesPerForm": 3,
            "webhookUrl": "https://hook.com",
            "tenantId": "tenant-123",
            "createdAt": "2024-01-01T00:00:00Z",
            "updatedAt": "2024-01-01T01:00:00Z",
            "startedAt": "2024-01-01T00:30:00Z",
            "completedAt": "2024-01-01T01:00:00Z",
            "progress": {"formsProcessed": 5, "totalForms": 5},
            "result": {"status": "success"},
            "error": None,
            "retryCount": 2,
            "maxRetries": 3,
        }
        job = ProcessingJob.from_dict(data)

        assert job.job_id == "job_456"
        assert job.blob_url == "https://storage/test.pdf"
        assert job.status == JobStatus.COMPLETED
        assert job.profile_name == "receipt"
        assert job.pages_per_form == 3
        assert job.webhook_url == "https://hook.com"
        assert job.tenant_id == "tenant-123"
        assert job.retry_count == 2
        assert job.max_retries == 3
        assert job.result == {"status": "success"}

    def test_from_dict_with_id_fallback(self):
        """Test from_dict uses 'id' when 'jobId' not present."""
        data = {
            "id": "job_789",
            "blobUrl": "https://storage/file.pdf",
            "blobName": "file.pdf",
            "modelId": "model",
        }
        job = ProcessingJob.from_dict(data)
        assert job.job_id == "job_789"

    def test_to_queue_message(self):
        """Test creating queue message."""
        job = ProcessingJob(
            job_id="job_abc",
            blob_url="https://storage/doc.pdf",
            blob_name="doc.pdf",
            model_id="custom-model",
            profile_name="w2",
            pages_per_form=2,
            webhook_url="https://notify.com",
        )
        message = job.to_queue_message()
        data = json.loads(message)

        assert data["jobId"] == "job_abc"
        assert data["blobUrl"] == "https://storage/doc.pdf"
        assert data["blobName"] == "doc.pdf"
        assert data["modelId"] == "custom-model"
        assert data["profileName"] == "w2"
        assert data["pagesPerForm"] == 2
        assert data["webhookUrl"] == "https://notify.com"

    def test_to_queue_message_with_tenant_id(self):
        """Test queue message includes tenantId when set."""
        job = ProcessingJob(
            job_id="job_abc",
            blob_url="https://storage/doc.pdf",
            blob_name="doc.pdf",
            model_id="model",
            tenant_id="tenant-111",
        )
        message = job.to_queue_message()
        data = json.loads(message)
        assert data["tenantId"] == "tenant-111"

    def test_to_queue_message_without_tenant_id(self):
        """Test queue message excludes tenantId when not set."""
        job = ProcessingJob(
            job_id="job_abc",
            blob_url="https://storage/doc.pdf",
            blob_name="doc.pdf",
            model_id="model",
        )
        message = job.to_queue_message()
        data = json.loads(message)
        assert "tenantId" not in data


class TestJobService:
    """Tests for JobService class."""

    @pytest.fixture
    def mock_cosmos(self):
        """Create mock Cosmos service."""
        cosmos = AsyncMock()
        cosmos.save_document_result = AsyncMock(return_value={"id": "test"})
        cosmos.get_document = AsyncMock(return_value=None)
        cosmos.query_documents = AsyncMock(return_value=[])
        return cosmos

    @pytest.fixture
    def job_service(self, mock_cosmos):
        """Create JobService with mock dependencies."""
        return JobService(
            cosmos_service=mock_cosmos,
            queue_connection_string=None,
            queue_name="test-queue",
        )

    def test_init_without_queue(self, mock_cosmos):
        """Test initialization without queue."""
        service = JobService(cosmos_service=mock_cosmos)
        assert service.cosmos == mock_cosmos
        assert service._queue_client is None

    def test_generate_job_id(self, job_service):
        """Test job ID generation."""
        job_id = job_service.generate_job_id()
        assert job_id.startswith("job_")
        assert len(job_id) == 16  # "job_" + 12 hex chars

    def test_generate_job_id_unique(self, job_service):
        """Test job IDs are unique."""
        ids = [job_service.generate_job_id() for _ in range(100)]
        assert len(set(ids)) == 100

    @pytest.mark.asyncio
    async def test_create_job(self, job_service, mock_cosmos):
        """Test creating a new job."""
        job = await job_service.create_job(
            blob_url="https://storage/test.pdf",
            blob_name="test.pdf",
            model_id="prebuilt-invoice",
            profile_name="invoice",
            pages_per_form=2,
            webhook_url="https://webhook.com",
            tenant_id="tenant-123",
        )

        assert job.blob_url == "https://storage/test.pdf"
        assert job.blob_name == "test.pdf"
        assert job.model_id == "prebuilt-invoice"
        assert job.profile_name == "invoice"
        assert job.pages_per_form == 2
        assert job.webhook_url == "https://webhook.com"
        assert job.tenant_id == "tenant-123"
        assert job.status == JobStatus.PENDING

        # Verify save was called
        mock_cosmos.save_document_result.assert_called_once()
        saved_data = mock_cosmos.save_document_result.call_args[0][0]
        assert saved_data["tenantId"] == "tenant-123"

    @pytest.mark.asyncio
    async def test_queue_job_no_client(self, job_service):
        """Test queueing job when queue client not available."""
        job = ProcessingJob(
            job_id="job_123",
            blob_url="https://storage/test.pdf",
            blob_name="test.pdf",
            model_id="model",
        )
        result = await job_service.queue_job(job)
        assert result is False

    @pytest.mark.asyncio
    async def test_queue_job_with_client(self, mock_cosmos):
        """Test queueing job with queue client."""
        mock_queue = MagicMock()
        mock_queue.send_message = MagicMock()

        service = JobService(cosmos_service=mock_cosmos)
        service._queue_client = mock_queue

        job = ProcessingJob(
            job_id="job_123",
            blob_url="https://storage/test.pdf",
            blob_name="test.pdf",
            model_id="model",
        )

        result = await service.queue_job(job)

        assert result is True
        assert job.status == JobStatus.QUEUED
        mock_queue.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_queue_job_error(self, mock_cosmos):
        """Test queueing job with error."""
        mock_queue = MagicMock()
        mock_queue.send_message = MagicMock(side_effect=Exception("Queue error"))

        service = JobService(cosmos_service=mock_cosmos)
        service._queue_client = mock_queue

        job = ProcessingJob(
            job_id="job_123",
            blob_url="https://storage/test.pdf",
            blob_name="test.pdf",
            model_id="model",
        )

        result = await service.queue_job(job)
        assert result is False

    @pytest.mark.asyncio
    async def test_get_job_not_found(self, job_service, mock_cosmos):
        """Test getting non-existent job."""
        mock_cosmos.get_document.return_value = None
        job = await job_service.get_job("nonexistent")
        assert job is None

    @pytest.mark.asyncio
    async def test_get_job_found(self, job_service, mock_cosmos):
        """Test getting existing job."""
        mock_cosmos.get_document.return_value = {
            "id": "job_123",
            "jobId": "job_123",
            "blobUrl": "https://storage/test.pdf",
            "blobName": "test.pdf",
            "modelId": "model",
            "status": "processing",
            "documentType": "job",
        }
        job = await job_service.get_job("job_123")
        assert job is not None
        assert job.job_id == "job_123"
        assert job.status == JobStatus.PROCESSING

    @pytest.mark.asyncio
    async def test_get_job_not_job_document(self, job_service, mock_cosmos):
        """Test getting document that isn't a job."""
        mock_cosmos.get_document.return_value = {
            "id": "doc_123",
            "sourceFile": "test.pdf",
            "documentType": "extraction",
        }
        job = await job_service.get_job("doc_123")
        assert job is None

    @pytest.mark.asyncio
    async def test_get_job_error(self, job_service, mock_cosmos):
        """Test get job with error."""
        mock_cosmos.get_document.side_effect = Exception("DB error")
        job = await job_service.get_job("job_123")
        assert job is None

    @pytest.mark.asyncio
    async def test_update_job(self, job_service, mock_cosmos):
        """Test updating a job."""
        job = ProcessingJob(
            job_id="job_123",
            blob_url="https://storage/test.pdf",
            blob_name="test.pdf",
            model_id="model",
        )
        job.status = JobStatus.PROCESSING

        result = await job_service.update_job(job)
        assert result is True
        mock_cosmos.save_document_result.assert_called()

    @pytest.mark.asyncio
    async def test_update_job_error(self, job_service, mock_cosmos):
        """Test update job with error."""
        mock_cosmos.save_document_result.side_effect = Exception("Save error")
        job = ProcessingJob(
            job_id="job_123",
            blob_url="https://storage/test.pdf",
            blob_name="test.pdf",
            model_id="model",
        )
        result = await job_service.update_job(job)
        assert result is False

    @pytest.mark.asyncio
    async def test_start_job(self, job_service, mock_cosmos):
        """Test starting a job."""
        mock_cosmos.get_document.return_value = {
            "id": "job_123",
            "jobId": "job_123",
            "blobUrl": "https://storage/test.pdf",
            "blobName": "test.pdf",
            "modelId": "model",
            "status": "queued",
            "documentType": "job",
        }

        job = await job_service.start_job("job_123")
        assert job is not None
        assert job.status == JobStatus.PROCESSING
        assert job.started_at is not None

    @pytest.mark.asyncio
    async def test_start_job_not_found(self, job_service, mock_cosmos):
        """Test starting non-existent job."""
        mock_cosmos.get_document.return_value = None
        job = await job_service.start_job("nonexistent")
        assert job is None

    @pytest.mark.asyncio
    async def test_complete_job(self, job_service, mock_cosmos):
        """Test completing a job."""
        mock_cosmos.get_document.return_value = {
            "id": "job_123",
            "jobId": "job_123",
            "blobUrl": "https://storage/test.pdf",
            "blobName": "test.pdf",
            "modelId": "model",
            "status": "processing",
            "documentType": "job",
        }

        result_data = {"formsProcessed": 5, "status": "success"}
        job = await job_service.complete_job("job_123", result_data)

        assert job is not None
        assert job.status == JobStatus.COMPLETED
        assert job.result == result_data
        assert job.completed_at is not None

    @pytest.mark.asyncio
    async def test_complete_job_partial(self, job_service, mock_cosmos):
        """Test completing job with partial status."""
        mock_cosmos.get_document.return_value = {
            "id": "job_123",
            "jobId": "job_123",
            "blobUrl": "https://storage/test.pdf",
            "blobName": "test.pdf",
            "modelId": "model",
            "status": "processing",
            "documentType": "job",
        }

        result_data = {"formsProcessed": 3, "totalForms": 5}
        job = await job_service.complete_job("job_123", result_data, JobStatus.PARTIAL)

        assert job.status == JobStatus.PARTIAL

    @pytest.mark.asyncio
    async def test_complete_job_not_found(self, job_service, mock_cosmos):
        """Test completing non-existent job."""
        mock_cosmos.get_document.return_value = None
        job = await job_service.complete_job("nonexistent", {})
        assert job is None

    @pytest.mark.asyncio
    async def test_fail_job(self, job_service, mock_cosmos):
        """Test failing a job."""
        mock_cosmos.get_document.return_value = {
            "id": "job_123",
            "jobId": "job_123",
            "blobUrl": "https://storage/test.pdf",
            "blobName": "test.pdf",
            "modelId": "model",
            "status": "processing",
            "retryCount": 0,
            "documentType": "job",
        }

        job = await job_service.fail_job("job_123", "Processing error")

        assert job is not None
        assert job.status == JobStatus.FAILED
        assert job.error == "Processing error"
        assert job.retry_count == 1
        assert job.completed_at is not None

    @pytest.mark.asyncio
    async def test_fail_job_not_found(self, job_service, mock_cosmos):
        """Test failing non-existent job."""
        mock_cosmos.get_document.return_value = None
        job = await job_service.fail_job("nonexistent", "Error")
        assert job is None

    @pytest.mark.asyncio
    async def test_update_progress(self, job_service, mock_cosmos):
        """Test updating job progress."""
        mock_cosmos.get_document.return_value = {
            "id": "job_123",
            "jobId": "job_123",
            "blobUrl": "https://storage/test.pdf",
            "blobName": "test.pdf",
            "modelId": "model",
            "status": "processing",
            "documentType": "job",
        }

        result = await job_service.update_progress(
            job_id="job_123",
            forms_processed=3,
            total_forms=5,
            current_form=4,
        )

        assert result is True
        # Verify save was called with updated progress
        saved_data = mock_cosmos.save_document_result.call_args[0][0]
        assert saved_data["progress"]["formsProcessed"] == 3
        assert saved_data["progress"]["totalForms"] == 5
        assert saved_data["progress"]["currentForm"] == 4
        assert saved_data["progress"]["percentComplete"] == 60.0

    @pytest.mark.asyncio
    async def test_update_progress_zero_total(self, job_service, mock_cosmos):
        """Test progress update with zero total forms."""
        mock_cosmos.get_document.return_value = {
            "id": "job_123",
            "jobId": "job_123",
            "blobUrl": "https://storage/test.pdf",
            "blobName": "test.pdf",
            "modelId": "model",
            "status": "processing",
            "documentType": "job",
        }

        result = await job_service.update_progress(
            job_id="job_123",
            forms_processed=0,
            total_forms=0,
        )

        assert result is True
        saved_data = mock_cosmos.save_document_result.call_args[0][0]
        assert saved_data["progress"]["percentComplete"] == 0

    @pytest.mark.asyncio
    async def test_update_progress_not_found(self, job_service, mock_cosmos):
        """Test progress update for non-existent job."""
        mock_cosmos.get_document.return_value = None
        result = await job_service.update_progress("nonexistent", 1, 1)
        assert result is False

    @pytest.mark.asyncio
    async def test_list_jobs(self, job_service, mock_cosmos):
        """Test listing jobs."""
        mock_cosmos.query_documents.return_value = [
            {
                "id": "job_1",
                "jobId": "job_1",
                "blobUrl": "https://storage/a.pdf",
                "blobName": "a.pdf",
                "modelId": "model",
                "status": "completed",
                "documentType": "job",
            },
            {
                "id": "job_2",
                "jobId": "job_2",
                "blobUrl": "https://storage/b.pdf",
                "blobName": "b.pdf",
                "modelId": "model",
                "status": "pending",
                "documentType": "job",
            },
        ]

        jobs = await job_service.list_jobs()
        assert len(jobs) == 2
        assert jobs[0].job_id == "job_1"
        assert jobs[1].job_id == "job_2"

    @pytest.mark.asyncio
    async def test_list_jobs_with_status_filter(self, job_service, mock_cosmos):
        """Test listing jobs filtered by status."""
        mock_cosmos.query_documents.return_value = []

        await job_service.list_jobs(status=JobStatus.COMPLETED, limit=10)

        # Verify query includes status filter
        query = mock_cosmos.query_documents.call_args[0][0]
        assert "completed" in query
        assert "LIMIT 10" in query

    @pytest.mark.asyncio
    async def test_list_jobs_error(self, job_service, mock_cosmos):
        """Test list jobs with error."""
        mock_cosmos.query_documents.side_effect = Exception("Query error")
        jobs = await job_service.list_jobs()
        assert jobs == []


class TestGetJobService:
    """Tests for get_job_service singleton."""

    def setup_method(self):
        """Reset singleton before each test."""
        reset_job_service()

    def teardown_method(self):
        """Reset singleton after each test."""
        reset_job_service()

    @patch("services.get_cosmos_service")
    @patch("config.get_config")
    def test_get_job_service_creates_singleton(self, mock_config, mock_cosmos):
        """Test get_job_service creates singleton."""
        mock_config.return_value = MagicMock(
            storage_connection_string=None,
        )
        mock_cosmos.return_value = AsyncMock()

        service1 = get_job_service()
        service2 = get_job_service()

        assert service1 is service2
        assert service1 is not None

    def test_reset_job_service(self):
        """Test reset_job_service clears singleton."""
        # This should work without error
        reset_job_service()
