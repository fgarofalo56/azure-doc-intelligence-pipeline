"""Caching service for Document Intelligence extraction results.

Implements a caching layer using Cosmos DB to avoid reprocessing identical documents.
Uses content hash as cache key for content-based deduplication.
"""

import hashlib
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger(__name__)

# Cache configuration
DEFAULT_CACHE_TTL_DAYS = 30  # Default cache validity period
CACHE_VERSION = "1.0"  # Increment when extraction logic changes


class CacheError(Exception):
    """Raised when cache operations fail."""

    def __init__(self, operation: str, reason: str) -> None:
        self.operation = operation
        self.reason = reason
        super().__init__(f"Cache {operation} failed: {reason}")


class CacheResult:
    """Result of a cache lookup."""

    def __init__(
        self,
        hit: bool,
        data: dict[str, Any] | None = None,
        cache_key: str = "",
        age_hours: float | None = None,
    ):
        self.hit = hit
        self.data = data
        self.cache_key = cache_key
        self.age_hours = age_hours

    @property
    def is_fresh(self) -> bool:
        """Check if cache entry is still fresh (less than 24 hours old)."""
        if self.age_hours is None:
            return False
        return self.age_hours < 24


class CacheService:
    """Service for caching Document Intelligence extraction results.

    Uses Cosmos DB as the cache store with content-based keys.
    Supports TTL-based expiration and version-based invalidation.
    """

    def __init__(
        self,
        cosmos_service: Any,
        cache_ttl_days: int = DEFAULT_CACHE_TTL_DAYS,
        cache_container: str | None = None,
    ) -> None:
        """Initialize Cache Service.

        Args:
            cosmos_service: CosmosService instance for storage.
            cache_ttl_days: Days until cache entries expire.
            cache_container: Optional separate container for cache (uses default if None).
        """
        self.cosmos_service = cosmos_service
        self.cache_ttl_days = cache_ttl_days
        self.cache_container = cache_container
        self._stats = {"hits": 0, "misses": 0, "writes": 0, "invalidations": 0}

    def generate_cache_key(
        self,
        content_hash: str,
        model_id: str,
        pages_per_form: int | None = None,
    ) -> str:
        """Generate a cache key based on content and processing parameters.

        Args:
            content_hash: Hash of the document content.
            model_id: Document Intelligence model ID.
            pages_per_form: Pages per form configuration.

        Returns:
            str: Cache key (SHA256 hash).
        """
        components = [
            content_hash,
            model_id,
            str(pages_per_form or "all"),
            CACHE_VERSION,
        ]
        key_input = "|".join(components)
        return f"cache_{hashlib.sha256(key_input.encode()).hexdigest()[:24]}"

    def generate_content_hash(self, content: bytes) -> str:
        """Generate a hash of document content.

        Args:
            content: PDF file bytes.

        Returns:
            str: SHA256 hash of content (32 chars).
        """
        return hashlib.sha256(content).hexdigest()[:32]

    async def get(
        self,
        content_hash: str,
        model_id: str,
        pages_per_form: int | None = None,
    ) -> CacheResult:
        """Retrieve cached extraction result.

        Args:
            content_hash: Hash of document content.
            model_id: Document Intelligence model ID.
            pages_per_form: Pages per form configuration.

        Returns:
            CacheResult: Cache lookup result with data if found.
        """
        cache_key = self.generate_cache_key(content_hash, model_id, pages_per_form)

        try:
            # Query for cache entry
            query = """
                SELECT * FROM c
                WHERE c.cacheKey = @cacheKey
                AND c.cacheVersion = @version
                AND c.status = 'completed'
            """
            parameters = [
                {"name": "@cacheKey", "value": cache_key},
                {"name": "@version", "value": CACHE_VERSION},
            ]

            # Use content hash as partition key for efficient lookup
            docs = await self.cosmos_service.query_documents(
                query=query,
                parameters=parameters,
            )

            if not docs:
                self._stats["misses"] += 1
                logger.debug(f"Cache miss for key: {cache_key}")
                return CacheResult(hit=False, cache_key=cache_key)

            cached = docs[0]

            # Check if cache entry has expired
            if self._is_expired(cached):
                self._stats["misses"] += 1
                logger.info(f"Cache entry expired for key: {cache_key}")
                return CacheResult(hit=False, cache_key=cache_key)

            # Calculate age
            cached_at = datetime.fromisoformat(cached.get("cachedAt", "").replace("Z", "+00:00"))
            age = datetime.now(timezone.utc) - cached_at
            age_hours = age.total_seconds() / 3600

            self._stats["hits"] += 1
            logger.info(f"Cache hit for key: {cache_key} (age: {age_hours:.1f}h)")

            return CacheResult(
                hit=True,
                data=cached.get("extractionResult"),
                cache_key=cache_key,
                age_hours=age_hours,
            )

        except Exception as e:
            logger.warning(f"Cache lookup failed: {e}")
            self._stats["misses"] += 1
            return CacheResult(hit=False, cache_key=cache_key)

    async def set(
        self,
        content_hash: str,
        model_id: str,
        extraction_result: dict[str, Any],
        source_file: str,
        pages_per_form: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Store extraction result in cache.

        Args:
            content_hash: Hash of document content.
            model_id: Document Intelligence model ID.
            extraction_result: Extraction result to cache.
            source_file: Original source file path.
            pages_per_form: Pages per form configuration.
            metadata: Optional additional metadata.

        Returns:
            str: Cache key of stored entry.

        Raises:
            CacheError: If cache write fails.
        """
        cache_key = self.generate_cache_key(content_hash, model_id, pages_per_form)
        now = datetime.now(timezone.utc)

        cache_entry = {
            "id": cache_key,
            "sourceFile": f"_cache/{cache_key}",  # Use cache prefix for partition
            "cacheKey": cache_key,
            "contentHash": content_hash,
            "modelId": model_id,
            "pagesPerForm": pages_per_form,
            "cacheVersion": CACHE_VERSION,
            "cachedAt": now.isoformat(),
            "expiresAt": (now + timedelta(days=self.cache_ttl_days)).isoformat(),
            "extractionResult": extraction_result,
            "originalSourceFile": source_file,
            "status": "completed",
            "ttl": int((now + timedelta(days=self.cache_ttl_days)).timestamp()),  # For Cosmos TTL
        }

        if metadata:
            cache_entry["metadata"] = metadata

        try:
            await self.cosmos_service.save_document_result(cache_entry)
            self._stats["writes"] += 1
            logger.info(f"Cached extraction result with key: {cache_key}")
            return cache_key

        except Exception as e:
            logger.error(f"Cache write failed: {e}")
            raise CacheError("write", str(e)) from e

    async def invalidate(
        self,
        content_hash: str,
        model_id: str,
        pages_per_form: int | None = None,
    ) -> bool:
        """Invalidate a cache entry.

        Args:
            content_hash: Hash of document content.
            model_id: Document Intelligence model ID.
            pages_per_form: Pages per form configuration.

        Returns:
            bool: True if entry was invalidated, False if not found.
        """
        cache_key = self.generate_cache_key(content_hash, model_id, pages_per_form)

        try:
            deleted = await self.cosmos_service.delete_document(
                doc_id=cache_key,
                partition_key=f"_cache/{cache_key}",
            )
            if deleted:
                self._stats["invalidations"] += 1
                logger.info(f"Invalidated cache entry: {cache_key}")
            return deleted

        except Exception as e:
            logger.warning(f"Cache invalidation failed: {e}")
            return False

    async def invalidate_by_model(self, model_id: str) -> int:
        """Invalidate all cache entries for a specific model.

        Useful when a model is updated/retrained.

        Args:
            model_id: Document Intelligence model ID.

        Returns:
            int: Number of entries invalidated.
        """
        try:
            query = """
                SELECT c.id, c.sourceFile FROM c
                WHERE c.modelId = @modelId
                AND STARTSWITH(c.sourceFile, '_cache/')
            """
            parameters = [{"name": "@modelId", "value": model_id}]

            docs = await self.cosmos_service.query_documents(
                query=query,
                parameters=parameters,
            )

            count = 0
            for doc in docs:
                try:
                    await self.cosmos_service.delete_document(
                        doc_id=doc["id"],
                        partition_key=doc["sourceFile"],
                    )
                    count += 1
                except Exception:
                    pass  # Continue with other deletions

            self._stats["invalidations"] += count
            logger.info(f"Invalidated {count} cache entries for model: {model_id}")
            return count

        except Exception as e:
            logger.error(f"Bulk cache invalidation failed: {e}")
            return 0

    async def get_or_process(
        self,
        content: bytes,
        model_id: str,
        process_func: Any,
        source_file: str,
        pages_per_form: int | None = None,
        **process_kwargs: Any,
    ) -> tuple[dict[str, Any], bool]:
        """Get from cache or process and cache result.

        This is the main entry point for cache-aware processing.

        Args:
            content: PDF file bytes.
            model_id: Document Intelligence model ID.
            process_func: Async function to call if cache miss.
            source_file: Original source file path.
            pages_per_form: Pages per form configuration.
            **process_kwargs: Additional kwargs for process_func.

        Returns:
            tuple: (extraction_result, from_cache) - result and whether it came from cache.
        """
        content_hash = self.generate_content_hash(content)

        # Check cache first
        cache_result = await self.get(content_hash, model_id, pages_per_form)

        if cache_result.hit and cache_result.data:
            logger.info(
                f"Using cached result for {source_file} (age: {cache_result.age_hours:.1f}h)"
            )
            return cache_result.data, True

        # Process document
        logger.info(f"Cache miss, processing {source_file}")
        result = await process_func(**process_kwargs)

        # Cache the result if successful
        if result.get("status") == "completed":
            try:
                await self.set(
                    content_hash=content_hash,
                    model_id=model_id,
                    extraction_result=result,
                    source_file=source_file,
                    pages_per_form=pages_per_form,
                    metadata={"processed_at": datetime.now(timezone.utc).isoformat()},
                )
            except CacheError:
                pass  # Don't fail processing if caching fails

        return result, False

    def _is_expired(self, cache_entry: dict[str, Any]) -> bool:
        """Check if a cache entry has expired.

        Args:
            cache_entry: Cache entry document.

        Returns:
            bool: True if expired.
        """
        expires_at = cache_entry.get("expiresAt")
        if not expires_at:
            return False

        try:
            expiry = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            return datetime.now(timezone.utc) > expiry
        except ValueError:
            return False

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            dict: Cache hit/miss statistics.
        """
        total = self._stats["hits"] + self._stats["misses"]
        hit_rate = (self._stats["hits"] / total * 100) if total > 0 else 0

        return {
            "hits": self._stats["hits"],
            "misses": self._stats["misses"],
            "writes": self._stats["writes"],
            "invalidations": self._stats["invalidations"],
            "total_lookups": total,
            "hit_rate_percent": round(hit_rate, 2),
        }

    def reset_stats(self) -> None:
        """Reset cache statistics."""
        self._stats = {"hits": 0, "misses": 0, "writes": 0, "invalidations": 0}


# Singleton instance
_cache_service: CacheService | None = None


def get_cache_service(cosmos_service: Any, **kwargs: Any) -> CacheService:
    """Get or create singleton CacheService instance.

    Args:
        cosmos_service: CosmosService instance.
        **kwargs: Additional CacheService constructor args.

    Returns:
        CacheService: Singleton instance.
    """
    global _cache_service
    if _cache_service is None:
        _cache_service = CacheService(cosmos_service, **kwargs)
    return _cache_service
