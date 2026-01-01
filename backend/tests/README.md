# Börslabbet App - Comprehensive Test Suite

A production-ready test suite for the Swedish quantitative investing platform implementing Börslabbet's proven investment strategies.

## 🎯 Test Coverage Overview

### Test Categories

| Category | Files | Description |
|----------|-------|-------------|
| **Unit Tests** | `tests/unit/` | Strategy calculations, data integrity |
| **API Tests** | `tests/integration/test_api_*.py` | All 135 API endpoints |
| **Security Tests** | `tests/integration/test_security.py` | Auth, injection, rate limiting |
| **Accessibility Tests** | `tests/integration/test_accessibility.py` | WCAG compliance, screen readers |
| **UI Page Tests** | `tests/integration/test_ui_pages.py` | Per-page scenarios |
| **Performance Tests** | `tests/integration/test_performance_reliability.py` | Load times, concurrency |
| **E2E Tests** | `tests/e2e/` | Complete user journeys |

### Critical Business Logic
- **4 Börslabbet Strategies**: Sammansatt Momentum, Trendande Värde, Trendande Utdelning, Trendande Kvalitet
- **Market Cap Filtering**: 2B SEK minimum threshold (since June 2023)
- **Portfolio Construction**: Equal-weighted, 10 stocks per strategy
- **Rebalancing Logic**: Quarterly (Momentum) vs Annual (Value/Dividend/Quality)

## 📁 Test Structure

```
backend/tests/
├── conftest.py                           # Test configuration and fixtures
├── unit/
│   ├── test_strategy_calculations.py     # Strategy calculation accuracy
│   └── test_data_integrity.py            # Database constraints, business rules
├── integration/
│   ├── test_api_endpoints.py            # Positive API tests
│   ├── test_api_negative.py             # Negative API tests (400, 401, 404, 422)
│   ├── test_avanza_integration.py       # Avanza API integration
│   ├── test_security.py                 # Security and vulnerability tests
│   ├── test_accessibility.py            # WCAG and a11y compliance
│   ├── test_ui_pages.py                 # Per-page UI scenarios
│   └── test_performance_reliability.py  # Performance and load testing
├── e2e/
│   └── test_user_journeys.py            # End-to-end user workflows
├── fixtures/
│   └── test_data.py                     # Test data generators and fixtures
└── reports/                             # Generated test reports
```

## 🚀 Quick Start

### Prerequisites
```bash
cd backend
pip install -r requirements.txt
```

### Run All Tests
```bash
python run_tests.py
```

### Run by Category
```bash
# Unit tests
pytest tests/unit/ -v -m unit

# API tests (positive + negative)
pytest tests/integration/test_api*.py -v -m api

# Security tests
pytest tests/integration/test_security.py -v -m security

# Accessibility tests
pytest tests/integration/test_accessibility.py -v -m accessibility

# Performance tests
pytest tests/integration/test_performance_reliability.py -v -m performance

# E2E tests
pytest tests/e2e/ -v -m e2e
```

### Generate Go/No-Go Report
```bash
python generate_test_report.py
```

## 📊 Test Categories Detail

### 1. Unit Tests (`tests/unit/`)

#### Strategy Calculations (`test_strategy_calculations.py`)
- Market cap filtering (2B SEK minimum)
- Momentum score calculation (3m, 6m, 12m average)
- Value strategy 6-factor scoring
- Dividend yield ranking
- Quality strategy 4-factor scoring
- Piotroski F-Score filter
- Edge cases and error handling

#### Data Integrity (`test_data_integrity.py`)
- Universe constraints (market cap, exchange)
- Strategy constraints (10 stocks, unique, ordered)
- Portfolio constraints (weights sum to 100%)
- Data completeness and consistency
- Idempotency and concurrency
- Business rule enforcement

### 2. API Tests (`tests/integration/`)

#### Positive Tests (`test_api_endpoints.py`)
- All 135 API endpoints
- Response schema validation
- Business logic verification
- Data freshness indicators

#### Negative Tests (`test_api_negative.py`)
- Invalid inputs (400, 422)
- Authentication failures (401, 403)
- Not found errors (404)
- Rate limiting (429)
- HTTP method validation (405)
- Content type validation

### 3. Security Tests (`test_security.py`)

| Test Category | Tests |
|---------------|-------|
| Authentication | Login failures, session management, logout |
| Authorization | User isolation, resource access control |
| Input Validation | SQL injection, XSS, path traversal |
| Rate Limiting | Brute force protection, API limits |
| Transport Security | No secrets in responses, safe error messages |
| Data Protection | User data isolation, PII handling |

### 4. Accessibility Tests (`test_accessibility.py`)

| WCAG Principle | Tests |
|----------------|-------|
| Perceivable | Text alternatives, descriptive names |
| Operable | No timing requirements, keyboard support |
| Understandable | Consistent responses, clear errors |
| Robust | Valid JSON, parseable data |

### 5. UI Page Tests (`test_ui_pages.py`)

| Page | Test Scenarios |
|------|----------------|
| Dashboard | Data loading, freshness indicators, strategy cards |
| Rebalancing | Trade generation, cost calculation, export |
| Holdings Detail | Fundamentals, price history, alerts |
| Strategies | List, rankings, comparison, performance |
| Portfolio Analysis | Sector allocation, drawdown, benchmark |
| Alerts | List, create, delete, rebalancing alerts |
| Settings | Sync config, stock config, preferences |
| Backtesting | Run, compare, export |
| Goals | Create, update, delete, projection |

### 6. Performance Tests (`test_performance_reliability.py`)

| Metric | Target | Test |
|--------|--------|------|
| Dashboard Load | <2s | `test_dashboard_load_time_under_2s` |
| Strategy Calculation | <5s | `test_strategy_calculation_time_under_5s` |
| API Response | <10s | `test_api_response_time_under_10s` |
| Backtest Execution | <30s | `test_backtest_execution_under_30s` |
| Cache Hit Ratio | >75% | `test_cache_hit_ratio_over_75_percent` |
| Concurrent Users | 10+ | `test_concurrent_user_handling` |
| Memory Usage | <500MB | `test_memory_usage_under_load` |

### 7. E2E Tests (`tests/e2e/`)

| Journey | Steps |
|---------|-------|
| Daily Monitoring | Dashboard → Strategies → Performance → Alerts |
| Quarterly Rebalancing | Notification → Review → Generate → Export → Confirm |
| Portfolio Import | CSV Upload → Parse → Display → Analyze → Backtest |
| Annual Rebalancing | Check dates → Review changes → Execute |
| New User Onboarding | Register → Setup → Import → Choose strategy |

## 🎯 Go/No-Go Checklist

### Critical Must-Pass (12 items)
- [ ] All 4 strategies return exactly 10 stocks
- [ ] 2B SEK minimum market cap filter applied
- [ ] Avanza API integration functional
- [ ] Cache system 24h TTL working
- [ ] Data freshness indicators accurate
- [ ] Strategy calculations match Börslabbet rules
- [ ] Rebalancing trades mathematically correct
- [ ] Portfolio import/export functional
- [ ] Performance metrics vs OMXS30 accurate
- [ ] All 19 pages load without errors
- [ ] Mobile responsiveness maintained
- [ ] Docker Compose deployment successful

### Security Gates (6 items)
- [ ] No SQL injection vulnerabilities
- [ ] No XSS vulnerabilities
- [ ] Auth endpoints protected
- [ ] Rate limiting enabled
- [ ] No secrets in responses
- [ ] Error messages not revealing

### Performance Gates (6 items)
- [ ] Dashboard loads <2s
- [ ] Strategy rankings <5s
- [ ] API response <10s
- [ ] Backtest <30s
- [ ] No memory leaks
- [ ] Cache efficiency >75%

### Data Quality Gates (6 items)
- [ ] No missing fundamental data
- [ ] Sufficient historical price data
- [ ] Backtest results reproducible
- [ ] Cost calculations accurate
- [ ] Universe constraints enforced
- [ ] Data consistency verified

### Accessibility Gates (3 items)
- [ ] API responses screen reader friendly
- [ ] Error messages descriptive
- [ ] Data structures accessible

### Reliability Gates (3 items)
- [ ] Concurrent requests handled
- [ ] Graceful degradation on errors
- [ ] Idempotent operations

## 📈 Test Data Strategy

### Synthetic Data
- User profiles (novice, experienced, intermediate)
- Portfolios (empty, small, standard, large, very large)
- Edge stocks (at market cap boundaries)
- Price histories (various trends and volatilities)

### Golden Files
- Expected backtest results for verification
- Expected strategy outputs for determinism
- Known good CSV import formats

### Fixtures
- Empty portfolio scenarios
- Single/multi strategy scenarios
- Rebalancing scenarios
- Valid/invalid CSV samples

## 🔧 Configuration

### pytest.ini Markers
```ini
markers =
    unit: Unit tests for core business logic
    integration: Integration tests for API and external systems
    e2e: End-to-end user journey tests
    api: API endpoint tests
    strategy: Strategy calculation tests
    performance: Performance and load tests
    security: Security and vulnerability tests
    accessibility: Accessibility compliance tests
    database: Database constraint and integrity tests
    ui: Per-page UI tests
    slow: Slow running tests (>30s)
    smoke: Quick smoke tests for deployment verification
```

## 🚀 CI/CD Integration

### GitHub Actions Workflow
- Multi-Python testing (3.9, 3.10, 3.11)
- Parallel test execution
- Security scanning (Bandit, Safety)
- Coverage reporting (Codecov)
- Deployment gates

### Smoke Tests for Deployment
```bash
pytest -m smoke --tb=short
```

## 📋 Test Maintenance

### Adding New Tests
1. Choose appropriate category (unit/integration/e2e)
2. Add appropriate markers
3. Use existing fixtures where possible
4. Update documentation

### Updating Test Data
- Modify `tests/fixtures/test_data.py`
- Update golden files for backtest verification
- Refresh edge case stocks as market changes

---

**Total Test Coverage**: 500+ test cases across 10 test files
**Categories**: Unit, API, Security, Accessibility, UI, Performance, E2E
**Go/No-Go Items**: 36 checklist items for production readiness
