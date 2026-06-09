"""Unit tests for circuit breaker service."""

import asyncio
import os
import sys

import pytest

# Add src/functions to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src/functions"))


class TestCircuitBreakerState:
    """Tests for CircuitBreakerState enum."""

    def test_state_values(self):
        """Test state enum values."""
        from services.circuit_breaker import CircuitBreakerState

        assert CircuitBreakerState.CLOSED.value == "closed"
        assert CircuitBreakerState.OPEN.value == "open"
        assert CircuitBreakerState.HALF_OPEN.value == "half_open"


class TestCircuitBreakerConfig:
    """Tests for CircuitBreakerConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        from services.circuit_breaker import CircuitBreakerConfig

        config = CircuitBreakerConfig()

        assert config.failure_threshold == 5
        assert config.success_threshold == 2
        assert config.recovery_timeout == 30.0
        assert config.half_open_max_calls == 3

    def test_custom_config(self):
        """Test custom configuration values."""
        from services.circuit_breaker import CircuitBreakerConfig

        config = CircuitBreakerConfig(
            failure_threshold=10,
            success_threshold=5,
            recovery_timeout=60.0,
            half_open_max_calls=1,
        )

        assert config.failure_threshold == 10
        assert config.success_threshold == 5
        assert config.recovery_timeout == 60.0
        assert config.half_open_max_calls == 1


class TestCircuitBreaker:
    """Tests for CircuitBreaker class."""

    @pytest.mark.asyncio
    async def test_initial_state_is_closed(self):
        """Test circuit breaker starts in closed state."""
        from services.circuit_breaker import CircuitBreaker, CircuitBreakerState

        breaker = CircuitBreaker(name="test")

        assert breaker.state == CircuitBreakerState.CLOSED
        assert breaker.is_closed
        assert not breaker.is_open
        assert not breaker.is_half_open

    @pytest.mark.asyncio
    async def test_successful_call_stays_closed(self):
        """Test successful calls keep circuit closed."""
        from services.circuit_breaker import CircuitBreaker

        breaker = CircuitBreaker(name="test")

        async with breaker:
            pass  # Success

        assert breaker.is_closed
        assert breaker.stats.successful_calls == 1
        assert breaker.stats.failed_calls == 0

    @pytest.mark.asyncio
    async def test_failure_increments_counter(self):
        """Test failures increment the failure counter."""
        from services.circuit_breaker import CircuitBreaker, CircuitBreakerConfig

        config = CircuitBreakerConfig(failure_threshold=5)
        breaker = CircuitBreaker(name="test", config=config)

        try:
            async with breaker:
                raise ValueError("Test error")
        except ValueError:
            pass

        assert breaker.stats.failed_calls == 1
        assert breaker.stats.consecutive_failures == 1
        assert breaker.is_closed  # Not enough failures yet

    @pytest.mark.asyncio
    async def test_opens_after_threshold(self):
        """Test circuit opens after failure threshold reached."""
        from services.circuit_breaker import CircuitBreaker, CircuitBreakerConfig

        config = CircuitBreakerConfig(failure_threshold=3)
        breaker = CircuitBreaker(name="test", config=config)

        # Trigger 3 failures
        for _ in range(3):
            try:
                async with breaker:
                    raise ValueError("Test error")
            except ValueError:
                pass

        assert breaker.is_open
        assert breaker.stats.failed_calls == 3
        assert breaker.stats.consecutive_failures == 3

    @pytest.mark.asyncio
    async def test_open_circuit_rejects_calls(self):
        """Test open circuit rejects calls immediately."""
        from services.circuit_breaker import (
            CircuitBreaker,
            CircuitBreakerConfig,
            CircuitBreakerOpen,
        )

        config = CircuitBreakerConfig(failure_threshold=1, recovery_timeout=60)
        breaker = CircuitBreaker(name="test", config=config)

        # Open the circuit
        try:
            async with breaker:
                raise ValueError("Test error")
        except ValueError:
            pass

        assert breaker.is_open

        # Try to make another call
        with pytest.raises(CircuitBreakerOpen) as exc_info:
            async with breaker:
                pass

        assert exc_info.value.service_name == "test"
        assert exc_info.value.retry_after > 0
        assert breaker.stats.rejected_calls == 1

    @pytest.mark.asyncio
    async def test_transitions_to_half_open(self):
        """Test circuit transitions to half-open after timeout."""
        from services.circuit_breaker import (
            CircuitBreaker,
            CircuitBreakerConfig,
            CircuitBreakerState,
        )

        config = CircuitBreakerConfig(failure_threshold=1, recovery_timeout=0.1)
        breaker = CircuitBreaker(name="test", config=config)

        # Open the circuit
        try:
            async with breaker:
                raise ValueError("Test error")
        except ValueError:
            pass

        assert breaker.is_open

        # Wait for recovery timeout
        await asyncio.sleep(0.15)

        # Next call should work (half-open allows limited calls)
        async with breaker:
            pass  # Success

        # After success in half-open, should close (if success_threshold=2, need one more)
        assert breaker.state in (CircuitBreakerState.HALF_OPEN, CircuitBreakerState.CLOSED)

    @pytest.mark.asyncio
    async def test_half_open_closes_on_success(self):
        """Test half-open closes after enough successes."""
        from services.circuit_breaker import CircuitBreaker, CircuitBreakerConfig

        config = CircuitBreakerConfig(
            failure_threshold=1,
            success_threshold=2,
            recovery_timeout=0.1,
        )
        breaker = CircuitBreaker(name="test", config=config)

        # Open the circuit
        try:
            async with breaker:
                raise ValueError("Test error")
        except ValueError:
            pass

        await asyncio.sleep(0.15)  # Wait for half-open

        # Two successes should close the circuit
        async with breaker:
            pass
        async with breaker:
            pass

        assert breaker.is_closed
        assert breaker.stats.consecutive_successes == 2

    @pytest.mark.asyncio
    async def test_half_open_reopens_on_failure(self):
        """Test half-open reopens on any failure."""
        from services.circuit_breaker import CircuitBreaker, CircuitBreakerConfig

        config = CircuitBreakerConfig(
            failure_threshold=1,
            recovery_timeout=0.1,
        )
        breaker = CircuitBreaker(name="test", config=config)

        # Open the circuit
        try:
            async with breaker:
                raise ValueError("First error")
        except ValueError:
            pass

        await asyncio.sleep(0.15)  # Wait for half-open

        # Failure in half-open should reopen
        try:
            async with breaker:
                raise ValueError("Second error")
        except ValueError:
            pass

        assert breaker.is_open

    @pytest.mark.asyncio
    async def test_reset(self):
        """Test manual reset of circuit breaker."""
        from services.circuit_breaker import CircuitBreaker, CircuitBreakerConfig

        config = CircuitBreakerConfig(failure_threshold=1)
        breaker = CircuitBreaker(name="test", config=config)

        # Open the circuit
        try:
            async with breaker:
                raise ValueError("Test error")
        except ValueError:
            pass

        assert breaker.is_open

        # Manual reset
        breaker.reset()

        assert breaker.is_closed
        assert breaker.stats.consecutive_failures == 0

    @pytest.mark.asyncio
    async def test_get_status(self):
        """Test status reporting."""
        from services.circuit_breaker import CircuitBreaker, CircuitBreakerConfig

        config = CircuitBreakerConfig(failure_threshold=5, recovery_timeout=30)
        breaker = CircuitBreaker(name="test-service", config=config)

        # Make some calls
        async with breaker:
            pass

        status = breaker.get_status()

        assert status["name"] == "test-service"
        assert status["state"] == "closed"
        assert status["stats"]["total_calls"] == 1
        assert status["stats"]["successful_calls"] == 1
        assert status["config"]["failure_threshold"] == 5
        assert status["retry_after"] is None


class TestCircuitBreakerDecorator:
    """Tests for circuit breaker decorator."""

    @pytest.mark.asyncio
    async def test_decorator_wraps_function(self):
        """Test decorator wraps async function correctly."""
        from services.circuit_breaker import CircuitBreaker, circuit_breaker_decorator

        breaker = CircuitBreaker(name="test")

        @circuit_breaker_decorator(breaker)
        async def sample_func() -> str:
            return "success"

        result = await sample_func()

        assert result == "success"
        assert breaker.stats.successful_calls == 1

    @pytest.mark.asyncio
    async def test_decorator_records_failures(self):
        """Test decorator records failures."""
        from services.circuit_breaker import CircuitBreaker, circuit_breaker_decorator

        breaker = CircuitBreaker(name="test")

        @circuit_breaker_decorator(breaker)
        async def failing_func() -> str:
            raise RuntimeError("Failure")

        with pytest.raises(RuntimeError):
            await failing_func()

        assert breaker.stats.failed_calls == 1


class TestCircuitBreakerRegistry:
    """Tests for circuit breaker registry functions."""

    @pytest.fixture(autouse=True)
    def reset_breakers(self):
        """Reset circuit breakers before each test."""
        from services.circuit_breaker import reset_circuit_breakers

        reset_circuit_breakers()
        yield
        reset_circuit_breakers()

    @pytest.mark.asyncio
    async def test_get_circuit_breaker_creates_new(self):
        """Test get_circuit_breaker creates new breaker."""
        from services.circuit_breaker import get_circuit_breaker

        breaker = await get_circuit_breaker("new-service")

        assert breaker.name == "new-service"
        assert breaker.is_closed

    @pytest.mark.asyncio
    async def test_get_circuit_breaker_returns_same(self):
        """Test get_circuit_breaker returns same instance."""
        from services.circuit_breaker import get_circuit_breaker

        breaker1 = await get_circuit_breaker("service")
        breaker2 = await get_circuit_breaker("service")

        assert breaker1 is breaker2

    def test_get_circuit_breaker_sync(self):
        """Test synchronous circuit breaker creation."""
        from services.circuit_breaker import (
            CircuitBreakerConfig,
            get_circuit_breaker_sync,
        )

        config = CircuitBreakerConfig(failure_threshold=10)
        breaker = get_circuit_breaker_sync("sync-service", config)

        assert breaker.name == "sync-service"
        assert breaker.config.failure_threshold == 10

    def test_get_all_circuit_breaker_status(self):
        """Test getting status of all circuit breakers."""
        from services.circuit_breaker import (
            get_all_circuit_breaker_status,
            get_circuit_breaker_sync,
        )

        get_circuit_breaker_sync("service-1")
        get_circuit_breaker_sync("service-2")

        statuses = get_all_circuit_breaker_status()

        assert len(statuses) == 2
        names = {s["name"] for s in statuses}
        assert "service-1" in names
        assert "service-2" in names


class TestCircuitBreakerOpen:
    """Tests for CircuitBreakerOpen exception."""

    def test_exception_message(self):
        """Test exception message format."""
        from services.circuit_breaker import CircuitBreakerOpen

        exc = CircuitBreakerOpen("test-service", retry_after=15.5)

        assert exc.service_name == "test-service"
        assert exc.retry_after == 15.5
        assert "OPEN" in str(exc)
        assert "test-service" in str(exc)
        assert "15.5" in str(exc)


class TestConcurrentCalls:
    """Tests for concurrent call handling."""

    @pytest.mark.asyncio
    async def test_half_open_limits_concurrent_calls(self):
        """Test half-open state limits concurrent calls."""
        from services.circuit_breaker import (
            CircuitBreaker,
            CircuitBreakerConfig,
            CircuitBreakerOpen,
        )

        config = CircuitBreakerConfig(
            failure_threshold=1,
            recovery_timeout=0.1,
            half_open_max_calls=1,
        )
        breaker = CircuitBreaker(name="test", config=config)

        # Open the circuit
        try:
            async with breaker:
                raise ValueError("Error")
        except ValueError:
            pass

        await asyncio.sleep(0.15)  # Wait for half-open

        # First call should be allowed
        # Second concurrent call should be rejected

        async def slow_call():
            async with breaker:
                await asyncio.sleep(0.1)
                return "success"

        async def fast_call():
            try:
                async with breaker:
                    return "success"
            except CircuitBreakerOpen:
                return "rejected"

        # Start a slow call, then try a fast one
        task1 = asyncio.create_task(slow_call())
        await asyncio.sleep(0.01)  # Let first call acquire semaphore
        result2 = await fast_call()

        result1 = await task1

        assert result1 == "success"
        assert result2 == "rejected"
