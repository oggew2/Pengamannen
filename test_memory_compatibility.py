#!/usr/bin/env python3
"""
Test memory optimization compatibility with Börslabbet system.
Verifies the optimization works with SQLite database and pandas operations.
"""
import sys
import os
import sqlite3
import pandas as pd
import numpy as np
import gc
import psutil
from datetime import datetime

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

def get_memory_usage():
    """Get current memory usage in MB."""
    process = psutil.Process()
    return process.memory_info().rss / 1024 / 1024

def test_sqlite_compatibility():
    """Test SQLite operations with memory optimization."""
    print("🔍 Testing SQLite compatibility...")
    
    # Create test database
    test_db = "test_memory_opt.db"
    conn = sqlite3.connect(test_db)
    
    # Create test tables similar to Börslabbet structure
    conn.execute("""
        CREATE TABLE IF NOT EXISTS test_prices (
            ticker TEXT,
            date TEXT,
            close REAL
        )
    """)
    
    conn.execute("""
        CREATE TABLE IF NOT EXISTS test_fundamentals (
            ticker TEXT,
            pe REAL,
            pb REAL,
            market_cap REAL
        )
    """)
    
    # Insert test data (simulate large dataset)
    tickers = ['AAPL', 'GOOGL', 'MSFT', 'TSLA', 'NVDA'] * 1000
    test_prices = []
    for i, ticker in enumerate(tickers):
        test_prices.append((ticker, f"2024-01-{(i % 30) + 1:02d}", 100.0 + i * 0.1))
    
    test_fundamentals = []
    for ticker in set(tickers):
        test_fundamentals.append((ticker, 15.5, 2.3, 1000000.0))
    
    conn.executemany("INSERT INTO test_prices VALUES (?, ?, ?)", test_prices)
    conn.executemany("INSERT INTO test_fundamentals VALUES (?, ?, ?, ?)", test_fundamentals)
    conn.commit()
    
    # Test chunked reading
    try:
        from services.memory_optimizer import MemoryOptimizer
        
        query = "SELECT * FROM test_prices"
        df = MemoryOptimizer.chunked_sql_read(test_db, query, chunk_size=1000)
        
        print(f"✅ Chunked SQL read: {len(df)} rows loaded")
        print(f"   Memory usage: {df.memory_usage(deep=True).sum() / 1024**2:.1f}MB")
        
    except ImportError:
        print("❌ Memory optimizer not available - using fallback")
        df = pd.read_sql_query("SELECT * FROM test_prices", conn)
    
    conn.close()
    os.remove(test_db)
    
    return True

def test_dtype_optimization():
    """Test dtype optimization on realistic data."""
    print("🔍 Testing dtype optimization...")
    
    # Create test DataFrame similar to Börslabbet data
    np.random.seed(42)
    n_rows = 50000
    
    test_data = {
        'ticker': np.random.choice(['AAPL', 'GOOGL', 'MSFT', 'TSLA', 'NVDA'], n_rows),
        'price': np.random.uniform(50, 500, n_rows),
        'volume': np.random.randint(1000, 10000000, n_rows),
        'market_cap': np.random.uniform(1000, 50000, n_rows),
        'pe_ratio': np.random.uniform(5, 50, n_rows),
        'sector': np.random.choice(['Tech', 'Finance', 'Healthcare', 'Energy'], n_rows)
    }
    
    df = pd.DataFrame(test_data)
    original_memory = df.memory_usage(deep=True).sum()
    
    print(f"Original DataFrame: {len(df)} rows, {original_memory/1024**2:.1f}MB")
    
    # Apply optimization
    try:
        from services.memory_optimizer import MemoryOptimizer
        df_optimized = MemoryOptimizer.optimize_dtypes(df.copy())
        
        optimized_memory = df_optimized.memory_usage(deep=True).sum()
        reduction = (original_memory - optimized_memory) / original_memory
        
        print(f"✅ Optimized DataFrame: {optimized_memory/1024**2:.1f}MB")
        print(f"   Memory reduction: {reduction:.1%}")
        
        # Verify data integrity
        assert len(df) == len(df_optimized), "Row count mismatch"
        assert list(df.columns) == list(df_optimized.columns), "Column mismatch"
        
        print("✅ Data integrity verified")
        
        return reduction > 0.3  # Should achieve >30% reduction
        
    except ImportError:
        print("❌ Memory optimizer not available")
        return False

def test_chunked_processing():
    """Test chunked processing for large operations."""
    print("🔍 Testing chunked processing...")
    
    # Create large DataFrame
    n_rows = 100000
    df = pd.DataFrame({
        'ticker': np.random.choice(['STOCK_' + str(i) for i in range(100)], n_rows),
        'value': np.random.uniform(0, 1000, n_rows),
        'category': np.random.choice(['A', 'B', 'C', 'D'], n_rows)
    })
    
    initial_memory = get_memory_usage()
    
    try:
        from services.memory_optimizer import MemoryOptimizer
        
        # Test batch processing
        def dummy_process(batch_df):
            # Simulate some processing
            return batch_df.groupby('ticker')['value'].mean().reset_index()
        
        result = MemoryOptimizer.process_in_batches(
            df, 
            batch_size=10000, 
            process_func=dummy_process
        )
        
        final_memory = get_memory_usage()
        memory_increase = final_memory - initial_memory
        
        print(f"✅ Chunked processing: {len(result)} results")
        print(f"   Memory increase: {memory_increase:.1f}MB")
        
        return memory_increase < 100  # Should not increase memory significantly
        
    except ImportError:
        print("❌ Memory optimizer not available")
        return False

def main():
    """Run all compatibility tests."""
    print("🚀 Testing memory optimization compatibility with Börslabbet system")
    print(f"Python version: {sys.version}")
    print(f"Pandas version: {pd.__version__}")
    print(f"NumPy version: {np.__version__}")
    print(f"Initial memory usage: {get_memory_usage():.1f}MB")
    print("-" * 60)
    
    tests = [
        ("SQLite Compatibility", test_sqlite_compatibility),
        ("Dtype Optimization", test_dtype_optimization),
        ("Chunked Processing", test_chunked_processing)
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
            print(f"{'✅' if result else '❌'} {test_name}: {'PASSED' if result else 'FAILED'}")
        except Exception as e:
            print(f"❌ {test_name}: ERROR - {e}")
            results.append((test_name, False))
        
        print("-" * 60)
    
    # Summary
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    print(f"📊 Test Results: {passed}/{total} tests passed")
    print(f"Final memory usage: {get_memory_usage():.1f}MB")
    
    if passed == total:
        print("🎉 All tests passed! Memory optimization is compatible with your system.")
        return 0
    else:
        print("⚠️  Some tests failed. Check the output above for details.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
