"""
Script to load CSV data into the database.
Usage: python -m backend.scripts.load_csv_data

Expected CSV files in backend/data/:
- stocks.csv: ticker, name, market_cap, sector, industry
- prices.csv: ticker, date, close, volume
- fundamentals.csv: ticker, fiscal_date, pe, pb, ps, pfcf, ev_ebitda, roe, roa, roic, fcfroe, dividend_yield, payout_ratio
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.db import SessionLocal, engine, Base
from backend.models import Stock, DailyPrice, Fundamentals
from backend.services.data_fetcher import load_stocks_csv, load_prices_csv, load_fundamentals_csv

def load_all():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    
    try:
        # Load stocks
        stocks_df = load_stocks_csv()
        if not stocks_df.empty:
            db.query(Stock).delete()
            for _, row in stocks_df.iterrows():
                db.add(Stock(
                    ticker=row['ticker'],
                    name=row.get('name'),
                    market_cap=row.get('market_cap'),
                    sector=row.get('sector'),
                    industry=row.get('industry')
                ))
            print(f"Loaded {len(stocks_df)} stocks")
        
        # Load prices
        prices_df = load_prices_csv()
        if not prices_df.empty:
            db.query(DailyPrice).delete()
            for _, row in prices_df.iterrows():
                db.add(DailyPrice(
                    ticker=row['ticker'],
                    date=row['date'],
                    close=row['close'],
                    volume=row.get('volume')
                ))
            print(f"Loaded {len(prices_df)} price records")
        
        # Load fundamentals
        fund_df = load_fundamentals_csv()
        if not fund_df.empty:
            db.query(Fundamentals).delete()
            for _, row in fund_df.iterrows():
                db.add(Fundamentals(
                    ticker=row['ticker'],
                    fiscal_date=row.get('fiscal_date'),
                    pe=row.get('pe'),
                    pb=row.get('pb'),
                    ps=row.get('ps'),
                    pfcf=row.get('pfcf'),
                    ev_ebitda=row.get('ev_ebitda'),
                    roe=row.get('roe'),
                    roa=row.get('roa'),
                    roic=row.get('roic'),
                    fcfroe=row.get('fcfroe'),
                    dividend_yield=row.get('dividend_yield'),
                    payout_ratio=row.get('payout_ratio')
                ))
            print(f"Loaded {len(fund_df)} fundamentals records")
        
        db.commit()
        print("Data loading complete")
    except Exception as e:
        db.rollback()
        print(f"Error: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    load_all()
