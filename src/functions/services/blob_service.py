"""Blob Storage service for SAS token generation.

Generates SAS tokens to allow Document Intelligence to access private blobs.
"""

import logging
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

from azure.storage.blob import BlobSasPermissions, BlobServiceClient, generate_blob_sas

logger = logging.getLogger(__name__)


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
            self._client = BlobServiceClient.from_connection_string(
                self.connection_string
            )
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
            # Parse the blob URL
            parsed = urlparse(blob_url)

            # Extract account name from URL
            # URL format: https://<account>.blob.core.windows.net/<container>/<blob>
            hostname_parts = parsed.netloc.split(".")
            if len(hostname_parts) < 1:
                raise BlobServiceError(f"Invalid blob URL hostname: {parsed.netloc}")

            account_name = hostname_parts[0]

            # Extract container and blob path
            # Path format: /<container>/<blob_path>
            path_parts = parsed.path.lstrip("/").split("/", 1)
            if len(path_parts) < 2:
                raise BlobServiceError(f"Invalid blob URL path: {parsed.path}")

            container_name = path_parts[0]
            blob_name = path_parts[1]

            logger.debug(
                f"Generating SAS for account={account_name}, "
                f"container={container_name}, blob={blob_name}"
            )

            # Get account key from connection string
            account_key = self._extract_account_key()

            # Generate SAS token
            sas_token = generate_blob_sas(
                account_name=account_name,
                container_name=container_name,
                blob_name=blob_name,
                account_key=account_key,
                permission=BlobSasPermissions(read=True),
                expiry=datetime.now(timezone.utc)
                + timedelta(hours=self.sas_expiry_hours),
            )

            # Construct SAS URL
            sas_url = f"{blob_url}?{sas_token}"
            logger.info(f"Generated SAS URL for blob: {blob_name}")

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
            # Parse the blob URL
            parsed = urlparse(blob_url.split("?")[0])  # Remove SAS token if present

            # Extract container and blob path
            path_parts = parsed.path.lstrip("/").split("/", 1)
            if len(path_parts) < 2:
                raise BlobServiceError(f"Invalid blob URL path: {parsed.path}")

            container_name = path_parts[0]
            blob_name = path_parts[1]

            logger.info(f"Downloading blob: {container_name}/{blob_name}")

            container_client = self.client.get_container_client(container_name)
            blob_client = container_client.get_blob_client(blob_name)

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
            tuple: (container_name, blob_name)

        Raises:
            BlobServiceError: If URL is invalid.
        """
        try:
            parsed = urlparse(blob_url.split("?")[0])  # Remove SAS token if present
            path_parts = parsed.path.lstrip("/").split("/", 1)

            if len(path_parts) < 2:
                raise BlobServiceError(f"Invalid blob URL path: {parsed.path}")

            return path_parts[0], path_parts[1]

        except BlobServiceError:
            raise
        except Exception as e:
            raise BlobServiceError(f"Failed to parse blob URL: {e}") from e
