# Börslabbet App - AI Context Document

> **Purpose**: This document provides complete context for AI assistants to understand and work with the Börslabbet codebase. It covers architecture, data flow, key algorithms, and implementation details.

---

## 1. PROJECT OVERVIEW

**What it is**: A quantitative Swedish stock strategy platform implementing Börslabbet's proven investment strategies.

**Tech Stack**:
- Backend: FastAPI + SQLAlchemy + SQLite
- Frontend: React + Chakra UI + Vite + TypeScript
- Data Source: Avanza public API (free Swedish stock data)
- Deployment: Docker Compose

**Core Value Proposition**: Automated strategy rankings, portfolio tracking, and backtesting for Swedish stocks using Börslabbet's published methodologies.

---

## 2. THE 4 BÖRSLABBET STRATEGIES

All strategies share these rules:
- **Universe**: Stockholmsbörsen + First North, minimum 2B SEK market cap (since June 2023)
- **Portfolio**: 10 stocks, equal-weighted (10% each)
- **Excludes**: Financial companies (banks, insurance, investment companies)

### 2.1 Sammansatt Momentum
```
Category: momentum
Rebalance: Quarterly (March, June, September, December)

Algorithm:
1. Calculate momentum score = average(3m_return, 6m_return, 12m_return)
2. Filter by Piotroski F-Score > 3 (quality gate)
3. Select top 10 by momentum score
```

### 2.2 Trendande Värde
```
Category: value
Rebalance: Annual (March)

Algorithm:
1. Calculate value score from 6 metrics (lower = better):
   - P/E, P/B, P/S, P/FCF, EV/EBITDA (ascending rank)
   - Dividend Yield (descending rank)
2. Keep top 40% by value score
3. From those, rank by Sammansatt Momentum
4. Select top 10 by momentum
```

### 2.3 Trendande Utdelning
```
Category: dividend
Rebalance: Annual (March)

Algorithm:
1. Rank by dividend yield (higher = better)
2. Keep top 40% by dividend yield
3. From those, rank by Sammansatt Momentum
4. Select top 10 by momentum
```

### 2.4 Trendande Kvalitet
```
Category: quality
Rebalance: Annual (March)

Algorithm:
1. Calculate quality score from 4 metrics (higher = better):
   - ROE, ROA, ROIC, FCFROE
2. Keep top 40% by quality score
3. From those, rank by Sammansatt Momentum
4. Select top 10 by momentum
```

---

## 3. BACKEND ARCHITECTURE

### 3.1 File Structure
```
backend/
├── main.py              # FastAPI app, 100+ endpoints under /v1
├── models.py            # SQLAlchemy models (20+ tables)
├── db.py                # Database connection
├── schemas.py           # Pydantic schemas
├── config/
│   ├── strategies.yaml  # Strategy definitions
│   └── settings.py      # Environment config
├── services/
│   ├── ranking.py       # Strategy scoring algorithms
│   ├── avanza_fetcher_v2.py  # Avanza API client
│   ├── backtesting.py   # Historical backtests
│   ├── smart_cache.py   # SQLite-based caching
│   ├── ranking_cache.py # Pre-computed rankings
│   └── ...              # 20+ service modules
├── jobs/
│   └── scheduler.py     # APScheduler for daily sync
└── tests/               # Pytest test suite
```

### 3.2 Key Database Models

```python
# Core data models
Stock(ticker, name, isin, avanza_id, market_cap_msek, sector, market, stock_type)
DailyPrice(ticker, date, open, close, high, low, volume)
Fundamentals(ticker, fiscal_date, pe, pb, ps, p_fcf, ev_ebitda, roe, roa, roic, fcfroe, dividend_yield, ...)

# Strategy outputs
StrategySignal(strategy_name, ticker, rank, score, calculated_date)

# User data
User(email, password_hash, name, market_filter)
UserSession(user_id, token, expires_at)
UserPortfolio(user_id, name, description)
PortfolioTransaction(user_id, portfolio_id, ticker, transaction_type, shares, price, fees)

# Tracking
RebalanceHistory(strategy, rebalance_date, trades_json, total_cost, portfolio_value)
RankingsSnapshot(strategy, snapshot_date, rankings_json)
```

### 3.3 Key API Endpoints

```
# Strategies
GET  /v1/strategies                    # List all 4 strategies
GET  /v1/strategies/{name}             # Get ranked stocks for strategy
GET  /v1/strategies/{name}/top10       # Top 10 only
GET  /v1/strategies/compare            # Side-by-side comparison

# Portfolio
GET  /v1/portfolio/sverige             # Combined portfolio
GET  /v1/portfolio/rebalance-dates     # Next rebalance dates
POST /v1/portfolio/combiner            # Custom strategy mix

# Data Sync
POST /v1/data/sync-now                 # Trigger full sync (~51 seconds)
GET  /v1/data/sync-status              # Current data status
GET  /v1/data/status/detailed          # Per-stock freshness

# Backtesting
POST /v1/backtesting/run               # Run backtest
POST /v1/backtesting/historical        # Long-term backtest with FinBas data

# Rebalancing
POST /v1/rebalance/trades              # Generate buy/sell trades
POST /v1/portfolio/divergence          # Check portfolio drift

# User
POST /v1/auth/register                 # Create account
POST /v1/auth/login                    # Get session token
GET  /v1/auth/me                       # Current user info
```

### 3.4 Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                        DATA PIPELINE                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Avanza API ──► avanza_sync() ──► Database ──► Rankings Cache   │
│       │              │               │              │           │
│       │              │               │              │           │
│  Stock Overview   Fundamentals    DailyPrice    StrategySignal  │
│  Historical       + Prices        (2.3M rows)   (pre-computed)  │
│  Prices                                                         │
│                                                                 │
│  ──────────────────────────────────────────────────────────────│
│                                                                 │
│  User Request ──► API Endpoint ──► Check Cache ──► Return JSON  │
│                                        │                        │
│                                   (if stale)                    │
│                                        │                        │
│                                   Compute Fresh                 │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 4. FRONTEND ARCHITECTURE

### 4.1 File Structure
```
frontend/src/
├── App.tsx              # Routes (20+ pages, lazy loaded)
├── main.tsx             # Entry point
├── api/
│   └── client.ts        # API client with typed methods
├── pages/
│   ├── Dashboard.tsx    # Portfolio overview + charts
│   ├── StrategyPage.tsx # Strategy details + rankings
│   ├── RebalancingPage.tsx
│   ├── BacktestingPage.tsx
│   └── ...              # 15+ page components
├── components/
│   ├── Navigation.tsx   # Sidebar navigation
│   ├── Pagination.tsx
│   └── ...              # Reusable components
├── theme/
│   ├── index.ts         # Chakra UI theme
│   └── tokens.ts        # Design tokens
└── types/
    └── index.ts         # TypeScript interfaces
```

### 4.2 Key Routes
```typescript
/                        → Dashboard (portfolio overview)
/strategies/:type        → StrategyPage (momentum|value|dividend|quality)
/portfolio/my            → MyPortfolioPage (user holdings)
/portfolio/combiner      → CombinerPage (custom strategy mix)
/rebalancing             → RebalancingPage (trade generator)
/backtesting             → BacktestingPage (run backtests)
/backtesting/historical  → HistoricalBacktestPage (long-term)
/analytics               → AnalyticsDashboard
/data                    → DataManagementPage (sync controls)
/settings                → SettingsPage
/stock/:ticker           → StockDetailPage
```

### 4.3 API Client Pattern
```typescript
// frontend/src/api/client.ts
export const api = {
  getStrategies: () => fetchJson<StrategyMeta[]>('/strategies'),
  getStrategyRankings: (name: string) => fetchJson<RankedStock[]>(`/strategies/${name}`),
  runBacktest: (req: BacktestRequest) => postJson<BacktestResult>('/backtesting/run', req),
  // ... typed methods for all endpoints
};
```

---

## 5. KEY ALGORITHMS

### 5.1 Momentum Score Calculation
```python
# services/ranking.py
def calculate_momentum_score(prices_df, price_pivot=None):
    """Sammansatt Momentum: average of 3m, 6m, 12m returns."""
    latest = price_pivot.iloc[-1]
    scores = pd.DataFrame(index=latest.index)
    
    for period in [3, 6, 12]:
        days = period * 21  # Trading days
        past = price_pivot.iloc[-days]
        scores[f'm{period}'] = (latest / past) - 1
    
    return scores.mean(axis=1)  # Average of 3 periods
```

### 5.2 Piotroski F-Score (Quality Filter)
```python
# 9-point scale quality score
# Profitability (4 points): ROA > 0, Operating CF > 0, ROA improving, CF > Net Income
# Leverage (3 points): Debt ratio decreasing, Current ratio improving, No dilution
# Efficiency (2 points): Gross margin improving, Asset turnover improving

# Used in Sammansatt Momentum to filter out low-quality stocks (F-Score <= 3)
```

### 5.3 Market Cap Filter
```python
# services/ranking.py
MIN_MARKET_CAP_MSEK = 2000  # 2B SEK since June 2023

def filter_by_min_market_cap(df, min_cap_msek=MIN_MARKET_CAP_MSEK):
    return df[df['market_cap'] >= min_cap_msek]

def filter_by_market_cap(fund_df, percentile=40):
    """Keep top 40% by market cap (Börslabbet rule)."""
    threshold = fund_df['market_cap'].quantile(1 - percentile / 100)
    return fund_df[fund_df['market_cap'] >= threshold]
```

### 5.4 Backtesting Engine
```python
# services/backtesting.py
def backtest_strategy(strategy_name, start_date, end_date, db, config):
    """
    1. Load historical prices (FinBas for pre-2023, Avanza for recent)
    2. Get rebalance dates based on strategy config
    3. At each rebalance:
       - Calculate rankings using data available at that date
       - Apply transaction costs (0.1% + 0.05% slippage)
       - Update holdings
    4. Track equity curve daily
    5. Calculate metrics: total return, Sharpe ratio, max drawdown
    """
```

---

## 6. DATA SOURCES

### 6.1 Avanza API (Primary)
```python
# services/avanza_fetcher_v2.py
class AvanzaDirectFetcher:
    """Free Swedish stock data from Avanza's public API."""
    
    def get_stock_overview(self, stock_id):
        """Fundamentals: P/E, P/B, ROE, dividend yield, etc."""
        url = f"https://www.avanza.se/_api/market-guide/stock/{stock_id}"
        
    def get_historical_prices(self, stock_id, days=400):
        """OHLCV data for momentum calculations."""
        url = f"https://www.avanza.se/_api/price-chart/stock/{stock_id}"
```

### 6.2 FinBas Historical Data
```
# For backtesting pre-2023 (includes delisted stocks)
# Source: Swedish House of Finance (data.houseoffinance.se/finbas/)
# Coverage: 1998-2023, 1,830 stocks
# Tables: finbas_historical, ticker_all_isins
```

### 6.3 Stock ID Mapping
```python
# Known Avanza stock IDs (147 Stockholmsbörsen stocks)
stockholmsborsen_stocks = {
    "VOLV-B": "5269",
    "ERIC-B": "5240",
    "H&M-B": "5364",
    "INVE-B": "5247",
    # ... etc
}
```

---

## 7. CACHING STRATEGY

### 7.1 Smart Cache (SQLite-based)
```python
# services/smart_cache.py
class SmartCache:
    TTL_PRICES = 6          # hours - current prices
    TTL_FUNDAMENTALS = 168  # hours (7 days) - P/E, ROE etc.
    TTL_RANKINGS = 24       # hours - strategy rankings
    TTL_BACKTEST = 720      # hours (30 days) - historical backtests
```

### 7.2 Rankings Cache
```python
# Pre-computed daily rankings stored in StrategySignal table
# Computed during sync, served instantly on API requests
```

---

## 8. SCHEDULED JOBS

```python
# jobs/scheduler.py
# Daily sync at configured hour (default 6:00 UTC)
scheduler.add_job(sync_job, CronTrigger(hour=6, minute=0), id="daily_sync")

# Bi-weekly stock scan for new listings (every other Sunday 3 AM)
scheduler.add_job(scan_new_stocks_job, CronTrigger(day_of_week="sun", hour=3, week="*/2"))
```

---

## 9. AUTHENTICATION

```python
# Simple session-based auth
# POST /v1/auth/register → Create user with hashed password
# POST /v1/auth/login → Get session token (stored in user_sessions table)
# Authorization header: Bearer <token>
```

---

## 10. COMMON TASKS

### 10.1 Add a New Strategy
1. Add config to `backend/config/strategies.yaml`
2. Add scoring function to `backend/services/ranking.py`
3. Update `_compute_strategy_rankings()` in `main.py`
4. Add frontend route and page

### 10.2 Add a New API Endpoint
1. Add route to `main.py` under `v1_router`
2. Add Pydantic schema if needed in `schemas.py`
3. Add typed method to `frontend/src/api/client.ts`

### 10.3 Modify Ranking Algorithm
1. Edit `backend/services/ranking.py`
2. Update `backend/config/strategies.yaml` if config changes
3. Run sync to regenerate rankings

### 10.4 Add New Data Field
1. Add column to model in `models.py`
2. Update `avanza_fetcher_v2.py` to fetch the field
3. Update `avanza_sync()` to store it
4. Add to API response schemas

---

## 11. ENVIRONMENT VARIABLES

```bash
DATABASE_URL=sqlite:///./app.db  # Database connection
DATA_SYNC_ENABLED=true           # Enable scheduled sync
DATA_SYNC_HOUR=6                 # Hour (UTC) for daily sync
```

---

## 12. TESTING

```bash
cd backend
pytest                           # Run all tests
pytest tests/unit/               # Unit tests only
pytest tests/integration/        # Integration tests
pytest -v --tb=short             # Verbose with short traceback
```

---

## 13. DEPLOYMENT

```bash
# Docker (recommended)
docker compose up -d

# Manual
cd backend && uvicorn main:app --reload
cd frontend && npm run dev

# Access
Frontend: http://localhost:5173
Backend: http://localhost:8000
API Docs: http://localhost:8000/docs
```

---

## 14. DATABASE SCHEMA SUMMARY

```
stocks              # 734 Swedish stocks
daily_prices        # ~2.3M price records (1982-present)
fundamentals        # Current snapshot of P/E, ROE, etc.
strategy_signals    # Pre-computed rankings (refreshed daily)
finbas_historical   # Historical fundamentals (1998-2023)
ticker_all_isins    # ISIN mapping for historical data
users               # User accounts
user_sessions       # Auth tokens
user_portfolios_v2  # User portfolio tracking
portfolio_transactions_v2  # Buy/sell records
saved_combinations  # Custom strategy mixes
backtest_results    # Saved backtest outputs
rebalance_history   # Rebalance event log
```

---

## 15. PERFORMANCE CHARACTERISTICS

| Operation | Time |
|-----------|------|
| Full sync (fundamentals + prices + rankings) | ~51 seconds |
| Strategy API (cached) | <50ms |
| Strategy API (compute fresh) | ~2-5 seconds |
| Backtest (1 year) | ~2 seconds |
| Backtest (10 years) | ~30 seconds |

---

## 16. KNOWN LIMITATIONS

1. **Look-ahead bias in backtests**: Value/dividend/quality strategies use current fundamentals for historical periods (only momentum uses pure historical data)
2. **Avanza API rate limits**: Respectful delays built in, but heavy usage may hit limits
3. **FinBas data ends 2023**: Historical backtests beyond 2023 use Avanza data only
4. **No real-time prices**: Data refreshed daily, not intraday

---

## 17. QUICK REFERENCE

### Strategy Names (API)
- `sammansatt_momentum`
- `trendande_varde`
- `trendande_utdelning`
- `trendande_kvalitet`

### Key Files to Edit
- Strategy logic: `backend/services/ranking.py`
- API endpoints: `backend/main.py`
- Strategy config: `backend/config/strategies.yaml`
- Frontend routes: `frontend/src/App.tsx`
- API client: `frontend/src/api/client.ts`

### Database Location
- Main: `backend/app.db`
- Cache: `backend/smart_cache.db`
- FinBas backup: `backend/data/backups/finbas_backup_*.db`
