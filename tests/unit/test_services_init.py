"""Unit tests for the services module singleton getters."""

import sys
from unittest.mock import MagicMock, patch

import pytest


class TestGetDocumentService:
    """Tests for get_document_service singleton."""

    def test_get_document_service_creates_singleton(self):
        """Test document service singleton creation."""
        import src.functions.services as services_module
        from src.functions.services import get_document_service

        # Reset singleton
        services_module._document_service = None

        mock_config = MagicMock()
        mock_config.doc_intel_endpoint = "https://test.cognitiveservices.azure.com"
        mock_config.doc_intel_api_key = "test-key"
        mock_config.max_concurrent_requests = 3

        mock_config_module = MagicMock()
        mock_config_module.get_config = MagicMock(return_value=mock_config)

        with patch.dict(sys.modules, {"config": mock_config_module}):
            with patch(
                "src.functions.services.DocumentService.__init__", return_value=None
            ):
                service1 = get_document_service()
                service2 = get_document_service()

                assert service1 is service2  # Same instance


class TestGetCosmosService:
    """Tests for get_cosmos_service singleton."""

    def test_get_cosmos_service_creates_singleton(self):
        """Test cosmos service singleton creation."""
        import src.functions.services as services_module
        from src.functions.services import get_cosmos_service

        # Reset singleton
        services_module._cosmos_service = None

        mock_config = MagicMock()
        mock_config.cosmos_endpoint = "https://test.documents.azure.com"
        mock_config.cosmos_database = "TestDB"
        mock_config.cosmos_container = "TestContainer"

        mock_config_module = MagicMock()
        mock_config_module.get_config = MagicMock(return_value=mock_config)

        with patch.dict(sys.modules, {"config": mock_config_module}):
            with patch("src.functions.services.CosmosService.__init__", return_value=None):
                service1 = get_cosmos_service()
                service2 = get_cosmos_service()

                assert service1 is service2


class TestGetBlobService:
    """Tests for get_blob_service singleton."""

    def test_get_blob_service_creates_singleton(self):
        """Test blob service singleton creation."""
        import src.functions.services as services_module
        from src.functions.services import get_blob_service

        # Reset singleton
        services_module._blob_service = None

        mock_config = MagicMock()
        mock_config.storage_connection_string = "DefaultEndpointsProtocol=https;AccountName=test"
        mock_config.sas_token_expiry_hours = 2

        mock_config_module = MagicMock()
        mock_config_module.get_config = MagicMock(return_value=mock_config)

        with patch.dict(sys.modules, {"config": mock_config_module}):
            with patch("src.functions.services.BlobService.__init__", return_value=None):
                service1 = get_blob_service()
                service2 = get_blob_service()

                assert service1 is service2

    def test_get_blob_service_returns_none_when_not_configured(self):
        """Test blob service returns None when connection string missing."""
        import src.functions.services as services_module
        from src.functions.services import get_blob_service

        # Reset singleton
        services_module._blob_service = None

        mock_config = MagicMock()
        mock_config.storage_connection_string = None

        mock_config_module = MagicMock()
        mock_config_module.get_config = MagicMock(return_value=mock_config)

        with patch.dict(sys.modules, {"config": mock_config_module}):
            service = get_blob_service()
            assert service is None


class TestGetPdfService:
    """Tests for get_pdf_service singleton."""

    def test_get_pdf_service_creates_singleton(self):
        """Test pdf service singleton creation."""
        from src.functions.services import get_pdf_service

        # Reset singleton
        import src.functions.services as services_module

        services_module._pdf_service = None

        service1 = get_pdf_service()
        service2 = get_pdf_service()

        assert service1 is service2
        assert service1.pages_per_form == 2  # Default

    def test_get_pdf_service_respects_pages_per_form(self):
        """Test pdf service uses provided pages_per_form."""
        from src.functions.services import get_pdf_service

        # Reset singleton
        import src.functions.services as services_module

        services_module._pdf_service = None

        service = get_pdf_service(pages_per_form=4)
        assert service.pages_per_form == 4


class TestResetServices:
    """Tests for reset_services function."""

    def test_reset_services_clears_all_singletons(self):
        """Test reset_services clears all service instances."""
        import src.functions.services as services_module
        from src.functions.services import reset_services

        # Set dummy values
        services_module._document_service = "dummy_doc"
        services_module._cosmos_service = "dummy_cosmos"
        services_module._blob_service = "dummy_blob"
        services_module._pdf_service = "dummy_pdf"

        reset_services()

        assert services_module._document_service is None
        assert services_module._cosmos_service is None
        assert services_module._blob_service is None
        assert services_module._pdf_service is None
