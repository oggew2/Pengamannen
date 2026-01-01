"""Stock validator - checks if stocks are still active on Avanza."""
import requests
import logging
from datetime import date
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)

def check_stock_status(avanza_id: str, session: requests.Session) -> Tuple[bool, bool]:
    """Check if stock exists and is tradeable on Avanza.
    
    Returns: (exists, is_tradeable)
    """
    try:
        r = session.get(f'https://www.avanza.se/_api/market-guide/stock/{avanza_id}', timeout=5)
        if r.status_code == 404:
            return False, False
        if r.status_code == 200:
            data = r.json()
            tradeable = data.get('listing', {}).get('marketTradesAvailable', False)
            return True, tradeable
        return False, False
    except:
        return None, None  # Network error, don't change status


def validate_stocks(db, max_workers: int = 10, limit: int = None) -> Dict:
    """Validate stocks against Avanza API and update is_active flag.
    
    Args:
        db: Database session
        max_workers: Parallel threads for API calls
        limit: Max stocks to check (None = all)
    """
    from models import Stock
    
    today = date.today()
    
    # Get stocks with avanza_id that haven't been validated recently
    query = db.query(Stock).filter(
        Stock.avanza_id != None,
        Stock.avanza_id != ''
    )
    if limit:
        query = query.limit(limit)
    
    stocks = query.all()
    logger.info(f"Validating {len(stocks)} stocks against Avanza API")
    
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)',
        'Accept': 'application/json',
    })
    
    results = {'validated': 0, 'active': 0, 'inactive': 0, 'errors': 0}
    
    def check_one(stock):
        exists, tradeable = check_stock_status(stock.avanza_id, session)
        return stock.ticker, exists, tradeable
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(check_one, s): s for s in stocks}
        
        for future in as_completed(futures):
            ticker, exists, tradeable = future.result()
            stock = db.query(Stock).filter(Stock.ticker == ticker).first()
            
            if exists is None:
                results['errors'] += 1
                continue
            
            stock.last_validated = today
            
            if exists and tradeable:
                stock.is_active = True
                results['active'] += 1
            else:
                stock.is_active = False
                results['inactive'] += 1
            
            results['validated'] += 1
            
            if results['validated'] % 100 == 0:
                logger.info(f"Validated {results['validated']}/{len(stocks)} stocks")
    
    db.commit()
    logger.info(f"Validation complete: {results}")
    return results


def mark_stocks_with_fundamentals_active(db, min_expected: int = 500) -> Dict:
    """Mark stocks with fundamentals as active. Includes safety checks.
    
    Args:
        db: Database session
        min_expected: Minimum expected stocks with fundamentals (safety threshold)
    
    Returns:
        Dict with results and any warnings
    """
    from models import Stock, Fundamentals
    
    today = date.today()
    
    # Get current active count BEFORE changes
    current_active = db.query(Stock).filter(
        Stock.stock_type.in_(['stock', 'sdb']),
        Stock.is_active == True
    ).count()
    
    # Get tickers with fundamentals
    fund_tickers = set(r[0] for r in db.query(Fundamentals.ticker).all())
    new_count = len(fund_tickers)
    
    # SAFETY CHECK: Don't proceed if fundamentals count is suspiciously low
    if new_count < min_expected:
        logger.error(f"SAFETY ABORT: Only {new_count} stocks with fundamentals (min: {min_expected}). "
                     f"Possible sync failure - not updating is_active flags.")
        return {
            'success': False,
            'error': 'Too few stocks with fundamentals - possible sync failure',
            'found': new_count,
            'min_expected': min_expected,
            'current_active': current_active
        }
    
    # SAFETY CHECK: Don't allow massive drops (>50% reduction)
    if current_active > 0 and new_count < current_active * 0.5:
        logger.error(f"SAFETY ABORT: Would reduce active stocks from {current_active} to {new_count} (>50% drop). "
                     f"Possible sync failure - not updating is_active flags.")
        return {
            'success': False,
            'error': 'Would cause >50% reduction in active stocks - possible sync failure',
            'found': new_count,
            'current_active': current_active
        }
    
    # Safe to proceed - mark stocks with fundamentals as active
    updated = 0
    for ticker in fund_tickers:
        stock = db.query(Stock).filter(Stock.ticker == ticker).first()
        if stock:
            stock.is_active = True
            stock.last_validated = today
            updated += 1
    
    db.commit()
    logger.info(f"Marked {updated} stocks with fundamentals as active")
    
    return {
        'success': True,
        'updated': updated,
        'previous_active': current_active
    }


def get_active_stock_count(db) -> Dict:
    """Get counts of active vs inactive stocks."""
    from models import Stock
    from sqlalchemy import func
    
    total = db.query(Stock).filter(Stock.stock_type.in_(['stock', 'sdb'])).count()
    active = db.query(Stock).filter(
        Stock.stock_type.in_(['stock', 'sdb']),
        Stock.is_active == True
    ).count()
    
    return {
        'total_real_stocks': total,
        'active': active,
        'inactive': total - active,
        'active_percent': round(active / total * 100, 1) if total > 0 else 0
    }
