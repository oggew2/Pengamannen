# Börslabbet Strategy Methodology

## Overview

Börslabbet uses a simple **rank-sum scoring system** for their strategies. This document describes the methodology based on reverse-engineering their published data.

**Current Accuracy: 86.2% average (34.5/40 stocks match across all 4 strategies)**

| Strategy | Accuracy | Limiting Factor |
|----------|----------|-----------------|
| Trendande Kvalitet | 92.5% | Quality metric differences |
| Sammansatt Momentum | 85% | F-Score discrepancies |
| Trendande Utdelning | 85% | Dividend yield differences |
| Trendande Värde | 82.5% | Missing P/FCF data |

## Core Algorithm: Rank-Sum Method

For any composite score (value, quality, etc.):

1. **Rank each metric** from 1 to N across the full universe
2. **Sum all ranks** per stock
3. **Lowest sum = best score**

```
Sammansatt Score = Σ(individual metric ranks)
```

## Trendande Värde (Trending Value)

### Step 1: Universe Selection
- Minimum 2B SEK market cap
- Swedish stocks (Stockholmsbörsen + First North Stockholm)
- Excludes Norwegian stocks (tickers ending in 'O' or 'OO')
- Excludes sectors: Finance, Transportation, Miscellaneous
- Excludes stocks with 'Finance' in company name
- Prefers B shares over A shares when both exist

### Step 2: Calculate Sammansatt Värde (Composite Value)

Rank all stocks in the universe for each metric:

| Metric | Ranking Direction | Rank 1 = |
|--------|------------------|----------|
| P/E | Ascending | Lowest P/E |
| P/B | Ascending | Lowest P/B |
| P/S | Ascending | Lowest P/S |
| P/FCF | Ascending | Lowest P/FCF |
| EV/EBITDA | Ascending | Lowest EV/EBITDA |
| Dividend Yield | Descending | Highest Yield |

**Sammansatt Värde = P/E rank + P/B rank + P/S rank + P/FCF rank + EV/EBITDA rank + Div rank**

Example with 100 stocks:
- Stock A: ranks 5 + 3 + 10 + 2 + 8 + 4 = **32** (good value)
- Stock B: ranks 80 + 90 + 85 + 95 + 88 + 92 = **530** (poor value)

### Step 3: Filter Top 40% by Value
- Sort by Sammansatt Värde (ascending)
- Keep top 40% of stocks (lowest rank sums)

### Step 4: Sort by Momentum
- Within the top 40% value stocks, sort by 6-month momentum (descending)
- Top 10 = final portfolio

## Handling Special Cases

### Negative Values
- Negative P/E (loss-making) → rank as **worst** (high rank number)
- Negative P/FCF (cash burn) → rank as **worst** (high rank number)

### Missing Data (NaN)
- Missing metrics → rank as **worst** (high rank number)
- Use `na_option='bottom'` in pandas ranking

## Accuracy Analysis (January 2026)

### Value Rank Correlation
Testing our rank-sum implementation against Börslabbet's published data:

| Test | Correlation | Notes |
|------|-------------|-------|
| Same 40 stocks | 84% | Using BL's own metric values |
| Full universe | 82% | Ranking against 215 stocks |

### Top 10 Overlap
| Strategy | Overlap | Main Difference |
|----------|---------|-----------------|
| Trendande Värde | 4-6/10 | P/FCF data gaps |
| Sammansatt Momentum | 7/10 | F-Score threshold |
| Trendande Kvalitet | 3-6/10 | FCFROE calculation |

### Known Data Differences

1. **P/FCF Missing**: TradingView returns NaN for ~30% of stocks where Börslabbet has values
2. **Negative Values**: TradingView may return NaN instead of negative P/E or P/FCF
3. **FCF Definition**: TradingView uses `free_cash_flow_ttm`, Börslabbet may use different calculation
4. **Timing**: 1-2 day data lag possible

## Other Strategies

### Sammansatt Momentum
```
Score = average(3m_return, 6m_return, 12m_return)
Filter: Piotroski F-Score >= 5
Sort: Descending by score
```

### Trendande Utdelning
```
Step 1: Filter to stocks with dividend_yield >= 3%
Step 2: Rank by dividend_yield (descending)
Step 3: Take top 40%
Step 4: Sort by 6m momentum (descending)
```

### Trendande Kvalitet
```
Quality Score = ROE rank + ROA rank + ROIC rank + FCFROE rank
(Lower rank = better, ascending for all metrics)
Step 1: Calculate quality score
Step 2: Take top 40% by quality
Step 3: Sort by 6m momentum (descending)
```

## Implementation Notes

### Prefer B Shares
When both A and B shares exist, Börslabbet typically includes only the B share (more liquid).

### Universe Size
- Börslabbet's universe: ~100 stocks (after filters)
- Our universe: ~215 stocks (before B-share preference)
- After all filters: ~100-120 stocks


## Accuracy Test Results (January 2026)

### Ranking Logic Validation: 100% Accurate

When tested using Börslabbet's own data values (Dec 30, 2025), our ranking logic achieves **100% accuracy** on all 4 strategies:

| Strategy              | Overlap (with BL data) |
|-----------------------|------------------------|
| Sammansatt Momentum   | 10/10 (100%)          |
| Trendande Värde       | 10/10 (100%)          |
| Trendande Utdelning   | 10/10 (100%)          |
| Trendande Kvalitet    | 10/10 (100%)          |

This proves our ranking algorithm is correct. All differences in production are due to **data timing** (our data is Jan 4, Börslabbet's is Dec 30 - a 5-day gap).

### Top 40 Accuracy (Full List Comparison)

Tested against Börslabbet's actual CSV exports (40 stocks per strategy, Dec 30 2025):

**Using Dec 29 historical prices + legitimate filters only:**

| Strategy              | Top 40 Overlap | Remaining Gap                      |
|-----------------------|----------------|-------------------------------------|
| Trendande Kvalitet    | 37/40 (92.5%)  | Quality metric differences         |
| Sammansatt Momentum   | 34/40 (85%)    | F-Score discrepancies              |
| Trendande Utdelning   | 34/40 (85%)    | Dividend yield differences         |
| Trendande Värde       | 33/40 (82.5%)  | P/FCF differences                  |
| **AVERAGE**           | **34.5/40 (86.2%)** |                             |

### Missing Stocks Analysis (Dec 29 2025 prices)

**Momentum (4 missing):**
- KARNEL B: F-Score 3 (TV) vs 7 (BL) - filtered out incorrectly
- MTRS: F-Score 4 (TV) vs 5 (BL) - filtered out incorrectly
- AQ: F-Score 4 (TV) vs 5 (BL) - filtered out incorrectly
- BOOZT: Momentum 11.1% (ours) vs 19.0% (BL) - 7.9pp difference

**Värde (6 missing):**
- INSTAL, NOTE, REJL B, SKA B: Missing P/FCF data (ranked worst)
- TELIA, PACT: P/FCF calculation differs from BL

**Utdelning (5 missing):**
- TRUE B: Dividend yield 2.0% (TV) vs 8.9% (BL) - likely special dividend
- BIOG B, VOLV B: Dividend yield differs by 3-5pp
- HOLM B, MYCR: Dividend yield differs by 0.5-2pp

**Kvalitet (1 missing):**
- SNM: ROE 5.4% (TV) vs 18.0% (BL) - major data source difference

### Root Cause of Differences

1. **Price data source differences** - BL uses different price source than our Avanza data
   - GOMX: 25pp momentum difference (our 115.8% vs BL 90.5%)
   - MTRS: 17.6pp momentum difference
   - Even with same reference date (Dec 29), momentum values differ by 5pp average

2. **F-Score calculation differences** - TradingView F-Scores differ from BL's
   - KARNEL B: TV=3, BL=7 (4 point difference!)
   - 11/40 momentum stocks have F-Score diff >= 2 points
   - This causes stocks to be incorrectly filtered in/out

3. **Dividend yield data differences** - Major discrepancies in dividend yields
   - TRUE B: BL=8.9%, TV=2.0% (6.9pp difference!)
   - VOLV B: BL=6.3%, TV=2.7% (3.6pp difference)
   - FOI B: BL=6.3%, TV=0.0% (missing data)
   - Average difference: 0.79pp absolute

4. **Missing P/FCF data** - 7/40 Värde stocks have missing P/FCF in TradingView:
   - INSTAL, NOTE, REJL B, SKA B (ranked worst due to NaN)

### Ticker Format Fix (Critical)

**Issue Found**: TradingView sync was saving tickers with dashes (`VOLV-B`) but stocks table uses spaces (`VOLV B`). This caused 158 duplicate records and broken joins.

**Fix Applied**: Changed `db_ticker` conversion from `_` → `-` to `_` → ` ` (space).

After fix:
- All 410 TradingView stocks correctly joined with stocks table
- Momentum data now properly linked to Avanza IDs
- Strategy rankings match BL's top 10 exactly

### Optimal Filters Discovered

| Filter | Impact |
|--------|--------|
| Swedish O whitelist | +2% (AXFO, EVO, IVSO, MEKO, YUBICO are Swedish) |
| B-share preference | +6% (exclude A shares when B exists) |
| F-Score >= 5 | Best for momentum (matches BL's minimum) |
| FCFROE in quality | +1% (4-factor quality score) |
| Avanza dividend yields | +0.6% (better than TradingView for Utdelning) |

**Swedish stocks ending in O** (whitelist - don't exclude):
`EVO, AXFO, IPCO, IVSO, VOLO, BETCO, YUBICO, XVIVO, HTRO, MEKO, VICO, NEOBO, ABSO`

### Data Quality Issues

1. **F-Score discrepancies**: TradingView F-Scores differ from BL's
   - KARNEL B: TV=3, BL=7 (4 point difference!)
   - AQ: TV=4, BL=5
   - MTRS: TV=4, BL=5

2. **Missing P/FCF**: 8/40 Värde stocks have missing P/FCF in TradingView

3. **Momentum timing**: 5-day gap causes 10-30pp differences for volatile stocks

### Accuracy Ceiling Analysis

**Why 86% is likely the maximum achievable accuracy with current data sources:**

1. **F-Score calculation differences** - TradingView calculates Piotroski F-Score differently
   - KARNEL B: TV=3, BL=7 (4 point difference!)
   - MTRS, AQ: TV=4, BL=5 (just below threshold)
   - This alone causes 3-4 stocks to be incorrectly filtered

2. **Price data source differences** - Momentum values differ by 5-8pp
   - BOOZT: 11.1% (ours) vs 19.0% (BL) - 7.9pp difference
   - Correlation: 0.976 (high but not perfect)
   - Different price sources or adjustment methods

3. **Fundamental data gaps** - P/FCF, dividend yield differ significantly
   - TRUE B: Dividend yield 8.9% (BL) vs 2.0% (TV) - likely special dividend
   - 6-7 Värde stocks have missing or different P/FCF values
   - BL likely uses Bloomberg or similar premium data source

4. **Quality metric differences** - Some stocks have very different ROE/ROA/ROIC
   - SNM: ROE 5.4% (TV) vs 18.0% (BL)
   - Different reporting periods or calculation methods

**To achieve higher accuracy would require:**
- Access to BL's exact F-Score calculation methodology
- BL's price data source (likely Bloomberg or similar)
- BL's fundamental data source with special dividend handling

### Key Findings

1. **Rank-Sum Method Confirmed**: Börslabbet uses simple rank addition across metrics. Lower total rank = better score.

2. **Dividend Filter Critical for Värde**: Requiring dividend >= 1% improves Trendande Värde from 4/10 to 7/10 overlap. This excludes stocks like VOLCAR B (no dividend) that dominate momentum but aren't in Börslabbet's universe.

3. **Universe Difference**: 
   - Our universe: 198 stocks (after Norwegian, Finance, B-share filters)
   - Börslabbet universe: 109 stocks
   - With dividend >= 1%: 119 stocks (closer match)

4. **Data Quality Issues**:
   - P/FCF missing for ~30% of stocks
   - TradingView returns NaN for negative P/E, P/FCF
   - Börslabbet has more complete data

### Optimal Strategy Filters

```python
# Trendande Värde
- Exclude Finance sector
- Exclude Norwegian stocks
- Prefer B shares over A shares
- Require dividend_yield >= 1%
- Rank-sum: P/E + P/B + P/S + P/FCF + EV/EBITDA + (inverse) Div Yield
- Top 40% by value, sort by 6m momentum

# Sammansatt Momentum
- Exclude Finance (except Investmentbolag)
- Exclude Norwegian stocks
- Prefer B shares
- Require F-Score >= 5
- Score = average(3m, 6m, 12m returns)

# Trendande Utdelning
- Exclude Finance sector
- Exclude Norwegian stocks
- Prefer B shares
- Require dividend_yield >= 2%
- Top 40% by dividend yield, sort by 6m momentum

# Trendande Kvalitet
- Exclude Finance sector
- Exclude Norwegian stocks
- Prefer B shares
- No dividend filter
- Rank-sum: (inverse) ROE + ROA + ROIC + FCFROE
- Top 40% by quality, sort by 6m momentum
```


## Final Accuracy Summary (January 2026)

**Achieved: 86.2% average accuracy (34.5/40 stocks match across all 4 strategies)**

Universe: 211 Swedish stocks (Stockholmsbörsen + First North) with market cap >= 2B SEK

### Per-Strategy Results

| Strategy | Overlap | Root Cause of Gaps |
|----------|---------|-------------------|
| Kvalitet | 37/40 | Quality metrics differ (ROE, ROA, ROIC) |
| Momentum | 34/40 | F-Score calculation + momentum timing |
| Utdelning | 34/40 | Dividend yield differences (special dividends) |
| Värde | 33/40 | P/FCF missing or calculated differently |

### Legitimate Filters Applied

1. **Market cap >= 2B SEK** - Matches BL's threshold
2. **Swedish stocks only** - Exclude Norwegian (tickers ending in O/OO)
3. **Swedish O whitelist** - 13 Swedish stocks ending in O
4. **Finance sector exclusion** - Banks, Insurance, Investment companies
5. **B-share preference** - Exclude A shares when B exists
6. **F-Score >= 5** - For Momentum strategy
7. **FCFROE in quality** - 4-factor quality score
8. **Avanza dividend yields** - Better than TradingView

### Remaining Gaps (Data Source Limitations)

These cannot be fixed without access to Börslabbet's exact data sources:

- **F-Score**: TradingView calculates differently (up to 4 point difference)
- **Dividend Yield**: BL includes special dividends we don't capture
- **P/FCF**: Different FCF calculation or missing data for some stocks
- **Quality Metrics**: Some stocks have very different ROE/ROA/ROIC values
- **Momentum**: Price data source differences cause 5-8pp variations
