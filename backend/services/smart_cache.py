"""
Improved cache system with smart TTL and data age indicators.
"""
import sqlite3
import json
import hashlib
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

class SmartCache:
    """Smart cache with adaptive TTL and data age indicators."""
    
    def __init__(self, cache_db_path: str = "smart_cache.db"):
        self.cache_db_path = cache_db_path
        self._init_cache_db()
    
    def _init_cache_db(self):
        """Initialize cache database with improved schema."""
        conn = sqlite3.connect(self.cache_db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS smart_cache (
                cache_key TEXT PRIMARY KEY,
                endpoint TEXT,
                params_hash TEXT,
                data TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,
                hit_count INTEGER DEFAULT 0,
                data_quality TEXT DEFAULT 'fresh',
                sync_generation INTEGER DEFAULT 0
            )
        """)
        
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_endpoint ON smart_cache(endpoint)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_expires_at ON smart_cache(expires_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sync_generation ON smart_cache(sync_generation)")
        
        conn.commit()
        conn.close()
    
    def _generate_cache_key(self, endpoint: str, params: dict = None) -> str:
        """Generate cache key from endpoint and parameters."""
        # Normalize params (None and empty dict should be treated the same)
        if params:
            params_str = json.dumps(params, sort_keys=True)
            params_hash = hashlib.md5(params_str.encode()).hexdigest()[:8]
            return f"{endpoint}:{params_hash}"
        return f"{endpoint}:no_params"
    
    def _get_data_age_category(self, created_at: datetime) -> str:
        """Categorize data age."""
        age = datetime.now() - created_at
        
        if age < timedelta(minutes=30):
            return 'fresh'
        elif age < timedelta(hours=4):
            return 'recent'
        elif age < timedelta(hours=24):
            return 'stale'
        else:
            return 'old'
    
    def set(self, endpoint: str, params: dict, data: Any, 
            ttl_hours: float = 24, sync_generation: int = 0):
        """Store data with smart TTL."""
        cache_key = self._generate_cache_key(endpoint, params)
        params_hash = hashlib.md5(json.dumps(params or {}, sort_keys=True).encode()).hexdigest()[:8]
        
        expires_at = datetime.now() + timedelta(hours=ttl_hours)
        
        try:
            conn = sqlite3.connect(self.cache_db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT OR REPLACE INTO smart_cache 
                (cache_key, endpoint, params_hash, data, expires_at, sync_generation)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (cache_key, endpoint, params_hash, json.dumps(data, default=str), 
                  expires_at, sync_generation))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Cache set error: {e}")
    
    def get(self, endpoint: str, params: dict = None, 
            include_stale: bool = True) -> Optional[Dict]:
        """Get cached data with age information."""
        cache_key = self._generate_cache_key(endpoint, params)
        
        try:
            conn = sqlite3.connect(self.cache_db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT data, created_at, expires_at, hit_count, sync_generation
                FROM smart_cache 
                WHERE cache_key = ?
            """, (cache_key,))
            
            result = cursor.fetchone()
            
            if result:
                data_json, created_str, expires_str, hit_count, sync_gen = result
                created_at = datetime.fromisoformat(created_str)
                expires_at = datetime.fromisoformat(expires_str)
                
                # Update hit count
                cursor.execute("""
                    UPDATE smart_cache 
                    SET hit_count = hit_count + 1, data_quality = ?
                    WHERE cache_key = ?
                """, (self._get_data_age_category(created_at), cache_key))
                
                conn.commit()
                
                # Check if expired
                now = datetime.now()
                is_expired = now > expires_at
                
                if is_expired and not include_stale:
                    conn.close()
                    return None
                
                # Parse data and add metadata
                data = json.loads(data_json)
                data['_cache_metadata'] = {
                    'created_at': created_str,
                    'expires_at': expires_str,
                    'age_category': self._get_data_age_category(created_at),
                    'is_expired': is_expired,
                    'hit_count': hit_count + 1,
                    'sync_generation': sync_gen,
                    'age_minutes': int((now - created_at).total_seconds() / 60)
                }
                
                conn.close()
                return data
            
            conn.close()
            return None
            
        except Exception as e:
            logger.error(f"Cache get error: {e}")
            return None
    
    def delete(self, endpoint: str, params: dict = None) -> bool:
        """Delete specific cache entry."""
        cache_key = self._generate_cache_key(endpoint, params)
        
        try:
            conn = sqlite3.connect(self.cache_db_path)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM smart_cache WHERE cache_key = ?", (cache_key,))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Cache delete error: {e}")
            return False
    
    def invalidate_by_sync_generation(self, max_generation: int):
        """Invalidate old cache entries by sync generation."""
        try:
            conn = sqlite3.connect(self.cache_db_path)
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM smart_cache 
                WHERE sync_generation < ?
            """, (max_generation,))
            deleted = cursor.rowcount
            conn.commit()
            conn.close()
            logger.info(f"Invalidated {deleted} old cache entries")
            return deleted
        except Exception as e:
            logger.error(f"Cache invalidation error: {e}")
            return 0
    
    def get_cache_stats(self) -> dict:
        """Get comprehensive cache statistics."""
        try:
            conn = sqlite3.connect(self.cache_db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_entries,
                    COUNT(CASE WHEN expires_at > CURRENT_TIMESTAMP THEN 1 END) as valid_entries,
                    COUNT(CASE WHEN data_quality = 'fresh' THEN 1 END) as fresh_entries,
                    COUNT(CASE WHEN data_quality = 'recent' THEN 1 END) as recent_entries,
                    COUNT(CASE WHEN data_quality = 'stale' THEN 1 END) as stale_entries,
                    COUNT(CASE WHEN data_quality = 'old' THEN 1 END) as old_entries,
                    SUM(hit_count) as total_hits,
                    AVG(hit_count) as avg_hits_per_entry,
                    MAX(sync_generation) as current_generation
                FROM smart_cache
            """)
            
            stats = cursor.fetchone()
            conn.close()
            
            return {
                'total_entries': stats[0],
                'valid_entries': stats[1],
                'fresh_entries': stats[2],
                'recent_entries': stats[3],
                'stale_entries': stats[4],
                'old_entries': stats[5],
                'total_hits': stats[6] or 0,
                'avg_hits_per_entry': round(stats[7] or 0, 2),
                'current_generation': stats[8] or 0,
                'cache_efficiency': f"{(stats[6] or 0) / max(stats[0], 1) * 100:.1f}%"
            }
            
        except Exception as e:
            logger.error(f"Cache stats error: {e}")
            return {}

    def clear_all(self) -> int:
        """Clear all cache entries. Returns number of deleted entries."""
        try:
            conn = sqlite3.connect(self.cache_db_path)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM smart_cache")
            deleted_count = cursor.rowcount
            conn.commit()
            conn.close()
            logger.info(f"Cleared {deleted_count} cache entries")
            return deleted_count
        except Exception as e:
            logger.error(f"Cache clear error: {e}")
            return 0
    
    def cleanup_expired(self) -> int:
        """Remove expired cache entries. Returns number of deleted entries."""
        try:
            conn = sqlite3.connect(self.cache_db_path)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM smart_cache WHERE expires_at < CURRENT_TIMESTAMP")
            deleted_count = cursor.rowcount
            conn.commit()
            conn.close()
            logger.info(f"Cleaned up {deleted_count} expired cache entries")
            return deleted_count
        except Exception as e:
            logger.error(f"Cache cleanup error: {e}")
            return 0

# Global smart cache instance
smart_cache = SmartCache()
