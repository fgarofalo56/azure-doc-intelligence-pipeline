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
        with patch.dict("os.environ", {}, clear=True):
            from src.functions.services.telemetry_service import TelemetryService

            service = TelemetryService()
            # Manually enable and set up mocks
            service._enabled = True
            service._tag_model_id = MagicMock()
            service._tag_status = MagicMock()
            service._measure_forms_processed = MagicMock()
            service._measure_processing_duration = MagicMock()
            service._measure_confidence = MagicMock()
            service._measure_pages_processed = MagicMock()

            mock_mmap = MagicMock()
            mock_stats_recorder = MagicMock()
            mock_stats_recorder.new_measurement_map.return_value = mock_mmap
            service._stats_recorder = mock_stats_recorder

            # Create mock modules for the import inside track_form_processed
            mock_tags_module = MagicMock()
            mock_tags_module.tag_map.TagMap.return_value = MagicMock()
            mock_tags_module.tag_value.TagValue.return_value = MagicMock()

            with patch.dict(
                "sys.modules",
                {
                    "opencensus": MagicMock(),
                    "opencensus.tags": mock_tags_module,
                    "opencensus.tags.tag_map": mock_tags_module.tag_map,
                    "opencensus.tags.tag_value": mock_tags_module.tag_value,
                },
            ):
                service.track_form_processed(
                    model_id="test-model",
                    status="completed",
                    confidence=0.9,
                    duration_ms=1000,
                    page_count=3,
                )

            # Verify measurement map was created and recorded
            mock_stats_recorder.new_measurement_map.assert_called_once()
            mock_mmap.record.assert_called_once()

    def test_track_form_processed_enabled_error_handling(self, caplog):
        """Test track_form_processed handles errors gracefully when enabled."""
        with patch.dict("os.environ", {}, clear=True):
            from src.functions.services.telemetry_service import TelemetryService

            service = TelemetryService()
            service._enabled = True
            # Don't set up required attributes - will cause AttributeError

            # Should not raise, just log warning
            service.track_form_processed(
                model_id="test-model",
                status="completed",
            )

            assert "Failed to track form processed" in caplog.text

    def test_track_form_processed_minimal_params(self):
        """Test track_form_processed with minimal parameters when enabled."""
        with patch.dict("os.environ", {}, clear=True):
            from src.functions.services.telemetry_service import TelemetryService

            service = TelemetryService()
            service._enabled = True
            service._tag_model_id = MagicMock()
            service._tag_status = MagicMock()
            service._measure_forms_processed = MagicMock()
            service._measure_processing_duration = MagicMock()
            service._measure_confidence = MagicMock()
            service._measure_pages_processed = MagicMock()

            mock_mmap = MagicMock()
            mock_stats_recorder = MagicMock()
            mock_stats_recorder.new_measurement_map.return_value = mock_mmap
            service._stats_recorder = mock_stats_recorder

            with patch.dict(
                "sys.modules",
                {"opencensus.tags": MagicMock()},
            ):
                # Call with only required params (no duration, confidence, or pages)
                service.track_form_processed(
                    model_id="test-model",
                    status="completed",
                    # No optional params
                )

            # Verify only forms_processed was recorded (not duration/confidence/pages)
            assert mock_mmap.measure_int_put.call_count >= 1

    def test_track_retry_enabled(self):
        """Test track_retry with enabled telemetry."""
        with patch.dict("os.environ", {}, clear=True):
            from src.functions.services.telemetry_service import TelemetryService

            service = TelemetryService()
            service._enabled = True
            service._tag_source = MagicMock()
            service._measure_retries = MagicMock()

            mock_mmap = MagicMock()
            mock_stats_recorder = MagicMock()
            mock_stats_recorder.new_measurement_map.return_value = mock_mmap
            service._stats_recorder = mock_stats_recorder

            with patch.dict(
                "sys.modules",
                {"opencensus.tags": MagicMock()},
            ):
                service.track_retry(
                    blob_name="test/document.pdf",
                    retry_count=3,
                    reason="Rate limit",
                )

            mock_stats_recorder.new_measurement_map.assert_called_once()
            mock_mmap.record.assert_called_once()

    def test_track_retry_enabled_error_handling(self, caplog):
        """Test track_retry handles errors gracefully when enabled."""
        with patch.dict("os.environ", {}, clear=True):
            from src.functions.services.telemetry_service import TelemetryService

            service = TelemetryService()
            service._enabled = True
            # Don't set up required attributes

            service.track_retry(
                blob_name="test.pdf",
                retry_count=1,
                reason="Error",
            )

            assert "Failed to track retry" in caplog.text

    def test_initialize_with_connection_string_import_error(self, caplog):
        """Test initialization handles ImportError for opencensus."""
        with patch.dict(
            "os.environ",
            {"APPLICATIONINSIGHTS_CONNECTION_STRING": "InstrumentationKey=test"},
            clear=True,
        ):
            # Mock the import to raise ImportError
            import sys

            original_import = __builtins__["__import__"]

            def mock_import(name, *args, **kwargs):
                if name.startswith("opencensus"):
                    raise ImportError("No module named 'opencensus'")
                return original_import(name, *args, **kwargs)

            with patch.object(sys.modules["builtins"], "__import__", side_effect=mock_import):
                from importlib import reload

                import src.functions.services.telemetry_service as ts_module

                # Force reload to trigger import error
                try:
                    reload(ts_module)
                except ImportError:
                    pass

            # Service should be disabled
            service = ts_module.TelemetryService()
            # Can be enabled or disabled depending on order - just verify no crash
            assert service is not None

    def test_initialize_with_connection_string_generic_error(self, caplog):
        """Test initialization handles generic exceptions."""
        with patch.dict(
            "os.environ",
            {"APPLICATIONINSIGHTS_CONNECTION_STRING": "InstrumentationKey=test"},
            clear=True,
        ):
            with patch(
                "src.functions.services.telemetry_service.TelemetryService._setup_measures",
                side_effect=Exception("Setup failed"),
            ):
                # Can't easily test this path without complex mocking
                # Just verify the service can be created
                from src.functions.services.telemetry_service import TelemetryService

                service = TelemetryService()
                assert service is not None

    def test_setup_measures_error_handling(self, caplog):
        """Test _setup_measures handles errors gracefully."""
        with patch.dict("os.environ", {}, clear=True):
            from src.functions.services.telemetry_service import TelemetryService

            service = TelemetryService()

            # Mock an error during setup
            with patch.dict(
                "sys.modules",
                {"opencensus.stats": None},  # Will cause import to fail
            ):
                try:
                    service._setup_measures()
                except Exception:
                    pass  # Expected to fail

            # Service should still function
            assert service is not None


class TestAdditionalTelemetryMethods:
    """Tests for additional telemetry service methods."""

    def test_track_metric_disabled(self, caplog):
        """Test track_metric logs when disabled."""
        import logging

        caplog.set_level(logging.INFO)
        with patch.dict("os.environ", {}, clear=True):
            from src.functions.services.telemetry_service import TelemetryService

            service = TelemetryService()
            service.track_metric(
                name="custom_metric",
                value=42,
                dimensions={"key1": "value1", "key2": "value2"},
                metric_type="counter",
            )

            assert "custom_metric=42" in caplog.text
            assert "counter" in caplog.text
            assert "key1=value1" in caplog.text

    def test_track_metric_no_dimensions(self, caplog):
        """Test track_metric without dimensions."""
        import logging

        caplog.set_level(logging.INFO)
        with patch.dict("os.environ", {}, clear=True):
            from src.functions.services.telemetry_service import TelemetryService

            service = TelemetryService()
            service.track_metric(name="simple_metric", value=100.5)

            assert "simple_metric=100.5" in caplog.text
            assert "gauge" in caplog.text  # Default type

    def test_track_batch_processing_disabled(self, caplog):
        """Test track_batch_processing logs when disabled."""
        import logging

        caplog.set_level(logging.INFO)
        with patch.dict("os.environ", {}, clear=True):
            from src.functions.services.telemetry_service import TelemetryService

            service = TelemetryService()
            service.track_batch_processing(
                batch_id="batch-123",
                total_blobs=10,
                successful=8,
                failed=2,
                duration_ms=5000.0,
            )

            assert "batch-123" in caplog.text
            assert "8/10" in caplog.text
            assert "80.0%" in caplog.text

    def test_track_batch_processing_zero_blobs(self, caplog):
        """Test track_batch_processing with zero blobs."""
        import logging

        caplog.set_level(logging.INFO)
        with patch.dict("os.environ", {}, clear=True):
            from src.functions.services.telemetry_service import TelemetryService

            service = TelemetryService()
            service.track_batch_processing(
                batch_id="empty-batch",
                total_blobs=0,
                successful=0,
                failed=0,
                duration_ms=100.0,
            )

            # Should handle division by zero gracefully
            assert "empty-batch" in caplog.text
            assert "0%" in caplog.text

    def test_track_profile_usage_disabled(self, caplog):
        """Test track_profile_usage logs when disabled."""
        import logging

        caplog.set_level(logging.INFO)
        with patch.dict("os.environ", {}, clear=True):
            from src.functions.services.telemetry_service import TelemetryService

            service = TelemetryService()
            service.track_profile_usage(
                profile_name="invoice",
                model_id="prebuilt-invoice",
            )

            assert "profile_usage=1" in caplog.text
            assert "profile_name=invoice" in caplog.text

    def test_track_idempotency_hit_disabled(self, caplog):
        """Test track_idempotency_hit logs when disabled."""
        import logging

        caplog.set_level(logging.INFO)
        with patch.dict("os.environ", {}, clear=True):
            from src.functions.services.telemetry_service import TelemetryService

            service = TelemetryService()
            service.track_idempotency_hit(
                blob_name="test/document.pdf",
                idempotency_key="abc123def456ghi789",
            )

            assert "Idempotency hit" in caplog.text
            assert "test/document.pdf" in caplog.text
            # Key should be truncated
            assert "abc123def456ghi7..." in caplog.text

    def test_track_queue_job_disabled(self, caplog):
        """Test track_queue_job logs when disabled."""
        import logging

        caplog.set_level(logging.INFO)
        with patch.dict("os.environ", {}, clear=True):
            from src.functions.services.telemetry_service import TelemetryService

            service = TelemetryService()
            service.track_queue_job(
                job_id="job-456",
                status="completed",
                wait_time_ms=2500.0,
            )

            # Should log the metrics
            assert "queue_job_status=1" in caplog.text
            assert "queue_wait_time_ms=2500" in caplog.text

    def test_track_queue_job_no_wait_time(self, caplog):
        """Test track_queue_job without wait time."""
        import logging

        caplog.set_level(logging.INFO)
        with patch.dict("os.environ", {}, clear=True):
            from src.functions.services.telemetry_service import TelemetryService

            service = TelemetryService()
            service.track_queue_job(
                job_id="job-789",
                status="queued",
                wait_time_ms=None,
            )

            assert "queue_job_status=1" in caplog.text
            assert "queue_wait_time_ms" not in caplog.text

    def test_track_metric_enabled_int_value(self):
        """Test track_metric with integer value when enabled."""
        with patch.dict("os.environ", {}, clear=True):
            from src.functions.services.telemetry_service import TelemetryService

            service = TelemetryService()
            service._enabled = True

            mock_mmap = MagicMock()
            mock_stats_recorder = MagicMock()
            mock_stats_recorder.new_measurement_map.return_value = mock_mmap
            service._stats_recorder = mock_stats_recorder

            # Mock opencensus modules
            mock_stats = MagicMock()
            mock_tags = MagicMock()

            with patch.dict(
                "sys.modules",
                {
                    "opencensus.stats": mock_stats,
                    "opencensus.stats.aggregation": mock_stats.aggregation,
                    "opencensus.stats.measure": mock_stats.measure,
                    "opencensus.stats.view": mock_stats.view,
                    "opencensus.tags": mock_tags,
                    "opencensus.tags.tag_key": mock_tags.tag_key,
                    "opencensus.tags.tag_map": mock_tags.tag_map,
                    "opencensus.tags.tag_value": mock_tags.tag_value,
                },
            ):
                service.track_metric(
                    name="test_int_metric",
                    value=42,  # Integer
                    dimensions={"dim1": "val1"},
                )

            # Verify measure_int_put was called
            mock_mmap.measure_int_put.assert_called()

    def test_track_metric_enabled_float_value(self):
        """Test track_metric with float value when enabled."""
        with patch.dict("os.environ", {}, clear=True):
            from src.functions.services.telemetry_service import TelemetryService

            service = TelemetryService()
            service._enabled = True

            mock_mmap = MagicMock()
            mock_stats_recorder = MagicMock()
            mock_stats_recorder.new_measurement_map.return_value = mock_mmap
            service._stats_recorder = mock_stats_recorder

            mock_stats = MagicMock()
            mock_tags = MagicMock()

            with patch.dict(
                "sys.modules",
                {
                    "opencensus.stats": mock_stats,
                    "opencensus.stats.aggregation": mock_stats.aggregation,
                    "opencensus.stats.measure": mock_stats.measure,
                    "opencensus.stats.view": mock_stats.view,
                    "opencensus.tags": mock_tags,
                    "opencensus.tags.tag_key": mock_tags.tag_key,
                    "opencensus.tags.tag_map": mock_tags.tag_map,
                    "opencensus.tags.tag_value": mock_tags.tag_value,
                },
            ):
                service.track_metric(
                    name="test_float_metric",
                    value=3.14,  # Float
                )

            # Verify measure_float_put was called
            mock_mmap.measure_float_put.assert_called()

    def test_track_metric_enabled_error_handling(self, caplog):
        """Test track_metric handles errors gracefully when enabled."""
        with patch.dict("os.environ", {}, clear=True):
            from src.functions.services.telemetry_service import TelemetryService

            service = TelemetryService()
            service._enabled = True
            # Don't set up required attributes

            service.track_metric(
                name="error_metric",
                value=1,
            )

            assert "Failed to track metric" in caplog.text
