#!/usr/bin/env python3
"""
Populate historical price data for backtesting.
Run: cd backend && source .venv/bin/activate && python scripts/populate_historical.py
"""
import sys
sys.path.insert(0, '.')

from db import SessionLocal
from models import Stock, DailyPrice
from services.avanza_fetcher_v2 import AvanzaDirectFetcher
from sqlalchemy import func
import time

def populate_historical(years=25, min_market_cap=None):
    """
    Populate historical prices. 
    min_market_cap=None fetches ALL stocks (recommended for backtesting).
    """
    db = SessionLocal()
    fetcher = AvanzaDirectFetcher()
    
    # Get stocks to process - filter only by stock_type, not market cap
    # (market cap changes over time, we need historical data for all)
    query = db.query(Stock).filter(
        Stock.avanza_id != None,
        Stock.stock_type == 'stock'  # Only real stocks, no ETFs/certificates
    )
    if min_market_cap:
        query = query.filter(Stock.market_cap_msek >= min_market_cap)
    
    stocks = query.all()
    
    print(f'=== HISTORICAL DATA POPULATION ===')
    print(f'Stocks: {len(stocks)}')
    print(f'Years: {years}')
    print(f'Min market cap: {min_market_cap} MSEK')
    print()
    
    # Check current data
    before_count = db.query(DailyPrice).count()
    print(f'Current records in DB: {before_count:,}')
    print()
    
    total_added = 0
    errors = 0
    
    for i, stock in enumerate(stocks):
        try:
            # Fetch extended historical data
            df = fetcher.get_historical_prices_extended(stock.avanza_id, years=years)
            
            if df is None or len(df) == 0:
                print(f'[{i+1}/{len(stocks)}] {stock.ticker}: No data')
                continue
            
            # Get existing dates for this ticker
            existing = set(
                d[0] for d in db.query(DailyPrice.date)
                .filter(DailyPrice.ticker == stock.ticker).all()
            )
            
            # Add new records
            added = 0
            for _, row in df.iterrows():
                price_date = row['date'].date()
                if price_date not in existing:
                    db.add(DailyPrice(
                        ticker=stock.ticker,
                        date=price_date,
                        open=row.get('open'),
                        high=row.get('high'),
                        low=row.get('low'),
                        close=row['close'],
                        volume=row.get('volume')
                    ))
                    added += 1
            
            if added > 0:
                db.commit()
                total_added += added
            
            status = f'+{added}' if added > 0 else 'up-to-date'
            print(f'[{i+1}/{len(stocks)}] {stock.ticker}: {status} ({len(df)} fetched, {len(existing)} existed)')
            
            time.sleep(0.2)  # Rate limit
            
        except Exception as e:
            errors += 1
            print(f'[{i+1}/{len(stocks)}] {stock.ticker}: ERROR - {e}')
            db.rollback()
    
    # Final stats
    after_count = db.query(DailyPrice).count()
    min_date = db.query(func.min(DailyPrice.date)).scalar()
    max_date = db.query(func.max(DailyPrice.date)).scalar()
    
    print()
    print(f'=== COMPLETE ===')
    print(f'New records: {total_added:,}')
    print(f'Errors: {errors}')
    print(f'Total records: {after_count:,}')
    print(f'Date range: {min_date} to {max_date}')
    
    db.close()

if __name__ == '__main__':
    # Fetch all stocks (no market cap filter) for proper backtesting
    populate_historical(years=25, min_market_cap=None)
