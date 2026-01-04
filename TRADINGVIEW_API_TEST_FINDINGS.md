# TradingView API - Comprehensive Test Findings

**Test Date:** 2026-01-04  
**Tested Against:** Swedish non-financial stocks with market cap > 2B SEK (300 stocks)  
**Total Valid Fields Discovered:** 172+ fields

---

## Executive Summary

Testing the TradingView Scanner API revealed **significantly more data** than documented in the migration report. 

### 🎯 HIGH-VALUE NEW FIELDS FOR BÖRSLABBET (80%+ Coverage)

These fields are **NOT in the migration report** but have excellent coverage and could enhance your strategies:

| Field | Coverage | Use Case |
|-------|----------|----------|
| `Recommend.All` | 99.7% | Pre-calculated technical buy/sell signal (-1 to +1) |
| `relative_volume_10d_calc` | 99.7% | Spot unusual trading activity |
| `net_debt_fq` | 99.7% | Better leverage metric than total_debt |
| `Volatility.D/W/M` | 100% | Risk-adjusted returns, position sizing |
| `beta_1_year` | 100% | Market sensitivity |
| `price_52_week_high/low` | 100% | Distance from highs (momentum confirmation) |
| `earnings_per_share_forecast_next_fy` | 96.0% | Forward P/E calculation |
| `revenue_forecast_next_fy` | 96.3% | Forward P/S calculation |
| `revenue_surprise_percent_fq` | 92.3% | Earnings quality signal |
| `gross_margin_ttm` | 96.0% | Quality indicator |
| `operating_margin_ttm` | 96.7% | Quality indicator |
| `net_margin_ttm` | 96.7% | Quality indicator |
| `working_capital_fq` | 100% | Liquidity analysis |
| `asset_turnover_fy` | 100% | Efficiency metric |
| `current_ratio_fq` | 100% | Liquidity (F-Score component) |
| `quick_ratio_fq` | 98.3% | Liquidity |
| `debt_to_equity_fq` | 98.7% | Leverage |
| `gross_profit_yoy_growth_ttm` | 92.7% | F-Score component |
| `revenue_per_employee` | 89.0% | Efficiency proxy |

---

## 🚀 Recommended Additions for Your Strategies

### 1. Sammansatt Momentum - Add These

| Field | Why | Implementation |
|-------|-----|----------------|
| `Recommend.All` | Confirm momentum with technicals | Filter: `Recommend.All > 0` |
| `relative_volume_10d_calc` | Spot breakouts | Filter: `> 1.5` for unusual volume |
| `Volatility.M` | Risk-adjusted momentum | `momentum / Volatility.M` |

### 2. Trendande Värde - Add These

| Field | Why | Implementation |
|-------|-----|----------------|
| `earnings_per_share_forecast_next_fy` | Forward P/E | `close / eps_forecast` |
| `net_debt_fq` | Better EV calculation | `EV = market_cap + net_debt` |
| `enterprise_value_to_revenue_ttm` | Alternative to P/S | Direct from API |

### 3. Trendande Kvalitet - Add These

| Field | Why | Implementation |
|-------|-----|----------------|
| `gross_margin_ttm` | Margin quality | Already have, but direct now |
| `operating_margin_ttm` | Operating efficiency | Rank descending |
| `net_margin_ttm` | Net profitability | Rank descending |
| `asset_turnover_fy` | Capital efficiency | F-Score component |
| `revenue_per_employee` | Productivity | Rank descending |

### 4. Trendande Utdelning - Add These

| Field | Why | Implementation |
|-------|-----|----------------|
| `dividend_payout_ratio_ttm` | Sustainability check | Filter: `< 80%` |
| `dps_common_stock_prim_issue_yoy_growth_fy` | Dividend growth | 67% coverage, use as bonus |

### 5. F-Score Calculation - Direct Fields Available!

| F-Score Component | TradingView Field | Coverage |
|-------------------|-------------------|----------|
| ROA > 0 | `return_on_assets` | 97.7% |
| OCF > 0 | `cash_f_operating_activities_ttm` | 100% |
| ROA improving | `net_income_yoy_growth_ttm` | 90.7% |
| Current ratio improving | `current_ratio_fq` | 100% |
| Gross margin improving | `gross_profit_yoy_growth_ttm` | 92.7% |
| Asset turnover | `asset_turnover_fy` | 100% |
| Debt ratio | `debt_to_equity_fq` | 98.7% |

**Or just use:** `piotroski_f_score_ttm` (91%) / `piotroski_f_score_fy` (96%)

---

## 🆕 NEW HIGH-VALUE FIELDS (Not in Migration Report)

### 1. Analyst Estimates (Forward-Looking Data!)

| Field | Description | Sample Value |
|-------|-------------|--------------|
| `earnings_per_share_forecast_next_fq` | EPS estimate next quarter | 19.55 |
| `earnings_per_share_forecast_next_fy` | EPS estimate next fiscal year | 84.81 |
| `revenue_forecast_next_fq` | Revenue estimate next quarter | 142.5B |
| `revenue_forecast_next_fy` | Revenue estimate next fiscal year | 540.9B |
| `revenue_surprise_percent_fq` | Revenue surprise % last quarter | 2.79% |
| `earnings_release_trading_date_fq` | Next earnings date (timestamp) | 1762387200 |

**Use Case:** Forward P/E calculation, earnings calendar, surprise analysis

### 2. Technical Recommendations (Pre-Calculated!)

| Field | Description | Range |
|-------|-------------|-------|
| `Recommend.All` | Overall recommendation | -1 (sell) to +1 (buy) |
| `Recommend.MA` | Moving average recommendation | -1 to +1 |
| `Recommend.Other` | Oscillator recommendation | -1 to +1 |

**Use Case:** Quick technical screening, momentum confirmation

### 3. Extended Performance Metrics

| Field | Description | Sample |
|-------|-------------|--------|
| `Perf.W` | 1-week performance | -0.29% |
| `Perf.YTD` | Year-to-date performance | -0.56% |
| `Perf.5Y` | 5-year performance | 102.39% |
| `Perf.All` | All-time performance | 379.89% |

### 4. Volatility & Beta (Extended)

| Field | Description | Sample |
|-------|-------------|--------|
| `Volatility.D` | Daily volatility | 1.89% |
| `Volatility.W` | Weekly volatility | 1.43% |
| `Volatility.M` | Monthly volatility | 1.17% |
| `beta_1_year` | 1-year beta | 0.86 |
| `beta_3_year` | 3-year beta | 1.03 |
| `beta_5_year` | 5-year beta | 0.85 |

### 5. Volume Analysis

| Field | Description | Sample |
|-------|-------------|--------|
| `average_volume_10d_calc` | 10-day avg volume | 226,744 |
| `average_volume_30d_calc` | 30-day avg volume | 275,353 |
| `average_volume_60d_calc` | 60-day avg volume | 270,910 |
| `average_volume_90d_calc` | 90-day avg volume | 283,587 |
| `relative_volume_10d_calc` | Relative volume (vs 10d avg) | 0.97 |

### 6. Additional Balance Sheet

| Field | Description | Sample |
|-------|-------------|--------|
| `net_debt_fq` | Net debt | 230.5B |
| `working_capital_fq` | Working capital | -38.8B |
| `short_term_debt_fq` | Short-term debt | 61.8B |
| `cash_n_short_term_invest_fq` | Cash + short-term investments | 77.1B |
| `total_current_assets_fq` | Current assets | 282.3B |
| `total_current_liabilities_fq` | Current liabilities | 321.1B |
| `goodwill_fq` | Goodwill | 200.1B |

### 7. Additional Income Statement

| Field | Description | Sample |
|-------|-------------|--------|
| `ebit_ttm` | EBIT (TTM) | 123.4B |
| `operating_margin_ttm` | Operating margin | 21.84% |
| `net_margin_ttm` | Net margin | 16.18% |
| `pre_tax_margin_ttm` | Pre-tax margin | 19.68% |
| `revenue_per_employee` | Revenue per employee | 6.24M |

### 8. Additional Growth Metrics

| Field | Description | Sample |
|-------|-------------|--------|
| `free_cash_flow_yoy_growth_ttm` | FCF YoY growth (TTM) | 17.46% |
| `free_cash_flow_yoy_growth_fy` | FCF YoY growth (FY) | 16.26% |
| `ebitda_yoy_growth_ttm` | EBITDA YoY growth | 10.13% |
| `dps_common_stock_prim_issue_yoy_growth_fy` | Dividend growth YoY | 16.20% |

---

## 📊 Technical Indicators (Multi-Timeframe!)

### RSI (Relative Strength Index)

| Field | Timeframe | Sample |
|-------|-----------|--------|
| `RSI` | Daily | 51.89 |
| `RSI\|5` | 5-minute | 37.08 |
| `RSI\|15` | 15-minute | 32.08 |
| `RSI\|60` | 1-hour | 40.26 |
| `RSI\|240` | 4-hour | 47.77 |

### MACD

| Field | Description | Sample |
|-------|-------------|--------|
| `MACD.macd` | MACD line | 6.13 |
| `MACD.signal` | Signal line | 8.66 |
| `MACD.hist` | Histogram | -2.53 |
| `MACD.macd\|5` | MACD (5-min) | -2.01 |
| `MACD.signal\|5` | Signal (5-min) | -2.08 |

### Stochastic

| Field | Description | Sample |
|-------|-------------|--------|
| `Stoch.K` | %K | 62.95 |
| `Stoch.D` | %D | 62.80 |
| `Stoch.RSI.K` | Stoch RSI %K | 83.65 |
| `Stoch.RSI.D` | Stoch RSI %D | 81.76 |

### Other Indicators

| Field | Description | Sample |
|-------|-------------|--------|
| `ADX` | Average Directional Index | 21.76 |
| `ADX+DI` | +DI | 25.55 |
| `ADX-DI` | -DI | 14.82 |
| `CCI20` | Commodity Channel Index | 40.52 |
| `AO` | Awesome Oscillator | 17.00 |
| `Mom` | Momentum | 2.50 |
| `ATR` | Average True Range | 30.77 |
| `ROC` | Rate of Change | 0.15% |
| `HullMA9` | Hull Moving Average (9) | 1703.04 |
| `VWMA` | Volume Weighted MA | 1694.09 |

### Bollinger Bands

| Field | Description | Sample |
|-------|-------------|--------|
| `BB.upper` | Upper band | 1744.70 |
| `BB.lower` | Lower band | 1643.25 |
| `BB.basis` | Middle band | 1693.97 |

### Keltner Channels

| Field | Description | Sample |
|-------|-------------|--------|
| `KltChnl.upper` | Upper channel | 1744.70 |
| `KltChnl.lower` | Lower channel | 1643.25 |
| `KltChnl.basis` | Middle channel | 1693.97 |

### Ichimoku Cloud

| Field | Description | Sample |
|-------|-------------|--------|
| `Ichimoku.BLine` | Base Line | 1706.25 |
| `Ichimoku.CLine` | Conversion Line | 1698.00 |
| `Ichimoku.Lead1` | Leading Span A | 1702.13 |
| `Ichimoku.Lead2` | Leading Span B | 1706.25 |

---

## 📈 Moving Averages

| Field | Period | Sample |
|-------|--------|--------|
| `SMA5` | 5-day | 1698.00 |
| `SMA10` | 10-day | 1693.80 |
| `SMA20` | 20-day | 1695.40 |
| `SMA50` | 50-day | 1662.11 |
| `SMA100` | 100-day | 1588.77 |
| `SMA200` | 200-day | 1485.80 |
| `EMA5` | 5-day EMA | 1697.24 |
| `EMA10` | 10-day EMA | 1695.92 |
| `EMA20` | 20-day EMA | 1693.97 |
| `EMA50` | 50-day EMA | 1660.74 |
| `EMA100` | 100-day EMA | 1602.64 |
| `EMA200` | 200-day EMA | 1549.55 |

---

## 🎯 Pivot Points

### Classic Pivots

| Field | Description | Sample |
|-------|-------------|--------|
| `Pivot.M.Classic.R1` | Resistance 1 | 1755.17 |
| `Pivot.M.Classic.S1` | Support 1 | 1655.17 |
| `Pivot.M.Classic.Middle` | Pivot Point | 1706.83 |

### Fibonacci Pivots

| Field | Description | Sample |
|-------|-------------|--------|
| `Pivot.M.Fibonacci.R1` | Fib Resistance 1 | 1745.03 |
| `Pivot.M.Fibonacci.S1` | Fib Support 1 | 1668.63 |

### Other Pivot Types

- `Pivot.M.Camarilla.R1/S1` - Camarilla pivots
- `Pivot.M.Woodie.R1/S1` - Woodie pivots
- `Pivot.M.Demark.R1/S1` - Demark pivots

---

## 🕯️ Candlestick Patterns

| Field | Pattern | Value |
|-------|---------|-------|
| `Candle.Doji` | Doji | 0/1 |
| `Candle.Hammer` | Hammer | 0/1 |
| `Candle.MorningStar` | Morning Star | 0/1 |
| `Candle.3WhiteSoldiers` | Three White Soldiers | 0/1 |
| `Candle.3BlackCrows` | Three Black Crows | 0/1 |

**Note:** Returns 0 (not present) or 1 (pattern detected)

---

## 📅 52-Week & All-Time

| Field | Description | Sample |
|-------|-------------|--------|
| `price_52_week_high` | 52-week high | 1786.50 |
| `price_52_week_low` | 52-week low | 1226.00 |
| `High.All` | All-time high | 1799.00 |
| `Low.All` | All-time low | 210.50 |

---

## 🚀 Recommendations for Your App

### High Priority (Implement First)

1. **Analyst Estimates** - Add forward P/E calculation:
   ```python
   forward_pe = close / earnings_per_share_forecast_next_fy
   ```

2. **Technical Recommendations** - Quick screening filter:
   ```python
   # Filter for stocks with bullish technicals
   where(col('Recommend.All') > 0.3)
   ```

3. **Relative Volume** - Identify unusual activity:
   ```python
   # Stocks with 2x normal volume
   where(col('relative_volume_10d_calc') > 2.0)
   ```

4. **Net Debt** - Better leverage analysis:
   ```python
   net_debt_to_ebitda = net_debt_fq / ebitda_ttm
   ```

### Medium Priority

5. **Volatility Metrics** - Risk-adjusted returns:
   ```python
   sharpe_proxy = Perf.Y / (Volatility.M * 12)
   ```

6. **Working Capital** - Liquidity analysis:
   ```python
   working_capital_ratio = working_capital_fq / total_revenue_ttm
   ```

7. **Earnings Calendar** - Track upcoming events:
   ```python
   days_to_earnings = (earnings_release_trading_date_fq - now) / 86400
   ```

### Lower Priority (Nice to Have)

8. **Candlestick Patterns** - Technical signals
9. **Pivot Points** - Support/resistance levels
10. **Multi-timeframe RSI** - Divergence detection

---

## ❌ Fields NOT Available

The following fields were tested but returned no data for Swedish stocks:

- `altman_z_score` - Bankruptcy prediction
- `beneish_m_score` - Earnings manipulation detection
- `quality_score` - Overall quality score
- `number_of_analysts` - Analyst coverage count
- `price_target` - Analyst price target
- `insider_ownership` - Insider ownership %
- `institutional_ownership` - Institutional ownership %
- `short_interest` - Short interest
- `ex_dividend_date` - Ex-dividend date
- `inventory_turnover_ttm` - Inventory turnover
- `receivables_turnover_ttm` - Receivables turnover

---

## API Usage Notes

### Timeframe Suffixes

| Suffix | Timeframe |
|--------|-----------|
| (none) | Daily |
| `\|1` | 1-minute |
| `\|5` | 5-minute |
| `\|15` | 15-minute |
| `\|60` | 1-hour |
| `\|240` | 4-hour |
| `\|1W` | Weekly |
| `\|1M` | Monthly |

### Period Suffixes

| Suffix | Period |
|--------|--------|
| `_ttm` | Trailing Twelve Months |
| `_fq` | Fiscal Quarter (most recent) |
| `_fy` | Fiscal Year (most recent) |

### Example Query

```python
payload = {
    "filter": [
        {"left": "market_cap_basic", "operation": "greater", "right": 2_000_000_000},
        {"left": "sector", "operation": "not_in_range", "right": ["Finance"]},
        {"left": "Recommend.All", "operation": "greater", "right": 0}
    ],
    "markets": ["sweden"],
    "symbols": {"query": {"types": ["stock", "dr"]}},
    "columns": [
        "name", "close", "market_cap_basic",
        "earnings_per_share_forecast_next_fy",
        "Recommend.All", "relative_volume_10d_calc",
        "net_debt_fq", "Volatility.M"
    ],
    "sort": {"sortBy": "Recommend.All", "sortOrder": "desc"},
    "range": [0, 50]
}
```

---

## Summary

| Category | Fields in Report | NEW Fields Found |
|----------|------------------|------------------|
| Basic/Metadata | 13 | +5 |
| Performance | 4 | +4 |
| Technical Indicators | 0 | +43 |
| Moving Averages | 0 | +12 |
| Recommendations | 0 | +3 |
| Volatility/Beta | 1 | +5 |
| Volume | 0 | +6 |
| Value Ratios | 6 | +1 |
| Profitability | 4 | +6 |
| F-Score | 2 | 0 |
| Dividend | 1 | +4 |
| Income Statement | 6 | +8 |
| Balance Sheet | 6 | +8 |
| Cash Flow | 4 | +4 |
| Ratios | 3 | +1 |
| Per Share | 0 | +6 |
| Growth YoY | 5 | +6 |
| Analyst Estimates | 0 | +6 |
| Pivot Points | 0 | +11 |
| Candlestick | 0 | +5 |
| 52-Week | 0 | +4 |
| **TOTAL** | **~39** | **+124** |

**Bottom Line:** TradingView provides ~3x more useful data than documented in the migration report!
