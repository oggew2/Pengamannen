"""
Enhanced Yahoo Finance fetcher with aggressive rate limiting and Nordic support.
Handles 30-880 stocks with proper error handling and data validation.
"""
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import date, datetime, timedelta
from typing import Optional, Dict, List, Tuple
import logging
import time
import random
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from fake_useragent import UserAgent

logger = logging.getLogger(__name__)

# Global rate limiting state
_last_request_time = 0
_request_count = 0
_session = None
_user_agent_pool = []
_circuit_breaker_until = 0
_consecutive_failures = 0

# Configuration
RATE_LIMIT_CONFIG = {
    'base_delay': (15, 30),           # 15-30 seconds between requests
    'backoff_multiplier': 2,          # Exponential backoff
    'max_backoff': 600,               # 10 minutes max
    'circuit_breaker_threshold': 5,   # Stop after 5 consecutive failures
    'circuit_breaker_timeout': 1800,  # 30 minutes timeout
    'session_refresh_after': 20,      # New session every 20 requests
    'user_agent_pool_size': 50        # 50 different user agents
}

STOCK_UNIVERSES = {
    'sweden_large': {
        'tickers': [
            'VOLV-B', 'SAND', 'ATCO-A', 'ATCO-B', 'ALFA', 'SKF-B', 'ASSA-B', 
            'HEXA-B', 'EPIR-B', 'SEB-A', 'SWED-A', 'SHB-A', 'NDA-SE', 'INVE-B',
            'AZN', 'GETI-B', 'ERIC-B', 'HM-B', 'TEL2-B', 'TELIA', 'BOL', 'SSAB-A',
            'SWEC-B', 'AFRY', 'NIBE-B', 'LIFCO-B', 'LAGR-B', 'ADDT-B', 'BURE', 'KINV-B'
        ],
        'suffix': '.ST',
        'count': 30
    },
    'sweden_all': {
        'tickers': [],  # Would need to fetch from OMX Stockholm All-Share
        'suffix': '.ST', 
        'count': 400
    },
    'nordic_large': {
        'tickers': [],  # Combined large caps from all Nordic countries
        'suffixes': ['.ST', '.OL', '.CO', '.HE'],
        'count': 120
    },
    'nordic_all': {
        'tickers': [],  # All Nordic stocks
        'suffixes': ['.ST', '.OL', '.CO', '.HE'],
        'count': 880
    }
}

def initialize_user_agents():
    """Initialize pool of realistic user agents."""
    global _user_agent_pool
    if not _user_agent_pool:
        ua = UserAgent()
        _user_agent_pool = [ua.random for _ in range(RATE_LIMIT_CONFIG['user_agent_pool_size'])]
    return random.choice(_user_agent_pool)

def get_session():
    """Get configured session with retry strategy and rotating user agents."""
    global _session, _request_count
    
    # Refresh session periodically
    if _session is None or _request_count % RATE_LIMIT_CONFIG['session_refresh_after'] == 0:
        _session = requests.Session()
        
        # Retry strategy
        retry_strategy = Retry(
            total=3,
            backoff_factor=2,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        _session.mount("http://", adapter)
        _session.mount("https://", adapter)
        
        # Set realistic headers
        _session.headers.update({
            'User-Agent': initialize_user_agents(),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
        
        logger.info(f"Created new session with User-Agent: {_session.headers['User-Agent'][:50]}...")
    
    return _session

def check_circuit_breaker():
    """Check if circuit breaker is active."""
    global _circuit_breaker_until
    if time.time() < _circuit_breaker_until:
        remaining = int(_circuit_breaker_until - time.time())
        raise Exception(f"Circuit breaker active for {remaining} more seconds")

def handle_failure():
    """Handle request failure for circuit breaker."""
    global _consecutive_failures, _circuit_breaker_until
    _consecutive_failures += 1
    
    if _consecutive_failures >= RATE_LIMIT_CONFIG['circuit_breaker_threshold']:
        _circuit_breaker_until = time.time() + RATE_LIMIT_CONFIG['circuit_breaker_timeout']
        logger.error(f"Circuit breaker activated for {RATE_LIMIT_CONFIG['circuit_breaker_timeout']} seconds")

def handle_success():
    """Handle successful request."""
    global _consecutive_failures
    _consecutive_failures = 0

def aggressive_rate_limit(attempt: int = 0):
    """Implement aggressive rate limiting with exponential backoff."""
    global _last_request_time, _request_count
    
    check_circuit_breaker()
    
    current_time = time.time()
    
    # Base delay
    min_delay, max_delay = RATE_LIMIT_CONFIG['base_delay']
    base_delay = random.uniform(min_delay, max_delay)
    
    # Exponential backoff on retries
    if attempt > 0:
        backoff_delay = min(
            base_delay * (RATE_LIMIT_CONFIG['backoff_multiplier'] ** attempt),
            RATE_LIMIT_CONFIG['max_backoff']
        )
        base_delay = backoff_delay
    
    # Ensure minimum time between requests
    time_since_last = current_time - _last_request_time
    if time_since_last < base_delay:
        sleep_time = base_delay - time_since_last
        logger.info(f"Rate limiting: sleeping for {sleep_time:.1f} seconds")
        time.sleep(sleep_time)
    
    _last_request_time = time.time()
    _request_count += 1

def fetch_stock_data_robust(ticker: str, max_retries: int = 3) -> Optional[Dict]:
    """Fetch stock data with robust error handling and rate limiting."""
    
    for attempt in range(max_retries):
        try:
            aggressive_rate_limit(attempt)
            
            session = get_session()
            stock = yf.Ticker(ticker, session=session)
            
            # Get basic info
            info = stock.info
            if not info or len(info) < 5:
                logger.warning(f"Insufficient data for {ticker}")
                continue
            
            # Get financial statements with error handling
            try:
                income = stock.quarterly_income_stmt
                balance = stock.quarterly_balance_sheet  
                cashflow = stock.quarterly_cashflow
            except Exception as e:
                logger.warning(f"Could not fetch financials for {ticker}: {e}")
                income = balance = cashflow = pd.DataFrame()
            
            # Calculate derived metrics
            roic = calculate_roic(income, balance) if not income.empty and not balance.empty else None
            p_fcf = info.get('marketCap', 0) / info.get('freeCashflow', 1) if info.get('freeCashflow') else None
            
            result = {
                'ticker': ticker.split('.')[0],  # Remove suffix
                'name': info.get('longName', ''),
                'sector': info.get('sector', ''),
                'country': get_country_from_suffix(ticker),
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
                'fetched_at': datetime.now()
            }
            
            handle_success()
            logger.info(f"Successfully fetched {ticker}")
            return result
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                # Handle 429 specifically
                retry_after = e.response.headers.get('Retry-After')
                if retry_after:
                    wait_time = int(retry_after)
                    logger.warning(f"429 error for {ticker}, waiting {wait_time} seconds")
                    time.sleep(wait_time)
                
                # Rotate user agent on 429
                get_session().headers['User-Agent'] = initialize_user_agents()
                logger.info(f"Rotated User-Agent for {ticker}")
                continue
            else:
                logger.error(f"HTTP error for {ticker}: {e}")
                handle_failure()
                break
                
        except Exception as e:
            logger.error(f"Error fetching {ticker} (attempt {attempt + 1}): {e}")
            handle_failure()
            if attempt == max_retries - 1:
                break
    
    return None

def get_country_from_suffix(ticker: str) -> str:
    """Get country from ticker suffix."""
    if '.ST' in ticker:
        return 'Sweden'
    elif '.OL' in ticker:
        return 'Norway'
    elif '.CO' in ticker:
        return 'Denmark'
    elif '.HE' in ticker:
        return 'Finland'
    return 'Unknown'

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

from services.live_universe import get_live_stock_universe, validate_data_completeness
    """Get stock universe based on user settings."""
    universe_key = f"{region}_{market_cap}"
    
    if universe_key not in STOCK_UNIVERSES:
        universe_key = 'sweden_large'  # Fallback
    
    universe = STOCK_UNIVERSES[universe_key]
    
    if universe['tickers']:
        # Add appropriate suffix
        if 'suffix' in universe:
            return [f"{ticker}{universe['suffix']}" for ticker in universe['tickers']]
        else:
            # Multiple suffixes for Nordic
            result = []
            for suffix in universe.get('suffixes', ['.ST']):
                result.extend([f"{ticker}{suffix}" for ticker in universe['tickers']])
            return result
    else:
        # TODO: Implement dynamic universe fetching for larger sets
        logger.warning(f"Universe {universe_key} not fully implemented, using sweden_large")
        return get_stock_universe('sweden', 'large')

def sync_stock_universe(db, region: str = 'sweden', market_cap: str = 'large') -> Dict:
    """Sync complete stock universe with live data and real-time error reporting."""
    from models import Stock, Fundamentals
    
    try:
        # Fetch live stock universe - NO HARDCODED LISTS
        tickers = get_live_stock_universe(region, market_cap)
        logger.info(f"Fetched live universe: {len(tickers)} stocks for {region}_{market_cap}")
        
    except Exception as e:
        logger.error(f"CRITICAL: Cannot fetch live stock universe: {e}")
        return {
            "status": "FAILED",
            "error": f"Live data unavailable: {str(e)}",
            "processed": 0,
            "successful": 0,
            "failed": 0,
            "coverage_percent": 0,
            "can_run_strategies": False
        }
    
    result = {
        "processed": 0,
        "successful": 0,
        "failed": 0,
        "errors": [],
        "universe_size": len(tickers),
        "coverage_percent": 0,
        "sync_started": datetime.now(),
        "region": region,
        "market_cap": market_cap,
        "successful_tickers": []
    }
    
    logger.info(f"Starting sync of {len(tickers)} stocks ({region}_{market_cap})")
    
    for i, ticker in enumerate(tickers):
        try:
            logger.info(f"Fetching {ticker} ({i+1}/{len(tickers)})")
            
            data = fetch_stock_data_robust(ticker)
            if not data:
                result["failed"] += 1
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
            
            result["successful"] += 1
            result["successful_tickers"].append(ticker)
            result["processed"] += 1
            
            # Commit every 10 stocks to avoid losing progress
            if result["processed"] % 10 == 0:
                db.commit()
                logger.info(f"Progress: {result['processed']}/{len(tickers)} stocks")
            
        except Exception as e:
            logger.error(f"Error processing {ticker}: {e}")
            result["failed"] += 1
            result["errors"].append(ticker)
            result["processed"] += 1
    
    # Final commit and validation
    try:
        db.commit()
        
        # Real-time data completeness validation
        completeness = validate_data_completeness(tickers, result["successful_tickers"])
        result.update(completeness)
        
        result["sync_completed"] = datetime.now()
        result["duration_minutes"] = (result["sync_completed"] - result["sync_started"]).total_seconds() / 60
        
        # Log critical status
        if result["status"] in ["CRITICAL", "ERROR"]:
            logger.error(f"SYNC FAILED: {result['message']}")
        elif result["status"] == "WARNING":
            logger.warning(f"SYNC WARNING: {result['message']}")
        else:
            logger.info(f"SYNC SUCCESS: {result['message']}")
        
    except Exception as e:
        db.rollback()
        logger.error(f"Database error: {e}")
        result["errors"].append(f"Database error: {str(e)}")
        result["status"] = "DATABASE_ERROR"
        result["can_run_strategies"] = False
    
    return result
