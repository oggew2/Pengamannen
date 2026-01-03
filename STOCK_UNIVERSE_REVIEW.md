# Stock Universe Review & Improvement Plan

**Last Updated:** 2026-01-03
**Status:** Analysis Complete - Ready for Implementation

---

## Executive Summary

### Current State
| Metric | Value | Status |
|--------|-------|--------|
| Total records in stocks table | 61,675 | Includes misclassified products |
| ETFs/Certificates | 51,506 | Correctly classified |
| Active stocks (with fundamentals) | 714 | ⚠️ Below expected |
| Strategy-eligible (>2B SEK) | 300 | ✅ Reasonable |
| Missing real stocks (inactive) | ~29 | 🔴 Should be synced |
| Misclassified warrants/bonds as 'stock' | ~9,400 | 🔴 Classification issue |

### Expected (from official sources)
| Source | Main Market | First North | Total |
|--------|-------------|-------------|-------|
| Stockanalysis.com (2026) | 755 | - | 755 |
| Nasdaq Nordic (end 2024) | 684 | 490 | 1,174 |
| Wikipedia (2024) | ~385 | ~550 | ~935 |

### Gap Analysis
- **Expected Swedish stocks:** ~755 (main) + ~400 (First North Swedish) ≈ **1,100-1,200**
- **Our active stocks:** 714
- **Gap:** ~400-500 stocks
- **Root cause:** Circular dependency + misclassification

---

## ROOT CAUSES IDENTIFIED 🔴

### Issue #1: Circular Dependency (is_active)

The sync system has a chicken-and-egg problem:

```
1. get_live_stock_universe() → Only returns stocks WHERE is_active = 1
2. avanza_sync() → Only fetches fundamentals for stocks from get_live_stock_universe()
3. mark_stocks_with_fundamentals_active() → Sets is_active = 1 only for stocks WITH fundamentals
```

**Result:** New stocks discovered by the scanner are NEVER synced because:
- They start with `is_active = 0` (default)
- The sync skips them because they're not active
- They never get fundamentals
- They stay inactive forever

**Evidence - Real stocks stuck as inactive:**
| Ticker | Name | Avanza ID | Tradeable | Has Fundamentals |
|--------|------|-----------|-----------|------------------|
| G5EN | G5 Entertainment | 152492 | ✅ Yes | ❌ No |
| NP3 | NP3 Fastigheter | 522855 | ✅ Yes | ❌ No |
| B3 | B3 Consulting Group | 665185 | ✅ Yes | ❌ No |
| EG7 | Enad Global 7 | 811105 | ✅ Yes | ❌ No |
| BRE2 | Bredband2 | 6047 | ✅ Yes | ❌ No |

All verified tradeable on Avanza API with P/E ratios and market caps available.

### Issue #2: Stock Type Misclassification

~9,400 warrants, bonds, and structured products are classified as `stock_type = 'stock'`:

**Examples of misclassified products:**
- `ABB6A 700SHB` - SHB warrant on ABB
- `OMXS306A` - Index option
- `VOL6A 277NDSX` - Nordea warrant on Volvo
- `BULL SILVER X1 N1` - Leveraged product
- Various bonds: `FABG_125`, `HEBA_101GB`, etc.

**Pattern analysis:**
- `XXX6A/6B/6C...SHB` - SHB bank warrants
- `XXX6A/6F/6L...NDS/NDSX` - Nordea warrants
- `OMXS30*`, `S30MIN*` - Index products
- `BULL*`, `BEAR*`, `MINI*` - Leveraged ETPs
- `XXX_123`, `XXX_123GB` - Bonds

### Issue #3: is_active Flag Confusion

**Original intent** (from models.py comment): "False if delisted or no longer on Avanza"
**Current behavior:** "True only if stock has fundamentals data"

This creates confusion because:
- `is_active` doesn't mean "tradeable" - it means "has fundamentals"
- Strategy filtering already handles stock selection via `stock_type` and `market_cap`
- The flag is redundant for filtering but creates sync problems

---

## Current System Architecture

### 1. Stock Discovery (stock_scanner.py)
- **Runs:** Bi-weekly (every other Sunday at 3 AM UTC)
- **Method:** Scans Avanza ID ranges (5000 - 10,000,000)
- **Classification:** Pattern matching for ETFs/certificates
- **Status:** ⚠️ Working but classification needs improvement
- **Issue:** Many warrants/bonds classified as 'stock'

### 2. Stock Validation (stock_validator.py)
- **Method:** `mark_stocks_with_fundamentals_active()`
- **Logic:** Sets `is_active = 1` only for stocks WITH fundamentals
- **Runs:** After each daily sync
- **Status:** ⚠️ Creates circular dependency

### 3. Daily Sync (avanza_fetcher_v2.py)
- **Runs:** Daily at 6 AM UTC
- **Fetches:** Fundamentals + prices via Avanza API
- **Status:** ⚠️ Only syncs 714 active stocks
- **Issue:** Uses `get_live_stock_universe()` which filters by `is_active = 1`

### 4. Live Universe (live_universe.py)
- **Function:** `get_live_stock_universe()`
- **Query:** `WHERE stock_type IN ('stock', 'sdb') AND is_active = 1`
- **Status:** 🔴 ROOT CAUSE - excludes new stocks

### 5. Strategy Filtering (ranking.py)
- **Market cap filter:** ≥2B SEK ✅ Correct per Börslabbet
- **Stock type filter:** Only 'stock' and 'sdb' ✅ Correct
- **Financial exclusion:** Banks, insurance, investment companies ✅ Correct
- **Status:** ✅ Working correctly

---

## Börslabbet Strategy Rules Verification

From [börslabbet.se/borslabbets-strategier](https://borslabbet.se/borslabbets-strategier/):

| Rule | Our Implementation | Status |
|------|-------------------|--------|
| Universe: Top 40% by market cap | `MIN_MARKET_CAP_MSEK = 2000` | ✅ Correct |
| Universe: Stockholmsbörsen + First North | `market IN ('Stockholmsbörsen', 'First North Stockholm')` | ✅ Correct |
| Exclude: Financial companies | `FINANCIAL_SECTORS` list | ✅ Correct |
| Momentum: 3m, 6m, 12m average | `calculate_momentum_score()` | ✅ Correct |
| Quality filter: Piotroski F-Score | `calculate_piotroski_f_score()` | ✅ Correct |
| Rebalancing: Quarterly | Configurable | ✅ Correct |
| Portfolio: Top 10 stocks | Configurable | ✅ Correct |

**Quote from Börslabbet:**
> "För att endast ha likvida aktier som enkelt går att handla till låga kostnader utgår vi från topp 40 % av alla aktier på börsen. Detta motsvarar bolag över 2 miljarder i börsvärde."

Our 2B SEK threshold is correct.

---

## Improvement Plan

### FIX #1: Remove is_active Filter from Sync (CRITICAL)

**File:** `backend/services/live_universe.py`

**Change:**
```python
# BEFORE:
query = """SELECT ticker FROM stocks 
           WHERE stock_type IN ('stock', 'sdb') 
           AND is_active = 1
           AND avanza_id IS NOT NULL AND avanza_id != ''"""

# AFTER:
query = """SELECT ticker FROM stocks 
           WHERE stock_type IN ('stock', 'sdb') 
           AND avanza_id IS NOT NULL AND avanza_id != ''"""
```

**Impact:**
- Sync will attempt ~10,000 stocks (including misclassified)
- Most will fail (no fundamentals on Avanza for warrants/bonds)
- ~29 real stocks will get synced
- After sync, `mark_stocks_with_fundamentals_active()` sets `is_active` correctly
- Strategy calculations continue to use `is_active` filter (unchanged)

**Risk:** Sync time increases from ~1 min to ~10-15 min (one-time)

### FIX #2: Improve Stock Type Classification

**File:** `backend/services/stock_scanner.py`

**Add patterns to `classify_stock_type()`:**
```python
# Warrant patterns
if re.search(r'\d[A-Z]\d', ticker):  # 6A2, 7L9
    return 'warrant'
if ticker.endswith(('SHB', 'NDS', 'NDSX')):
    return 'warrant'
if ticker.startswith(('OMXS', 'S30MIN')):
    return 'index_product'
if ticker.startswith(('BULL', 'BEAR', 'MINI')):
    return 'etf_certificate'
if '_' in ticker and re.search(r'_\d+', ticker):
    return 'bond'
```

**Impact:** Prevents future misclassification

### FIX #3: Clean Up Existing Misclassified Stocks

**One-time migration script:**
```sql
-- Reclassify warrants
UPDATE stocks SET stock_type = 'warrant' 
WHERE stock_type = 'stock' 
AND (ticker LIKE '%SHB' OR ticker LIKE '%NDS%' OR ticker GLOB '*[0-9][A-Z][0-9]*');

-- Reclassify index products
UPDATE stocks SET stock_type = 'index_product'
WHERE stock_type = 'stock'
AND (ticker LIKE 'OMXS%' OR ticker LIKE 'S30MIN%');

-- Reclassify leveraged products
UPDATE stocks SET stock_type = 'etf_certificate'
WHERE stock_type = 'stock'
AND (ticker LIKE 'BULL%' OR ticker LIKE 'BEAR%' OR ticker LIKE 'MINI%');
```

### FIX #4: Consider Removing is_active Dependency

**Analysis:**
- `is_active` is currently redundant for strategy filtering
- `ranking.py` already filters by `stock_type` and `market_cap`
- Only real use is in `data_integrity.py` for coverage checks

**Options:**
1. Keep `is_active` but change meaning to "has fundamentals" (current)
2. Remove `is_active` entirely, use `fundamentals` table join instead
3. Add `has_fundamentals` flag, repurpose `is_active` for "tradeable"

**Recommendation:** Option 1 (keep current behavior, just fix sync)

---

## Action Items

### Immediate (Today)
- [x] Fix `get_live_stock_universe()` to remove `is_active` filter ✅ DONE
- [x] Run cleanup script to reclassify warrants/bonds ✅ DONE (2,308 reclassified)
- [x] Update `classify_stock_type()` with better patterns ✅ DONE
- [ ] Run manual sync to populate fundamentals for all stocks
- [ ] Verify ~29 missing stocks get synced (G5EN, NP3, B3, etc.)

### Short-term (This Week)
- [ ] Add monitoring for stock count changes
- [ ] Verify active stock count increases to ~750-800 after sync

### Medium-term (This Month)
- [ ] Add Nasdaq official list as validation source
- [ ] Implement weekly full validation against official lists
- [ ] Add data quality dashboard
- [ ] Consider adding `instrument_type` field for better classification

---

## Validation Checklist

After implementing fixes, verify:

- [ ] Active stocks ≥ 700 (currently 714, should stay similar or increase)
- [ ] G5EN, NP3, B3, EG7, BRE2 have fundamentals
- [ ] Strategy-eligible stocks ≥ 280 (currently 300)
- [ ] No warrants/bonds in strategy rankings
- [ ] Sync completes without errors
- [ ] Data integrity checks pass

---

## References

### Official Sources
- [Stockanalysis.com - Nasdaq Stockholm](https://stockanalysis.com/list/nasdaq-stockholm/) - 755 stocks (2026)
- [Nasdaq Nordic 2024 Statistics](https://www.marketsmedia.com/nasdaq-nordic-baltic-markets-annual-trading-statistics-2024/) - 1,174 companies (684 main + 490 First North)
- [Baker McKenzie - Nasdaq Stockholm](https://resourcehub.bakermckenzie.com/en/resources/cross-border-listings-guide/europe-middle-east--africa/nasdaq-stockholm/topics/overview-of-exchange) - 636 companies on main market (Dec 2024)
- [Wikipedia - Nasdaq First North](https://en.wikipedia.org/wiki/Nasdaq_First_North) - ~550 companies (early 2024)

### Strategy Rules
- [Börslabbet Strategies](https://borslabbet.se/borslabbets-strategier/) - Official rules
  - Top 40% by market cap = ~2B SEK threshold
  - Stockholmsbörsen + First North universe
  - Excludes financial companies
  - Quarterly rebalancing for momentum

### Data Sources
- [Börsdata](https://www.borsdata.se/) - Used by Börslabbet for backtesting
- [Avanza API](https://www.avanza.se/) - Our primary data source

---

## Appendix: Database Statistics

```
=== STOCK TYPE BREAKDOWN (After Fixes) ===
Type                 Count
etf_certificate      51,552
stock                7,840
warrant              1,344 (NEW - reclassified)
bond                 521 (NEW - reclassified)
index_product        397 (NEW - reclassified)
preference           13
sdb                  8

=== SYNC UNIVERSE ===
Stocks for sync (stock + sdb): 7,848
Previously: 714 (with is_active filter)
Increase: +7,134 stocks now eligible for sync

=== STRATEGY ELIGIBLE ===
Stocks with market_cap >= 2B SEK: 300
Active stocks (with fundamentals): 713

=== INACTIVE REAL STOCKS (will be synced) ===
2CUREX, 4C, 8TRA, ALVO SDB, ARION SDB, B3, BRE2, CYB1, 
DMXSE SDB, EG7, EXPRS2, G2M, G5EN, GIG SDB, GSKR SDB, 
IMP A SDB, K2A B, K33, NP3, S2M, SAMPO SDB, VO2, W5, etc.
```
