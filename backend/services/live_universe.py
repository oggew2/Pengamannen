"""
Live stock universe fetcher - uses Avanza mappings for Swedish stocks.
"""
import requests
from bs4 import BeautifulSoup
import pandas as pd
from typing import List, Dict
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

def get_live_stock_universe(region: str = 'sweden', market_cap: str = 'large', market: str = 'both') -> List[str]:
    """Get stock universe from database - only active stocks with avanza_id."""
    import sqlite3
    
    conn = sqlite3.connect('app.db')
    cur = conn.cursor()
    
    # Only fetch active stocks (those with fundamentals data)
    query = """SELECT ticker FROM stocks 
               WHERE stock_type IN ('stock', 'sdb') 
               AND is_active = 1
               AND avanza_id IS NOT NULL AND avanza_id != ''"""
    if market == 'stockholmsborsen':
        query += " AND market = 'Stockholmsbörsen'"
    elif market == 'first_north':
        query += " AND market = 'First North Stockholm'"
    
    cur.execute(query)
    tickers = [row[0] for row in cur.fetchall()]
    conn.close()
    
    logger.info(f"Using {len(tickers)} active Swedish stocks ({market})")
    return tickers


def get_avanza_id_map() -> Dict[str, str]:
    """Get ticker -> avanza_id mapping from database."""
    import sqlite3
    
    conn = sqlite3.connect('app.db')
    cur = conn.cursor()
    cur.execute("SELECT ticker, avanza_id FROM stocks WHERE avanza_id IS NOT NULL AND avanza_id != ''")
    mapping = {row[0]: row[1] for row in cur.fetchall()}
    conn.close()
    return mapping

def fetch_omx_stockholm_30() -> List[str]:
    """Fetch live OMX Stockholm 30 constituents."""
    try:
        # Method 1: Try yfinance to get index constituents
        try:
            index = yf.Ticker("^OMXS30")
            # This might not work, yfinance doesn't always have index constituents
            pass
        except:
            pass
        
        # Method 2: Scrape from Nasdaq OMX website
        try:
            url = "https://indexes.nasdaqomx.com/Index/Overview/OMXS30"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            }
            response = requests.get(url, headers=headers, timeout=30)
            
            if response.status_code == 200:
                # Parse HTML for ticker symbols
                soup = BeautifulSoup(response.content, 'html.parser')
                # This would need specific parsing logic for the Nasdaq OMX page
                # For now, we'll implement a fallback
                pass
        except Exception as e:
            logger.warning(f"Failed to scrape OMX Stockholm 30: {e}")
        
        # Method 3: Use known major constituents as emergency fallback
        # BUT log this as an error since we want live data
        logger.error("CRITICAL: Using hardcoded OMX Stockholm 30 - live data fetch failed")
        
        fallback_tickers = [
            'VOLV-B', 'SAND', 'ATCO-A', 'ATCO-B', 'ALFA', 'SKF-B', 'ASSA-B', 
            'HEXA-B', 'EPIR-B', 'SEB-A', 'SWED-A', 'SHB-A', 'NDA-SE', 'INVE-B',
            'AZN', 'GETI-B', 'ERIC-B', 'HM-B', 'TEL2-B', 'TELIA', 'BOL', 'SSAB-A',
            'SWEC-B', 'AFRY', 'NIBE-B', 'LIFCO-B', 'LAGR-B', 'ADDT-B', 'BURE', 'KINV-B'
        ]
        
        return [f"{ticker}.ST" for ticker in fallback_tickers]
        
    except Exception as e:
        logger.error(f"Failed to fetch OMX Stockholm 30: {e}")
        raise Exception("Cannot fetch OMX Stockholm 30 constituents")

def fetch_omx_stockholm_all_share() -> List[str]:
    """Fetch all OMX Stockholm stocks."""
    try:
        # This would require scraping the full OMX Stockholm All-Share index
        # or using a financial data API that provides complete listings
        
        logger.error("OMX Stockholm All-Share fetching not implemented")
        raise NotImplementedError(
            "Complete Swedish stock universe (400+ stocks) requires premium data source. "
            "Use 'large' market cap setting for now."
        )
        
    except Exception as e:
        logger.error(f"Failed to fetch OMX Stockholm All-Share: {e}")
        raise Exception("Cannot fetch complete Swedish stock universe")

def fetch_oslo_bors(market_cap: str) -> List[str]:
    """Fetch Norwegian stocks from Oslo Børs."""
    try:
        logger.warning("Oslo Børs fetching not implemented")
        return []  # Return empty rather than fail completely
    except Exception as e:
        logger.error(f"Failed to fetch Oslo Børs: {e}")
        return []

def fetch_omx_copenhagen(market_cap: str) -> List[str]:
    """Fetch Danish stocks from OMX Copenhagen."""
    try:
        logger.warning("OMX Copenhagen fetching not implemented")
        return []
    except Exception as e:
        logger.error(f"Failed to fetch OMX Copenhagen: {e}")
        return []

def fetch_omx_helsinki(market_cap: str) -> List[str]:
    """Fetch Finnish stocks from OMX Helsinki."""
    try:
        logger.warning("OMX Helsinki fetching not implemented")
        return []
    except Exception as e:
        logger.error(f"Failed to fetch OMX Helsinki: {e}")
        return []

def validate_data_completeness(expected_tickers: List[str], successful_tickers: List[str]) -> Dict:
    """Validate data completeness and return real-time error status."""
    total = len(expected_tickers)
    successful = len(successful_tickers)
    missing = total - successful
    coverage = (successful / total * 100) if total > 0 else 0
    
    # Real-time error classification
    if coverage < 50:
        status = "CRITICAL"
        message = f"CRITICAL: Only {successful}/{total} stocks available ({coverage:.1f}%). All strategies disabled."
        can_run_strategies = False
    elif coverage < 70:
        status = "ERROR" 
        message = f"ERROR: Missing {missing} stocks ({coverage:.1f}% coverage). Rankings unreliable."
        can_run_strategies = False
    elif coverage < 90:
        status = "WARNING"
        message = f"WARNING: Missing {missing} stocks ({coverage:.1f}% coverage). Some rankings may be inaccurate."
        can_run_strategies = True
    else:
        status = "OK"
        message = f"Good coverage: {successful}/{total} stocks ({coverage:.1f}%)"
        can_run_strategies = True
    
    # Find missing tickers
    successful_base_tickers = [t.split('.')[0] for t in successful_tickers]
    expected_base_tickers = [t.split('.')[0] for t in expected_tickers]
    missing_tickers = [t for t in expected_base_tickers if t not in successful_base_tickers]
    
    return {
        "status": status,
        "message": message,
        "can_run_strategies": can_run_strategies,
        "total_expected": total,
        "successful": successful,
        "missing_count": missing,
        "coverage_percent": round(coverage, 1),
        "missing_tickers": missing_tickers,
        "timestamp": datetime.now().isoformat(),
        "data_source": "live" if total > 0 else "none"
    }

def get_data_quality_status(db) -> Dict:
    """Get real-time data quality status from database."""
    from models import Stock, Fundamentals
    from datetime import timedelta
    
    try:
        # Count stocks with recent data
        cutoff_date = datetime.now() - timedelta(hours=48)
        
        total_stocks = db.query(Stock).count()
        recent_fundamentals = db.query(Fundamentals).filter(
            Fundamentals.fetched_date >= cutoff_date.date()
        ).count()
        
        if total_stocks == 0:
            return {
                "status": "NO_DATA",
                "message": "No stock data in database. Run initial sync.",
                "can_run_strategies": False,
                "coverage_percent": 0
            }
        
        coverage = (recent_fundamentals / total_stocks * 100) if total_stocks > 0 else 0
        
        if coverage < 50:
            status = "STALE"
            message = f"Data too old: {recent_fundamentals}/{total_stocks} stocks have fresh data"
            can_run = False
        elif coverage < 80:
            status = "PARTIAL"
            message = f"Some stale data: {recent_fundamentals}/{total_stocks} stocks current"
            can_run = True
        else:
            status = "FRESH"
            message = f"Data current: {recent_fundamentals}/{total_stocks} stocks up to date"
            can_run = True
        
        return {
            "status": status,
            "message": message,
            "can_run_strategies": can_run,
            "total_stocks": total_stocks,
            "fresh_data_count": recent_fundamentals,
            "coverage_percent": round(coverage, 1),
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error checking data quality: {e}")
        return {
            "status": "ERROR",
            "message": f"Cannot check data quality: {str(e)}",
            "can_run_strategies": False,
            "coverage_percent": 0
        }
