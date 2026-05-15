"""Unit tests for cache_service module."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.cache_service import (
    CACHE_VERSION,
    CacheError,
    CacheResult,
    CacheService,
    get_cache_service,
)


class TestCacheResult:
    """Tests for CacheResult class."""

    def test_cache_result_hit(self):
        """Test cache result with hit."""
        result = CacheResult(
            hit=True,
            data={"fields": {"vendor": "Test"}},
            cache_key="cache_abc123",
            age_hours=2.5,
        )
        assert result.hit is True
        assert result.data["fields"]["vendor"] == "Test"
        assert result.age_hours == 2.5

    def test_cache_result_miss(self):
        """Test cache result with miss."""
        result = CacheResult(hit=False, cache_key="cache_xyz789")
        assert result.hit is False
        assert result.data is None
        assert result.age_hours is None

    def test_is_fresh_true(self):
        """Test is_fresh returns True for recent entries."""
        result = CacheResult(hit=True, data={}, cache_key="key", age_hours=12.0)
        assert result.is_fresh is True

    def test_is_fresh_false_old(self):
        """Test is_fresh returns False for old entries."""
        result = CacheResult(hit=True, data={}, cache_key="key", age_hours=48.0)
        assert result.is_fresh is False

    def test_is_fresh_false_no_age(self):
        """Test is_fresh returns False when age is None."""
        result = CacheResult(hit=True, data={}, cache_key="key")
        assert result.is_fresh is False


class TestCacheError:
    """Tests for CacheError class."""

    def test_cache_error_creation(self):
        """Test CacheError creation."""
        error = CacheError("write", "Connection timeout")
        assert error.operation == "write"
        assert error.reason == "Connection timeout"
        assert "Cache write failed" in str(error)


class TestCacheService:
    """Tests for CacheService class."""

    @pytest.fixture
    def mock_cosmos(self):
        """Create mock cosmos service."""
        cosmos = MagicMock()
        cosmos.query_documents = AsyncMock(return_value=[])
        cosmos.save_document_result = AsyncMock()
        cosmos.delete_document = AsyncMock(return_value=True)
        return cosmos

    @pytest.fixture
    def cache_service(self, mock_cosmos):
        """Create cache service with mock cosmos."""
        return CacheService(cosmos_service=mock_cosmos, cache_ttl_days=30)

    def test_init(self, mock_cosmos):
        """Test cache service initialization."""
        service = CacheService(mock_cosmos, cache_ttl_days=7)
        assert service.cache_ttl_days == 7
        assert service.cosmos_service == mock_cosmos

    def test_generate_content_hash(self, cache_service):
        """Test content hash generation."""
        content = b"PDF content here"
        hash1 = cache_service.generate_content_hash(content)
        hash2 = cache_service.generate_content_hash(content)

        assert hash1 == hash2
        assert len(hash1) == 32

    def test_generate_content_hash_different_content(self, cache_service):
        """Test different content produces different hashes."""
        hash1 = cache_service.generate_content_hash(b"Content A")
        hash2 = cache_service.generate_content_hash(b"Content B")

        assert hash1 != hash2

    def test_generate_cache_key(self, cache_service):
        """Test cache key generation."""
        key = cache_service.generate_cache_key(
            content_hash="abc123def456",
            model_id="prebuilt-invoice",
            pages_per_form=2,
        )

        assert key.startswith("cache_")
        assert len(key) == 30  # "cache_" + 24 chars

    def test_generate_cache_key_consistency(self, cache_service):
        """Test same inputs produce same cache key."""
        key1 = cache_service.generate_cache_key("hash123", "model-a")
        key2 = cache_service.generate_cache_key("hash123", "model-a")

        assert key1 == key2

    def test_generate_cache_key_different_model(self, cache_service):
        """Test different models produce different keys."""
        key1 = cache_service.generate_cache_key("hash123", "model-a")
        key2 = cache_service.generate_cache_key("hash123", "model-b")

        assert key1 != key2


class TestCacheServiceGet:
    """Tests for CacheService.get method."""

    @pytest.fixture
    def mock_cosmos(self):
        """Create mock cosmos service."""
        return MagicMock()

    @pytest.fixture
    def cache_service(self, mock_cosmos):
        """Create cache service with mock cosmos."""
        return CacheService(cosmos_service=mock_cosmos)

    @pytest.mark.asyncio
    async def test_get_cache_miss(self, cache_service, mock_cosmos):
        """Test cache miss returns empty result."""
        mock_cosmos.query_documents = AsyncMock(return_value=[])

        result = await cache_service.get(
            content_hash="abc123",
            model_id="prebuilt-invoice",
        )

        assert result.hit is False
        assert result.data is None
        assert cache_service._stats["misses"] == 1

    @pytest.mark.asyncio
    async def test_get_cache_hit(self, cache_service, mock_cosmos):
        """Test cache hit returns cached data."""
        cached_entry = {
            "cacheKey": "cache_abc123",
            "cachedAt": datetime.now(timezone.utc).isoformat(),
            "expiresAt": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
            "extractionResult": {"fields": {"vendor": "Test Corp"}},
        }
        mock_cosmos.query_documents = AsyncMock(return_value=[cached_entry])

        result = await cache_service.get(
            content_hash="abc123",
            model_id="prebuilt-invoice",
        )

        assert result.hit is True
        assert result.data["fields"]["vendor"] == "Test Corp"
        assert cache_service._stats["hits"] == 1

    @pytest.mark.asyncio
    async def test_get_cache_expired(self, cache_service, mock_cosmos):
        """Test expired cache entry returns miss."""
        cached_entry = {
            "cacheKey": "cache_abc123",
            "cachedAt": (datetime.now(timezone.utc) - timedelta(days=60)).isoformat(),
            "expiresAt": (datetime.now(timezone.utc) - timedelta(days=30)).isoformat(),
            "extractionResult": {"fields": {}},
        }
        mock_cosmos.query_documents = AsyncMock(return_value=[cached_entry])

        result = await cache_service.get(
            content_hash="abc123",
            model_id="prebuilt-invoice",
        )

        assert result.hit is False
        assert cache_service._stats["misses"] == 1

    @pytest.mark.asyncio
    async def test_get_cache_error(self, cache_service, mock_cosmos):
        """Test cache lookup error returns miss gracefully."""
        mock_cosmos.query_documents = AsyncMock(side_effect=Exception("DB error"))

        result = await cache_service.get(
            content_hash="abc123",
            model_id="prebuilt-invoice",
        )

        assert result.hit is False
        assert cache_service._stats["misses"] == 1


class TestCacheServiceSet:
    """Tests for CacheService.set method."""

    @pytest.fixture
    def mock_cosmos(self):
        """Create mock cosmos service."""
        cosmos = MagicMock()
        cosmos.save_document_result = AsyncMock()
        return cosmos

    @pytest.fixture
    def cache_service(self, mock_cosmos):
        """Create cache service with mock cosmos."""
        return CacheService(cosmos_service=mock_cosmos)

    @pytest.mark.asyncio
    async def test_set_cache_entry(self, cache_service, mock_cosmos):
        """Test storing cache entry."""
        extraction_result = {"fields": {"vendor": "Test"}, "status": "completed"}

        cache_key = await cache_service.set(
            content_hash="abc123",
            model_id="prebuilt-invoice",
            extraction_result=extraction_result,
            source_file="test/doc.pdf",
        )

        assert cache_key.startswith("cache_")
        assert cache_service._stats["writes"] == 1
        mock_cosmos.save_document_result.assert_called_once()

        # Verify saved document structure
        saved_doc = mock_cosmos.save_document_result.call_args[0][0]
        assert saved_doc["cacheKey"] == cache_key
        assert saved_doc["contentHash"] == "abc123"
        assert saved_doc["modelId"] == "prebuilt-invoice"
        assert saved_doc["cacheVersion"] == CACHE_VERSION
        assert "cachedAt" in saved_doc
        assert "expiresAt" in saved_doc
        assert "ttl" in saved_doc

    @pytest.mark.asyncio
    async def test_set_cache_entry_with_metadata(self, cache_service, mock_cosmos):
        """Test storing cache entry with metadata."""
        cache_key = await cache_service.set(
            content_hash="abc123",
            model_id="prebuilt-invoice",
            extraction_result={"status": "completed"},
            source_file="test/doc.pdf",
            metadata={"custom": "value"},
        )

        saved_doc = mock_cosmos.save_document_result.call_args[0][0]
        assert saved_doc["metadata"]["custom"] == "value"

    @pytest.mark.asyncio
    async def test_set_cache_error(self, cache_service, mock_cosmos):
        """Test cache write error raises CacheError."""
        mock_cosmos.save_document_result = AsyncMock(side_effect=Exception("Write failed"))

        with pytest.raises(CacheError) as exc_info:
            await cache_service.set(
                content_hash="abc123",
                model_id="prebuilt-invoice",
                extraction_result={"status": "completed"},
                source_file="test/doc.pdf",
            )

        assert exc_info.value.operation == "write"


class TestCacheServiceInvalidate:
    """Tests for CacheService.invalidate method."""

    @pytest.fixture
    def mock_cosmos(self):
        """Create mock cosmos service."""
        cosmos = MagicMock()
        cosmos.delete_document = AsyncMock(return_value=True)
        cosmos.query_documents = AsyncMock(return_value=[])
        return cosmos

    @pytest.fixture
    def cache_service(self, mock_cosmos):
        """Create cache service with mock cosmos."""
        return CacheService(cosmos_service=mock_cosmos)

    @pytest.mark.asyncio
    async def test_invalidate_existing(self, cache_service, mock_cosmos):
        """Test invalidating existing cache entry."""
        result = await cache_service.invalidate(
            content_hash="abc123",
            model_id="prebuilt-invoice",
        )

        assert result is True
        assert cache_service._stats["invalidations"] == 1

    @pytest.mark.asyncio
    async def test_invalidate_not_found(self, cache_service, mock_cosmos):
        """Test invalidating non-existent entry."""
        mock_cosmos.delete_document = AsyncMock(return_value=False)

        result = await cache_service.invalidate(
            content_hash="nonexistent",
            model_id="prebuilt-invoice",
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_invalidate_by_model(self, cache_service, mock_cosmos):
        """Test invalidating all entries for a model."""
        mock_cosmos.query_documents = AsyncMock(return_value=[
            {"id": "cache_1", "sourceFile": "_cache/cache_1"},
            {"id": "cache_2", "sourceFile": "_cache/cache_2"},
        ])

        count = await cache_service.invalidate_by_model("prebuilt-invoice")

        assert count == 2
        assert cache_service._stats["invalidations"] == 2


class TestCacheServiceGetOrProcess:
    """Tests for CacheService.get_or_process method."""

    @pytest.fixture
    def mock_cosmos(self):
        """Create mock cosmos service."""
        cosmos = MagicMock()
        cosmos.query_documents = AsyncMock(return_value=[])
        cosmos.save_document_result = AsyncMock()
        return cosmos

    @pytest.fixture
    def cache_service(self, mock_cosmos):
        """Create cache service with mock cosmos."""
        return CacheService(cosmos_service=mock_cosmos)

    @pytest.mark.asyncio
    async def test_get_or_process_cache_hit(self, cache_service, mock_cosmos):
        """Test get_or_process returns cached result on hit."""
        cached_entry = {
            "cachedAt": datetime.now(timezone.utc).isoformat(),
            "expiresAt": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
            "extractionResult": {"fields": {"cached": True}, "status": "completed"},
        }
        mock_cosmos.query_documents = AsyncMock(return_value=[cached_entry])

        process_func = AsyncMock(return_value={"fields": {"processed": True}})

        result, from_cache = await cache_service.get_or_process(
            content=b"PDF content",
            model_id="prebuilt-invoice",
            process_func=process_func,
            source_file="test/doc.pdf",
        )

        assert from_cache is True
        assert result["fields"]["cached"] is True
        process_func.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_or_process_cache_miss(self, cache_service, mock_cosmos):
        """Test get_or_process calls process_func on miss."""
        mock_cosmos.query_documents = AsyncMock(return_value=[])
        process_func = AsyncMock(return_value={
            "fields": {"processed": True},
            "status": "completed",
        })

        result, from_cache = await cache_service.get_or_process(
            content=b"PDF content",
            model_id="prebuilt-invoice",
            process_func=process_func,
            source_file="test/doc.pdf",
        )

        assert from_cache is False
        assert result["fields"]["processed"] is True
        process_func.assert_called_once()
        mock_cosmos.save_document_result.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_or_process_failed_not_cached(self, cache_service, mock_cosmos):
        """Test failed results are not cached."""
        mock_cosmos.query_documents = AsyncMock(return_value=[])
        process_func = AsyncMock(return_value={
            "fields": {},
            "status": "failed",
            "error": "Processing failed",
        })

        result, from_cache = await cache_service.get_or_process(
            content=b"PDF content",
            model_id="prebuilt-invoice",
            process_func=process_func,
            source_file="test/doc.pdf",
        )

        assert from_cache is False
        assert result["status"] == "failed"
        mock_cosmos.save_document_result.assert_not_called()


class TestCacheServiceStats:
    """Tests for cache statistics."""

    @pytest.fixture
    def cache_service(self):
        """Create cache service with mock cosmos."""
        mock_cosmos = MagicMock()
        mock_cosmos.query_documents = AsyncMock(return_value=[])
        return CacheService(cosmos_service=mock_cosmos)

    def test_get_stats_initial(self, cache_service):
        """Test initial stats are zero."""
        stats = cache_service.get_stats()
        assert stats["hits"] == 0
        assert stats["misses"] == 0
        assert stats["writes"] == 0
        assert stats["hit_rate_percent"] == 0

    @pytest.mark.asyncio
    async def test_get_stats_after_operations(self, cache_service):
        """Test stats after cache operations."""
        # Simulate some operations
        await cache_service.get("hash1", "model")
        await cache_service.get("hash2", "model")
        cache_service._stats["hits"] = 1
        cache_service._stats["misses"] = 1

        stats = cache_service.get_stats()
        assert stats["total_lookups"] == 2
        assert stats["hit_rate_percent"] == 50.0

    def test_reset_stats(self, cache_service):
        """Test resetting statistics."""
        cache_service._stats["hits"] = 10
        cache_service._stats["misses"] = 5

        cache_service.reset_stats()

        stats = cache_service.get_stats()
        assert stats["hits"] == 0
        assert stats["misses"] == 0


class TestGetCacheServiceSingleton:
    """Tests for get_cache_service singleton function."""

    def test_get_cache_service_creates_singleton(self):
        """Test singleton creation."""
        import services.cache_service as cache_module

        # Reset singleton
        cache_module._cache_service = None

        mock_cosmos = MagicMock()
        service1 = get_cache_service(mock_cosmos)
        service2 = get_cache_service(mock_cosmos)

        assert service1 is service2

        # Cleanup
        cache_module._cache_service = None
