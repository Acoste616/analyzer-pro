import json
import hashlib
import asyncio
from typing import Dict, Any, Optional, Union
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass, asdict
import aiofiles
import aiofiles.os

from ..config.settings import settings_manager
from ..utils.logger import get_logger


@dataclass
class CacheEntry:
    key: str
    value: Any
    created_at: datetime
    expires_at: Optional[datetime] = None
    hit_count: int = 0
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class CacheManager:
    """Asynchronous cache manager for storing and retrieving analysis results."""
    
    def __init__(self, cache_dir: Optional[str] = None, default_ttl: int = 3600):
        self.settings = settings_manager.settings
        self.logger = get_logger(__name__)
        self.cache_dir = Path(cache_dir) if cache_dir else Path("data/cache")
        self.default_ttl = default_ttl  # seconds
        
        # In-memory cache for frequently accessed items
        self.memory_cache: Dict[str, CacheEntry] = {}
        self.max_memory_items = 1000
        
        # Statistics
        self.stats = {
            'hits': 0,
            'misses': 0,
            'writes': 0,
            'evictions': 0,
            'errors': 0
        }
        
        # Ensure cache directory exists
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def _generate_cache_key(self, content: str, provider: str = "", **kwargs) -> str:
        """Generate a cache key from content and parameters."""
        # Create a unique key based on content and parameters
        key_data = {
            'content_hash': hashlib.sha256(content.encode()).hexdigest()[:16],
            'provider': provider,
            'params': sorted(kwargs.items())
        }
        
        key_string = json.dumps(key_data, sort_keys=True)
        return hashlib.md5(key_string.encode()).hexdigest()
    
    def _get_cache_file_path(self, key: str) -> Path:
        """Get the file path for a cache key."""
        # Create subdirectories based on first 2 characters for better file system performance
        subdir = key[:2]
        cache_subdir = self.cache_dir / subdir
        cache_subdir.mkdir(exist_ok=True)
        return cache_subdir / f"{key}.json"
    
    async def get(self, key: str) -> Optional[Any]:
        """Get a value from cache."""
        try:
            # Check memory cache first
            if key in self.memory_cache:
                entry = self.memory_cache[key]
                if self._is_entry_valid(entry):
                    entry.hit_count += 1
                    self.stats['hits'] += 1
                    self.logger.debug(f"Cache hit (memory): {key}")
                    return entry.value
                else:
                    # Remove expired entry
                    del self.memory_cache[key]
            
            # Check disk cache
            cache_file = self._get_cache_file_path(key)
            if await aiofiles.os.path.exists(cache_file):
                async with aiofiles.open(cache_file, 'r') as f:
                    cache_data = json.loads(await f.read())
                
                entry = CacheEntry(
                    key=cache_data['key'],
                    value=cache_data['value'],
                    created_at=datetime.fromisoformat(cache_data['created_at']),
                    expires_at=datetime.fromisoformat(cache_data['expires_at']) if cache_data.get('expires_at') else None,
                    hit_count=cache_data.get('hit_count', 0),
                    metadata=cache_data.get('metadata', {})
                )
                
                if self._is_entry_valid(entry):
                    entry.hit_count += 1
                    self.stats['hits'] += 1
                    
                    # Add to memory cache if space available
                    if len(self.memory_cache) < self.max_memory_items:
                        self.memory_cache[key] = entry
                    
                    # Update hit count on disk
                    await self._update_entry_stats(cache_file, entry)
                    
                    self.logger.debug(f"Cache hit (disk): {key}")
                    return entry.value
                else:
                    # Remove expired file
                    await aiofiles.os.remove(cache_file)
            
            self.stats['misses'] += 1
            self.logger.debug(f"Cache miss: {key}")
            return None
            
        except Exception as e:
            self.stats['errors'] += 1
            self.logger.error(f"Error getting cache entry {key}: {str(e)}")
            return None
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set a value in cache."""
        try:
            ttl = ttl or self.default_ttl
            expires_at = datetime.now() + timedelta(seconds=ttl) if ttl > 0 else None
            
            entry = CacheEntry(
                key=key,
                value=value,
                created_at=datetime.now(),
                expires_at=expires_at,
                hit_count=0,
                metadata={'size_bytes': len(json.dumps(value, default=str))}
            )
            
            # Add to memory cache
            if len(self.memory_cache) >= self.max_memory_items:
                # Evict least recently used item
                await self._evict_lru()
            
            self.memory_cache[key] = entry
            
            # Write to disk
            cache_file = self._get_cache_file_path(key)
            cache_data = {
                'key': entry.key,
                'value': entry.value,
                'created_at': entry.created_at.isoformat(),
                'expires_at': entry.expires_at.isoformat() if entry.expires_at else None,
                'hit_count': entry.hit_count,
                'metadata': entry.metadata
            }
            
            async with aiofiles.open(cache_file, 'w') as f:
                await f.write(json.dumps(cache_data, default=str, indent=2))
            
            self.stats['writes'] += 1
            self.logger.debug(f"Cache set: {key}")
            return True
            
        except Exception as e:
            self.stats['errors'] += 1
            self.logger.error(f"Error setting cache entry {key}: {str(e)}")
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete a cache entry."""
        try:
            # Remove from memory cache
            if key in self.memory_cache:
                del self.memory_cache[key]
            
            # Remove from disk
            cache_file = self._get_cache_file_path(key)
            if await aiofiles.os.path.exists(cache_file):
                await aiofiles.os.remove(cache_file)
            
            self.logger.debug(f"Cache deleted: {key}")
            return True
            
        except Exception as e:
            self.stats['errors'] += 1
            self.logger.error(f"Error deleting cache entry {key}: {str(e)}")
            return False
    
    async def clear(self) -> bool:
        """Clear all cache entries."""
        try:
            # Clear memory cache
            self.memory_cache.clear()
            
            # Clear disk cache
            for cache_file in self.cache_dir.rglob("*.json"):
                await aiofiles.os.remove(cache_file)
            
            self.logger.info("Cache cleared")
            return True
            
        except Exception as e:
            self.stats['errors'] += 1
            self.logger.error(f"Error clearing cache: {str(e)}")
            return False
    
    async def get_cached_analysis(self, content: str, provider: str = "", **kwargs) -> Optional[Any]:
        """Get cached analysis result for content."""
        cache_key = self._generate_cache_key(content, provider, **kwargs)
        return await self.get(cache_key)
    
    async def cache_analysis(self, content: str, result: Any, provider: str = "", ttl: Optional[int] = None, **kwargs) -> bool:
        """Cache analysis result for content."""
        cache_key = self._generate_cache_key(content, provider, **kwargs)
        return await self.set(cache_key, result, ttl)
    
    def _is_entry_valid(self, entry: CacheEntry) -> bool:
        """Check if cache entry is still valid."""
        if entry.expires_at is None:
            return True
        return datetime.now() < entry.expires_at
    
    async def _evict_lru(self):
        """Evict least recently used item from memory cache."""
        if not self.memory_cache:
            return
        
        # Find entry with lowest hit count (simple LRU approximation)
        lru_key = min(self.memory_cache.keys(), key=lambda k: self.memory_cache[k].hit_count)
        del self.memory_cache[lru_key]
        self.stats['evictions'] += 1
    
    async def _update_entry_stats(self, cache_file: Path, entry: CacheEntry):
        """Update entry statistics on disk."""
        try:
            cache_data = {
                'key': entry.key,
                'value': entry.value,
                'created_at': entry.created_at.isoformat(),
                'expires_at': entry.expires_at.isoformat() if entry.expires_at else None,
                'hit_count': entry.hit_count,
                'metadata': entry.metadata
            }
            
            async with aiofiles.open(cache_file, 'w') as f:
                await f.write(json.dumps(cache_data, default=str, indent=2))
                
        except Exception as e:
            self.logger.warning(f"Error updating cache stats: {str(e)}")
    
    async def cleanup_expired(self) -> int:
        """Clean up expired cache entries."""
        cleaned_count = 0
        
        try:
            # Clean memory cache
            expired_keys = [
                key for key, entry in self.memory_cache.items()
                if not self._is_entry_valid(entry)
            ]
            
            for key in expired_keys:
                del self.memory_cache[key]
                cleaned_count += 1
            
            # Clean disk cache
            for cache_file in self.cache_dir.rglob("*.json"):
                try:
                    async with aiofiles.open(cache_file, 'r') as f:
                        cache_data = json.loads(await f.read())
                    
                    if cache_data.get('expires_at'):
                        expires_at = datetime.fromisoformat(cache_data['expires_at'])
                        if datetime.now() >= expires_at:
                            await aiofiles.os.remove(cache_file)
                            cleaned_count += 1
                            
                except Exception as e:
                    self.logger.warning(f"Error checking cache file {cache_file}: {str(e)}")
            
            self.logger.info(f"Cleaned up {cleaned_count} expired cache entries")
            return cleaned_count
            
        except Exception as e:
            self.logger.error(f"Error during cache cleanup: {str(e)}")
            return cleaned_count
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total_requests = self.stats['hits'] + self.stats['misses']
        hit_rate = (self.stats['hits'] / total_requests * 100) if total_requests > 0 else 0
        
        return {
            'hits': self.stats['hits'],
            'misses': self.stats['misses'],
            'writes': self.stats['writes'],
            'evictions': self.stats['evictions'],
            'errors': self.stats['errors'],
            'hit_rate_percentage': round(hit_rate, 2),
            'memory_cache_size': len(self.memory_cache),
            'max_memory_items': self.max_memory_items
        }
    
    async def get_cache_size(self) -> Dict[str, Any]:
        """Get cache size information."""
        try:
            disk_files = 0
            total_size = 0
            
            for cache_file in self.cache_dir.rglob("*.json"):
                disk_files += 1
                stat = await aiofiles.os.stat(cache_file)
                total_size += stat.st_size
            
            return {
                'disk_files': disk_files,
                'disk_size_bytes': total_size,
                'disk_size_mb': round(total_size / (1024 * 1024), 2),
                'memory_entries': len(self.memory_cache)
            }
            
        except Exception as e:
            self.logger.error(f"Error getting cache size: {str(e)}")
            return {
                'disk_files': 0,
                'disk_size_bytes': 0,
                'disk_size_mb': 0,
                'memory_entries': len(self.memory_cache)
            }


# Global cache instance
cache_manager = CacheManager()