"""Unit tests for the rate limiter service."""

import asyncio
import time
from unittest.mock import patch

import pytest


class TestRateLimitConfig:
    """Tests for RateLimitConfig dataclass."""

    def test_default_values(self):
        """Test default configuration values."""
        from src.functions.services.rate_limiter import RateLimitConfig

        config = RateLimitConfig()

        assert config.requests_per_minute == 60
        assert config.burst_size == 10
        assert config.window_seconds == 60

    def test_custom_values(self):
        """Test custom configuration values."""
        from src.functions.services.rate_limiter import RateLimitConfig

        config = RateLimitConfig(
            requests_per_minute=100,
            burst_size=20,
            window_seconds=120,
        )

        assert config.requests_per_minute == 100
        assert config.burst_size == 20
        assert config.window_seconds == 120


class TestTokenBucket:
    """Tests for TokenBucket class."""

    def test_init(self):
        """Test bucket initialization."""
        from src.functions.services.rate_limiter import TokenBucket

        bucket = TokenBucket(capacity=10)

        assert bucket.capacity == 10
        assert bucket.tokens == 10.0  # Starts full
        assert bucket.refill_rate == 10.0 / 60.0  # capacity / 60 seconds

    def test_consume_success(self):
        """Test successful token consumption."""
        from src.functions.services.rate_limiter import TokenBucket

        bucket = TokenBucket(capacity=10)
        result = bucket.consume(1)

        assert result is True
        assert bucket.tokens < 10.0

    def test_consume_multiple_tokens(self):
        """Test consuming multiple tokens at once."""
        from src.functions.services.rate_limiter import TokenBucket

        bucket = TokenBucket(capacity=10)
        result = bucket.consume(5)

        assert result is True
        # Should have approximately 5 tokens left (may have refilled slightly)
        assert bucket.tokens <= 5.1

    def test_consume_all_tokens(self):
        """Test consuming all tokens."""
        from src.functions.services.rate_limiter import TokenBucket

        bucket = TokenBucket(capacity=5)

        # Consume all tokens
        for _ in range(5):
            bucket.consume(1)

        # Next consume should fail
        result = bucket.consume(1)
        assert result is False

    def test_consume_rate_limited(self):
        """Test rate limiting when bucket empty."""
        from src.functions.services.rate_limiter import TokenBucket

        bucket = TokenBucket(capacity=2)

        # Consume all tokens
        bucket.consume(2)

        # Should be rate limited
        result = bucket.consume(1)
        assert result is False

    def test_token_refill_over_time(self):
        """Test tokens refill over time."""
        from src.functions.services.rate_limiter import TokenBucket

        bucket = TokenBucket(capacity=10)

        # Consume all tokens
        bucket.consume(10)
        assert bucket.tokens < 1.0

        # Simulate time passing by manipulating last_update
        bucket.last_update = time.monotonic() - 6  # 6 seconds ago

        # Try to consume - should trigger refill
        result = bucket.consume(1)
        assert result is True  # Refilled 1 token (10/60 * 6 = 1 token)

    def test_token_refill_caps_at_capacity(self):
        """Test tokens don't exceed capacity after refill."""
        from src.functions.services.rate_limiter import TokenBucket

        bucket = TokenBucket(capacity=5)

        # Simulate long time passing
        bucket.last_update = time.monotonic() - 120  # 2 minutes ago

        # Consume should trigger refill but cap at capacity
        bucket.consume(1)

        assert bucket.tokens <= 5.0

    def test_get_wait_time_zero(self):
        """Test wait time is zero when tokens available."""
        from src.functions.services.rate_limiter import TokenBucket

        bucket = TokenBucket(capacity=10)

        wait_time = bucket.get_wait_time(1)
        assert wait_time == 0.0

    def test_get_wait_time_when_empty(self):
        """Test wait time when tokens needed."""
        from src.functions.services.rate_limiter import TokenBucket

        bucket = TokenBucket(capacity=10)
        bucket.tokens = 0.0

        wait_time = bucket.get_wait_time(1)
        assert wait_time > 0.0
        # Should be approximately 6 seconds for 1 token (60 / 10 = 6 seconds per token)
        assert wait_time == pytest.approx(6.0, rel=0.1)

    def test_get_wait_time_partial(self):
        """Test wait time when partially depleted."""
        from src.functions.services.rate_limiter import TokenBucket

        bucket = TokenBucket(capacity=10)
        bucket.tokens = 0.5

        wait_time = bucket.get_wait_time(1)
        # Need 0.5 more tokens
        assert wait_time == pytest.approx(3.0, rel=0.1)


class TestRateLimiter:
    """Tests for RateLimiter class."""

    def test_init_default_config(self):
        """Test initialization with default config."""
        from src.functions.services.rate_limiter import RateLimiter

        limiter = RateLimiter()

        assert limiter.config.requests_per_minute == 60
        assert limiter.config.burst_size == 10

    def test_init_custom_config(self):
        """Test initialization with custom config."""
        from src.functions.services.rate_limiter import RateLimitConfig, RateLimiter

        config = RateLimitConfig(requests_per_minute=30, burst_size=5)
        limiter = RateLimiter(config=config)

        assert limiter.config.requests_per_minute == 30
        assert limiter.config.burst_size == 5

    def test_set_endpoint_limit(self):
        """Test setting endpoint-specific limits."""
        from src.functions.services.rate_limiter import RateLimitConfig, RateLimiter

        limiter = RateLimiter()
        custom_config = RateLimitConfig(requests_per_minute=10, burst_size=2)

        limiter.set_endpoint_limit("expensive", custom_config)

        assert "expensive" in limiter._endpoint_limits
        assert limiter._endpoint_limits["expensive"].burst_size == 2

    def test_get_bucket_key_no_endpoint(self):
        """Test bucket key without endpoint."""
        from src.functions.services.rate_limiter import RateLimiter

        limiter = RateLimiter()
        key = limiter.get_bucket_key("client-123")

        assert key == "client-123"

    def test_get_bucket_key_with_endpoint(self):
        """Test bucket key with endpoint."""
        from src.functions.services.rate_limiter import RateLimitConfig, RateLimiter

        limiter = RateLimiter()
        limiter.set_endpoint_limit("api/process", RateLimitConfig())

        key = limiter.get_bucket_key("client-123", "api/process")

        assert key == "client-123:api/process"

    def test_get_bucket_key_unknown_endpoint(self):
        """Test bucket key with unknown endpoint uses client only."""
        from src.functions.services.rate_limiter import RateLimiter

        limiter = RateLimiter()
        key = limiter.get_bucket_key("client-123", "unknown-endpoint")

        assert key == "client-123"

    @pytest.mark.asyncio
    async def test_check_rate_limit_allowed(self):
        """Test rate limit check passes when under limit."""
        from src.functions.services.rate_limiter import RateLimiter

        limiter = RateLimiter()
        allowed, headers = await limiter.check_rate_limit("client-123")

        assert allowed is True
        assert "X-RateLimit-Limit" in headers
        assert "X-RateLimit-Remaining" in headers
        assert "X-RateLimit-Reset" in headers

    @pytest.mark.asyncio
    async def test_check_rate_limit_blocked(self):
        """Test rate limit check fails when over limit."""
        from src.functions.services.rate_limiter import RateLimitConfig, RateLimiter

        # Very restrictive config
        config = RateLimitConfig(requests_per_minute=1, burst_size=1)
        limiter = RateLimiter(config=config)

        # First request should pass
        allowed1, _ = await limiter.check_rate_limit("client-123")
        assert allowed1 is True

        # Second request should be blocked
        allowed2, headers = await limiter.check_rate_limit("client-123")
        assert allowed2 is False
        assert "Retry-After" in headers

    @pytest.mark.asyncio
    async def test_check_rate_limit_with_endpoint(self):
        """Test rate limit with endpoint-specific bucket."""
        from src.functions.services.rate_limiter import RateLimitConfig, RateLimiter

        limiter = RateLimiter()
        limiter.set_endpoint_limit(
            "expensive",
            RateLimitConfig(requests_per_minute=1, burst_size=1),
        )

        # First request to endpoint passes
        allowed1, _ = await limiter.check_rate_limit("client-123", "expensive")
        assert allowed1 is True

        # Second blocked
        allowed2, _ = await limiter.check_rate_limit("client-123", "expensive")
        assert allowed2 is False

        # Different endpoint still works
        allowed3, _ = await limiter.check_rate_limit("client-123", "other")
        assert allowed3 is True

    @pytest.mark.asyncio
    async def test_check_rate_limit_different_clients(self):
        """Test rate limiting is per-client."""
        from src.functions.services.rate_limiter import RateLimitConfig, RateLimiter

        config = RateLimitConfig(requests_per_minute=1, burst_size=1)
        limiter = RateLimiter(config=config)

        # Client 1 uses their limit
        allowed1, _ = await limiter.check_rate_limit("client-1")
        allowed2, _ = await limiter.check_rate_limit("client-1")

        assert allowed1 is True
        assert allowed2 is False

        # Client 2 has their own limit
        allowed3, _ = await limiter.check_rate_limit("client-2")
        assert allowed3 is True

    @pytest.mark.asyncio
    async def test_wait_if_limited_allowed(self):
        """Test wait_if_limited when not rate limited."""
        from src.functions.services.rate_limiter import RateLimiter

        limiter = RateLimiter()
        result = await limiter.wait_if_limited("client-123")

        assert result is True

    @pytest.mark.asyncio
    async def test_wait_if_limited_exceeds_max_wait(self):
        """Test wait_if_limited when wait exceeds max."""
        from src.functions.services.rate_limiter import RateLimitConfig, RateLimiter

        config = RateLimitConfig(requests_per_minute=1, burst_size=1)
        limiter = RateLimiter(config=config)

        # Exhaust limit
        await limiter.check_rate_limit("client-123")
        await limiter.check_rate_limit("client-123")

        # Wait with very short max_wait
        result = await limiter.wait_if_limited("client-123", max_wait=0.001)

        assert result is False

    @pytest.mark.asyncio
    async def test_wait_if_limited_waits_and_proceeds(self):
        """Test wait_if_limited actually waits when within max_wait."""
        from src.functions.services.rate_limiter import RateLimitConfig, RateLimiter

        # Use high requests_per_minute for fast refill (1 token per second)
        config = RateLimitConfig(requests_per_minute=60, burst_size=1)
        limiter = RateLimiter(config=config)

        # Exhaust limit
        await limiter.check_rate_limit("client-123")

        # Second check exhausts
        allowed, _ = await limiter.check_rate_limit("client-123")
        assert allowed is False

        # Create a mock sleep that also advances the bucket's token refill
        async def mock_sleep_with_refill(duration):
            bucket = limiter._buckets.get("client-123")
            if bucket:
                # Simulate token refill by moving last_update to the past
                bucket.last_update -= duration

        with patch("asyncio.sleep", side_effect=mock_sleep_with_refill):
            # Use max_wait long enough for refill (60 seconds for 1 token at rate 1/60 per sec)
            result = await limiter.wait_if_limited("client-123", max_wait=120.0)
            # Will be True because we mocked the sleep with token refill simulation
            assert result is True

    def test_reset_specific_client(self):
        """Test resetting specific client's buckets."""
        from src.functions.services.rate_limiter import RateLimiter

        limiter = RateLimiter()
        limiter._buckets["client-1"] = "bucket1"
        limiter._buckets["client-1:endpoint"] = "bucket2"
        limiter._buckets["client-2"] = "bucket3"

        limiter.reset("client-1")

        assert "client-1" not in limiter._buckets
        assert "client-1:endpoint" not in limiter._buckets
        assert "client-2" in limiter._buckets

    def test_reset_all_clients(self):
        """Test resetting all buckets."""
        from src.functions.services.rate_limiter import RateLimiter

        limiter = RateLimiter()
        limiter._buckets["client-1"] = "bucket1"
        limiter._buckets["client-2"] = "bucket2"

        limiter.reset()

        assert len(limiter._buckets) == 0


class TestGetRateLimiter:
    """Tests for get_rate_limiter singleton."""

    def test_get_rate_limiter_creates_singleton(self):
        """Test singleton creation."""
        from src.functions.services import rate_limiter

        # Reset singleton for clean test
        rate_limiter._rate_limiter = None

        limiter1 = rate_limiter.get_rate_limiter()
        limiter2 = rate_limiter.get_rate_limiter()

        assert limiter1 is limiter2

    def test_get_rate_limiter_has_endpoint_limits(self):
        """Test singleton has preset endpoint limits."""
        from src.functions.services import rate_limiter

        # Reset singleton
        rate_limiter._rate_limiter = None

        limiter = rate_limiter.get_rate_limiter()

        assert "reprocess" in limiter._endpoint_limits
        assert "batch" in limiter._endpoint_limits
        assert limiter._endpoint_limits["reprocess"].burst_size == 3
        assert limiter._endpoint_limits["batch"].burst_size == 2
