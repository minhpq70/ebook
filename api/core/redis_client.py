"""
Redis Client for Caching Infrastructure
- Connection pooling
- Cache management for embeddings, queries, metadata
- TTL management and invalidation
"""
import base64
import json
import logging
import zlib
from array import array
from functools import lru_cache
from redis.asyncio import Redis
from core.config import settings

logger = logging.getLogger("ebook.redis")


def _encode_embedding_payload(embedding: list[float]) -> str:
    """Compress embedding payload for Redis storage."""
    if not settings.embedding_cache_compression_enabled:
        rounded = [round(float(value), settings.embedding_cache_precision) for value in embedding]
        return json.dumps({"encoding": "json", "values": rounded})

    arr = array("f", (round(float(value), settings.embedding_cache_precision) for value in embedding))
    compressed = zlib.compress(arr.tobytes(), level=6)
    return json.dumps({
        "encoding": "zlib-f32",
        "values": base64.b64encode(compressed).decode("ascii"),
    })


def _decode_embedding_payload(payload: str) -> list[float]:
    """Decode embedding payload from Redis."""
    parsed = json.loads(payload)
    encoding = parsed.get("encoding")
    if encoding == "json":
        return [float(value) for value in parsed.get("values", [])]
    if encoding == "zlib-f32":
        raw = zlib.decompress(base64.b64decode(parsed["values"]))
        arr = array("f")
        arr.frombytes(raw)
        return [float(value) for value in arr]
    if isinstance(parsed, list):
        return [float(value) for value in parsed]
    return []


class CacheManager:
    """Redis-based caching manager with TTL and invalidation"""

    def __init__(self, redis_url: str):
        self.redis_url = redis_url
        self._redis: Redis | None = None

        # TTL configurations (seconds)
        self.embedding_ttl = 86400  # 24 hours
        self.query_ttl = 3600       # 1 hour
        self.metadata_ttl = 21600   # 6 hours
        self.cover_ttl = 604800     # 7 days

    async def get_redis(self) -> Redis:
        """Lazy initialization of Redis connection"""
        if self._redis is None:
            try:
                self._redis = Redis.from_url(
                    self.redis_url,
                    encoding="utf-8",
                    decode_responses=True,
                    max_connections=20,
                    retry_on_timeout=True,
                    socket_timeout=5,
                    socket_connect_timeout=5,
                    health_check_interval=30
                )
                await self._redis.ping()
                logger.info("Redis connection established")
            except Exception as e:
                logger.warning(f"Redis connection failed: {e}")
                self._redis = None
        return self._redis

    async def get_embedding(self, text: str) -> list[float] | None:
        """Get cached embedding or return None"""
        try:
            redis = await self.get_redis()
            if not redis:
                return None

            # Use hash for sharding and consistent key generation
            key = f"embed:{hash(text) % 10000}"
            cached = await redis.get(key)
            if cached:
                logger.debug(f"Cache hit for embedding: {key}")
                return _decode_embedding_payload(cached)
        except Exception as e:
            logger.warning(f"Error getting cached embedding: {e}")
        return None

    async def set_embedding(self, text: str, embedding: list[float]):
        """Cache embedding with TTL"""
        try:
            redis = await self.get_redis()
            if not redis:
                return

            key = f"embed:{hash(text) % 10000}"
            await redis.setex(key, self.embedding_ttl, _encode_embedding_payload(embedding))
            logger.debug(f"Cached embedding: {key}")
        except Exception as e:
            logger.warning(f"Error caching embedding: {e}")

    async def get_query_result(self, query_hash: str, book_id: str) -> dict | None:
        """Get cached query result"""
        try:
            redis = await self.get_redis()
            if not redis:
                return None

            key = f"query:{book_id}:{query_hash}"
            cached = await redis.get(key)
            if cached:
                logger.debug(f"Cache hit for query: {key}")
                return json.loads(cached)
        except Exception as e:
            logger.warning(f"Error getting cached query result: {e}")
        return None

    async def set_query_result(self, query_hash: str, book_id: str, result: dict):
        """Cache query result with TTL"""
        try:
            redis = await self.get_redis()
            if not redis:
                return

            key = f"query:{book_id}:{query_hash}"
            await redis.setex(key, self.query_ttl, json.dumps(result))
            logger.debug(f"Cached query result: {key}")
        except Exception as e:
            logger.warning(f"Error caching query result: {e}")

    async def get_query_expansion(self, query_hash: str) -> list[str] | None:
        """Get cached query expansion variants."""
        try:
            redis = await self.get_redis()
            if not redis:
                return None

            cached = await redis.get(f"query:expand:{query_hash}")
            if cached:
                return json.loads(cached)
        except Exception as e:
            logger.warning(f"Error getting cached query expansion: {e}")
        return None

    async def set_query_expansion(self, query_hash: str, variants: list[str]):
        """Cache query expansion variants with TTL."""
        try:
            redis = await self.get_redis()
            if not redis:
                return

            await redis.setex(
                f"query:expand:{query_hash}",
                settings.query_expansion_ttl,
                json.dumps(variants),
            )
        except Exception as e:
            logger.warning(f"Error caching query expansion: {e}")

    async def get_book_metadata(self, book_id: str) -> dict | None:
        """Get cached book metadata"""
        try:
            redis = await self.get_redis()
            if not redis:
                return None

            key = f"book:meta:{book_id}"
            cached = await redis.get(key)
            if cached:
                logger.debug(f"Cache hit for book metadata: {key}")
                return json.loads(cached)
        except Exception as e:
            logger.warning(f"Error getting cached book metadata: {e}")
        return None

    async def set_book_metadata(self, book_id: str, metadata: dict):
        """Cache book metadata with TTL"""
        try:
            redis = await self.get_redis()
            if not redis:
                return

            key = f"book:meta:{book_id}"
            await redis.setex(key, self.metadata_ttl, json.dumps(metadata))
            logger.debug(f"Cached book metadata: {key}")
        except Exception as e:
            logger.warning(f"Error caching book metadata: {e}")

    async def get_book_cover(self, book_id: str) -> str | None:
        """Get cached cover URL"""
        try:
            redis = await self.get_redis()
            if not redis:
                return None

            key = f"book:cover:{book_id}"
            cached = await redis.get(key)
            if cached:
                logger.debug(f"Cache hit for book cover: {key}")
                return cached
        except Exception as e:
            logger.warning(f"Error getting cached book cover: {e}")
        return None

    async def set_book_cover(self, book_id: str, cover_url: str):
        """Cache book cover URL with TTL"""
        try:
            redis = await self.get_redis()
            if not redis:
                return

            key = f"book:cover:{book_id}"
            await redis.setex(key, self.cover_ttl, cover_url)
            logger.debug(f"Cached book cover: {key}")
        except Exception as e:
            logger.warning(f"Error caching book cover: {e}")

    async def get_ingestion_progress(self, book_id: str) -> dict | None:
        """Get ingestion progress for a book."""
        try:
            redis = await self.get_redis()
            if not redis:
                return None

            key = f"ingestion:progress:{book_id}"
            cached = await redis.get(key)
            if cached:
                return json.loads(cached)
        except Exception as e:
            logger.warning(f"Error getting ingestion progress: {e}")
        return None

    async def set_ingestion_progress(self, book_id: str, progress: dict):
        """Cache ingestion progress with TTL."""
        try:
            redis = await self.get_redis()
            if not redis:
                return

            key = f"ingestion:progress:{book_id}"
            await redis.setex(key, settings.ingestion_progress_ttl, json.dumps(progress))
        except Exception as e:
            logger.warning(f"Error caching ingestion progress: {e}")

    async def clear_ingestion_progress(self, book_id: str):
        """Clear ingestion progress state."""
        try:
            redis = await self.get_redis()
            if not redis:
                return
            await redis.delete(f"ingestion:progress:{book_id}")
        except Exception as e:
            logger.warning(f"Error clearing ingestion progress: {e}")

    async def get_metrics_snapshot(self) -> dict | None:
        """Get persisted metrics snapshot."""
        try:
            redis = await self.get_redis()
            if not redis:
                return None
            cached = await redis.get("metrics:snapshot")
            if cached:
                return json.loads(cached)
        except Exception as e:
            logger.warning(f"Error getting metrics snapshot: {e}")
        return None

    async def set_metrics_snapshot(self, snapshot: dict):
        """Persist metrics snapshot with TTL."""
        try:
            redis = await self.get_redis()
            if not redis:
                return
            await redis.setex(
                "metrics:snapshot",
                settings.metrics_snapshot_ttl,
                json.dumps(snapshot),
            )
        except Exception as e:
            logger.warning(f"Error setting metrics snapshot: {e}")

    async def invalidate_book_cache(self, book_id: str):
        """Invalidate all caches for a book"""
        try:
            redis = await self.get_redis()
            if not redis:
                return

            # Delete all keys matching patterns
            patterns = [
                f"query:{book_id}:*",
                f"book:meta:{book_id}",
                f"book:cover:{book_id}",
                f"ingestion:progress:{book_id}",
            ]

            for pattern in patterns:
                keys = await redis.keys(pattern)
                if keys:
                    await redis.delete(*keys)
                    logger.info(f"Invalidated {len(keys)} cache keys for book {book_id}")

        except Exception as e:
            logger.warning(f"Error invalidating book cache: {e}")

    async def get_cache_stats(self) -> dict:
        """Get cache statistics"""
        try:
            redis = await self.get_redis()
            if not redis:
                return {"status": "disconnected"}

            info = await redis.info()
            return {
                "status": "connected",
                "used_memory": info.get("used_memory_human", "unknown"),
                "connected_clients": info.get("connected_clients", 0),
                "total_keys": await redis.dbsize()
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    async def clear_all_cache(self):
        """Clear all cache data (use with caution)"""
        try:
            redis = await self.get_redis()
            if redis:
                await redis.flushdb()
                logger.info("All cache cleared")
        except Exception as e:
            logger.warning(f"Error clearing cache: {e}")


@lru_cache(maxsize=1)
def get_cache_manager() -> CacheManager:
    """Get singleton cache manager instance"""
    return CacheManager(settings.redis_url)
