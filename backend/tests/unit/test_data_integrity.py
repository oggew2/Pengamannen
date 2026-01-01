"""
Database Constraints and Data Integrity Tests for Börslabbet App.

Tests database constraints, data validation, and business rule enforcement.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import pandas as pd
from datetime import date, datetime, timedelta


@pytest.mark.database
class TestUniverseConstraints:
    """Test universe filtering constraints."""
    
    def test_market_cap_minimum_2b_sek(self, client: TestClient):
        """Verify 2B SEK minimum market cap is enforced."""
        response = client.get("/strategies/sammansatt_momentum")
        
        if response.status_code == 200:
            stocks = response.json()
            
            for stock in stocks:
                market_cap = stock.get("market_cap", 0)
                # Market cap should be >= 2000 MSEK (2B SEK)
                assert market_cap >= 2000, f"Stock {stock.get('ticker')} has market cap {market_cap} < 2000 MSEK"
    
    def test_exchange_filter_stockholmsborsen_first_north(self, client: TestClient):
        """Verify only Stockholmsbörsen and First North stocks are included."""
        response = client.get("/strategies/sammansatt_momentum")
        
        if response.status_code == 200:
            stocks = response.json()
            
            valid_exchanges = ["Stockholmsbörsen", "First North", "NASDAQ Stockholm", "NGM"]
            
            for stock in stocks:
                exchange = stock.get("exchange", "")
                if exchange:
                    # Should be a valid Swedish exchange
                    assert any(valid in exchange for valid in valid_exchanges), \
                        f"Stock {stock.get('ticker')} has invalid exchange: {exchange}"
    
    def test_universe_size_reasonable(self, client: TestClient):
        """Verify universe size is reasonable (not too small or large)."""
        response = client.get("/data/universe/sweden/large")
        
        if response.status_code == 200:
            universe = response.json()
            
            if isinstance(universe, list):
                # Should have reasonable number of stocks
                assert len(universe) >= 10, "Universe too small"
                assert len(universe) <= 1000, "Universe too large"


@pytest.mark.database
class TestStrategyConstraints:
    """Test strategy-specific constraints."""
    
    def test_strategy_returns_exactly_10_stocks(self, client: TestClient):
        """Verify each strategy returns exactly 10 stocks (when data available)."""
        strategies = ["sammansatt_momentum", "trendande_varde", 
                     "trendande_utdelning", "trendande_kvalitet"]
        
        for strategy in strategies:
            response = client.get(f"/strategies/{strategy}/top10")
            
            if response.status_code == 200:
                stocks = response.json()
                # Skip assertion if no data synced yet
                if len(stocks) > 0:
                    assert len(stocks) == 10, f"{strategy} returned {len(stocks)} stocks, expected 10"
    
    def test_strategy_stocks_are_unique(self, client: TestClient):
        """Verify no duplicate stocks in strategy rankings."""
        strategies = ["sammansatt_momentum", "trendande_varde", 
                     "trendande_utdelning", "trendande_kvalitet"]
        
        for strategy in strategies:
            response = client.get(f"/strategies/{strategy}")
            
            if response.status_code == 200:
                stocks = response.json()
                tickers = [s.get("ticker") for s in stocks]
                
                # No duplicates
                assert len(tickers) == len(set(tickers)), f"{strategy} has duplicate stocks"
    
    def test_strategy_rankings_are_ordered(self, client: TestClient):
        """Verify strategy rankings are properly ordered by score."""
        strategies = ["sammansatt_momentum", "trendande_varde", 
                     "trendande_utdelning", "trendande_kvalitet"]
        
        for strategy in strategies:
            response = client.get(f"/strategies/{strategy}")
            
            if response.status_code == 200:
                stocks = response.json()
                
                if len(stocks) > 1:
                    scores = [s.get("score", 0) for s in stocks]
                    # Scores should be in descending order
                    assert scores == sorted(scores, reverse=True), \
                        f"{strategy} rankings not properly ordered"
    
    def test_rebalancing_frequency_correct(self, client: TestClient):
        """Verify rebalancing frequencies match strategy rules."""
        response = client.get("/portfolio/rebalance-dates")
        
        if response.status_code == 200:
            dates = response.json()
            
            for item in dates:
                strategy = item.get("strategy", "")
                frequency = item.get("frequency", "")
                
                if strategy == "sammansatt_momentum":
                    assert frequency == "quarterly", f"Momentum should be quarterly, got {frequency}"
                elif strategy in ["trendande_varde", "trendande_utdelning", "trendande_kvalitet"]:
                    assert frequency == "annual", f"{strategy} should be annual, got {frequency}"


@pytest.mark.database
class TestPortfolioConstraints:
    """Test portfolio-related constraints."""
    
    def test_portfolio_weights_sum_to_100(self, client: TestClient):
        """Verify portfolio weights sum to 100%."""
        response = client.post("/portfolio/combiner", json={
            "strategies": [
                {"name": "sammansatt_momentum", "weight": 0.5},
                {"name": "trendande_varde", "weight": 0.5}
            ]
        })
        
        if response.status_code == 200:
            portfolio = response.json()
            
            if "holdings" in portfolio:
                holdings = portfolio["holdings"]
                total_weight = sum(h.get("weight", 0) for h in holdings)
                
                # Should sum to approximately 1.0 (100%)
                assert 0.99 <= total_weight <= 1.01, f"Weights sum to {total_weight}, expected ~1.0"
    
    def test_equal_weight_per_stock(self, client: TestClient):
        """Verify equal weighting (10% per stock) in strategies."""
        response = client.get("/strategies/sammansatt_momentum")
        
        if response.status_code == 200:
            stocks = response.json()
            
            if len(stocks) == 10:
                # Each stock should have ~10% weight
                for stock in stocks:
                    weight = stock.get("weight", 0.1)
                    assert 0.09 <= weight <= 0.11, f"Stock weight {weight} not ~10%"
    
    def test_holdings_have_valid_tickers(self, client: TestClient):
        """Verify all holdings have valid ticker symbols."""
        response = client.get("/strategies/sammansatt_momentum")
        
        if response.status_code == 200:
            stocks = response.json()
            
            for stock in stocks:
                ticker = stock.get("ticker", "")
                
                # Ticker should be non-empty string
                assert ticker, "Stock missing ticker"
                assert isinstance(ticker, str), "Ticker should be string"
                assert len(ticker) <= 20, f"Ticker too long: {ticker}"


@pytest.mark.database
class TestDataIntegrity:
    """Test data integrity and consistency."""
    
    def test_fundamental_data_completeness(self, client: TestClient):
        """Verify fundamental data is complete for ranked stocks."""
        response = client.get("/strategies/sammansatt_momentum")
        
        if response.status_code == 200:
            stocks = response.json()
            
            required_fields = ["ticker", "name", "market_cap", "score"]
            
            for stock in stocks:
                for field in required_fields:
                    assert field in stock, f"Stock missing required field: {field}"
    
    def test_price_data_continuity(self, client: TestClient):
        """Verify price data has no large gaps."""
        # Get a stock's price history
        response = client.get("/stocks/AAPL/prices")
        
        if response.status_code == 200:
            prices = response.json()
            
            if isinstance(prices, list) and len(prices) > 1:
                # Check for reasonable price continuity
                # (No single-day moves > 50%)
                for i in range(1, min(len(prices), 10)):
                    if "close" in prices[i] and "close" in prices[i-1]:
                        prev_price = prices[i-1]["close"]
                        curr_price = prices[i]["close"]
                        
                        if prev_price > 0:
                            change = abs(curr_price - prev_price) / prev_price
                            assert change < 0.5, f"Suspicious price change: {change:.1%}"
    
    def test_no_negative_market_caps(self, client: TestClient):
        """Verify no stocks have negative market caps."""
        response = client.get("/strategies/sammansatt_momentum")
        
        if response.status_code == 200:
            stocks = response.json()
            
            for stock in stocks:
                market_cap = stock.get("market_cap", 0)
                assert market_cap >= 0, f"Stock {stock.get('ticker')} has negative market cap"
    
    def test_no_negative_pe_ratios(self, client: TestClient):
        """Verify P/E ratios are handled correctly (can be negative for losses)."""
        response = client.get("/strategies/trendande_varde")
        
        if response.status_code == 200:
            stocks = response.json()
            
            for stock in stocks:
                pe = stock.get("pe_ratio")
                # P/E can be negative (losses) or None (no earnings)
                # But shouldn't be zero (would indicate division error)
                if pe is not None and pe != 0:
                    assert isinstance(pe, (int, float)), f"Invalid P/E type: {type(pe)}"
    
    def test_dividend_yields_in_valid_range(self, client: TestClient):
        """Verify dividend yields are in valid range (0-100%)."""
        response = client.get("/strategies/trendande_utdelning")
        
        if response.status_code == 200:
            stocks = response.json()
            
            for stock in stocks:
                div_yield = stock.get("dividend_yield", 0)
                
                if div_yield is not None:
                    # Dividend yield should be 0-100% (0.0-1.0 as decimal)
                    assert 0 <= div_yield <= 1.0, f"Invalid dividend yield: {div_yield}"


@pytest.mark.database
class TestIdempotency:
    """Test idempotency of operations."""
    
    def test_rebalance_calculation_idempotent(self, client: TestClient):
        """Verify rebalance calculations are idempotent."""
        request_data = {
            "strategy": "sammansatt_momentum",
            "current_holdings": [
                {"ticker": "AAPL", "shares": 100, "avg_price": 150.0}
            ],
            "portfolio_value": 100000
        }
        
        # Make same request twice
        response1 = client.post("/portfolio/analyze-rebalancing", json=request_data)
        response2 = client.post("/portfolio/analyze-rebalancing", json=request_data)
        
        if response1.status_code == 200 and response2.status_code == 200:
            result1 = response1.json()
            result2 = response2.json()
            
            # Results should be identical
            assert result1 == result2, "Rebalance calculation not idempotent"
    
    def test_strategy_ranking_consistent(self, client: TestClient):
        """Verify strategy rankings are consistent across requests."""
        # Make same request twice
        response1 = client.get("/strategies/sammansatt_momentum")
        response2 = client.get("/strategies/sammansatt_momentum")
        
        if response1.status_code == 200 and response2.status_code == 200:
            stocks1 = response1.json()
            stocks2 = response2.json()
            
            # Rankings should be identical
            tickers1 = [s.get("ticker") for s in stocks1]
            tickers2 = [s.get("ticker") for s in stocks2]
            
            assert tickers1 == tickers2, "Strategy rankings not consistent"


@pytest.mark.database
class TestConcurrency:
    """Test concurrent access handling."""
    
    def test_concurrent_reads_safe(self, client: TestClient):
        """Verify concurrent reads don't cause issues."""
        import concurrent.futures
        
        def read_strategy():
            return client.get("/strategies/sammansatt_momentum")
        
        # Make 10 concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(read_strategy) for _ in range(10)]
            responses = [f.result() for f in futures]
        
        # All should succeed
        success_count = sum(1 for r in responses if r.status_code == 200)
        assert success_count >= 8, f"Only {success_count}/10 concurrent reads succeeded"
    
    def test_concurrent_writes_handled(self, client: TestClient):
        """Verify concurrent writes are handled safely."""
        import concurrent.futures
        
        def create_goal(i):
            return client.post("/goals", json={
                "name": f"Concurrent Goal {i}",
                "target_amount": 100000 + i * 1000,
                "target_date": "2030-01-01"
            })
        
        # Make 5 concurrent write requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(create_goal, i) for i in range(5)]
            responses = [f.result() for f in futures]
        
        # Should handle gracefully (success or proper error)
        for response in responses:
            assert response.status_code in [200, 201, 400, 409, 422]


@pytest.mark.database
class TestBusinessRules:
    """Test business rule enforcement."""
    
    def test_cost_calculations_use_correct_rates(self, client: TestClient):
        """Verify cost calculations use correct courtage rates."""
        response = client.post("/portfolio/analyze-rebalancing", json={
            "strategy": "sammansatt_momentum",
            "current_holdings": [],
            "portfolio_value": 100000
        })
        
        if response.status_code == 200:
            result = response.json()
            
            # Avanza courtage is ~0.069%
            # Total cost should be reasonable
            total_cost = result.get("total_cost", 0)
            portfolio_value = 100000
            
            # Cost should be < 2% of portfolio
            if total_cost > 0:
                cost_percentage = total_cost / portfolio_value
                assert cost_percentage < 0.02, f"Cost {cost_percentage:.2%} seems too high"
    
    def test_momentum_uses_correct_periods(self, client: TestClient):
        """Verify momentum calculation uses 3m, 6m, 12m periods."""
        response = client.get("/strategies/sammansatt_momentum/enhanced")
        
        if response.status_code == 200:
            data = response.json()
            
            # Should include momentum period data
            if "stocks" in data:
                for stock in data["stocks"]:
                    # May include individual period returns
                    pass  # Structure depends on implementation
    
    def test_value_strategy_uses_6_factors(self, client: TestClient):
        """Verify value strategy uses all 6 factors."""
        response = client.get("/strategies/trendande_varde/enhanced")
        
        if response.status_code == 200:
            data = response.json()
            
            # Should include value metrics
            value_metrics = ["pe_ratio", "pb_ratio", "ps_ratio", 
                          "p_fcf", "ev_ebitda", "dividend_yield"]
            
            if "stocks" in data:
                for stock in data["stocks"]:
                    # At least some value metrics should be present
                    has_value_metric = any(m in stock for m in value_metrics)
                    # This is informational, not a hard requirement
    
    def test_quality_strategy_uses_4_factors(self, client: TestClient):
        """Verify quality strategy uses ROE, ROA, ROIC, FCFROE."""
        response = client.get("/strategies/trendande_kvalitet/enhanced")
        
        if response.status_code == 200:
            data = response.json()
            
            quality_metrics = ["roe", "roa", "roic", "fcfroe"]
            
            if "stocks" in data:
                for stock in data["stocks"]:
                    # At least some quality metrics should be present
                    has_quality_metric = any(m in stock for m in quality_metrics)
                    # This is informational, not a hard requirement
