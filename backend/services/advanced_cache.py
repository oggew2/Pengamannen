"""
Advanced caching system for TwelveData API to minimize API calls.
Implements multi-layer caching with TTL and intelligent cache invalidation.
"""
import sqlite3
import json
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import logging
import os

logger = logging.getLogger(__name__)

class AdvancedCache:
    """State-of-the-art caching system with SQLite backend."""
    
    def __init__(self, cache_db_path: str = "cache.db"):
        self.cache_db_path = cache_db_path
        self._init_cache_db()
    
    def _init_cache_db(self):
        """Initialize cache database with optimized schema."""
        conn = sqlite3.connect(self.cache_db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS api_cache (
                cache_key TEXT PRIMARY KEY,
                data TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NOT NULL,
                api_endpoint TEXT NOT NULL,
                ticker TEXT,
                data_type TEXT,
                hit_count INTEGER DEFAULT 0,
                last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create indexes for performance
        conn.execute("CREATE INDEX IF NOT EXISTS idx_expires_at ON api_cache(expires_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ticker ON api_cache(ticker)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_data_type ON api_cache(data_type)")
        
        conn.commit()
        conn.close()
    
    def _generate_cache_key(self, endpoint: str, params: Dict) -> str:
        """Generate unique cache key from endpoint and parameters."""
        key_data = f"{endpoint}:{json.dumps(params, sort_keys=True)}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def get(self, endpoint: str, params: Dict) -> Optional[Dict]:
        """Get cached data if valid."""
        cache_key = self._generate_cache_key(endpoint, params)
        
        conn = sqlite3.connect(self.cache_db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT data, expires_at FROM api_cache 
            WHERE cache_key = ? AND expires_at > CURRENT_TIMESTAMP
        """, (cache_key,))
        
        result = cursor.fetchone()
        
        if result:
            # Update hit count and last accessed
            cursor.execute("""
                UPDATE api_cache 
                SET hit_count = hit_count + 1, last_accessed = CURRENT_TIMESTAMP
                WHERE cache_key = ?
            """, (cache_key,))
            conn.commit()
            
            logger.debug(f"Cache HIT for {endpoint}")
            conn.close()
            return json.loads(result[0])
        
        conn.close()
        logger.debug(f"Cache MISS for {endpoint}")
        return None
    
    def set(self, endpoint: str, params: Dict, data: Dict, ttl_hours: int = 24):
        """Cache data with TTL."""
        cache_key = self._generate_cache_key(endpoint, params)
        expires_at = datetime.now() + timedelta(hours=ttl_hours)
        
        conn = sqlite3.connect(self.cache_db_path)
        
        # Extract metadata
        ticker = params.get('symbol', '').replace('.STO', '')
        data_type = 'quote' if 'quote' in endpoint else 'fundamentals'
        
        conn.execute("""
            INSERT OR REPLACE INTO api_cache 
            (cache_key, data, expires_at, api_endpoint, ticker, data_type)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (cache_key, json.dumps(data), expires_at, endpoint, ticker, data_type))
        
        conn.commit()
        conn.close()
        
        logger.debug(f"Cached data for {endpoint} (TTL: {ttl_hours}h)")
    
    def cleanup_expired(self):
        """Remove expired cache entries."""
        conn = sqlite3.connect(self.cache_db_path)
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM api_cache WHERE expires_at <= CURRENT_TIMESTAMP")
        deleted = cursor.rowcount
        
        conn.commit()
        conn.close()
        
        if deleted > 0:
            logger.info(f"Cleaned up {deleted} expired cache entries")
    
    def get_cache_stats(self) -> Dict:
        """Get cache statistics."""
        conn = sqlite3.connect(self.cache_db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                COUNT(*) as total_entries,
                COUNT(CASE WHEN expires_at > CURRENT_TIMESTAMP THEN 1 END) as valid_entries,
                SUM(hit_count) as total_hits,
                AVG(hit_count) as avg_hits_per_entry
            FROM api_cache
        """)
        
        stats = cursor.fetchone()
        conn.close()
        
        return {
            'total_entries': stats[0],
            'valid_entries': stats[1],
            'total_hits': stats[2] or 0,
            'avg_hits_per_entry': round(stats[3] or 0, 2),
            'cache_efficiency': f"{(stats[2] or 0) / max(stats[0], 1) * 100:.1f}%"
        }
    
    def delete(self, endpoint: str, params: dict = None):
        """Delete a specific cache entry."""
        cache_key = self._generate_cache_key(endpoint, params)
        
        try:
            conn = sqlite3.connect(self.cache_db_path)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM api_cache WHERE cache_key = ?", (cache_key,))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Cache delete error: {e}")
            return False

class HistoricalTracker:
    """Track historical data for portfolio performance over time."""
    
    def __init__(self, history_db_path: str = "history.db"):
        self.history_db_path = history_db_path
        self._init_history_db()
    
    def _init_history_db(self):
        """Initialize historical tracking database."""
        conn = sqlite3.connect(self.history_db_path)
        
        # Price history table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS price_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                price REAL NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                source TEXT DEFAULT 'TwelveData',
                volume INTEGER,
                change_percent REAL
            )
        """)
        
        # Fundamentals history table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS fundamentals_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                pe_ratio REAL,
                pb_ratio REAL,
                dividend_yield REAL,
                roe REAL,
                market_cap REAL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                source TEXT DEFAULT 'TwelveData'
            )
        """)
        
        # Portfolio snapshots table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS portfolio_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                portfolio_name TEXT NOT NULL,
                ticker TEXT NOT NULL,
                shares REAL NOT NULL,
                price REAL NOT NULL,
                value REAL NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create indexes
        conn.execute("CREATE INDEX IF NOT EXISTS idx_price_ticker_time ON price_history(ticker, timestamp)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_fund_ticker_time ON fundamentals_history(ticker, timestamp)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_portfolio_time ON portfolio_snapshots(portfolio_name, timestamp)")
        
        conn.commit()
        conn.close()
    
    def record_price(self, ticker: str, price: float, volume: int = None, change_percent: float = None):
        """Record price data point."""
        conn = sqlite3.connect(self.history_db_path)
        
        conn.execute("""
            INSERT INTO price_history (ticker, price, volume, change_percent)
            VALUES (?, ?, ?, ?)
        """, (ticker, price, volume, change_percent))
        
        conn.commit()
        conn.close()
        
        logger.debug(f"Recorded price history: {ticker} = {price}")
    
    def record_fundamentals(self, ticker: str, pe: float = None, pb: float = None, 
                          dividend_yield: float = None, roe: float = None, market_cap: float = None):
        """Record fundamental data point."""
        conn = sqlite3.connect(self.history_db_path)
        
        conn.execute("""
            INSERT INTO fundamentals_history 
            (ticker, pe_ratio, pb_ratio, dividend_yield, roe, market_cap)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (ticker, pe, pb, dividend_yield, roe, market_cap))
        
        conn.commit()
        conn.close()
        
        logger.debug(f"Recorded fundamentals history: {ticker}")
    
    def record_portfolio_snapshot(self, portfolio_name: str, holdings: List[Dict]):
        """Record portfolio snapshot for tracking performance."""
        conn = sqlite3.connect(self.history_db_path)
        
        for holding in holdings:
            conn.execute("""
                INSERT INTO portfolio_snapshots 
                (portfolio_name, ticker, shares, price, value)
                VALUES (?, ?, ?, ?, ?)
            """, (
                portfolio_name,
                holding['ticker'],
                holding['shares'],
                holding['price'],
                holding['shares'] * holding['price']
            ))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Recorded portfolio snapshot: {portfolio_name} ({len(holdings)} holdings)")
    
    def get_price_history(self, ticker: str, days: int = 30) -> List[Dict]:
        """Get price history for a ticker."""
        conn = sqlite3.connect(self.history_db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT price, timestamp, volume, change_percent
            FROM price_history 
            WHERE ticker = ? AND timestamp >= datetime('now', '-{} days')
            ORDER BY timestamp ASC
        """.format(days), (ticker,))
        
        results = cursor.fetchall()
        conn.close()
        
        return [
            {
                'price': row[0],
                'timestamp': row[1],
                'volume': row[2],
                'change_percent': row[3]
            }
            for row in results
        ]
    
    def get_portfolio_performance(self, portfolio_name: str, days: int = 30) -> Dict:
        """Get portfolio performance over time."""
        conn = sqlite3.connect(self.history_db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                DATE(timestamp) as date,
                SUM(value) as total_value,
                COUNT(DISTINCT ticker) as num_holdings
            FROM portfolio_snapshots 
            WHERE portfolio_name = ? AND timestamp >= datetime('now', '-{} days')
            GROUP BY DATE(timestamp)
            ORDER BY date ASC
        """.format(days), (portfolio_name,))
        
        results = cursor.fetchall()
        conn.close()
        
        if not results:
            return {'performance': [], 'total_return': 0, 'days_tracked': 0}
        
        performance = [
            {
                'date': row[0],
                'total_value': row[1],
                'num_holdings': row[2]
            }
            for row in results
        ]
        
        # Calculate total return
        if len(performance) > 1:
            start_value = performance[0]['total_value']
            end_value = performance[-1]['total_value']
            total_return = ((end_value - start_value) / start_value) * 100
        else:
            total_return = 0
        
        return {
            'performance': performance,
            'total_return': round(total_return, 2),
            'days_tracked': len(performance)
        }
