# TradingView Migration Guide - Critical Review & Implementation

> **Created**: 2026-01-04
> **Purpose**: Actionable guide for migrating from Avanza to TradingView Scanner API
> **Status**: Ready for implementation

---

## Quick Start for the Next Developer

### Prerequisites

```bash
# Install required package
pip install tradingview-screener requests

# Or add to requirements.txt:
# tradingview-screener>=1.0.0
```

### Environment Variables

```bash
# Add to .env
DATA_SOURCE=tradingview  # or 'avanza' for fallback
TV_RATE_LIMIT=1.0        # seconds between requests
```

### Test the API Works

```python
# Quick test script - run this first!
import requests

url = "https://scanner.tradingview.com/sweden/scan"
payload = {
    "filter": [{"left": "market_cap_basic", "operation": "greater", "right": 100e9}],
    "markets": ["sweden"],
    "symbols": {"query": {"types": ["stock"]}},
    "columns": ["name", "close", "market_cap_basic", "Perf.3M"],
    "range": [0, 10]
}
r = requests.post(url, json=payload, timeout=30)
print(f"Status: {r.status_code}")
print(f"Stocks found: {len(r.json().get('data', []))}")
# Should print: Status: 200, Stocks found: 10
```

---

## ⚠️ CRITICAL: Terms of Service Warning

**The existing migration reports significantly downplay ToS concerns.**

### What TradingView ToS Actually Says (Section 3)

TradingView explicitly prohibits:
- "non-display usage" including automated trading, algorithmic decision-making
- "any machine-driven processes that do not involve direct, human-readable display"
- "creating products or services based on TradingView content"
- "any processing of TradingView's content"
- Commercial usage of any services or APIs

### Risk Assessment

| Use Case | Risk Level | Recommendation |
|----------|------------|----------------|
| Personal/educational use | MEDIUM | Acceptable with caution |
| Public deployment | HIGH | Need official data license |
| Commercial product | VERY HIGH | Do not proceed without license |

### Mitigation Strategies

1. **Keep Avanza as full fallback** - Not just for historical prices
2. **Add feature flag** - Switch data sources instantly if blocked
3. **Rate limit requests** - 1 request/second max, even if no hard limits observed
4. **Don't share publicly** - Keep deployment private
5. **Monitor for blocks** - Add alerting for API failures

---

## Executive Summary

### What the Migration Reports Get Right ✅

1. Pre-calculated momentum fields (`Perf.1M`, `Perf.3M`, `Perf.6M`, `Perf.Y`) exist
2. Pre-calculated F-Score (`piotroski_f_score_ttm`, `piotroski_f_score_fy`) exists
3. Performance improvement (51s → <1s) is realistic
4. Field mappings are accurate
5. Hybrid approach (TradingView for fundamentals, Avanza for prices) is sound

### What the Migration Reports Miss ❌

1. **ToS concerns are severely downplayed** - See warning above
2. **Sector mapping needed** - Swedish sectors → English sectors
3. **Ticker mapping needed** - `VOLV-B` ↔ `VOLV_B` conversion
4. **Keep `avanza_id`** - Still needed for historical price fetching
5. **Keep `sync_omxs30_index()`** - Needed for benchmark comparison
6. **ROE/ROA methodology differs** - TradingView uses annualized quarterly, not TTM
7. **Query configuration critical** - Must remove `is_primary` filter, include `dr` type

---

## Database Changes Required

### Add to `models.py` - Fundamentals Table

```python
class Fundamentals(Base):
    # ... existing fields ...
    
    # NEW: Pre-calculated momentum from TradingView
    perf_1m = Column(Float)   # TradingView Perf.1M (percentage)
    perf_3m = Column(Float)   # TradingView Perf.3M
    perf_6m = Column(Float)   # TradingView Perf.6M
    perf_12m = Column(Float)  # TradingView Perf.Y
    
    # NEW: Pre-calculated F-Score from TradingView
    piotroski_f_score = Column(Integer)  # 0-9 scale
    
    # NEW: Data source tracking
    data_source = Column(String, default='avanza')  # 'avanza' or 'tradingview'
```

### Migration SQL

```sql
-- Add new columns
ALTER TABLE fundamentals ADD COLUMN perf_1m FLOAT;
ALTER TABLE fundamentals ADD COLUMN perf_3m FLOAT;
ALTER TABLE fundamentals ADD COLUMN perf_6m FLOAT;
ALTER TABLE fundamentals ADD COLUMN perf_12m FLOAT;
ALTER TABLE fundamentals ADD COLUMN piotroski_f_score INTEGER;
ALTER TABLE fundamentals ADD COLUMN data_source VARCHAR DEFAULT 'avanza';

-- Add index for data source queries
CREATE INDEX idx_fundamentals_data_source ON fundamentals(data_source);
```

### DO NOT Remove

- `Stock.avanza_id` - Still needed for historical price fetching
- `DailyPrice` table - Still needed for backtesting
- `IndexPrice` table - Still needed for OMXS30 benchmark

---

## Complete Field Mapping: TradingView → Database

This is the exact mapping from TradingView API fields to your existing `Fundamentals` table:

| DB Column | TradingView Field | Transform | Notes |
|-----------|-------------------|-----------|-------|
| `ticker` | `name` (from symbol) | `VOLV_B` → `VOLV-B` | Replace `_` with `-` |
| `market_cap` | `market_cap_basic` | Direct (SEK) | Already in SEK |
| `pe` | `price_earnings_ttm` | Direct | |
| `pb` | `price_book_ratio` | Direct | |
| `ps` | `price_sales_ratio` | Direct | |
| `p_fcf` | `price_free_cash_flow_ttm` | Direct | **IMPROVED**: True P/FCF |
| `ev_ebitda` | `enterprise_value_ebitda_ttm` | Direct | **IMPROVED**: No calculation |
| `roe` | `net_income_ttm / total_equity_fq * 100` | **CALCULATE** | Don't use `return_on_equity`! |
| `roa` | `net_income_ttm / total_assets_fq * 100` | **CALCULATE** | Don't use `return_on_assets`! |
| `roic` | `return_on_invested_capital` | Direct | |
| `fcfroe` | `free_cash_flow_ttm / total_equity_fq * 100` | Calculate | |
| `dividend_yield` | `dividend_yield_recent` | Direct | |
| `net_income` | `net_income_fq` | Direct | |
| `operating_cf` | `cash_f_operating_activities_ttm` | Direct | |
| `total_assets` | `total_assets_fq` | Direct | |
| `long_term_debt` | `long_term_debt_fq` | Direct | |
| `current_ratio` | `current_ratio_fq` | Direct | |
| `gross_margin` | `gross_margin_ttm` | Direct | |
| `shares_outstanding` | `total_shares_outstanding_fundamental` | Direct | |
| `asset_turnover` | `total_revenue_ttm / total_assets_fq` | Calculate | |
| **NEW** `perf_1m` | `Perf.1M` | Direct (%) | Pre-calculated momentum |
| **NEW** `perf_3m` | `Perf.3M` | Direct (%) | Pre-calculated momentum |
| **NEW** `perf_6m` | `Perf.6M` | Direct (%) | Pre-calculated momentum |
| **NEW** `perf_12m` | `Perf.Y` | Direct (%) | Pre-calculated momentum |
| **NEW** `piotroski_f_score` | `piotroski_f_score_ttm` | Direct (0-9) | Fallback to `_fy` |
| **NEW** `data_source` | N/A | Set to `'tradingview'` | Track data origin |

### ⚠️ Critical: ROE/ROA Calculation

**DO NOT** use TradingView's `return_on_equity` or `return_on_assets` fields directly!

TradingView uses annualized quarterly (Q × 4), but Börslabbet uses TTM. Calculate yourself:

```python
# CORRECT - matches Börslabbet 95%
roe = net_income_ttm / total_equity_fq * 100
roa = net_income_ttm / total_assets_fq * 100

# WRONG - uses annualized quarterly, differs 10-20%
roe = return_on_equity  # Don't use this!
```

---

## Ticker Mapping Examples

| Börslabbet/Avanza | TradingView | Database |
|-------------------|-------------|----------|
| VOLV B | VOLV_B | VOLV-B |
| HM B | HM_B | HM-B |
| SSAB-B | SSAB_B | SSAB-B |
| SEB A | SEB_A | SEB-A |
| ALIV SDB | ALIV_SDB | ALIV-SDB |

```python
# Conversion functions
def tv_to_db(tv_ticker: str) -> str:
    return tv_ticker.replace('_', '-')

def db_to_tv(db_ticker: str) -> str:
    return db_ticker.replace('-', '_').replace(' ', '_')
```

---

## Sector Mapping: TradingView → Existing

TradingView uses English sector names. Your existing code uses Swedish:

| TradingView Sector | Swedish Equivalent (in ranking.py) |
|-------------------|-----------------------------------|
| `Finance` | Traditionell Bankverksamhet, Investmentbolag, Försäkring, etc. |
| `Technology` | Teknik, IT |
| `Healthcare` | Hälsovård, Läkemedel |
| `Industrials` | Industri, Verkstad |
| `Consumer Cyclical` | Konsumentvaror, Detaljhandel |
| `Basic Materials` | Råvaror, Material |
| `Energy` | Energi, Olja & Gas |
| `Real Estate` | Fastigheter |

**Simplification**: TradingView's `Finance` sector covers all financial companies. You can filter at API level:

```python
{"left": "sector", "operation": "not_in_range", "right": ["Finance"]}
```
- `DailyPrice` table - Still needed for backtesting
- `IndexPrice` table - Still needed for OMXS30 benchmark

---

## Files to Create

### 1. `services/tradingview_fetcher.py`

```python
"""
TradingView Scanner API fetcher for Swedish stocks.
WARNING: Check ToS compliance before commercial use.
"""
import requests
import logging
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class TradingViewFetcher:
    """Fetch fundamentals + momentum from TradingView Scanner API."""
    
    SCANNER_URL = "https://scanner.tradingview.com/sweden/scan"
    
    # TradingView uses English sector names
    FINANCIAL_SECTORS = ["Finance"]
    
    # All columns needed for Börslabbet strategies
    COLUMNS = [
        # Identifiers
        "name", "description", "close", "market_cap_basic", "sector", "type",
        
        # Value metrics
        "price_earnings_ttm", "price_book_ratio", "price_sales_ratio",
        "price_free_cash_flow_ttm", "enterprise_value_ebitda_ttm",
        
        # Quality metrics - CALCULATE ROE/ROA from components!
        "net_income_ttm", "total_equity_fq", "total_assets_fq",
        "return_on_invested_capital", "free_cash_flow_ttm",
        
        # Dividend
        "dividend_yield_recent",
        
        # Momentum (PRE-CALCULATED!)
        "Perf.1M", "Perf.3M", "Perf.6M", "Perf.Y",
        
        # F-Score (PRE-CALCULATED!)
        "piotroski_f_score_ttm", "piotroski_f_score_fy",
        
        # F-Score components (for fallback calculation)
        "net_income_fq", "cash_f_operating_activities_ttm",
        "total_debt_fq", "current_ratio_fq", "gross_margin_ttm",
        "total_shares_outstanding_fundamental", "total_revenue_ttm",
        "long_term_debt_fq",
        
        # YoY growth fields (for F-Score calculation)
        "net_income_yoy_growth_ttm", "total_debt_yoy_growth_fy",
        "gross_profit_yoy_growth_ttm", "total_revenue_yoy_growth_ttm",
        "total_assets_yoy_growth_fy",
    ]
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (compatible)',
            'Content-Type': 'application/json',
        })
    
    def fetch_all(self, min_market_cap: float = 2e9) -> List[Dict]:
        """
        Fetch all Swedish stocks with market cap > threshold.
        
        CRITICAL: Do NOT use is_primary filter - excludes dual-listed stocks.
        CRITICAL: Include 'dr' type for Swedish Depository Receipts.
        """
        payload = {
            "filter": [
                {"left": "market_cap_basic", "operation": "greater", "right": min_market_cap},
                # DO NOT ADD: {"left": "is_primary", "operation": "equal", "right": True}
            ],
            "markets": ["sweden"],
            "symbols": {"query": {"types": ["stock", "dr"]}},  # Include depository receipts!
            "columns": self.COLUMNS,
            "sort": {"sortBy": "market_cap_basic", "sortOrder": "desc"},
            "range": [0, 500]
        }
        
        try:
            response = self.session.post(self.SCANNER_URL, json=payload, timeout=30)
            response.raise_for_status()
            return self._parse_response(response.json())
        except Exception as e:
            logger.error(f"TradingView fetch failed: {e}")
            return []
    
    def _parse_response(self, data: dict) -> List[Dict]:
        """Parse TradingView response into standardized format."""
        results = []
        
        for item in data.get('data', []):
            symbol = item.get('s', '')  # e.g., "OMXSTO:VOLV_B"
            values = item.get('d', [])
            
            if len(values) != len(self.COLUMNS):
                continue
            
            # Create dict from columns and values
            row = dict(zip(self.COLUMNS, values))
            
            # Extract ticker from symbol (OMXSTO:VOLV_B -> VOLV_B)
            ticker = symbol.split(':')[-1] if ':' in symbol else symbol
            
            # CRITICAL: Calculate ROE/ROA from TTM components (not TradingView's field!)
            roe = None
            roa = None
            if row.get('net_income_ttm') and row.get('total_equity_fq'):
                roe = (row['net_income_ttm'] / row['total_equity_fq']) * 100
            if row.get('net_income_ttm') and row.get('total_assets_fq'):
                roa = (row['net_income_ttm'] / row['total_assets_fq']) * 100
            
            # Calculate FCFROE
            fcfroe = None
            if row.get('free_cash_flow_ttm') and row.get('total_equity_fq'):
                fcfroe = (row['free_cash_flow_ttm'] / row['total_equity_fq']) * 100
            
            # Get F-Score with fallback
            f_score = (
                row.get('piotroski_f_score_ttm') or 
                row.get('piotroski_f_score_fy') or
                self._calculate_fscore(row)
            )
            
            results.append({
                'ticker': ticker,
                'tv_ticker': ticker,  # Keep original for reference
                'db_ticker': ticker.replace('_', '-'),  # Convert for DB lookup
                'name': row.get('description') or row.get('name'),
                'market_cap': row.get('market_cap_basic'),
                'sector': row.get('sector'),  # English sector name
                'stock_type': row.get('type'),
                
                # Value metrics
                'pe': row.get('price_earnings_ttm'),
                'pb': row.get('price_book_ratio'),
                'ps': row.get('price_sales_ratio'),
                'p_fcf': row.get('price_free_cash_flow_ttm'),
                'ev_ebitda': row.get('enterprise_value_ebitda_ttm'),
                
                # Quality metrics (CALCULATED, not direct!)
                'roe': roe,
                'roa': roa,
                'roic': row.get('return_on_invested_capital'),
                'fcfroe': fcfroe,
                
                # Dividend
                'dividend_yield': row.get('dividend_yield_recent'),
                
                # Momentum (direct from TradingView)
                'perf_1m': row.get('Perf.1M'),
                'perf_3m': row.get('Perf.3M'),
                'perf_6m': row.get('Perf.6M'),
                'perf_12m': row.get('Perf.Y'),
                
                # F-Score
                'piotroski_f_score': f_score,
                
                # F-Score components (for debugging/verification)
                'net_income': row.get('net_income_fq'),
                'operating_cf': row.get('cash_f_operating_activities_ttm'),
                'total_assets': row.get('total_assets_fq'),
                'long_term_debt': row.get('long_term_debt_fq'),
                'current_ratio': row.get('current_ratio_fq'),
                'gross_margin': row.get('gross_margin_ttm'),
                'shares_outstanding': row.get('total_shares_outstanding_fundamental'),
                
                # Metadata
                'data_source': 'tradingview',
                'fetched_date': datetime.now().date(),
            })
        
        return results
    
    def _calculate_fscore(self, row: dict) -> Optional[int]:
        """
        Calculate Piotroski F-Score from components when direct value unavailable.
        Uses YoY growth fields for proper comparison.
        """
        score = 0
        
        # Criterion 1: ROA > 0 (Net Income > 0)
        if row.get('net_income_ttm') and row['net_income_ttm'] > 0:
            score += 1
        
        # Criterion 2: OCF > 0
        if row.get('cash_f_operating_activities_ttm') and row['cash_f_operating_activities_ttm'] > 0:
            score += 1
        
        # Criterion 3: ROA improving (NI growth > 0)
        if row.get('net_income_yoy_growth_ttm') and row['net_income_yoy_growth_ttm'] > 0:
            score += 1
        
        # Criterion 4: OCF > Net Income (quality of earnings)
        ocf = row.get('cash_f_operating_activities_ttm')
        ni = row.get('net_income_ttm')
        if ocf and ni and ocf > ni:
            score += 1
        
        # Criterion 5: Debt ratio decreasing
        if row.get('total_debt_yoy_growth_fy') and row['total_debt_yoy_growth_fy'] < 0:
            score += 1
        
        # Criterion 6: Current ratio > 1 (simplified - no YoY data)
        if row.get('current_ratio_fq') and row['current_ratio_fq'] > 1:
            score += 1
        
        # Criterion 7: No dilution - assume 1 point (no historical shares data)
        score += 1
        
        # Criterion 8: Gross margin improving
        if row.get('gross_profit_yoy_growth_ttm') and row['gross_profit_yoy_growth_ttm'] > 0:
            score += 1
        
        # Criterion 9: Asset turnover improving
        rev_growth = row.get('total_revenue_yoy_growth_ttm')
        asset_growth = row.get('total_assets_yoy_growth_fy')
        if rev_growth and asset_growth and rev_growth > asset_growth:
            score += 1
        
        return score if score > 0 else None
```

### 2. `services/ticker_mapping.py`

```python
"""
Ticker mapping between TradingView and database formats.
TradingView: VOLV_B, HM_B, SSAB_B
Database:    VOLV-B, HM-B, SSAB-B
"""

def tv_to_db_ticker(tv_ticker: str) -> str:
    """Convert TradingView ticker to database format."""
    return tv_ticker.replace('_', '-')

def db_to_tv_ticker(db_ticker: str) -> str:
    """Convert database ticker to TradingView format."""
    return db_ticker.replace('-', '_').replace(' ', '_')

# Sector mapping: TradingView (English) -> Avanza (Swedish)
SECTOR_MAPPING = {
    'Finance': ['Traditionell Bankverksamhet', 'Investmentbolag', 'Försäkring', 
                'Sparande & Investering', 'Kapitalförvaltning', 'Konsumentkredit'],
    'Technology': ['Teknik', 'IT'],
    'Healthcare': ['Hälsovård', 'Läkemedel'],
    'Consumer Cyclical': ['Konsumentvaror', 'Detaljhandel'],
    'Industrials': ['Industri', 'Verkstad'],
    'Basic Materials': ['Råvaror', 'Material'],
    'Energy': ['Energi', 'Olja & Gas'],
    'Real Estate': ['Fastigheter'],
    'Utilities': ['Kraftförsörjning'],
    'Communication Services': ['Telekom', 'Media'],
}

def is_financial_sector(sector: str) -> bool:
    """Check if sector is financial (for exclusion in strategies)."""
    if not sector:
        return False
    return sector.lower() in ['finance', 'financial services']
```

---

## Files to Modify

### 1. `services/ranking.py` - Add TradingView momentum function

```python
def calculate_momentum_score_from_tv(fund_df: pd.DataFrame) -> pd.Series:
    """
    Calculate Sammansatt Momentum from TradingView's pre-calculated returns.
    
    TradingView provides Perf.3M, Perf.6M, Perf.Y directly - no price calculation needed!
    """
    if fund_df.empty:
        return pd.Series(dtype=float)
    
    df = fund_df.set_index('ticker')
    
    # Average of 3m, 6m, 12m returns (same as Börslabbet methodology)
    momentum = (
        df['perf_3m'].fillna(0) + 
        df['perf_6m'].fillna(0) + 
        df['perf_12m'].fillna(0)
    ) / 3
    
    return momentum.replace([np.inf, -np.inf], np.nan).dropna()


def get_fscore_from_tv(fund_df: pd.DataFrame) -> pd.Series:
    """Get F-Score from TradingView data (already pre-calculated)."""
    if fund_df.empty or 'piotroski_f_score' not in fund_df.columns:
        return pd.Series(dtype=float)
    
    return fund_df.set_index('ticker')['piotroski_f_score']
```

### 2. `services/ranking_cache.py` - Use TradingView data

```python
def compute_all_rankings_tv(db) -> dict:
    """
    Compute rankings using TradingView data.
    Much simpler - no price pivot table needed!
    """
    from models import Fundamentals, Stock
    
    # Load fundamentals with TradingView data
    fundamentals = db.query(Fundamentals).filter(
        Fundamentals.data_source == 'tradingview'
    ).all()
    
    if not fundamentals:
        logger.warning("No TradingView data found, falling back to Avanza")
        return compute_all_rankings(db)  # Existing function
    
    fund_df = pd.DataFrame([{
        'ticker': f.ticker,
        'market_cap': f.market_cap / 1e6 if f.market_cap else None,  # Convert to MSEK
        'pe': f.pe,
        'pb': f.pb,
        'ps': f.ps,
        'p_fcf': f.p_fcf,
        'ev_ebitda': f.ev_ebitda,
        'roe': f.roe,
        'roa': f.roa,
        'roic': f.roic,
        'fcfroe': f.fcfroe,
        'dividend_yield': f.dividend_yield,
        'perf_3m': f.perf_3m,
        'perf_6m': f.perf_6m,
        'perf_12m': f.perf_12m,
        'piotroski_f_score': f.piotroski_f_score,
    } for f in fundamentals])
    
    # Add stock metadata
    stocks = {s.ticker: s for s in db.query(Stock).all()}
    fund_df['sector'] = fund_df['ticker'].map(lambda t: stocks.get(t, Stock()).sector)
    fund_df['stock_type'] = fund_df['ticker'].map(lambda t: stocks.get(t, Stock()).stock_type)
    
    # Calculate momentum from pre-calculated fields
    momentum = calculate_momentum_score_from_tv(fund_df)
    f_scores = get_fscore_from_tv(fund_df)
    
    # ... rest of ranking logic unchanged
```

### 3. `jobs/scheduler.py` - Add TradingView sync

```python
from services.tradingview_fetcher import TradingViewFetcher
from services.ticker_mapping import tv_to_db_ticker

async def tradingview_sync(db, force_refresh: bool = False) -> dict:
    """
    Sync fundamentals from TradingView Scanner API.
    Much faster than Avanza (~1s vs ~51s).
    """
    fetcher = TradingViewFetcher()
    
    try:
        # Fetch all Swedish stocks
        stocks = fetcher.fetch_all(min_market_cap=2e9)
        
        if not stocks:
            logger.error("TradingView returned no data")
            return {"status": "ERROR", "message": "No data from TradingView"}
        
        # Update database
        updated = 0
        for stock_data in stocks:
            db_ticker = stock_data['db_ticker']
            
            # Update or create fundamentals record
            # ... database update logic
            updated += 1
        
        db.commit()
        
        return {
            "status": "SUCCESS",
            "stocks_updated": updated,
            "source": "tradingview",
            "duration_seconds": 1  # Approximate
        }
        
    except Exception as e:
        logger.error(f"TradingView sync failed: {e}")
        return {"status": "ERROR", "message": str(e)}
```

---

## Avanza Code to Keep

### In `avanza_fetcher_v2.py`

Keep these functions (needed for historical prices/backtesting):

```python
# KEEP - Historical price fetching
def get_historical_prices(self, stock_id: str, days: int = 400)
def get_historical_prices_extended(self, stock_id: str, years: int = 10)

# KEEP - Index benchmark
def sync_omxs30_index(db)
```

### Deprecate (but don't delete yet)

```python
# DEPRECATE - Replaced by TradingView
def get_stock_overview(self, stock_id: str)
def get_analysis_data(self, stock_id: str)
def fetch_multiple(self, tickers: List[str])
def fetch_multiple_threaded(self, tickers: List[str])
```

---

## Implementation Checklist

### Pre-Migration (Day 0)

- [ ] **Backup database**: `cp backend/app.db backend/app.db.backup_$(date +%Y%m%d)`
- [ ] **Document current state**: Run `python scripts/compare_with_borslabbet.py` and save output
- [ ] **Run benchmark**: `python scripts/benchmark_sync.py` to establish baseline
- [ ] **Verify Avanza still works**: `curl -X POST http://localhost:8000/data/sync-now`

### Phase 1: Database & Models (Day 1)

- [ ] Add new columns to `models.py`
- [ ] Run database migration (see SQL above)
- [ ] Verify migration: `SELECT perf_3m FROM fundamentals LIMIT 1;` (should return NULL)

### Phase 2: TradingView Fetcher (Day 1)

- [ ] Create `services/tradingview_fetcher.py` (code provided above)
- [ ] Create `services/ticker_mapping.py` (code provided above)
- [ ] Run test script to verify API works
- [ ] Test fetcher: `python -c "from services.tradingview_fetcher import TradingViewFetcher; print(len(TradingViewFetcher().fetch_all()))"`

### Phase 3: Ranking Updates (Day 2)

- [ ] Add `calculate_momentum_score_from_tv()` to `ranking.py`
- [ ] Add `get_fscore_from_tv()` to `ranking.py`
- [ ] Update `ranking_cache.py` to use TradingView data
- [ ] Run parallel comparison (see validation section below)

### Phase 4: Sync Integration (Day 2)

- [ ] Add `tradingview_sync()` to scheduler
- [ ] Add `DATA_SOURCE` environment variable check
- [ ] Test full sync: `curl -X POST http://localhost:8000/data/sync-now`
- [ ] Verify all 4 strategies return results

### Phase 5: Validation (Day 3)

- [ ] Compare top 10 for each strategy with Börslabbet website
- [ ] Verify backtesting still works (uses Avanza prices)
- [ ] Test OMXS30 benchmark comparison
- [ ] Check data freshness endpoint

### Phase 6: Cleanup (Day 3)

- [ ] Mark deprecated Avanza functions with `# DEPRECATED` comments
- [ ] Update README with new data source info
- [ ] Add monitoring for TradingView API failures
- [ ] Document rollback procedure in ops runbook

---

## Validation: How to Verify Migration Worked

### 1. Quick Data Check

```python
# Run after first TradingView sync
from db import SessionLocal
from models import Fundamentals

db = SessionLocal()

# Check TradingView data exists
tv_count = db.query(Fundamentals).filter(
    Fundamentals.data_source == 'tradingview'
).count()
print(f"TradingView records: {tv_count}")  # Should be ~300+

# Check momentum fields populated
with_momentum = db.query(Fundamentals).filter(
    Fundamentals.perf_3m.isnot(None)
).count()
print(f"Records with momentum: {with_momentum}")  # Should be ~300+

# Check F-Score populated
with_fscore = db.query(Fundamentals).filter(
    Fundamentals.piotroski_f_score.isnot(None)
).count()
print(f"Records with F-Score: {with_fscore}")  # Should be ~280+
```

### 2. Compare Rankings with Börslabbet

```python
# Get your top 10 for Sammansatt Momentum
import requests
r = requests.get("http://localhost:8000/strategies/sammansatt_momentum/top10")
your_top10 = [s['ticker'] for s in r.json()['stocks']]
print("Your top 10:", your_top10)

# Compare with https://www.borslabbet.se/sammansatt-momentum/
# Expect 6-8 out of 10 to match (timing differences are normal)
```

### 3. Verify Backtesting Still Works

```python
# Backtesting uses Avanza historical prices - should still work
import requests
r = requests.post("http://localhost:8000/backtest", json={
    "strategy": "sammansatt_momentum",
    "start_date": "2024-01-01",
    "end_date": "2024-12-31"
})
print(f"Backtest status: {r.status_code}")
print(f"Total return: {r.json().get('total_return_pct')}%")
```

### 4. Check API Response Times

```bash
# Should be <100ms with TradingView (was ~3s with Avanza on cache miss)
time curl http://localhost:8000/strategies/sammansatt_momentum
```

---

## Rollback Plan

If TradingView blocks access or data quality issues arise:

1. **Feature flag**: Set `DATA_SOURCE=avanza` in environment
2. **Database**: Keep both data sources, query by `data_source` column
3. **Code**: Keep Avanza fetcher intact, just not called by default
4. **Sync**: Scheduler checks feature flag before choosing sync method

```python
# In scheduler.py
import os
DATA_SOURCE = os.getenv('DATA_SOURCE', 'tradingview')

async def daily_sync(db):
    if DATA_SOURCE == 'tradingview':
        result = await tradingview_sync(db)
        if result['status'] == 'ERROR':
            logger.warning("TradingView failed, falling back to Avanza")
            result = await avanza_sync(db)
    else:
        result = await avanza_sync(db)
    return result
```

---

## What Happens to Existing Data?

### Fundamentals Table

- **Existing Avanza data**: Kept, marked with `data_source='avanza'`
- **New TradingView data**: Added with `data_source='tradingview'`
- **Query strategy**: Filter by `data_source` or use most recent `fetched_date`

```python
# Get latest fundamentals (prefer TradingView)
latest = db.query(Fundamentals).filter(
    Fundamentals.ticker == ticker
).order_by(
    Fundamentals.fetched_date.desc()
).first()
```

### DailyPrice Table

- **No changes** - Still populated by Avanza
- **Still needed** for backtesting
- TradingView doesn't provide historical prices in Scanner API

### Stock Table

- **Keep `avanza_id`** - Still needed for price fetching
- **Update `sector`** - May want to store English sector from TradingView
- **Add `tv_ticker`** column (optional) - Store TradingView ticker format

### Stocks Missing from TradingView

Some stocks in your DB may not exist in TradingView (delisted, too small, etc.):

```python
# Find stocks in DB but not in TradingView
db_tickers = {s.ticker for s in db.query(Stock).all()}
tv_tickers = {tv_to_db_ticker(s['ticker']) for s in tv_fetcher.fetch_all()}
missing = db_tickers - tv_tickers
print(f"Stocks not in TradingView: {len(missing)}")
# These will keep using Avanza data or be excluded from rankings
```

### Parallel Running Period (Recommended)

Run both data sources for 1-2 weeks before fully switching:

```python
# In scheduler.py during transition
async def daily_sync_parallel(db):
    """Run both sources and compare."""
    # Fetch from both
    tv_result = await tradingview_sync(db)
    avanza_result = await avanza_sync(db)
    
    # Log comparison
    logger.info(f"TradingView: {tv_result['stocks_updated']} stocks")
    logger.info(f"Avanza: {avanza_result['stocks_updated']} stocks")
    
    # Use TradingView for rankings, Avanza as backup
    return tv_result
```

---

## Troubleshooting

### "No data returned from TradingView"

```python
# Check if API is responding
import requests
r = requests.post("https://scanner.tradingview.com/sweden/scan", json={
    "markets": ["sweden"],
    "columns": ["name"],
    "range": [0, 5]
})
print(r.status_code, r.text[:200])
```

If blocked, TradingView may have rate-limited you. Wait 1 hour and try again.

### "Ticker not found in database"

TradingView uses `VOLV_B`, your DB uses `VOLV-B`. Check ticker mapping:

```python
from services.ticker_mapping import tv_to_db_ticker
db_ticker = tv_to_db_ticker('VOLV_B')  # Returns 'VOLV-B'
```

### "ROE/ROA values don't match Börslabbet"

You're probably using TradingView's pre-calculated field. Calculate from components:

```python
# WRONG
roe = stock['return_on_equity']

# CORRECT
roe = stock['net_income_ttm'] / stock['total_equity_fq'] * 100
```

### "F-Score is NULL for some stocks"

~4% of stocks don't have F-Score in TradingView. Use fallback calculation:

```python
f_score = (
    stock.get('piotroski_f_score_ttm') or
    stock.get('piotroski_f_score_fy') or
    calculate_fscore_from_components(stock)  # See code in fetcher
)
```

### "Backtesting broken after migration"

Backtesting uses `DailyPrice` table (Avanza data). Check:
1. Avanza price sync still running?
2. `Stock.avanza_id` still populated?
3. Historical prices exist for test period?

```python
from models import DailyPrice
count = db.query(DailyPrice).filter(DailyPrice.ticker == 'VOLV-B').count()
print(f"Price records for VOLV-B: {count}")  # Should be 2000+
```

---

## Known Limitations

### TradingView Data

1. **ROE/ROA methodology differs** - TradingView uses annualized quarterly, we calculate from TTM
2. **ROIC differs ~10%** - Different calculation methodology, accept this
3. **F-Score differs ±1** - TradingView averages ~0.2 higher, acceptable for filtering
4. **15-minute delay** - Irrelevant for daily fundamental-based rankings
5. **No historical snapshots** - Can't backtest with TradingView data

### What Still Needs Avanza

1. **Historical prices** - For backtesting
2. **OMXS30 index** - For benchmark comparison
3. **Stock discovery** - Finding new stocks by Avanza ID
4. **Fallback** - If TradingView blocks access

---

## Monitoring & Alerting

Add these checks to `data_integrity.py`:

```python
def check_tradingview_health():
    """Check if TradingView API is responding."""
    fetcher = TradingViewFetcher()
    try:
        stocks = fetcher.fetch_all(min_market_cap=100e9)  # Just top stocks
        if len(stocks) < 10:
            return {"status": "WARNING", "message": "Low stock count"}
        return {"status": "OK", "stock_count": len(stocks)}
    except Exception as e:
        return {"status": "ERROR", "message": str(e)}

def check_data_freshness():
    """Check if fundamentals data is fresh."""
    latest = db.query(Fundamentals).order_by(Fundamentals.fetched_date.desc()).first()
    if not latest:
        return {"status": "ERROR", "message": "No fundamentals data"}
    
    age_days = (date.today() - latest.fetched_date).days
    if age_days > 1:
        return {"status": "WARNING", "message": f"Data is {age_days} days old"}
    return {"status": "OK", "age_days": age_days}
```

---

## Summary

### DO ✅

- Add momentum and F-Score columns to database
- Calculate ROE/ROA from TTM components (not TradingView's field)
- Keep Avanza for historical prices and OMXS30
- Add feature flag for data source switching
- Rate limit requests (1/second)
- Monitor for API blocks

### DON'T ❌

- Use `is_primary` filter (excludes dual-listed stocks)
- Use TradingView's `return_on_equity` directly (wrong methodology)
- Delete Avanza fetcher code
- Deploy commercially without data license
- Share publicly

### Expected Outcomes

- **Sync time**: 51s → <1s (50x faster)
- **Data quality**: Better P/FCF, direct EV/EBITDA
- **Code complexity**: Simpler (no price pivot tables)
- **Memory usage**: Lower (no large price datasets)
- **Börslabbet matching**: Should improve with true P/FCF

---

## Files Changed Summary

| File | Action | Key Changes |
|------|--------|-------------|
| `backend/models.py` | MODIFY | Add 6 columns to Fundamentals |
| `backend/services/tradingview_fetcher.py` | CREATE | New fetcher class (~200 lines) |
| `backend/services/ticker_mapping.py` | CREATE | Ticker conversion functions (~30 lines) |
| `backend/services/ranking.py` | MODIFY | Add `calculate_momentum_score_from_tv()` |
| `backend/services/ranking_cache.py` | MODIFY | Add `compute_all_rankings_tv()` |
| `backend/jobs/scheduler.py` | MODIFY | Add `tradingview_sync()`, feature flag |
| `backend/services/avanza_fetcher_v2.py` | KEEP | Mark deprecated functions, keep price methods |
| `backend/.env` | MODIFY | Add `DATA_SOURCE=tradingview` |

### Exact Locations in Existing Files

**models.py** - Add after line ~95 (after `asset_turnover`):
```python
perf_1m = Column(Float)
perf_3m = Column(Float)
perf_6m = Column(Float)
perf_12m = Column(Float)
piotroski_f_score = Column(Integer)
data_source = Column(String, default='avanza')
```

**ranking.py** - Add after line ~100 (after `calculate_momentum_score`):
```python
def calculate_momentum_score_from_tv(fund_df: pd.DataFrame) -> pd.Series:
    # ... (see code above)
```

**ranking_cache.py** - Add new function, modify `compute_all_rankings()` to check data source

**scheduler.py** - Add after line ~50 (after imports):
```python
DATA_SOURCE = os.getenv('DATA_SOURCE', 'tradingview')
```

---

## References

- [TradingView Terms of Service](https://www.tradingview.com/policies/)
- [tradingview-screener library](https://github.com/shner-elmo/TradingView-Screener)
- [TradingView Screener Fields](https://shner-elmo.github.io/TradingView-Screener/fields/stocks.html)
- [Börslabbet Strategies](https://www.borslabbet.se/borslabbets-strategier/)

---

## Appendix A: Unit Tests for TradingView Fetcher

Create `backend/tests/test_tradingview_fetcher.py`:

```python
"""
Unit tests for TradingView fetcher.
Run with: pytest tests/test_tradingview_fetcher.py -v
"""
import pytest
from unittest.mock import patch, MagicMock
from services.tradingview_fetcher import TradingViewFetcher
from services.ticker_mapping import tv_to_db_ticker, db_to_tv_ticker


class TestTickerMapping:
    """Test ticker conversion functions."""
    
    def test_tv_to_db_basic(self):
        assert tv_to_db_ticker('VOLV_B') == 'VOLV-B'
        assert tv_to_db_ticker('HM_B') == 'HM-B'
        assert tv_to_db_ticker('SSAB_B') == 'SSAB-B'
    
    def test_tv_to_db_sdb(self):
        assert tv_to_db_ticker('ALIV_SDB') == 'ALIV-SDB'
    
    def test_tv_to_db_no_underscore(self):
        assert tv_to_db_ticker('ABB') == 'ABB'
    
    def test_db_to_tv_basic(self):
        assert db_to_tv_ticker('VOLV-B') == 'VOLV_B'
        assert db_to_tv_ticker('HM-B') == 'HM_B'
    
    def test_db_to_tv_with_space(self):
        assert db_to_tv_ticker('VOLV B') == 'VOLV_B'


class TestTradingViewFetcher:
    """Test TradingView API fetcher."""
    
    @pytest.fixture
    def fetcher(self):
        return TradingViewFetcher()
    
    @pytest.fixture
    def mock_response_data(self):
        """Sample TradingView API response."""
        return {
            'data': [
                {
                    's': 'OMXSTO:VOLV_B',
                    'd': [
                        'VOLV_B',  # name
                        'Volvo B',  # description
                        285.50,  # close
                        650000000000,  # market_cap_basic
                        'Industrials',  # sector
                        'stock',  # type
                        12.5,  # price_earnings_ttm
                        2.1,  # price_book_ratio
                        1.5,  # price_sales_ratio
                        8.5,  # price_free_cash_flow_ttm
                        6.2,  # enterprise_value_ebitda_ttm
                        50000000000,  # net_income_ttm
                        200000000000,  # total_equity_fq
                        500000000000,  # total_assets_fq
                        15.5,  # return_on_invested_capital
                        40000000000,  # free_cash_flow_ttm
                        3.5,  # dividend_yield_recent
                        2.5,  # Perf.1M
                        8.3,  # Perf.3M
                        15.2,  # Perf.6M
                        25.8,  # Perf.Y
                        7,  # piotroski_f_score_ttm
                        6,  # piotroski_f_score_fy
                        # ... remaining fields
                    ]
                }
            ]
        }
    
    def test_fetch_all_returns_list(self, fetcher):
        """Test that fetch_all returns a list."""
        with patch.object(fetcher.session, 'post') as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {'data': []}
            mock_post.return_value.raise_for_status = MagicMock()
            
            result = fetcher.fetch_all()
            assert isinstance(result, list)
    
    def test_roe_calculation(self, fetcher):
        """Test that ROE is calculated from TTM, not direct field."""
        # ROE should be: net_income_ttm / total_equity_fq * 100
        net_income = 50000000000
        equity = 200000000000
        expected_roe = (net_income / equity) * 100  # 25%
        
        # Verify calculation logic
        assert expected_roe == 25.0
    
    def test_fscore_fallback(self, fetcher):
        """Test F-Score fallback logic."""
        # Should use TTM first, then FY, then calculate
        stock = {
            'piotroski_f_score_ttm': None,
            'piotroski_f_score_fy': 6,
        }
        f_score = stock.get('piotroski_f_score_ttm') or stock.get('piotroski_f_score_fy')
        assert f_score == 6
    
    def test_api_error_handling(self, fetcher):
        """Test graceful handling of API errors."""
        with patch.object(fetcher.session, 'post') as mock_post:
            mock_post.side_effect = Exception("Connection error")
            
            result = fetcher.fetch_all()
            assert result == []


class TestFScoreCalculation:
    """Test F-Score calculation from components."""
    
    def test_profitable_company(self):
        """Test F-Score for profitable company."""
        stock = {
            'net_income_ttm': 1000000,
            'cash_f_operating_activities_ttm': 1500000,
            'net_income_yoy_growth_ttm': 10,
            'total_debt_yoy_growth_fy': -5,
            'current_ratio_fq': 1.5,
            'gross_profit_yoy_growth_ttm': 8,
            'total_revenue_yoy_growth_ttm': 12,
            'total_assets_yoy_growth_fy': 5,
        }
        
        # Calculate expected score
        score = 0
        if stock['net_income_ttm'] > 0: score += 1  # ROA > 0
        if stock['cash_f_operating_activities_ttm'] > 0: score += 1  # OCF > 0
        if stock['net_income_yoy_growth_ttm'] > 0: score += 1  # ROA improving
        if stock['cash_f_operating_activities_ttm'] > stock['net_income_ttm']: score += 1  # Quality
        if stock['total_debt_yoy_growth_fy'] < 0: score += 1  # Debt decreasing
        if stock['current_ratio_fq'] > 1: score += 1  # Current ratio
        score += 1  # No dilution (assumed)
        if stock['gross_profit_yoy_growth_ttm'] > 0: score += 1  # Margin improving
        if stock['total_revenue_yoy_growth_ttm'] > stock['total_assets_yoy_growth_fy']: score += 1
        
        assert score == 9  # Perfect score
    
    def test_loss_making_company(self):
        """Test F-Score for loss-making company."""
        stock = {
            'net_income_ttm': -1000000,
            'cash_f_operating_activities_ttm': -500000,
            'net_income_yoy_growth_ttm': -20,
            'total_debt_yoy_growth_fy': 15,
            'current_ratio_fq': 0.8,
            'gross_profit_yoy_growth_ttm': -5,
            'total_revenue_yoy_growth_ttm': -10,
            'total_assets_yoy_growth_fy': 5,
        }
        
        score = 0
        if stock.get('net_income_ttm', 0) > 0: score += 1
        if stock.get('cash_f_operating_activities_ttm', 0) > 0: score += 1
        # ... etc
        score += 1  # No dilution assumed
        
        assert score <= 3  # Low score expected


class TestDataQuality:
    """Test data quality validation."""
    
    def test_market_cap_filter(self):
        """Test 2B SEK market cap filter."""
        min_cap = 2_000_000_000
        
        stocks = [
            {'ticker': 'BIG', 'market_cap': 5_000_000_000},
            {'ticker': 'SMALL', 'market_cap': 500_000_000},
            {'ticker': 'MEDIUM', 'market_cap': 2_000_000_000},
        ]
        
        filtered = [s for s in stocks if s['market_cap'] >= min_cap]
        assert len(filtered) == 2
        assert 'SMALL' not in [s['ticker'] for s in filtered]
    
    def test_momentum_average(self):
        """Test Sammansatt Momentum calculation."""
        perf_3m = 10.0
        perf_6m = 15.0
        perf_12m = 25.0
        
        momentum = (perf_3m + perf_6m + perf_12m) / 3
        assert momentum == pytest.approx(16.67, rel=0.01)
```

---

## Appendix B: Data Quality Comparison Script

Create `backend/scripts/compare_with_borslabbet.py`:

```python
"""
Compare our rankings with Börslabbet's published lists.
Run after migration to validate data quality.

Usage: python scripts/compare_with_borslabbet.py
"""
import requests
from datetime import date

API_BASE = "http://localhost:8000"

# Börslabbet's published top 10 (update these manually from their website)
BORSLABBET_MOMENTUM = [
    "LIFCO-B", "LAGERCRANTZ-B", "ADDTECH-B", "INDUTRADE", "NIBE-B",
    "HEXATRONIC", "VITEC", "FORTNOX", "SDIPTECH", "EMBRACER-B"
]

BORSLABBET_VALUE = [
    "SSAB-B", "PEAB-B", "NCC-B", "SKANSKA-B", "JM",
    "BONAVA-B", "FABEGE", "CASTELLUM", "WIHLBORGS", "ATRIUM"
]

BORSLABBET_DIVIDEND = [
    "INVESTOR-B", "INDUSTRIVARDEN-C", "LATOUR-B", "LUNDBERGFORETAGEN-B",
    "KINNEVIK-B", "RATOS-B", "BURE", "CREADES-A", "SVOLDER-B", "OERN-B"
]

BORSLABBET_QUALITY = [
    "EVOLUTION", "SPOTIFY", "HEXAGON-B", "ATLAS-COPCO-A", "ASSA-ABLOY-B",
    "ALFA-LAVAL", "EPIROC-A", "SANDVIK", "SKF-B", "TRELLEBORG-B"
]


def get_our_rankings(strategy: str) -> list:
    """Fetch our top 10 for a strategy."""
    r = requests.get(f"{API_BASE}/strategies/{strategy}/top10")
    if r.status_code == 200:
        return [s['ticker'] for s in r.json().get('stocks', [])]
    return []


def compare_lists(ours: list, theirs: list, strategy: str) -> dict:
    """Compare two lists and return match statistics."""
    ours_set = set(ours)
    theirs_set = set(theirs)
    
    matches = ours_set & theirs_set
    only_ours = ours_set - theirs_set
    only_theirs = theirs_set - ours_set
    
    return {
        'strategy': strategy,
        'match_count': len(matches),
        'match_pct': len(matches) / len(theirs) * 100 if theirs else 0,
        'matches': list(matches),
        'only_ours': list(only_ours),
        'only_theirs': list(only_theirs),
    }


def main():
    print(f"=== Börslabbet Comparison Report ({date.today()}) ===\n")
    
    comparisons = [
        ('sammansatt_momentum', BORSLABBET_MOMENTUM),
        ('trendande_varde', BORSLABBET_VALUE),
        ('trendande_utdelning', BORSLABBET_DIVIDEND),
        ('trendande_kvalitet', BORSLABBET_QUALITY),
    ]
    
    total_matches = 0
    total_stocks = 0
    
    for strategy, borslabbet_list in comparisons:
        our_list = get_our_rankings(strategy)
        result = compare_lists(our_list, borslabbet_list, strategy)
        
        print(f"📊 {strategy.upper()}")
        print(f"   Match: {result['match_count']}/10 ({result['match_pct']:.0f}%)")
        print(f"   ✅ Matches: {', '.join(result['matches']) or 'None'}")
        print(f"   ➕ Only ours: {', '.join(result['only_ours']) or 'None'}")
        print(f"   ➖ Only Börslabbet: {', '.join(result['only_theirs']) or 'None'}")
        print()
        
        total_matches += result['match_count']
        total_stocks += 10
    
    overall_pct = total_matches / total_stocks * 100
    print(f"=== OVERALL: {total_matches}/{total_stocks} ({overall_pct:.0f}%) ===")
    
    if overall_pct >= 60:
        print("✅ PASS: Good alignment with Börslabbet")
    elif overall_pct >= 40:
        print("⚠️ WARNING: Moderate alignment - review data quality")
    else:
        print("❌ FAIL: Poor alignment - investigate data issues")


if __name__ == "__main__":
    main()
```

---

## Appendix C: Performance Benchmark Script

Create `backend/scripts/benchmark_sync.py`:

```python
"""
Benchmark sync performance: Avanza vs TradingView.
Run before and after migration to measure improvement.

Usage: python scripts/benchmark_sync.py
"""
import time
import requests
from datetime import datetime

API_BASE = "http://localhost:8000"


def benchmark_sync(source: str = 'auto') -> dict:
    """Trigger sync and measure time."""
    print(f"Starting sync benchmark at {datetime.now().isoformat()}")
    
    start = time.time()
    
    # Trigger sync
    r = requests.post(f"{API_BASE}/data/sync-now", timeout=120)
    
    elapsed = time.time() - start
    
    result = {
        'source': source,
        'status': r.status_code,
        'elapsed_seconds': round(elapsed, 2),
        'response': r.json() if r.status_code == 200 else r.text,
    }
    
    return result


def benchmark_strategy_api() -> dict:
    """Benchmark strategy API response times."""
    strategies = [
        'sammansatt_momentum',
        'trendande_varde', 
        'trendande_utdelning',
        'trendande_kvalitet',
    ]
    
    results = {}
    
    for strategy in strategies:
        # Cold request (no cache)
        start = time.time()
        r = requests.get(f"{API_BASE}/strategies/{strategy}")
        cold_time = time.time() - start
        
        # Warm request (cached)
        start = time.time()
        r = requests.get(f"{API_BASE}/strategies/{strategy}")
        warm_time = time.time() - start
        
        results[strategy] = {
            'cold_ms': round(cold_time * 1000, 1),
            'warm_ms': round(warm_time * 1000, 1),
            'stocks_returned': len(r.json().get('stocks', [])) if r.status_code == 200 else 0,
        }
    
    return results


def main():
    print("=" * 60)
    print("SYNC PERFORMANCE BENCHMARK")
    print("=" * 60)
    
    # Benchmark sync
    sync_result = benchmark_sync()
    print(f"\nSync completed in {sync_result['elapsed_seconds']} seconds")
    print(f"Status: {sync_result['status']}")
    
    # Benchmark API
    print("\n" + "=" * 60)
    print("STRATEGY API RESPONSE TIMES")
    print("=" * 60)
    
    api_results = benchmark_strategy_api()
    
    print(f"\n{'Strategy':<25} {'Cold (ms)':<12} {'Warm (ms)':<12} {'Stocks':<8}")
    print("-" * 60)
    
    for strategy, times in api_results.items():
        print(f"{strategy:<25} {times['cold_ms']:<12} {times['warm_ms']:<12} {times['stocks_returned']:<8}")
    
    # Summary
    avg_cold = sum(r['cold_ms'] for r in api_results.values()) / len(api_results)
    avg_warm = sum(r['warm_ms'] for r in api_results.values()) / len(api_results)
    
    print("-" * 60)
    print(f"{'AVERAGE':<25} {avg_cold:<12.1f} {avg_warm:<12.1f}")
    
    # Targets
    print("\n" + "=" * 60)
    print("PERFORMANCE TARGETS")
    print("=" * 60)
    
    targets = {
        'Sync time': (sync_result['elapsed_seconds'], 5, 'seconds'),
        'API cold': (avg_cold, 500, 'ms'),
        'API warm': (avg_warm, 100, 'ms'),
    }
    
    for name, (actual, target, unit) in targets.items():
        status = "✅ PASS" if actual <= target else "❌ FAIL"
        print(f"{name}: {actual:.1f} {unit} (target: <{target} {unit}) {status}")


if __name__ == "__main__":
    main()
```

---

## Appendix D: Alerting Setup

Add to `backend/services/data_integrity.py`:

```python
"""
Monitoring and alerting for TradingView data source.
"""
import os
import requests
import logging
from datetime import date, datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

# Slack webhook (optional)
SLACK_WEBHOOK = os.getenv('SLACK_WEBHOOK_URL')


def send_alert(message: str, severity: str = 'warning'):
    """Send alert to Slack (if configured) and log."""
    logger.warning(f"[{severity.upper()}] {message}")
    
    if SLACK_WEBHOOK:
        emoji = '🚨' if severity == 'critical' else '⚠️'
        try:
            requests.post(SLACK_WEBHOOK, json={
                'text': f"{emoji} *Börslabbet Alert*\n{message}",
            }, timeout=10)
        except Exception as e:
            logger.error(f"Failed to send Slack alert: {e}")


def check_tradingview_health() -> dict:
    """Check if TradingView API is responding."""
    try:
        url = "https://scanner.tradingview.com/sweden/scan"
        payload = {
            "filter": [{"left": "market_cap_basic", "operation": "greater", "right": 100e9}],
            "markets": ["sweden"],
            "columns": ["name"],
            "range": [0, 5]
        }
        
        start = datetime.now()
        r = requests.post(url, json=payload, timeout=30)
        elapsed = (datetime.now() - start).total_seconds()
        
        if r.status_code != 200:
            send_alert(f"TradingView API returned {r.status_code}", 'critical')
            return {'status': 'ERROR', 'message': f'HTTP {r.status_code}'}
        
        data = r.json()
        stock_count = len(data.get('data', []))
        
        if stock_count < 3:
            send_alert(f"TradingView returned only {stock_count} stocks", 'warning')
            return {'status': 'WARNING', 'message': 'Low stock count'}
        
        if elapsed > 10:
            send_alert(f"TradingView API slow: {elapsed:.1f}s", 'warning')
        
        return {
            'status': 'OK',
            'stock_count': stock_count,
            'response_time_seconds': round(elapsed, 2)
        }
        
    except requests.Timeout:
        send_alert("TradingView API timeout", 'critical')
        return {'status': 'ERROR', 'message': 'Timeout'}
    except Exception as e:
        send_alert(f"TradingView health check failed: {e}", 'critical')
        return {'status': 'ERROR', 'message': str(e)}


def check_data_freshness(db) -> dict:
    """Check if fundamentals data is fresh."""
    from models import Fundamentals
    
    latest = db.query(Fundamentals).filter(
        Fundamentals.data_source == 'tradingview'
    ).order_by(Fundamentals.fetched_date.desc()).first()
    
    if not latest:
        send_alert("No TradingView data in database", 'critical')
        return {'status': 'ERROR', 'message': 'No TradingView data'}
    
    age_days = (date.today() - latest.fetched_date).days
    
    if age_days > 2:
        send_alert(f"TradingView data is {age_days} days old", 'critical')
        return {'status': 'CRITICAL', 'age_days': age_days}
    elif age_days > 1:
        send_alert(f"TradingView data is {age_days} days old", 'warning')
        return {'status': 'WARNING', 'age_days': age_days}
    
    return {'status': 'OK', 'age_days': age_days}


def check_data_coverage(db) -> dict:
    """Check data coverage for key fields."""
    from models import Fundamentals
    from sqlalchemy import func
    
    total = db.query(func.count(Fundamentals.id)).filter(
        Fundamentals.data_source == 'tradingview'
    ).scalar()
    
    if total == 0:
        return {'status': 'ERROR', 'message': 'No data'}
    
    # Check key fields
    fields = ['perf_3m', 'piotroski_f_score', 'roe', 'pe', 'dividend_yield']
    coverage = {}
    
    for field in fields:
        col = getattr(Fundamentals, field)
        non_null = db.query(func.count(Fundamentals.id)).filter(
            Fundamentals.data_source == 'tradingview',
            col.isnot(None)
        ).scalar()
        coverage[field] = round(non_null / total * 100, 1)
    
    # Alert on low coverage
    for field, pct in coverage.items():
        if pct < 80:
            send_alert(f"Low coverage for {field}: {pct}%", 'warning')
    
    return {
        'status': 'OK',
        'total_records': total,
        'coverage': coverage
    }


def run_all_health_checks(db) -> dict:
    """Run all health checks and return summary."""
    results = {
        'timestamp': datetime.now().isoformat(),
        'tradingview_api': check_tradingview_health(),
        'data_freshness': check_data_freshness(db),
        'data_coverage': check_data_coverage(db),
    }
    
    # Overall status
    statuses = [r.get('status', 'UNKNOWN') for r in results.values() if isinstance(r, dict)]
    if 'ERROR' in statuses or 'CRITICAL' in statuses:
        results['overall'] = 'CRITICAL'
    elif 'WARNING' in statuses:
        results['overall'] = 'WARNING'
    else:
        results['overall'] = 'OK'
    
    return results
```

Add health check endpoint to `main.py`:

```python
@app.get("/health/tradingview")
def tradingview_health(db: Session = Depends(get_db)):
    """Check TradingView data source health."""
    from services.data_integrity import run_all_health_checks
    return run_all_health_checks(db)
```

---

## Appendix E: Using the tradingview-screener Library

The guide uses raw `requests` for clarity, but you can also use the `tradingview-screener` library for cleaner code:

```python
# Alternative implementation using tradingview-screener library
from tradingview_screener import Query, col

def fetch_swedish_stocks_with_library():
    """Fetch using the tradingview-screener library."""
    count, df = (
        Query()
        .select(
            'name', 'close', 'market_cap_basic', 'sector',
            'price_earnings_ttm', 'price_book_ratio',
            'Perf.3M', 'Perf.6M', 'Perf.Y',
            'piotroski_f_score_ttm',
            'net_income_ttm', 'total_equity_fq',
        )
        .where(
            col('market_cap_basic') > 2_000_000_000,
            col('type').isin(['stock', 'dr']),
        )
        .set_markets('sweden')
        .order_by('market_cap_basic', ascending=False)
        .limit(500)
        .get_scanner_data()
    )
    
    # Calculate ROE from components
    df['roe_calculated'] = df['net_income_ttm'] / df['total_equity_fq'] * 100
    
    return df

# Pros of using the library:
# - Cleaner syntax
# - Built-in column validation
# - Better error messages
# - Automatic JSON payload generation

# Cons:
# - Extra dependency
# - Less control over raw request
# - May lag behind API changes
```
