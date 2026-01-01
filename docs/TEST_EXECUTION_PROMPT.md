# Test Execution Prompt for Börslabbet App

## Context

You are a QA engineer testing a Swedish stock strategy application (Börslabbet). This is a financial application where users make real investment decisions based on backtesting results - accuracy is paramount.

**Important:** Many issues from the previous test run have been fixed. Your job is to verify the fixes work and test remaining items.

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
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

## Your Working Documents

1. **docs/TESTING_PLAN.md** - Master test plan with 235 test items across 27 categories
2. **docs/RESEARCH_FINDINGS.md** - Documents what was fixed and what was researched as not a problem

## What Was Already Fixed (Verify These Work)

### Backend Fixes
| # | Issue | Fix Applied |
|---|-------|-------------|
| 148 | Transaction costs | 0.15% deducted at each rebalance in backtesting.py |
| 149 | Survivorship bias | FinBas prices used for historical backtests |
| 143 | Look-ahead bias | Warning added for value/dividend/quality strategies |
| 217 | Division by zero | `.replace(0, np.nan)` in ranking.py |
| 218 | Infinity filtering | `.replace([np.inf, -np.inf], np.nan)` in ranking.py |
| 89 | Rate limiting | slowapi: 5/min auth, 10/min backtest, 2/min sync |
| 93 | Security headers | X-Frame-Options, X-Content-Type-Options, X-XSS-Protection |
| 105 | GZip compression | GZipMiddleware for responses >1KB |
| 176 | Metrics endpoint | GET /v1/metrics (Prometheus format) |
| 180 | Alerting | GET /v1/alerts (data staleness, sync failures) |
| 179 | Audit logging | Auth events logged to audit.log |
| 161 | API versioning | All routes under /v1 prefix |

### Frontend Fixes
| # | Issue | Fix Applied |
|---|-------|-------------|
| 115 | Error boundaries | ErrorBoundary component wraps App |
| 114 | Noscript | `<noscript>` tag in index.html |
| 81 | Form labels | htmlFor/id attributes added |
| 69 | Pagination | Pagination component on StrategyPage |
| 73 | Print styles | @media print CSS in index.css |
| 214 | Optimistic UI | useOptimistic hook available |
| 216 | Multi-tab sync | useTabSync hook available |
| 138 | Snapshot tests | Vitest + Pagination.test.tsx |
| 135 | Golden files | test_golden.py for strategy baselines |

### Verified as Not Real Problems (Skip These)
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
| 79 | Focus indicators | Already in index.css (:focus-visible) |
| 106 | Cache effectiveness | StrategySignal table works correctly |
| 154 | Disk exhaustion | Generic exception handlers exist |
| 156 | Network partitions | Generic exception handlers exist |
| 170 | Market holidays | Handled implicitly via price data |
| 181-183 | Memory leaks | No long-running effects to clean up |

### Deferred (Not Applicable)
| # | Issue | Reason |
|---|-------|--------|
| 92 | HTTPS | Deployment infrastructure concern |
| 193 | RTL layout | Swedish-only app |
| 194 | Pluralization | Swedish-only app |

## Test Execution Process

### Phase 1: Verify Fixes (Priority)

For each fix in the "What Was Already Fixed" section:

1. **Test the fix works** - Run specific test to confirm
2. **Check for regressions** - Ensure fix didn't break anything else
3. **Document result** - PASS/FAIL with evidence

Example verifications:
```bash
# Verify rate limiting
for i in {1..10}; do curl -X POST http://localhost:8000/v1/auth/login -d "email=test&password=test"; done
# Should see 429 after 5 requests

# Verify security headers
curl -I http://localhost:8000/v1/health
# Should see X-Frame-Options: DENY, X-Content-Type-Options: nosniff

# Verify metrics endpoint
curl http://localhost:8000/v1/metrics
# Should see Prometheus-format metrics

# Verify API versioning
curl http://localhost:8000/v1/strategies
# Should return strategies (old /strategies should 404)

# Verify transaction costs in backtest
curl -X POST http://localhost:8000/v1/backtest -H "Content-Type: application/json" \
  -d '{"strategy_name":"sammansatt_momentum","start_date":"2020-01-01","end_date":"2022-01-01"}'
# Response should include transaction_costs_total > 0
```

### Phase 2: Run Remaining Tests

Work through TESTING_PLAN.md categories, focusing on items marked 📋 (Pending).

For each test:
1. Execute the test
2. Record result: ✅ PASS | ❌ FAIL | ⚠️ SKIP (with reason)
3. If FAIL, document:
   - Expected behavior
   - Actual behavior
   - Steps to reproduce
   - Severity (CRITICAL/HIGH/MEDIUM/LOW)

### Phase 3: Create Test Report

Create `docs/TEST_RESULTS_[DATE].md` with:

```markdown
# Test Execution Report - [DATE]

## Summary
- Total Tests: X
- Passed: X
- Failed: X
- Skipped: X

## Fix Verification Results
[Table of fixes verified]

## New Issues Found
[Any new issues discovered]

## Category Results
[Results by category]

## Recommendations
[Next steps]
```

## Test Categories to Cover

1. Backend API (23 items) - Strategy endpoints, auth, data sync
2. Strategy Edge Cases (11 items) - Boundary conditions
3. Database Integrity (10 items) - Data consistency
4. Frontend Pages (19 items) - All pages load correctly
5. UX/Usability (15 items) - Loading states, errors, responsive
6. Accessibility (8 items) - WCAG 2.1 compliance
7. Security (12 items) - SQL injection, XSS, auth
8. Performance (12 items) - Load times, memory
9. Reliability (8 items) - Error handling, offline
10. Deployment (8 items) - Docker, env vars
11. Cross-browser (6 items) - Chrome, Firefox, Safari, Edge
12. Localization (5 items) - Swedish formatting
13. Regression (5 items) - Golden files, snapshots
14. Documentation (4 items) - README accuracy
15. Backtesting Bias (7 items) - Financial accuracy ⚠️ CRITICAL
16. Chaos Testing (7 items) - Failure injection
17. Contract Testing (5 items) - API schemas
18. Visual Regression (6 items) - Screenshot comparison
19. Date/Time (6 items) - Timezone, holidays
20. Observability (7 items) - Logging, metrics
21. Memory Profiling (7 items) - Leak detection
22. I18N (7 items) - Number/date formatting
23. Data Quality (7 items) - ETL integrity
24. Negative API (9 items) - Invalid inputs
25. State Management (6 items) - React state
26. Financial Calculations (6 items) - Math accuracy ⚠️ CRITICAL
27. Test Infrastructure (6 items) - Vitest, pytest

## Quality Standards

This is financial software. Tests must verify:
- **Correctness** - Calculations are mathematically accurate
- **Completeness** - Edge cases handled
- **Security** - No vulnerabilities
- **Performance** - Meets targets (<2s dashboard, <5s API)
- **Reliability** - Graceful error handling

## Commands Reference

```bash
# Run backend tests
cd backend && pytest tests/ -v

# Run frontend tests
cd frontend && npm run test

# Run specific test file
cd backend && pytest tests/test_golden.py -v

# Check test coverage
cd backend && pytest --cov=services tests/
```

## Notes

- All API endpoints now use /v1 prefix
- Frontend API client updated to use /api/v1
- Vitest configured for frontend testing
- Golden file tests require --update-golden flag to create baselines

Good luck with testing!
