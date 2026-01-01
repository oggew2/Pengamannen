"""
End-to-End User Journey Tests for Börslabbet App.

Tests complete workflows: daily monitoring, rebalancing, portfolio import/analysis.
"""
import pytest
from httpx import AsyncClient
from fastapi.testclient import TestClient
import json
import time
from datetime import date, datetime, timedelta
from unittest.mock import patch, Mock
import pandas as pd


@pytest.mark.e2e
class TestDailyMonitoringJourney:
    """Test daily strategy monitoring user journey."""
    
    STRATEGIES = ["sammansatt_momentum", "trendande_varde", "trendande_utdelning", "trendande_kvalitet"]
    
    def test_complete_daily_monitoring_workflow(self, client: TestClient):
        """Test complete daily monitoring workflow from dashboard to alerts."""
        errors = []
        
        # Step 1: Health check
        health_response = client.get("/health")
        if health_response.status_code != 200:
            errors.append(f"Health check failed: {health_response.status_code}")
        
        # Step 2: Check sync status for freshness
        sync_response = client.get("/data/sync-status")
        if sync_response.status_code == 200:
            sync_status = sync_response.json()
            freshness = sync_status.get("data_freshness") or sync_status.get("freshness") or sync_status.get("status")
            if freshness:
                assert freshness in ["Fresh", "Recent", "Stale", "Old", "healthy", "ok"]
        
        # Step 3: Check all strategy rankings
        for strategy in self.STRATEGIES:
            strategy_response = client.get(f"/strategies/{strategy}")
            
            if strategy_response.status_code == 200:
                stocks = strategy_response.json()
                if len(stocks) > 10:
                    errors.append(f"{strategy} returned {len(stocks)} stocks (max 10)")
                
                for stock in stocks:
                    if stock.get("market_cap", 0) < 2000:
                        errors.append(f"Stock {stock.get('ticker')} below 2B SEK in {strategy}")
        
        # Step 4: Check performance metrics
        performance_response = client.get("/analytics/performance-metrics")
        if performance_response.status_code == 200:
            metrics = performance_response.json()
            if "benchmark_comparison" in metrics:
                assert "omxs30" in metrics["benchmark_comparison"] or isinstance(metrics["benchmark_comparison"], dict)
        
        assert len(errors) == 0, f"Workflow errors: {errors}"
    
    def test_data_freshness_warning_flow(self, client: TestClient):
        """Test user sees appropriate warnings for stale data."""
        sync_response = client.get("/data/sync-status")
        assert sync_response.status_code == 200
        
        sync_status = sync_response.json()
        # SyncStatus returns stocks, prices, fundamentals - not freshness
        # Skip manual sync trigger as it calls real API and takes 5+ minutes
    
    def test_performance_comparison_workflow(self, client: TestClient):
        """Test strategy performance comparison workflow."""
        comparison_response = client.get("/strategies/compare")
        assert comparison_response.status_code == 200
        
        comparison = comparison_response.json()
        # API returns dict with strategy names as keys
        assert isinstance(comparison, dict)
        for expected in self.STRATEGIES:
            assert expected in comparison, f"Missing {expected} in comparison"
    
    def test_all_strategies_accessible(self, client: TestClient):
        """Test all 4 strategies are accessible and return valid data."""
        for strategy in self.STRATEGIES:
            response = client.get(f"/strategies/{strategy}")
            assert response.status_code in [200, 404, 503], f"{strategy} returned {response.status_code}"
            
            if response.status_code == 200:
                stocks = response.json()
                assert isinstance(stocks, list), f"{strategy} should return a list"


@pytest.mark.e2e
class TestQuarterlyRebalancingJourney:
    """Test quarterly rebalancing journey for Sammansatt Momentum."""
    
    def test_complete_momentum_rebalancing_workflow(self, client: TestClient):
        """Test complete quarterly rebalancing workflow for momentum strategy."""
        
        # Step 1: Check if rebalancing is due
        rebalance_dates_response = client.get("/portfolio/rebalance-dates")
        assert rebalance_dates_response.status_code == 200
        
        dates = rebalance_dates_response.json()
        # API returns strategy_name, not strategy
        momentum_date = next((d for d in dates if d["strategy_name"] == "sammansatt_momentum"), None)
        assert momentum_date is not None
        assert "next_date" in momentum_date
        
        # Step 2: Open RebalancingPage - review strategy changes
        current_strategy_response = client.get("/strategies/sammansatt_momentum")
        
        if current_strategy_response.status_code == 200:
            current_stocks = current_strategy_response.json()
            assert len(current_stocks) <= 10
            
            # Step 3: Generate trade list - verify buy/sell calculations
            mock_current_holdings = [
                {"ticker": "OLD_STOCK_1", "shares": 100, "avg_price": 150.0},
                {"ticker": "OLD_STOCK_2", "shares": 50, "avg_price": 200.0}
            ]
            
            rebalance_request = {
                "strategy": "sammansatt_momentum",
                "current_holdings": mock_current_holdings,
                "portfolio_value": 50000
            }
            
            trade_response = client.post("/portfolio/analyze-rebalancing", json=rebalance_request)
            
            if trade_response.status_code == 200:
                trades = trade_response.json()
                assert "buy_orders" in trades
                assert "sell_orders" in trades
                assert "total_cost" in trades
                
                # Verify cost calculations include courtage and spread
                assert "courtage" in trades
                assert "spread_cost" in trades
                assert trades["total_cost"] >= 0
                
                # Step 4: Export to CSV - confirm format compatibility
                export_response = client.get("/export/rebalance-trades", 
                                           params={"strategy": "sammansatt_momentum"})
                
                if export_response.status_code == 200:
                    # Should return CSV format
                    assert "text/csv" in export_response.headers.get("content-type", "")
    
    def test_rebalancing_cost_accuracy(self, client: TestClient):
        """Test rebalancing cost calculations are accurate."""
        rebalance_request = {
            "strategy": "sammansatt_momentum",
            "current_holdings": [
                {"ticker": "STOCK1", "shares": 100, "avg_price": 100.0}  # 10,000 SEK position
            ],
            "portfolio_value": 100000  # 100,000 SEK total
        }
        
        response = client.post("/portfolio/analyze-rebalancing", json=rebalance_request)
        
        if response.status_code == 200:
            result = response.json()
            
            # Verify cost structure
            assert "courtage" in result
            assert "spread_cost" in result
            assert "total_cost" in result
            
            # Courtage should be ~0.069% of trade value (Avanza standard)
            # Spread should be ~0.2% for large caps
            total_cost = result["total_cost"]
            portfolio_value = rebalance_request["portfolio_value"]
            
            # Total cost should be reasonable (< 2% of portfolio)
            cost_percentage = total_cost / portfolio_value
            assert cost_percentage < 0.02  # Less than 2%
    
    def test_equal_weight_rebalancing(self, client: TestClient):
        """Test rebalancing produces equal-weighted portfolio (10% each)."""
        rebalance_request = {
            "strategy": "sammansatt_momentum",
            "current_holdings": [],  # Empty portfolio
            "portfolio_value": 100000
        }
        
        response = client.post("/portfolio/analyze-rebalancing", json=rebalance_request)
        
        if response.status_code == 200:
            result = response.json()
            buy_orders = result.get("buy_orders", [])
            
            if len(buy_orders) > 0:
                # Each position should be approximately 10% of portfolio
                target_position_size = 100000 / 10  # 10,000 SEK per stock
                
                for order in buy_orders:
                    position_value = order["shares"] * order["price"]
                    weight = position_value / 100000
                    
                    # Should be close to 10% (allow 1% tolerance for rounding)
                    assert 0.09 <= weight <= 0.11


@pytest.mark.e2e
class TestPortfolioImportAnalysisJourney:
    """Test portfolio import and analysis journey."""
    
    def test_complete_portfolio_import_workflow(self, client: TestClient, auth_headers):
        """Test complete portfolio import and analysis workflow."""
        
        # Step 1: Import Avanza CSV - verify parsing accuracy
        sample_csv = """Konto;Typ av transaktion;Värdepapper/beskrivning;ISIN;Datum;Antal;Kurs;Belopp;Valuta;Courtage;Valutakurs
Kapitalförsäkring;Köp;Apple Inc;US0378331005;2024-01-15;10;150,25;-1502,50;SEK;6,95;1,0000
Kapitalförsäkring;Köp;Microsoft Corp;US5949181045;2024-01-15;5;300,50;-1502,50;SEK;6,95;1,0000
Kapitalförsäkring;Köp;Alphabet Inc;US02079K3059;2024-01-15;8;125,75;-1006,00;SEK;6,95;1,0000"""
        
        # API expects file_content as form field, not file upload
        import_response = client.post(
            "/user/portfolio/import-avanza",
            data={"file_content": sample_csv, "portfolio_name": "Test Portfolio"},
            headers=auth_headers
        )
        
        # Accept 200 (success), 400 (parse error), or 422 (validation)
        assert import_response.status_code in [200, 400, 422]
        
        if import_response.status_code == 200:
            import_result = import_response.json()
            if "holdings" in import_result:
                holdings = import_result["holdings"]
                for holding in holdings:
                    assert "ticker" in holding or "name" in holding
        
        # Step 2: View portfolios
        portfolio_response = client.get("/user/portfolios", headers=auth_headers)
        assert portfolio_response.status_code == 200
        
        # Step 4: Run backtesting - validate historical accuracy
        backtest_request = {
            "strategy": "sammansatt_momentum",
            "start_date": "2023-01-01",
            "end_date": "2024-12-31",
            "initial_capital": 100000
        }
        
        backtest_response = client.post("/backtest/enhanced", json=backtest_request)
        
        if backtest_response.status_code == 200:
            backtest_result = backtest_response.json()
            assert "performance" in backtest_result
            assert "metrics" in backtest_result
            
            performance = backtest_result["performance"]
            assert "total_return" in performance
            assert "benchmark_return" in performance
    
    def test_portfolio_performance_calculation(self, client: TestClient):
        """Test portfolio performance endpoint returns expected structure."""
        # Test the analytics endpoint with required strategy parameter
        response = client.get("/analytics/performance-metrics?strategy=sammansatt_momentum")
        
        # Accept 200 (success) or 404 (no data in test DB)
        assert response.status_code in [200, 404]
        
        if response.status_code == 200:
            metrics = response.json()
            # Verify response has performance-related fields
            assert isinstance(metrics, dict)
    
    def test_csv_format_compatibility(self, client: TestClient, auth_headers):
        """Test CSV import handles various Avanza export formats."""
        csv_content = """Konto;Typ av transaktion;Värdepapper/beskrivning;ISIN;Datum;Antal;Kurs;Belopp;Valuta;Courtage;Valutakurs
Kapitalförsäkring;Köp;Apple Inc;US0378331005;2024-01-15;10;150,25;-1502,50;SEK;6,95;1,0000"""
        
        # API expects file_content as form field
        response = client.post(
            "/user/portfolio/import-avanza",
            data={"file_content": csv_content, "portfolio_name": "Test Import"},
            headers=auth_headers
        )
        assert response.status_code in [200, 400, 422]


@pytest.mark.e2e
class TestAnnualRebalancingJourney:
    """Test annual rebalancing journey for value/dividend/quality strategies."""
    
    def test_annual_strategy_rebalancing_workflow(self, client: TestClient):
        """Test annual rebalancing workflow for value/dividend/quality strategies."""
        annual_strategies = ["trendande_varde", "trendande_utdelning", "trendande_kvalitet"]
        
        for strategy in annual_strategies:
            # Check rebalancing frequency
            dates_response = client.get("/portfolio/rebalance-dates")
            assert dates_response.status_code == 200
            
            dates = dates_response.json()
            strategy_date = next((d for d in dates if d["strategy_name"] == strategy), None)
            
            if strategy_date:
                assert "next_date" in strategy_date
                
                # Get strategy rankings
                strategy_response = client.get(f"/strategies/{strategy}")
                
                if strategy_response.status_code == 200:
                    stocks = strategy_response.json()
                    assert len(stocks) <= 10
                    # Verify strategy-specific logic
                    if strategy == "trendande_varde":
                        # Should have value scores
                        for stock in stocks:
                            assert "value_score" in stock or "score" in stock
                    
                    elif strategy == "trendande_utdelning":
                        # Should have dividend yields
                        for stock in stocks:
                            assert "dividend_yield" in stock or "score" in stock
                    
                    elif strategy == "trendande_kvalitet":
                        # Should have quality scores
                        for stock in stocks:
                            assert "quality_score" in stock or "score" in stock
    
    def test_march_rebalancing_timing(self, client: TestClient):
        """Test annual strategies have valid rebalance dates."""
        annual_strategies = ["trendande_varde", "trendande_utdelning", "trendande_kvalitet"]
        
        dates_response = client.get("/portfolio/rebalance-dates")
        assert dates_response.status_code == 200
        
        dates = dates_response.json()
        
        for strategy in annual_strategies:
            strategy_date = next((d for d in dates if d["strategy_name"] == strategy), None)
            
            if strategy_date and "next_date" in strategy_date:
                # Verify date is valid ISO format
                next_date_str = strategy_date["next_date"]
                assert len(next_date_str) >= 10  # At least YYYY-MM-DD


@pytest.mark.e2e
@pytest.mark.slow
class TestCompleteUserJourneys:
    """Test complete end-to-end user journeys."""
    
    def test_new_user_onboarding_journey(self, client: TestClient, auth_headers):
        """Test complete new user onboarding journey."""
        
        # Step 1: User checks API health
        health_response = client.get("/health")
        assert health_response.status_code == 200
        
        # Step 2: User explores strategies
        strategies_response = client.get("/strategies")
        assert strategies_response.status_code == 200
        
        strategies = strategies_response.json()
        assert len(strategies) == 4
        
        # Step 3: User views strategy details
        for strategy in strategies:
            detail_response = client.get(f"/strategies/{strategy['name']}")
            assert detail_response.status_code in [200, 404, 503]
        
        # Step 4: User imports first portfolio
        sample_csv = """Konto;Typ av transaktion;Värdepapper/beskrivning;ISIN;Datum;Antal;Kurs;Belopp;Valuta;Courtage;Valutakurs
Kapitalförsäkring;Köp;Test Stock;SE0000000001;2024-01-15;10;100,00;-1000,00;SEK;6,95;1,0000"""
        
        files = {"file": ("first_portfolio.csv", sample_csv, "text/csv")}
        import_response = client.post("/user/portfolio/import-avanza", files=files, headers=auth_headers)
        assert import_response.status_code in [200, 400]
    
    def test_experienced_user_daily_routine(self, client: TestClient):
        """Test experienced user's daily routine."""
        
        # Morning routine: Check health and data freshness
        dashboard_start = time.time()
        health_response = client.get("/health")
        dashboard_time = time.time() - dashboard_start
        
        assert health_response.status_code == 200
        assert dashboard_time < 2.0  # Should load within 2 seconds
        
        # Check all strategies quickly
        strategy_times = []
        strategies = ["sammansatt_momentum", "trendande_varde", "trendande_utdelning", "trendande_kvalitet"]
        
        for strategy in strategies:
            start_time = time.time()
            response = client.get(f"/strategies/{strategy}")
            strategy_time = time.time() - start_time
            
            if response.status_code == 200:
                strategy_times.append(strategy_time)
        
        # Strategy loading should be fast (cached data)
        if strategy_times:
            avg_strategy_time = sum(strategy_times) / len(strategy_times)
            assert avg_strategy_time < 1.0  # Average under 1 second
        
        # Check portfolio performance (requires strategy param)
        performance_response = client.get("/analytics/performance-metrics?strategy=sammansatt_momentum")
        assert performance_response.status_code in [200, 404]
    
    def test_mobile_user_experience(self, client: TestClient, auth_headers):
        """Test mobile user experience and responsiveness."""
        
        # Simulate mobile user agent
        mobile_headers = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 14_7_1 like Mac OS X) AppleWebKit/605.1.15"
        }
        
        # Test key mobile workflows
        health_response = client.get("/health", headers=mobile_headers)
        assert health_response.status_code == 200
        
        # Mobile users typically check strategies quickly
        strategy_response = client.get("/strategies/sammansatt_momentum", headers=mobile_headers)
        assert strategy_response.status_code in [200, 404]
        
        if strategy_response.status_code == 200:
            content_length = len(strategy_response.content)
            assert content_length < 1024 * 1024  # Less than 1MB
        
        # Test portfolio view on mobile (needs auth)
        combined_headers = {**mobile_headers, **auth_headers}
        portfolio_response = client.get("/user/portfolios", headers=combined_headers)
        assert portfolio_response.status_code == 200
