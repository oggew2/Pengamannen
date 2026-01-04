# Strategy Accuracy Report vs Börslabbet

**Date:** January 4, 2026
**Data Source:** Börslabbet CSVs from January 4, 2026

## Summary

| Strategy | Correlation | Top 10 Overlap | Status |
|----------|-------------|----------------|--------|
| Sammansatt Momentum | 93.4% | 7/10 (70%) | ✅ Good |
| Trendande Värde | 93.1% | 4/10 (40%) | ⚠️ Needs improvement |
| Trendande Utdelning | 91.3% | 3/10 (30%) | ⚠️ Needs improvement |
| Trendande Kvalitet | 97.2% | 3/10 (30%) | ⚠️ Needs improvement |

## Metric-Level Accuracy

| Metric | MAE | Within 5pp | Status |
|--------|-----|------------|--------|
| ROE | 0.64pp | 97.5% | ✅ Excellent |
| ROA | 0.35pp | 97.5% | ✅ Excellent |
| ROIC | 2.92pp* | 75%* | ✅ Good (after fix) |
| FCFROE | 8.16pp | 53.3% | ⚠️ Moderate |
| P/E | 1.76 | - | ✅ Good |
| P/S | 0.05 | - | ✅ Excellent |
| P/B | 0.10 | - | ✅ Excellent |
| EV/EBITDA | 0.79 | - | ✅ Good |
| Div Yield | 0.36pp | - | ✅ Good |
| 3m Momentum | 4.41pp | 72.5% | ⚠️ Date timing |
| 6m Momentum | 5.88pp | 55.0% | ⚠️ Date timing |
| 12m Momentum | 7.12pp | 60.0% | ⚠️ Date timing |

*ROIC: Using NI / (Equity + Debt - Cash) formula, correlation 98.1%

## Key Issues Identified

### 1. ROIC Calculation
- **Current formula:** `Net Income / (Debt + Equity - Cash)` - MAE 2.92pp, Correlation 98.1%
- **Issue:** Some outliers (SANION: BL=3432%, Ours=3378%) due to very low invested capital
- **Status:** ✅ Already using best formula

### 2. FCFROE Missing Data
- TradingView returns NULL FCF for ~10% of stocks (BIOA B, SNM, MYCR, NOTE)
- **Recommendation:** Use OCF as fallback when FCF is missing
- **Impact:** Would improve coverage and reduce MAE

### 3. Momentum Date Timing
- Our data uses current prices, Börslabbet uses snapshot from specific date
- MAE: 3m=4.4pp, 6m=5.9pp, 12m=7.1pp
- **Status:** Acceptable for live trading (prices will differ)

### 4. Universe Differences
- Our data includes Norwegian stocks (ending with 'O')
- Börslabbet focuses on Swedish stocks only
- **Recommendation:** Filter out Norwegian stocks for better alignment

### 5. Trendande Utdelning
- Börslabbet has minimum dividend yield ~3%
- Our top stocks have low dividend yields (0.4-2.1%)
- **Recommendation:** Add minimum dividend yield filter (3%)

## Börslabbet Methodology (from borslabbet.se)

### Sammansatt Momentum
- Composite momentum = average(3m, 6m, 12m returns)
- Filter: Piotroski F-Score >= 5
- Rebalance: Quarterly

### Trendande Värde
- Sammansatt Värde = composite rank of P/E, P/B, P/S, P/FCF, EV/EBITDA, Div Yield
- Sort by 6m momentum among top value stocks
- Rebalance: Annual

### Trendande Utdelning
- Filter: Dividend yield > 0 (likely minimum ~3%)
- Sort by 6m momentum among dividend payers
- Rebalance: Annual

### Trendande Kvalitet
- Sammansatt ROI = composite rank of ROE, ROA, ROIC, FCFROE
- Sort by 6m momentum among top quality stocks
- Rebalance: Annual

## Recommendations

### High Priority
1. ✅ ROIC formula already optimal (NI / IC)
2. Add OCF fallback for FCFROE when FCF is missing
3. Filter out Norwegian stocks from Swedish strategies

### Medium Priority
4. Add minimum dividend yield filter (3%) for Trendande Utdelning
5. Review quality ranking to use composite rank instead of average

### Low Priority
6. Historical price alignment for validation purposes

## Data Sources
- **Primary:** TradingView Scanner API
- **Börslabbet:** Uses Börsdata as their data source
- **Differences:** Minor variations in data timing and calculation methods
