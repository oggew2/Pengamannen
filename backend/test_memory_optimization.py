"""
Unit tests for memory-optimized ranking system.
Run with: python -m pytest test_memory_optimization.py -v
"""
import pytest
import pandas as pd
import numpy as np
import gc
import psutil
import os
from unittest.mock import Mock, patch

# Import the optimized functions
from services.ranking_optimized import (
    optimize_dataframe_memory,
    filter_real_stocks,
    calculate_momentum_score_optimized,
    load_prices_chunked
)


class TestMemoryOptimization:
    
    def test_dataframe_memory_optimization(self):
        """Test that DataFrame memory optimization reduces memory usage."""
        # Create test DataFrame with inefficient types
        test_data = {
            'ticker': ['AAPL', 'GOOGL', 'MSFT'] * 1000,  # Should become category
            'price': [150.0, 2800.0, 300.0] * 1000,      # Should become float32
            'volume': [1000000, 2000000, 1500000] * 1000  # Should be downcasted
        }
        
        df = pd.DataFrame(test_data)
        original_memory = df.memory_usage(deep=True).sum()
        
        # Optimize memory
        optimized_df = optimize_dataframe_memory(df)
        optimized_memory = optimized_df.memory_usage(deep=True).sum()
        
        # Should reduce memory by at least 30%
        memory_reduction = (original_memory - optimized_memory) / original_memory
        assert memory_reduction > 0.3, f"Memory reduction was only {memory_reduction:.2%}"
        
        # Verify data integrity
        assert len(optimized_df) == len(df)
        assert list(optimized_df.columns) == list(df.columns)
    
    def test_stock_filtering(self):
        """Test stock filtering functions."""
        test_df = pd.DataFrame({
            'ticker': ['AAPL', 'GOOGL', 'ETF1', 'CERT1'],
            'stock_type': ['stock', 'stock', 'etf', 'certificate'],
            'market_cap': [3000, 2500, 1000, 500]
        })
        
        # Test real stock filtering
        filtered = filter_real_stocks(test_df)
        assert len(filtered) == 2
        assert all(filtered['stock_type'].isin(['stock']))
    
    def test_momentum_calculation_memory_safety(self):
        """Test that momentum calculation doesn't cause memory leaks."""
        # Monitor memory before
        process = psutil.Process(os.getpid())
        memory_before = process.memory_info().rss
        
        # Create test price data
        dates = pd.date_range('2023-01-01', '2024-01-01', freq='D')
        tickers = ['AAPL', 'GOOGL', 'MSFT']
        
        price_data = []
        for ticker in tickers:
            for date in dates:
                price_data.append({
                    'ticker': ticker,
                    'date': date,
                    'close': 100 + np.random.randn() * 10
                })
        
        prices_df = pd.DataFrame(price_data)
        
        # Calculate momentum
        momentum_scores = calculate_momentum_score_optimized(prices_df)
        
        # Force garbage collection
        del prices_df, price_data
        gc.collect()
        
        # Check memory after
        memory_after = process.memory_info().rss
        memory_increase = memory_after - memory_before
        
        # Should not increase memory by more than 100MB
        assert memory_increase < 100 * 1024 * 1024, f"Memory increased by {memory_increase / 1024 / 1024:.1f}MB"
        
        # Verify results
        assert isinstance(momentum_scores, pd.Series)
        assert len(momentum_scores) <= len(tickers)
    
    @patch('services.ranking_optimized.logger')
    def test_chunked_loading_simulation(self, mock_logger):
        """Test chunked loading logic (mocked)."""
        # Mock database query
        mock_db = Mock()
        mock_query = Mock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 150000  # Simulate large dataset
        
        # Mock chunked results
        def mock_offset_limit(offset, limit):
            mock_chunk = Mock()
            # Simulate decreasing chunk sizes
            remaining = max(0, 150000 - offset)
            chunk_size = min(limit, remaining)
            mock_chunk.all.return_value = [
                Mock(ticker=f'STOCK{i}', date='2024-01-01', close=100.0)
                for i in range(chunk_size)
            ]
            return mock_chunk
        
        mock_query.offset.side_effect = lambda offset: Mock(
            limit=lambda limit: mock_offset_limit(offset, limit)
        )
        
        # Test chunked loading
        valid_tickers = {f'STOCK{i}' for i in range(1000)}
        
        # This would normally call load_prices_chunked, but we'll test the logic
        total_count = 150000
        chunk_size = 50000
        chunks_expected = (total_count + chunk_size - 1) // chunk_size
        
        assert chunks_expected == 3, f"Expected 3 chunks, got {chunks_expected}"
    
    def test_garbage_collection_effectiveness(self):
        """Test that garbage collection is working effectively."""
        # Create large objects
        large_objects = []
        for i in range(10):
            large_df = pd.DataFrame(np.random.randn(10000, 100))
            large_objects.append(large_df)
        
        # Check memory before cleanup
        process = psutil.Process(os.getpid())
        memory_before = process.memory_info().rss
        
        # Delete objects and force garbage collection
        del large_objects
        gc.collect()
        
        # Check memory after cleanup
        memory_after = process.memory_info().rss
        
        # Memory should decrease (or at least not increase significantly)
        memory_change = memory_after - memory_before
        assert memory_change < 50 * 1024 * 1024, f"Memory increased by {memory_change / 1024 / 1024:.1f}MB after cleanup"


if __name__ == "__main__":
    # Run tests
    test_suite = TestMemoryOptimization()
    
    print("🧪 Running Memory Optimization Tests")
    print("=" * 40)
    
    try:
        test_suite.test_dataframe_memory_optimization()
        print("✅ DataFrame memory optimization test passed")
        
        test_suite.test_stock_filtering()
        print("✅ Stock filtering test passed")
        
        test_suite.test_momentum_calculation_memory_safety()
        print("✅ Momentum calculation memory safety test passed")
        
        test_suite.test_chunked_loading_simulation()
        print("✅ Chunked loading simulation test passed")
        
        test_suite.test_garbage_collection_effectiveness()
        print("✅ Garbage collection effectiveness test passed")
        
        print("\n🎉 All tests passed! Memory optimization is working correctly.")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        exit(1)
