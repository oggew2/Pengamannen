# Börslabbet V2 Roadmap Analysis

## Executive Summary

This document analyzes the proposed V2 features against:
1. What we already have implemented
2. Technical feasibility
3. Business value
4. Regulatory considerations
5. Recommendations

---

## TIER 1: Critical Path Analysis

### 1. Broker Integration API ⚠️ HIGH RISK

**Current State:** We have NO broker integration. Only CSV import from Avanza.

**Research Findings:**

| Broker | API Status | Notes |
|--------|------------|-------|
| **Avanza** | ❌ No public API | Only unofficial Python wrappers exist (avanzapy, pyavanza). Requires 2FA TOTP secret. Avanza actively discourages automated trading. |
| **Nordnet** | ✅ Official API | `nordnet/next-api-v2-examples` on GitHub. REST API with OAuth. Documentation at nordnet.se/externalapi/docs |
| **Saxo Bank** | ✅ Official API | OpenAPI available for partners |
| **Interactive Brokers** | ✅ Official API | Well-documented, but complex |

**Regulatory Concerns:**
- Automated order execution may require FI (Finansinspektionen) license under MiFID II
- "Reception and transmission of orders" and "execution of orders on behalf of clients" are regulated activities
- Would need legal review before implementation

**Recommendation:** 
- ⚠️ **DEFER** full broker integration
- ✅ **DO** Nordnet API integration for portfolio READ-ONLY (holdings sync)
- ✅ **DO** Generate order lists that users copy to broker (current approach is safer)
- 🔴 **DON'T** auto-execute trades without legal clearance

**Effort:** 3-6 months for read-only integration, 12+ months for full execution

---

### 2. Portfolio Tracking Dashboard ✅ PARTIALLY EXISTS

**Current State:**
- ✅ CSV import from Avanza (parse_avanza_csv)
- ✅ Holdings tracking with P&L calculation
- ✅ Portfolio value calculation (get_portfolio_value)
- ✅ Rebalance trade generator with cost estimates
- ✅ Transaction cost calculator (courtage, spread, slippage)
- ❌ No real-time broker sync
- ❌ No performance vs benchmark comparison in UI
- ❌ No "Portfolio Health" score
- ❌ No deviation alerts

**What We Have:**
```
backend/services/user_portfolio.py - Portfolio value tracking
backend/services/transaction_costs.py - Full cost calculator
backend/services/csv_import.py - Avanza CSV parser
backend/services/alerts.py - Basic alert system
```

**Gaps to Fill:**
1. Add benchmark comparison (OMXS30 data now available!)
2. Add "deviation from strategy" calculation
3. Add portfolio health scoring
4. Improve cost visualization in UI

**Recommendation:** ✅ **HIGH PRIORITY** - Build on existing foundation

**Effort:** 2-4 weeks

---

### 3. Strategy Recommendation Engine ❌ NOT EXISTS

**Current State:** Users manually choose from 4 strategies. No guidance.

**Proposed Quiz Flow:**
1. Risk tolerance → Maps to max drawdown tolerance
2. Time commitment → Quarterly vs annual rebalancing
3. Capital size → Minimum viability check
4. Market outlook → Not really needed (strategies are systematic)
5. Geographic preference → Currently Sweden-only

**Technical Feasibility:** Easy to implement - just conditional logic

**Recommendation:** ✅ **HIGH PRIORITY** - Simple to build, high impact

**Implementation:**
```typescript
// Simple decision tree
if (capital < 50000) return "ETF_RECOMMENDATION";
if (riskTolerance < 3) return "trendande_kvalitet"; // Lower volatility
if (timeCommitment === "quarterly") return "sammansatt_momentum";
return "trendande_varde"; // Default for annual
```

**Effort:** 1-2 weeks

---

### 4. Cost Transparency Tool ✅ MOSTLY EXISTS

**Current State:**
- ✅ `transaction_costs.py` - Full cost calculator
- ✅ Broker fee structures (Avanza, Nordnet, DEGIRO, IB)
- ✅ Spread estimates by market cap
- ✅ Rebalance cost calculation
- ✅ Annual cost projection
- ❌ No interactive UI calculator
- ❌ No breakeven analysis
- ❌ No comparison with alternatives

**What We Have:**
```python
# backend/services/transaction_costs.py
BROKERS = {
    "avanza": BrokerFees("Avanza", min_fee=1, percentage=0.0015),
    "nordnet": BrokerFees("Nordnet", min_fee=39, percentage=0.0015),
    ...
}
SPREAD_ESTIMATES = {
    "large_cap": 0.001,   # 0.1%
    "mid_cap": 0.002,     # 0.2%
    "small_cap": 0.005,   # 0.5%
}
```

**Gaps to Fill:**
1. Create interactive UI component
2. Add breakeven analysis (minimum account size)
3. Add comparison with ETF alternatives
4. Show compound effect over time

**Recommendation:** ✅ **HIGH PRIORITY** - Backend ready, need UI

**Effort:** 1-2 weeks

---

### 5. Mobile App ⚠️ MEDIUM PRIORITY

**Current State:** Web-only, no mobile app

**Options Analysis:**

| Approach | Pros | Cons | Effort |
|----------|------|------|--------|
| **PWA** | Fast, cheap, works now | Limited push notifications on iOS, no app store presence | 2-4 weeks |
| **React Native** | Native feel, app stores, team knows React | Separate codebase, longer dev time | 3-6 months |
| **Flutter** | Best performance, single codebase | New language (Dart), learning curve | 3-6 months |

**Research Findings:**
- PWAs are gaining traction in fintech due to app store restrictions
- React Native has 42% market share for cross-platform
- For a "check portfolio status" app, PWA is sufficient

**Recommendation:** 
- ✅ **Phase 1:** PWA with push notifications (2-4 weeks)
- ⏳ **Phase 2:** React Native if user demand exists (3-6 months)

**Effort:** PWA: 2-4 weeks, Native: 3-6 months

---

## TIER 2: High-Impact Extensions

### 6. Tax Optimization Module ⚠️ COMPLEX

**Current State:** Nothing implemented

**Swedish Tax Context:**
- ISK (Investeringssparkonto): ~0.888% annual tax on holdings (2025)
- KF (Kapitalförsäkring): Similar to ISK
- Regular account: 30% capital gains tax

**Research Findings:**
- ISK tax is calculated on average quarterly value × government borrowing rate × 30%
- 2025 ISK tax rate: 0.888%
- New 2026 rules: 300,000 SEK tax-free threshold proposed

**Technical Feasibility:**
- ISK tax calculation: Easy (just holdings × rate)
- ISK vs KF comparison: Medium
- SKV integration: Very complex (government API)

**Recommendation:** 
- ✅ **DO** Simple ISK tax calculator
- ⏳ **DEFER** SKV integration
- 🔴 **DON'T** Provide tax advice (liability risk)

**Effort:** 2-4 weeks for calculator

---

### 7. Automated Rebalancing 🔴 HIGH RISK

**Current State:** Manual rebalancing with trade suggestions

**Regulatory Concerns:**
- Requires FI license for "portfolio management" or "execution of orders"
- MiFID II compliance required
- Would transform Börslabbet from "information service" to "investment service"

**Recommendation:** 🔴 **DON'T DO** without legal entity restructuring

**Alternative:** "One-click copy to clipboard" for order details

---

### 8. AI Strategy Optimizer ⚠️ OVERLY COMPLEX

**Current State:** Fixed strategy parameters

**Analysis:**
- Strategies are based on academic research with proven parameters
- "Optimizing" parameters risks overfitting
- Users want simplicity, not more choices

**Recommendation:** 🔴 **UNNECESSARY** - Adds complexity without clear value

---

### 9. Performance Attribution Engine ✅ VALUABLE

**Current State:**
- ✅ Backtest results show total return, Sharpe, max DD
- ✅ OMXS30 benchmark comparison (just implemented!)
- ❌ No stock-level attribution
- ❌ No factor attribution
- ❌ No sector analysis

**Recommendation:** ✅ **MEDIUM PRIORITY** - Builds confidence

**Effort:** 2-4 weeks

---

### 10. Community Features ⚠️ LOW PRIORITY

**Current State:** No community features

**Analysis:**
- Community features are engagement tools, not core value
- Risk of negative sentiment spreading
- Moderation overhead

**Recommendation:** ⏳ **DEFER** - Focus on core product first

---

## TIER 3: Market Expansion

### 11. International Markets ⚠️ COMPLEX

**Current State:** Sweden-only (Stockholmsbörsen + First North)

**Data Availability:**
- EODHD API: $19.99/mo for international fundamentals
- Would need new data pipeline
- Different market rules per country

**Recommendation:** ⏳ **DEFER** - Focus on Swedish market excellence first

---

### 12. ETF-based Strategy Implementation ✅ INTERESTING

**Analysis:**
- Could partner with ETF provider
- Lower barrier for small accounts
- Different business model (AUM fee vs subscription)

**Recommendation:** ⏳ **LONG-TERM** - Requires significant business development

---

## Summary: What We Already Have

| Feature | Status | Notes |
|---------|--------|-------|
| Strategy rankings | ✅ Complete | 4 strategies, daily refresh |
| Backtesting | ✅ Complete | 42 years of data, OMXS30 benchmark |
| CSV import | ✅ Complete | Avanza format |
| Cost calculator | ✅ Backend ready | Needs UI |
| Rebalance generator | ✅ Complete | With cost estimates |
| Alerts | ✅ Basic | Rebalance reminders |
| Portfolio tracking | ✅ Partial | Needs benchmark comparison |
| Mobile | ❌ None | PWA recommended |
| Broker API | ❌ None | Nordnet read-only possible |
| Strategy quiz | ❌ None | Easy to build |
| Tax calculator | ❌ None | Medium complexity |

---

## Recommended Priority Order

### Phase 1: Quick Wins (4-6 weeks)
1. **Strategy Quiz** - 1-2 weeks, high impact
2. **Cost Calculator UI** - 1-2 weeks, backend ready
3. **Portfolio vs Benchmark** - 1-2 weeks, data ready

### Phase 2: Core Improvements (6-12 weeks)
4. **PWA Mobile App** - 2-4 weeks
5. **Portfolio Health Dashboard** - 2-4 weeks
6. **Performance Attribution** - 2-4 weeks

### Phase 3: Advanced Features (3-6 months)
7. **Nordnet Read-Only Integration** - 4-8 weeks
8. **ISK Tax Calculator** - 2-4 weeks
9. **Deviation Alerts** - 2-4 weeks

### Defer/Don't Do
- ❌ Automated trading (regulatory risk)
- ❌ AI optimizer (unnecessary complexity)
- ❌ Full broker execution (legal issues)
- ❌ International markets (focus first)
- ❌ Community features (distraction)

---

## Key Insights

1. **Regulatory Risk is Real**: Automated trading requires FI license. Stay as "information service."

2. **We Have More Than We Think**: Cost calculator, backtesting, portfolio tracking - all exist in backend.

3. **UI is the Gap**: Most features exist in backend but lack good UI.

4. **Simplicity is the Brand**: Don't add complexity. Users chose Börslabbet for simplicity.

5. **PWA Before Native**: Mobile presence via PWA is faster and cheaper.

6. **Nordnet > Avanza for API**: Nordnet has official API, Avanza doesn't.

---

## Cost Estimates

| Feature | Effort | Priority |
|---------|--------|----------|
| Strategy Quiz | 1-2 weeks | HIGH |
| Cost Calculator UI | 1-2 weeks | HIGH |
| Portfolio Benchmark | 1-2 weeks | HIGH |
| PWA Mobile | 2-4 weeks | HIGH |
| Portfolio Dashboard | 2-4 weeks | MEDIUM |
| Performance Attribution | 2-4 weeks | MEDIUM |
| Nordnet Integration | 4-8 weeks | MEDIUM |
| ISK Calculator | 2-4 weeks | LOW |

**Total for Phase 1-2:** ~12-20 weeks of development

---

*Analysis completed: 2026-01-03*
*Based on current codebase review and web research*
