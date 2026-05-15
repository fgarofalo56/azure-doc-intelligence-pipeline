"""Blob Storage service for SAS token generation.

Generates SAS tokens to allow Document Intelligence to access private blobs.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.parse import unquote, urlparse

from azure.storage.blob import BlobSasPermissions, BlobServiceClient, generate_blob_sas

logger = logging.getLogger(__name__)

# Maximum blob size allowed for processing (100 MB)
MAX_BLOB_SIZE_BYTES = 100 * 1024 * 1024


@dataclass
class ParsedBlobUrl:
    """Parsed components of an Azure Blob Storage URL."""

    account_name: str
    container_name: str
    blob_name: str
    original_url: str

    @property
    def base_url(self) -> str:
        """Return URL without SAS token."""
        return self.original_url.split("?")[0]


def parse_blob_url_components(blob_url: str, validate: bool = True) -> ParsedBlobUrl:
    """Parse a blob URL into its components.

    This is the single source of truth for blob URL parsing.
    URL format: https://<account>.blob.core.windows.net/<container>/<blob_path>

    Args:
        blob_url: Full blob URL (may include SAS token).
        validate: Whether to validate blob name for security issues (default True).

    Returns:
        ParsedBlobUrl: Parsed URL components.

    Raises:
        BlobServiceError: If URL is invalid or contains path traversal.
    """
    try:
        # Remove SAS token if present
        base_url = blob_url.split("?")[0]
        parsed = urlparse(base_url)

        # Validate hostname
        if not parsed.netloc or "." not in parsed.netloc:
            raise BlobServiceError(f"Invalid blob URL hostname: {parsed.netloc}")

        # Extract account name
        hostname_parts = parsed.netloc.split(".")
        account_name = hostname_parts[0]

        if not account_name:
            raise BlobServiceError(f"Could not extract account name from URL: {blob_url}")

        # Extract container and blob path
        # Path format: /<container>/<blob_path>
        path_parts = parsed.path.lstrip("/").split("/", 1)
        if len(path_parts) < 2:
            raise BlobServiceError(f"Invalid blob URL path: {parsed.path}")

        container_name = path_parts[0]
        # URL-decode the blob name to handle spaces (%20) and special chars
        blob_name = unquote(path_parts[1])

        # Security: Validate blob name for path traversal attacks
        if validate:
            validate_blob_name(blob_name)

        return ParsedBlobUrl(
            account_name=account_name,
            container_name=container_name,
            blob_name=blob_name,
            original_url=blob_url,
        )

    except BlobServiceError:
        raise
    except Exception as e:
        raise BlobServiceError(f"Failed to parse blob URL: {e}") from e


def sanitize_blob_url(blob_url: str) -> str:
    """Remove SAS token from URL for safe logging.

    Args:
        blob_url: Blob URL that may contain SAS token.

    Returns:
        str: URL without SAS token query parameters.
    """
    return blob_url.split("?")[0]


def validate_blob_name(blob_name: str) -> None:
    """Validate blob name for security issues.

    Args:
        blob_name: Blob name to validate.

    Raises:
        BlobServiceError: If blob name is invalid or contains path traversal.
    """
    if not blob_name:
        raise BlobServiceError("Blob name cannot be empty")

    if ".." in blob_name:
        raise BlobServiceError(f"Invalid blob name (path traversal detected): {blob_name}")

    if blob_name.startswith("/"):
        raise BlobServiceError(f"Invalid blob name (absolute path not allowed): {blob_name}")

    # Check for null bytes (path injection)
    if "\x00" in blob_name:
        raise BlobServiceError("Invalid blob name (null byte detected)")


class BlobServiceError(Exception):
    """Raised when blob operations fail."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


class BlobService:
    """Service for blob operations including SAS token generation."""

    def __init__(self, connection_string: str, sas_expiry_hours: int = 1) -> None:
        """Initialize Blob Service.

        Args:
            connection_string: Azure Storage connection string.
            sas_expiry_hours: Hours until SAS token expires (default 1).
        """
        self.connection_string = connection_string
        self.sas_expiry_hours = sas_expiry_hours
        self._client: BlobServiceClient | None = None

    @property
    def client(self) -> BlobServiceClient:
        """Lazy initialization of BlobServiceClient."""
        if self._client is None:
            self._client = BlobServiceClient.from_connection_string(self.connection_string)
        return self._client

    def generate_sas_url(self, blob_url: str) -> str:
        """Generate a SAS URL for a blob from a plain blob URL.

        Takes a URL like:
            https://account.blob.core.windows.net/container/path/file.pdf

        Returns a URL like:
            https://account.blob.core.windows.net/container/path/file.pdf?sv=...&sig=...

        Args:
            blob_url: Plain blob URL without SAS token.

        Returns:
            str: Blob URL with SAS token appended.

        Raises:
            BlobServiceError: If SAS generation fails.
        """
        try:
            # Parse the blob URL using shared utility
            parsed = parse_blob_url_components(blob_url)

            logger.debug(
                f"Generating SAS for account={parsed.account_name}, "
                f"container={parsed.container_name}, blob={parsed.blob_name}"
            )

            # Get account key from connection string
            account_key = self._extract_account_key()

            # Generate SAS token
            sas_token = generate_blob_sas(
                account_name=parsed.account_name,
                container_name=parsed.container_name,
                blob_name=parsed.blob_name,
                account_key=account_key,
                permission=BlobSasPermissions(read=True),
                expiry=datetime.now(timezone.utc) + timedelta(hours=self.sas_expiry_hours),
            )

            # Construct SAS URL
            sas_url = f"{parsed.base_url}?{sas_token}"
            logger.info(f"Generated SAS URL for blob: {parsed.blob_name}")

            return sas_url

        except BlobServiceError:
            raise
        except Exception as e:
            logger.exception(f"Failed to generate SAS token: {e}")
            raise BlobServiceError(f"SAS token generation failed: {e}") from e

    def _extract_account_key(self) -> str:
        """Extract account key from connection string.

        Returns:
            str: Account key.

        Raises:
            BlobServiceError: If account key not found in connection string.
        """
        # Connection string format:
        # DefaultEndpointsProtocol=https;AccountName=xxx;AccountKey=xxx;...
        parts = dict(
            part.split("=", 1) for part in self.connection_string.split(";") if "=" in part
        )

        account_key = parts.get("AccountKey")
        if not account_key:
            raise BlobServiceError(
                "AccountKey not found in connection string. "
                "Ensure STORAGE_CONNECTION_STRING contains a valid connection string."
            )

        return account_key

    def download_blob(self, blob_url: str) -> bytes:
        """Download blob content from a URL.

        Args:
            blob_url: Blob URL (with or without SAS token).

        Returns:
            bytes: Blob content.

        Raises:
            BlobServiceError: If download fails.
        """
        try:
            # Parse the blob URL using shared utility
            parsed = parse_blob_url_components(blob_url)

            logger.info(f"Downloading blob: {parsed.container_name}/{parsed.blob_name}")

            container_client = self.client.get_container_client(parsed.container_name)
            blob_client = container_client.get_blob_client(parsed.blob_name)

            blob_data = blob_client.download_blob().readall()
            logger.info(f"Downloaded {len(blob_data)} bytes")

            return blob_data

        except BlobServiceError:
            raise
        except Exception as e:
            logger.exception(f"Failed to download blob: {e}")
            raise BlobServiceError(f"Blob download failed: {e}") from e

    def upload_blob(
        self,
        container_name: str,
        blob_name: str,
        content: bytes,
        overwrite: bool = True,
    ) -> str:
        """Upload content to a blob.

        Args:
            container_name: Container name.
            blob_name: Blob name (path within container).
            content: Content to upload.
            overwrite: Whether to overwrite if exists (default True).

        Returns:
            str: Full blob URL.

        Raises:
            BlobServiceError: If upload fails.
        """
        try:
            logger.info(f"Uploading blob: {container_name}/{blob_name}")

            container_client = self.client.get_container_client(container_name)
            blob_client = container_client.get_blob_client(blob_name)

            blob_client.upload_blob(content, overwrite=overwrite)

            blob_url = blob_client.url
            logger.info(f"Uploaded blob: {blob_url}")

            return blob_url

        except Exception as e:
            logger.exception(f"Failed to upload blob: {e}")
            raise BlobServiceError(f"Blob upload failed: {e}") from e

    def delete_blob(self, container_name: str, blob_name: str) -> None:
        """Delete a blob.

        Args:
            container_name: Container name.
            blob_name: Blob name.

        Raises:
            BlobServiceError: If delete fails.
        """
        try:
            logger.info(f"Deleting blob: {container_name}/{blob_name}")

            container_client = self.client.get_container_client(container_name)
            blob_client = container_client.get_blob_client(blob_name)

            blob_client.delete_blob()
            logger.info(f"Deleted blob: {blob_name}")

        except Exception as e:
            logger.exception(f"Failed to delete blob: {e}")
            raise BlobServiceError(f"Blob delete failed: {e}") from e

    def parse_blob_url(self, blob_url: str) -> tuple[str, str]:
        """Parse blob URL into container and blob name.

        Args:
            blob_url: Full blob URL.

        Returns:
            tuple: (container_name, blob_name) - blob_name is URL-decoded and validated

        Raises:
            BlobServiceError: If URL is invalid or contains path traversal.
        """
        # Use shared utility for consistent parsing
        parsed = parse_blob_url_components(blob_url)
        return parsed.container_name, parsed.blob_name

    def list_blobs(
        self,
        container_name: str,
        prefix: str | None = None,
    ) -> list[str]:
        """List blobs in a container with optional prefix filter.

        Args:
            container_name: Container name.
            prefix: Optional blob name prefix filter.

        Returns:
            list[str]: List of blob names.

        Raises:
            BlobServiceError: If list operation fails.
        """
        try:
            container_client = self.client.get_container_client(container_name)
            blobs = container_client.list_blobs(name_starts_with=prefix)
            return [blob.name for blob in blobs]

        except Exception as e:
            logger.exception(f"Failed to list blobs: {e}")
            raise BlobServiceError(f"Blob list failed: {e}") from e

    def move_blob(
        self,
        source_container: str,
        source_blob: str,
        dest_container: str,
        dest_blob: str | None = None,
    ) -> str:
        """Move a blob from one location to another.

        Args:
            source_container: Source container name.
            source_blob: Source blob name.
            dest_container: Destination container name.
            dest_blob: Destination blob name (defaults to source name).

        Returns:
            str: Destination blob URL.

        Raises:
            BlobServiceError: If move operation fails.
        """
        try:
            dest_blob = dest_blob or source_blob

            # Get source blob
            source_container_client = self.client.get_container_client(source_container)
            source_blob_client = source_container_client.get_blob_client(source_blob)

            # Create destination container if needed
            dest_container_client = self.client.get_container_client(dest_container)
            try:
                dest_container_client.create_container()
            except Exception:
                pass  # Container may already exist

            # Copy to destination
            dest_blob_client = dest_container_client.get_blob_client(dest_blob)
            dest_blob_client.start_copy_from_url(source_blob_client.url)

            # Delete source
            source_blob_client.delete_blob()

            logger.info(
                f"Moved blob from {source_container}/{source_blob} to {dest_container}/{dest_blob}"
            )
            return dest_blob_client.url

        except Exception as e:
            logger.exception(f"Failed to move blob: {e}")
            raise BlobServiceError(f"Blob move failed: {e}") from e

    def blob_exists(self, container_name: str, blob_name: str) -> bool:
        """Check if a blob exists.

        Args:
            container_name: Container name.
            blob_name: Blob name.

        Returns:
            bool: True if blob exists.
        """
        try:
            container_client = self.client.get_container_client(container_name)
            blob_client = container_client.get_blob_client(blob_name)
            return blob_client.exists()
        except Exception:
            return False
