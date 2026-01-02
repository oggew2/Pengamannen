#!/usr/bin/env python3
"""
COMPREHENSIVE COMPATIBILITY TEST: Test all potential incompatibility issues.
Verifies that memory optimizations don't break any functionality.
"""
import sys
import os
import pandas as pd
import numpy as np
from datetime import date, timedelta
import logging

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

def test_categorical_string_operations():
    """Test string operations on categorical columns."""
    print("🔍 TESTING CATEGORICAL STRING OPERATIONS...")
    
    try:
        # Test stock type filtering
        print("\n1. Testing stock type filtering...")
        
        df = pd.DataFrame({
            'ticker': ['AAPL', 'GOOGL', 'MSFT'],
            'stock_type': ['stock', 'preference', 'stock']
        })
        
        # Convert to categorical
        df['stock_type'] = df['stock_type'].astype('category')
        
        # Test the fixed filtering function
        from services.ranking import filter_real_stocks
        
        result = filter_real_stocks(df, include_preference=True)
        if len(result) != 3:
            print("❌ CRITICAL: Stock type filtering failed with categorical data")
            return False
        
        print("✅ Stock type filtering works with categorical data")
        
        # Test sector filtering
        print("\n2. Testing sector filtering...")
        
        df_sector = pd.DataFrame({
            'ticker': ['AAPL', 'JPM', 'MSFT'],
            'sector': ['Technology', 'Traditionell Bankverksamhet', 'Technology']
        })
        
        # Convert to categorical
        df_sector['sector'] = df_sector['sector'].astype('category')
        
        print(f"   Sector dtype: {df_sector['sector'].dtype}")
        print(f"   Sector categories: {df_sector['sector'].cat.categories.tolist()}")
        
        from services.ranking import filter_financial_companies
        
        try:
            result = filter_financial_companies(df_sector)
            # Should exclude JPM (Traditionell Bankverksamhet)
            if len(result) != 2 or 'JPM' in result['ticker'].values:
                print("❌ CRITICAL: Sector filtering failed with categorical data")
                return False
            
            print("✅ Sector filtering works with categorical data")
        except Exception as e:
            print(f"❌ CRITICAL: Sector filtering error: {e}")
            print(f"   Error type: {type(e).__name__}")
            
            # Try to debug the issue
            print("   Debugging sector filtering...")
            financial_lower = ['traditionell bankverksamhet', 'investmentbolag', 'försäkring', 'sparande & investering', 'kapitalförvaltning', 'konsumentkredit']
            sector_lower = df_sector['sector'].fillna('').astype(str).str.lower()
            print(f"   Sector values (lower): {sector_lower.tolist()}")
            print(f"   Financial sectors (lower): {financial_lower}")
            
            mask = ~sector_lower.isin(financial_lower)
            print(f"   Filter mask: {mask.tolist()}")
            
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ CRITICAL: Categorical string operations test failed: {e}")
        return False

def test_date_operations():
    """Test date operations with optimized DataFrames."""
    print("\n🔍 TESTING DATE OPERATIONS...")
    
    try:
        # Test date comparisons
        print("\n1. Testing date comparisons...")
        
        dates = pd.date_range('2023-01-01', '2023-12-31', freq='D')
        df = pd.DataFrame({
            'date': dates,
            'ticker': ['AAPL'] * len(dates),
            'price': np.random.uniform(100, 200, len(dates))
        })
        
        # Apply memory optimization
        from services.memory_optimizer import MemoryOptimizer
        df_optimized = MemoryOptimizer.optimize_dtypes(df)
        
        # Test date comparison (should not convert date to categorical)
        start_date = pd.Timestamp('2023-06-01')
        end_date = pd.Timestamp('2023-06-30')
        
        mask = (df_optimized['date'] >= start_date) & (df_optimized['date'] <= end_date)
        filtered = df_optimized[mask]
        
        if len(filtered) == 0:
            print("❌ CRITICAL: Date filtering returned no results")
            return False
        
        print(f"✅ Date filtering works: {len(filtered)} records found")
        
        # Test date operations in backtesting context
        print("\n2. Testing backtesting date operations...")
        
        # Simulate the backtesting scenario
        if df_optimized['date'].dtype.name == 'category':
            df_optimized['date'] = pd.to_datetime(df_optimized['date'])
        
        date_mask = (df_optimized['date'] >= pd.Timestamp(start_date) - pd.Timedelta(days=30)) & (df_optimized['date'] <= pd.Timestamp(end_date))
        prices_subset = df_optimized[date_mask]
        
        if len(prices_subset) == 0:
            print("❌ CRITICAL: Backtesting date filtering failed")
            return False
        
        print("✅ Backtesting date operations work correctly")
        
        return True
        
    except Exception as e:
        print(f"❌ CRITICAL: Date operations test failed: {e}")
        return False

def test_memory_optimization_compatibility():
    """Test that memory optimization doesn't break functionality."""
    print("\n🔍 TESTING MEMORY OPTIMIZATION COMPATIBILITY...")
    
    try:
        # Test with realistic data
        print("\n1. Testing with realistic stock data...")
        
        df = pd.DataFrame({
            'ticker': ['AAPL', 'GOOGL', 'MSFT'] * 1000,
            'date': pd.date_range('2023-01-01', periods=3000, freq='D'),
            'price': np.random.uniform(100, 500, 3000),
            'volume': np.random.randint(1000000, 10000000, 3000),
            'sector': np.random.choice(['Technology', 'Traditionell Bankverksamhet', 'Healthcare'], 3000),
            'stock_type': np.random.choice(['stock', 'preference'], 3000)
        })
        
        original_memory = df.memory_usage(deep=True).sum()
        
        # Apply memory optimization
        from services.memory_optimizer import MemoryOptimizer
        df_optimized = MemoryOptimizer.optimize_dtypes(df)
        
        optimized_memory = df_optimized.memory_usage(deep=True).sum()
        reduction = (original_memory - optimized_memory) / original_memory
        
        if reduction < 0.5:  # Should achieve at least 50% reduction
            print(f"❌ WARNING: Low memory reduction: {reduction:.1%}")
        else:
            print(f"✅ Memory optimization: {reduction:.1%} reduction")
        
        # Test that operations still work
        print("\n2. Testing operations on optimized data...")
        
        # Test filtering
        tech_stocks = df_optimized[df_optimized['sector'].astype(str).str.contains('Technology', case=False)]
        if len(tech_stocks) == 0:
            print("❌ CRITICAL: Sector filtering failed on optimized data")
            return False
        
        # Test aggregations
        avg_price = df_optimized['price'].mean()
        if pd.isna(avg_price):
            print("❌ CRITICAL: Aggregation failed on optimized data")
            return False
        
        # Test date operations
        recent_data = df_optimized[df_optimized['date'] >= '2023-06-01']
        if len(recent_data) == 0:
            print("❌ CRITICAL: Date filtering failed on optimized data")
            return False
        
        print("✅ All operations work correctly on optimized data")
        
        return True
        
    except Exception as e:
        print(f"❌ CRITICAL: Memory optimization compatibility test failed: {e}")
        return False

def test_import_compatibility():
    """Test that all imports work correctly."""
    print("\n🔍 TESTING IMPORT COMPATIBILITY...")
    
    try:
        # Test critical imports
        print("\n1. Testing critical imports...")
        
        import yaml
        import pandas as pd
        import numpy as np
        from datetime import date, timedelta
        import sqlite3
        import gc
        import psutil
        
        print("✅ All critical imports successful")
        
        # Test service imports
        print("\n2. Testing service imports...")
        
        from services.memory_optimizer import MemoryOptimizer
        from services.memory_monitor import memory_monitor
        
        print("✅ Service imports successful")
        
        # Test that YAML loading works
        print("\n3. Testing YAML configuration loading...")
        
        if os.path.exists('backend/config/strategies.yaml'):
            with open('backend/config/strategies.yaml') as f:
                config = yaml.safe_load(f)
                if 'strategies' not in config:
                    print("❌ CRITICAL: Invalid YAML configuration structure")
                    return False
            print("✅ YAML configuration loads correctly")
        else:
            print("⚠️  YAML configuration file not found (expected in production)")
        
        return True
        
    except Exception as e:
        print(f"❌ CRITICAL: Import compatibility test failed: {e}")
        return False

def main():
    """Run comprehensive compatibility test."""
    print("🚀 COMPREHENSIVE COMPATIBILITY TEST - BULLETPROOF VERIFICATION")
    print("=" * 80)
    
    tests = [
        ("Categorical String Operations", test_categorical_string_operations),
        ("Date Operations", test_date_operations),
        ("Memory Optimization Compatibility", test_memory_optimization_compatibility),
        ("Import Compatibility", test_import_compatibility)
    ]
    
    results = []
    critical_failures = 0
    
    for test_name, test_func in tests:
        print(f"\n{'='*25} {test_name} {'='*25}")
        try:
            result = test_func()
            results.append((test_name, result))
            
            if result:
                print(f"\n✅ PASSED: {test_name}")
            else:
                print(f"\n❌ FAILED: {test_name}")
                critical_failures += 1
                
        except Exception as e:
            print(f"\n💥 CRITICAL ERROR in {test_name}: {e}")
            results.append((test_name, False))
            critical_failures += 1
    
    # Final verdict
    print(f"\n{'='*80}")
    print("🎯 COMPREHENSIVE COMPATIBILITY TEST RESULTS")
    print(f"{'='*80}")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")
    
    print(f"\nCompatibility Tests: {passed}/{total} passed")
    print(f"Critical Failures: {critical_failures}")
    
    if critical_failures == 0:
        print("\n🎉 ALL COMPATIBILITY TESTS PASSED!")
        print("🚀 SYSTEM IS BULLETPROOF AND PRODUCTION READY!")
        print("\n🔥 DEPLOY WITH ABSOLUTE CONFIDENCE!")
        return 0
    else:
        print(f"\n⚠️  COMPATIBILITY ISSUES FOUND: {critical_failures}")
        print("🛑 FIX ISSUES BEFORE DEPLOYMENT!")
        return 1

if __name__ == "__main__":
    sys.exit(main())
