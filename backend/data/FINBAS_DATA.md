# FinBas Historical Data

## Overview
Historical Swedish stock data from FinBas (Swedish House of Finance), covering 1998-2023.

**Source:** https://data.houseoffinance.se/finbas/  
**License:** Academic research only (SWAMID login required)

## Data Coverage
- **Date range:** 1998-01-30 to 2023-06-30
- **Stocks:** 1,830 unique ISINs, 1,841 tickers
- **Markets:** SSE (Stockholmsbörsen) + SSEFN (First North)
- **Rows:** 2.88 million

## Database Tables

### `finbas_historical`
Main historical data table.

| Column | Type | Description |
|--------|------|-------------|
| isin | TEXT | ISIN identifier |
| ticker | TEXT | FinBas ticker (e.g., "ATCO-A.SE") |
| name | TEXT | Company name |
| market | TEXT | SSE or SSEFN |
| date | TEXT | Date (YYYY-MM-DD) |
| close | REAL | Adjusted closing price |
| high | REAL | Adjusted high |
| low | REAL | Adjusted low |
| volume | REAL | Trading volume |
| book_value | REAL | Book value (from annual reports) |
| market_cap | REAL | Total market capitalization (SEK) |

**Note:** Market cap is recorded monthly (end of month only).

### `ticker_all_isins`
Maps normalized tickers to ALL historical ISINs (stocks change ISIN over time).

| Column | Type | Description |
|--------|------|-------------|
| normalized_ticker | TEXT | Ticker without ".SE" suffix (e.g., "ATCO A") |
| isin | TEXT | ISIN identifier |

### `ticker_isin_map`
Maps normalized tickers to their LATEST ISIN only.

## How to Query

### Get historical data for a stock (handles ISIN changes):
```sql
SELECT f.*
FROM stocks s
JOIN ticker_all_isins t ON t.normalized_ticker = s.ticker
JOIN finbas_historical f ON f.isin = t.isin
WHERE s.ticker = 'ATCO A'
ORDER BY f.date
```

### Get stocks with market cap >= 2B SEK on a date:
```sql
SELECT DISTINCT s.ticker, f.market_cap
FROM stocks s
JOIN ticker_all_isins t ON t.normalized_ticker = s.ticker
JOIN finbas_historical f ON f.isin = t.isin
WHERE f.date = '2015-01-30' AND f.market_cap >= 2000000000
```

## Backup & Restore

### Backup Location
- **SQLite backup:** `backend/data/backups/finbas_backup_YYYYMMDD.db`
- **Raw CSV files:** `data/sthlm_daily.csv`, `data/FN_Daily.csv`

### Restore from Backup
```python
import sqlite3

# Connect to backup and main DB
backup = sqlite3.connect('data/backups/finbas_backup_20251231.db')
main = sqlite3.connect('app.db')

# Restore each table
for table in ['finbas_historical', 'ticker_all_isins', 'ticker_isin_map']:
    # Drop existing
    main.execute(f'DROP TABLE IF EXISTS {table}')
    
    # Get schema from backup
    schema = backup.execute(f"SELECT sql FROM sqlite_master WHERE name='{table}'").fetchone()[0]
    main.execute(schema)
    
    # Copy data
    data = backup.execute(f'SELECT * FROM {table}').fetchall()
    cols = len(data[0]) if data else 0
    main.executemany(f"INSERT INTO {table} VALUES ({','.join(['?']*cols)})", data)
    main.commit()
    print(f'Restored {table}: {len(data)} rows')

backup.close()
main.close()
```

### Re-import from CSV
```bash
cd backend
python scripts/import_finbas.py
```

## Re-downloading from FinBas

1. Go to https://data.houseoffinance.se/finbas/
2. Login with SWAMID (Swedish university credentials)
3. Select preset: "Stockholm Stock Exchange"
4. Date range: 1998-01-01 to 2023-06-30
5. Frequency: Daily
6. Select: LAST, HIGH, LOW, OAT, BOOK VALUE, MARKET CAPITALIZATION
7. Run query and download CSV
8. Repeat for "Stockholm Stock Exchange First North"
9. Save as `data/sthlm_daily.csv` and `data/FN_Daily.csv`
10. Run `python scripts/import_finbas.py`

## Important Notes

1. **Data ends June 2023** - Use Avanza data for 2023-2025
2. **Market cap is monthly** - Only available at month-end dates
3. **ISINs change over time** - Use `ticker_all_isins` for full history
4. **Academic use only** - FinBas license restricts commercial use
