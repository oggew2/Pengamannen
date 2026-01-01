# Börslabbet App Architecture

> Technical documentation for the quantitative Swedish stock strategy platform.

## Quick Reference

| What | Where |
|------|-------|
| API endpoints | [`backend/main.py`](backend/main.py) |
| Database models | [`backend/models.py`](backend/models.py) |
| Strategy calculations | [`backend/services/ranking.py`](backend/services/ranking.py) |
| Data fetching | [`backend/services/avanza_fetcher_v2.py`](backend/services/avanza_fetcher_v2.py) |
| Ranking cache | [`backend/services/ranking_cache.py`](backend/services/ranking_cache.py) |
| Backtesting | [`backend/services/backtesting.py`](backend/services/backtesting.py) |
| API cache | [`backend/services/smart_cache.py`](backend/services/smart_cache.py) |
| Scheduled jobs | [`backend/jobs/scheduler.py`](backend/jobs/scheduler.py) |
| Strategy config | [`backend/config/strategies.yaml`](backend/config/strategies.yaml) |
| System tests | [`backend/tests/test_system.py`](backend/tests/test_system.py) |

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         FRONTEND                                 │
│  React + TypeScript + Chakra UI (localhost:5173)                │
│  frontend/src/pages/*.tsx                                        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      FASTAPI BACKEND                             │
│  backend/main.py (localhost:8000)                                │
│  ├── /strategies/{name}  → Rankings from StrategySignal table   │
│  ├── /data/sync-now      → Trigger avanza_sync()                │
│  └── /backtest           → backtest_strategy()                  │
└─────────────────────────────────────────────────────────────────┘
                              │
          ┌───────────────────┼───────────────────┐
          ▼                   ▼                   ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│   SQLite DB     │  │  Smart Cache    │  │  Avanza API     │
│   app.db        │  │  smart_cache.db │  │  (External)     │
└─────────────────┘  └─────────────────┘  └─────────────────┘
```

## Data Flow

### Daily Sync (`avanza_sync()` in `avanza_fetcher_v2.py`)

```
1. Clear caches (smart_cache.clear_all() + invalidate_cache())
   
2. Fetch fundamentals (734 stocks, 10 threads) ──► ~2 seconds
   └─► Save to: Stock table (merge), Fundamentals table (delete+insert)
   
3. Fetch prices (400 days, 10 threads) ──────────► ~14 seconds
   └─► Save to: DailyPrice table (merge on ticker+date)
   
4. Compute rankings (compute_all_rankings()) ────► ~35 seconds
   └─► Save to: StrategySignal table (delete all + insert)

Total: ~51 seconds
```

### User Request Flow

```
GET /strategies/sammansatt_momentum
         │
         ▼
_compute_strategy_rankings() in main.py
         │
         ├─► Query StrategySignal WHERE calculated_date = today
         │   │
         │   ├─► Found → Return cached (instant)
         │   │
         │   └─► Not found → Compute fresh, save to DB, return
```

## Database Schema (`models.py`)

### Tables

| Table | Primary Key | Key Columns |
|-------|-------------|-------------|
| `stocks` | `ticker` | name, market_cap_msek, avanza_id, market |
| `daily_prices` | `(ticker, date)` | open, high, low, close, volume |
| `fundamentals` | `id` | ticker, pe, pb, roe, dividend_yield, fetched_date |
| `strategy_signals` | `id` | strategy_name, ticker, rank, score, calculated_date |

### Key Points

- `DailyPrice` uses composite primary key - no duplicates possible
- `Stock.market_cap_msek` is in MSEK (millions SEK)
- `Fundamentals.market_cap` is in SEK (raw from API) - **don't use for filtering**
- `StrategySignal` is cleared and recomputed on each sync

## Strategy Calculations (`ranking.py`)

### Sammansatt Momentum
```python
# Lines 53-75 in ranking.py
def calculate_momentum_score(prices_df, price_pivot=None):
    # Average of 3m, 6m, 12m price returns
    for period in [3, 6, 12]:
        days = period * 21  # Trading days
        scores[f'm{period}'] = (latest / past) - 1
    return scores.mean(axis=1)
```

### Momentum with F-Score Filter
```python
# Lines 230-280 in ranking.py
def calculate_momentum_with_quality_filter(prices_df, fund_df):
    # 1. Filter to top 40% by market cap
    # 2. Calculate momentum
    # 3. Remove stocks with F-Score <= 3
    # 4. Return top 10
```

### Trendande Värde
```python
# Lines 285-330 in ranking.py
def calculate_value_score(fund_df, prices_df):
    # 1. Rank by 6 factors: P/E, P/B, P/S, P/FCF, EV/EBITDA, DivYield
    # 2. Average ranks (lower = better value)
    # 3. Take top 10% by value
    # 4. Sort by momentum, return top 10
```

### Trendande Utdelning
```python
# Lines 332-365 in ranking.py
def calculate_dividend_score(fund_df, prices_df):
    # 1. Rank by dividend yield (higher = better)
    # 2. Take top 10%
    # 3. Sort by momentum, return top 10
```

### Trendande Kvalitet
```python
# Lines 367-400 in ranking.py
def calculate_quality_score(fund_df, prices_df):
    # 1. Rank by 4 factors: ROE, ROA, ROIC, FCFROE
    # 2. Average ranks (higher = better quality)
    # 3. Take top 10%
    # 4. Sort by momentum, return top 10
```

### Piotroski F-Score
```python
# Lines 77-140 in ranking.py
def calculate_piotroski_f_score(fund_df):
    # 9-point scale:
    # Profitability (4 pts): ROA>0, CFO>0, ROA improving, CFO>NI
    # Leverage (3 pts): Debt decreasing, Current ratio up, No dilution
    # Efficiency (2 pts): Gross margin up, Asset turnover up
```

## Filters (`ranking.py`)

```python
# Line 14
MIN_MARKET_CAP_MSEK = 2000  # 2B SEK minimum since June 2023

# Lines 31-38
def filter_by_min_market_cap(df, min_cap_msek=2000):
    return df[df['market_cap'] >= min_cap_msek]

# Lines 20-28
def filter_real_stocks(df):
    # Exclude ETFs, certificates - only keep stock_type in ['stock', 'sdb']
```

## Cache Architecture

### Smart Cache (`smart_cache.py`)

SQLite-based cache for API responses during sync.

```python
# Key methods:
smart_cache.set(endpoint, params, data, ttl_hours)
smart_cache.get(endpoint, params)
smart_cache.clear_all()  # Called at start of sync
```

### Ranking Cache (`ranking_cache.py`)

Pre-computed rankings stored in `StrategySignal` table.

```python
# Called after sync:
compute_all_rankings(db)  # Computes all 4 strategies, saves to DB

# Called on API request:
get_cached_rankings(db, strategy_name)  # Returns today's rankings or empty
```

### In-Memory Cache (`cache.py`)

Decorator-based function cache, 24h TTL.

```python
@cached(ttl_minutes=1440)
def expensive_function():
    ...
```

## Scheduled Jobs (`scheduler.py`)

| Job | Schedule | Function |
|-----|----------|----------|
| `daily_sync` | Daily at DATA_SYNC_HOUR (default 6 UTC) | `sync_job()` |
| `biweekly_stock_scan` | Every other Sunday 3AM | `scan_new_stocks_job()` |

```python
# sync_job() calls:
avanza_sync(db)  # Which includes compute_all_rankings()
```

## API Endpoints (`main.py`)

### Strategy Rankings (Lines 269-285)
```
GET /strategies                    → List all 4 strategies
GET /strategies/{name}             → Get ranked stocks (from cache)
GET /strategies/{name}/top10       → Top 10 only
```

### Data Management (Lines 1079-1110)
```
POST /data/sync-now                → Trigger full sync
GET  /data/status/detailed         → Data freshness info
GET  /cache/stats                  → Cache statistics
```

### Backtesting (Lines ~1400)
```
POST /backtest                     → Run historical backtest
GET  /backtest/results             → Get saved results
```

## Key Constants

```python
# ranking.py
MIN_MARKET_CAP_MSEK = 2000      # 2B SEK minimum
VALID_STOCK_TYPES = ['stock', 'sdb']

# strategies.yaml
rebalance_months: [3, 6, 9, 12]  # Quarterly for momentum
position_count: 10               # Top 10 stocks per strategy

# avanza_fetcher_v2.py
max_workers = 10                 # Parallel API threads
days = 400                       # Price history to fetch
```

## Testing

### System Tests
```bash
cd backend && python tests/test_system.py
```
Verifies: imports, database integrity, calculations, cache, API endpoints.

### Validation Tests
```bash
cd backend && python tests/test_validation.py
```
Verifies implementation matches Börslabbet's published rules:

| Rule | Source | Verified |
|------|--------|----------|
| Momentum = avg(3m, 6m, 12m) | börslabbet.se/sammansatt-momentum | ✓ |
| Market cap ≥ 2B SEK | börslabbet.se/borslabbets-strategier | ✓ |
| F-Score 0-9 scale | Academic standard | ✓ |
| Momentum filters F-Score ≤ 3 | börslabbet.se | ✓ |
| Value = 6 factors | börslabbet.se/trendande-varde | ✓ |
| Quality = 4 ROI factors | börslabbet.se | ✓ |
| Trendande: top 10% → momentum → top 10 | börslabbet.se | ✓ |
| Momentum: quarterly rebalance | börslabbet.se | ✓ |
| Trendande: annual rebalance | börslabbet.se | ✓ |
| 10 stocks per strategy | börslabbet.se | ✓ |
| Equal-weighted | börslabbet.se | ✓ |
| Universe: Stockholmsbörsen + First North | börslabbet.se | ✓ |

### Manual Verification
The validation test prints our current top 10 for each strategy. Compare with:
- https://www.borslabbet.se/sammansatt-momentum/
- https://www.borslabbet.se/trendande-varde/

Note: Rankings may differ slightly due to data timing differences.

## Performance

| Operation | Time | Location |
|-----------|------|----------|
| Full sync | ~51s | `avanza_sync()` |
| Strategy API (cached) | <50ms | `_compute_strategy_rankings()` |
| Strategy API (compute) | ~3s | First request of day |
| Backtest (1 year) | ~2s | `backtest_strategy()` |

## Error Handling

- **Missing data**: Returns empty rankings, logs warning
- **API failures**: Logged, continues with available data
- **DB errors**: Transaction rollback via SQLAlchemy
- **Stale cache**: Recomputes on next request (checks `calculated_date`)
