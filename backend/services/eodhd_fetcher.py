"""
EODHD API fetcher service.
Handles fetching Swedish stock data from EODHD API (free tier: 20 calls/day).
"""
import requests
import pandas as pd
import logging
import time
from datetime import date, datetime, timedelta
from typing import Optional

EODHD_BASE_URL = "https://eodhd.com/api"
logger = logging.getLogger(__name__)


def get_omx_stockholm_stocks() -> list[tuple]:
    """
    Return hardcoded list of major Swedish stocks on OMX Stockholm.
    Format: [(ticker, name, sector), ...]
    """
    return [
        # Large Cap - Industrials
        ("VOLV-B", "Volvo", "Industrials"),
        ("SAND", "Sandvik", "Industrials"),
        ("ATCO-A", "Atlas Copco A", "Industrials"),
        ("ATCO-B", "Atlas Copco B", "Industrials"),
        ("ALFA", "Alfa Laval", "Industrials"),
        ("SKF-B", "SKF", "Industrials"),
        ("ASSA-B", "Assa Abloy", "Industrials"),
        ("HEXA-B", "Hexagon", "Industrials"),
        ("EPIR-B", "Epiroc", "Industrials"),
        ("INDU-C", "Industrivärden C", "Industrials"),
        
        # Large Cap - Financials
        ("SEB-A", "SEB A", "Financials"),
        ("SWED-A", "Swedbank A", "Financials"),
        ("SHB-A", "Handelsbanken A", "Financials"),
        ("NDA-SE", "Nordea", "Financials"),
        ("INVE-B", "Investor B", "Financials"),
        ("LUND-B", "Lundbergföretagen B", "Financials"),
        ("KINV-B", "Kinnevik B", "Financials"),
        
        # Large Cap - Healthcare
        ("AZN", "AstraZeneca", "Healthcare"),
        ("GETI-B", "Getinge B", "Healthcare"),
        ("ESSITY-B", "Essity B", "Healthcare"),
        
        # Large Cap - Technology
        ("ERIC-B", "Ericsson B", "Technology"),
        ("HM-B", "H&M B", "Consumer Discretionary"),
        ("ELUX-B", "Electrolux B", "Consumer Discretionary"),
        
        # Large Cap - Consumer
        ("ESSITY-B", "Essity B", "Consumer Staples"),
        
        # Large Cap - Telecom
        ("TEL2-B", "Tele2 B", "Telecom"),
        ("TELIA", "Telia", "Telecom"),
        
        # Large Cap - Real Estate
        ("FABG", "Fabege", "Real Estate"),
        ("WALL-B", "Wallenstam B", "Real Estate"),
        ("CAST", "Castellum", "Real Estate"),
        
        # Large Cap - Materials
        ("BOL", "Boliden", "Materials"),
        ("SSAB-A", "SSAB A", "Materials"),
        ("SSAB-B", "SSAB B", "Materials"),
        
        # Mid Cap - Various
        ("SWEC-B", "Sweco B", "Industrials"),
        ("AFRY", "AFRY", "Industrials"),
        ("HUFV-A", "Hufvudstaden A", "Real Estate"),
        ("BILI-A", "Bilia A", "Consumer Discretionary"),
        ("AXFO", "Axfood", "Consumer Staples"),
        ("CLAS-B", "Clas Ohlson B", "Consumer Discretionary"),
        ("ELEC", "Electra Gruppen", "Consumer Discretionary"),
        ("HUSQ-B", "Husqvarna B", "Industrials"),
        ("NIBE-B", "NIBE B", "Industrials"),
        ("TREL-B", "Trelleborg B", "Industrials"),
        ("LIFCO-B", "Lifco B", "Industrials"),
        ("LAGR-B", "Lagercrantz B", "Industrials"),
        ("ADDT-B", "Addtech B", "Industrials"),
        ("BURE", "Bure Equity", "Financials"),
        ("CRED-A", "Creades A", "Financials"),
        ("LATOUR-B", "Latour B", "Financials"),
        ("SAGA-B", "Sagax B", "Real Estate"),
        ("WIHL", "Wihlborgs", "Real Estate"),
    ]


def validate_api_key(api_key: str) -> bool:
    """Validate EODHD API key by making a test call."""
    if not api_key:
        return False
    try:
        url = f"{EODHD_BASE_URL}/eod/VOLV-B.ST"
        params = {"api_token": api_key, "fmt": "json", "limit": 1}
        resp = requests.get(url, params=params, timeout=10)
        return resp.status_code == 200
    except Exception:
        return False


def fetch_eod_prices(ticker: str, api_key: str, start_date: date = None, retries: int = 3) -> dict:
    """
    Fetch end-of-day prices from EODHD API.
    
    Args:
        ticker: Stock ticker (e.g., "VOLV-B")
        api_key: EODHD API key
        start_date: Optional start date for historical data
        retries: Number of retry attempts
    
    Returns:
        Dict with 'data' (list of prices) or 'error' message
    """
    if not api_key:
        return {"error": "No API key provided"}
    
    url = f"{EODHD_BASE_URL}/eod/{ticker}.ST"
    params = {"api_token": api_key, "fmt": "json", "period": "d"}
    if start_date:
        params["from"] = start_date.isoformat()
    
    for attempt in range(retries):
        try:
            logger.info(f"EODHD API call: eod/{ticker}.ST (attempt {attempt + 1})")
            resp = requests.get(url, params=params, timeout=30)
            
            if resp.status_code == 429:
                logger.warning("Rate limit hit")
                return {"error": "rate_limit", "data": []}
            
            resp.raise_for_status()
            data = resp.json()
            logger.info(f"Fetched {len(data)} price records for {ticker}")
            return {"data": data}
            
        except requests.exceptions.RequestException as e:
            logger.warning(f"API error for {ticker}: {e}")
            if attempt < retries - 1:
                time.sleep(2 ** attempt)  # Exponential backoff
            else:
                return {"error": str(e), "data": []}
    
    return {"error": "Max retries exceeded", "data": []}


def fetch_fundamentals(ticker: str, api_key: str, retries: int = 3) -> dict:
    """
    Fetch fundamental data from EODHD API.
    
    Args:
        ticker: Stock ticker
        api_key: EODHD API key
        retries: Number of retry attempts
    
    Returns:
        Dict with extracted metrics or None for missing values
    """
    if not api_key:
        return None
    
    url = f"{EODHD_BASE_URL}/fundamentals/{ticker}.ST"
    params = {"api_token": api_key, "fmt": "json"}
    
    for attempt in range(retries):
        try:
            logger.info(f"EODHD API call: fundamentals/{ticker}.ST (attempt {attempt + 1})")
            resp = requests.get(url, params=params, timeout=30)
            
            if resp.status_code == 429:
                logger.warning("Rate limit hit")
                return None
            
            resp.raise_for_status()
            raw = resp.json()
            
            # Extract relevant metrics
            highlights = raw.get('Highlights', {})
            valuation = raw.get('Valuation', {})
            general = raw.get('General', {})
            
            result = {
                "name": general.get('Name'),
                "sector": general.get('Sector'),
                "market_cap": highlights.get('MarketCapitalization'),
                "pe": valuation.get('TrailingPE'),
                "pb": valuation.get('PriceBookMRQ'),
                "ps": valuation.get('PriceSalesTTM'),
                "roe": highlights.get('ReturnOnEquityTTM'),
                "roa": highlights.get('ReturnOnAssetsTTM'),
                "roic": None,  # Not directly available, would need calculation
                "dividend_yield": highlights.get('DividendYield'),
                "payout_ratio": highlights.get('PayoutRatio'),
            }
            
            logger.info(f"Fetched fundamentals for {ticker}")
            return result
            
        except requests.exceptions.RequestException as e:
            logger.warning(f"API error for {ticker} fundamentals: {e}")
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
            else:
                return None
    
    return None


def sync_all_stocks(api_key: str, db, full_refresh: bool = False) -> dict:
    """
    Sync stock data from EODHD API.
    Respects free tier limit (20 calls/day).
    
    Args:
        api_key: EODHD API key
        db: Database session
        full_refresh: If True, refresh all data regardless of age
    
    Returns:
        Dict with sync statistics
    """
    from backend.models import Stock, DailyPrice, Fundamentals
    
    stocks = get_omx_stockholm_stocks()
    
    result = {
        "processed": 0,
        "prices_updated": 0,
        "fundamentals_updated": 0,
        "rate_limit_hit": False,
        "errors": []
    }
    
    calls_made = 0
    max_calls = 20  # Free tier limit
    
    for ticker, name, sector in stocks:
        if calls_made >= max_calls:
            logger.warning("Reached API call limit")
            result["rate_limit_hit"] = True
            break
        
        # Check if fundamentals need refresh (> 7 days old)
        existing_fund = db.query(Fundamentals).filter(
            Fundamentals.ticker == ticker
        ).order_by(Fundamentals.fetched_date.desc()).first()
        
        needs_fund_refresh = full_refresh or not existing_fund or (
            existing_fund.fetched_date and 
            (date.today() - existing_fund.fetched_date).days > 7
        )
        
        # Check if prices need refresh
        latest_price = db.query(DailyPrice).filter(
            DailyPrice.ticker == ticker
        ).order_by(DailyPrice.date.desc()).first()
        
        needs_price_refresh = full_refresh or not latest_price or (
            (date.today() - latest_price.date).days > 1
        )
        
        # Fetch prices if needed
        if needs_price_refresh and calls_made < max_calls:
            start = latest_price.date if latest_price and not full_refresh else date.today() - timedelta(days=365)
            price_result = fetch_eod_prices(ticker, api_key, start_date=start)
            calls_made += 1
            
            if price_result.get("error") == "rate_limit":
                result["rate_limit_hit"] = True
                break
            
            if price_result.get("data"):
                for p in price_result["data"]:
                    try:
                        db.merge(DailyPrice(
                            ticker=ticker,
                            date=datetime.strptime(p['date'], '%Y-%m-%d').date(),
                            open=p.get('open'),
                            close=p.get('close'),
                            high=p.get('high'),
                            low=p.get('low'),
                            volume=p.get('volume')
                        ))
                    except Exception as e:
                        logger.error(f"Error saving price for {ticker}: {e}")
                result["prices_updated"] += 1
        
        # Fetch fundamentals if needed
        if needs_fund_refresh and calls_made < max_calls:
            fund_data = fetch_fundamentals(ticker, api_key)
            calls_made += 1
            
            if fund_data is None:
                if calls_made >= max_calls:
                    result["rate_limit_hit"] = True
                    break
                result["errors"].append(ticker)
                continue
            
            # Update Stock
            db.merge(Stock(
                ticker=ticker,
                name=fund_data.get("name") or name,
                market_cap_msek=(fund_data.get("market_cap") or 0) / 1e6,
                sector=fund_data.get("sector") or sector
            ))
            
            # Update Fundamentals
            db.add(Fundamentals(
                ticker=ticker,
                fiscal_date=date.today(),
                pe=fund_data.get("pe"),
                pb=fund_data.get("pb"),
                ps=fund_data.get("ps"),
                roe=fund_data.get("roe"),
                roa=fund_data.get("roa"),
                roic=fund_data.get("roic"),
                dividend_yield=fund_data.get("dividend_yield"),
                payout_ratio=fund_data.get("payout_ratio"),
                fetched_date=date.today()
            ))
            result["fundamentals_updated"] += 1
        
        result["processed"] += 1
    
    try:
        db.commit()
        logger.info(f"Sync complete: {result}")
    except Exception as e:
        db.rollback()
        logger.error(f"Database error: {e}")
        result["errors"].append(str(e))
    
    return result


def get_historical_prices(ticker: str, db, start_date: date, end_date: date) -> pd.DataFrame:
    """
    Query historical prices from database.
    
    Args:
        ticker: Stock ticker
        db: Database session
        start_date: Start date
        end_date: End date
    
    Returns:
        DataFrame with columns [date, open, high, low, close, volume]
    """
    from backend.models import DailyPrice
    
    prices = db.query(DailyPrice).filter(
        DailyPrice.ticker == ticker,
        DailyPrice.date >= start_date,
        DailyPrice.date <= end_date
    ).order_by(DailyPrice.date).all()
    
    if not prices:
        return pd.DataFrame(columns=['date', 'open', 'high', 'low', 'close', 'volume'])
    
    return pd.DataFrame([{
        'date': p.date,
        'open': p.open,
        'high': p.high,
        'low': p.low,
        'close': p.close,
        'volume': p.volume
    } for p in prices])


def get_sync_status(db) -> dict:
    """Get current sync status from database."""
    from backend.models import Stock, DailyPrice, Fundamentals
    
    stock_count = db.query(Stock).count()
    price_count = db.query(DailyPrice).count()
    fund_count = db.query(Fundamentals).count()
    
    latest_price = db.query(DailyPrice).order_by(DailyPrice.date.desc()).first()
    latest_fund = db.query(Fundamentals).order_by(Fundamentals.fetched_date.desc()).first()
    
    return {
        "stocks": stock_count,
        "prices": price_count,
        "fundamentals": fund_count,
        "latest_price_date": latest_price.date.isoformat() if latest_price else None,
        "latest_fundamental_date": latest_fund.fetched_date.isoformat() if latest_fund and latest_fund.fetched_date else None
    }
