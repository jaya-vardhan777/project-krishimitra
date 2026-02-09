"""
Caching utilities for low-bandwidth optimization and offline support.

This module provides intelligent caching with Redis (ElastiCache) and local SQLite
for offline-first data architecture.
"""

import json
import sqlite3
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional, Union
from enum import Enum

import redis
from redis.exceptions import RedisError

from .compression import DataCompressor, CompressionAlgorithm


class CacheBackend(Enum):
    """Cache backend options."""
    REDIS = "redis"
    SQLITE = "sqlite"
    MEMORY = "memory"


class CacheEntry:
    """Represents a cached entry with metadata."""
    
    def __init__(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        compressed: bool = False
    ):
        """
        Initialize cache entry.
        
        Args:
            key: Cache key
            value: Cached value
            ttl: Time-to-live in seconds
            compressed: Whether value is compressed
        """
        self.key = key
        self.value = value
        self.ttl = ttl
        self.compressed = compressed
        self.created_at = datetime.utcnow()
        self.expires_at = (
            self.created_at + timedelta(seconds=ttl) if ttl else None
        )
    
    def is_expired(self) -> bool:
        """Check if cache entry has expired."""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at


class RedisCache:
    """
    Redis-based caching for distributed scenarios.
    
    Uses Amazon ElastiCache for Redis in production.
    """
    
    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: Optional[str] = None,
        enable_compression: bool = True
    ):
        """
        Initialize Redis cache.
        
        Args:
            host: Redis host
            port: Redis port
            db: Redis database number
            password: Redis password
            enable_compression: Enable data compression
        """
        self.client = redis.Redis(
            host=host,
            port=port,
            db=db,
            password=password,
            decode_responses=False  # We handle encoding/decoding
        )
        self.enable_compression = enable_compression
        self.compressor = DataCompressor(
            algorithm=CompressionAlgorithm.GZIP
        ) if enable_compression else None
    
    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found
        """
        try:
            data = self.client.get(key)
            if data is None:
                return None
            
            # Decompress if needed
            if self.enable_compression and self.compressor:
                data = self.compressor.decompress_bytes(data)
            
            # Deserialize JSON
            return json.loads(data.decode('utf-8'))
        except RedisError:
            return None
    
    def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None
    ) -> bool:
        """
        Set value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Serialize to JSON
            data = json.dumps(value, separators=(',', ':')).encode('utf-8')
            
            # Compress if enabled
            if self.enable_compression and self.compressor:
                data = self.compressor.compress_bytes(data)
            
            # Store in Redis
            if ttl:
                return self.client.setex(key, ttl, data)
            else:
                return self.client.set(key, data)
        except RedisError:
            return False
    
    def delete(self, key: str) -> bool:
        """
        Delete value from cache.
        
        Args:
            key: Cache key
            
        Returns:
            True if deleted, False otherwise
        """
        try:
            return self.client.delete(key) > 0
        except RedisError:
            return False
    
    def exists(self, key: str) -> bool:
        """
        Check if key exists in cache.
        
        Args:
            key: Cache key
            
        Returns:
            True if exists, False otherwise
        """
        try:
            return self.client.exists(key) > 0
        except RedisError:
            return False
    
    def clear(self) -> bool:
        """
        Clear all cache entries.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            self.client.flushdb()
            return True
        except RedisError:
            return False


class SQLiteCache:
    """
    SQLite-based local caching for offline support.
    
    Provides persistent local storage for critical agricultural data.
    """
    
    def __init__(
        self,
        db_path: Union[str, Path] = "cache.db",
        enable_compression: bool = True
    ):
        """
        Initialize SQLite cache.
        
        Args:
            db_path: Path to SQLite database file
            enable_compression: Enable data compression
        """
        self.db_path = Path(db_path)
        self.enable_compression = enable_compression
        self.compressor = DataCompressor(
            algorithm=CompressionAlgorithm.GZIP
        ) if enable_compression else None
        
        self._init_db()
    
    def _init_db(self):
        """Initialize database schema."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cache (
                key TEXT PRIMARY KEY,
                value BLOB NOT NULL,
                created_at REAL NOT NULL,
                expires_at REAL,
                compressed INTEGER NOT NULL DEFAULT 0
            )
        """)
        
        # Create index on expires_at for efficient cleanup
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_expires_at 
            ON cache(expires_at)
        """)
        
        conn.commit()
        conn.close()
    
    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found or expired
        """
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT value, expires_at, compressed FROM cache WHERE key = ?",
            (key,)
        )
        row = cursor.fetchone()
        conn.close()
        
        if row is None:
            return None
        
        value_bytes, expires_at, compressed = row
        
        # Check expiration
        if expires_at and time.time() > expires_at:
            self.delete(key)
            return None
        
        # Decompress if needed
        if compressed and self.compressor:
            value_bytes = self.compressor.decompress_bytes(value_bytes)
        
        # Deserialize JSON
        return json.loads(value_bytes.decode('utf-8'))
    
    def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None
    ) -> bool:
        """
        Set value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Serialize to JSON
            data = json.dumps(value, separators=(',', ':')).encode('utf-8')
            
            # Compress if enabled
            compressed = 0
            if self.enable_compression and self.compressor:
                data = self.compressor.compress_bytes(data)
                compressed = 1
            
            # Calculate expiration
            created_at = time.time()
            expires_at = created_at + ttl if ttl else None
            
            # Store in SQLite
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT OR REPLACE INTO cache 
                (key, value, created_at, expires_at, compressed)
                VALUES (?, ?, ?, ?, ?)
            """, (key, data, created_at, expires_at, compressed))
            
            conn.commit()
            conn.close()
            
            return True
        except Exception:
            return False
    
    def delete(self, key: str) -> bool:
        """
        Delete value from cache.
        
        Args:
            key: Cache key
            
        Returns:
            True if deleted, False otherwise
        """
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            cursor.execute("DELETE FROM cache WHERE key = ?", (key,))
            deleted = cursor.rowcount > 0
            
            conn.commit()
            conn.close()
            
            return deleted
        except Exception:
            return False
    
    def exists(self, key: str) -> bool:
        """
        Check if key exists in cache.
        
        Args:
            key: Cache key
            
        Returns:
            True if exists and not expired, False otherwise
        """
        return self.get(key) is not None
    
    def clear(self) -> bool:
        """
        Clear all cache entries.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            cursor.execute("DELETE FROM cache")
            
            conn.commit()
            conn.close()
            
            return True
        except Exception:
            return False
    
    def cleanup_expired(self) -> int:
        """
        Remove expired cache entries.
        
        Returns:
            Number of entries removed
        """
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            current_time = time.time()
            cursor.execute(
                "DELETE FROM cache WHERE expires_at IS NOT NULL AND expires_at < ?",
                (current_time,)
            )
            deleted = cursor.rowcount
            
            conn.commit()
            conn.close()
            
            return deleted
        except Exception:
            return 0


class HybridCache:
    """
    Hybrid caching strategy using both Redis and SQLite.
    
    Uses Redis for fast distributed caching and SQLite for offline persistence.
    Automatically falls back to SQLite when Redis is unavailable.
    """
    
    def __init__(
        self,
        redis_host: str = "localhost",
        redis_port: int = 6379,
        redis_password: Optional[str] = None,
        sqlite_path: Union[str, Path] = "cache.db",
        enable_compression: bool = True
    ):
        """
        Initialize hybrid cache.
        
        Args:
            redis_host: Redis host
            redis_port: Redis port
            redis_password: Redis password
            sqlite_path: Path to SQLite database
            enable_compression: Enable data compression
        """
        self.redis_cache = RedisCache(
            host=redis_host,
            port=redis_port,
            password=redis_password,
            enable_compression=enable_compression
        )
        self.sqlite_cache = SQLiteCache(
            db_path=sqlite_path,
            enable_compression=enable_compression
        )
        self.redis_available = self._check_redis_availability()
    
    def _check_redis_availability(self) -> bool:
        """Check if Redis is available."""
        try:
            self.redis_cache.client.ping()
            return True
        except RedisError:
            return False
    
    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache (Redis first, then SQLite).
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found
        """
        # Try Redis first if available
        if self.redis_available:
            value = self.redis_cache.get(key)
            if value is not None:
                return value
        
        # Fall back to SQLite
        return self.sqlite_cache.get(key)
    
    def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        persist_offline: bool = True
    ) -> bool:
        """
        Set value in cache (both Redis and SQLite).
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds
            persist_offline: Also store in SQLite for offline access
            
        Returns:
            True if at least one backend succeeded
        """
        redis_success = False
        sqlite_success = False
        
        # Try Redis if available
        if self.redis_available:
            redis_success = self.redis_cache.set(key, value, ttl)
        
        # Always store in SQLite for offline access if requested
        if persist_offline:
            sqlite_success = self.sqlite_cache.set(key, value, ttl)
        
        return redis_success or sqlite_success
    
    def delete(self, key: str) -> bool:
        """
        Delete value from both caches.
        
        Args:
            key: Cache key
            
        Returns:
            True if deleted from at least one backend
        """
        redis_deleted = False
        sqlite_deleted = False
        
        if self.redis_available:
            redis_deleted = self.redis_cache.delete(key)
        
        sqlite_deleted = self.sqlite_cache.delete(key)
        
        return redis_deleted or sqlite_deleted
    
    def exists(self, key: str) -> bool:
        """
        Check if key exists in any cache.
        
        Args:
            key: Cache key
            
        Returns:
            True if exists in Redis or SQLite
        """
        if self.redis_available and self.redis_cache.exists(key):
            return True
        
        return self.sqlite_cache.exists(key)
