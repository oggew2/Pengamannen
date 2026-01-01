# Börslabbet Strategy Implementation - Comprehensive Research

This document compiles research from multiple Börslabbet and Investerarfysikern sources to validate and document the strategy implementations.

## Sources Researched

### Börslabbet (börslabbet.se)
- `/sammansatt-momentum` - Momentum strategy details
- `/trendande-varde` - Value strategy details
- `/trendande-kvalitet` - Quality strategy details
- `/trendande-utdelning` - Dividend strategy details
- `/borslabbets-strategier` - Main study "Vad fungerar på Stockholmsbörsen?"
- `/vanliga-fragor` - FAQ with implementation details
- `/kom-igang` - Getting started guide
- `/backtest-av-borslabbets-svenska-portfolj` - Swedish portfolio backtest
- `/varfor-fungerar-varde-och-momentum` - Why value and momentum work

### Investerarfysikern (investerarfysikern.se)
- `/portfolj-och-utveckling` - Henning Hammar's personal portfolio
- `/investerarfysikerportfoljen-in-i-2026` - Latest portfolio update (Nov 2025)
- `/investera-systematiskt-och-sla-borsen` - Systematic investing overview

---

## Strategy Definitions

### 1. Sammansatt Momentum

**Formula:** Average of 3-month, 6-month, and 12-month price returns
```
Sammansatt Momentum = (return_3m + return_6m + return_12m) / 3
```

**Quality Filter:** Piotroski F-Score
- Remove stocks with lowest F-Score (≤3 out of 9)
- F-Score measures profitability, leverage, and operating efficiency
- Purpose: Avoid speculative momentum driven by hype rather than fundamentals

**Rebalancing:** 
- Quarterly (March, June, September, December) - 31.3% annual return in backtest
- Monthly with banding - 31.9% annual return (reduces turnover)
- Annual loses significant returns (24.8%)

**Source Quote:** "Sammansatt momentum är ett sammansatt mått på prisuppgång och mäter uppgången över de senaste 3-, 6- och 12-månaderna."

---

### 2. Trendande Värde

**Step 1 - Sammansatt Värde (6 factors):**
1. P/E (pris/vinst) - lower is better
2. P/B (pris/eget kapital) - lower is better
3. P/S (pris/försäljning) - lower is better
4. P/FCF (pris/fritt kassaflöde) - lower is better
5. EV/EBITDA - lower is better
6. Direktavkastning (dividend yield) - higher is better

**Step 2:** Sort by Sammansatt Momentum (3m, 6m, 12m average)

**Selection Process:**
- Filter to top 40% by primary factor (value)
- Select top quarter by momentum
- Results in ~top 10% of universe

**Rebalancing:** Annual (19.2% return in backtest)

**Inspiration:** "What Works on Wall Street" by James O'Shaughnessy

**Source Quote:** "Sammansatt värde är ett gemensamt mått utifrån de enskilda nyckeltalen P/E, P/B, P/S, P/FCF, EV/EBITDA samt direktavkastning."

---

### 3. Trendande Kvalitet

**Step 1 - Sammansatt ROI (4 factors):**
1. ROE (Return on Equity)
2. ROA (Return on Assets)
3. ROIC (Return on Invested Capital)
4. FCFROE (Free Cash Flow / Equity)

**Step 2:** Sort by Sammansatt Momentum

**Rebalancing:** Annual (23.9% return in backtest)

**Source Quote:** "Detta mått utgår från de enskilda nyckeltalen avkastning på eget kapital (ROE), avkastning på totalt kapital (ROA), avkastning på investerat kapital (ROIC) och fritt kassaflöde genom eget kapital (FCFROE)."

---

### 4. Trendande Utdelning

**Step 1:** Filter by highest Direktavkastning (dividend yield)

**Step 2:** Sort by Sammansatt Momentum

**Purpose:** Avoid "dividend traps" - stocks with high yield due to falling prices

**Rebalancing:** Annual (21.7% return in backtest)

**Source Quote:** "Efter att ha valt ut bolagen utifrån direktavkastning väljs de högst rankade aktierna efter sammansatt momentum."

---

## Universal Rules

### Market Cap Filter
- **Minimum:** 2 billion SEK (since June 2023)
- **Liquidity filter:** Top 40% of stocks by market cap
- **Source:** "bolag över 2 miljarder i börsvärde"

### Universe
- Stockholmsbörsen (Stockholm Stock Exchange)
- First North (growth market)
- **Excludes:** Financial companies (nyckeltal don't apply well)

### Portfolio Construction
- **Position count:** 10 stocks per strategy
- **Weighting:** Equal weight (likaviktat)
- **Overlap handling:** Double position for stocks appearing in multiple strategies

### Rebalancing Schedule
| Strategy | Frequency | Best Months |
|----------|-----------|-------------|
| Sammansatt Momentum | Quarterly | March, June, September, December |
| Trendande Värde | Annual | March |
| Trendande Kvalitet | Annual | March |
| Trendande Utdelning | Annual | March |

### Banding (Momentum only)
- Used to reduce turnover in monthly rebalancing
- Only sell if stock drops out of top 20%
- Buy from top 10%

---

## Historical Performance (Backtest 2001-2021)

| Strategy | Annual Return | Volatility | Sharpe | Max Drawdown |
|----------|--------------|------------|--------|--------------|
| Stockholmsbörsen (index) | 10.1% | 18.5% | 0.55 | -54% |
| Sammansatt Momentum | 31.3% | 24.7% | 1.18 | -50% |
| Trendande Kvalitet | 25.0% | 21.4% | 1.10 | -57% |
| Trendande Värde | 20.1% | 21.6% | 0.90 | -63% |
| Trendande Utdelning | 19.2% | 19.6% | 0.94 | -56% |
| **Combined (Svenska portföljen)** | **25.7%** | **20.8%** | **1.15** | **-54%** |

---

## Why These Strategies Work

### Value (from Börslabbet research)
- Market is too pessimistic about future earnings
- Stocks are cheap because expectations are too low
- Value stocks have negative EPS growth but multiple expansion
- P/E goes from ~10 at purchase to ~15 at sale

### Momentum (from Börslabbet research)
- Market underreacts to earnings growth
- Stocks with rising prices have strong EPS growth
- Better predictor of future growth than high P/E
- Works best over 3-12 month periods

### Combining Value and Momentum
- Low correlation between factors
- Value = pessimism play, Momentum = optimism play
- Different market conditions favor different factors
- Combining provides smoother returns

---

## Implementation Verification

### ✅ Correctly Implemented
- Sammansatt Momentum formula (avg 3m, 6m, 12m)
- Piotroski F-Score filter for momentum (removes F-Score ≤ 3)
- Sammansatt Värde (6 factors: P/E, P/B, P/S, P/FCF, EV/EBITDA, dividend yield)
- Sammansatt ROI (4 quality factors: ROE, ROA, ROIC, FCFROE)
- Market cap filter (2B SEK minimum)
- Top 10 stocks per strategy
- Equal weight portfolios
- **Trendande filtering**: Top 40% by primary factor → Top 25% by momentum (~10% final)
- **Financial exclusion**: Banks, investment companies, insurance excluded
- **Banding**: Momentum uses current holdings, only sells if stock drops out of top 20%

### Financial Sectors Excluded
- Traditionell Bankverksamhet (Traditional Banking)
- Investmentbolag (Investment Companies)
- Försäkring (Insurance)
- Sparande & Investering (Savings & Investment)
- Kapitalförvaltning (Asset Management)
- Konsumentkredit (Consumer Credit)

---

## About the Creator

**Henning Hammar** (Investerarfysikern)
- PhD in Physics, MSc in Engineering Physics
- Founded Börslabbet in 2017
- Personal portfolio: 50-55% quantitative strategies, 20-25% trend following, 15-20% gold, 5-10% bonds
- Achieved 17.2% CAGR since 2020 with Sharpe 1.18
- Uses all 4 Börslabbet strategies equally weighted

---

## References

1. https://borslabbet.se/sammansatt-momentum/
2. https://borslabbet.se/trendande-varde/
3. https://borslabbet.se/trendande-kvalitet/
4. https://borslabbet.se/trendande-utdelning/
5. https://borslabbet.se/borslabbets-strategier/
6. https://borslabbet.se/vanliga-fragor/
7. https://borslabbet.se/backtest-av-borslabbets-svenska-portfolj/
8. https://borslabbet.se/varfor-fungerar-varde-och-momentum/
9. https://investerarfysikern.se/portfolj-och-utveckling/
10. https://investerarfysikern.se/investerarfysikerportfoljen-in-i-2026/
11. https://investerarfysikern.se/investera-systematiskt-och-sla-borsen/

*Last updated: December 2025*
