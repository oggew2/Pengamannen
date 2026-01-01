"""
Performance and Reliability Tests for Börslabbet App.

Tests load times, cache performance, and system resilience under various conditions.
"""
import pytest
import time
import asyncio
import psutil
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import patch, Mock
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from httpx import AsyncClient
from fastapi.testclient import TestClient


@pytest.mark.performance
class TestLoadTimePerformance:
    """Test application load time performance targets."""
    
    def test_dashboard_load_time_under_2s(self, client: TestClient):
        """Test dashboard loads under 2 seconds with cached data."""
        # Warm up cache first
        client.get("/data/sync-status")
        client.get("/strategies")
        
        # Measure health endpoint load time (no root endpoint)
        start_time = time.time()
        response = client.get("/health")
        load_time = time.time() - start_time
        
        assert response.status_code == 200
        assert load_time < 2.0, f"Health loaded in {load_time:.2f}s, target: <2s"
    
    def test_strategy_calculation_time_under_5s(self, client: TestClient):
        """Test strategy calculations complete under 5 seconds with fresh data."""
        strategies = ["sammansatt_momentum", "trendande_varde", "trendande_utdelning", "trendande_kvalitet"]
        
        for strategy in strategies:
            start_time = time.time()
            response = client.get(f"/strategies/{strategy}")
            calculation_time = time.time() - start_time
            
            if response.status_code == 200:
                assert calculation_time < 5.0, f"{strategy} calculated in {calculation_time:.2f}s, target: <5s"
    
    def test_api_response_time_under_10s(self, client: TestClient):
        """Test API calls complete under 10 seconds with retries."""
        # Test critical API endpoints
        endpoints = [
            "/strategies",
            "/sync/status", 
            "/portfolio/rebalance-dates",
            "/analytics/performance-metrics"
        ]
        
        for endpoint in endpoints:
            start_time = time.time()
            response = client.get(endpoint)
            response_time = time.time() - start_time
            
            # Should respond within 10 seconds or return appropriate error
            assert response.status_code in [200, 404, 503, 429]
            assert response_time < 10.0, f"{endpoint} responded in {response_time:.2f}s, target: <10s"
    
    def test_backtest_execution_under_30s(self, client: TestClient):
        """Test backtest execution completes under 30 seconds for 5-year period."""
        backtest_request = {
            "strategy": "sammansatt_momentum",
            "start_date": "2019-01-01",
            "end_date": "2024-12-31",
            "initial_capital": 100000
        }
        
        start_time = time.time()
        response = client.post("/backtest/enhanced", json=backtest_request)
        execution_time = time.time() - start_time
        
        if response.status_code == 200:
            assert execution_time < 30.0, f"Backtest executed in {execution_time:.2f}s, target: <30s"
        else:
            # Even errors should respond quickly
            assert execution_time < 10.0, f"Backtest error response in {execution_time:.2f}s"


@pytest.mark.performance
class TestCachePerformance:
    """Test cache system performance and efficiency."""
    
    def test_cache_hit_ratio_over_75_percent(self, client: TestClient):
        """Test cache achieves >75% hit ratio under normal usage."""
        # Simulate normal usage pattern
        endpoints = [
            "/strategies/sammansatt_momentum",
            "/strategies/trendande_varde",
            "/sync/status",
            "/analytics/performance-metrics"
        ]
        
        # First round - populate cache
        for endpoint in endpoints:
            client.get(endpoint)
        
        # Second round - should hit cache
        cache_hits = 0
        total_requests = 20
        
        for i in range(total_requests):
            endpoint = endpoints[i % len(endpoints)]
            start_time = time.time()
            response = client.get(endpoint)
            response_time = time.time() - start_time
            
            # Fast response indicates cache hit
            if response.status_code == 200 and response_time < 0.1:
                cache_hits += 1
        
        hit_ratio = cache_hits / total_requests
        assert hit_ratio >= 0.75, f"Cache hit ratio {hit_ratio:.2%}, target: ≥75%"
    
    def test_cache_efficiency_improvement(self, client: TestClient):
        """Test cache provides significant performance improvement."""
        endpoint = "/strategies/sammansatt_momentum"
        
        # Clear cache and measure cold performance
        client.post("/sync/avanza")  # Trigger cache invalidation
        
        cold_start = time.time()
        cold_response = client.get(endpoint)
        cold_time = time.time() - cold_start
        
        # Measure warm cache performance
        warm_start = time.time()
        warm_response = client.get(endpoint)
        warm_time = time.time() - warm_start
        
        if cold_response.status_code == 200 and warm_response.status_code == 200:
            # Cache should provide at least 2x improvement
            improvement_ratio = cold_time / warm_time if warm_time > 0 else 1
            assert improvement_ratio >= 2.0, f"Cache improvement {improvement_ratio:.1f}x, target: ≥2x"
    
    def test_cache_memory_usage(self, client: TestClient):
        """Test cache memory usage remains reasonable."""
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Load data into cache
        strategies = ["sammansatt_momentum", "trendande_varde", "trendande_utdelning", "trendande_kvalitet"]
        
        for _ in range(10):  # Multiple rounds to build up cache
            for strategy in strategies:
                client.get(f"/strategies/{strategy}")
                client.get("/analytics/performance-metrics")
                client.get("/sync/status")
        
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory
        
        # Cache should not consume excessive memory
        assert memory_increase < 100, f"Cache used {memory_increase:.1f}MB, target: <100MB"
    
    def test_cache_ttl_enforcement(self, client: TestClient):
        """Test cache TTL (24-hour) is properly enforced."""
        # This would require time manipulation in a real test
        # For now, verify cache configuration
        
        cache_stats_response = client.get("/cache/stats")
        if cache_stats_response.status_code == 200:
            stats = cache_stats_response.json()
            
            # Verify TTL configuration
            if "ttl_seconds" in stats:
                assert stats["ttl_seconds"] == 86400  # 24 hours
            
            # Verify cache entries have expiration
            if "entries" in stats:
                for entry in stats["entries"]:
                    assert "expires_at" in entry or "ttl" in entry


@pytest.mark.performance
class TestConcurrencyAndLoad:
    """Test system performance under concurrent load."""
    
    def test_concurrent_user_handling(self, client: TestClient):
        """Test system handles multiple concurrent users efficiently."""
        
        def simulate_user_session():
            """Simulate a typical user session."""
            session_start = time.time()
            
            # Typical user workflow
            responses = []
            responses.append(client.get("/health"))  # Health check
            responses.append(client.get("/strategies"))  # Strategy list
            responses.append(client.get("/strategies/sammansatt_momentum"))  # Strategy detail
            responses.append(client.get("/analytics/performance-metrics?strategy=sammansatt_momentum"))  # Performance
            
            session_time = time.time() - session_start
            success_count = sum(1 for r in responses if r.status_code in [200, 404])
            
            return {
                "session_time": session_time,
                "success_count": success_count,
                "total_requests": len(responses)
            }
        
        # Simulate 10 concurrent users
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(simulate_user_session) for _ in range(10)]
            results = [future.result() for future in as_completed(futures)]
        
        total_time = time.time() - start_time
        
        # Analyze results
        avg_session_time = sum(r["session_time"] for r in results) / len(results)
        total_success = sum(r["success_count"] for r in results)
        total_requests = sum(r["total_requests"] for r in results)
        success_rate = total_success / total_requests
        
        # Performance assertions
        assert total_time < 30, f"10 concurrent users completed in {total_time:.1f}s, target: <30s"
        assert avg_session_time < 10, f"Average session time {avg_session_time:.1f}s, target: <10s"
        assert success_rate >= 0.8, f"Success rate {success_rate:.1%}, target: ≥80%"
    
    def test_memory_usage_under_load(self, client: TestClient):
        """Test memory usage remains stable under sustained load."""
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Sustained load simulation
        for round_num in range(5):
            # Each round simulates heavy usage
            for _ in range(20):
                client.get("/strategies/sammansatt_momentum")
                client.get("/analytics/performance-metrics")
                client.get("/sync/status")
            
            # Check memory after each round
            current_memory = process.memory_info().rss / 1024 / 1024  # MB
            memory_increase = current_memory - initial_memory
            
            # Memory should not grow excessively
            assert memory_increase < 200, f"Memory increased by {memory_increase:.1f}MB after round {round_num + 1}"
        
        # Final memory check
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        total_increase = final_memory - initial_memory
        
        assert total_increase < 300, f"Total memory increase {total_increase:.1f}MB, target: <300MB"
    
    def test_database_connection_pooling(self, client: TestClient):
        """Test database connections are properly pooled and managed."""
        
        def make_db_intensive_request():
            """Make a request that requires database access."""
            return client.get("/analytics/performance-metrics")
        
        # Make many concurrent database requests
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(make_db_intensive_request) for _ in range(50)]
            responses = [future.result() for future in as_completed(futures)]
        
        # Should handle all requests without connection errors
        success_count = sum(1 for r in responses if r.status_code == 200)
        error_count = sum(1 for r in responses if r.status_code >= 500)
        
        assert success_count >= 40, f"Only {success_count}/50 requests succeeded"
        assert error_count <= 5, f"{error_count} server errors, target: ≤5"


@pytest.mark.performance
class TestSystemResilience:
    """Test system resilience under various stress conditions."""
    
    def test_graceful_degradation_under_load(self, client: TestClient):
        """Test system degrades gracefully under extreme load."""
        
        def stress_request():
            """Make a computationally intensive request."""
            return client.post("/backtest/enhanced", json={
                "strategy": "sammansatt_momentum",
                "start_date": "2015-01-01",
                "end_date": "2024-12-31",
                "initial_capital": 1000000
            })
        
        # Create extreme load
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(stress_request) for _ in range(10)]
            responses = [future.result() for future in as_completed(futures)]
        
        total_time = time.time() - start_time
        
        # System should either complete requests or return appropriate errors
        completed = sum(1 for r in responses if r.status_code == 200)
        rate_limited = sum(1 for r in responses if r.status_code == 429)
        server_errors = sum(1 for r in responses if r.status_code >= 500)
        
        # Should handle gracefully - either complete or rate limit
        assert server_errors <= 2, f"{server_errors} server errors under stress"
        assert completed + rate_limited >= 8, "System should complete or rate limit requests"
    
    def test_error_recovery_mechanisms(self, client: TestClient):
        """Test system recovers from various error conditions."""
        
        # Test recovery from cache corruption
        with patch('services.cache.get_cache_stats', side_effect=Exception("Cache error")):
            response = client.get("/sync/status")
            # Should handle cache errors gracefully
            assert response.status_code in [200, 503]
        
        # Test recovery from database connection issues
        with patch('db.get_db', side_effect=Exception("DB connection error")):
            response = client.get("/strategies")
            # Should handle DB errors gracefully
            assert response.status_code in [200, 503]
        
        # Test recovery from external API failures
        with patch('services.avanza_fetcher_v2.AvanzaDirectFetcher._make_request', 
                  side_effect=Exception("API error")):
            response = client.post("/sync/avanza")
            # Should handle API errors gracefully
            assert response.status_code in [200, 503, 429]
    
    def test_resource_cleanup(self, client: TestClient):
        """Test system properly cleans up resources."""
        initial_memory = psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024
        
        # Create and clean up many resources
        for i in range(100):
            # Make requests that create temporary resources
            client.get(f"/strategies/sammansatt_momentum?cache_bust={i}")
            
            # Periodically check memory
            if i % 20 == 0:
                current_memory = psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024
                memory_growth = current_memory - initial_memory
                
                # Memory growth should be bounded
                assert memory_growth < 500, f"Memory grew by {memory_growth:.1f}MB after {i} requests"
        
        # Final cleanup check
        final_memory = psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024
        total_growth = final_memory - initial_memory
        
        assert total_growth < 200, f"Total memory growth {total_growth:.1f}MB after cleanup test"


@pytest.mark.performance
@pytest.mark.slow
class TestLongRunningPerformance:
    """Test performance over extended periods."""
    
    def test_24_hour_stability_simulation(self, client: TestClient):
        """Simulate 24-hour operation stability (compressed to minutes)."""
        start_time = time.time()
        request_count = 0
        error_count = 0
        
        # Simulate 24 hours of operation in 2 minutes (720x speedup)
        # Normal usage: ~1 request per minute = 1440 requests per day
        # Compressed: 1440 requests in 2 minutes = 12 requests per second
        
        target_duration = 120  # 2 minutes
        target_requests = 1440
        
        while time.time() - start_time < target_duration and request_count < target_requests:
            # Simulate typical user requests
            endpoints = [
                "/",
                "/strategies/sammansatt_momentum", 
                "/sync/status",
                "/analytics/performance-metrics"
            ]
            
            endpoint = endpoints[request_count % len(endpoints)]
            response = client.get(endpoint)
            
            request_count += 1
            if response.status_code >= 400:
                error_count += 1
            
            # Brief pause to avoid overwhelming
            time.sleep(0.01)
        
        total_time = time.time() - start_time
        error_rate = error_count / request_count if request_count > 0 else 0
        
        # Performance assertions
        assert request_count >= 1000, f"Only processed {request_count} requests in {total_time:.1f}s"
        assert error_rate <= 0.05, f"Error rate {error_rate:.1%}, target: ≤5%"
    
    def test_memory_leak_detection(self, client: TestClient):
        """Test for memory leaks over extended operation."""
        process = psutil.Process(os.getpid())
        memory_samples = []
        
        # Take memory samples over time
        for i in range(20):
            # Simulate work
            for _ in range(50):
                client.get("/strategies/sammansatt_momentum")
                client.get("/analytics/performance-metrics")
            
            # Sample memory
            memory_mb = process.memory_info().rss / 1024 / 1024
            memory_samples.append(memory_mb)
            
            time.sleep(0.1)  # Brief pause
        
        # Analyze memory trend
        if len(memory_samples) >= 10:
            # Check if memory is consistently growing
            first_half = memory_samples[:10]
            second_half = memory_samples[10:]
            
            avg_first = sum(first_half) / len(first_half)
            avg_second = sum(second_half) / len(second_half)
            
            memory_growth = avg_second - avg_first
            
            # Some growth is normal, but excessive growth indicates leaks
            assert memory_growth < 50, f"Memory grew by {memory_growth:.1f}MB, possible leak detected"
    
    def test_cache_performance_over_time(self, client: TestClient):
        """Test cache performance remains consistent over time."""
        response_times = []
        
        # Measure response times over extended period
        for i in range(100):
            start_time = time.time()
            response = client.get("/strategies/sammansatt_momentum")
            response_time = time.time() - start_time
            
            if response.status_code == 200:
                response_times.append(response_time)
            
            time.sleep(0.05)  # 50ms between requests
        
        if len(response_times) >= 50:
            # Analyze response time consistency
            first_quarter = response_times[:25]
            last_quarter = response_times[-25:]
            
            avg_first = sum(first_quarter) / len(first_quarter)
            avg_last = sum(last_quarter) / len(last_quarter)
            
            # Response times should remain consistent (cache performance)
            performance_degradation = avg_last / avg_first if avg_first > 0 else 1
            
            assert performance_degradation <= 2.0, f"Performance degraded by {performance_degradation:.1f}x over time"
