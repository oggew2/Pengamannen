"""Stock scanner service - discovers new stocks from Avanza with multi-threading."""
import requests
import time
import json
import sqlite3
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import List, Dict, Optional

# Default scan ranges based on known stock distribution
DEFAULT_RANGES = [
    {"start": 5000, "end": 100000, "name": "Classic Stocks"},
    {"start": 100000, "end": 400000, "name": "Mid Range"},
    {"start": 400000, "end": 800000, "name": "Upper Range"},
    {"start": 800000, "end": 1200000, "name": "Recent Stocks 1"},
    {"start": 1200000, "end": 1600000, "name": "Recent Stocks 2"},
    {"start": 1600000, "end": 2000000, "name": "Latest Stocks"},
]

ETF_PATTERNS = ['XACT', 'BULL ', 'BEAR ', 'SHRT ', 'LONG ', 'X2 ', 'X3 ', 'X4 ', 'X5 ']
# Avanza tracker products (commodities, crypto, gaming, etc.)
AVA_TRACKER_PATTERNS = [' AVA', 'AVA ']
# Nordnet and other tracker products
TRACKER_PATTERNS = ['TRACK', 'SKALA ', 'AXESS ', ' NORDNET']
# ETF ticker prefixes (Xtrackers, iShares, etc.)
ETF_PREFIXES = ['XDAX', 'XD3E', 'XRS2', 'XNAS', 'XSPX', 'XMWO', 'XMEM', 'XESX']
# Crypto tracker patterns
CRYPTO_PATTERNS = ['BITCOIN', 'ETHEREUM', 'XBT', 'CRYPTO']
# Name patterns indicating ETPs (not stocks)
ETP_NAME_PATTERNS = ['WisdomTree', 'Physical Solana', 'Physical Bitcoin', 'Physical Ethereum',
                     'Xtrackers', 'UCITS ETF', 'Tracker', 'CoinShares']
SCAN_STATE_FILE = 'scan_state.json'

# Regex for warrants/options (e.g., ASSAB7R200, HMB6B170, NDASE6C140)
import re
WARRANT_PATTERN = re.compile(r'^[A-Z]+\d+[A-Z]\d+$')  # TICKER + digits + letter + digits
MINI_PATTERN = re.compile(r'^MINI [LS] ')  # Mini futures


def classify_stock_type(ticker: str, name: str = '') -> str:
    """Classify stock type based on ticker and name patterns."""
    ticker_upper = ticker.upper()
    name_upper = name.upper() if name else ''
    
    # Warrants/options (ASSAB7R200, HMB6B170, etc.)
    if WARRANT_PATTERN.match(ticker_upper):
        return 'etf_certificate'
    # Mini futures
    if MINI_PATTERN.match(ticker_upper):
        return 'etf_certificate'
    # ETF/Certificate patterns
    if any(p in ticker_upper for p in ETF_PATTERNS):
        return 'etf_certificate'
    # ETF prefixes
    if any(ticker_upper.startswith(p) for p in ETF_PREFIXES):
        return 'etf_certificate'
    # Crypto trackers
    if any(p in ticker_upper for p in CRYPTO_PATTERNS):
        return 'etf_certificate'
    # Avanza tracker products (OLJA AVA, GULD AVA, etc.)
    if any(p in ticker_upper for p in AVA_TRACKER_PATTERNS):
        return 'etf_certificate'
    # Other tracker certificates
    if any(p in ticker_upper for p in TRACKER_PATTERNS):
        return 'etf_certificate'
    # Tickers ending with ' H' (hedge products)
    if ticker_upper.endswith(' H'):
        return 'etf_certificate'
    # Name-based ETP detection
    if any(p.upper() in name_upper for p in ETP_NAME_PATTERNS):
        return 'etf_certificate'
    # Preference shares
    if ' PREF' in ticker_upper:
        return 'preference'
    # Swedish Depositary Receipts
    if ' SDB' in ticker_upper or ticker_upper.endswith('SDB'):
        return 'sdb'
    return 'stock'


def load_scan_state() -> Dict:
    """Load scan state from file."""
    try:
        with open(SCAN_STATE_FILE) as f:
            return json.load(f)
    except:
        return {"ranges": {}, "last_full_scan": None}


def save_scan_state(state: Dict):
    """Save scan state to file."""
    with open(SCAN_STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)


def scan_single_id(stock_id: int, session: requests.Session) -> Optional[Dict]:
    """Scan a single Avanza ID."""
    try:
        r = session.get(f'https://www.avanza.se/_api/market-guide/stock/{stock_id}', timeout=3)
        if r.status_code == 200:
            data = r.json()
            ticker = data.get('listing', {}).get('tickerSymbol', '')
            market = data.get('listing', {}).get('marketPlaceName', '')
            name = data.get('name', '')
            
            # Only Swedish markets - exclude First North from other countries
            valid_markets = ['Stockholmsbörsen', 'First North Stockholm']
            if ticker and any(m in market for m in valid_markets):
                return {
                    'ticker': ticker,
                    'name': name,
                    'market': market,
                    'stock_type': classify_stock_type(ticker, name),
                    'avanza_id': str(stock_id)
                }
    except:
        pass
    return None


def scan_range_threaded(start: int, end: int, existing_tickers: set, max_workers: int = 10) -> tuple:
    """Scan a range using multiple threads. Returns (new_stocks, all_found_stocks)."""
    import logging
    logger = logging.getLogger(__name__)
    
    new_stocks = []
    all_found = []  # All stocks found (for updating avanza_id)
    found_tickers = set()
    
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'Accept': 'application/json',
    })
    
    total = end - start
    completed = 0
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(scan_single_id, i, session): i for i in range(start, end)}
        
        for future in as_completed(futures):
            completed += 1
            if completed % 1000 == 0 or (completed < 5000 and completed % 200 == 0):
                logger.info(f"Scan progress: {completed}/{total} IDs checked, {len(all_found)} stocks found")
            
            result = future.result()
            if result and result['ticker'] not in found_tickers:
                all_found.append(result)
                found_tickers.add(result['ticker'])
                
                if result['ticker'] not in existing_tickers:
                    new_stocks.append(result)
                    logger.info(f"NEW: {result['ticker']} ({result['name']}) - ID {result['avanza_id']}")
    
    return new_stocks, all_found


def scan_for_new_stocks(
    db_path: str = 'app.db',
    ranges: Optional[List[Dict]] = None,
    max_workers: int = 10
) -> Dict:
    """
    Scan Avanza for stocks not in database.
    
    Args:
        db_path: Path to SQLite database
        ranges: List of {"start": int, "end": int} ranges to scan
        max_workers: Number of parallel threads
    """
    import logging
    logger = logging.getLogger(__name__)
    
    if ranges is None:
        ranges = DEFAULT_RANGES
    
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    cur.execute('SELECT ticker FROM stocks')
    existing_tickers = {row[0] for row in cur.fetchall()}
    
    state = load_scan_state()
    all_new_stocks = []
    all_found_stocks = []
    scanned_ids = 0
    
    for r in ranges:
        start, end = r.get('start', r.get('from', 0)), r.get('end', r.get('to', 0))
        if start >= end:
            continue
            
        range_key = f"{start}-{end}"
        logger.info(f"Scanning range {start}-{end}...")
        new_stocks, found_stocks = scan_range_threaded(start, end, existing_tickers, max_workers)
        
        # Update existing tickers to avoid duplicates across ranges
        for s in new_stocks:
            existing_tickers.add(s['ticker'])
        
        all_new_stocks.extend(new_stocks)
        all_found_stocks.extend(found_stocks)
        scanned_ids += (end - start)
        
        # Update state
        state["ranges"][range_key] = {
            "last_scanned": datetime.now().isoformat(),
            "stocks_found": len(found_stocks)
        }
    
    # Insert new stocks
    for stock in all_new_stocks:
        try:
            cur.execute('''
                INSERT INTO stocks (ticker, name, market, stock_type, avanza_id, sector, market_cap_msek)
                VALUES (?, ?, ?, ?, ?, 'Unknown', 0)
            ''', (stock['ticker'], stock['name'], stock['market'], stock['stock_type'], stock['avanza_id']))
        except:
            pass
    
    # Update avanza_id for ALL found stocks (including existing)
    updated = 0
    for stock in all_found_stocks:
        cur.execute('''
            UPDATE stocks SET avanza_id = ?, market = ?, name = COALESCE(NULLIF(name, ''), ?)
            WHERE ticker = ? AND (avanza_id IS NULL OR avanza_id = '')
        ''', (stock['avanza_id'], stock['market'], stock['name'], stock['ticker']))
        if cur.rowcount > 0:
            updated += 1
    
    logger.info(f"Updated avanza_id for {updated} existing stocks")
    
    conn.commit()
    conn.close()
    
    state["last_full_scan"] = datetime.now().isoformat()
    save_scan_state(state)
    
    return {
        'scanned_ids': scanned_ids,
        'new_stocks_found': len(all_new_stocks),
        'new_stocks': all_new_stocks[:50],
        'ranges_scanned': len(ranges)
    }


def get_scan_status() -> Dict:
    """Get current stock counts and scan state."""
    conn = sqlite3.connect('app.db')
    cur = conn.cursor()
    
    cur.execute('SELECT stock_type, COUNT(*) FROM stocks GROUP BY stock_type')
    by_type = {row[0]: row[1] for row in cur.fetchall()}
    
    cur.execute('SELECT market, COUNT(*) FROM stocks WHERE stock_type = "stock" GROUP BY market')
    by_market = {row[0] or 'Unknown': row[1] for row in cur.fetchall()}
    
    cur.execute('SELECT COUNT(*) FROM stocks')
    total = cur.fetchone()[0]
    conn.close()
    
    state = load_scan_state()
    
    return {
        'total': total,
        'by_type': by_type,
        'by_market': by_market,
        'real_stocks': by_type.get('stock', 0) + by_type.get('sdb', 0),
        'scan_state': state,
        'default_ranges': DEFAULT_RANGES
    }


def get_scan_ranges() -> List[Dict]:
    """Get available scan ranges with their status."""
    state = load_scan_state()
    ranges_with_status = []
    
    for r in DEFAULT_RANGES:
        range_key = f"{r['start']}-{r['end']}"
        range_state = state.get("ranges", {}).get(range_key, {})
        ranges_with_status.append({
            **r,
            "last_scanned": range_state.get("last_scanned"),
            "stocks_found": range_state.get("stocks_found", 0)
        })
    
    return ranges_with_status
