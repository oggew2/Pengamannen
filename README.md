# Börslabbet App

A quantitative Swedish stock strategy platform implementing Börslabbet's proven investment strategies.

## Features

- **4 Börslabbet Strategies**:
  - Sammansatt Momentum (Quarterly rebalancing)
  - Trendande Värde (Annual, January)
  - Trendande Utdelning (Annual, February)
  - Trendande Kvalitet (Annual, March)

- **Portfolio Management**: Combine strategies, track holdings, view rebalance calendar
- **Backtesting**: Historical performance simulation with Sharpe ratio, max drawdown
- **Data Sync**: Automatic daily updates from EODHD API

## Quick Start

### Prerequisites
- Python 3.9+
- Node.js 18+
- EODHD API key (free tier: https://eodhd.com)

### Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env and add your EODHD_API_KEY

# Start server
python -m uvicorn backend.main:app --reload
```

Backend runs at http://localhost:8000 (Swagger docs at /docs)

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Start dev server
npm run dev
```

Frontend runs at http://localhost:5173

## Project Structure

```
borslabbet-app/
├── backend/
│   ├── main.py              # FastAPI application
│   ├── models.py            # SQLAlchemy models
│   ├── schemas.py           # Pydantic schemas
│   ├── db.py                # Database setup
│   ├── config/
│   │   ├── settings.py      # Environment config
│   │   └── strategies.yaml  # Strategy definitions
│   ├── services/
│   │   ├── ranking.py       # Strategy scoring
│   │   ├── portfolio.py     # Portfolio management
│   │   ├── backtesting.py   # Historical simulation
│   │   └── eodhd_fetcher.py # Data fetching
│   └── jobs/
│       └── scheduler.py     # Automatic sync
├── frontend/
│   ├── src/
│   │   ├── pages/           # React pages
│   │   ├── components/      # Reusable components
│   │   ├── api/             # API client
│   │   └── types/           # TypeScript types
│   └── vite.config.ts
└── README.md
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/strategies` | GET | List all strategies |
| `/strategies/{name}` | GET | Get ranked stocks |
| `/portfolio/sverige` | GET | Combined portfolio |
| `/portfolio/rebalance-dates` | GET | Rebalance calendar |
| `/portfolio/combiner` | POST | Custom combination |
| `/backtesting/run` | POST | Run backtest |
| `/data/sync-now` | POST | Trigger data sync |

## Strategy Details

### Sammansatt Momentum
- **Rebalance**: Quarterly (March, June, September, December)
- **Scoring**: Composite momentum (3m + 6m + 12m returns)
- **Filter**: Piotroski F-Score ≥ 4

### Trendande Värde
- **Rebalance**: Annual (January)
- **Scoring**: Lowest P/E, P/B, P/S, EV/EBITDA
- **Filter**: None

### Trendande Utdelning
- **Rebalance**: Annual (February)
- **Scoring**: Highest dividend yield
- **Filters**: Payout ratio < 100%, ROE > 5%, Yield > 1.5%

### Trendande Kvalitet
- **Rebalance**: Annual (March)
- **Scoring**: ROIC (50%) + Momentum (50%)
- **Filter**: ROIC > 10% OR ROE > 15%

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `EODHD_API_KEY` | - | EODHD API key (required for data) |
| `DATABASE_URL` | `sqlite:///./app.db` | Database connection |
| `DATA_SYNC_ENABLED` | `true` | Enable automatic sync |
| `DATA_SYNC_HOUR` | `18` | Hour for daily sync (UTC) |

## Development

```bash
# Run tests
cd backend && pytest

# Type check frontend
cd frontend && npx tsc --noEmit

# Build frontend
cd frontend && npm run build
```

## License

MIT

## Disclaimer

This is for educational purposes only. Past performance does not guarantee future results. Always do your own research before investing.
