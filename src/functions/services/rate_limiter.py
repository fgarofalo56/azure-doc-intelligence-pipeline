"""Rate limiting service for API protection.

Implements token bucket algorithm with configurable limits per endpoint.
"""

import asyncio
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""

    requests_per_minute: int = 60
    burst_size: int = 10
    window_seconds: int = 60


@dataclass
class TokenBucket:
    """Token bucket for rate limiting."""

    capacity: int
    tokens: float = field(init=False)
    last_update: float = field(init=False)
    refill_rate: float = field(init=False)

    def __post_init__(self) -> None:
        """Initialize bucket with full tokens."""
        self.tokens = float(self.capacity)
        self.last_update = time.monotonic()
        self.refill_rate = self.capacity / 60.0  # Refill per second

    def consume(self, tokens: int = 1) -> bool:
        """Try to consume tokens from bucket.

        Args:
            tokens: Number of tokens to consume.

        Returns:
            True if tokens consumed, False if rate limited.
        """
        now = time.monotonic()
        elapsed = now - self.last_update
        self.last_update = now

        # Refill tokens based on elapsed time
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)

        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False

    def get_wait_time(self, tokens: int = 1) -> float:
        """Get time to wait until tokens are available.

        Args:
            tokens: Number of tokens needed.

        Returns:
            Wait time in seconds.
        """
        if self.tokens >= tokens:
            return 0.0
        needed = tokens - self.tokens
        return needed / self.refill_rate


class RateLimiter:
    """Rate limiter using token bucket algorithm."""

    def __init__(self, config: RateLimitConfig | None = None) -> None:
        """Initialize rate limiter.

        Args:
            config: Rate limit configuration.
        """
        self.config = config or RateLimitConfig()
        self._buckets: dict[str, TokenBucket] = defaultdict(
            lambda: TokenBucket(capacity=self.config.burst_size)
        )
        self._endpoint_limits: dict[str, RateLimitConfig] = {}
        self._lock = asyncio.Lock()

    def set_endpoint_limit(self, endpoint: str, config: RateLimitConfig) -> None:
        """Set custom limit for specific endpoint.

        Args:
            endpoint: Endpoint path.
            config: Rate limit configuration.
        """
        self._endpoint_limits[endpoint] = config

    def get_bucket_key(self, client_id: str, endpoint: str | None = None) -> str:
        """Get bucket key for client and optional endpoint.

        Args:
            client_id: Client identifier (IP, API key, etc.).
            endpoint: Optional endpoint for per-endpoint limits.

        Returns:
            Bucket key string.
        """
        if endpoint and endpoint in self._endpoint_limits:
            return f"{client_id}:{endpoint}"
        return client_id

    async def check_rate_limit(
        self,
        client_id: str,
        endpoint: str | None = None,
    ) -> tuple[bool, dict[str, Any]]:
        """Check if request is allowed under rate limit.

        Args:
            client_id: Client identifier.
            endpoint: Optional endpoint path.

        Returns:
            Tuple of (allowed, headers) where headers contain rate limit info.
        """
        async with self._lock:
            bucket_key = self.get_bucket_key(client_id, endpoint)

            # Get or create bucket
            if bucket_key not in self._buckets:
                config = self._endpoint_limits.get(endpoint, self.config) if endpoint else self.config
                self._buckets[bucket_key] = TokenBucket(capacity=config.burst_size)

            bucket = self._buckets[bucket_key]
            allowed = bucket.consume()

            headers = {
                "X-RateLimit-Limit": str(self.config.requests_per_minute),
                "X-RateLimit-Remaining": str(int(bucket.tokens)),
                "X-RateLimit-Reset": str(int(time.time() + 60)),
            }

            if not allowed:
                headers["Retry-After"] = str(int(bucket.get_wait_time()) + 1)

            return allowed, headers

    async def wait_if_limited(
        self,
        client_id: str,
        endpoint: str | None = None,
        max_wait: float = 30.0,
    ) -> bool:
        """Wait if rate limited, up to max_wait seconds.

        Args:
            client_id: Client identifier.
            endpoint: Optional endpoint path.
            max_wait: Maximum seconds to wait.

        Returns:
            True if request can proceed, False if max_wait exceeded.
        """
        allowed, _ = await self.check_rate_limit(client_id, endpoint)
        if allowed:
            return True

        bucket_key = self.get_bucket_key(client_id, endpoint)
        bucket = self._buckets.get(bucket_key)

        if bucket:
            wait_time = bucket.get_wait_time()
            if wait_time <= max_wait:
                await asyncio.sleep(wait_time)
                return True

        return False

    def reset(self, client_id: str | None = None) -> None:
        """Reset rate limit buckets.

        Args:
            client_id: Specific client to reset, or None for all.
        """
        if client_id:
            keys_to_remove = [k for k in self._buckets if k.startswith(client_id)]
            for key in keys_to_remove:
                del self._buckets[key]
        else:
            self._buckets.clear()


# Global rate limiter instance
_rate_limiter: RateLimiter | None = None


def get_rate_limiter() -> RateLimiter:
    """Get or create rate limiter singleton.

    Returns:
        RateLimiter instance.
    """
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()

        # Set stricter limits for expensive endpoints
        _rate_limiter.set_endpoint_limit(
            "reprocess",
            RateLimitConfig(requests_per_minute=10, burst_size=3),
        )
        _rate_limiter.set_endpoint_limit(
            "batch",
            RateLimitConfig(requests_per_minute=5, burst_size=2),
        )

    return _rate_limiter
