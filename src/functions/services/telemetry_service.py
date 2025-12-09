"""Application Insights telemetry service for custom metrics and events.

Provides structured logging and metrics tracking for document processing.
"""

import logging
import os
import time
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

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
                from opencensus.stats import aggregation, measure, stats, view  # noqa: F401

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
                aggregation.DistributionAggregation([0, 1000, 5000, 10000, 30000, 60000, 120000]),
            )

            confidence_view = view.View(
                "model_confidence_distribution",
                "Distribution of confidence scores",
                [self._tag_model_id],
                self._measure_confidence,
                aggregation.DistributionAggregation([0.0, 0.5, 0.7, 0.8, 0.9, 0.95, 1.0]),
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

    def track_metric(
        self,
        name: str,
        value: float | int,
        dimensions: dict[str, str] | None = None,
        metric_type: str = "gauge",
    ) -> None:
        """Track a custom metric with dimensions.

        Flexible method for any custom metric tracking.

        Args:
            name: Metric name (e.g., "forms_processed", "avg_confidence").
            value: Metric value.
            dimensions: Key-value pairs for metric dimensions (e.g., {"model_id": "invoice"}).
            metric_type: Type of metric ("gauge", "counter", "histogram").
        """
        # Build dimension string for logging
        dim_str = ", ".join(f"{k}={v}" for k, v in (dimensions or {}).items())
        logger.info(f"Metric: {name}={value} [{metric_type}] {dim_str}")

        if not self._enabled:
            return

        try:
            from opencensus.stats import aggregation, measure, view
            from opencensus.tags import tag_key, tag_map, tag_value

            # Create dynamic measure if needed
            if isinstance(value, int):
                m = measure.MeasureInt(name, f"Custom metric: {name}", "count")
            else:
                m = measure.MeasureFloat(name, f"Custom metric: {name}", "value")

            # Create tag map from dimensions
            tmap = tag_map.TagMap()
            tag_keys = []
            if dimensions:
                for k, v in dimensions.items():
                    tk = tag_key.TagKey(k)
                    tag_keys.append(tk)
                    tmap.insert(tk, tag_value.TagValue(str(v)))

            # Record the metric
            mmap = self._stats_recorder.new_measurement_map()
            if isinstance(value, int):
                mmap.measure_int_put(m, value)
            else:
                mmap.measure_float_put(m, value)
            mmap.record(tmap)

        except Exception as e:
            logger.warning(f"Failed to track metric {name}: {e}")

    def track_batch_processing(
        self,
        batch_id: str,
        total_blobs: int,
        successful: int,
        failed: int,
        duration_ms: float,
    ) -> None:
        """Track batch processing metrics.

        Args:
            batch_id: Unique batch identifier.
            total_blobs: Total blobs in batch.
            successful: Number of successfully processed blobs.
            failed: Number of failed blobs.
            duration_ms: Total batch processing duration.
        """
        success_rate = (successful / total_blobs * 100) if total_blobs > 0 else 0

        logger.info(
            f"Batch {batch_id} completed: {successful}/{total_blobs} successful "
            f"({success_rate:.1f}%), {failed} failed, {duration_ms:.0f}ms"
        )

        self.track_metric("batch_total_blobs", total_blobs, {"batch_id": batch_id})
        self.track_metric("batch_successful", successful, {"batch_id": batch_id})
        self.track_metric("batch_failed", failed, {"batch_id": batch_id})
        self.track_metric("batch_duration_ms", duration_ms, {"batch_id": batch_id})
        self.track_metric("batch_success_rate", success_rate, {"batch_id": batch_id})

    def track_profile_usage(self, profile_name: str, model_id: str) -> None:
        """Track usage of a processing profile.

        Args:
            profile_name: Name of the profile used.
            model_id: Model ID from the profile.
        """
        self.track_metric(
            "profile_usage",
            1,
            {"profile_name": profile_name, "model_id": model_id},
            metric_type="counter",
        )

    def track_idempotency_hit(self, blob_name: str, idempotency_key: str) -> None:
        """Track when idempotency check prevents duplicate processing.

        Args:
            blob_name: Name of the blob that was already processed.
            idempotency_key: The idempotency key that matched.
        """
        logger.info(f"Idempotency hit: {blob_name} (key: {idempotency_key[:16]}...)")
        self.track_metric("idempotency_hits", 1, {"source": "cache"}, metric_type="counter")

    def track_queue_job(
        self,
        job_id: str,
        status: str,
        wait_time_ms: float | None = None,
    ) -> None:
        """Track queue job metrics.

        Args:
            job_id: Job identifier.
            status: Job status (queued, processing, completed, failed).
            wait_time_ms: Time spent waiting in queue (for processing/completed).
        """
        self.track_metric("queue_job_status", 1, {"job_id": job_id, "status": status})
        if wait_time_ms is not None:
            self.track_metric("queue_wait_time_ms", wait_time_ms, {"job_id": job_id})

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
