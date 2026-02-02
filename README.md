# Börslabbet App

A quantitative Nordic stock strategy platform implementing Börslabbet's proven momentum strategy.

## Active Strategy

**Nordic Momentum (Sammansatt Momentum)** - The only active strategy
- Quarterly rebalancing (March, June, September, December)
- Top 10 stocks from Nordic markets (Sweden, Finland, Norway, Denmark)
- Buy: Top 10 ranked stocks
- Keep: Top 20 ranked stocks
- Sell: Below rank 20

> **Note:** Other strategies (Trendande Värde, Utdelning, Kvalitet) are deprecated and not maintained.

## Data Pipeline
- **TradingView Scanner API** - Primary data source for fundamentals + momentum (<2s sync)
- **Avanza API** - Fallback for fundamentals, historical prices for backtesting
- **Daily sync** - Automated data refresh
- **Pre-computed rankings** - Instant API responses from DB cache
- **Historical backtesting** - Test strategies on 10+ years of data

### Portfolio Management
- Track holdings with P&L calculation
- Import from Avanza CSV exports
- Rebalance trade generator with cost estimates
- Strategy comparison (side-by-side top 10)

## Quick Start

### Docker (Recommended)
```bash
docker compose up -d
```
- Frontend: http://localhost:5173
- Backend: http://localhost:8000
- API Docs: http://localhost:8000/docs

### Manual Setup
```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload

# Frontend
cd frontend
npm install && npm run dev
```

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed technical documentation.

### Data Flow
```
TradingView API → tradingview_sync() → Database → Pre-compute rankings → API cache
                                                                    ↓
                                              User request → Instant response
```

### Key Components
| Component | Purpose |
|-----------|---------|
| `tradingview_fetcher.py` | Fetch data from TradingView Scanner API |
| `avanza_fetcher_v2.py` | Fetch historical prices from Avanza API |
| `ranking.py` | Strategy scoring calculations |
| `ranking_cache.py` | Pre-compute and cache rankings |
| `smart_cache.py` | SQLite-based API response cache |
| `scheduler.py` | Daily automated sync jobs |

## API Endpoints

### Strategy Rankings
| Endpoint | Description |
|----------|-------------|
| `GET /strategies` | List all strategies |
| `GET /strategies/{name}` | Get ranked stocks (cached) |
| `GET /strategies/{name}/top10` | Top 10 only |

### Data Management
| Endpoint | Description |
|----------|-------------|
| `POST /data/sync-now` | Trigger full sync (~51s) |
| `GET /data/status/detailed` | Data freshness info |
| `GET /cache/stats` | Cache statistics |

### Backtesting
| Endpoint | Description |
|----------|-------------|
| `POST /backtest` | Run historical backtest |
| `GET /backtest/results` | Get saved results |

## Strategy Rules

All strategies apply:
- **2B SEK minimum market cap** (since June 2023)
- **Equal-weight portfolios** (10% per stock)
- **Stockholmsbörsen + First North** universe
- **Top 10 stocks** selected per strategy

### Momentum Calculation
```
Sammansatt Momentum = average(3m_return, 6m_return, 12m_return)
```

### Rebalancing Schedule
- **Sammansatt Momentum**: Quarterly (March, June, September, December)
- **Trendande strategies**: Annual

## Database

SQLite database (`app.db`) with tables:
- `stocks` - Stock metadata (734 Swedish stocks)
- `daily_prices` - Historical OHLCV (~2.3M rows, 1982-present)
- `fundamentals` - P/E, P/B, ROE, etc. (current snapshot)
- `strategy_signals` - Pre-computed rankings (refreshed daily)
- `finbas_historical` - Historical fundamentals from FinBas (1998-2023)
- `ticker_all_isins` - ISIN mapping for historical data

### FinBas Historical Data
Historical Swedish stock data from [Swedish House of Finance](https://data.houseoffinance.se/finbas/) for backtesting:
- **Coverage:** 1998-2023, 1,830 stocks (SSE + First North)
- **Data:** Prices, market cap, book value
- **Backup:** `backend/data/backups/finbas_backup_*.db`
- **Docs:** See `backend/data/FINBAS_DATA.md`

## Performance

| Operation | Time |
|-----------|------|
| Full sync (TradingView) | ~2 seconds |
| Full sync (Avanza fallback) | ~51 seconds |
| Strategy API (cached) | <50ms |
| Backtest (1 year) | ~2 seconds |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite:///./app.db` | Database connection |
| `DATA_SOURCE` | `tradingview` | Data source: `tradingview` or `avanza` |
| `DATA_SYNC_ENABLED` | `true` | Enable scheduled sync |
| `DATA_SYNC_HOUR` | `6` | Hour (UTC) for daily sync |

## Development

```bash
# Verify backend
cd backend && python -c "from main import app; print('OK')"

# Run sync manually
curl -X POST http://localhost:8000/data/sync-now

# Check rankings
curl http://localhost:8000/strategies/sammansatt_momentum
```

## Project Structure

```
borslabbet-app/
├── ARCHITECTURE.md          # Technical documentation
├── backend/
│   ├── main.py              # FastAPI app
│   ├── models.py            # SQLAlchemy models
│   ├── config/
│   │   └── strategies.yaml  # Strategy definitions
│   ├── services/
│   │   ├── avanza_fetcher_v2.py
│   │   ├── ranking.py
│   │   ├── ranking_cache.py
│   │   ├── backtesting.py
│   │   └── smart_cache.py
│   └── jobs/
│       └── scheduler.py
├── frontend/
│   └── src/
│       ├── pages/
│       └── components/
└── docker-compose.yml
```

## Disclaimer

For educational purposes only. Past performance does not guarantee future results. Not investment advice.
