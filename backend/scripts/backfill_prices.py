"""Backfill historical prices from Avanza API. Handles recently listed stocks and gaps."""
import sys
sys.path.append('.')

from datetime import datetime, timedelta
from db import SessionLocal
from models import Stock, DailyPrice
from services.avanza_fetcher_v2 import AvanzaDirectFetcher
from sqlalchemy import func
import pandas as pd
import time

def backfill_prices(max_years: int = 20):
    """Fetch historical prices. Data is saved permanently - only fetches missing dates."""
    db = SessionLocal()
    fetcher = AvanzaDirectFetcher()
    
    stocks = db.query(Stock).all()
    print(f"Backfilling up to {max_years} years of prices for {len(stocks)} stocks...")
    print("(Already fetched data is preserved - only missing dates are fetched)\n")
    
    for stock in stocks:
        ticker = stock.ticker
        stock_id = fetcher.stockholmsborsen_stocks.get(ticker) or fetcher.first_north_stocks.get(ticker)
        
        if not stock_id:
            print(f"  {ticker}: No Avanza ID, skipping")
            continue
        
        existing_min = db.query(func.min(DailyPrice.date)).filter(DailyPrice.ticker == ticker).scalar()
        existing_count = db.query(DailyPrice).filter(DailyPrice.ticker == ticker).count()
        
        print(f"  {ticker}: Have {existing_count} rows" + (f" (from {existing_min})" if existing_min else ""))
        
        total_added = 0
        consecutive_empty = 0
        
        for chunk in range(max_years // 5 + 1):
            # Calculate chunk period - go backwards from oldest existing or from now
            if existing_min:
                chunk_end = datetime.combine(existing_min, datetime.min.time()) - timedelta(days=1)
            else:
                chunk_end = datetime.now() - timedelta(days=chunk * 5 * 365)
            
            chunk_start = chunk_end - timedelta(days=5 * 365)
            
            df = _fetch_range(fetcher, stock_id, chunk_start, chunk_end)
            
            if df is None or df.empty:
                consecutive_empty += 1
                if consecutive_empty >= 2:
                    break  # No more data available after 2 empty chunks
                continue
            
            consecutive_empty = 0
            
            # Get existing dates
            existing = set(r[0] for r in db.query(DailyPrice.date).filter(DailyPrice.ticker == ticker).all())
            
            added = 0
            for _, row in df.iterrows():
                d = row['date'].date() if hasattr(row['date'], 'date') else row['date']
                if d in existing:
                    continue
                db.add(DailyPrice(
                    ticker=ticker, date=d, open=row.get('open'), close=row['close'],
                    high=row.get('high'), low=row.get('low'), volume=row.get('volume')
                ))
                added += 1
            
            db.commit()
            total_added += added
            
            # Update existing_min for next iteration
            new_min = db.query(func.min(DailyPrice.date)).filter(DailyPrice.ticker == ticker).scalar()
            if new_min == existing_min and added == 0:
                consecutive_empty += 1
                if consecutive_empty >= 2:
                    break
            else:
                existing_min = new_min
                if added > 0:
                    print(f"       Chunk {chunk+1}: Added {added} rows (now from {existing_min})")
            
            time.sleep(0.3)
        
        if total_added > 0:
            final_count = db.query(DailyPrice).filter(DailyPrice.ticker == ticker).count()
            final_min = db.query(func.min(DailyPrice.date)).filter(DailyPrice.ticker == ticker).scalar()
            print(f"       Total: {final_count} rows from {final_min}")
    
    db.close()
    print("\nDone!")

def _fetch_range(fetcher, stock_id, start, end):
    """Fetch prices for a specific date range."""
    url = f"https://www.avanza.se/_api/price-chart/stock/{stock_id}"
    params = {'from': start.strftime('%Y-%m-%d'), 'to': end.strftime('%Y-%m-%d'), 'resolution': 'day'}
    
    try:
        r = fetcher.session.get(url, params=params, timeout=15)
        if r.status_code == 200:
            ohlc = r.json().get('ohlc', [])
            if ohlc:
                df = pd.DataFrame(ohlc)
                df['date'] = pd.to_datetime(df['timestamp'], unit='ms')
                df = df.rename(columns={'totalVolumeTraded': 'volume'})
                return df[['date', 'close', 'volume', 'open', 'high', 'low']]
    except Exception as e:
        print(f"       Error: {e}")
    return None

if __name__ == "__main__":
    backfill_prices()
