# Börslabbet Strategy Reverse Engineering Analysis

**Date:** 2026-01-03
**Objective:** Compare our implementation with Börslabbet's actual rankings to identify differences

## Executive Summary

After analyzing Börslabbet's CSV exports against our implementation, I've identified several key differences:

| Issue | Impact | Priority |
|-------|--------|----------|
| F-Score calculation differs | High - affects Momentum strategy | 🔴 Critical |
| Trendande percentile logic | High - affects all Trendande strategies | 🔴 Critical |
| Financial sector exclusion | Medium - Investmentbolag handling | 🟡 Medium |
| Data timing differences | Low - expected variation | 🟢 Low |

---

## 1. SAMMANSATT MOMENTUM - Detailed Comparison

### Börslabbet's Top 10 (from CSV):
| Rank | Ticker | 3m | 6m | 12m | Sammansatt | F-Score |
|------|--------|-----|-----|------|------------|---------|
| 1 | NELLY | 42.3% | 158.8% | 266.1% | 155.7% | 5 |
| 2 | SANION | 76.0% | 96.4% | 167.1% | 113.2% | 5 |
| 3 | LUG | 27.4% | 59.6% | 212.5% | 99.8% | 5 |
| 4 | GOMX | 11.5% | -9.8% | 269.8% | 90.5% | 5 |
| 5 | LUMI | 41.3% | 94.3% | 97.5% | 77.7% | 7 |
| 6 | NREST | 21.9% | 35.0% | 120.0% | 59.0% | 5 |
| 7 | SVIK | 6.5% | 57.3% | 107.9% | 57.2% | 8 |
| 8 | HAYPP | -10.3% | 9.7% | 141.9% | 47.1% | 5 |
| 9 | BIOA B | 8.1% | 75.4% | 49.4% | 44.3% | 7 |
| 10 | KARNEL B | 26.4% | 30.7% | 74.8% | 44.0% | 7 |

### Our Top 10:
| Rank | Ticker | Calculated Momentum |
|------|--------|---------------------|
| 1 | NELLY | 157.2% |
| 2 | GOMX | 123.4% |
| 3 | SANION | 118.5% |
| 4 | ACAST | 110.1% |
| 5 | LUG | 88.9% |
| 6 | LUMI | 76.4% |
| 7 | SVIK | 66.5% |
| 8 | NREST | 59.0% |
| 9 | VOLCAR B | 57.0% |
| 10 | BOL | 55.2% |

### Key Differences:

#### 🔴 F-Score Calculation Mismatch
| Ticker | Our F-Score | Börslabbet F-Score |
|--------|-------------|-------------------|
| HAYPP | 3 | 5 |
| GOMX | 4 | 5 |
| SVIK | 5 | 8 |
| LUMI | 5 | 7 |
| BIOA B | 6 | 7 |
| KARNEL B | 5 | 7 |

**Impact:** HAYPP is filtered out by us (F-Score ≤ 3) but included by Börslabbet (F-Score = 5)

**Root Cause:** Our F-Score calculation uses different data or methodology:
- We may be missing year-over-year comparison data
- We give "benefit of doubt" points when data is missing
- Börslabbet likely has access to more complete historical data

#### 🔴 Stocks We Include That They Don't:
- **ACAST** (F-Score = 4): High momentum but filtered by Börslabbet
- **VOLCAR B** (F-Score = 4): Filtered by Börslabbet
- **BOL** (F-Score = 6): Lower momentum, not in their top 10

#### 🟡 Investmentbolag Handling:
- **KARNEL B** is in Börslabbet's top 10 (sector: Investmentbolag)
- Our code excludes Investmentbolag for Trendande strategies but NOT for Momentum
- This appears correct ✓

---

## 2. TRENDANDE VÄRDE - Detailed Comparison

### Börslabbet's Top 10 (from CSV):
| Rank | Ticker | Sammansatt Värde Rank |
|------|--------|----------------------|
| 1 | SSAB B | 14 |
| 2 | ATT | 26 |
| 3 | CLA B | 28 |
| 4 | HUM | 1 |
| 5 | AMBEA | 36 |
| 6 | NCC B | 4 |
| 7 | ACAD | 2 |
| 8 | COOR | 37 |
| 9 | TELIA | 38 |
| 10 | BILI A | 12 |

### Our Top 10:
| Rank | Ticker |
|------|--------|
| 1 | SANION |
| 2 | VOLCAR B |
| 3 | BOL |
| 4 | SVED B |
| 5 | BHG |
| 6 | SSAB B |
| 7 | SSAB A |
| 8 | ATT |
| 9 | CLA B |
| 10 | HUM |

### Key Insight from Börslabbet's Data:
The "Sammansatt värde Rank" column shows the VALUE rank, but the final ranking is sorted by MOMENTUM.

- HUM has value rank #1 but is #4 overall (lower momentum)
- SSAB B has value rank #14 but is #1 overall (highest momentum among top value stocks)

### 🔴 Critical Issue: Percentile Logic

**Börslabbet's method (from their documentation):**
> "topp 40% av aktierna efter det primära kriteriet → översta fjärdedelen efter momentum"
> (top 40% by primary criterion → top quarter by momentum)

**This means:**
1. Take top 40% by value (Sammansatt Värde)
2. From that pool, take top 25% by momentum
3. Result: ~10% of universe

**Our current implementation:**
```python
# In calculate_value_score():
top_value = _filter_top_percentile(-value_score, 40)  # Top 40% by value
n_select = max(10, int(len(filtered_mom) * 0.25))     # Top 25% by momentum
```

**Problem:** Looking at Börslabbet's CSV, their "Sammansatt värde Rank" goes up to 40, suggesting they show top ~40 stocks by value, then sort by momentum. But our results show SANION at #1 which has very high momentum but may not be in top 40% by value.

**Hypothesis:** We might be:
1. Including stocks that shouldn't pass the value filter
2. Using different value metrics
3. Having data quality issues in fundamentals

---

## 3. TRENDANDE UTDELNING - Detailed Comparison

### Börslabbet's Top 10:
| Rank | Ticker | Direktavk. | Direktavk. Rank |
|------|--------|------------|-----------------|
| 1 | SSAB B | 3.8% | 25 |
| 2 | HM B | 3.7% | 28 |
| 3 | NCC B | 5.0% | 13 |
| 4 | FMM B | 3.1% | 40 |
| 5 | TELIA | 5.1% | 12 |
| 6 | TEL2 B | 4.1% | 20 |
| 7 | BILI A | 4.1% | 19 |
| 8 | SKF B | 3.2% | 37 |
| 9 | PEAB B | 3.2% | 35 |
| 10 | DUNI | 4.8% | 15 |

### Our Top 10:
| Rank | Ticker |
|------|--------|
| 1 | RVRC |
| 2 | SVED B |
| 3 | SSAB B |
| 4 | SSAB A |
| 5 | CLA B |
| 6 | SYNSAM |
| 7 | FMM B |
| 8 | NOKIA SEK |
| 9 | SHOT |
| 10 | NCC B |

### Key Observation:
- SSAB B has dividend rank #25 but is #1 overall (best momentum among top dividend stocks)
- This confirms the two-step process: filter by dividend, sort by momentum

### 🔴 Issue: Our dividend yield data may be incorrect
Looking at our fundamentals:
- SSAB B: dividend_yield = 0.04% (should be ~3.8%)
- This suggests our dividend_yield is stored as a decimal (0.04 = 4%) but Börslabbet shows percentages

**Data format issue:** We may be storing dividend yield as decimal (0.038) but treating it as percentage (3.8%).

---

## 4. TRENDANDE KVALITET - Detailed Comparison

### Börslabbet's Top 10:
| Rank | Ticker | ROE | ROA | ROIC | FCFROE | Sammansatt ROI Rank |
|------|--------|-----|-----|------|--------|---------------------|
| 1 | NELLY | 42.1% | 15.0% | 35.9% | 35.5% | 11 |
| 2 | SANION | 83.2% | 74.8% | 3432.0% | 83.3% | 1 |
| 3 | LUG | 56.0% | 45.1% | 83.5% | 62.6% | 2 |
| 4 | NREST | 46.4% | 16.2% | 43.8% | 36.7% | 8 |
| 5 | RVRC | 23.7% | 17.9% | 26.5% | 26.1% | 17 |
| 6 | BIOA B | 50.8% | 38.4% | 111.5% | 25.4% | 7 |
| 7 | HM B | 27.6% | 6.3% | 13.5% | 46.7% | 29 |
| 8 | AZN | 20.6% | 8.3% | 13.1% | 26.0% | 35 |
| 9 | SNM | 18.0% | 9.6% | 11.5% | 49.1% | 31 |
| 10 | ZZ B | 42.2% | 15.2% | 134.4% | 58.1% | 4 |

### Our Top 10:
| Rank | Ticker |
|------|--------|
| 1 | NELLY |
| 2 | SANION |
| 3 | LUG |
| 4 | NREST |
| 5 | BOL |
| 6 | SAAB B |
| 7 | RVRC |
| 8 | SVED B |
| 9 | BIOA B |
| 10 | HANZA |

### Observations:
- Top 4 match! (NELLY, SANION, LUG, NREST)
- Divergence starts at #5
- SANION has quality rank #1 but is #2 overall (NELLY has better momentum)

---

## 5. Root Cause Analysis

### Issue 1: F-Score Calculation
**Current implementation problems:**
1. Missing year-over-year data for proper comparison
2. Giving "benefit of doubt" points when data is missing
3. Not using the same data sources as Börslabbet

**Börslabbet likely uses:**
- Complete historical fundamentals from Börsdata
- Proper YoY comparisons for all 9 F-Score components
- No "benefit of doubt" - missing data = 0 points

### Issue 2: Trendande Percentile Logic
**Current implementation:**
```python
top_value = _filter_top_percentile(-value_score, 40)  # Top 40%
n_select = max(10, int(len(filtered_mom) * 0.25))     # Top 25%
```

**Problem:** We're taking top 25% of the filtered pool, but Börslabbet might be:
1. Taking exactly top 10 stocks by momentum from the filtered pool
2. Using a different percentile calculation

### Issue 3: Data Quality
- Dividend yield format (decimal vs percentage)
- Missing or stale fundamentals data
- Different data timing

---

## 6. Recommended Fixes

### Priority 1: F-Score Calculation (Critical)
```python
# Current: F-Score <= 3 filtered out
# Proposed: F-Score < 5 filtered out (matches Börslabbet's minimum of 5)

# Also need to:
# 1. Get proper YoY fundamentals data
# 2. Remove "benefit of doubt" logic
# 3. Validate against Börslabbet's published F-Scores
```

### Priority 2: Trendande Strategy Logic
```python
# Current: Top 40% by primary → Top 25% by momentum
# Proposed: Top 40% by primary → Sort by momentum → Take top 10

def calculate_value_score(fund_df, prices_df):
    # Step 1: Calculate value ranks
    # Step 2: Filter to top 40% by value
    # Step 3: Calculate momentum for filtered stocks
    # Step 4: Sort by momentum descending
    # Step 5: Return top 10 (not top 25%)
```

### Priority 3: Data Validation
1. Compare our fundamentals with Börslabbet's CSV values
2. Fix dividend yield format if needed
3. Ensure we have complete data for all stocks

---

## 7. Validation Checklist

After implementing fixes, validate against Börslabbet's CSV:

- [ ] Momentum: At least 8/10 stocks match
- [ ] F-Scores: Within ±1 of Börslabbet's values
- [ ] Trendande Värde: At least 7/10 stocks match
- [ ] Trendande Utdelning: At least 7/10 stocks match
- [ ] Trendande Kvalitet: At least 8/10 stocks match

---

## 8. Data Quality Issues Identified

### Dividend Yield Format ✓ CORRECT
Our data stores dividend yield as decimal (0.0357 = 3.57%), which is correct.
- SSAB B: 0.0357 = 3.57% (Börslabbet shows 3.8%)
- TELIA: 0.0504 = 5.04% (Börslabbet shows 5.1%)
- NCC B: 0.0408 = 4.08% (Börslabbet shows 5.0%)

Small differences are expected due to data timing.

### P/FCF Discrepancy 🔴 MAJOR ISSUE
| Stock | Our P/FCF | Börslabbet P/FCF |
|-------|-----------|------------------|
| SSAB B | 7.15 | 48.1 |

This is a 7x difference! Our P/FCF calculation may be inverted or using different data.

### EV/EBITDA Discrepancy 🔴 MAJOR ISSUE
| Stock | Our EV/EBITDA | Börslabbet EV/EBITDA |
|-------|---------------|----------------------|
| SSAB B | 10.52 | 5.8 |

Almost 2x difference. This significantly affects value rankings.

### ROE/ROA Format
Our data stores as decimal (0.0728 = 7.28%), Börslabbet shows as percentage.
Need to verify this is handled correctly in calculations.

---

## 9. Root Causes Summary

| Issue | Impact | Fix Complexity |
|-------|--------|----------------|
| F-Score calculation | High | Medium |
| P/FCF data quality | High | Low (data source) |
| EV/EBITDA data quality | High | Low (data source) |
| Trendande percentile logic | Medium | Low (code fix) |

---

## 10. Next Steps

### Immediate (Today)
1. **Fix F-Score cutoff** from ≤3 to <5 (or investigate exact Börslabbet threshold)
2. **Investigate P/FCF calculation** - may be inverted or using wrong data
3. **Investigate EV/EBITDA calculation** - significant discrepancy

### Short-term (This Week)
1. **Implement proper YoY F-Score calculation** with historical data
2. **Validate all 6 value metrics** against Börslabbet's CSV
3. **Fix Trendande strategy logic** to match "top 40% → sort by momentum → top 10"

### Medium-term
1. **Add data validation tests** comparing our values to Börslabbet's
2. **Consider Börsdata API** for data parity (they use same source)
3. **Implement automated comparison** with Börslabbet's published rankings

---

## 11. Quick Wins

### Fix 1: F-Score Threshold
```python
# In ranking.py, line ~250
# Current:
if not f_scores.empty:
    valid = f_scores[f_scores > 3].index  # F-Score > 3

# Change to:
if not f_scores.empty:
    valid = f_scores[f_scores >= 5].index  # F-Score >= 5 (matches Börslabbet)
```

### Fix 2: Trendande Strategy Logic
```python
# In calculate_value_score(), change:
n_select = max(10, int(len(filtered_mom) * 0.25))
top_n = filtered_mom.sort_values(ascending=False).head(n_select)

# To:
top_n = filtered_mom.sort_values(ascending=False).head(10)  # Always top 10
```

### Fix 3: Validate Data Source
Check if Avanza API returns P/FCF and EV/EBITDA correctly, or if we need to calculate them from raw data.

---

## 12. Avanza API Deep Dive - Root Cause Analysis

### What Avanza Provides (keyIndicators):
```
priceEarningsRatio    ✓ Direct
priceSalesRatio       ✓ Direct
priceBookRatio        ✓ Direct
evEbitRatio           ⚠️ This is EV/EBIT, NOT EV/EBITDA!
directYield           ✓ Direct (as decimal, e.g., 0.0357 = 3.57%)
returnOnEquity        ✓ Direct (as decimal)
returnOnTotalAssets   ✓ Direct (as decimal)
returnOnCapitalEmployed ✓ Direct (ROIC)
operatingCashFlow     ✓ Direct (but this is OCF, not FCF!)
marketCapital         ✓ Direct
```

### What Avanza Does NOT Provide:
- **EV/EBITDA** - Only provides EV/EBIT
- **Free Cash Flow (FCF)** - Only provides Operating Cash Flow
- **EBITDA** - Not available
- **CapEx** - Not available (needed to calculate FCF)
- **FCFROE** - Not available (we calculate it incorrectly)

### Our Calculation Errors:

#### 1. P/FCF Calculation (WRONG)
```python
# Current code (avanza_fetcher_v2.py line 207-209):
p_fcf = None
if market_cap and operating_cash_flow and operating_cash_flow > 0:
    p_fcf = market_cap / operating_cash_flow  # ❌ WRONG!
```

**Problem:** We use Operating Cash Flow, but P/FCF should use Free Cash Flow.
- FCF = Operating Cash Flow - Capital Expenditures
- Avanza doesn't provide CapEx, so we can't calculate true FCF

**Example (SSAB B):**
| Metric | Our Value | Börslabbet |
|--------|-----------|------------|
| Market Cap | 72.8B | 69.1B |
| Operating CF | 10.2B | N/A |
| Our P/OCF | 7.15 | - |
| True P/FCF | ? | 48.1 |
| Implied FCF | - | 1.44B |
| Implied CapEx | - | ~8.8B |

#### 2. EV/EBITDA (WRONG METRIC)
```python
# Current code (avanza_fetcher_v2.py line 253):
'ev_ebitda': key_indicators.get('evEbitRatio'),  # ❌ This is EV/EBIT!
```

**Problem:** Avanza provides `evEbitRatio` which is EV/EBIT, not EV/EBITDA.
- EBIT = Earnings Before Interest and Taxes
- EBITDA = EBIT + Depreciation + Amortization
- EV/EBITDA is always lower than EV/EBIT

**Example (SSAB B):**
| Metric | Our Value | Börslabbet |
|--------|-----------|------------|
| EV/EBIT (Avanza) | 10.52 | - |
| EV/EBITDA | ? | 5.8 |

#### 3. FCFROE Calculation (WRONG)
```python
# Current code (avanza_fetcher_v2.py line 216-219):
fcfroe = None
if operating_cash_flow and total_equity and total_equity > 0:
    fcfroe = operating_cash_flow / total_equity  # ❌ Should use FCF!
```

**Problem:** We use Operating CF instead of Free Cash Flow.

### Comparison Table: Avanza vs Börslabbet (SSAB B)

| Metric | Avanza Raw | Our Stored | Börslabbet | Match? |
|--------|------------|------------|------------|--------|
| P/E | 14.63 | 14.63 | 13.9 | ✓ Close |
| P/S | 0.74 | 0.74 | 0.7 | ✓ Close |
| P/B | 1.07 | 1.07 | 1.0 | ✓ Close |
| EV/EBIT | 10.52 | - | - | N/A |
| EV/EBITDA | N/A | 10.52 ❌ | 5.8 | ❌ WRONG |
| P/FCF | N/A | 7.15 ❌ | 48.1 | ❌ WRONG |
| Div Yield | 0.0357 | 0.0357 | 0.038 | ✓ Close |
| ROE | 0.0728 | 0.0728 | - | ✓ |
| ROA | 0.0474 | 0.0474 | - | ✓ |
| ROIC | 0.0754 | 0.0754 | - | ✓ |

### Options to Fix:

#### Option A: Use Börsdata API (Recommended)
Börslabbet uses Börsdata as their data source. Börsdata provides:
- True EV/EBITDA
- Free Cash Flow
- EBITDA
- CapEx
- All metrics Börslabbet uses

**Pros:** Perfect data parity with Börslabbet
**Cons:** Requires Börsdata subscription (~1000 SEK/year)

#### Option B: Estimate from Available Data
We could try to estimate the missing metrics:
- EV/EBITDA ≈ EV/EBIT * 0.6 (rough approximation)
- FCF ≈ Operating CF * 0.3 (very rough, varies by industry)

**Pros:** Free, uses existing data
**Cons:** Inaccurate, will never match Börslabbet exactly

#### Option C: Scrape Börsdata (Not Recommended)
Scrape the metrics from Börsdata's website.

**Pros:** Free
**Cons:** Against ToS, unreliable, could break

#### Option D: Accept Limitations
Document that our P/FCF and EV/EBITDA are approximations and may differ from Börslabbet.

**Pros:** Honest, no additional work
**Cons:** Rankings will differ from Börslabbet

### Recommendation

**Short-term:** Rename our metrics to be accurate:
- `ev_ebitda` → `ev_ebit` (what we actually have)
- `p_fcf` → `p_ocf` (Price/Operating Cash Flow)

**Medium-term:** Consider Börsdata API subscription for accurate data.

**Long-term:** If exact Börslabbet replication is critical, Börsdata API is the only reliable solution.
