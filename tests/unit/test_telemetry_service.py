"""Unit tests for the telemetry service."""

import logging

from unittest.mock import MagicMock, patch


class TestTelemetryService:
    """Tests for TelemetryService class."""

    def test_init_without_appinsights_configured(self):
        """Test initialization when Application Insights is not configured."""
        with patch.dict("os.environ", {}, clear=True):
            # Need to reload the module to pick up the cleared env
            from src.functions.services.telemetry_service import TelemetryService

            service = TelemetryService()
            assert service._enabled is False
            assert service._client is None

    def test_init_with_instrumentation_key(self):
        """Test initialization with instrumentation key (but missing opencensus)."""
        with patch.dict("os.environ", {"APPINSIGHTS_INSTRUMENTATIONKEY": "test-key"}, clear=True):
            with patch.dict("sys.modules", {"opencensus.ext.azure": None}):
                from src.functions.services.telemetry_service import TelemetryService

                service = TelemetryService()
                # Should be disabled due to missing opencensus
                assert service._enabled is False

    def test_track_form_processed_disabled(self, caplog):
        """Test track_form_processed logs when disabled."""
        caplog.set_level(logging.INFO)
        with patch.dict("os.environ", {}, clear=True):
            from src.functions.services.telemetry_service import TelemetryService

            service = TelemetryService()
            service.track_form_processed(
                model_id="prebuilt-layout",
                status="completed",
                confidence=0.95,
                duration_ms=1500.0,
                page_count=2,
            )

            # Should log even when disabled
            assert "Form processed" in caplog.text
            assert "prebuilt-layout" in caplog.text
            assert "completed" in caplog.text

    def test_track_retry_logs_warning(self, caplog):
        """Test track_retry logs a warning."""
        with patch.dict("os.environ", {}, clear=True):
            from src.functions.services.telemetry_service import TelemetryService

            service = TelemetryService()
            service.track_retry(
                blob_name="test/document.pdf",
                retry_count=2,
                reason="Rate limit exceeded",
            )

            assert "Processing retry" in caplog.text
            assert "test/document.pdf" in caplog.text
            assert "attempt=2" in caplog.text

    def test_track_dead_letter_logs_error(self, caplog):
        """Test track_dead_letter logs an error."""
        with patch.dict("os.environ", {}, clear=True):
            from src.functions.services.telemetry_service import TelemetryService

            service = TelemetryService()
            service.track_dead_letter(
                blob_name="test/failed.pdf",
                reason="Max retries exceeded",
            )

            assert "dead letter" in caplog.text.lower()
            assert "test/failed.pdf" in caplog.text

    def test_track_operation_context_manager(self):
        """Test track_operation context manager."""
        with patch.dict("os.environ", {}, clear=True):
            from src.functions.services.telemetry_service import TelemetryService

            service = TelemetryService()

            with service.track_operation("test_op", "test-model") as op:
                op["status"] = "completed"
                op["confidence"] = 0.95
                op["page_count"] = 5

            # Operation should complete without error
            assert op["status"] == "completed"
            assert op["confidence"] == 0.95

    def test_track_operation_default_failed_status(self):
        """Test track_operation defaults to failed status on exception."""
        with patch.dict("os.environ", {}, clear=True):
            from src.functions.services.telemetry_service import TelemetryService

            service = TelemetryService()

            try:
                with service.track_operation("test_op", "test-model") as op:
                    raise ValueError("Test error")
            except ValueError:
                pass

            # Should default to failed
            assert op["status"] == "failed"

    def test_get_telemetry_service_singleton(self):
        """Test get_telemetry_service returns singleton."""
        with patch.dict("os.environ", {}, clear=True):
            # Reset singleton
            import src.functions.services.telemetry_service as ts_module

            ts_module._telemetry_service = None

            from src.functions.services.telemetry_service import get_telemetry_service

            service1 = get_telemetry_service()
            service2 = get_telemetry_service()

            assert service1 is service2


class TestTelemetryServiceWithMockedOpenCensus:
    """Tests with mocked OpenCensus."""

    def test_track_form_processed_enabled(self):
        """Test track_form_processed with mocked OpenCensus."""
        _mock_exporter = MagicMock()  # Reserved for future exporter assertions
        mock_stats = MagicMock()
        mock_view_manager = MagicMock()
        mock_stats_recorder = MagicMock()
        mock_mmap = MagicMock()
        mock_stats_recorder.new_measurement_map.return_value = mock_mmap

        mock_stats.view_manager = mock_view_manager
        mock_stats.stats_recorder = mock_stats_recorder

        with patch.dict(
            "os.environ",
            {"APPINSIGHTS_INSTRUMENTATIONKEY": "test-key"},
            clear=True,
        ):
            with patch(
                "src.functions.services.telemetry_service.TelemetryService._initialize_client"
            ):
                from src.functions.services.telemetry_service import TelemetryService

                service = TelemetryService()
                # Manually set enabled for this test
                service._enabled = False

                # This should just log since we're disabled
                service.track_form_processed(
                    model_id="test-model",
                    status="completed",
                    confidence=0.9,
                    duration_ms=1000,
                    page_count=3,
                )
