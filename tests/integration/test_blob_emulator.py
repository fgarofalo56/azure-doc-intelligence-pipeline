"""Emulator-based tests for Blob Storage service.

These tests run against Azurite (Azure Storage Emulator) for CI-friendly
integration testing without requiring real Azure resources.

To run these tests:
1. Start Azurite: docker compose up azurite -d
2. Run tests: RUN_EMULATOR_TESTS=1 uv run pytest tests/integration/test_blob_emulator.py -v
"""

from uuid import uuid4

import pytest

# Mark all tests in this module as emulator tests
pytestmark = pytest.mark.emulator


class TestBlobEmulatorBasicOperations:
    """Basic blob operations using Azurite emulator."""

    def test_upload_and_download_blob(self, azurite_blob_service, azurite_test_container):
        """Test uploading and downloading a blob via emulator."""
        blob_name = f"test-blob-{uuid4().hex[:8]}.txt"
        content = b"Test content for emulator integration test"

        # Upload
        blob_url = azurite_blob_service.upload_blob(
            container_name=azurite_test_container,
            blob_name=blob_name,
            content=content,
        )

        assert blob_url is not None
        assert blob_name in blob_url
        assert "devstoreaccount1" in blob_url  # Azurite account name

        # Download
        downloaded = azurite_blob_service.download_blob(blob_url)
        assert downloaded == content

        # Cleanup
        azurite_blob_service.delete_blob(azurite_test_container, blob_name)

    def test_upload_pdf_content(self, azurite_blob_service, azurite_test_container):
        """Test uploading PDF-like content (binary)."""
        blob_name = f"test-document-{uuid4().hex[:8]}.pdf"
        # Minimal valid PDF structure
        pdf_content = (
            b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF"
        )

        blob_url = azurite_blob_service.upload_blob(
            container_name=azurite_test_container,
            blob_name=blob_name,
            content=pdf_content,
        )

        assert blob_url is not None

        downloaded = azurite_blob_service.download_blob(blob_url)
        assert downloaded == pdf_content

        # Cleanup
        azurite_blob_service.delete_blob(azurite_test_container, blob_name)

    def test_upload_to_subfolder(self, azurite_blob_service, azurite_test_container):
        """Test uploading to a virtual folder path."""
        folder_path = f"incoming/{uuid4().hex[:8]}"
        blob_name = f"{folder_path}/document.pdf"
        content = b"Subfolder test content"

        blob_url = azurite_blob_service.upload_blob(
            container_name=azurite_test_container,
            blob_name=blob_name,
            content=content,
        )

        assert folder_path in blob_url

        downloaded = azurite_blob_service.download_blob(blob_url)
        assert downloaded == content

        # Cleanup
        azurite_blob_service.delete_blob(azurite_test_container, blob_name)


class TestBlobEmulatorSASOperations:
    """SAS URL generation tests using Azurite emulator."""

    def test_generate_sas_url(self, azurite_blob_service, azurite_test_container):
        """Test SAS URL generation for emulator blob."""
        blob_name = f"sas-test-{uuid4().hex[:8]}.txt"
        content = b"SAS test content"

        # Upload
        blob_url = azurite_blob_service.upload_blob(
            container_name=azurite_test_container,
            blob_name=blob_name,
            content=content,
        )

        # Generate SAS URL
        sas_url = azurite_blob_service.generate_sas_url(blob_url)

        assert "?" in sas_url
        assert "sig=" in sas_url
        assert "sv=" in sas_url
        assert "se=" in sas_url

        # Cleanup
        azurite_blob_service.delete_blob(azurite_test_container, blob_name)

    def test_sas_url_accessible(self, azurite_blob_service, azurite_test_container):
        """Test that SAS URL allows access to blob content."""
        import httpx

        blob_name = f"sas-access-{uuid4().hex[:8]}.txt"
        content = b"SAS access test content"

        # Upload
        blob_url = azurite_blob_service.upload_blob(
            container_name=azurite_test_container,
            blob_name=blob_name,
            content=content,
        )

        # Generate SAS URL
        sas_url = azurite_blob_service.generate_sas_url(blob_url)

        # Access via HTTP directly (using SAS URL)
        response = httpx.get(sas_url)
        assert response.status_code == 200
        assert response.content == content

        # Cleanup
        azurite_blob_service.delete_blob(azurite_test_container, blob_name)


class TestBlobEmulatorListOperations:
    """Blob listing tests using Azurite emulator."""

    def test_list_blobs(self, azurite_blob_service, azurite_test_container):
        """Test listing blobs in a container."""
        prefix = f"list-test-{uuid4().hex[:8]}"
        blob_names = [f"{prefix}/file1.txt", f"{prefix}/file2.txt", f"{prefix}/file3.txt"]

        # Upload test blobs
        for name in blob_names:
            azurite_blob_service.upload_blob(
                container_name=azurite_test_container,
                blob_name=name,
                content=b"test content",
            )

        # List blobs with prefix
        listed = azurite_blob_service.list_blobs(azurite_test_container, prefix=prefix)

        assert len(listed) == 3
        for name in blob_names:
            assert name in listed

        # Cleanup
        for name in blob_names:
            azurite_blob_service.delete_blob(azurite_test_container, name)

    def test_list_blobs_empty_result(self, azurite_blob_service, azurite_test_container):
        """Test listing blobs with a prefix that matches nothing."""
        listed = azurite_blob_service.list_blobs(
            azurite_test_container, prefix=f"nonexistent-{uuid4().hex}"
        )
        assert listed == []


class TestBlobEmulatorExistenceAndDeletion:
    """Blob existence and deletion tests using Azurite emulator."""

    def test_blob_exists(self, azurite_blob_service, azurite_test_container):
        """Test checking if a blob exists."""
        blob_name = f"exists-test-{uuid4().hex[:8]}.txt"

        # Should not exist initially
        assert azurite_blob_service.blob_exists(azurite_test_container, blob_name) is False

        # Upload
        azurite_blob_service.upload_blob(
            container_name=azurite_test_container,
            blob_name=blob_name,
            content=b"test",
        )

        # Should exist now
        assert azurite_blob_service.blob_exists(azurite_test_container, blob_name) is True

        # Cleanup
        azurite_blob_service.delete_blob(azurite_test_container, blob_name)

        # Should not exist after deletion
        assert azurite_blob_service.blob_exists(azurite_test_container, blob_name) is False

    def test_delete_nonexistent_blob(self, azurite_blob_service, azurite_test_container):
        """Test deleting a blob that doesn't exist (should not raise)."""
        # This should not raise an exception
        azurite_blob_service.delete_blob(azurite_test_container, f"nonexistent-{uuid4().hex}.txt")


class TestBlobEmulatorMoveOperations:
    """Blob move/copy tests using Azurite emulator."""

    def test_move_blob(self, azurite_blob_service, azurite_test_container):
        """Test moving a blob to a new location."""
        source_name = f"source-{uuid4().hex[:8]}.txt"
        dest_name = f"moved/{uuid4().hex[:8]}.txt"
        content = b"Content to move"

        # Upload source
        azurite_blob_service.upload_blob(
            container_name=azurite_test_container,
            blob_name=source_name,
            content=content,
        )

        # Move
        dest_url = azurite_blob_service.move_blob(
            source_container=azurite_test_container,
            source_blob=source_name,
            dest_container=azurite_test_container,
            dest_blob=dest_name,
        )

        assert dest_name in dest_url

        # Verify source deleted
        assert azurite_blob_service.blob_exists(azurite_test_container, source_name) is False

        # Verify destination exists with correct content
        downloaded = azurite_blob_service.download_blob(dest_url)
        assert downloaded == content

        # Cleanup
        azurite_blob_service.delete_blob(azurite_test_container, dest_name)


class TestBlobEmulatorURLParsing:
    """URL parsing tests using Azurite URLs."""

    def test_parse_emulator_url(self, azurite_blob_service, azurite_test_container):
        """Test parsing an Azurite blob URL."""
        blob_name = f"parse-test-{uuid4().hex[:8]}.txt"

        blob_url = azurite_blob_service.upload_blob(
            container_name=azurite_test_container,
            blob_name=blob_name,
            content=b"test",
        )

        container, parsed_name = azurite_blob_service.parse_blob_url(blob_url)

        assert container == azurite_test_container
        assert parsed_name == blob_name

        # Cleanup
        azurite_blob_service.delete_blob(azurite_test_container, blob_name)

    def test_parse_emulator_url_with_spaces(self, azurite_blob_service, azurite_test_container):
        """Test parsing URL with spaces in blob name."""
        blob_name = f"folder with spaces/file {uuid4().hex[:8]}.txt"

        blob_url = azurite_blob_service.upload_blob(
            container_name=azurite_test_container,
            blob_name=blob_name,
            content=b"test",
        )

        container, parsed_name = azurite_blob_service.parse_blob_url(blob_url)

        assert container == azurite_test_container
        assert parsed_name == blob_name  # Should be decoded

        # Cleanup
        azurite_blob_service.delete_blob(azurite_test_container, blob_name)
