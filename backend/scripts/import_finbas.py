#!/usr/bin/env python3
"""Import FinBas historical data into database."""

import pandas as pd
from sqlalchemy import create_engine, text
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent.parent / "data"
DB_PATH = Path(__file__).parent.parent / "app.db"

def import_finbas():
    engine = create_engine(f"sqlite:///{DB_PATH}")
    
    # Create table
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS finbas_historical (
                isin TEXT,
                ticker TEXT,
                name TEXT,
                market TEXT,
                date TEXT,
                close REAL,
                high REAL,
                low REAL,
                volume REAL,
                book_value REAL,
                market_cap REAL,
                PRIMARY KEY (isin, date)
            )
        """))
        conn.commit()
    
    # Load data
    print("Loading FinBas data...")
    df = pd.read_csv(DATA_DIR / "Stockholm_daily.csv", sep=";", low_memory=False)
    
    # Filter to SSE + First North
    df = df[df["marketname"].isin(["SSE", "SSEFN"])]
    print(f"Rows after market filter: {len(df):,}")
    
    # Convert columns
    df["lastad"] = pd.to_numeric(df["lastad"], errors="coerce")
    df["highad"] = pd.to_numeric(df["highad"], errors="coerce")
    df["lowad"] = pd.to_numeric(df["lowad"], errors="coerce")
    df["oatad"] = pd.to_numeric(df["oatad"], errors="coerce")
    df["bookvalue"] = pd.to_numeric(df["bookvalue"], errors="coerce")
    df["totalmarketvalue"] = pd.to_numeric(df["totalmarketvalue"], errors="coerce")
    
    # Prepare for insert
    df_insert = pd.DataFrame({
        "isin": df["isin"],
        "ticker": df["ticker"],
        "name": df["name"],
        "market": df["marketname"],
        "date": df["day"],
        "close": df["lastad"],
        "high": df["highad"],
        "low": df["lowad"],
        "volume": df["oatad"],
        "book_value": df["bookvalue"],
        "market_cap": df["totalmarketvalue"],
    })
    
    # Drop rows with no price
    df_insert = df_insert[df_insert["close"].notna()]
    print(f"Rows with price data: {len(df_insert):,}")
    
    # Insert
    print("Inserting into database...")
    df_insert.to_sql("finbas_historical", engine, if_exists="replace", index=False)
    
    # Create index
    with engine.connect() as conn:
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_finbas_date ON finbas_historical(date)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_finbas_isin ON finbas_historical(isin)"))
        conn.commit()
    
    # Summary
    with engine.connect() as conn:
        r = conn.execute(text("SELECT COUNT(*), COUNT(DISTINCT isin), MIN(date), MAX(date) FROM finbas_historical")).fetchone()
        print(f"\nImported: {r[0]:,} rows, {r[1]} stocks, {r[2]} to {r[3]}")
        
        r = conn.execute(text("SELECT COUNT(*) FROM finbas_historical WHERE market_cap IS NOT NULL")).fetchone()
        print(f"Rows with market cap: {r[0]:,}")
        
        r = conn.execute(text("SELECT COUNT(*) FROM finbas_historical WHERE book_value IS NOT NULL")).fetchone()
        print(f"Rows with book value: {r[0]:,}")

if __name__ == "__main__":
    import_finbas()
