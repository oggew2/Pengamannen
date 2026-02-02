# Avanza CSV Import & Portfolio Performance Tracking

## Implementation Report
**Date:** 2026-02-02  
**Status:** Ready for Implementation

---

## Executive Summary

This document outlines the complete implementation plan for:
1. **Avanza CSV Import** - Import transaction history from Avanza exports
2. **Portfolio Performance Tracking** - Visualize returns over time with fee/spread breakdown
3. **Gross vs Net Returns Toggle** - Show performance before and after costs

---

## Part 1: Avanza CSV Import

### 1.1 CSV Format Analysis

**Avanza Export Columns:**
| Column | Swedish Name | Example | Usage |
|--------|--------------|---------|-------|
| Date | Datum | 2026-02-02 | Transaction date |
| Account | Konto | Quant-Momentum-Dec,Mar,Jun,Sep | Filter (optional) |
| Type | Typ av transaktion | Köp, Sälj, Insättning | Filter to Köp/Sälj |
| Security | Värdepapper/beskrivning | Vestas Wind Systems | Name (backup match) |
| Quantity | Antal | 10, -87 | Shares (negative = sell) |
| Price | Kurs | 190.9 | Price in instrument currency |
| Amount | Belopp | -1909 | Total (negative = buy) |
| Currency | Transaktionsvaluta | SEK, DKK, EUR, NOK | Transaction currency |
| Fee | Courtage | 6.22 | Brokerage fee |
| FX Rate | Valutakurs | 1.439705 | Exchange rate |
| Instrument Currency | Instrumentvaluta | DKK | Stock's native currency |
| ISIN | ISIN | DK0061539921 | **Primary identifier** |
| Result | Resultat | | P&L for sells |

### 1.2 ISIN Matching Strategy

**Primary: TradingView ISIN Lookup**
- TradingView Scanner API returns ISIN for all Nordic stocks
- Fetch fresh on import or cache daily
- 100% match rate in testing (13/13 stocks from sample CSV)

```python
# TradingView API request
payload = {
    "columns": ["name", "description", "isin"],
    "range": [0, 3000]
}
# Returns: {"ticker": "BITTI", "name": "Bittium Corporation", "isin": "FI0009007264"}
```

**Fallback: Fuzzy Name Match**
- If ISIN not found, match by security name
- Use Levenshtein distance or contains match
- Show ambiguous matches for user confirmation

### 1.3 Import Modes

| Mode | Swedish | Description | Use Case |
|------|---------|-------------|----------|
| `replace` | 🔄 Ersätt allt | Clear existing, import fresh | Start over |
| `add_new` | ➕ Lägg till nya | Skip duplicates, add new only | Monthly sync |
| `calculate` | 📊 Beräkna position | Process full history → holdings | Import 1 year |

### 1.4 Duplicate Detection

**Hash Formula:**
```
hash = SHA256(date + isin + type + shares + round(price, 2))
```

**Why these fields:**
- `date` - Same day transactions are different
- `isin` - Unique stock identifier
- `type` - Buy vs Sell
- `shares` - Different quantities = different transactions
- `price` - Same stock, same day, different price = different transaction

**Storage:**
```sql
CREATE TABLE imported_transaction_hashes (
    hash TEXT PRIMARY KEY,
    ticker TEXT,
    imported_at TIMESTAMP
);
```

### 1.5 Transaction Storage

```typescript
interface ImportedTransaction {
    id: string;              // UUID
    date: string;            // "2026-01-07"
    ticker: string;          // "BITTI"
    isin: string;            // "FI0009007264"
    type: 'BUY' | 'SELL';
    shares: number;          // 8
    priceLocal: number;      // 30.65 (EUR)
    priceSek: number;        // 330.22 (SEK)
    currency: string;        // "EUR"
    fee: number;             // 10.22 (SEK)
    fxRate: number;          // 10.75868
    hash: string;            // For duplicate detection
    importedAt: string;      // When imported
}
```

### 1.6 Position Calculation (Average Cost Method)

```python
def calculate_position(transactions: List[Transaction]) -> Position:
    total_shares = 0
    total_cost = 0  # In SEK
    total_fees = 0
    
    for t in sorted(transactions, key=lambda x: x.date):
        if t.type == 'BUY':
            total_shares += t.shares
            total_cost += t.shares * t.priceSek
            total_fees += t.fee
        else:  # SELL
            # Reduce position, adjust cost proportionally
            sell_ratio = t.shares / total_shares
            total_cost -= total_cost * sell_ratio
            total_shares -= t.shares
            total_fees += t.fee
    
    avg_price = total_cost / total_shares if total_shares > 0 else 0
    
    return Position(
        ticker=transactions[0].ticker,
        shares=total_shares,
        avgPriceSek=avg_price,
        totalFees=total_fees,
        currency=transactions[0].currency
    )
```

### 1.7 Edge Cases

| Edge Case | Detection | Solution |
|-----------|-----------|----------|
| Negative position | `total_shares < 0` | Warn: "Saknar köphistorik för {ticker}" |
| ISIN not found | No match in TradingView | Fuzzy name match → manual selection |
| Duplicate import | Hash exists in DB | Skip, show count of skipped |
| Multiple accounts | Different `Konto` values | Import all (user requested) |
| Stock split | Historical prices don't match | Warn user, suggest manual adjustment |
| Currency mismatch | `Instrumentvaluta` differs | Use CSV's currency, convert to SEK |

---

## Part 2: Portfolio Performance Tracking

### 2.1 Data Model

```typescript
// Calculated on-demand, can be cached
interface PortfolioSnapshot {
    date: string;
    holdings: HoldingSnapshot[];
    totalValueSek: number;      // Current market value
    totalCostSek: number;       // What we paid (cost basis)
    totalFeesSek: number;       // Accumulated fees
    estimatedSpreadSek: number; // 0.3% of turnover
    grossReturnPct: number;     // Before fees
    netReturnPct: number;       // After fees
}

interface HoldingSnapshot {
    ticker: string;
    shares: number;
    valueSek: number;
    costSek: number;
    returnPct: number;
}
```

### 2.2 Performance Calculation

```python
def calculate_performance(transactions: List[Transaction], as_of_date: date) -> PortfolioSnapshot:
    # 1. Get holdings at date
    holdings = calculate_holdings_at_date(transactions, as_of_date)
    
    # 2. Get prices for that date
    prices = get_prices_for_date(holdings.keys(), as_of_date)
    
    # 3. Calculate values
    total_value = sum(h.shares * prices[h.ticker] for h in holdings)
    total_cost = sum(h.cost_basis for h in holdings)
    total_fees = sum(t.fee for t in transactions if t.date <= as_of_date)
    
    # 4. Estimate spread (0.3% of all buy/sell turnover)
    turnover = sum(abs(t.shares * t.priceSek) for t in transactions if t.date <= as_of_date)
    estimated_spread = turnover * 0.003
    
    # 5. Calculate returns
    gross_return_pct = ((total_value - total_cost) / total_cost) * 100 if total_cost > 0 else 0
    net_return_pct = ((total_value - total_cost - total_fees - estimated_spread) / total_cost) * 100
    
    return PortfolioSnapshot(
        date=as_of_date,
        totalValueSek=total_value,
        totalCostSek=total_cost,
        totalFeesSek=total_fees,
        estimatedSpreadSek=estimated_spread,
        grossReturnPct=gross_return_pct,
        netReturnPct=net_return_pct
    )
```

### 2.3 Graph Data Generation

```python
def generate_performance_graph(transactions: List[Transaction], period: str = '1Y') -> List[DataPoint]:
    """Generate daily performance data for charting."""
    
    if not transactions:
        return []
    
    start_date = get_period_start(period)  # 1M, 3M, 6M, YTD, 1Y, ALL
    end_date = date.today()
    
    data_points = []
    
    for d in date_range(start_date, end_date):
        snapshot = calculate_performance(transactions, d)
        data_points.append({
            'date': d.isoformat(),
            'grossReturnPct': snapshot.grossReturnPct,
            'netReturnPct': snapshot.netReturnPct,
            'totalValue': snapshot.totalValueSek,
            'totalFees': snapshot.totalFeesSek,
            'totalSpread': snapshot.estimatedSpreadSek
        })
    
    return data_points
```

### 2.4 Fee & Spread Tracking

**Fees (Courtage):**
- Extracted directly from CSV `Courtage` column
- Stored per transaction
- Accumulated over time

**Spread (Estimated):**
- Not in CSV (invisible cost)
- Estimated at 0.3% of transaction value
- Industry standard for Nordic small/mid caps
- Can be adjusted in settings

**Display:**
```
┌─────────────────────────────────────────────────────────────┐
│  Kostnader                                                  │
│                                                             │
│  Courtage (faktisk)      127 kr    (0.13% av investerat)   │
│  Spread (uppskattad)     294 kr    (0.30% av omsättning)   │
│  ─────────────────────────────────────────────────────────  │
│  Totala kostnader        421 kr    (0.43%)                 │
│                                                             │
│  Påverkan på avkastning:                                    │
│  Brutto: +18.4%  →  Netto: +17.9%  (−0.5 procentenheter)   │
└─────────────────────────────────────────────────────────────┘
```

---

## Part 3: UI Design

### 3.1 Import Flow

**Step 1: Upload**
```
┌─────────────────────────────────────────────────────────────┐
│  📥 Importera från Avanza                                   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                                                     │   │
│  │         Dra och släpp CSV-fil här                  │   │
│  │         eller klicka för att välja                 │   │
│  │                                                     │   │
│  │         Accepterar: .csv                           │   │
│  │                                                     │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  💡 Exportera från Avanza:                                  │
│     Mina sidor → Transaktioner → Exportera                 │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Step 2: Preview & Options**
```
┌─────────────────────────────────────────────────────────────┐
│  Hittade 24 transaktioner (Jan 7 - Feb 2, 2026)            │
│                                                             │
│  Importläge:                                                │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ ○ 🔄 Ersätt allt                                    │   │
│  │   Radera befintlig portfölj och importera på nytt   │   │
│  │                                                     │   │
│  │ ● ➕ Lägg till nya                                  │   │
│  │   Behåll befintliga, lägg till nya transaktioner    │   │
│  │                                                     │   │
│  │ ○ 📊 Beräkna slutposition                          │   │
│  │   Beräkna nuvarande innehav från all historik       │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ─────────────────────────────────────────────────────────  │
│                                                             │
│  Matchning:                                                 │
│  ✓ 22 transaktioner matchade                               │
│  ⚠️ 2 redan importerade (hoppas över)                      │
│                                                             │
│  Förhandsvisning:                                           │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Aktie      Antal    Snitt      Valuta    Avgift    │   │
│  │ ─────────────────────────────────────────────────── │   │
│  │ BITTI      +8 st    33.50      EUR       20 kr     │   │
│  │ GOMX      +257 st   20.40      SEK       12 kr     │   │
│  │ VWS       +10 st    190.90     DKK       6 kr      │   │
│  │ SMOP      −87 st    (såld)     NOK       6 kr      │   │
│  │ ...                                                 │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  [Avbryt]                              [Importera]         │
└─────────────────────────────────────────────────────────────┘
```

**Step 3: Confirmation**
```
┌─────────────────────────────────────────────────────────────┐
│  ✓ Import klar!                                             │
│                                                             │
│  • 20 nya transaktioner importerade                        │
│  • 2 duplicerade hoppades över                             │
│  • 10 aktier i portföljen                                  │
│  • Totalt investerat: 98 432 kr                            │
│                                                             │
│  [Visa portfölj]                                           │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 Performance Dashboard

```
┌─────────────────────────────────────────────────────────────────────────┐
│  📊 Portföljöversikt                                                    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  Avkastning                                    [1M][3M][YTD][1Y]│   │
│  │                                                                  │   │
│  │  +18.4%  (brutto)                                               │   │
│  │  +17.9%  (netto, efter avgifter)                                │   │
│  │                                                                  │   │
│  │       ╭────────────────────────────────────────╮                │   │
│  │  +20% │                                    ╱───│                │   │
│  │  +15% │                                ╱───    │  ── Brutto     │   │
│  │  +10% │                            ╱───        │  ── Netto      │   │
│  │   +5% │                    ────────            │                │   │
│  │    0% │────────────────────                    │                │   │
│  │       ╰────────────────────────────────────────╯                │   │
│  │         Jan 7    Jan 15    Jan 22    Jan 29    Feb 2            │   │
│  │                                                                  │   │
│  │  [✓] Visa netto (efter avgifter)                                │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌───────────────┬───────────────┬───────────────┬─────────────────┐   │
│  │  Investerat   │  Nuvarande    │  Avkastning   │  Kostnader      │   │
│  │  98 432 kr    │  116 543 kr   │  +18 111 kr   │  421 kr         │   │
│  │               │               │  (+18.4%)     │  (0.43%)        │   │
│  └───────────────┴───────────────┴───────────────┴─────────────────┘   │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  Kostnadsfördelning                                              │   │
│  │                                                                  │   │
│  │  Courtage (faktisk)       127 kr   ████████░░░░░░░░  30%        │   │
│  │  Spread (uppskattad)      294 kr   ██████████████████  70%      │   │
│  │  ───────────────────────────────────────────────────────────    │   │
│  │  Totalt                   421 kr   (0.43% av investerat)        │   │
│  │                                                                  │   │
│  │  💡 Spread är en uppskattning baserad på 0.3% av omsättning     │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  Innehav                                              Sortera ▼ │   │
│  │                                                                  │   │
│  │  Aktie     Antal    Värde       Kostnad     Avkastning          │   │
│  │  ─────────────────────────────────────────────────────────────  │   │
│  │  BITTI     8 st     3 220 kr    2 318 kr    +902 kr (+38.9%)   │   │
│  │  GOMX    257 st     5 654 kr    5 222 kr    +432 kr (+8.3%)    │   │
│  │  VWS      10 st     2 960 kr    2 960 kr    +0 kr (0%)         │   │
│  │  SANION  222 st     5 850 kr    5 201 kr    +649 kr (+12.5%)   │   │
│  │  NELLY    41 st     5 486 kr    4 676 kr    +810 kr (+17.3%)   │   │
│  │  ...                                                            │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  [📥 Importera CSV]  [📜 Transaktionshistorik]  [📤 Exportera]        │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 3.3 Transaction History View

```
┌─────────────────────────────────────────────────────────────────────────┐
│  📜 Transaktionshistorik                                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Filter: [Alla ▼]  [Alla aktier ▼]  Sök: [____________]                │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  Datum       Typ    Aktie    Antal    Pris       Avgift        │   │
│  │  ─────────────────────────────────────────────────────────────  │   │
│  │  2026-02-02  SÄLJ   SMOP     87 st    28.80 NOK  0 kr          │   │
│  │  2026-02-02  KÖP    VWS      10 st    190.90 DKK 0 kr          │   │
│  │  2026-02-02  KÖP    BITTI    7 st     37.60 EUR  0 kr          │   │
│  │  2026-02-02  KÖP    GOMX     121 st   22.50 SEK  0 kr          │   │
│  │  2026-01-07  KÖP    BITTI    8 st     30.65 EUR  10 kr         │   │
│  │  2026-01-07  KÖP    GOMX     136 st   18.30 SEK  6 kr          │   │
│  │  ...                                                            │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  Visar 24 av 24 transaktioner                                          │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Part 4: API Design

### 4.1 Endpoints

```yaml
# Import CSV
POST /api/v1/portfolio/import-csv
Request:
  csv_content: string (base64 or raw)
  mode: "replace" | "add_new" | "calculate"
Response:
  parsed: number
  matched: number
  duplicates_skipped: number
  unmatched: [{name, isin, row}]
  preview: [{ticker, shares, avgPrice, currency, fees}]
  warnings: [string]

# Get ISIN lookup (for matching)
GET /api/v1/isin-lookup
Response:
  {isin: {ticker, name, currency}}

# Get transactions
GET /api/v1/portfolio/transactions
Query: ?from=2026-01-01&to=2026-02-02&ticker=BITTI
Response:
  transactions: [ImportedTransaction]

# Get performance data
GET /api/v1/portfolio/performance
Query: ?period=1Y
Response:
  dataPoints: [{date, grossReturnPct, netReturnPct, totalValue, totalFees, totalSpread}]
  summary: {invested, currentValue, grossReturn, netReturn, totalFees, totalSpread}

# Confirm import
POST /api/v1/portfolio/import-confirm
Request:
  transactions: [ImportedTransaction]
  mode: string
Response:
  success: boolean
  imported: number
```

### 4.2 Database Schema

```sql
-- Individual transactions (imported from CSV)
CREATE TABLE portfolio_transactions_imported (
    id TEXT PRIMARY KEY,
    date TEXT NOT NULL,
    ticker TEXT NOT NULL,
    isin TEXT,
    type TEXT NOT NULL,  -- 'BUY' or 'SELL'
    shares INTEGER NOT NULL,
    price_local REAL NOT NULL,
    price_sek REAL NOT NULL,
    currency TEXT NOT NULL,
    fee REAL DEFAULT 0,
    fx_rate REAL,
    hash TEXT UNIQUE,  -- For duplicate detection
    imported_at TEXT NOT NULL,
    source TEXT DEFAULT 'avanza_csv'
);

-- ISIN lookup cache (refreshed daily from TradingView)
CREATE TABLE isin_lookup (
    isin TEXT PRIMARY KEY,
    ticker TEXT NOT NULL,
    name TEXT,
    currency TEXT,
    market TEXT,
    updated_at TEXT
);

-- Performance snapshots cache (optional, for speed)
CREATE TABLE portfolio_snapshots_cache (
    date TEXT PRIMARY KEY,
    total_value_sek REAL,
    total_cost_sek REAL,
    total_fees_sek REAL,
    gross_return_pct REAL,
    net_return_pct REAL,
    holdings_json TEXT,
    computed_at TEXT
);
```

---

## Part 5: Implementation Plan

### Phase 1: ISIN Lookup (2h)
- [ ] Add `isin` column to TradingView fetcher
- [ ] Create `isin_lookup` table
- [ ] Add endpoint `GET /api/v1/isin-lookup`
- [ ] Cache ISIN data daily during sync

### Phase 2: CSV Parser (2h)
- [ ] Parse Avanza CSV format
- [ ] Filter to Köp/Sälj transactions
- [ ] Match ISIN → ticker
- [ ] Calculate positions (average cost)
- [ ] Duplicate detection with hash

### Phase 3: Import UI (3h)
- [ ] File upload component (drag & drop)
- [ ] Preview table with matched stocks
- [ ] Import mode selector
- [ ] Confirmation dialog
- [ ] Error handling for unmatched

### Phase 4: Transaction Storage (1h)
- [ ] Create `portfolio_transactions_imported` table
- [ ] Store individual transactions
- [ ] Update holdings from transactions

### Phase 5: Performance Calculation (2h)
- [ ] Calculate holdings at any date
- [ ] Get historical prices from `daily_prices`
- [ ] Calculate gross/net returns
- [ ] Generate time series data

### Phase 6: Performance UI (3h)
- [ ] Performance chart with Recharts
- [ ] Gross/Net toggle
- [ ] Period selector (1M, 3M, YTD, 1Y)
- [ ] Cost breakdown panel
- [ ] Holdings table with P&L

### Phase 7: Testing & Polish (2h)
- [ ] Test with real Avanza CSV
- [ ] Edge cases (negative positions, missing ISIN)
- [ ] Mobile responsive
- [ ] Loading states

**Total Estimate: ~15 hours**

---

## Part 6: Best Practices (from Research)

### From Simple Portfolio:
- Show **annualized** returns for long-term perspective
- Display **fee ratio** as percentage of invested
- Include **benchmark comparison** (OMXS30)
- Track dividends automatically

### From Koinly:
- Duplicate detection based on **same source + format**
- Hash using **timestamp + amount + asset**
- Warn when mixing import methods (CSV vs API)
- Allow **permanent deletion** of duplicates

### From TradingView:
- Default to **merge mode** (add unique only)
- Match on **all parameters** for duplicate check
- Provide **example CSV** for format reference
- Show **line number** for format errors

### From Portfolio Performance:
- Support multiple **import types** (transactions, securities, quotes)
- Allow **custom field mapping**
- Save **import configurations** for reuse
- Validate **consistency** (can't sell more than owned)

### From BlackLabel (Cost Tracking):
- Show costs **over time** (trend visualization)
- Break down by **cost type** (fees, spread, taxes)
- Calculate **impact on returns** (gross vs net)
- Identify **cost sources** and patterns

---

## Part 7: Files to Create/Modify

### Backend:
```
backend/
├── services/
│   ├── tradingview_fetcher.py  # Add ISIN column
│   ├── csv_importer.py         # NEW: Parse Avanza CSV
│   └── portfolio_performance.py # NEW: Calculate returns
├── main.py                      # Add import endpoints
└── models.py                    # Add transaction table
```

### Frontend:
```
frontend/src/
├── components/
│   ├── CsvImporter.tsx          # NEW: Upload & preview
│   ├── PerformanceChart.tsx     # NEW: Returns graph
│   ├── CostBreakdown.tsx        # NEW: Fee visualization
│   └── TransactionHistory.tsx   # NEW: Transaction list
├── pages/
│   └── PortfolioPage.tsx        # Update with new components
└── api/
    └── client.ts                # Add import endpoints
```

---

## Summary

This implementation adds:

1. **Avanza CSV Import** with ISIN-based matching (100% accuracy)
2. **Transaction History** stored individually for full traceability
3. **Performance Tracking** showing returns over time
4. **Gross vs Net Toggle** to see impact of fees/spread
5. **Cost Breakdown** showing exact fees and estimated spread

The UI follows best practices from leading portfolio trackers (Simple Portfolio, TradingView, Portfolio Performance) with clear visualization of costs and their impact on returns.

---

*Ready for implementation. Start with Phase 1 (ISIN Lookup) to enable accurate matching.*
