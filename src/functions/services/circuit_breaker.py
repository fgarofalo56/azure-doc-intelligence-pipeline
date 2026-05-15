"""Circuit Breaker pattern implementation for resilient API calls.

Prevents cascading failures by failing fast when a service is unhealthy.

States:
- CLOSED: Normal operation, requests pass through
- OPEN: Service unhealthy, requests fail immediately (fast-fail)
- HALF_OPEN: Testing recovery, limited requests allowed through

Usage:
    breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=30)

    try:
        async with breaker:
            result = await some_api_call()
    except CircuitBreakerOpen:
        # Service is down, handle gracefully
        pass
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps
from typing import Any, Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CircuitBreakerState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Fast-fail mode
    HALF_OPEN = "half_open"  # Testing recovery


class CircuitBreakerError(Exception):
    """Base exception for circuit breaker errors."""

    pass


class CircuitBreakerOpen(CircuitBreakerError):
    """Raised when circuit is open and request cannot proceed."""

    def __init__(self, service_name: str, retry_after: float) -> None:
        self.service_name = service_name
        self.retry_after = retry_after
        super().__init__(
            f"Circuit breaker is OPEN for '{service_name}'. "
            f"Retry after {retry_after:.1f} seconds."
        )


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker behavior."""

    failure_threshold: int = 5  # Failures before opening circuit
    success_threshold: int = 2  # Successes in half-open before closing
    recovery_timeout: float = 30.0  # Seconds before trying half-open
    half_open_max_calls: int = 3  # Max concurrent calls in half-open


@dataclass
class CircuitBreakerStats:
    """Statistics for circuit breaker monitoring."""

    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    rejected_calls: int = 0
    state_changes: int = 0
    last_failure_time: float | None = None
    last_success_time: float | None = None
    consecutive_failures: int = 0
    consecutive_successes: int = 0


@dataclass
class CircuitBreaker:
    """Circuit breaker for protecting external service calls.

    Implements the circuit breaker pattern to prevent cascading failures
    when an external service becomes unavailable.

    Attributes:
        name: Identifier for this circuit breaker (e.g., 'document-intelligence')
        config: Configuration settings for thresholds and timeouts
    """

    name: str
    config: CircuitBreakerConfig = field(default_factory=CircuitBreakerConfig)
    _state: CircuitBreakerState = field(default=CircuitBreakerState.CLOSED, init=False)
    _stats: CircuitBreakerStats = field(default_factory=CircuitBreakerStats, init=False)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)
    _half_open_semaphore: asyncio.Semaphore | None = field(default=None, init=False)
    _opened_at: float | None = field(default=None, init=False)

    def __post_init__(self) -> None:
        """Initialize semaphore after dataclass creation."""
        self._half_open_semaphore = asyncio.Semaphore(self.config.half_open_max_calls)

    @property
    def state(self) -> CircuitBreakerState:
        """Current circuit state."""
        return self._state

    @property
    def stats(self) -> CircuitBreakerStats:
        """Circuit breaker statistics."""
        return self._stats

    @property
    def is_closed(self) -> bool:
        """Check if circuit is closed (normal operation)."""
        return self._state == CircuitBreakerState.CLOSED

    @property
    def is_open(self) -> bool:
        """Check if circuit is open (fast-fail mode)."""
        return self._state == CircuitBreakerState.OPEN

    @property
    def is_half_open(self) -> bool:
        """Check if circuit is half-open (testing recovery)."""
        return self._state == CircuitBreakerState.HALF_OPEN

    def _get_retry_after(self) -> float:
        """Calculate time until retry is allowed."""
        if self._opened_at is None:
            return 0.0
        elapsed = time.monotonic() - self._opened_at
        remaining = self.config.recovery_timeout - elapsed
        return max(0.0, remaining)

    async def _check_state(self) -> None:
        """Check and potentially transition state based on timeouts."""
        if self._state == CircuitBreakerState.OPEN:
            if self._opened_at is not None:
                elapsed = time.monotonic() - self._opened_at
                if elapsed >= self.config.recovery_timeout:
                    await self._transition_to(CircuitBreakerState.HALF_OPEN)

    async def _transition_to(self, new_state: CircuitBreakerState) -> None:
        """Transition to a new state."""
        old_state = self._state
        self._state = new_state
        self._stats.state_changes += 1

        if new_state == CircuitBreakerState.OPEN:
            self._opened_at = time.monotonic()
            self._stats.consecutive_successes = 0
            logger.warning(
                f"Circuit breaker '{self.name}' OPENED after "
                f"{self._stats.consecutive_failures} consecutive failures"
            )
        elif new_state == CircuitBreakerState.HALF_OPEN:
            self._stats.consecutive_failures = 0
            self._stats.consecutive_successes = 0
            logger.info(
                f"Circuit breaker '{self.name}' entering HALF_OPEN state "
                f"(testing recovery)"
            )
        elif new_state == CircuitBreakerState.CLOSED:
            self._opened_at = None
            self._stats.consecutive_failures = 0
            logger.info(
                f"Circuit breaker '{self.name}' CLOSED "
                f"(recovered after {old_state.value})"
            )

    async def _record_success(self) -> None:
        """Record a successful call."""
        async with self._lock:
            self._stats.total_calls += 1
            self._stats.successful_calls += 1
            self._stats.consecutive_successes += 1
            self._stats.consecutive_failures = 0
            self._stats.last_success_time = time.monotonic()

            if self._state == CircuitBreakerState.HALF_OPEN:
                if self._stats.consecutive_successes >= self.config.success_threshold:
                    await self._transition_to(CircuitBreakerState.CLOSED)

    async def _record_failure(self, error: Exception) -> None:
        """Record a failed call."""
        async with self._lock:
            self._stats.total_calls += 1
            self._stats.failed_calls += 1
            self._stats.consecutive_failures += 1
            self._stats.consecutive_successes = 0
            self._stats.last_failure_time = time.monotonic()

            logger.warning(
                f"Circuit breaker '{self.name}' recorded failure: {error} "
                f"(consecutive: {self._stats.consecutive_failures})"
            )

            # Check if we should open the circuit
            if self._state == CircuitBreakerState.CLOSED:
                if self._stats.consecutive_failures >= self.config.failure_threshold:
                    await self._transition_to(CircuitBreakerState.OPEN)
            elif self._state == CircuitBreakerState.HALF_OPEN:
                # Any failure in half-open reopens the circuit
                await self._transition_to(CircuitBreakerState.OPEN)

    async def _can_execute(self) -> bool:
        """Check if a call can be executed based on current state."""
        async with self._lock:
            await self._check_state()

            if self._state == CircuitBreakerState.CLOSED:
                return True
            elif self._state == CircuitBreakerState.OPEN:
                self._stats.rejected_calls += 1
                return False
            else:  # HALF_OPEN
                # Limited calls allowed in half-open
                if self._half_open_semaphore and self._half_open_semaphore.locked():
                    self._stats.rejected_calls += 1
                    return False
                return True

    async def __aenter__(self) -> "CircuitBreaker":
        """Enter circuit breaker context."""
        if not await self._can_execute():
            raise CircuitBreakerOpen(self.name, self._get_retry_after())

        # Acquire semaphore in half-open state
        if self._state == CircuitBreakerState.HALF_OPEN and self._half_open_semaphore:
            await self._half_open_semaphore.acquire()

        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        """Exit circuit breaker context."""
        # Release semaphore if we were in half-open
        if self._state == CircuitBreakerState.HALF_OPEN and self._half_open_semaphore:
            self._half_open_semaphore.release()

        if exc_type is None:
            await self._record_success()
        elif exc_val is not None:
            await self._record_failure(exc_val)

    def reset(self) -> None:
        """Manually reset circuit breaker to closed state."""
        self._state = CircuitBreakerState.CLOSED
        self._opened_at = None
        self._stats.consecutive_failures = 0
        self._stats.consecutive_successes = 0
        logger.info(f"Circuit breaker '{self.name}' manually reset")

    def get_status(self) -> dict[str, Any]:
        """Get current circuit breaker status for monitoring."""
        return {
            "name": self.name,
            "state": self._state.value,
            "stats": {
                "total_calls": self._stats.total_calls,
                "successful_calls": self._stats.successful_calls,
                "failed_calls": self._stats.failed_calls,
                "rejected_calls": self._stats.rejected_calls,
                "state_changes": self._stats.state_changes,
                "consecutive_failures": self._stats.consecutive_failures,
                "consecutive_successes": self._stats.consecutive_successes,
            },
            "config": {
                "failure_threshold": self.config.failure_threshold,
                "success_threshold": self.config.success_threshold,
                "recovery_timeout": self.config.recovery_timeout,
            },
            "retry_after": self._get_retry_after() if self.is_open else None,
        }


def circuit_breaker_decorator(
    breaker: CircuitBreaker,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator to wrap async functions with circuit breaker protection.

    Usage:
        doc_intel_breaker = CircuitBreaker("document-intelligence")

        @circuit_breaker_decorator(doc_intel_breaker)
        async def call_document_intelligence(url: str) -> dict:
            ...
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            async with breaker:
                return await func(*args, **kwargs)

        return wrapper

    return decorator


# Global circuit breakers for different services
_circuit_breakers: dict[str, CircuitBreaker] = {}
_breaker_lock = asyncio.Lock()


async def get_circuit_breaker(
    name: str,
    config: CircuitBreakerConfig | None = None,
) -> CircuitBreaker:
    """Get or create a named circuit breaker.

    Args:
        name: Unique identifier for the circuit breaker
        config: Optional configuration (used only on first creation)

    Returns:
        CircuitBreaker instance
    """
    async with _breaker_lock:
        if name not in _circuit_breakers:
            _circuit_breakers[name] = CircuitBreaker(
                name=name,
                config=config or CircuitBreakerConfig(),
            )
            logger.info(f"Created circuit breaker '{name}'")
        return _circuit_breakers[name]


def get_circuit_breaker_sync(
    name: str,
    config: CircuitBreakerConfig | None = None,
) -> CircuitBreaker:
    """Synchronous version of get_circuit_breaker for initialization.

    Args:
        name: Unique identifier for the circuit breaker
        config: Optional configuration (used only on first creation)

    Returns:
        CircuitBreaker instance
    """
    if name not in _circuit_breakers:
        _circuit_breakers[name] = CircuitBreaker(
            name=name,
            config=config or CircuitBreakerConfig(),
        )
        logger.info(f"Created circuit breaker '{name}'")
    return _circuit_breakers[name]


def reset_circuit_breakers() -> None:
    """Reset all circuit breakers (for testing)."""
    global _circuit_breakers
    _circuit_breakers = {}
    logger.info("All circuit breakers reset")


def get_all_circuit_breaker_status() -> list[dict[str, Any]]:
    """Get status of all circuit breakers for monitoring."""
    return [breaker.get_status() for breaker in _circuit_breakers.values()]
