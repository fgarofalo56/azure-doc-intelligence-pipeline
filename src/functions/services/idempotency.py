"""Idempotency service for preventing duplicate document processing.

Generates and validates idempotency keys based on document content and processing parameters.
"""

import hashlib
import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

# Processing version - increment when extraction logic changes significantly
PROCESSING_VERSION = "2.1.0"


def generate_idempotency_key(
    blob_name: str,
    model_id: str,
    pages_per_form: int | None = None,
    content_hash: str | None = None,
) -> str:
    """Generate an idempotency key for document processing.

    The key uniquely identifies a processing request based on:
    - blob_name: Source document path
    - model_id: Document Intelligence model used
    - pages_per_form: Splitting configuration
    - content_hash: Optional hash of document content (for re-uploads with same name)

    Args:
        blob_name: Blob path within container.
        model_id: Document Intelligence model ID.
        pages_per_form: Pages per form configuration.
        content_hash: Optional hash of PDF content.

    Returns:
        str: SHA256 hash truncated to 32 chars.
    """
    components = [
        blob_name,
        model_id,
        str(pages_per_form or "default"),
        PROCESSING_VERSION,
    ]

    if content_hash:
        components.append(content_hash)

    key_input = "|".join(components)
    full_hash = hashlib.sha256(key_input.encode()).hexdigest()

    # Use first 32 chars for readability while maintaining uniqueness
    return full_hash[:32]


def generate_content_hash(content: bytes) -> str:
    """Generate a hash of document content.

    Args:
        content: PDF file bytes.

    Returns:
        str: SHA256 hash of content.
    """
    return hashlib.sha256(content).hexdigest()[:16]


async def check_idempotency(
    cosmos_service: Any,
    idempotency_key: str,
    source_file: str,
) -> dict[str, Any] | None:
    """Check if a document with this idempotency key already exists.

    Args:
        cosmos_service: CosmosService instance.
        idempotency_key: Key to check.
        source_file: Source file for partition key.

    Returns:
        dict: Existing document if found and completed, None otherwise.
    """
    try:
        query = """
            SELECT * FROM c
            WHERE c.idempotencyKey = @key
            AND c.status = 'completed'
        """
        parameters = [{"name": "@key", "value": idempotency_key}]

        docs = await cosmos_service.query_documents(
            query=query,
            parameters=parameters,
            partition_key=source_file,
        )

        if docs:
            logger.info(f"Found existing completed document with idempotency key: {idempotency_key}")
            return docs[0]

        return None

    except Exception as e:
        logger.warning(f"Idempotency check failed: {e}")
        # Continue processing on error - better to duplicate than fail
        return None


def create_idempotent_document(
    base_document: dict[str, Any],
    idempotency_key: str,
    content_hash: str | None = None,
) -> dict[str, Any]:
    """Add idempotency fields to a document.

    Args:
        base_document: Document to enhance.
        idempotency_key: Generated idempotency key.
        content_hash: Optional content hash.

    Returns:
        dict: Document with idempotency fields added.
    """
    document = base_document.copy()
    document["idempotencyKey"] = idempotency_key
    document["processingVersion"] = PROCESSING_VERSION
    document["idempotencyCreatedAt"] = datetime.now(timezone.utc).isoformat()

    if content_hash:
        document["contentHash"] = content_hash

    return document


class IdempotencyResult:
    """Result of idempotency check."""

    def __init__(
        self,
        is_duplicate: bool,
        existing_document: dict[str, Any] | None = None,
        idempotency_key: str = "",
    ):
        self.is_duplicate = is_duplicate
        self.existing_document = existing_document
        self.idempotency_key = idempotency_key


async def check_and_generate_idempotency(
    cosmos_service: Any,
    blob_name: str,
    model_id: str,
    pages_per_form: int | None = None,
    content_hash: str | None = None,
) -> IdempotencyResult:
    """Check idempotency and generate key in one call.

    Args:
        cosmos_service: CosmosService instance.
        blob_name: Blob path within container.
        model_id: Document Intelligence model ID.
        pages_per_form: Pages per form configuration.
        content_hash: Optional hash of PDF content.

    Returns:
        IdempotencyResult with is_duplicate flag, existing document, and key.
    """
    # Generate key
    idempotency_key = generate_idempotency_key(
        blob_name=blob_name,
        model_id=model_id,
        pages_per_form=pages_per_form,
        content_hash=content_hash,
    )

    # Check for existing
    existing = await check_idempotency(
        cosmos_service=cosmos_service,
        idempotency_key=idempotency_key,
        source_file=blob_name,
    )

    return IdempotencyResult(
        is_duplicate=existing is not None,
        existing_document=existing,
        idempotency_key=idempotency_key,
    )
