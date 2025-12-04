"""Cosmos DB service for document storage.

Implements async Cosmos DB operations with proper partition key handling.
"""

import logging
from typing import Any

from azure.cosmos.aio import CosmosClient
from azure.cosmos.exceptions import CosmosHttpResponseError
from azure.identity.aio import DefaultAzureCredential

logger = logging.getLogger(__name__)


class CosmosError(Exception):
    """Raised when Cosmos DB operations fail."""

    def __init__(self, operation: str, reason: str) -> None:
        self.operation = operation
        self.reason = reason
        super().__init__(f"Cosmos DB {operation} failed: {reason}")


class CosmosService:
    """Async Cosmos DB service for document persistence."""

    def __init__(
        self,
        endpoint: str,
        database_name: str,
        container_name: str,
    ) -> None:
        """Initialize Cosmos Service.

        Args:
            endpoint: Cosmos DB account endpoint.
            database_name: Database name.
            container_name: Container name.
        """
        self.endpoint = endpoint
        self.database_name = database_name
        self.container_name = container_name
        # Use managed identity for authentication
        self.credential = DefaultAzureCredential()

    async def save_document_result(self, document: dict[str, Any]) -> dict[str, Any]:
        """Save document processing result to Cosmos DB.

        CRITICAL: Document must have 'id' (string!) and 'sourceFile' (partition key).

        Args:
            document: Document data to save. Must include:
                - id: Unique identifier (string, not integer!)
                - sourceFile: Partition key (immutable)

        Returns:
            dict: Saved document with Cosmos metadata.

        Raises:
            CosmosError: If save operation fails.
        """
        # CRITICAL: Validate required fields
        if "id" not in document:
            raise CosmosError("save", "Document missing required 'id' field")
        if "sourceFile" not in document:
            raise CosmosError("save", "Document missing required 'sourceFile' partition key")

        # CRITICAL: ID must be string, not integer
        if not isinstance(document["id"], str):
            document["id"] = str(document["id"])

        try:
            async with CosmosClient(
                url=self.endpoint,
                credential=self.credential,
            ) as client:
                database = client.get_database_client(self.database_name)
                container = database.get_container_client(self.container_name)

                # Upsert (insert or update)
                result = await container.upsert_item(body=document)

                logger.info(f"Saved document {document['id']} to Cosmos DB")
                return result

        except CosmosHttpResponseError as e:
            logger.error(f"Cosmos DB error: {e.message}")
            raise CosmosError("save", e.message) from e
        except Exception as e:
            logger.exception(f"Unexpected error saving document: {e}")
            raise CosmosError("save", str(e)) from e

    async def get_document(
        self,
        doc_id: str,
        partition_key: str,
    ) -> dict[str, Any] | None:
        """Retrieve document by ID and partition key.

        CRITICAL: Partition key is required for all read operations.

        Args:
            doc_id: Document ID.
            partition_key: Partition key value (sourceFile).

        Returns:
            dict: Document if found, None otherwise.

        Raises:
            CosmosError: If read operation fails (except 404).
        """
        try:
            async with CosmosClient(
                url=self.endpoint,
                credential=self.credential,
            ) as client:
                database = client.get_database_client(self.database_name)
                container = database.get_container_client(self.container_name)

                result = await container.read_item(
                    item=doc_id,
                    partition_key=partition_key,
                )
                return result

        except CosmosHttpResponseError as e:
            if e.status_code == 404:
                logger.info(f"Document {doc_id} not found")
                return None
            logger.error(f"Cosmos DB error: {e.message}")
            raise CosmosError("get", e.message) from e
        except Exception as e:
            logger.exception(f"Unexpected error getting document: {e}")
            raise CosmosError("get", str(e)) from e

    async def query_documents(
        self,
        query: str,
        parameters: list[dict[str, Any]] | None = None,
        partition_key: str | None = None,
    ) -> list[dict[str, Any]]:
        """Query documents using SQL syntax.

        CRITICAL: Cross-partition queries are expensive - use partition_key when possible.

        Args:
            query: SQL query string.
            parameters: Query parameters (optional).
            partition_key: Partition key to limit query scope (recommended).

        Returns:
            list: List of matching documents.

        Raises:
            CosmosError: If query fails.
        """
        try:
            async with CosmosClient(
                url=self.endpoint,
                credential=self.credential,
            ) as client:
                database = client.get_database_client(self.database_name)
                container = database.get_container_client(self.container_name)

                query_params = parameters or []
                items = []

                # CRITICAL: Use partition_key to avoid expensive cross-partition queries
                async for item in container.query_items(
                    query=query,
                    parameters=query_params,
                    partition_key=partition_key,
                ):
                    items.append(item)

                return items

        except CosmosHttpResponseError as e:
            logger.error(f"Cosmos DB query error: {e.message}")
            raise CosmosError("query", e.message) from e
        except Exception as e:
            logger.exception(f"Unexpected error querying documents: {e}")
            raise CosmosError("query", str(e)) from e

    async def get_document_status(self, source_file: str) -> str | None:
        """Get processing status for a document.

        Args:
            source_file: Source file path (partition key).

        Returns:
            str: Status if document exists, None otherwise.
        """
        # Derive ID from source file (same logic as document creation)
        doc_id = source_file.replace("/", "_").replace(".", "_")

        doc = await self.get_document(doc_id, source_file)
        if doc:
            return doc.get("status")
        return None
