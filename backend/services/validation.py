"""
Data validation utilities for stock data.
"""
import pandas as pd
import numpy as np
from datetime import date, timedelta
import logging

logger = logging.getLogger(__name__)


def validate_price_data(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """
    Validate and clean price data.
    
    Returns:
        Tuple of (cleaned DataFrame, list of warnings)
    """
    warnings = []
    
    if df.empty:
        return df, ["No price data to validate"]
    
    original_len = len(df)
    
    # Remove rows with null close prices
    df = df.dropna(subset=['close'])
    if len(df) < original_len:
        warnings.append(f"Removed {original_len - len(df)} rows with null close prices")
    
    # Remove zero or negative prices
    df = df[df['close'] > 0]
    
    # Remove extreme outliers (> 10x or < 0.1x median)
    for ticker in df['ticker'].unique():
        ticker_data = df[df['ticker'] == ticker]['close']
        if len(ticker_data) > 10:
            median = ticker_data.median()
            outlier_mask = (ticker_data > median * 10) | (ticker_data < median * 0.1)
            if outlier_mask.any():
                warnings.append(f"{ticker}: Removed {outlier_mask.sum()} outlier prices")
                df = df[~((df['ticker'] == ticker) & outlier_mask)]
    
    return df, warnings


def validate_fundamentals(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """
    Validate and clean fundamental data.
    
    Returns:
        Tuple of (cleaned DataFrame, list of warnings)
    """
    warnings = []
    
    if df.empty:
        return df, ["No fundamental data to validate"]
    
    # Cap extreme P/E ratios
    if 'pe' in df.columns:
        extreme_pe = (df['pe'] > 1000) | (df['pe'] < -1000)
        if extreme_pe.any():
            warnings.append(f"Capped {extreme_pe.sum()} extreme P/E values")
            df.loc[df['pe'] > 1000, 'pe'] = np.nan
            df.loc[df['pe'] < -1000, 'pe'] = np.nan
    
    # Validate percentage fields (0-1 range for ratios)
    pct_fields = ['roe', 'roa', 'roic', 'dividend_yield', 'payout_ratio']
    for field in pct_fields:
        if field in df.columns:
            # Some APIs return percentages as decimals, some as whole numbers
            # Normalize to decimal (0.15 = 15%)
            if df[field].max() > 10:  # Likely whole number percentages
                df[field] = df[field] / 100
    
    return df, warnings


def check_data_freshness(db, max_age_days: int = 7) -> dict:
    """
    Check if data is fresh enough for strategy calculations.
    
    Returns:
        Dict with freshness status and details
    """
    from models import DailyPrice, Fundamentals
    
    today = date.today()
    cutoff = today - timedelta(days=max_age_days)
    
    latest_price = db.query(DailyPrice).order_by(DailyPrice.date.desc()).first()
    latest_fund = db.query(Fundamentals).order_by(Fundamentals.fetched_date.desc()).first()
    
    price_fresh = latest_price and latest_price.date >= cutoff
    fund_fresh = latest_fund and latest_fund.fetched_date and latest_fund.fetched_date >= cutoff
    
    return {
        "prices_fresh": price_fresh,
        "fundamentals_fresh": fund_fresh,
        "latest_price_date": latest_price.date.isoformat() if latest_price else None,
        "latest_fundamental_date": latest_fund.fetched_date.isoformat() if latest_fund and latest_fund.fetched_date else None,
        "all_fresh": price_fresh and fund_fresh,
        "warning": None if (price_fresh and fund_fresh) else "Data may be stale, consider running sync"
    }
