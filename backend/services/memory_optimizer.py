"""
Advanced memory optimization for Börslabbet ranking computations.
Implements chunked processing, dtype optimization, and SQLite-specific optimizations.
"""
import logging
import gc
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
import sqlite3
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class MemoryOptimizer:
    """Memory optimization utilities for large DataFrame operations."""
    
    @staticmethod
    def optimize_dtypes(df: pd.DataFrame) -> pd.DataFrame:
        """
        Optimize DataFrame dtypes to reduce memory usage by 50-80%.
        Based on latest pandas optimization techniques.
        """
        original_memory = df.memory_usage(deep=True).sum()
        
        for col in df.columns:
            col_type = df[col].dtype
            
            if col_type == 'object':
                # Convert to category if low cardinality
                unique_ratio = df[col].nunique() / len(df)
                if unique_ratio < 0.5:
                    df[col] = df[col].astype('category')
                    logger.debug(f"Converted {col} to category (unique ratio: {unique_ratio:.2%})")
            
            elif col_type == 'int64':
                # Downcast integers
                col_min, col_max = df[col].min(), df[col].max()
                if col_min >= 0:
                    if col_max <= 255:
                        df[col] = df[col].astype('uint8')
                    elif col_max <= 65535:
                        df[col] = df[col].astype('uint16')
                    elif col_max <= 4294967295:
                        df[col] = df[col].astype('uint32')
                else:
                    if col_min >= -128 and col_max <= 127:
                        df[col] = df[col].astype('int8')
                    elif col_min >= -32768 and col_max <= 32767:
                        df[col] = df[col].astype('int16')
                    elif col_min >= -2147483648 and col_max <= 2147483647:
                        df[col] = df[col].astype('int32')
            
            elif col_type == 'float64':
                # Use float32 if precision allows
                df[col] = pd.to_numeric(df[col], downcast='float')
        
        optimized_memory = df.memory_usage(deep=True).sum()
        reduction = (original_memory - optimized_memory) / original_memory
        
        logger.info(f"Memory optimization: {original_memory/1024**2:.1f}MB → {optimized_memory/1024**2:.1f}MB "
                   f"(reduced by {reduction:.1%})")
        
        return df
    
    @staticmethod
    def chunked_sql_read(db_path: str, query: str, chunk_size: int = 50000) -> pd.DataFrame:
        """
        Read large SQL results in chunks to prevent memory overflow.
        Optimized for SQLite with proper connection handling.
        """
        chunks = []
        offset = 0
        
        with sqlite3.connect(db_path) as conn:
            while True:
                chunked_query = f"{query} LIMIT {chunk_size} OFFSET {offset}"
                chunk = pd.read_sql_query(chunked_query, conn)
                
                if chunk.empty:
                    break
                
                # Optimize each chunk immediately
                chunk = MemoryOptimizer.optimize_dtypes(chunk)
                chunks.append(chunk)
                
                offset += chunk_size
                logger.debug(f"Loaded chunk {len(chunks)}: {len(chunk)} rows")
                
                # Memory safety check
                current_memory = sum(c.memory_usage(deep=True).sum() for c in chunks) / 1024**3
                if current_memory > 1.5:  # 1.5GB limit
                    logger.warning(f"Memory usage {current_memory:.2f}GB - consider smaller chunks")
        
        if not chunks:
            return pd.DataFrame()
        
        result = pd.concat(chunks, ignore_index=True)
        
        # Final optimization after concatenation
        result = MemoryOptimizer.optimize_dtypes(result)
        
        # Force garbage collection
        del chunks
        gc.collect()
        
        return result
    
    @staticmethod
    def process_in_batches(df: pd.DataFrame, batch_size: int = 10000, 
                          process_func=None) -> pd.DataFrame:
        """
        Process large DataFrame in batches to prevent memory spikes.
        """
        if len(df) <= batch_size:
            return process_func(df) if process_func else df
        
        results = []
        
        for i in range(0, len(df), batch_size):
            batch = df.iloc[i:i + batch_size].copy()
            
            if process_func:
                batch = process_func(batch)
            
            results.append(batch)
            
            # Memory cleanup
            del batch
            if i % (batch_size * 5) == 0:  # Every 5 batches
                gc.collect()
        
        result = pd.concat(results, ignore_index=True)
        
        # Cleanup
        del results
        gc.collect()
        
        return result


class SQLiteOptimizer:
    """SQLite-specific optimizations for better performance with large datasets."""
    
    @staticmethod
    @contextmanager
    def optimized_connection(db_path: str):
        """
        Create optimized SQLite connection with performance settings.
        """
        conn = sqlite3.connect(db_path)
        try:
            # Performance optimizations
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA synchronous = NORMAL")
            conn.execute("PRAGMA cache_size = -64000")  # 64MB cache
            conn.execute("PRAGMA temp_store = MEMORY")
            conn.execute("PRAGMA mmap_size = 268435456")  # 256MB mmap
            
            yield conn
        finally:
            conn.close()
    
    @staticmethod
    def create_indexes_for_ranking(db_path: str):
        """
        Create optimized indexes for ranking queries.
        """
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_daily_prices_ticker_date ON daily_prices(ticker, date DESC)",
            "CREATE INDEX IF NOT EXISTS idx_fundamentals_ticker ON fundamentals(ticker)",
            "CREATE INDEX IF NOT EXISTS idx_stocks_market_cap ON stocks(market_cap_msek DESC)",
            "CREATE INDEX IF NOT EXISTS idx_strategy_signals_strategy_rank ON strategy_signals(strategy_name, rank)"
        ]
        
        with SQLiteOptimizer.optimized_connection(db_path) as conn:
            for index_sql in indexes:
                conn.execute(index_sql)
            conn.commit()
            logger.info("Created optimized indexes for ranking queries")


def optimize_ranking_computation(prices_df: pd.DataFrame, fund_df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Apply comprehensive memory optimization to ranking computation DataFrames.
    """
    logger.info("Starting comprehensive memory optimization...")
    
    # Track original memory usage
    original_prices_mem = prices_df.memory_usage(deep=True).sum() / 1024**2
    original_fund_mem = fund_df.memory_usage(deep=True).sum() / 1024**2
    
    # Optimize dtypes
    prices_df = MemoryOptimizer.optimize_dtypes(prices_df)
    fund_df = MemoryOptimizer.optimize_dtypes(fund_df)
    
    # Sort by ticker for better cache locality
    prices_df = prices_df.sort_values(['ticker', 'date'])
    fund_df = fund_df.sort_values('ticker')
    
    # Track optimized memory usage
    opt_prices_mem = prices_df.memory_usage(deep=True).sum() / 1024**2
    opt_fund_mem = fund_df.memory_usage(deep=True).sum() / 1024**2
    
    total_reduction = ((original_prices_mem + original_fund_mem) - 
                      (opt_prices_mem + opt_fund_mem)) / (original_prices_mem + original_fund_mem)
    
    logger.info(f"Memory optimization complete:")
    logger.info(f"  Prices: {original_prices_mem:.1f}MB → {opt_prices_mem:.1f}MB")
    logger.info(f"  Fundamentals: {original_fund_mem:.1f}MB → {opt_fund_mem:.1f}MB")
    logger.info(f"  Total reduction: {total_reduction:.1%}")
    
    # Force garbage collection
    gc.collect()
    
    return prices_df, fund_df
