"""
Enhanced yfinance fetcher with aggressive rate limiting mitigation.
"""
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import date, datetime, timedelta
from typing import Optional, Dict, List
import logging
import time
import random
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

# Global rate limiting
_last_request_time = 0
_request_count = 0
_session = None

def get_session():
    """Get configured session with retry strategy."""
    global _session
    if _session is None:
        _session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=2,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        _session.mount("http://", adapter)
        _session.mount("https://", adapter)
        
        # Set headers to avoid blocking
        _session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
    return _session

def rate_limit():
    """Implement aggressive rate limiting."""
    global _last_request_time, _request_count
    
    current_time = time.time()
    
    # Reset counter every minute
    if current_time - _last_request_time > 60:
        _request_count = 0
    
    # Limit to 5 requests per minute
    if _request_count >= 5:
        sleep_time = 60 - (current_time - _last_request_time)
        if sleep_time > 0:
            time.sleep(sleep_time)
        _request_count = 0
    
    # Add random delay between requests
    time.sleep(random.uniform(3, 8))
    
    _last_request_time = time.time()
    _request_count += 1

def fetch_stock_data_cached(ticker: str) -> Optional[Dict]:
    """Fetch stock data with caching and rate limiting."""
    rate_limit()
    
    try:
        session = get_session()
        stock = yf.Ticker(ticker, session=session)
        
        # Try to get basic info first
        info = stock.info
        if not info or len(info) < 5:
            return None
            
        # Get financial statements with error handling
        try:
            income = stock.quarterly_income_stmt
            balance = stock.quarterly_balance_sheet  
            cashflow = stock.quarterly_cashflow
        except:
            income = balance = cashflow = pd.DataFrame()
        
        # Calculate derived metrics
        roic = calculate_roic(income, balance) if not income.empty and not balance.empty else None
        p_fcf = info.get('marketCap', 0) / info.get('freeCashflow', 1) if info.get('freeCashflow') else None
        
        return {
            'ticker': ticker.replace('.ST', ''),
            'name': info.get('longName', ''),
            'sector': info.get('sector', ''),
            'market_cap': info.get('marketCap', 0) / 1e6,
            'pe': info.get('trailingPE'),
            'pb': info.get('priceToBook'),
            'ps': info.get('priceToSalesTrailing12Months'),
            'p_fcf': p_fcf,
            'ev_ebitda': info.get('enterpriseToEbitda'),
            'dividend_yield': info.get('dividendYield', 0) * 100 if info.get('dividendYield') else 0,
            'roe': info.get('returnOnEquity', 0) * 100 if info.get('returnOnEquity') else 0,
            'roa': info.get('returnOnAssets', 0) * 100 if info.get('returnOnAssets') else 0,
            'roic': roic,
            'payout_ratio': info.get('payoutRatio', 0) * 100 if info.get('payoutRatio') else 0,
            'current_ratio': info.get('currentRatio'),
        }
        
    except Exception as e:
        logger.error(f"Error fetching {ticker}: {e}")
        return None

def calculate_roic(income_stmt: pd.DataFrame, balance_sheet: pd.DataFrame) -> Optional[float]:
    """Calculate ROIC = EBIT * (1 - tax_rate) / (Equity + Debt - Cash)"""
    try:
        if income_stmt.empty or balance_sheet.empty:
            return None
            
        ebit = income_stmt.loc['EBIT'].iloc[0] if 'EBIT' in income_stmt.index else None
        if ebit is None:
            ebit = income_stmt.loc['Operating Income'].iloc[0] if 'Operating Income' in income_stmt.index else None
        
        tax_expense = income_stmt.loc['Tax Provision'].iloc[0] if 'Tax Provision' in income_stmt.index else 0
        pretax_income = income_stmt.loc['Pretax Income'].iloc[0] if 'Pretax Income' in income_stmt.index else ebit
        
        tax_rate = abs(tax_expense / pretax_income) if pretax_income and pretax_income != 0 else 0.25
        
        equity = balance_sheet.loc['Stockholder Equity'].iloc[0] if 'Stockholder Equity' in balance_sheet.index else 0
        debt = balance_sheet.loc['Total Debt'].iloc[0] if 'Total Debt' in balance_sheet.index else 0
        cash = balance_sheet.loc['Cash And Cash Equivalents'].iloc[0] if 'Cash And Cash Equivalents' in balance_sheet.index else 0
        
        invested_capital = equity + debt - cash
        
        if ebit and invested_capital and invested_capital != 0:
            return (ebit * (1 - tax_rate) / invested_capital) * 100
        return None
    except Exception:
        return None

def get_swedish_tickers() -> List[str]:
    """Get Swedish stock tickers with .ST suffix for yfinance."""
    base_tickers = [
        "VOLV-B", "SAND", "ATCO-A", "ATCO-B", "ALFA", "SKF-B", "ASSA-B", 
        "HEXA-B", "EPIR-B", "SEB-A", "SWED-A", "SHB-A", "NDA-SE", "INVE-B",
        "AZN", "GETI-B", "ERIC-B", "HM-B", "TEL2-B", "TELIA", "BOL", "SSAB-A"
    ]
    return [f"{ticker}.ST" for ticker in base_tickers]

def sync_all_data(db) -> Dict:
    """Sync Swedish stocks with aggressive rate limiting."""
    from models import Stock, Fundamentals
    
    tickers = get_swedish_tickers()[:5]  # Limit to 5 stocks for testing
    result = {"processed": 0, "errors": []}
    
    logger.info(f"Starting sync of {len(tickers)} stocks with rate limiting")
    
    for ticker in tickers:
        try:
            data = fetch_stock_data_cached(ticker)
            if not data:
                result["errors"].append(ticker)
                continue
                
            # Update database
            db.merge(Stock(
                ticker=data['ticker'],
                name=data['name'],
                market_cap_msek=data['market_cap'],
                sector=data['sector']
            ))
            
            db.merge(Fundamentals(
                ticker=data['ticker'],
                fiscal_date=date.today(),
                pe=data['pe'],
                pb=data['pb'],
                ps=data['ps'],
                p_fcf=data['p_fcf'],
                ev_ebitda=data['ev_ebitda'],
                dividend_yield=data['dividend_yield'],
                roe=data['roe'],
                roa=data['roa'],
                roic=data['roic'],
                payout_ratio=data['payout_ratio'],
                current_ratio=data['current_ratio'],
                fetched_date=date.today()
            ))
            
            result["processed"] += 1
            logger.info(f"Successfully synced {ticker}")
            
        except Exception as e:
            logger.error(f"Error processing {ticker}: {e}")
            result["errors"].append(ticker)
    
    try:
        db.commit()
        logger.info(f"Sync complete: {result}")
    except Exception as e:
        db.rollback()
        logger.error(f"Database error: {e}")
        result["errors"].append(str(e))
    
    return result
