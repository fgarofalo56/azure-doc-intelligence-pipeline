"""Application Insights telemetry service for custom metrics and events.

Provides structured logging and metrics tracking for document processing.
"""

import logging
import os
import time
from contextlib import contextmanager
from typing import Any, Generator

logger = logging.getLogger(__name__)


class TelemetryService:
    """Service for tracking custom metrics and events in Application Insights."""

    def __init__(self) -> None:
        """Initialize telemetry service."""
        self._client = None
        self._enabled = False
        self._initialize_client()

    def _initialize_client(self) -> None:
        """Initialize Application Insights client if configured."""
        connection_string = os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING")
        instrumentation_key = os.environ.get("APPINSIGHTS_INSTRUMENTATIONKEY")

        if connection_string or instrumentation_key:
            try:
                from opencensus.ext.azure import metrics_exporter
                from opencensus.stats import aggregation, measure, stats, view

                self._metrics_exporter = metrics_exporter.new_metrics_exporter(
                    connection_string=connection_string
                )
                self._stats = stats.stats
                self._view_manager = self._stats.view_manager
                self._stats_recorder = self._stats.stats_recorder

                # Register custom measures
                self._setup_measures()
                self._enabled = True
                logger.info("Application Insights telemetry initialized")
            except ImportError:
                logger.warning(
                    "opencensus-ext-azure not installed. "
                    "Install with: pip install opencensus-ext-azure"
                )
            except Exception as e:
                logger.warning(f"Failed to initialize Application Insights: {e}")
        else:
            logger.info("Application Insights not configured, telemetry disabled")

    def _setup_measures(self) -> None:
        """Set up custom measures and views."""
        try:
            from opencensus.stats import aggregation, measure, view
            from opencensus.tags import tag_key

            # Define tag keys for dimensions
            self._tag_model_id = tag_key.TagKey("model_id")
            self._tag_status = tag_key.TagKey("status")
            self._tag_source = tag_key.TagKey("source")

            # Forms processed counter
            self._measure_forms_processed = measure.MeasureInt(
                "forms_processed",
                "Number of forms processed",
                "forms",
            )

            # Processing duration
            self._measure_processing_duration = measure.MeasureFloat(
                "processing_duration_ms",
                "Document processing duration in milliseconds",
                "ms",
            )

            # Confidence score
            self._measure_confidence = measure.MeasureFloat(
                "model_confidence",
                "Document Intelligence model confidence score",
                "score",
            )

            # PDF pages processed
            self._measure_pages_processed = measure.MeasureInt(
                "pages_processed",
                "Number of PDF pages processed",
                "pages",
            )

            # Retry count
            self._measure_retries = measure.MeasureInt(
                "retry_count",
                "Number of processing retries",
                "retries",
            )

            # Register views
            forms_view = view.View(
                "forms_processed_total",
                "Total forms processed",
                [self._tag_model_id, self._tag_status],
                self._measure_forms_processed,
                aggregation.CountAggregation(),
            )

            duration_view = view.View(
                "processing_duration_distribution",
                "Distribution of processing durations",
                [self._tag_model_id],
                self._measure_processing_duration,
                aggregation.DistributionAggregation(
                    [0, 1000, 5000, 10000, 30000, 60000, 120000]
                ),
            )

            confidence_view = view.View(
                "model_confidence_distribution",
                "Distribution of confidence scores",
                [self._tag_model_id],
                self._measure_confidence,
                aggregation.DistributionAggregation(
                    [0.0, 0.5, 0.7, 0.8, 0.9, 0.95, 1.0]
                ),
            )

            self._view_manager.register_view(forms_view)
            self._view_manager.register_view(duration_view)
            self._view_manager.register_view(confidence_view)

            logger.info("Custom metrics views registered")

        except Exception as e:
            logger.warning(f"Failed to setup measures: {e}")

    def track_form_processed(
        self,
        model_id: str,
        status: str,
        confidence: float | None = None,
        duration_ms: float | None = None,
        page_count: int = 0,
    ) -> None:
        """Track a processed form.

        Args:
            model_id: Document Intelligence model ID used.
            status: Processing status (completed, failed, etc.).
            confidence: Model confidence score (0-1).
            duration_ms: Processing duration in milliseconds.
            page_count: Number of pages processed.
        """
        if not self._enabled:
            # Log metrics even if App Insights not configured
            logger.info(
                f"Form processed: model={model_id}, status={status}, "
                f"confidence={confidence}, duration_ms={duration_ms}, pages={page_count}"
            )
            return

        try:
            from opencensus.stats import measure as measure_module
            from opencensus.tags import tag_map, tag_value

            # Create tag map
            tmap = tag_map.TagMap()
            tmap.insert(self._tag_model_id, tag_value.TagValue(model_id))
            tmap.insert(self._tag_status, tag_value.TagValue(status))

            # Record forms processed
            mmap = self._stats_recorder.new_measurement_map()
            mmap.measure_int_put(self._measure_forms_processed, 1)

            if duration_ms is not None:
                mmap.measure_float_put(self._measure_processing_duration, duration_ms)

            if confidence is not None:
                mmap.measure_float_put(self._measure_confidence, confidence)

            if page_count > 0:
                mmap.measure_int_put(self._measure_pages_processed, page_count)

            mmap.record(tmap)

        except Exception as e:
            logger.warning(f"Failed to track form processed: {e}")

    def track_retry(self, blob_name: str, retry_count: int, reason: str) -> None:
        """Track a processing retry.

        Args:
            blob_name: Name of the blob being retried.
            retry_count: Current retry attempt number.
            reason: Reason for retry.
        """
        logger.warning(
            f"Processing retry: blob={blob_name}, attempt={retry_count}, reason={reason}"
        )

        if not self._enabled:
            return

        try:
            from opencensus.tags import tag_map, tag_value

            tmap = tag_map.TagMap()
            tmap.insert(self._tag_source, tag_value.TagValue(blob_name[:50]))

            mmap = self._stats_recorder.new_measurement_map()
            mmap.measure_int_put(self._measure_retries, retry_count)
            mmap.record(tmap)

        except Exception as e:
            logger.warning(f"Failed to track retry: {e}")

    def track_dead_letter(self, blob_name: str, reason: str) -> None:
        """Track a document moved to dead letter queue.

        Args:
            blob_name: Name of the blob moved to DLQ.
            reason: Reason for moving to DLQ.
        """
        logger.error(f"Document moved to dead letter: blob={blob_name}, reason={reason}")

    @contextmanager
    def track_operation(
        self,
        operation_name: str,
        model_id: str = "unknown",
    ) -> Generator[dict[str, Any], None, None]:
        """Context manager for tracking operation duration.

        Args:
            operation_name: Name of the operation being tracked.
            model_id: Model ID for the operation.

        Yields:
            Dict to store operation results (status, confidence, etc.)

        Example:
            with telemetry.track_operation("process_form", "my-model") as op:
                result = process_form()
                op["status"] = "completed"
                op["confidence"] = result.confidence
        """
        start_time = time.perf_counter()
        result: dict[str, Any] = {
            "status": "failed",
            "confidence": None,
            "page_count": 0,
        }

        try:
            yield result
        finally:
            duration_ms = (time.perf_counter() - start_time) * 1000
            self.track_form_processed(
                model_id=model_id,
                status=result.get("status", "failed"),
                confidence=result.get("confidence"),
                duration_ms=duration_ms,
                page_count=result.get("page_count", 0),
            )


# Singleton instance
_telemetry_service: TelemetryService | None = None


def get_telemetry_service() -> TelemetryService:
    """Get or create the telemetry service singleton.

    Returns:
        TelemetryService instance.
    """
    global _telemetry_service
    if _telemetry_service is None:
        _telemetry_service = TelemetryService()
    return _telemetry_service
