"""Unit tests for the test fixtures module.

Ensures the fixture factories work correctly and produce valid test data.
"""

import pytest

from tests.fixtures import (
    SAMPLE_BLOB_URL,
    SAMPLE_CONNECTION_STRING,
    SAMPLE_COSMOS_ENDPOINT,
    SAMPLE_DOC_INTEL_ENDPOINT,
    SAMPLE_MODEL_ID,
    create_dead_letter_item,
    create_document_intel_response,
    create_mock_blob_service,
    create_mock_cosmos_service,
    create_mock_document_service,
    create_mock_http_request,
    create_mock_queue_client,
    create_processing_job,
    create_sample_config,
    create_sample_document,
    create_sample_form_result,
    create_webhook_payload,
)


class TestConstants:
    """Tests for fixture constants."""

    def test_sample_urls_are_valid(self) -> None:
        """Test that sample URLs have valid format."""
        assert SAMPLE_BLOB_URL.startswith("https://")
        assert SAMPLE_COSMOS_ENDPOINT.startswith("https://")
        assert SAMPLE_DOC_INTEL_ENDPOINT.startswith("https://")

    def test_connection_string_format(self) -> None:
        """Test that connection string has required parts."""
        assert "AccountName=" in SAMPLE_CONNECTION_STRING
        assert "AccountKey=" in SAMPLE_CONNECTION_STRING

    def test_model_id_is_string(self) -> None:
        """Test that model ID is a non-empty string."""
        assert isinstance(SAMPLE_MODEL_ID, str)
        assert len(SAMPLE_MODEL_ID) > 0


class TestMockCosmosService:
    """Tests for MockCosmosService."""

    @pytest.mark.asyncio
    async def test_save_document_tracks_documents(self) -> None:
        """Test that saved documents are tracked."""
        mock = create_mock_cosmos_service()
        doc = {"id": "test", "sourceFile": "test.pdf"}

        await mock.save_document_result(doc)

        assert len(mock.saved_documents) == 1
        assert mock.saved_documents[0] == doc

    @pytest.mark.asyncio
    async def test_get_document_returns_configured_value(self) -> None:
        """Test that get returns configured value."""
        expected = {"id": "test", "status": "completed"}
        mock = create_mock_cosmos_service(get_return_value=expected)

        result = await mock.get_document("test", "test.pdf")

        assert result == expected

    @pytest.mark.asyncio
    async def test_query_returns_configured_list(self) -> None:
        """Test that query returns configured list."""
        docs = [{"id": "doc1"}, {"id": "doc2"}]
        mock = create_mock_cosmos_service(query_return_value=docs)

        result = await mock.query_documents("SELECT * FROM c")

        assert result == docs

    @pytest.mark.asyncio
    async def test_save_failure(self) -> None:
        """Test that save can be configured to fail."""
        mock = create_mock_cosmos_service(
            save_should_fail=True,
            save_failure_message="Connection failed",
        )

        with pytest.raises(Exception) as exc_info:
            await mock.save_document_result({"id": "test"})

        assert "Connection failed" in str(exc_info.value)


class TestMockBlobService:
    """Tests for MockBlobService."""

    def test_upload_stores_blob(self) -> None:
        """Test that upload stores blob content."""
        mock = create_mock_blob_service()

        url = mock.upload_blob("container", "test.pdf", b"content")

        assert "container/test.pdf" in mock.stored_blobs
        assert mock.stored_blobs["container/test.pdf"] == b"content"
        assert "test.pdf" in url

    def test_download_returns_stored_blob(self) -> None:
        """Test that download returns stored content."""
        mock = create_mock_blob_service()
        mock.upload_blob("container", "test.pdf", b"pdf content")

        result = mock.download_blob("container", "test.pdf")

        assert result == b"pdf content"

    def test_generate_sas_url(self) -> None:
        """Test SAS URL generation."""
        mock = create_mock_blob_service()

        url = mock.generate_sas_url("container", "test.pdf")

        assert "container" in url
        assert "test.pdf" in url
        assert "?" in url  # Has SAS token

    def test_list_blobs(self) -> None:
        """Test listing blobs."""
        mock = create_mock_blob_service(list_return_value=["a.pdf", "b.pdf"])

        result = mock.list_blobs("container")

        assert result == ["a.pdf", "b.pdf"]


class TestMockDocumentService:
    """Tests for MockDocumentService."""

    @pytest.mark.asyncio
    async def test_analyze_returns_default_response(self) -> None:
        """Test that analyze returns a valid default response."""
        mock = create_mock_document_service()

        result = await mock.analyze_document("https://...", "model")

        assert result["status"] == "succeeded"
        assert "analyzeResult" in result
        assert mock.call_count == 1

    @pytest.mark.asyncio
    async def test_analyze_returns_configured_response(self) -> None:
        """Test that analyze returns configured response."""
        custom_response = {"status": "succeeded", "custom": "data"}
        mock = create_mock_document_service(analyze_return_value=custom_response)

        result = await mock.analyze_document("url", "model")

        assert result == custom_response

    @pytest.mark.asyncio
    async def test_analyze_failure(self) -> None:
        """Test that analyze can be configured to fail."""
        mock = create_mock_document_service(
            analyze_should_fail=True,
            analyze_failure_message="Rate limit",
        )

        with pytest.raises(Exception) as exc_info:
            await mock.analyze_document("url", "model")

        assert "Rate limit" in str(exc_info.value)


class TestMockHttpRequest:
    """Tests for create_mock_http_request."""

    def test_get_request(self) -> None:
        """Test creating GET request."""
        req = create_mock_http_request(method="GET")

        assert req.method == "GET"

    def test_post_with_json_body(self) -> None:
        """Test POST with JSON body."""
        body = {"key": "value", "number": 123}
        req = create_mock_http_request(method="POST", body=body)

        assert req.get_json() == body

    def test_route_params(self) -> None:
        """Test route parameters."""
        req = create_mock_http_request(route_params={"id": "123"})

        assert req.route_params["id"] == "123"

    def test_query_params(self) -> None:
        """Test query parameters."""
        req = create_mock_http_request(params={"status": "completed"})

        assert req.params["status"] == "completed"


class TestMockQueueClient:
    """Tests for create_mock_queue_client."""

    def test_send_message(self) -> None:
        """Test sending message."""
        queue = create_mock_queue_client()

        result = queue.send_message("test message")

        assert result.id == "msg_123"

    def test_send_message_failure(self) -> None:
        """Test send failure."""
        queue = create_mock_queue_client(send_should_fail=True)

        with pytest.raises(Exception):
            queue.send_message("test")

    def test_receive_messages(self) -> None:
        """Test receiving messages."""
        messages = [{"id": "m1", "content": "data1"}]
        queue = create_mock_queue_client(messages=messages)

        received = list(queue.receive_messages())

        assert len(received) == 1
        assert received[0].id == "m1"


class TestDocumentFactories:
    """Tests for document factory functions."""

    def test_create_sample_document_defaults(self) -> None:
        """Test sample document with defaults."""
        doc = create_sample_document()

        assert "id" in doc
        assert "sourceFile" in doc
        assert doc["status"] == "completed"
        assert "fields" in doc
        assert "confidence" in doc

    def test_create_sample_document_custom(self) -> None:
        """Test sample document with custom values."""
        doc = create_sample_document(
            doc_id="custom_id",
            status="failed",
            error="Test error",
        )

        assert doc["id"] == "custom_id"
        assert doc["status"] == "failed"
        assert doc["error"] == "Test error"

    def test_create_sample_form_result(self) -> None:
        """Test form result factory."""
        result = create_sample_form_result(
            form_number=2,
            total_forms=5,
            page_range="3-4",
        )

        assert result["formNumber"] == 2
        assert result["totalForms"] == 5
        assert result["pageRange"] == "3-4"


class TestJobFactories:
    """Tests for job factory functions."""

    def test_create_processing_job_pending(self) -> None:
        """Test creating pending job."""
        job = create_processing_job(status="pending")

        assert job["status"] == "pending"
        assert job["startedAt"] is None
        assert job["completedAt"] is None

    def test_create_processing_job_completed(self) -> None:
        """Test creating completed job."""
        job = create_processing_job(status="completed")

        assert job["status"] == "completed"
        assert job["startedAt"] is not None
        assert job["completedAt"] is not None
        assert job["result"] is not None

    def test_create_processing_job_failed(self) -> None:
        """Test creating failed job."""
        job = create_processing_job(status="failed", error="Custom error")

        assert job["status"] == "failed"
        assert job["error"] == "Custom error"


class TestConfigFactory:
    """Tests for config factory."""

    def test_create_sample_config_defaults(self) -> None:
        """Test config with defaults."""
        config = create_sample_config()

        assert config["doc_intel_endpoint"] == SAMPLE_DOC_INTEL_ENDPOINT
        assert config["function_timeout"] == 230
        assert config["log_level"] == "INFO"

    def test_create_sample_config_custom(self) -> None:
        """Test config with custom values."""
        config = create_sample_config(
            function_timeout=300,
            log_level="DEBUG",
        )

        assert config["function_timeout"] == 300
        assert config["log_level"] == "DEBUG"


class TestApiResponseFactories:
    """Tests for API response factories."""

    def test_create_document_intel_response(self) -> None:
        """Test Document Intelligence response factory."""
        response = create_document_intel_response()

        assert response["status"] == "succeeded"
        assert "analyzeResult" in response
        assert "documents" in response["analyzeResult"]

    def test_create_document_intel_response_custom_fields(self) -> None:
        """Test response with custom fields."""
        fields = {"customField": {"content": "value", "confidence": 0.9}}
        response = create_document_intel_response(fields=fields)

        assert "customField" in response["analyzeResult"]["documents"][0]["fields"]

    def test_create_webhook_payload(self) -> None:
        """Test webhook payload factory."""
        payload = create_webhook_payload(
            event_type="processing.completed",
            job_id="job_123",
        )

        assert payload["eventType"] == "processing.completed"
        assert payload["data"]["jobId"] == "job_123"

    def test_create_dead_letter_item(self) -> None:
        """Test dead letter item factory."""
        item = create_dead_letter_item(
            reason="rate_limit",
            retry_count=2,
        )

        assert item["reason"] == "rate_limit"
        assert item["retryCount"] == 2
        assert item["documentType"] == "dead_letter"
