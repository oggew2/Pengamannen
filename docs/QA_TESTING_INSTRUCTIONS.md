# QA Testing Instructions for Börslabbet App

## Context

You are a QA engineer testing a Swedish stock strategy application (Börslabbet). This is a financial application where users make real investment decisions - accuracy is paramount.

Many issues from a previous test run have been fixed. Your job is to:
1. **Verify the fixes work** - Test each implemented fix
2. **Run remaining tests** - Execute pending test items
3. **Create a test report** - Document all results

---

## Application Setup

```bash
# Start the application
cd /path/to/borslabbet-app
docker compose up -d

# Or manually:
# Backend
cd backend && source .venv/bin/activate && uvicorn main:app --reload

# Frontend  
cd frontend && npm run dev
```

- Frontend: http://localhost:5173
- Backend: http://localhost:8000
- API Docs: http://localhost:8000/docs

---

## Related Documents

| Document | Purpose |
|----------|---------|
| `docs/TESTING_PLAN.md` | Full test plan with 235 items. Look for: 📋 = pending, ✅ = implemented, 🔬 = not a problem |
| `docs/RESEARCH_FINDINGS.md` | What was fixed and why some issues aren't real problems |

---

## Fixes to Verify

### Backend Fixes

| # | Issue | Fix Applied | How to Verify |
|---|-------|-------------|---------------|
| 148 | Transaction costs | 0.15% deducted at each rebalance | Run backtest, check `transaction_costs_total > 0` |
| 149 | Survivorship bias | FinBas prices for historical backtests | Backtest pre-2023 dates, verify uses FinBas |
| 143 | Look-ahead bias | Warning for value/dividend/quality | Run value strategy backtest, check warnings array |
| 217 | Division by zero | `.replace(0, np.nan)` in ranking.py | Check ranking.py line ~82 |
| 218 | Infinity filtering | `.replace([np.inf, -np.inf], np.nan)` | Check ranking.py after momentum calc |
| 89 | Rate limiting | slowapi: 5/min auth, 10/min backtest | Hit auth endpoint 6 times, expect 429 |
| 93 | Security headers | X-Frame-Options, X-Content-Type-Options | `curl -I /v1/health`, check headers |
| 105 | GZip compression | GZipMiddleware for >1KB | Check Content-Encoding header on large response |
| 176 | Metrics endpoint | GET /v1/metrics | `curl /v1/metrics`, expect Prometheus format |
| 180 | Alerting | GET /v1/alerts | `curl /v1/alerts`, expect alerts array |
| 179 | Audit logging | Auth events to audit.log | Login, check audit.log file exists |
| 161 | API versioning | All routes under /v1 | `curl /v1/strategies` works, `/strategies` 404s |

### Frontend Fixes

| # | Issue | Fix Applied | How to Verify |
|---|-------|-------------|---------------|
| 115 | Error boundaries | ErrorBoundary wraps App | Check App.tsx imports ErrorBoundary |
| 114 | Noscript | `<noscript>` in index.html | View source of index.html |
| 81 | Form labels | htmlFor/id attributes | Inspect GoalsPage, HistoricalBacktestPage forms |
| 69 | Pagination | Pagination on StrategyPage | Visit strategy page, scroll to "Full Rankings" |
| 73 | Print styles | @media print in index.css | Print preview any page |
| 214 | Optimistic UI | useOptimistic hook | Check hooks/useOptimistic.ts exists |
| 216 | Multi-tab sync | useTabSync hook | Check hooks/useTabSync.ts exists |
| 138 | Snapshot tests | Vitest + Pagination.test.tsx | `npm run test` in frontend |
| 135 | Golden files | test_golden.py | Check backend/tests/test_golden.py exists |

---

## Verified as Not Real Problems (Skip These)

| # | Issue | Reason |
|---|-------|--------|
| 146 | Delisted stocks | Only 2 large-cap cases in 25 years |
| 147 | Corporate actions | Data already split-adjusted |
| 219 | Floating point | Rankings use relative comparisons |
| 222 | Compound returns | Implementation is mathematically correct |
| 24 | Zero volume | Not used in rankings |
| 27 | Exchange transitions | Handled via market cap filter |
| 67 | Keyboard navigation | Chakra UI handles automatically |
| 76-77 | ARIA labels | Chakra UI provides ARIA support |
| 79 | Focus indicators | Already in index.css |
| 106 | Cache effectiveness | StrategySignal table works correctly |
| 154 | Disk exhaustion | Generic exception handlers exist |
| 156 | Network partitions | Generic exception handlers exist |
| 170 | Market holidays | Handled implicitly via price data |
| 181-183 | Memory leaks | No long-running effects |

---

## Deferred (Not Applicable)

| # | Issue | Reason |
|---|-------|--------|
| 92 | HTTPS | Deployment infrastructure concern |
| 193 | RTL layout | Swedish-only app |
| 194 | Pluralization | Swedish-only app |

---

## Test Execution Process

### Phase 1: Verify Fixes (Priority)

For each fix above:
1. Run the verification test
2. Record: ✅ PASS or ❌ FAIL
3. If FAIL, document what went wrong

**Example verification commands:**
```bash
# Rate limiting
for i in {1..6}; do curl -s -o /dev/null -w "%{http_code}\n" -X POST "http://localhost:8000/v1/auth/login?email=test&password=test"; done
# Expect: 200, 200, 200, 200, 200, 429

# Security headers
curl -I http://localhost:8000/v1/health 2>/dev/null | grep -E "X-Frame|X-Content|X-XSS"
# Expect: X-Frame-Options: DENY, X-Content-Type-Options: nosniff, X-XSS-Protection: 1; mode=block

# Metrics endpoint
curl http://localhost:8000/v1/metrics
# Expect: borslabbet_stocks_total, borslabbet_prices_total, borslabbet_signals_total

# API versioning
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/v1/strategies
# Expect: 200

# Transaction costs in backtest
curl -X POST http://localhost:8000/v1/backtest \
  -H "Content-Type: application/json" \
  -d '{"strategy_name":"sammansatt_momentum","start_date":"2020-01-01","end_date":"2022-01-01"}'
# Expect: response contains "transaction_costs_total" > 0
```

### Phase 2: Run Remaining Tests

Work through `TESTING_PLAN.md`, focusing on items marked 📋 (Pending).

**Priority categories:**
1. Backtesting Bias & Accuracy (#143-149) - CRITICAL
2. Financial Calculations (#217-222) - CRITICAL  
3. Security (#84-95)
4. Backend API (#1-23)

For each test:
- Execute the test
- Record: ✅ PASS | ❌ FAIL | ⚠️ SKIP
- If FAIL, document expected vs actual behavior

### Phase 3: Create Test Report

Create `docs/TEST_RESULTS_[DATE].md`:

```markdown
# Test Execution Report - [DATE]

## Summary
- Total Tests Executed: X
- Passed: X
- Failed: X  
- Skipped: X

## Fix Verification Results
| # | Issue | Result | Notes |
|---|-------|--------|-------|
| 148 | Transaction costs | ✅/❌ | |
...

## New Issues Found
[List any new issues discovered]

## Category Results
[Summary by category]

## Recommendations
[Next steps]
```

---

## Commands Reference

```bash
# Run backend tests
cd backend && source .venv/bin/activate && pytest tests/ -v

# Run frontend tests  
cd frontend && npm run test

# Run golden file tests (creates baselines first time)
cd backend && pytest tests/test_golden.py -v --update-golden

# Check backend loads
cd backend && python -c "from main import app; print('OK')"

# Check frontend builds
cd frontend && npm run build
```

---

## Quality Standards

This is financial software. Tests must verify:
- **Correctness** - Calculations are mathematically accurate
- **Security** - No vulnerabilities (SQL injection, XSS, etc.)
- **Performance** - Dashboard <2s, API <5s
- **Reliability** - Graceful error handling

---

## Notes

- All API endpoints use `/v1` prefix
- Frontend API client uses `/api/v1` (proxied to backend)
- Vitest configured for frontend testing
- pytest configured for backend testing

Take your time. Thoroughness over speed.
