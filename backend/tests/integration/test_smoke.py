"""
Smoke Tests for Börslabbet App.

Quick tests to verify basic functionality after deployment.
Run with: pytest -m smoke --tb=short
"""
import pytest
from fastapi.testclient import TestClient


@pytest.mark.smoke
class TestSmokeTests:
    """Quick smoke tests for deployment verification."""
    
    def test_health_endpoint(self, client: TestClient):
        """Verify health endpoint is accessible."""
        response = client.get("/health")
        assert response.status_code == 200
        
        health = response.json()
        assert health.get("status") in ["healthy", "ok", True]
    
    def test_strategies_endpoint(self, client: TestClient):
        """Verify strategies endpoint returns data."""
        response = client.get("/strategies")
        assert response.status_code == 200
        
        strategies = response.json()
        assert len(strategies) == 4
    
    def test_strategy_rankings_accessible(self, client: TestClient):
        """Verify at least one strategy returns rankings."""
        response = client.get("/strategies/sammansatt_momentum")
        assert response.status_code in [200, 503]  # OK or service unavailable
        
        if response.status_code == 200:
            stocks = response.json()
            assert isinstance(stocks, list)
    
    def test_sync_status_accessible(self, client: TestClient):
        """Verify sync status endpoint is accessible."""
        response = client.get("/data/sync-status")
        assert response.status_code == 200
    
    def test_rebalance_dates_accessible(self, client: TestClient):
        """Verify rebalance dates endpoint is accessible."""
        response = client.get("/portfolio/rebalance-dates")
        assert response.status_code == 200
        
        dates = response.json()
        assert isinstance(dates, list)
        assert len(dates) >= 4
    
    def test_analytics_accessible(self, client: TestClient):
        """Verify analytics endpoint is accessible."""
        response = client.get("/analytics/performance-metrics?strategy=sammansatt_momentum")
        assert response.status_code in [200, 404]  # 404 if no data
    
    def test_api_returns_json(self, client: TestClient):
        """Verify API returns valid JSON."""
        endpoints = ["/strategies", "/health", "/portfolio/rebalance-dates"]
        
        for endpoint in endpoints:
            response = client.get(endpoint)
            if response.status_code == 200:
                try:
                    data = response.json()
                    assert data is not None
                except Exception as e:
                    pytest.fail(f"{endpoint} did not return valid JSON: {e}")
    
    def test_no_500_errors_on_main_endpoints(self, client: TestClient):
        """Verify main endpoints don't return 500 errors."""
        endpoints = [
            "/health",
            "/strategies",
            "/strategies/sammansatt_momentum",
            "/portfolio/rebalance-dates",
            "/data/sync-status"
        ]
        
        for endpoint in endpoints:
            response = client.get(endpoint)
            assert response.status_code != 500, f"{endpoint} returned 500 error"
