"""Integration tests for Blob Storage service.

Tests actual Azure Blob Storage operations including:
- SAS URL generation
- Blob upload/download
- Blob listing and deletion
- URL parsing

Requires STORAGE_CONNECTION_STRING environment variable.
"""

import os
from uuid import uuid4

import pytest

# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def blob_service():
    """Create BlobService with real credentials."""
    connection_string = os.environ.get("STORAGE_CONNECTION_STRING")
    if not connection_string:
        pytest.skip("STORAGE_CONNECTION_STRING not set")

    from services.blob_service import BlobService

    return BlobService(connection_string=connection_string)


@pytest.fixture(scope="module")
def test_container():
    """Test container name for integration tests."""
    return os.environ.get("STORAGE_CONTAINER", "integration-tests")


@pytest.fixture
def test_blob_name():
    """Generate unique blob name for test isolation."""
    return f"test-blob-{uuid4().hex[:8]}.txt"


@pytest.fixture
def test_pdf_content():
    """Sample PDF-like content for testing."""
    # Minimal valid PDF structure
    return b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF"


class TestBlobUploadDownload:
    """Tests for blob upload and download operations."""

    def test_upload_and_download_blob(
        self, blob_service, test_container, test_blob_name
    ):
        """Test uploading and downloading a blob."""
        content = b"Test content for integration test"

        # Upload
        blob_url = blob_service.upload_blob(
            container_name=test_container,
            blob_name=test_blob_name,
            content=content,
        )

        assert blob_url is not None
        assert test_blob_name in blob_url

        # Download
        downloaded = blob_service.download_blob(blob_url)
        assert downloaded == content

        # Cleanup
        blob_service.delete_blob(test_container, test_blob_name)

    def test_upload_large_blob(
        self, blob_service, test_container, test_blob_name
    ):
        """Test uploading a larger blob (simulating PDF size)."""
        # 1MB of data
        content = b"x" * (1024 * 1024)

        blob_url = blob_service.upload_blob(
            container_name=test_container,
            blob_name=test_blob_name,
            content=content,
        )

        assert blob_url is not None

        # Verify download
        downloaded = blob_service.download_blob(blob_url)
        assert len(downloaded) == len(content)

        # Cleanup
        blob_service.delete_blob(test_container, test_blob_name)

    def test_upload_overwrite(
        self, blob_service, test_container, test_blob_name
    ):
        """Test overwriting an existing blob."""
        content1 = b"Original content"
        content2 = b"Updated content"

        # Upload original
        blob_service.upload_blob(
            container_name=test_container,
            blob_name=test_blob_name,
            content=content1,
        )

        # Overwrite
        blob_url = blob_service.upload_blob(
            container_name=test_container,
            blob_name=test_blob_name,
            content=content2,
            overwrite=True,
        )

        # Verify updated content
        downloaded = blob_service.download_blob(blob_url)
        assert downloaded == content2

        # Cleanup
        blob_service.delete_blob(test_container, test_blob_name)


class TestSASGeneration:
    """Tests for SAS URL generation."""

    def test_generate_sas_url(
        self, blob_service, test_container, test_blob_name
    ):
        """Test SAS URL generation for an existing blob."""
        content = b"Test content for SAS generation"

        # Upload blob
        blob_url = blob_service.upload_blob(
            container_name=test_container,
            blob_name=test_blob_name,
            content=content,
        )

        # Generate SAS URL
        sas_url = blob_service.generate_sas_url(blob_url)

        assert "?" in sas_url
        assert "sig=" in sas_url
        assert "sv=" in sas_url
        assert "se=" in sas_url

        # Cleanup
        blob_service.delete_blob(test_container, test_blob_name)

    def test_sas_url_allows_read_access(
        self, blob_service, test_container, test_blob_name
    ):
        """Test that generated SAS URL allows read access."""
        import httpx

        content = b"Test content for SAS read access"

        # Upload blob
        blob_url = blob_service.upload_blob(
            container_name=test_container,
            blob_name=test_blob_name,
            content=content,
        )

        # Generate SAS URL
        sas_url = blob_service.generate_sas_url(blob_url)

        # Access blob using SAS URL directly (without SDK)
        response = httpx.get(sas_url)
        assert response.status_code == 200
        assert response.content == content

        # Cleanup
        blob_service.delete_blob(test_container, test_blob_name)

    def test_generate_sas_url_with_special_characters(
        self, blob_service, test_container
    ):
        """Test SAS URL generation for blob with special characters in name."""
        blob_name = f"test folder/test file {uuid4().hex[:8]}.txt"
        content = b"Content with special chars in path"

        # Upload blob
        blob_url = blob_service.upload_blob(
            container_name=test_container,
            blob_name=blob_name,
            content=content,
        )

        # Generate SAS URL
        sas_url = blob_service.generate_sas_url(blob_url)

        # Verify it works
        downloaded = blob_service.download_blob(sas_url)
        assert downloaded == content

        # Cleanup
        blob_service.delete_blob(test_container, blob_name)


class TestBlobListing:
    """Tests for blob listing operations."""

    def test_list_blobs(self, blob_service, test_container):
        """Test listing blobs in a container."""
        prefix = f"list-test-{uuid4().hex[:8]}"
        blob_names = [f"{prefix}/file1.txt", f"{prefix}/file2.txt"]

        # Upload test blobs
        for name in blob_names:
            blob_service.upload_blob(
                container_name=test_container,
                blob_name=name,
                content=b"test",
            )

        # List blobs with prefix
        blobs = blob_service.list_blobs(test_container, prefix=prefix)

        assert len(blobs) >= 2
        for name in blob_names:
            assert name in blobs

        # Cleanup
        for name in blob_names:
            blob_service.delete_blob(test_container, name)

    def test_list_blobs_empty_prefix(self, blob_service, test_container):
        """Test listing blobs with empty prefix returns all blobs."""
        blobs = blob_service.list_blobs(test_container)
        assert isinstance(blobs, list)


class TestBlobExistence:
    """Tests for blob existence checks."""

    def test_blob_exists_true(
        self, blob_service, test_container, test_blob_name
    ):
        """Test blob_exists returns True for existing blob."""
        blob_service.upload_blob(
            container_name=test_container,
            blob_name=test_blob_name,
            content=b"test",
        )

        assert blob_service.blob_exists(test_container, test_blob_name) is True

        # Cleanup
        blob_service.delete_blob(test_container, test_blob_name)

    def test_blob_exists_false(self, blob_service, test_container):
        """Test blob_exists returns False for non-existing blob."""
        assert blob_service.blob_exists(test_container, "nonexistent.txt") is False


class TestBlobDeletion:
    """Tests for blob deletion operations."""

    def test_delete_blob(
        self, blob_service, test_container, test_blob_name
    ):
        """Test deleting a blob."""
        blob_service.upload_blob(
            container_name=test_container,
            blob_name=test_blob_name,
            content=b"test",
        )

        # Verify exists
        assert blob_service.blob_exists(test_container, test_blob_name) is True

        # Delete
        blob_service.delete_blob(test_container, test_blob_name)

        # Verify deleted
        assert blob_service.blob_exists(test_container, test_blob_name) is False


class TestBlobMove:
    """Tests for blob move operations."""

    def test_move_blob_same_container(
        self, blob_service, test_container, test_blob_name
    ):
        """Test moving blob within same container."""
        dest_name = f"moved-{test_blob_name}"
        content = b"Test content to move"

        # Upload original
        blob_service.upload_blob(
            container_name=test_container,
            blob_name=test_blob_name,
            content=content,
        )

        # Move
        dest_url = blob_service.move_blob(
            source_container=test_container,
            source_blob=test_blob_name,
            dest_container=test_container,
            dest_blob=dest_name,
        )

        assert dest_name in dest_url

        # Verify source deleted
        assert blob_service.blob_exists(test_container, test_blob_name) is False

        # Verify destination exists with same content
        downloaded = blob_service.download_blob(dest_url)
        assert downloaded == content

        # Cleanup
        blob_service.delete_blob(test_container, dest_name)


class TestURLParsing:
    """Tests for blob URL parsing."""

    def test_parse_blob_url(
        self, blob_service, test_container, test_blob_name
    ):
        """Test parsing blob URL into container and blob name."""
        # Upload to get a real URL
        blob_url = blob_service.upload_blob(
            container_name=test_container,
            blob_name=test_blob_name,
            content=b"test",
        )

        container, blob_name = blob_service.parse_blob_url(blob_url)

        assert container == test_container
        assert blob_name == test_blob_name

        # Cleanup
        blob_service.delete_blob(test_container, test_blob_name)

    def test_parse_blob_url_with_sas(
        self, blob_service, test_container, test_blob_name
    ):
        """Test parsing blob URL that includes SAS token."""
        blob_url = blob_service.upload_blob(
            container_name=test_container,
            blob_name=test_blob_name,
            content=b"test",
        )

        sas_url = blob_service.generate_sas_url(blob_url)

        container, blob_name = blob_service.parse_blob_url(sas_url)

        assert container == test_container
        assert blob_name == test_blob_name

        # Cleanup
        blob_service.delete_blob(test_container, test_blob_name)

    def test_parse_blob_url_with_encoded_spaces(
        self, blob_service, test_container
    ):
        """Test parsing URL with URL-encoded spaces."""
        original_name = f"test folder/test file {uuid4().hex[:8]}.txt"

        blob_url = blob_service.upload_blob(
            container_name=test_container,
            blob_name=original_name,
            content=b"test",
        )

        container, blob_name = blob_service.parse_blob_url(blob_url)

        assert container == test_container
        assert blob_name == original_name  # Should be decoded

        # Cleanup
        blob_service.delete_blob(test_container, original_name)
