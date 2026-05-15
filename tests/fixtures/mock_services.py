"""Mock service factories for testing.

Provides reusable mock objects for Azure services and internal services.
These mocks follow consistent patterns and can be customized per test.

Usage:
    # Basic usage with defaults
    mock_cosmos = create_mock_cosmos_service()

    # Customized mock with specific behavior
    mock_cosmos = create_mock_cosmos_service(
        save_return_value={"id": "custom_id"},
        query_return_value=[{"id": "doc1"}, {"id": "doc2"}],
    )
"""

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch


@dataclass
class MockCosmosService:
    """Mock Cosmos DB service with configurable behavior.

    Attributes:
        saved_documents: List of documents that were "saved" during test.
        get_return_value: Value to return from get_document calls.
        query_return_value: Value to return from query calls.
        save_should_fail: If True, save operations will raise an exception.
    """

    saved_documents: list[dict] = field(default_factory=list)
    get_return_value: dict | None = None
    query_return_value: list[dict] = field(default_factory=list)
    save_should_fail: bool = False
    save_failure_message: str = "Mock save failure"

    async def save_document_result(self, document: dict) -> dict:
        """Mock save operation."""
        if self.save_should_fail:
            raise Exception(self.save_failure_message)
        self.saved_documents.append(document)
        return document

    async def get_document(self, doc_id: str, partition_key: str) -> dict | None:
        """Mock get document operation."""
        return self.get_return_value

    async def query_documents(self, query: str) -> list[dict]:
        """Mock query operation."""
        return self.query_return_value

    async def query_by_source_file(self, source_file: str) -> list[dict]:
        """Mock query by source file."""
        return self.query_return_value

    async def delete_document(self, doc_id: str, partition_key: str) -> bool:
        """Mock delete operation."""
        return True

    async def delete_by_source_file(self, source_file: str) -> int:
        """Mock delete by source file."""
        return len(self.query_return_value)


@dataclass
class MockBlobService:
    """Mock Blob Storage service with configurable behavior.

    Attributes:
        stored_blobs: Dict of blob_name -> content for blobs stored during test.
        get_return_value: Value to return from blob reads.
        sas_token: SAS token to return from generate_sas_url.
    """

    stored_blobs: dict[str, bytes] = field(default_factory=dict)
    get_return_value: bytes | None = None
    sas_token: str = "sv=2021-06-08&sig=mock_signature"
    list_return_value: list[str] = field(default_factory=list)

    def generate_sas_url(
        self,
        container_name: str,
        blob_name: str,
        expiry_hours: int = 1,
    ) -> str:
        """Generate mock SAS URL."""
        return f"https://mockaccount.blob.core.windows.net/{container_name}/{blob_name}?{self.sas_token}"

    def upload_blob(
        self,
        container_name: str,
        blob_name: str,
        data: bytes,
        content_type: str = "application/octet-stream",
    ) -> str:
        """Mock upload operation."""
        self.stored_blobs[f"{container_name}/{blob_name}"] = data
        return f"https://mockaccount.blob.core.windows.net/{container_name}/{blob_name}"

    def download_blob(self, container_name: str, blob_name: str) -> bytes:
        """Mock download operation."""
        key = f"{container_name}/{blob_name}"
        if key in self.stored_blobs:
            return self.stored_blobs[key]
        if self.get_return_value is not None:
            return self.get_return_value
        raise Exception(f"Blob not found: {blob_name}")

    def list_blobs(self, container_name: str, prefix: str = "") -> list[str]:
        """Mock list blobs operation."""
        if self.list_return_value:
            return self.list_return_value
        return [
            k.split("/", 1)[1]
            for k in self.stored_blobs.keys()
            if k.startswith(container_name) and k.split("/", 1)[1].startswith(prefix)
        ]

    def delete_blob(self, container_name: str, blob_name: str) -> bool:
        """Mock delete operation."""
        key = f"{container_name}/{blob_name}"
        if key in self.stored_blobs:
            del self.stored_blobs[key]
        return True


@dataclass
class MockDocumentService:
    """Mock Document Intelligence service with configurable behavior.

    Attributes:
        analyze_return_value: Value to return from analyze_document.
        analyze_should_fail: If True, analyze operations will raise.
        call_count: Number of times analyze_document was called.
    """

    analyze_return_value: dict | None = None
    analyze_should_fail: bool = False
    analyze_failure_message: str = "Mock analysis failure"
    call_count: int = 0

    async def analyze_document(
        self,
        blob_url: str,
        model_id: str,
    ) -> dict:
        """Mock document analysis."""
        self.call_count += 1

        if self.analyze_should_fail:
            raise Exception(self.analyze_failure_message)

        if self.analyze_return_value is not None:
            return self.analyze_return_value

        # Return default mock response
        return {
            "status": "succeeded",
            "analyzeResult": {
                "documents": [
                    {
                        "docType": "invoice",
                        "fields": {
                            "vendorName": {"content": "Test Vendor", "confidence": 0.95},
                            "amount": {"content": "100.00", "confidence": 0.90},
                        },
                        "confidence": 0.92,
                    }
                ],
                "pages": [{"pageNumber": 1, "width": 8.5, "height": 11}],
            },
        }


def create_mock_cosmos_service(**kwargs) -> MockCosmosService:
    """Factory function to create MockCosmosService.

    Args:
        **kwargs: Arguments passed to MockCosmosService constructor.

    Returns:
        MockCosmosService instance.

    Example:
        mock = create_mock_cosmos_service(
            get_return_value={"id": "test", "status": "completed"},
            query_return_value=[{"id": "doc1"}, {"id": "doc2"}],
        )
    """
    return MockCosmosService(**kwargs)


def create_mock_blob_service(**kwargs) -> MockBlobService:
    """Factory function to create MockBlobService.

    Args:
        **kwargs: Arguments passed to MockBlobService constructor.

    Returns:
        MockBlobService instance.

    Example:
        mock = create_mock_blob_service(
            get_return_value=b"PDF content here",
            list_return_value=["file1.pdf", "file2.pdf"],
        )
    """
    return MockBlobService(**kwargs)


def create_mock_document_service(**kwargs) -> MockDocumentService:
    """Factory function to create MockDocumentService.

    Args:
        **kwargs: Arguments passed to MockDocumentService constructor.

    Returns:
        MockDocumentService instance.

    Example:
        mock = create_mock_document_service(
            analyze_return_value={"status": "succeeded", "analyzeResult": {...}},
        )
    """
    return MockDocumentService(**kwargs)


def create_mock_http_request(
    method: str = "POST",
    url: str = "https://test.azurewebsites.net/api/test",
    body: dict | bytes | None = None,
    headers: dict[str, str] | None = None,
    route_params: dict[str, str] | None = None,
    params: dict[str, str] | None = None,
) -> MagicMock:
    """Create a mock Azure Functions HTTP request.

    Args:
        method: HTTP method (GET, POST, etc.).
        url: Request URL.
        body: Request body (dict will be JSON encoded).
        headers: Request headers.
        route_params: Route parameters (e.g., {"id": "123"}).
        params: Query string parameters.

    Returns:
        MagicMock configured as azure.functions.HttpRequest.

    Example:
        req = create_mock_http_request(
            method="POST",
            body={"blobUrl": "https://...", "modelId": "custom-model"},
            headers={"Content-Type": "application/json"},
        )
    """
    mock_request = MagicMock()
    mock_request.method = method
    mock_request.url = url
    mock_request.headers = headers or {"Content-Type": "application/json"}
    mock_request.route_params = route_params or {}
    mock_request.params = params or {}

    # Handle body
    if body is None:
        mock_request.get_body.return_value = b""
        mock_request.get_json.side_effect = ValueError("No JSON body")
    elif isinstance(body, dict):
        json_body = json.dumps(body)
        mock_request.get_body.return_value = json_body.encode("utf-8")
        mock_request.get_json.return_value = body
    else:
        mock_request.get_body.return_value = body
        try:
            mock_request.get_json.return_value = json.loads(body)
        except (json.JSONDecodeError, TypeError):
            mock_request.get_json.side_effect = ValueError("Invalid JSON")

    return mock_request


def create_mock_queue_client(
    messages: list[dict] | None = None,
    send_should_fail: bool = False,
) -> MagicMock:
    """Create a mock Azure Storage Queue client.

    Args:
        messages: List of messages to return from receive_messages.
        send_should_fail: If True, send_message will raise an exception.

    Returns:
        MagicMock configured as QueueClient.

    Example:
        queue = create_mock_queue_client(
            messages=[{"id": "msg1", "content": "..."}],
        )
    """
    mock_queue = MagicMock()
    mock_queue.queue_name = "mock-queue"

    # Configure send_message
    if send_should_fail:
        mock_queue.send_message.side_effect = Exception("Queue send failed")
    else:
        mock_queue.send_message.return_value = MagicMock(id="msg_123")

    # Configure receive_messages
    if messages:
        mock_messages = []
        for msg in messages:
            mock_msg = MagicMock()
            mock_msg.id = msg.get("id", f"msg_{len(mock_messages)}")
            mock_msg.content = msg.get("content", "{}")
            mock_msg.dequeue_count = msg.get("dequeue_count", 1)
            mock_messages.append(mock_msg)
        mock_queue.receive_messages.return_value = iter(mock_messages)
    else:
        mock_queue.receive_messages.return_value = iter([])

    # Configure delete_message
    mock_queue.delete_message.return_value = None

    # Configure create_queue (for initialization)
    mock_queue.create_queue.return_value = None

    return mock_queue


def create_cosmos_client_patch():
    """Create a patch context for CosmosClient that provides full mock chain.

    Returns:
        Tuple of (patch context manager, mock container) for use in tests.

    Example:
        cosmos_patch, mock_container = create_cosmos_client_patch()
        mock_container.upsert_item = AsyncMock(return_value={"id": "test"})

        with cosmos_patch:
            result = await cosmos_service.save_document_result(doc)
    """
    mock_container = AsyncMock()
    mock_database = MagicMock()
    mock_database.get_container_client = MagicMock(return_value=mock_container)

    mock_client = AsyncMock()
    mock_client.get_database_client = MagicMock(return_value=mock_database)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock()

    cosmos_patch = patch("services.cosmos_service.CosmosClient", return_value=mock_client)
    credential_patch = patch("services.cosmos_service.DefaultAzureCredential")

    class CombinedPatch:
        def __enter__(self):
            cosmos_patch.__enter__()
            credential_patch.__enter__()
            return mock_container

        def __exit__(self, *args):
            cosmos_patch.__exit__(*args)
            credential_patch.__exit__(*args)

    return CombinedPatch(), mock_container
