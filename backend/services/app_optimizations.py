"""
App-wide performance and optimization improvements.
"""
from functools import lru_cache
from typing import Dict, List, Any
import asyncio
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class AppOptimizations:
    """Collection of app-wide performance optimizations."""
    
    @staticmethod
    @lru_cache(maxsize=128)
    def cached_strategy_config():
        """Cache strategy configuration to avoid repeated YAML parsing."""
        from config.strategies import STRATEGIES_CONFIG
        return STRATEGIES_CONFIG
    
    @staticmethod
    def optimize_database_queries(db):
        """Optimize database performance."""
        # Add indexes for common queries
        db.execute("CREATE INDEX IF NOT EXISTS idx_fundamentals_ticker_date ON fundamentals(ticker, fetched_date)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_daily_prices_ticker_date ON daily_prices(ticker, date)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_stocks_market_cap ON stocks(market_cap_msek)")
        db.commit()
        logger.info("Database indexes optimized")
    
    @staticmethod
    def optimize_pandas_operations():
        """Optimize pandas for better performance."""
        import pandas as pd
        
        # Use faster engines
        pd.set_option('compute.use_bottleneck', True)
        pd.set_option('compute.use_numexpr', True)
        
        # Optimize memory usage
        pd.set_option('mode.copy_on_write', True)
        
        logger.info("Pandas optimizations applied")
    
    @staticmethod
    def precompute_common_calculations(db):
        """Precompute expensive calculations."""
        from models import Fundamentals
        
        # Precompute market cap percentiles
        fundamentals = db.query(Fundamentals).filter(
            Fundamentals.fetched_date >= datetime.now().date() - timedelta(days=7)
        ).all()
        
        if fundamentals:
            market_caps = [f.market_cap for f in fundamentals if f.market_cap]
            percentiles = {
                'p40': np.percentile(market_caps, 60),  # Top 40%
                'p20': np.percentile(market_caps, 80),  # Top 20%
                'p10': np.percentile(market_caps, 90)   # Top 10%
            }
            
            # Cache these for fast filtering
            return percentiles
        
        return {}
    
    @staticmethod
    def optimize_api_responses():
        """Optimize API response formats."""
        return {
            'compression': 'gzip',
            'json_separators': (',', ':'),  # Compact JSON
            'exclude_none': True,  # Remove null fields
            'datetime_format': 'iso'  # Faster parsing
        }

class CacheManager:
    """Intelligent caching system."""
    
    def __init__(self):
        self._cache = {}
        self._ttl = {}
    
    def get(self, key: str, default=None):
        """Get cached value if not expired."""
        if key in self._cache:
            if datetime.now() < self._ttl[key]:
                return self._cache[key]
            else:
                # Expired
                del self._cache[key]
                del self._ttl[key]
        return default
    
    def set(self, key: str, value: Any, ttl_minutes: int = 15):
        """Set cached value with TTL."""
        self._cache[key] = value
        self._ttl[key] = datetime.now() + timedelta(minutes=ttl_minutes)
    
    def clear_expired(self):
        """Clear expired cache entries."""
        now = datetime.now()
        expired_keys = [k for k, ttl in self._ttl.items() if now >= ttl]
        for key in expired_keys:
            del self._cache[key]
            del self._ttl[key]
        return len(expired_keys)

# Global cache instance
app_cache = CacheManager()

def performance_monitor(func):
    """Decorator to monitor function performance."""
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        duration = time.time() - start_time
        
        if duration > 1.0:  # Log slow operations
            logger.warning(f"Slow operation: {func.__name__} took {duration:.2f}s")
        
        return result
    return wrapper

class DataQualityOptimizer:
    """Optimize data quality checks."""
    
    @staticmethod
    def fast_data_validation(stocks_data: List[Dict]) -> Dict:
        """Fast validation of stock data quality."""
        if not stocks_data:
            return {'status': 'NO_DATA', 'coverage': 0}
        
        # Quick quality checks
        total = len(stocks_data)
        valid_pe = sum(1 for s in stocks_data if s.get('pe') and s['pe'] > 0)
        valid_market_cap = sum(1 for s in stocks_data if s.get('market_cap') and s['market_cap'] > 0)
        
        coverage = (valid_pe + valid_market_cap) / (total * 2) * 100
        
        if coverage > 80:
            status = 'EXCELLENT'
        elif coverage > 60:
            status = 'GOOD'
        elif coverage > 40:
            status = 'DEGRADED'
        else:
            status = 'POOR'
        
        return {
            'status': status,
            'coverage': round(coverage, 1),
            'total_stocks': total,
            'valid_ratios': valid_pe,
            'valid_market_caps': valid_market_cap
        }

def apply_all_optimizations(app, db):
    """Apply all performance optimizations."""
    logger.info("Applying app-wide optimizations...")
    
    # Database optimizations
    AppOptimizations.optimize_database_queries(db)
    
    # Pandas optimizations
    AppOptimizations.optimize_pandas_operations()
    
    # API optimizations
    api_opts = AppOptimizations.optimize_api_responses()
    
    # Cache precomputation
    percentiles = AppOptimizations.precompute_common_calculations(db)
    app_cache.set('market_cap_percentiles', percentiles, ttl_minutes=60)
    
    logger.info("✅ All optimizations applied")
    
    return {
        'database_indexes': 'created',
        'pandas_optimizations': 'enabled',
        'api_compression': api_opts['compression'],
        'cache_precomputed': len(percentiles) > 0,
        'status': 'OPTIMIZED'
    }
