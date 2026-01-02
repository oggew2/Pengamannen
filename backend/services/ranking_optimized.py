"""
Memory-optimized ranking service with latest best practices.
Implements chunked processing, dtype optimization, and proper garbage collection.
"""
import pandas as pd
import numpy as np
import gc
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# Memory optimization constants
CHUNK_SIZE = 50000  # Process 50k records at a time
MIN_MARKET_CAP_MSEK = 2000  # 2B SEK = 2000 MSEK
VALID_STOCK_TYPES = ['stock', 'sdb']
FINANCIAL_SECTORS = [
    'Traditionell Bankverksamhet', 'Investmentbolag', 'Försäkring',
    'Sparande & Investering', 'Kapitalförvaltning', 'Konsumentkredit',
]

# Optimized dtypes for memory efficiency
PRICE_DTYPES = {
    'ticker': 'category',  # Saves 75% memory vs object
    'date': 'datetime64[ns]',
    'close': 'float32'  # Saves 50% memory vs float64
}

FUNDAMENTALS_DTYPES = {
    'ticker': 'category',
    'pe': 'float32', 'pb': 'float32', 'ps': 'float32',
    'p_fcf': 'float32', 'ev_ebitda': 'float32',
    'dividend_yield': 'float32', 'roe': 'float32',
    'roa': 'float32', 'roic': 'float32', 'fcfroe': 'float32',
    'payout_ratio': 'float32', 'market_cap': 'float32'
}


def optimize_dataframe_memory(df: pd.DataFrame) -> pd.DataFrame:
    """Optimize DataFrame memory usage with proper dtypes."""
    if df.empty:
        return df
    
    # Convert object columns to category if low cardinality
    for col in df.select_dtypes(include=['object']).columns:
        if df[col].nunique() / len(df) < 0.5:  # Less than 50% unique values
            df[col] = df[col].astype('category')
    
    # Downcast numeric types
    for col in df.select_dtypes(include=['int64']).columns:
        df[col] = pd.to_numeric(df[col], downcast='integer')
    
    for col in df.select_dtypes(include=['float64']).columns:
        df[col] = pd.to_numeric(df[col], downcast='float')
    
    return df


def filter_real_stocks(df: pd.DataFrame, include_preference: bool = False) -> pd.DataFrame:
    """Memory-efficient stock filtering."""
    if df.empty or 'stock_type' not in df.columns:
        return df
    
    valid_types = VALID_STOCK_TYPES + (['preference'] if include_preference else [])
    # CRITICAL FIX: Don't convert to category if we need string operations
    valid_types_lower = [t.lower() for t in valid_types]
    
    if df['stock_type'].dtype.name == 'category':
        # Handle existing categorical column
        return df[df['stock_type'].astype(str).str.lower().isin(valid_types_lower)]
    else:
        # Case-insensitive comparison for non-categorical
        return df[df['stock_type'].str.lower().isin(valid_types_lower)]


def filter_financial_companies(df: pd.DataFrame) -> pd.DataFrame:
    """Memory-efficient financial sector filtering."""
    if df.empty or 'sector' not in df.columns:
        return df
    
    # CRITICAL FIX: Handle categorical columns properly
    financial_lower = [s.lower() for s in FINANCIAL_SECTORS]
    
    if df['sector'].dtype.name == 'category':
        # Handle categorical sector column - convert to string first to avoid category issues
        sector_lower = df['sector'].astype(str).str.lower()
        # Handle NaN values properly for categorical
        sector_lower = sector_lower.fillna('unknown')
        return df[~sector_lower.isin(financial_lower)]
    else:
        # Case-insensitive comparison for non-categorical
        return df[~df['sector'].fillna('').str.lower().isin(financial_lower)]


def filter_by_min_market_cap(df: pd.DataFrame, min_cap_msek: float = MIN_MARKET_CAP_MSEK) -> pd.DataFrame:
    """Memory-efficient market cap filtering."""
    if df.empty or 'market_cap' not in df.columns:
        return df
    return df[df['market_cap'] >= min_cap_msek]


def calculate_momentum_score_optimized(prices_df: pd.DataFrame) -> pd.Series:
    """
    Memory-optimized momentum calculation.
    Uses chunked processing and proper memory management.
    """
    if prices_df.empty:
        return pd.Series(dtype='float32')
    
    # Optimize dtypes first
    prices_df = optimize_dataframe_memory(prices_df)
    
    # Create pivot table with memory optimization
    try:
        price_pivot = prices_df.pivot_table(
            index='date', 
            columns='ticker', 
            values='close', 
            aggfunc='last'
        ).sort_index()
        
        # Convert to float32 to save memory
        price_pivot = price_pivot.astype('float32')
        
    except MemoryError:
        logger.error("Memory error in pivot table creation")
        return pd.Series(dtype='float32')
    
    if price_pivot.empty:
        return pd.Series(dtype='float32')
    
    latest = price_pivot.iloc[-1]
    scores = pd.DataFrame(index=latest.index, dtype='float32')
    
    # Calculate momentum periods
    for period in [3, 6, 12]:
        days = period * 21
        if len(price_pivot) >= days:
            past = price_pivot.iloc[-days].replace(0, np.nan)
            scores[f'm{period}'] = ((latest / past) - 1).astype('float32')
        else:
            scores[f'm{period}'] = np.nan
    
    # Calculate mean and clean up
    result = scores.mean(axis=1, skipna=True)
    result = result.replace([np.inf, -np.inf], np.nan).dropna()
    
    # Force garbage collection
    del price_pivot, scores, latest
    gc.collect()
    
    return result.astype('float32')


def load_prices_chunked(db, valid_tickers: set) -> pd.DataFrame:
    """
    Load price data in chunks to prevent memory overflow.
    """
    from models import DailyPrice
    
    logger.info(f"Loading prices for {len(valid_tickers)} tickers in chunks...")
    
    # Get total count for progress tracking
    total_count = db.query(DailyPrice).filter(DailyPrice.ticker.in_(valid_tickers)).count()
    logger.info(f"Total price records to load: {total_count}")
    
    if total_count == 0:
        return pd.DataFrame()
    
    # Load in chunks
    all_prices = []
    processed = 0
    
    for offset in range(0, total_count, CHUNK_SIZE):
        chunk_query = db.query(DailyPrice).filter(
            DailyPrice.ticker.in_(valid_tickers)
        ).offset(offset).limit(CHUNK_SIZE)
        
        chunk_data = [{
            'ticker': p.ticker,
            'date': p.date,
            'close': float(p.close)
        } for p in chunk_query.all()]
        
        if chunk_data:
            chunk_df = pd.DataFrame(chunk_data)
            # Optimize dtypes immediately
            chunk_df['ticker'] = chunk_df['ticker'].astype('category')
            chunk_df['close'] = chunk_df['close'].astype('float32')
            all_prices.append(chunk_df)
        
        processed += len(chunk_data)
        logger.info(f"Loaded chunk {offset//CHUNK_SIZE + 1}: {processed}/{total_count} records")
        
        # Force garbage collection after each chunk
        del chunk_data
        gc.collect()
    
    if not all_prices:
        return pd.DataFrame()
    
    # Concatenate all chunks
    logger.info("Concatenating price chunks...")
    result = pd.concat(all_prices, ignore_index=True)
    
    # Final cleanup
    del all_prices
    gc.collect()
    
    logger.info(f"Price loading complete: {len(result)} records")
    return result


def calculate_value_score_optimized(fund_df: pd.DataFrame, prices_df: pd.DataFrame) -> pd.DataFrame:
    """Memory-optimized value score calculation."""
    if fund_df.empty:
        return pd.DataFrame()
    
    # Work with copy to avoid modifying original
    df = fund_df.copy()
    
    # Optimize memory usage
    df = optimize_dataframe_memory(df)
    
    # Calculate value factors with memory efficiency
    factors = ['pe', 'pb', 'ps', 'ev_ebitda', 'p_fcf']
    
    for factor in factors:
        if factor in df.columns:
            # Rank and normalize (lower is better for value)
            df[f'{factor}_rank'] = df[factor].rank(ascending=True, na_option='bottom')
    
    # Calculate composite score
    rank_cols = [f'{f}_rank' for f in factors if f'{f}_rank' in df.columns]
    if rank_cols:
        df['value_score'] = df[rank_cols].mean(axis=1, skipna=True)
        df['rank'] = df['value_score'].rank(ascending=True)
    
    # Clean up intermediate columns
    df = df.drop(columns=[col for col in df.columns if col.endswith('_rank')])
    
    # Force garbage collection
    gc.collect()
    
    return df[['ticker', 'value_score', 'rank']].dropna()


def calculate_momentum_with_quality_filter_optimized(
    prices_df: pd.DataFrame, 
    fund_df: pd.DataFrame,
    current_holdings: Optional[list] = None
) -> pd.DataFrame:
    """
    Memory-optimized momentum calculation with quality filter.
    """
    if prices_df.empty or fund_df.empty:
        return pd.DataFrame()
    
    logger.info("Calculating momentum scores...")
    momentum_scores = calculate_momentum_score_optimized(prices_df)
    
    if momentum_scores.empty:
        return pd.DataFrame()
    
    # Merge with fundamentals efficiently
    result_df = fund_df[['ticker']].copy()
    result_df = result_df.merge(
        momentum_scores.reset_index().rename(columns={0: 'momentum_score', 'index': 'ticker'}),
        on='ticker',
        how='inner'
    )
    
    # Apply quality filter (simplified Piotroski)
    if 'roe' in fund_df.columns:
        quality_filter = fund_df['roe'] > 0.05  # ROE > 5%
        result_df = result_df.merge(
            fund_df[quality_filter][['ticker']],
            on='ticker',
            how='inner'
        )
    
    # Rank by momentum
    result_df['rank'] = result_df['momentum_score'].rank(ascending=False)
    result_df['score'] = result_df['momentum_score']
    
    # Apply banding if current holdings exist
    if current_holdings:
        # Keep current holdings unless they drop below top 20%
        top_20_pct = len(result_df) * 0.2
        for holding in current_holdings:
            if holding in result_df['ticker'].values:
                holding_rank = result_df[result_df['ticker'] == holding]['rank'].iloc[0]
                if holding_rank > top_20_pct:
                    # Remove from results (sell signal)
                    result_df = result_df[result_df['ticker'] != holding]
    
    # Force garbage collection
    gc.collect()
    
    return result_df[['ticker', 'score', 'rank']].sort_values('rank').head(10)


# Export optimized functions
__all__ = [
    'optimize_dataframe_memory',
    'filter_real_stocks',
    'filter_financial_companies', 
    'filter_by_min_market_cap',
    'calculate_momentum_score_optimized',
    'load_prices_chunked',
    'calculate_value_score_optimized',
    'calculate_momentum_with_quality_filter_optimized'
]
