"""Unit tests for the blob service."""

from unittest.mock import MagicMock, patch

import pytest


class TestParsedBlobUrl:
    """Tests for ParsedBlobUrl dataclass."""

    def test_dataclass_creation(self):
        """Test creating ParsedBlobUrl instance."""
        from src.functions.services.blob_service import ParsedBlobUrl

        parsed = ParsedBlobUrl(
            account_name="storage",
            container_name="pdfs",
            blob_name="folder/file.pdf",
            original_url="https://storage.blob.core.windows.net/pdfs/folder/file.pdf?sv=2021",
        )

        assert parsed.account_name == "storage"
        assert parsed.container_name == "pdfs"
        assert parsed.blob_name == "folder/file.pdf"

    def test_base_url_property(self):
        """Test base_url property removes SAS token."""
        from src.functions.services.blob_service import ParsedBlobUrl

        parsed = ParsedBlobUrl(
            account_name="storage",
            container_name="pdfs",
            blob_name="file.pdf",
            original_url="https://storage.blob.core.windows.net/pdfs/file.pdf?sv=2021&sig=xxx",
        )

        assert parsed.base_url == "https://storage.blob.core.windows.net/pdfs/file.pdf"

    def test_base_url_property_no_sas(self):
        """Test base_url property when no SAS token."""
        from src.functions.services.blob_service import ParsedBlobUrl

        parsed = ParsedBlobUrl(
            account_name="storage",
            container_name="pdfs",
            blob_name="file.pdf",
            original_url="https://storage.blob.core.windows.net/pdfs/file.pdf",
        )

        assert parsed.base_url == "https://storage.blob.core.windows.net/pdfs/file.pdf"


class TestParseBlobUrlComponents:
    """Tests for parse_blob_url_components function."""

    def test_parse_basic_url(self):
        """Test parsing a basic blob URL."""
        from src.functions.services.blob_service import parse_blob_url_components

        result = parse_blob_url_components(
            "https://myaccount.blob.core.windows.net/container/folder/file.pdf"
        )

        assert result.account_name == "myaccount"
        assert result.container_name == "container"
        assert result.blob_name == "folder/file.pdf"

    def test_parse_url_with_sas_token(self):
        """Test parsing URL with SAS token."""
        from src.functions.services.blob_service import parse_blob_url_components

        result = parse_blob_url_components(
            "https://myaccount.blob.core.windows.net/container/file.pdf?sv=2021-06-08&sig=xxx"
        )

        assert result.account_name == "myaccount"
        assert result.blob_name == "file.pdf"

    def test_parse_url_with_encoded_spaces(self):
        """Test parsing URL with URL-encoded spaces."""
        from src.functions.services.blob_service import parse_blob_url_components

        result = parse_blob_url_components(
            "https://myaccount.blob.core.windows.net/container/my%20document.pdf"
        )

        assert result.blob_name == "my document.pdf"

    def test_parse_url_with_encoded_special_chars(self):
        """Test parsing URL with URL-encoded special characters."""
        from src.functions.services.blob_service import parse_blob_url_components

        result = parse_blob_url_components(
            "https://myaccount.blob.core.windows.net/container/file%28copy%29.pdf"
        )

        assert result.blob_name == "file(copy).pdf"

    def test_parse_url_invalid_hostname(self):
        """Test error on invalid hostname."""
        from src.functions.services.blob_service import BlobServiceError, parse_blob_url_components

        with pytest.raises(BlobServiceError) as exc:
            parse_blob_url_components("https://localhost/container/file.pdf")

        assert "Invalid blob URL hostname" in str(exc.value)

    def test_parse_url_invalid_path(self):
        """Test error on invalid path (no blob name)."""
        from src.functions.services.blob_service import BlobServiceError, parse_blob_url_components

        with pytest.raises(BlobServiceError) as exc:
            parse_blob_url_components("https://myaccount.blob.core.windows.net/container")

        assert "Invalid blob URL path" in str(exc.value)

    def test_parse_url_path_traversal(self):
        """Test error on path traversal attempt."""
        from src.functions.services.blob_service import BlobServiceError, parse_blob_url_components

        with pytest.raises(BlobServiceError) as exc:
            parse_blob_url_components(
                "https://myaccount.blob.core.windows.net/container/../../../etc/passwd"
            )

        assert "path traversal" in str(exc.value).lower()

    def test_parse_url_skip_validation(self):
        """Test skipping blob name validation."""
        from src.functions.services.blob_service import parse_blob_url_components

        # This would normally fail validation, but with validate=False it passes
        result = parse_blob_url_components(
            "https://myaccount.blob.core.windows.net/container/../etc/passwd",
            validate=False,
        )

        assert "../etc/passwd" in result.blob_name

    def test_parse_url_generic_error(self):
        """Test handling of generic exceptions."""
        from src.functions.services.blob_service import BlobServiceError, parse_blob_url_components

        with patch("src.functions.services.blob_service.urlparse") as mock_urlparse:
            mock_urlparse.side_effect = RuntimeError("Unexpected error")

            with pytest.raises(BlobServiceError) as exc:
                parse_blob_url_components("https://test.blob.core.windows.net/c/b")

            assert "Failed to parse blob URL" in str(exc.value)


class TestSanitizeBlobUrl:
    """Tests for sanitize_blob_url function."""

    def test_sanitize_url_with_sas_token(self):
        """Test removing SAS token from URL."""
        from src.functions.services.blob_service import sanitize_blob_url

        url = "https://storage.blob.core.windows.net/container/file.pdf?sv=2021-06-08&sig=abc123"
        result = sanitize_blob_url(url)
        assert result == "https://storage.blob.core.windows.net/container/file.pdf"

    def test_sanitize_url_without_sas_token(self):
        """Test URL without SAS token remains unchanged."""
        from src.functions.services.blob_service import sanitize_blob_url

        url = "https://storage.blob.core.windows.net/container/file.pdf"
        result = sanitize_blob_url(url)
        assert result == "https://storage.blob.core.windows.net/container/file.pdf"


class TestValidateBlobName:
    """Tests for validate_blob_name function."""

    def test_valid_blob_name(self):
        """Test valid blob name passes validation."""
        from src.functions.services.blob_service import validate_blob_name

        # Should not raise
        validate_blob_name("folder/subfolder/file.pdf")

    def test_empty_blob_name_raises(self):
        """Test empty blob name raises error."""
        from src.functions.services.blob_service import BlobServiceError, validate_blob_name

        with pytest.raises(BlobServiceError) as exc_info:
            validate_blob_name("")
        assert "cannot be empty" in str(exc_info.value)

    def test_path_traversal_double_dot_raises(self):
        """Test path traversal with .. raises error."""
        from src.functions.services.blob_service import BlobServiceError, validate_blob_name

        with pytest.raises(BlobServiceError) as exc_info:
            validate_blob_name("folder/../../../etc/passwd")
        assert "path traversal" in str(exc_info.value).lower()

    def test_absolute_path_raises(self):
        """Test absolute path raises error."""
        from src.functions.services.blob_service import BlobServiceError, validate_blob_name

        with pytest.raises(BlobServiceError) as exc_info:
            validate_blob_name("/etc/passwd")
        assert "absolute path" in str(exc_info.value).lower()

    def test_null_byte_raises(self):
        """Test null byte injection raises error."""
        from src.functions.services.blob_service import BlobServiceError, validate_blob_name

        with pytest.raises(BlobServiceError) as exc_info:
            validate_blob_name("file.pdf\x00.txt")
        assert "null byte" in str(exc_info.value).lower()


class TestBlobServiceError:
    """Tests for BlobServiceError exception."""

    def test_error_creation(self):
        """Test BlobServiceError creation."""
        from src.functions.services.blob_service import BlobServiceError

        error = BlobServiceError("Test error")

        assert error.reason == "Test error"
        assert "Test error" in str(error)


class TestBlobService:
    """Tests for BlobService class."""

    @pytest.fixture
    def connection_string(self):
        """Return a mock connection string."""
        return "DefaultEndpointsProtocol=https;AccountName=teststorage;AccountKey=dGVzdGtleQ==;EndpointSuffix=core.windows.net"

    @pytest.fixture
    def blob_service(self, connection_string):
        """Create a BlobService instance."""
        from src.functions.services.blob_service import BlobService

        return BlobService(connection_string=connection_string)

    def test_init(self, blob_service):
        """Test initialization."""
        assert blob_service.sas_expiry_hours == 1
        assert blob_service._client is None

    def test_client_lazy_init(self, blob_service):
        """Test lazy initialization of client."""
        with patch(
            "src.functions.services.blob_service.BlobServiceClient.from_connection_string"
        ) as mock_from_conn:
            mock_client = MagicMock()
            mock_from_conn.return_value = mock_client

            # First access creates client
            client1 = blob_service.client
            assert client1 is mock_client
            mock_from_conn.assert_called_once()

            # Second access returns same client
            client2 = blob_service.client
            assert client2 is client1
            mock_from_conn.assert_called_once()  # Not called again

    def test_extract_account_key(self, blob_service):
        """Test extracting account key from connection string."""
        key = blob_service._extract_account_key()
        assert key == "dGVzdGtleQ=="

    def test_extract_account_key_missing(self):
        """Test error when account key is missing."""
        from src.functions.services.blob_service import BlobService, BlobServiceError

        service = BlobService(connection_string="DefaultEndpointsProtocol=https")

        with pytest.raises(BlobServiceError) as exc:
            service._extract_account_key()

        assert "AccountKey not found" in str(exc.value)

    def test_parse_blob_url(self, blob_service):
        """Test parsing blob URL."""
        url = "https://teststorage.blob.core.windows.net/pdfs/incoming/test.pdf"
        container, blob_name = blob_service.parse_blob_url(url)

        assert container == "pdfs"
        assert blob_name == "incoming/test.pdf"

    def test_parse_blob_url_with_sas(self, blob_service):
        """Test parsing blob URL with SAS token."""
        url = "https://teststorage.blob.core.windows.net/pdfs/test.pdf?sv=2021-06-08&sig=xxx"
        container, blob_name = blob_service.parse_blob_url(url)

        assert container == "pdfs"
        assert blob_name == "test.pdf"

    def test_parse_blob_url_with_spaces(self, blob_service):
        """Test parsing URL with URL-encoded spaces."""
        url = "https://teststorage.blob.core.windows.net/pdfs/my%20document.pdf"
        container, blob_name = blob_service.parse_blob_url(url)

        assert container == "pdfs"
        assert blob_name == "my document.pdf"  # Decoded

    def test_parse_blob_url_invalid(self, blob_service):
        """Test error on invalid blob URL."""
        from src.functions.services.blob_service import BlobServiceError

        url = "https://teststorage.blob.core.windows.net/container"  # No blob path

        with pytest.raises(BlobServiceError) as exc:
            blob_service.parse_blob_url(url)

        assert "Invalid blob URL" in str(exc.value)

    def test_parse_blob_url_invalid_hostname(self, blob_service):
        """Test error on invalid hostname without dots."""
        from src.functions.services.blob_service import BlobServiceError

        url = "https://localhost/container/blob.pdf"  # No dots in hostname

        with pytest.raises(BlobServiceError) as exc:
            blob_service.parse_blob_url(url)

        assert "Invalid blob URL hostname" in str(exc.value)

    def test_parse_blob_url_path_traversal(self, blob_service):
        """Test error on path traversal attempt."""
        from src.functions.services.blob_service import BlobServiceError

        url = "https://storage.blob.core.windows.net/container/../../../etc/passwd"

        with pytest.raises(BlobServiceError) as exc:
            blob_service.parse_blob_url(url)

        assert "path traversal" in str(exc.value).lower()

    def test_parse_blob_url_generic_error(self, blob_service):
        """Test parse_blob_url handles generic exceptions."""
        from src.functions.services.blob_service import BlobServiceError

        with patch("src.functions.services.blob_service.urlparse") as mock_urlparse:
            mock_urlparse.side_effect = RuntimeError("Parse error")

            with pytest.raises(BlobServiceError) as exc:
                blob_service.parse_blob_url("https://test.blob.core.windows.net/c/b")

            assert "Failed to parse blob URL" in str(exc.value)

    def test_generate_sas_url(self, blob_service):
        """Test SAS URL generation."""
        with patch("src.functions.services.blob_service.generate_blob_sas") as mock_gen_sas:
            mock_gen_sas.return_value = "sv=2021&sig=xxx"

            url = "https://teststorage.blob.core.windows.net/pdfs/test.pdf"
            sas_url = blob_service.generate_sas_url(url)

            assert sas_url == f"{url}?sv=2021&sig=xxx"
            mock_gen_sas.assert_called_once()

    def test_generate_sas_url_invalid_path(self, blob_service):
        """Test SAS URL generation with invalid path (no blob name)."""
        from src.functions.services.blob_service import BlobServiceError

        # URL with container only, no blob path
        url = "https://teststorage.blob.core.windows.net/container"

        with pytest.raises(BlobServiceError) as exc:
            blob_service.generate_sas_url(url)

        assert "Invalid blob URL" in str(exc.value)

    def test_generate_sas_url_generic_error(self, blob_service):
        """Test SAS URL generation handles generic exceptions."""
        from src.functions.services.blob_service import BlobServiceError

        with patch("src.functions.services.blob_service.generate_blob_sas") as mock_gen_sas:
            mock_gen_sas.side_effect = RuntimeError("Unexpected error")

            url = "https://teststorage.blob.core.windows.net/pdfs/test.pdf"

            with pytest.raises(BlobServiceError) as exc:
                blob_service.generate_sas_url(url)

            assert "SAS token generation failed" in str(exc.value)

    def test_download_blob(self, connection_string):
        """Test downloading a blob."""
        from src.functions.services.blob_service import BlobService

        with patch(
            "src.functions.services.blob_service.BlobServiceClient.from_connection_string"
        ) as mock_from_conn:
            mock_blob_client = MagicMock()
            mock_blob_client.download_blob.return_value.readall.return_value = b"PDF content"

            mock_container_client = MagicMock()
            mock_container_client.get_blob_client.return_value = mock_blob_client

            mock_client = MagicMock()
            mock_client.get_container_client.return_value = mock_container_client
            mock_from_conn.return_value = mock_client

            service = BlobService(connection_string)
            content = service.download_blob(
                "https://teststorage.blob.core.windows.net/pdfs/test.pdf"
            )

            assert content == b"PDF content"

    def test_download_blob_error(self, connection_string):
        """Test error when download fails."""
        from src.functions.services.blob_service import BlobService, BlobServiceError

        with patch(
            "src.functions.services.blob_service.BlobServiceClient.from_connection_string"
        ) as mock_from_conn:
            mock_from_conn.return_value.get_container_client.side_effect = Exception(
                "Connection error"
            )

            service = BlobService(connection_string)

            with pytest.raises(BlobServiceError) as exc:
                service.download_blob("https://teststorage.blob.core.windows.net/pdfs/test.pdf")

            assert "download failed" in str(exc.value).lower()

    def test_upload_blob(self, connection_string):
        """Test uploading a blob."""
        from src.functions.services.blob_service import BlobService

        with patch(
            "src.functions.services.blob_service.BlobServiceClient.from_connection_string"
        ) as mock_from_conn:
            mock_blob_client = MagicMock()
            mock_blob_client.url = "https://teststorage.blob.core.windows.net/pdfs/uploaded.pdf"

            mock_container_client = MagicMock()
            mock_container_client.get_blob_client.return_value = mock_blob_client

            mock_client = MagicMock()
            mock_client.get_container_client.return_value = mock_container_client
            mock_from_conn.return_value = mock_client

            service = BlobService(connection_string)
            url = service.upload_blob(
                container_name="pdfs",
                blob_name="uploaded.pdf",
                content=b"PDF content",
            )

            assert "uploaded.pdf" in url
            mock_blob_client.upload_blob.assert_called_once_with(b"PDF content", overwrite=True)

    def test_upload_blob_error(self, connection_string):
        """Test error when upload fails."""
        from src.functions.services.blob_service import BlobService, BlobServiceError

        with patch(
            "src.functions.services.blob_service.BlobServiceClient.from_connection_string"
        ) as mock_from_conn:
            mock_from_conn.return_value.get_container_client.side_effect = Exception("Upload error")

            service = BlobService(connection_string)

            with pytest.raises(BlobServiceError) as exc:
                service.upload_blob("container", "blob.pdf", b"content")

            assert "upload failed" in str(exc.value).lower()

    def test_delete_blob(self, connection_string):
        """Test deleting a blob."""
        from src.functions.services.blob_service import BlobService

        with patch(
            "src.functions.services.blob_service.BlobServiceClient.from_connection_string"
        ) as mock_from_conn:
            mock_blob_client = MagicMock()
            mock_container_client = MagicMock()
            mock_container_client.get_blob_client.return_value = mock_blob_client

            mock_client = MagicMock()
            mock_client.get_container_client.return_value = mock_container_client
            mock_from_conn.return_value = mock_client

            service = BlobService(connection_string)
            service.delete_blob("pdfs", "test.pdf")

            mock_blob_client.delete_blob.assert_called_once()

    def test_delete_blob_error(self, connection_string):
        """Test error when delete fails."""
        from src.functions.services.blob_service import BlobService, BlobServiceError

        with patch(
            "src.functions.services.blob_service.BlobServiceClient.from_connection_string"
        ) as mock_from_conn:
            mock_from_conn.return_value.get_container_client.side_effect = Exception("Delete error")

            service = BlobService(connection_string)

            with pytest.raises(BlobServiceError) as exc:
                service.delete_blob("container", "blob.pdf")

            assert "delete failed" in str(exc.value).lower()

    def test_list_blobs(self, connection_string):
        """Test listing blobs."""
        from src.functions.services.blob_service import BlobService

        with patch(
            "src.functions.services.blob_service.BlobServiceClient.from_connection_string"
        ) as mock_from_conn:
            mock_blob1 = MagicMock()
            mock_blob1.name = "incoming/doc1.pdf"
            mock_blob2 = MagicMock()
            mock_blob2.name = "incoming/doc2.pdf"

            mock_container_client = MagicMock()
            mock_container_client.list_blobs.return_value = [mock_blob1, mock_blob2]

            mock_client = MagicMock()
            mock_client.get_container_client.return_value = mock_container_client
            mock_from_conn.return_value = mock_client

            service = BlobService(connection_string)
            blobs = service.list_blobs("pdfs", prefix="incoming/")

            assert len(blobs) == 2
            assert "incoming/doc1.pdf" in blobs
            mock_container_client.list_blobs.assert_called_once_with(name_starts_with="incoming/")

    def test_list_blobs_error(self, connection_string):
        """Test error when list fails."""
        from src.functions.services.blob_service import BlobService, BlobServiceError

        with patch(
            "src.functions.services.blob_service.BlobServiceClient.from_connection_string"
        ) as mock_from_conn:
            mock_from_conn.return_value.get_container_client.side_effect = Exception("List error")

            service = BlobService(connection_string)

            with pytest.raises(BlobServiceError) as exc:
                service.list_blobs("container")

            assert "list failed" in str(exc.value).lower()

    def test_blob_exists_true(self, connection_string):
        """Test blob exists returns True."""
        from src.functions.services.blob_service import BlobService

        with patch(
            "src.functions.services.blob_service.BlobServiceClient.from_connection_string"
        ) as mock_from_conn:
            mock_blob_client = MagicMock()
            mock_blob_client.exists.return_value = True

            mock_container_client = MagicMock()
            mock_container_client.get_blob_client.return_value = mock_blob_client

            mock_client = MagicMock()
            mock_client.get_container_client.return_value = mock_container_client
            mock_from_conn.return_value = mock_client

            service = BlobService(connection_string)
            exists = service.blob_exists("pdfs", "test.pdf")

            assert exists is True

    def test_blob_exists_false(self, connection_string):
        """Test blob exists returns False."""
        from src.functions.services.blob_service import BlobService

        with patch(
            "src.functions.services.blob_service.BlobServiceClient.from_connection_string"
        ) as mock_from_conn:
            mock_blob_client = MagicMock()
            mock_blob_client.exists.return_value = False

            mock_container_client = MagicMock()
            mock_container_client.get_blob_client.return_value = mock_blob_client

            mock_client = MagicMock()
            mock_client.get_container_client.return_value = mock_container_client
            mock_from_conn.return_value = mock_client

            service = BlobService(connection_string)
            exists = service.blob_exists("pdfs", "nonexistent.pdf")

            assert exists is False

    def test_blob_exists_error_returns_false(self, connection_string):
        """Test blob exists returns False on error."""
        from src.functions.services.blob_service import BlobService

        with patch(
            "src.functions.services.blob_service.BlobServiceClient.from_connection_string"
        ) as mock_from_conn:
            mock_from_conn.return_value.get_container_client.side_effect = Exception("Error")

            service = BlobService(connection_string)
            exists = service.blob_exists("pdfs", "test.pdf")

            assert exists is False

    def test_move_blob(self, connection_string):
        """Test moving a blob."""
        from src.functions.services.blob_service import BlobService

        with patch(
            "src.functions.services.blob_service.BlobServiceClient.from_connection_string"
        ) as mock_from_conn:
            mock_source_blob = MagicMock()
            mock_source_blob.url = "https://source.blob.core.windows.net/src/test.pdf"

            mock_dest_blob = MagicMock()
            mock_dest_blob.url = "https://dest.blob.core.windows.net/dest/test.pdf"

            mock_source_container = MagicMock()
            mock_source_container.get_blob_client.return_value = mock_source_blob

            mock_dest_container = MagicMock()
            mock_dest_container.get_blob_client.return_value = mock_dest_blob

            mock_client = MagicMock()

            def get_container(name):
                if name == "src":
                    return mock_source_container
                return mock_dest_container

            mock_client.get_container_client.side_effect = get_container
            mock_from_conn.return_value = mock_client

            service = BlobService(connection_string)
            result = service.move_blob("src", "test.pdf", "dest")

            assert result == mock_dest_blob.url
            mock_dest_blob.start_copy_from_url.assert_called_once_with(mock_source_blob.url)
            mock_source_blob.delete_blob.assert_called_once()

    def test_move_blob_container_exists(self, connection_string):
        """Test moving a blob when destination container already exists."""
        from src.functions.services.blob_service import BlobService

        with patch(
            "src.functions.services.blob_service.BlobServiceClient.from_connection_string"
        ) as mock_from_conn:
            mock_source_blob = MagicMock()
            mock_source_blob.url = "https://source.blob.core.windows.net/src/test.pdf"

            mock_dest_blob = MagicMock()
            mock_dest_blob.url = "https://dest.blob.core.windows.net/dest/test.pdf"

            mock_source_container = MagicMock()
            mock_source_container.get_blob_client.return_value = mock_source_blob

            mock_dest_container = MagicMock()
            mock_dest_container.get_blob_client.return_value = mock_dest_blob
            # Simulate container already exists error
            mock_dest_container.create_container.side_effect = Exception("Container already exists")

            mock_client = MagicMock()

            def get_container(name):
                if name == "src":
                    return mock_source_container
                return mock_dest_container

            mock_client.get_container_client.side_effect = get_container
            mock_from_conn.return_value = mock_client

            service = BlobService(connection_string)
            # Should succeed despite create_container error
            result = service.move_blob("src", "test.pdf", "dest")

            assert result == mock_dest_blob.url
            mock_dest_blob.start_copy_from_url.assert_called_once()

    def test_move_blob_error(self, connection_string):
        """Test error when move fails."""
        from src.functions.services.blob_service import BlobService, BlobServiceError

        with patch(
            "src.functions.services.blob_service.BlobServiceClient.from_connection_string"
        ) as mock_from_conn:
            mock_from_conn.return_value.get_container_client.side_effect = Exception("Move error")

            service = BlobService(connection_string)

            with pytest.raises(BlobServiceError) as exc:
                service.move_blob("src", "test.pdf", "dest")

            assert "move failed" in str(exc.value).lower()
