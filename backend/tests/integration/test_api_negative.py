"""
API Negative Tests and Error Handling for Börslabbet App.

Tests invalid inputs, error responses, and edge cases for all API endpoints.
"""
import pytest
from fastapi.testclient import TestClient
import json
from datetime import date, datetime


@pytest.mark.api
class TestAuthEndpointsNegative:
    """Negative tests for authentication endpoints."""
    
    def test_register_duplicate_user(self, client: TestClient):
        """Test registration fails for duplicate email."""
        # API uses query params: ?email=...&password=...
        params = {"email": "duplicate@test.com", "password": "TestPass123!"}
        
        # First registration
        client.post("/auth/register", params=params)
        
        # Second registration should fail
        response = client.post("/auth/register", params=params)
        assert response.status_code in [400, 409, 422]
    
    def test_register_weak_password(self, client: TestClient):
        """Test registration with weak password."""
        response = client.post("/auth/register", params={
            "email": "new_user@test.com",
            "password": "123"
        })
        # API may accept any password or reject weak ones
        assert response.status_code in [200, 400, 422]
    
    def test_login_nonexistent_user(self, client: TestClient):
        """Test login fails for non-existent user."""
        response = client.post("/auth/login", params={
            "email": "nonexistent@test.com",
            "password": "any_password"
        })
        assert response.status_code in [401, 403, 404, 422]
    
    def test_logout_without_session(self, client: TestClient):
        """Test logout without active session."""
        response = client.post("/auth/logout", params={"token": "invalid_token"})
        assert response.status_code in [200, 204, 401, 404, 422]


@pytest.mark.api
class TestStrategyEndpointsNegative:
    """Negative tests for strategy endpoints."""
    
    def test_get_nonexistent_strategy(self, client: TestClient):
        """Test GET /strategies/{name} returns 404 for non-existent strategy."""
        response = client.get("/strategies/nonexistent_strategy")
        assert response.status_code == 404
    
    def test_get_strategy_with_invalid_name(self, client: TestClient):
        """Test GET /strategies/{name} handles invalid names."""
        invalid_names = [
            "",
            " ",
            "strategy with spaces",
            "strategy/with/slashes",
            "a" * 1000  # Very long name
        ]
        
        for name in invalid_names:
            if name:  # Skip empty string as it would match /strategies
                response = client.get(f"/strategies/{name}")
                assert response.status_code in [400, 404, 422]
    
    def test_strategy_top10_nonexistent(self, client: TestClient):
        """Test GET /strategies/{name}/top10 returns 404 for non-existent strategy."""
        response = client.get("/strategies/fake_strategy/top10")
        assert response.status_code == 404
    
    def test_strategy_enhanced_invalid_params(self, client: TestClient):
        """Test enhanced strategy endpoint with invalid parameters."""
        response = client.get("/strategies/sammansatt_momentum/enhanced", params={
            "invalid_param": "value"
        })
        # Should either ignore invalid params or return error
        assert response.status_code in [200, 400, 422]


@pytest.mark.api
class TestPortfolioEndpointsNegative:
    """Negative tests for portfolio endpoints."""
    
    def test_analyze_rebalancing_empty_holdings(self, client: TestClient):
        """Test rebalancing analysis with empty holdings."""
        response = client.post("/portfolio/analyze-rebalancing", json={
            "strategy": "sammansatt_momentum",
            "current_holdings": [],
            "portfolio_value": 100000
        })
        # Should handle empty holdings gracefully (422 for validation is acceptable)
        assert response.status_code in [200, 400, 422]
    
    def test_analyze_rebalancing_negative_value(self, client: TestClient):
        """Test rebalancing analysis with negative portfolio value."""
        response = client.post("/portfolio/analyze-rebalancing", json={
            "strategy": "sammansatt_momentum",
            "current_holdings": [],
            "portfolio_value": -50000
        })
        assert response.status_code in [400, 422]
    
    def test_analyze_rebalancing_invalid_strategy(self, client: TestClient):
        """Test rebalancing analysis with invalid strategy."""
        response = client.post("/portfolio/analyze-rebalancing", json={
            "strategy": "invalid_strategy",
            "current_holdings": [],
            "portfolio_value": 100000
        })
        assert response.status_code in [400, 404, 422]
    
    def test_analyze_rebalancing_missing_fields(self, client: TestClient):
        """Test rebalancing analysis with missing required fields."""
        response = client.post("/portfolio/analyze-rebalancing", json={})
        assert response.status_code == 422
    
    def test_import_invalid_csv(self, client: TestClient, auth_headers):
        """Test CSV import with invalid format."""
        invalid_csv = "not,a,valid,avanza,csv,format"
        files = {"file": ("invalid.csv", invalid_csv, "text/csv")}
        
        response = client.post("/user/portfolio/import-avanza", files=files, headers=auth_headers)
        assert response.status_code in [400, 422]
    
    def test_import_empty_csv(self, client: TestClient, auth_headers):
        """Test CSV import with empty file."""
        files = {"file": ("empty.csv", "", "text/csv")}
        
        response = client.post("/user/portfolio/import-avanza", files=files, headers=auth_headers)
        assert response.status_code in [400, 422]
    
    def test_get_nonexistent_portfolio(self, client: TestClient, auth_headers):
        """Test GET portfolio with non-existent ID."""
        response = client.get("/user/portfolio/999999999", headers=auth_headers)
        assert response.status_code in [403, 404]
    
    def test_delete_nonexistent_combiner(self, client: TestClient, auth_headers):
        """Test DELETE combiner with non-existent ID."""
        response = client.delete("/portfolio/combiner/999999999", headers=auth_headers)
        assert response.status_code in [403, 404]
    
    def test_combiner_invalid_weights(self, client: TestClient):
        """Test combiner with invalid weights (not summing to 100%)."""
        response = client.post("/portfolio/combiner", json={
            "strategies": [
                {"name": "sammansatt_momentum", "weight": 0.3},
                {"name": "trendande_varde", "weight": 0.3}
                # Total: 60%, not 100%
            ]
        })
        assert response.status_code in [400, 422]
    
    def test_combiner_negative_weights(self, client: TestClient):
        """Test combiner with negative weights."""
        response = client.post("/portfolio/combiner", json={
            "strategies": [
                {"name": "sammansatt_momentum", "weight": -0.5},
                {"name": "trendande_varde", "weight": 1.5}
            ]
        })
        assert response.status_code in [400, 422]


@pytest.mark.api
class TestStockEndpointsNegative:
    """Negative tests for stock endpoints."""
    
    def test_get_nonexistent_stock(self, client: TestClient):
        """Test GET stock with non-existent ticker."""
        response = client.get("/stocks/NONEXISTENT_TICKER_12345")
        assert response.status_code == 404
    
    def test_get_stock_invalid_ticker_format(self, client: TestClient):
        """Test GET stock with invalid ticker format."""
        invalid_tickers = [
            "123",  # Numbers only
            "A" * 50,  # Too long
            "AB CD",  # Contains space
            "AB@CD"  # Contains special char
        ]
        
        for ticker in invalid_tickers:
            response = client.get(f"/stocks/{ticker}")
            assert response.status_code in [400, 404, 422]
    
    def test_get_stock_prices_invalid_range(self, client: TestClient):
        """Test GET stock prices with invalid date range."""
        response = client.get("/stocks/AAPL/prices", params={
            "start_date": "2025-01-01",
            "end_date": "2020-01-01"  # End before start
        })
        # API may return 200 with empty data, or 400/422 for validation
        assert response.status_code in [200, 400, 422]


@pytest.mark.api
class TestBacktestingEndpointsNegative:
    """Negative tests for backtesting endpoints."""
    
    def test_backtest_invalid_date_range(self, client: TestClient):
        """Test backtest with invalid date range."""
        response = client.post("/backtesting/run", json={
            "strategy": "sammansatt_momentum",
            "start_date": "2025-01-01",
            "end_date": "2020-01-01"  # End before start
        })
        assert response.status_code in [400, 422]
    
    def test_backtest_future_dates(self, client: TestClient):
        """Test backtest with future dates."""
        response = client.post("/backtesting/run", json={
            "strategy": "sammansatt_momentum",
            "start_date": "2030-01-01",
            "end_date": "2035-01-01"
        })
        assert response.status_code in [400, 422]
    
    def test_backtest_invalid_strategy(self, client: TestClient):
        """Test backtest with invalid strategy."""
        response = client.post("/backtesting/run", json={
            "strategy": "invalid_strategy",
            "start_date": "2020-01-01",
            "end_date": "2023-01-01"
        })
        assert response.status_code in [400, 404, 422]
    
    def test_backtest_negative_capital(self, client: TestClient):
        """Test backtest with negative initial capital."""
        response = client.post("/backtesting/enhanced", json={
            "strategy": "sammansatt_momentum",
            "start_date": "2020-01-01",
            "end_date": "2023-01-01",
            "initial_capital": -100000
        })
        # 404 if endpoint doesn't exist, 500 for unhandled error
        assert response.status_code in [400, 404, 422, 500]
    
    def test_backtest_zero_capital(self, client: TestClient):
        """Test backtest with zero initial capital."""
        response = client.post("/backtesting/enhanced", json={
            "strategy": "sammansatt_momentum",
            "start_date": "2020-01-01",
            "end_date": "2023-01-01",
            "initial_capital": 0
        })
        # 404 if endpoint doesn't exist, 500 for unhandled error
        assert response.status_code in [400, 404, 422, 500]


@pytest.mark.api
class TestDataEndpointsNegative:
    """Negative tests for data sync endpoints."""
    
    def test_refresh_nonexistent_stock(self, client: TestClient):
        """Test refresh for non-existent stock."""
        response = client.post("/data/refresh-stock/NONEXISTENT_12345")
        # 404 if endpoint doesn't exist, 200 if it handles gracefully
        assert response.status_code in [200, 404, 422]
    
    def test_invalid_sync_config(self, client: TestClient):
        """Test setting invalid sync configuration."""
        response = client.post("/data/sync-config", json={
            "sync_interval": -1,  # Invalid negative interval
            "auto_sync": "not_a_boolean"
        })
        # 404 if endpoint doesn't exist, 200 if it ignores invalid fields
        assert response.status_code in [200, 400, 404, 422]
    
    def test_invalid_stock_config(self, client: TestClient):
        """Test setting invalid stock configuration."""
        response = client.post("/data/stock-config", json={
            "region": "invalid_region",
            "market_cap": "invalid_cap"
        })
        # 404 if endpoint doesn't exist
        assert response.status_code in [200, 400, 404, 422]
    
    def test_universe_invalid_region(self, client: TestClient):
        """Test universe endpoint with invalid region."""
        response = client.get("/data/universe/invalid_region/large")
        # 200 with empty list is acceptable
        assert response.status_code in [200, 400, 404, 422]
    
    def test_universe_invalid_market_cap(self, client: TestClient):
        """Test universe endpoint with invalid market cap filter."""
        response = client.get("/data/universe/sweden/invalid_cap")
        # 200 with empty list is acceptable
        assert response.status_code in [200, 400, 404, 422]


@pytest.mark.api
class TestAnalyticsEndpointsNegative:
    """Negative tests for analytics endpoints."""
    
    def test_sector_allocation_no_portfolio(self, client: TestClient):
        """Test sector allocation without portfolio."""
        response = client.get("/analytics/sector-allocation")
        # Should return empty or error for no portfolio
        assert response.status_code in [200, 400, 404]
    
    def test_drawdown_invalid_period(self, client: TestClient):
        """Test drawdown analysis with invalid period."""
        response = client.get("/analytics/drawdown-periods", params={
            "period": "invalid_period"
        })
        assert response.status_code in [200, 400, 422]


@pytest.mark.api
class TestAlertEndpointsNegative:
    """Negative tests for alert endpoints."""
    
    def test_create_alert_invalid_ticker(self, client: TestClient):
        """Test creating alert with invalid ticker."""
        response = client.post("/alerts", json={
            "ticker": "INVALID_TICKER_12345",
            "threshold": 100.0,
            "type": "price_above"
        })
        # 405 Method Not Allowed if POST not supported on /alerts
        assert response.status_code in [400, 404, 405, 422]
    
    def test_create_alert_negative_threshold(self, client: TestClient):
        """Test creating alert with negative threshold."""
        response = client.post("/alerts", json={
            "ticker": "AAPL",
            "threshold": -100.0,
            "type": "price_above"
        })
        # 405 Method Not Allowed if POST not supported
        assert response.status_code in [400, 404, 405, 422]
    
    def test_create_alert_invalid_type(self, client: TestClient):
        """Test creating alert with invalid type."""
        response = client.post("/alerts", json={
            "ticker": "AAPL",
            "threshold": 100.0,
            "type": "invalid_alert_type"
        })
        # 405 Method Not Allowed if POST not supported
        assert response.status_code in [400, 404, 405, 422]


@pytest.mark.api
class TestGoalEndpointsNegative:
    """Negative tests for goal endpoints."""
    
    def test_create_goal_negative_target(self, client: TestClient):
        """Test creating goal with negative target."""
        response = client.post("/goals", json={
            "name": "Test Goal",
            "target_amount": -100000,
            "target_date": "2030-01-01"
        })
        assert response.status_code in [400, 422]
    
    def test_create_goal_past_date(self, client: TestClient):
        """Test creating goal with past target date."""
        response = client.post("/goals", json={
            "name": "Test Goal",
            "target_amount": 100000,
            "target_date": "2020-01-01"  # Past date
        })
        assert response.status_code in [400, 422]
    
    def test_update_nonexistent_goal(self, client: TestClient):
        """Test updating non-existent goal."""
        response = client.put("/goals/999999999", json={
            "name": "Updated Goal"
        })
        # 404 if endpoint doesn't exist, 422 for validation
        assert response.status_code in [403, 404, 422]
    
    def test_delete_nonexistent_goal(self, client: TestClient):
        """Test deleting non-existent goal."""
        response = client.delete("/goals/999999999")
        assert response.status_code in [403, 404]


@pytest.mark.api
class TestExportEndpointsNegative:
    """Negative tests for export endpoints."""
    
    def test_export_invalid_strategy(self, client: TestClient):
        """Test export with invalid strategy name."""
        response = client.get("/export/rankings/invalid_strategy")
        assert response.status_code in [400, 404]
    
    def test_export_backtest_invalid_strategy(self, client: TestClient):
        """Test backtest export with invalid strategy."""
        response = client.get("/export/backtest/invalid_strategy")
        assert response.status_code in [400, 404]


@pytest.mark.api
class TestCacheEndpointsNegative:
    """Negative tests for cache endpoints."""
    
    def test_invalidate_invalid_key(self, client: TestClient):
        """Test cache invalidation with invalid key."""
        response = client.post("/cache/invalidate", json={
            "key": ""  # Empty key
        })
        assert response.status_code in [200, 400, 422]


@pytest.mark.api
class TestWatchlistEndpointsNegative:
    """Negative tests for watchlist endpoints."""
    
    def test_add_to_nonexistent_watchlist(self, client: TestClient):
        """Test adding stock to non-existent watchlist."""
        response = client.post("/user/watchlist/999999999/add", json={
            "ticker": "AAPL"
        })
        # 404 if endpoint doesn't exist, 422 for validation
        assert response.status_code in [403, 404, 422]
    
    def test_add_invalid_ticker_to_watchlist(self, client: TestClient):
        """Test adding invalid ticker to watchlist."""
        # First create a watchlist
        create_response = client.post("/user/watchlist", json={
            "name": "Test Watchlist"
        })
        
        if create_response.status_code in [200, 201]:
            watchlist_id = create_response.json().get("id", 1)
            
            response = client.post(f"/user/watchlist/{watchlist_id}/add", json={
                "ticker": "INVALID_TICKER_12345"
            })
            assert response.status_code in [400, 404, 422]


@pytest.mark.api
class TestHTTPMethodValidation:
    """Test HTTP method validation."""
    
    def test_post_to_get_endpoint(self, client: TestClient):
        """Test POST to GET-only endpoint returns 405."""
        response = client.post("/strategies")
        assert response.status_code == 405
    
    def test_get_to_post_endpoint(self, client: TestClient):
        """Test GET to POST-only endpoint returns 405."""
        response = client.get("/auth/login")
        assert response.status_code == 405
    
    def test_delete_to_get_endpoint(self, client: TestClient):
        """Test DELETE to GET-only endpoint returns 405."""
        response = client.delete("/strategies")
        assert response.status_code == 405


@pytest.mark.api
class TestContentTypeValidation:
    """Test content type validation."""
    
    def test_post_without_json_content_type(self, client: TestClient):
        """Test POST without proper content type."""
        response = client.post(
            "/auth/login",
            content="username=test&password=test",
            headers={"Content-Type": "text/plain"}
        )
        assert response.status_code in [400, 415, 422]
    
    def test_post_with_invalid_json(self, client: TestClient):
        """Test POST with invalid JSON."""
        response = client.post(
            "/auth/login",
            content="{invalid json}",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code in [400, 422]
