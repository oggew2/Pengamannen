#!/usr/bin/env python3
"""
Comprehensive system test for Börslabbet App.
Run: cd backend && python tests/test_system.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import date, timedelta
import pandas as pd

def test_imports():
    """Test all critical imports work."""
    print("\n=== TEST: Imports ===")
    
    from main import app
    from models import Stock, DailyPrice, Fundamentals, StrategySignal
    from services.avanza_fetcher_v2 import avanza_sync, AvanzaDirectFetcher
    from services.ranking import (
        calculate_momentum_score, calculate_value_score,
        calculate_dividend_score, calculate_quality_score,
        calculate_piotroski_f_score, filter_by_min_market_cap
    )
    from services.ranking_cache import compute_all_rankings, get_cached_rankings
    from services.backtesting import backtest_strategy
    from services.smart_cache import smart_cache
    from services.historical_tracker import HistoricalTracker
    from jobs.scheduler import sync_job, start_scheduler
    
    print("✓ All imports successful")
    return True


def test_database_integrity():
    """Test database tables and data integrity."""
    print("\n=== TEST: Database Integrity ===")
    
    from db import SessionLocal
    from models import Stock, DailyPrice, Fundamentals, StrategySignal
    from sqlalchemy import func
    
    db = SessionLocal()
    
    # Check tables exist and have data
    stocks = db.query(Stock).count()
    prices = db.query(DailyPrice).count()
    funds = db.query(Fundamentals).count()
    signals = db.query(StrategySignal).count()
    
    print(f"  Stocks: {stocks}")
    print(f"  DailyPrices: {prices}")
    print(f"  Fundamentals: {funds}")
    print(f"  StrategySignals: {signals}")
    
    assert stocks > 0, "No stocks in database"
    assert prices > 0, "No prices in database"
    assert funds > 0, "No fundamentals in database"
    
    # Check no duplicate prices (composite PK)
    from sqlalchemy import text
    dup_prices = db.execute(text(
        "SELECT ticker, date, COUNT(*) as cnt FROM daily_prices GROUP BY ticker, date HAVING cnt > 1"
    )).fetchall()
    assert len(dup_prices) == 0, f"Found {len(dup_prices)} duplicate prices"
    
    # Check price date range
    latest_price = db.query(func.max(DailyPrice.date)).scalar()
    oldest_price = db.query(func.min(DailyPrice.date)).scalar()
    print(f"  Price range: {oldest_price} to {latest_price}")
    
    # Check fundamentals freshness
    latest_fund = db.query(func.max(Fundamentals.fetched_date)).scalar()
    print(f"  Latest fundamentals: {latest_fund}")
    
    # Check avanza_id preserved
    sample = db.query(Stock).filter(Stock.avanza_id != None).first()
    assert sample and sample.avanza_id, "avanza_id not preserved"
    print(f"  Sample avanza_id: {sample.ticker} = {sample.avanza_id}")
    
    db.close()
    print("✓ Database integrity OK")
    return True


def test_strategy_calculations():
    """Test all strategy scoring functions."""
    print("\n=== TEST: Strategy Calculations ===")
    
    from db import SessionLocal
    from models import DailyPrice, Fundamentals, Stock
    from services.ranking import (
        calculate_momentum_score, calculate_value_score,
        calculate_dividend_score, calculate_quality_score,
        calculate_piotroski_f_score, calculate_momentum_with_quality_filter,
        filter_by_min_market_cap, filter_real_stocks
    )
    
    db = SessionLocal()
    
    # Load data
    prices = pd.read_sql(db.query(DailyPrice).statement, db.bind)
    funds_raw = db.query(Fundamentals).all()
    stocks = {s.ticker: s for s in db.query(Stock).all()}
    
    fund_df = pd.DataFrame([{
        'ticker': f.ticker, 'pe': f.pe, 'pb': f.pb, 'ps': f.ps,
        'p_fcf': f.p_fcf, 'ev_ebitda': f.ev_ebitda,
        'dividend_yield': f.dividend_yield, 'roe': f.roe,
        'roa': f.roa, 'roic': f.roic, 'fcfroe': f.fcfroe,
        'payout_ratio': f.payout_ratio,
        'market_cap': stocks[f.ticker].market_cap_msek if f.ticker in stocks else 0,
        'stock_type': getattr(stocks.get(f.ticker), 'stock_type', 'stock')
    } for f in funds_raw])
    
    print(f"  Loaded {len(prices)} prices, {len(fund_df)} fundamentals")
    
    # Test filters
    filtered = filter_real_stocks(fund_df)
    print(f"  After real stock filter: {len(filtered)}")
    
    filtered = filter_by_min_market_cap(filtered)
    print(f"  After 2B SEK filter: {len(filtered)}")
    assert len(filtered) > 100, "Too few stocks after filtering"
    
    # Test momentum
    momentum = calculate_momentum_score(prices)
    print(f"  Momentum scores: {len(momentum)}")
    assert len(momentum) > 100, "Too few momentum scores"
    assert momentum.max() < 10, "Momentum scores too high (likely error)"
    
    # Test F-Score
    fscore = calculate_piotroski_f_score(fund_df)
    print(f"  F-Scores: {len(fscore)}, range {fscore.min()}-{fscore.max()}")
    assert fscore.min() >= 0 and fscore.max() <= 9, "F-Score out of range"
    
    # Test momentum with quality filter
    mom_filtered = calculate_momentum_with_quality_filter(prices, fund_df)
    print(f"  Momentum+F-Score: {len(mom_filtered)} stocks")
    assert len(mom_filtered) == 10, "Should return top 10"
    
    # Test value score
    value = calculate_value_score(fund_df, prices)
    print(f"  Value scores: {len(value)} stocks")
    assert len(value) == 10, "Should return top 10"
    
    # Test dividend score
    dividend = calculate_dividend_score(fund_df, prices)
    print(f"  Dividend scores: {len(dividend)} stocks")
    assert len(dividend) == 10, "Should return top 10"
    
    # Test quality score
    quality = calculate_quality_score(fund_df, prices)
    print(f"  Quality scores: {len(quality)} stocks")
    assert len(quality) == 10, "Should return top 10"
    
    db.close()
    print("✓ Strategy calculations OK")
    return True


def test_ranking_cache():
    """Test ranking cache system."""
    print("\n=== TEST: Ranking Cache ===")
    
    from db import SessionLocal
    from models import StrategySignal
    from services.ranking_cache import compute_all_rankings, get_cached_rankings
    
    db = SessionLocal()
    
    # Test compute
    result = compute_all_rankings(db)
    print(f"  Computed: {result}")
    assert result.get('total_rankings', 0) == 40, "Should compute 40 rankings (10 x 4 strategies)"
    
    # Test cache retrieval
    for strategy in ['sammansatt_momentum', 'trendande_varde', 'trendande_utdelning', 'trendande_kvalitet']:
        cached = get_cached_rankings(db, strategy)
        assert len(cached) == 10, f"{strategy} should have 10 cached rankings"
        print(f"  {strategy}: {len(cached)} cached")
    
    # Test stale detection (yesterday)
    yesterday = date.today() - timedelta(days=1)
    stale = db.query(StrategySignal).filter(
        StrategySignal.calculated_date == yesterday
    ).count()
    assert stale == 0, "Should not have yesterday's rankings"
    
    # Test unknown strategy
    unknown = get_cached_rankings(db, 'nonexistent')
    assert len(unknown) == 0, "Unknown strategy should return empty"
    
    db.close()
    print("✓ Ranking cache OK")
    return True


def test_backtesting():
    """Test backtesting functionality."""
    print("\n=== TEST: Backtesting ===")
    
    from db import SessionLocal
    from services.backtesting import backtest_strategy
    import yaml
    
    with open('config/strategies.yaml') as f:
        strategies = yaml.safe_load(f)['strategies']
    
    db = SessionLocal()
    
    for name, config in strategies.items():
        result = backtest_strategy(
            name, 
            date(2024, 1, 1), 
            date(2024, 12, 31), 
            db, 
            config
        )
        
        assert 'error' not in result, f"{name} backtest failed: {result.get('error')}"
        assert 'total_return_pct' in result, f"{name} missing total_return_pct"
        
        print(f"  {name}: {result['total_return_pct']:.1f}% return")
    
    db.close()
    print("✓ Backtesting OK")
    return True


def test_smart_cache():
    """Test smart cache functionality."""
    print("\n=== TEST: Smart Cache ===")
    
    from services.smart_cache import smart_cache
    
    # Test stats
    stats = smart_cache.get_cache_stats()
    print(f"  Cache entries: {stats['total_entries']}")
    print(f"  Valid entries: {stats['valid_entries']}")
    
    # Test set/get
    smart_cache.set("test_endpoint", {"key": "value"}, {"data": "test"}, ttl_hours=1)
    cached = smart_cache.get("test_endpoint", {"key": "value"})
    assert cached and cached.get('data') == 'test', "Cache set/get failed"
    
    # Test delete
    smart_cache.delete("test_endpoint", {"key": "value"})
    deleted = smart_cache.get("test_endpoint", {"key": "value"})
    assert deleted is None, "Cache delete failed"
    
    print("✓ Smart cache OK")
    return True


def test_api_endpoints():
    """Test API endpoints (requires running server)."""
    print("\n=== TEST: API Endpoints ===")
    
    try:
        import requests
    except ImportError:
        print("  Skipping (requests not installed)")
        return True
    
    base = "http://localhost:8000"
    
    tests = [
        ("GET", "/strategies", lambda r: len(r.json()) == 4),
        ("GET", "/strategies/sammansatt_momentum", lambda r: len(r.json()) == 10),
        ("GET", "/strategies/trendande_varde", lambda r: len(r.json()) == 10),
        ("GET", "/strategies/trendande_utdelning", lambda r: len(r.json()) == 10),
        ("GET", "/strategies/trendande_kvalitet", lambda r: len(r.json()) == 10),
        ("GET", "/data/status/detailed", lambda r: r.status_code == 200),
        ("GET", "/cache/stats", lambda r: 'smart_cache' in r.json()),
    ]
    
    for method, path, check in tests:
        try:
            r = requests.request(method, f"{base}{path}", timeout=10)
            if r.status_code == 200 and check(r):
                print(f"  ✓ {method} {path}")
            else:
                print(f"  ✗ {method} {path} - status={r.status_code}")
                return False
        except requests.exceptions.ConnectionError:
            print(f"  Skipping {path} (server not running)")
            return True
    
    print("✓ API endpoints OK")
    return True


def test_data_freshness():
    """Test data freshness checks."""
    print("\n=== TEST: Data Freshness ===")
    
    from db import SessionLocal
    from models import Fundamentals, DailyPrice
    from sqlalchemy import func
    
    db = SessionLocal()
    
    # Check fundamentals age
    latest_fund = db.query(func.max(Fundamentals.fetched_date)).scalar()
    if latest_fund:
        age = (date.today() - latest_fund).days
        print(f"  Fundamentals age: {age} days")
        assert age <= 7, f"Fundamentals too old ({age} days)"
    
    # Check price age
    latest_price = db.query(func.max(DailyPrice.date)).scalar()
    if latest_price:
        age = (date.today() - latest_price).days
        print(f"  Price age: {age} days")
        # Allow weekend gap
        assert age <= 5, f"Prices too old ({age} days)"
    
    db.close()
    print("✓ Data freshness OK")
    return True


def run_all_tests():
    """Run all tests."""
    print("=" * 60)
    print("BÖRSLABBET APP - COMPREHENSIVE SYSTEM TEST")
    print("=" * 60)
    
    tests = [
        ("Imports", test_imports),
        ("Database Integrity", test_database_integrity),
        ("Strategy Calculations", test_strategy_calculations),
        ("Ranking Cache", test_ranking_cache),
        ("Backtesting", test_backtesting),
        ("Smart Cache", test_smart_cache),
        ("Data Freshness", test_data_freshness),
        ("API Endpoints", test_api_endpoints),
    ]
    
    results = []
    for name, test_fn in tests:
        try:
            passed = test_fn()
            results.append((name, passed, None))
        except Exception as e:
            results.append((name, False, str(e)))
            print(f"✗ {name} FAILED: {e}")
    
    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    
    passed = sum(1 for _, p, _ in results if p)
    total = len(results)
    
    for name, p, err in results:
        status = "✓ PASS" if p else f"✗ FAIL: {err}"
        print(f"  {name}: {status}")
    
    print(f"\n{passed}/{total} tests passed")
    
    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
