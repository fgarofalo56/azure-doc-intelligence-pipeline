"""Graceful shutdown manager for long-running operations.

Handles SIGTERM/SIGINT signals and coordinates checkpoint-based
progress saving for multi-form PDF processing.
"""

import asyncio
import logging
import signal
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class ShutdownState(str, Enum):
    """Shutdown state machine."""

    RUNNING = "running"
    SHUTDOWN_REQUESTED = "shutdown_requested"
    GRACEFUL_PERIOD = "graceful_period"
    FORCE_SHUTDOWN = "force_shutdown"


@dataclass
class ProcessingCheckpoint:
    """Checkpoint for resumable processing."""

    job_id: str
    blob_name: str
    total_forms: int
    forms_completed: list[int] = field(default_factory=list)
    forms_in_progress: int | None = None
    last_checkpoint_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    original_page_count: int | None = None
    split_pdf_urls: dict[int, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "jobId": self.job_id,
            "blobName": self.blob_name,
            "totalForms": self.total_forms,
            "formsCompleted": self.forms_completed,
            "formsInProgress": self.forms_in_progress,
            "lastCheckpointAt": self.last_checkpoint_at,
            "originalPageCount": self.original_page_count,
            "splitPdfUrls": self.split_pdf_urls,
            "metadata": self.metadata,
            "documentType": "checkpoint",
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProcessingCheckpoint":
        """Create from dictionary."""
        return cls(
            job_id=data.get("jobId", ""),
            blob_name=data.get("blobName", ""),
            total_forms=data.get("totalForms", 0),
            forms_completed=data.get("formsCompleted", []),
            forms_in_progress=data.get("formsInProgress"),
            last_checkpoint_at=data.get("lastCheckpointAt", ""),
            original_page_count=data.get("originalPageCount"),
            split_pdf_urls=data.get("splitPdfUrls", {}),
            metadata=data.get("metadata", {}),
        )

    @property
    def is_complete(self) -> bool:
        """Check if all forms are processed."""
        return len(self.forms_completed) >= self.total_forms

    @property
    def next_form(self) -> int | None:
        """Get next form number to process (1-indexed)."""
        if self.is_complete:
            return None
        for i in range(1, self.total_forms + 1):
            if i not in self.forms_completed:
                return i
        return None

    @property
    def percent_complete(self) -> float:
        """Get completion percentage."""
        if self.total_forms == 0:
            return 0.0
        return round((len(self.forms_completed) / self.total_forms) * 100, 1)


class ShutdownManager:
    """Manages graceful shutdown for long-running operations.

    Features:
    - Signal handling (SIGTERM, SIGINT)
    - Checkpoint-based progress saving
    - Configurable graceful shutdown timeout
    - Callback support for cleanup operations
    """

    def __init__(
        self,
        graceful_timeout_seconds: int = 30,
        enable_signal_handlers: bool = True,
    ) -> None:
        """Initialize shutdown manager.

        Args:
            graceful_timeout_seconds: Time allowed for graceful shutdown.
            enable_signal_handlers: Whether to register signal handlers.
        """
        self._state = ShutdownState.RUNNING
        self._graceful_timeout = graceful_timeout_seconds
        self._shutdown_event = asyncio.Event()
        self._shutdown_callbacks: list[Callable[[], None]] = []
        self._active_operations: dict[str, ProcessingCheckpoint] = {}
        self._lock = threading.Lock()

        if enable_signal_handlers:
            self._setup_signal_handlers()

    def _setup_signal_handlers(self) -> None:
        """Setup signal handlers for graceful shutdown."""
        try:
            # For Unix-like systems
            signal.signal(signal.SIGTERM, self._handle_signal)
            signal.signal(signal.SIGINT, self._handle_signal)
            logger.debug("Signal handlers registered for SIGTERM and SIGINT")
        except (ValueError, OSError) as e:
            # May fail in non-main thread or on Windows
            logger.debug(f"Could not register signal handlers: {e}")

    def _handle_signal(self, signum: int, frame: Any) -> None:
        """Handle shutdown signal.

        Args:
            signum: Signal number received.
            frame: Current stack frame.
        """
        signal_name = signal.Signals(signum).name
        logger.warning(f"Received {signal_name}, initiating graceful shutdown")
        self.request_shutdown()

    def request_shutdown(self) -> None:
        """Request graceful shutdown."""
        with self._lock:
            if self._state == ShutdownState.RUNNING:
                self._state = ShutdownState.SHUTDOWN_REQUESTED
                self._shutdown_event.set()
                logger.info(f"Shutdown requested. Grace period: {self._graceful_timeout}s")

                # Run callbacks
                for callback in self._shutdown_callbacks:
                    try:
                        callback()
                    except Exception as e:
                        logger.error(f"Shutdown callback error: {e}")

    @property
    def is_shutdown_requested(self) -> bool:
        """Check if shutdown has been requested."""
        return self._state != ShutdownState.RUNNING

    @property
    def state(self) -> ShutdownState:
        """Get current shutdown state."""
        return self._state

    def add_shutdown_callback(self, callback: Callable[[], None]) -> None:
        """Add callback to run on shutdown.

        Args:
            callback: Function to call when shutdown is requested.
        """
        self._shutdown_callbacks.append(callback)

    async def wait_for_shutdown(self, timeout: float | None = None) -> bool:
        """Wait for shutdown signal.

        Args:
            timeout: Maximum time to wait in seconds.

        Returns:
            bool: True if shutdown was requested, False if timeout.
        """
        try:
            await asyncio.wait_for(
                self._shutdown_event.wait(),
                timeout=timeout or self._graceful_timeout,
            )
            return True
        except asyncio.TimeoutError:
            return False

    def should_continue_processing(self) -> bool:
        """Check if processing should continue.

        Returns:
            bool: True if safe to continue, False if should stop.
        """
        return self._state == ShutdownState.RUNNING

    # Checkpoint management

    def start_operation(
        self,
        job_id: str,
        blob_name: str,
        total_forms: int,
        original_page_count: int | None = None,
    ) -> ProcessingCheckpoint:
        """Start tracking a multi-form processing operation.

        Args:
            job_id: Job ID for this operation.
            blob_name: Source blob being processed.
            total_forms: Total number of forms to process.
            original_page_count: Page count of original PDF.

        Returns:
            ProcessingCheckpoint: Checkpoint for tracking progress.
        """
        checkpoint = ProcessingCheckpoint(
            job_id=job_id,
            blob_name=blob_name,
            total_forms=total_forms,
            original_page_count=original_page_count,
        )

        with self._lock:
            self._active_operations[job_id] = checkpoint

        logger.debug(f"Started tracking operation {job_id} with {total_forms} forms")
        return checkpoint

    def update_checkpoint(
        self,
        job_id: str,
        form_number: int,
        completed: bool = False,
        split_pdf_url: str | None = None,
    ) -> ProcessingCheckpoint | None:
        """Update checkpoint for a form.

        Args:
            job_id: Job ID to update.
            form_number: Form number (1-indexed).
            completed: Whether form processing completed.
            split_pdf_url: URL to split PDF for this form.

        Returns:
            Updated checkpoint or None if not found.
        """
        with self._lock:
            checkpoint = self._active_operations.get(job_id)
            if not checkpoint:
                return None

            if completed:
                if form_number not in checkpoint.forms_completed:
                    checkpoint.forms_completed.append(form_number)
                checkpoint.forms_in_progress = None
            else:
                checkpoint.forms_in_progress = form_number

            if split_pdf_url:
                checkpoint.split_pdf_urls[form_number] = split_pdf_url

            checkpoint.last_checkpoint_at = datetime.now(timezone.utc).isoformat()

        logger.debug(
            f"Checkpoint updated for {job_id}: form {form_number}, "
            f"completed={completed}, progress={checkpoint.percent_complete}%"
        )
        return checkpoint

    def get_checkpoint(self, job_id: str) -> ProcessingCheckpoint | None:
        """Get checkpoint for a job.

        Args:
            job_id: Job ID to retrieve.

        Returns:
            ProcessingCheckpoint or None if not found.
        """
        with self._lock:
            return self._active_operations.get(job_id)

    def complete_operation(self, job_id: str) -> ProcessingCheckpoint | None:
        """Mark operation as complete and remove from tracking.

        Args:
            job_id: Job ID to complete.

        Returns:
            Final checkpoint or None if not found.
        """
        with self._lock:
            return self._active_operations.pop(job_id, None)

    def get_incomplete_operations(self) -> list[ProcessingCheckpoint]:
        """Get all incomplete operations.

        Returns:
            List of checkpoints for incomplete operations.
        """
        with self._lock:
            return [cp for cp in self._active_operations.values() if not cp.is_complete]

    def reset(self) -> None:
        """Reset shutdown manager state."""
        with self._lock:
            self._state = ShutdownState.RUNNING
            self._shutdown_event.clear()
            self._active_operations.clear()


# Global shutdown manager instance
_shutdown_manager: ShutdownManager | None = None


def get_shutdown_manager() -> ShutdownManager:
    """Get or create ShutdownManager singleton.

    Returns:
        ShutdownManager instance.
    """
    global _shutdown_manager
    if _shutdown_manager is None:
        from config import get_config

        config = get_config()
        _shutdown_manager = ShutdownManager(
            graceful_timeout_seconds=config.shutdown_timeout,
            enable_signal_handlers=True,
        )
    return _shutdown_manager


def reset_shutdown_manager() -> None:
    """Reset shutdown manager (for testing)."""
    global _shutdown_manager
    if _shutdown_manager:
        _shutdown_manager.reset()
    _shutdown_manager = None
