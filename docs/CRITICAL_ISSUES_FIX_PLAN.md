# Börslabbet App Critical Issue Resolution

## Approach

1. **No assumptions** - If unsure about anything (existing code behavior, business logic, data formats, dependencies), ASK before implementing
2. **Research first** - Use web search to find latest best practices, library documentation, and security guidelines before implementing each fix
3. **One fix at a time** - Implement, test, and verify each fix before moving to the next
4. **Verify integration** - After each fix, run relevant tests to ensure nothing else broke
5. **Document everything** - Update the test results document after each verified fix

## Process

### Phase 1: Research
For each issue, investigate the current implementation and document findings in [RESEARCH_FINDINGS.md](RESEARCH_FINDINGS.md). No code changes until all issues are researched.

### Phase 2: Review
Once all research is complete, review findings to ensure proposed implementations are compatible with each other and won't conflict.

### Phase 3: Implementation
Implement fixes one at a time, in priority order, with testing after each.

---

## System Context

- **Stack:** FastAPI backend, React frontend, SQLite database
- **Purpose:** Quantitative Swedish stock strategies with backtesting
- **Data:** 734 stocks, 2.3M price rows, FinBas historical data (1998-2023)
- **Key files:**
  - `backend/services/backtesting.py` - Backtesting engine
  - `backend/services/ranking.py` - Strategy calculations
  - `backend/main.py` - FastAPI app
  - `frontend/src/` - React components

---

## Critical Issues

### PRIORITY 1: Backtesting Integrity
*Financial accuracy - users make investment decisions based on this*

| # | Issue | Location | Problem |
|---|-------|----------|---------|
| 146 | Delisted stocks | backtesting.py:336 | ffill() forward-fills last price instead of recording -100% loss for bankruptcies/delistings |
| 149 | Survivorship bias | backtesting.py | 960 delisted stocks in FinBas but losses not captured |
| 148 | Slippage not applied | backtesting.py | calculate_transaction_costs() defined but never called in backtest_strategy() |
| 143 | Look-ahead bias | backtesting.py | Value/dividend/quality strategies use CURRENT fundamentals when backtesting historical periods |
| 147 | Corporate actions | backtesting.py | No split/dividend adjustment - large price jumps visible |

### PRIORITY 2: Financial Calculations

| # | Issue | Location | Problem |
|---|-------|----------|---------|
| 217 | Division by zero | ranking.py | Momentum calc (latest/past)-1 produces inf if past price = 0 |
| 218 | Infinity filtering | ranking.py | No isinf() checks, infinity propagates |
| 219 | Floating point | Multiple | No explicit precision handling for financial calculations |
| 222 | Compound returns | backtesting.py | Uses simple returns, should use geometric mean for multi-period |

### PRIORITY 3: Security

| # | Issue | Location | Problem |
|---|-------|----------|---------|
| 89 | Rate limiting | main.py | No rate limiting on any endpoints |
| 92 | HTTPS | Deployment | No TLS configuration |
| 93 | Security headers | main.py | Missing CSP, X-Frame-Options, HSTS, X-Content-Type-Options |

### PRIORITY 4: Performance

| # | Issue | Location | Problem |
|---|-------|----------|---------|
| 106 | Cache not working | smart_cache.py / main.py | Cache exists (734 entries) but 0% hit ratio - not being used |
| 105 | No compression | main.py | No gzip/brotli compression on responses |

---

## Requirements for Each Fix

For EACH issue:

### 1. Research Phase
- Search for current best practices
- Check library documentation for any tools planned
- Ask clarifying questions if existing code behavior is unclear
- Document in RESEARCH_FINDINGS.md

### 2. Implementation Phase
- Show exact code changes with full context
- Explain WHY this approach was chosen over alternatives
- Ensure backward compatibility with existing data/APIs

### 3. Testing Phase
- Write a specific test that proves the fix works
- Run the test and show output
- Verify no regressions in related functionality

### 4. Verification Phase
- Update TEST_RESULTS_2026-01-01.md changing the test from FAIL to PASS
- Include evidence of the fix working

---

## Output Format

After each fix:

```
## Fix #[number]: [Issue name]

### Research
- [What you looked up and learned]

### Changes Made
- [File]: [Description of change]

### Test Results
- [Test command and output]

### Verification
- Status: PASS/FAIL
- Evidence: [Proof it works]

### Remaining Issues
- [Updated count]
```
