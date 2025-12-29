"""
Data fetcher service - stub for CSV/API data ingestion.
TODO: Implement actual data fetching logic when data sources are defined.
"""
import pandas as pd
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"

def load_stocks_csv(path: Path = None) -> pd.DataFrame:
    """Load stocks from CSV file."""
    path = path or DATA_DIR / "stocks.csv"
    if not path.exists():
        return pd.DataFrame(columns=['ticker', 'name', 'market_cap', 'sector', 'industry'])
    return pd.read_csv(path)

def load_prices_csv(path: Path = None) -> pd.DataFrame:
    """Load daily prices from CSV file."""
    path = path or DATA_DIR / "prices.csv"
    if not path.exists():
        return pd.DataFrame(columns=['ticker', 'date', 'close', 'volume'])
    df = pd.read_csv(path)
    df['date'] = pd.to_datetime(df['date']).dt.date
    return df

def load_fundamentals_csv(path: Path = None) -> pd.DataFrame:
    """Load fundamentals from CSV file."""
    path = path or DATA_DIR / "fundamentals.csv"
    if not path.exists():
        return pd.DataFrame(columns=['ticker', 'fiscal_date', 'pe', 'pb', 'ps', 'pfcf', 
                                      'ev_ebitda', 'roe', 'roa', 'roic', 'fcfroe', 
                                      'dividend_yield', 'payout_ratio'])
    df = pd.read_csv(path)
    if 'fiscal_date' in df.columns:
        df['fiscal_date'] = pd.to_datetime(df['fiscal_date']).dt.date
    return df

# TODO: Add API fetching functions when external data sources are defined
