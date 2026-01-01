#!/usr/bin/env python3
"""
Import scraped Börsdata data into the database.

Usage:
    python scripts/import_borsdata.py
"""

import json
import sys
from pathlib import Path
from datetime import datetime, date

sys.path.insert(0, str(Path(__file__).parent.parent))

from db import SessionLocal, engine
from sqlalchemy import Column, Integer, String, Float, Date, text
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class HistoricalFundamentals(Base):
    """Quarterly fundamentals - one row per stock per quarter."""
    __tablename__ = "historical_fundamentals"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    borsdata_id = Column(Integer, index=True)
    ticker = Column(String, index=True)
    name = Column(String)
    sector = Column(String, index=True)
    industry = Column(String)
    report_date = Column(Date, index=True)
    
    # Valuation
    pe = Column(Float)
    ps = Column(Float)
    ev_ebit = Column(Float)
    peg = Column(Float)
    
    # Profitability
    roe = Column(Float)
    roa = Column(Float)
    roic = Column(Float)
    roc = Column(Float)
    
    # Margins
    gross_margin = Column(Float)
    ebit_margin = Column(Float)
    profit_margin = Column(Float)
    fcf_margin = Column(Float)
    ebitda_margin = Column(Float)
    
    # Per-share
    eps = Column(Float)
    book_value_per_share = Column(Float)
    fcf_per_share = Column(Float)
    dividend_per_share = Column(Float)
    revenue_per_share = Column(Float)
    
    # Absolute (MSEK)
    revenue = Column(Float)
    ebitda = Column(Float)
    ebit = Column(Float)
    net_income = Column(Float)
    equity = Column(Float)
    total_assets = Column(Float)
    net_debt = Column(Float)
    fcf = Column(Float)
    operating_cf = Column(Float)
    shares = Column(Float)
    
    # Balance sheet
    equity_ratio = Column(Float)
    debt_equity = Column(Float)
    current_ratio = Column(Float)
    net_debt_ebitda = Column(Float)
    
    # Dividend (annual)
    dividend_yield = Column(Float)
    payout_ratio = Column(Float)


class ReportDate(Base):
    """Report publication dates - for point-in-time accuracy."""
    __tablename__ = "report_dates"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    borsdata_id = Column(Integer, index=True)
    ticker = Column(String, index=True)
    report_date = Column(Date, index=True)  # When report was published
    report_type = Column(String)  # Q1, Q2, Q3, Q4
    revenue = Column(Float)
    eps = Column(Float)


class BorsdataPrice(Base):
    """Daily prices from Börsdata (up to 28 years)."""
    __tablename__ = "borsdata_prices"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    borsdata_id = Column(Integer, index=True)
    ticker = Column(String, index=True)
    date = Column(Date, index=True)
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    volume = Column(Float)


def create_tables():
    Base.metadata.create_all(engine)
    print("✓ Tables created")


def import_data():
    data_file = Path(__file__).parent.parent / "data" / "borsdata_fundamentals.json"
    
    if not data_file.exists():
        print(f"ERROR: {data_file} not found. Run scrape_borsdata.py first.")
        return
    
    with open(data_file) as f:
        data = json.load(f)
    
    print(f"Loaded {len(data)} stocks")
    
    db = SessionLocal()
    
    try:
        # Clear existing
        db.execute(text("DELETE FROM historical_fundamentals"))
        db.execute(text("DELETE FROM report_dates"))
        db.execute(text("DELETE FROM borsdata_prices"))
        db.commit()
        print("✓ Cleared existing data")
        
        fund_rows = 0
        report_rows = 0
        price_rows = 0
        
        for borsdata_id, stock in data.items():
            ticker = stock.get('ticker')
            name = stock.get('name')
            sector = stock.get('sector')
            industry = stock.get('industry')
            
            # Import quarterly fundamentals
            quarterly = stock.get('fundamentals', {}).get('quarterly', {})
            annual = stock.get('fundamentals', {}).get('annual', {})
            
            for date_str, vals in quarterly.items():
                try:
                    report_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                except:
                    continue
                
                # Get annual dividend data for this year
                year = report_date.year
                annual_vals = annual.get(year, {})
                
                row = HistoricalFundamentals(
                    borsdata_id=int(borsdata_id),
                    ticker=ticker,
                    name=name,
                    sector=sector,
                    industry=industry,
                    report_date=report_date,
                    pe=vals.get('pe'),
                    ps=vals.get('ps'),
                    ev_ebit=vals.get('ev_ebit'),
                    peg=vals.get('peg'),
                    roe=vals.get('roe'),
                    roa=vals.get('roa'),
                    roic=vals.get('roic'),
                    roc=vals.get('roc'),
                    gross_margin=vals.get('gross_margin'),
                    ebit_margin=vals.get('ebit_margin'),
                    profit_margin=vals.get('profit_margin'),
                    fcf_margin=vals.get('fcf_margin'),
                    ebitda_margin=vals.get('ebitda_margin'),
                    eps=vals.get('eps'),
                    book_value_per_share=vals.get('book_value_per_share'),
                    fcf_per_share=vals.get('fcf_per_share'),
                    dividend_per_share=vals.get('dividend_per_share'),
                    revenue_per_share=vals.get('revenue_per_share'),
                    revenue=vals.get('revenue'),
                    ebitda=vals.get('ebitda'),
                    ebit=vals.get('ebit'),
                    net_income=vals.get('net_income'),
                    equity=vals.get('equity'),
                    total_assets=vals.get('total_assets'),
                    net_debt=vals.get('net_debt'),
                    fcf=vals.get('fcf'),
                    operating_cf=vals.get('operating_cf'),
                    shares=vals.get('shares'),
                    equity_ratio=vals.get('equity_ratio'),
                    debt_equity=vals.get('debt_equity'),
                    current_ratio=vals.get('current_ratio'),
                    net_debt_ebitda=vals.get('net_debt_ebitda'),
                    dividend_yield=annual_vals.get('dividend_yield'),
                    payout_ratio=annual_vals.get('payout_ratio'),
                )
                db.add(row)
                fund_rows += 1
            
            # Import report dates
            for report in stock.get('report_dates', []):
                try:
                    report_date = datetime.fromtimestamp(report['t']).date()
                    row = ReportDate(
                        borsdata_id=int(borsdata_id),
                        ticker=ticker,
                        report_date=report_date,
                        report_type=report.get('name'),
                        revenue=report.get('oms'),
                        eps=report.get('vinst'),
                    )
                    db.add(row)
                    report_rows += 1
                except:
                    pass
            
            # Import prices
            prices = stock.get('prices')
            if prices and prices.get('timestamps'):
                timestamps = prices['timestamps']
                opens = prices.get('open', [])
                highs = prices.get('high', [])
                lows = prices.get('low', [])
                closes = prices.get('close', [])
                volumes = prices.get('volume', [])
                
                for i, ts in enumerate(timestamps):
                    try:
                        price_date = datetime.fromtimestamp(ts).date()
                        row = BorsdataPrice(
                            borsdata_id=int(borsdata_id),
                            ticker=ticker,
                            date=price_date,
                            open=opens[i] if i < len(opens) else None,
                            high=highs[i] if i < len(highs) else None,
                            low=lows[i] if i < len(lows) else None,
                            close=closes[i] if i < len(closes) else None,
                            volume=volumes[i] if i < len(volumes) else None,
                        )
                        db.add(row)
                        price_rows += 1
                    except:
                        pass
            
            # Commit every 50 stocks
            if fund_rows % 5000 == 0:
                db.commit()
                print(f"  Progress: {fund_rows} fundamentals, {price_rows} prices...")
        
        db.commit()
        
        print(f"\n✓ Imported:")
        print(f"  Fundamentals: {fund_rows:,} rows")
        print(f"  Report dates: {report_rows:,} rows")
        print(f"  Prices: {price_rows:,} rows")
        
    finally:
        db.close()


def main():
    print("=" * 50)
    print("Import Börsdata Data")
    print("=" * 50)
    
    create_tables()
    import_data()
    
    print("\n✓ Import complete!")


if __name__ == '__main__':
    main()
