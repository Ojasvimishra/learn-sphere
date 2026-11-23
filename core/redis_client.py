"""
LearnSphere - Unified Cache, Rate Limiter & Token Revocation Client
Connects to Redis when available; falls back to thread-safe in-memory store with TTL.
"""

import os
import time
import threading
from typing import Any, Optional, Set
from collections import defaultdict, deque

try:
    import redis
    _HAS_REDIS = True
except ImportError:
    _HAS_REDIS = False


class InMemoryStore:
    """Thread-safe in-memory key-value store with TTL and set operations."""
    def __init__(self):
        self._data = {}
        self._expires = {}
        self._sets = defaultdict(set)
        self._lock = threading.RLock()

    def _purge_expired(self, key: str) -> bool:
        if key in self._expires:
            if time.time() > self._expires[key]:
                self._data.pop(key, None)
                self._expires.pop(key, None)
                self._sets.pop(key, None)
                return True
        return False

    def get(self, key: str) -> Optional[str]:
        with self._lock:
            if self._purge_expired(key):
                return None
            return self._data.get(key)

    def set(self, key: str, value: str, ex: Optional[int] = None) -> bool:
        with self._lock:
            self._data[key] = str(value)
            if ex:
                self._expires[key] = time.time() + ex
            else:
                self._expires.pop(key, None)
            return True

    def delete(self, key: str) -> bool:
        with self._lock:
            removed = (key in self._data or key in self._sets)
            self._data.pop(key, None)
            self._expires.pop(key, None)
            self._sets.pop(key, None)
            return removed

    def exists(self, key: str) -> bool:
        with self._lock:
            if self._purge_expired(key):
                return False
            return key in self._data or key in self._sets

    def incr(self, key: str) -> int:
        with self._lock:
            self._purge_expired(key)
            val = int(self._data.get(key, 0)) + 1
            self._data[key] = str(val)
            return val

    def expire(self, key: str, seconds: int) -> bool:
        with self._lock:
            if key in self._data or key in self._sets:
                self._expires[key] = time.time() + seconds
                return True
            return False

    def sadd(self, key: str, *members: str) -> int:
        with self._lock:
            self._purge_expired(key)
            count = 0
            for m in members:
                if m not in self._sets[key]:
                    self._sets[key].add(str(m))
                    count += 1
            return count

    def sismember(self, key: str, member: str) -> bool:
        with self._lock:
            if self._purge_expired(key):
                return False
            return str(member) in self._sets[key]

    def srem(self, key: str, *members: str) -> int:
        with self._lock:
            self._purge_expired(key)
            count = 0
            for m in members:
                if str(m) in self._sets[key]:
                    self._sets[key].remove(str(m))
                    count += 1
            return count


class CacheManager:
    """Singleton cache & token revocation manager."""
    _instance = None
    _lock = threading.Lock()

    def __init__(self):
        self.redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self._redis_client = None
        self._fallback_store = InMemoryStore()
        self._using_redis = False
        self._init_backend()

    def _init_backend(self):
        if _HAS_REDIS:
            try:
                client = redis.Redis.from_url(
                    self.redis_url,
                    socket_connect_timeout=1,
                    socket_timeout=2,
                    decode_responses=True
                )
                client.ping()
                self._redis_client = client
                self._using_redis = True
            except Exception:
                self._redis_client = None
                self._using_redis = False
        else:
            self._redis_client = None
            self._using_redis = False

    @property
    def is_redis_active(self) -> bool:
        return self._using_redis

    def get(self, key: str) -> Optional[str]:
        if self._using_redis and self._redis_client:
            try:
                return self._redis_client.get(key)
            except Exception:
                pass
        return self._fallback_store.get(key)

    def set(self, key: str, value: str, ex: Optional[int] = None) -> bool:
        if self._using_redis and self._redis_client:
            try:
                return bool(self._redis_client.set(key, value, ex=ex))
            except Exception:
                pass
        return self._fallback_store.set(key, value, ex=ex)

    def delete(self, key: str) -> bool:
        if self._using_redis and self._redis_client:
            try:
                return bool(self._redis_client.delete(key))
            except Exception:
                pass
        return self._fallback_store.delete(key)

    def exists(self, key: str) -> bool:
        if self._using_redis and self._redis_client:
            try:
                return bool(self._redis_client.exists(key))
            except Exception:
                pass
        return self._fallback_store.exists(key)

    def incr(self, key: str) -> int:
        if self._using_redis and self._redis_client:
            try:
                return self._redis_client.incr(key)
            except Exception:
                pass
        return self._fallback_store.incr(key)

    def expire(self, key: str, seconds: int) -> bool:
        if self._using_redis and self._redis_client:
            try:
                return bool(self._redis_client.expire(key, seconds))
            except Exception:
                pass
        return self._fallback_store.expire(key, seconds)

    def sadd(self, key: str, *members: str) -> int:
        if self._using_redis and self._redis_client:
            try:
                return self._redis_client.sadd(key, *members)
            except Exception:
                pass
        return self._fallback_store.sadd(key, *members)

    def sismember(self, key: str, member: str) -> bool:
        if self._using_redis and self._redis_client:
            try:
                return bool(self._redis_client.sismember(key, member))
            except Exception:
                pass
        return self._fallback_store.sismember(key, member)

    def srem(self, key: str, *members: str) -> int:
        if self._using_redis and self._redis_client:
            try:
                return self._redis_client.srem(key, *members)
            except Exception:
                pass
        return self._fallback_store.srem(key, *members)


def get_cache_client() -> CacheManager:
    """Returns singleton cache manager."""
    if CacheManager._instance is None:
        with CacheManager._lock:
            if CacheManager._instance is None:
                CacheManager._instance = CacheManager()
    return CacheManager._instance
