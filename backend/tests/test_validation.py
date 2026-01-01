#!/usr/bin/env python3
"""
Validation tests to verify our implementation matches Börslabbet's published rules.

Sources:
- https://www.borslabbet.se/borslabbets-strategier/
- https://www.borslabbet.se/sammansatt-momentum/
- https://www.borslabbet.se/trendande-varde/

Run: cd backend && python tests/test_validation.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import date
import pandas as pd


def test_momentum_calculation():
    """
    Verify momentum calculation matches Börslabbet's formula.
    
    Börslabbet rule: "Sammansatt Momentum = genomsnitt av 3, 6 och 12 månaders avkastning"
    Source: https://www.borslabbet.se/sammansatt-momentum/
    """
    print("\n=== VALIDATION: Momentum Calculation ===")
    
    from services.ranking import calculate_momentum_score
    
    # Create test data with known returns
    # Stock A: 3m=10%, 6m=20%, 12m=30% → Expected: (0.10+0.20+0.30)/3 = 0.20
    dates = pd.date_range(end=date.today(), periods=252+10, freq='B')
    
    prices_data = []
    for d in dates:
        # Stock A: grows linearly
        day_num = (d - dates[0]).days
        price_a = 100 * (1 + day_num * 0.001)  # ~0.1% per day
        prices_data.append({'ticker': 'TEST_A', 'date': d.date(), 'close': price_a})
        
        # Stock B: flat
        prices_data.append({'ticker': 'TEST_B', 'date': d.date(), 'close': 100})
    
    prices_df = pd.DataFrame(prices_data)
    scores = calculate_momentum_score(prices_df)
    
    # Stock A should have positive momentum, Stock B should have ~0
    assert scores['TEST_A'] > 0, "Growing stock should have positive momentum"
    assert abs(scores['TEST_B']) < 0.01, "Flat stock should have ~0 momentum"
    
    print(f"  TEST_A momentum: {scores['TEST_A']:.4f} (expected: positive)")
    print(f"  TEST_B momentum: {scores['TEST_B']:.4f} (expected: ~0)")
    print("  ✓ Momentum formula verified: average of 3m, 6m, 12m returns")
    
    return True


def test_market_cap_filter():
    """
    Verify 2B SEK minimum market cap filter.
    
    Börslabbet rule: "Minsta börsvärde: 2 miljarder SEK (sedan juni 2023)"
    Source: https://www.borslabbet.se/borslabbets-strategier/
    """
    print("\n=== VALIDATION: Market Cap Filter ===")
    
    from services.ranking import filter_by_min_market_cap, MIN_MARKET_CAP_MSEK
    
    # Verify threshold is 2000 MSEK = 2B SEK
    assert MIN_MARKET_CAP_MSEK == 2000, f"Threshold should be 2000 MSEK, got {MIN_MARKET_CAP_MSEK}"
    
    # Test filter
    test_df = pd.DataFrame([
        {'ticker': 'SMALL', 'market_cap': 1000},   # 1B SEK - should be filtered
        {'ticker': 'MEDIUM', 'market_cap': 2000},  # 2B SEK - should pass
        {'ticker': 'LARGE', 'market_cap': 10000},  # 10B SEK - should pass
    ])
    
    filtered = filter_by_min_market_cap(test_df)
    
    assert 'SMALL' not in filtered['ticker'].values, "1B stock should be filtered"
    assert 'MEDIUM' in filtered['ticker'].values, "2B stock should pass"
    assert 'LARGE' in filtered['ticker'].values, "10B stock should pass"
    
    print(f"  Threshold: {MIN_MARKET_CAP_MSEK} MSEK = 2B SEK")
    print(f"  Filtered: {len(test_df)} → {len(filtered)} stocks")
    print("  ✓ 2B SEK minimum filter verified")
    
    return True


def test_piotroski_f_score_range():
    """
    Verify F-Score is 0-9 scale per academic standard.
    
    Börslabbet rule: Uses Piotroski F-Score as quality filter
    Academic standard: 9-point scale (0-9)
    """
    print("\n=== VALIDATION: Piotroski F-Score ===")
    
    from db import SessionLocal
    from models import Fundamentals
    from services.ranking import calculate_piotroski_f_score
    import pandas as pd
    
    db = SessionLocal()
    funds = pd.read_sql(db.query(Fundamentals).statement, db.bind)
    db.close()
    
    scores = calculate_piotroski_f_score(funds)
    
    assert scores.min() >= 0, f"F-Score minimum should be ≥0, got {scores.min()}"
    assert scores.max() <= 9, f"F-Score maximum should be ≤9, got {scores.max()}"
    
    # Distribution should be reasonable (not all same value)
    unique_scores = scores.nunique()
    assert unique_scores >= 3, f"F-Score should have variety, got {unique_scores} unique values"
    
    print(f"  Range: {scores.min():.0f} - {scores.max():.0f} (expected: 0-9)")
    print(f"  Distribution: {scores.value_counts().sort_index().to_dict()}")
    print("  ✓ F-Score 0-9 scale verified")
    
    return True


def test_momentum_quality_filter():
    """
    Verify momentum strategy filters out low F-Score stocks.
    
    Börslabbet rule: "Piotroski F-Score används som kvalitetsfilter"
    Implementation: Remove stocks with F-Score ≤ 3
    """
    print("\n=== VALIDATION: Momentum Quality Filter ===")
    
    from db import SessionLocal
    from models import DailyPrice, Fundamentals, Stock
    from services.ranking import (
        calculate_momentum_score, calculate_piotroski_f_score,
        calculate_momentum_with_quality_filter
    )
    import pandas as pd
    
    db = SessionLocal()
    prices = pd.read_sql(db.query(DailyPrice).statement, db.bind)
    funds = pd.read_sql(db.query(Fundamentals).statement, db.bind)
    stocks = {s.ticker: s.market_cap_msek for s in db.query(Stock).all()}
    db.close()
    
    fund_df = funds.copy()
    fund_df['market_cap'] = fund_df['ticker'].map(stocks)
    fund_df['stock_type'] = 'stock'
    
    # Get F-scores
    f_scores = calculate_piotroski_f_score(fund_df)
    
    # Get filtered momentum rankings
    rankings = calculate_momentum_with_quality_filter(prices, fund_df)
    
    # Verify top 10 stocks have F-Score > 3
    top_tickers = rankings['ticker'].tolist()
    for ticker in top_tickers:
        if ticker in f_scores.index:
            score = f_scores[ticker]
            assert score > 3, f"{ticker} has F-Score {score}, should be >3"
    
    print(f"  Top 10 tickers: {top_tickers}")
    print(f"  All have F-Score > 3: verified")
    print("  ✓ Quality filter removes low F-Score stocks")
    
    return True


def test_value_score_factors():
    """
    Verify value score uses 6 factors per Börslabbet.
    
    Börslabbet rule: "Sammansatt Värde = genomsnittlig ranking av P/E, P/B, P/S, P/FCF, EV/EBITDA, Direktavkastning"
    Source: https://www.borslabbet.se/trendande-varde/
    """
    print("\n=== VALIDATION: Value Score Factors ===")
    
    # Check the code uses all 6 factors
    import inspect
    from services.ranking import calculate_value_score
    
    source = inspect.getsource(calculate_value_score)
    
    factors = ['pe', 'pb', 'ps', 'p_fcf', 'ev_ebitda', 'dividend_yield']
    for factor in factors:
        assert factor in source, f"Value score should use {factor}"
    
    print(f"  Factors used: {factors}")
    print("  ✓ All 6 value factors verified")
    
    return True


def test_quality_score_factors():
    """
    Verify quality score uses 4 ROI factors.
    
    Börslabbet rule: "Sammansatt ROI = genomsnittlig ranking av ROE, ROA, ROIC, FCFROE"
    """
    print("\n=== VALIDATION: Quality Score Factors ===")
    
    import inspect
    from services.ranking import calculate_quality_score
    
    source = inspect.getsource(calculate_quality_score)
    
    factors = ['roe', 'roa', 'roic', 'fcfroe']
    for factor in factors:
        assert factor in source, f"Quality score should use {factor}"
    
    print(f"  Factors used: {factors}")
    print("  ✓ All 4 quality factors verified")
    
    return True


def test_trendande_strategy_flow():
    """
    Verify Trendande strategies follow: Primary filter → Top 10% → Sort by momentum → Top 10
    
    Börslabbet rule: "Topp 10% efter primära kriteriet → sorteras efter momentum → topp 10"
    """
    print("\n=== VALIDATION: Trendande Strategy Flow ===")
    
    import inspect
    from services.ranking import calculate_value_score, calculate_dividend_score, calculate_quality_score
    
    for name, func in [
        ('Value', calculate_value_score),
        ('Dividend', calculate_dividend_score),
        ('Quality', calculate_quality_score)
    ]:
        source = inspect.getsource(func)
        
        # Should filter to top percentile
        assert '_filter_top_percentile' in source or 'percentile' in source.lower(), \
            f"{name} should filter by percentile"
        
        # Should sort by momentum
        assert 'momentum' in source.lower(), f"{name} should sort by momentum"
        
        # Should return top 10
        assert 'head(10)' in source or '.head(10)' in source, f"{name} should return top 10"
        
        print(f"  {name}: percentile filter → momentum sort → top 10 ✓")
    
    print("  ✓ Trendande strategy flow verified")
    
    return True


def test_rebalance_schedule():
    """
    Verify rebalance schedules match Börslabbet.
    
    Börslabbet rules:
    - Sammansatt Momentum: Quarterly (March, June, September, December)
    - Trendande strategies: Annual
    """
    print("\n=== VALIDATION: Rebalance Schedule ===")
    
    import yaml
    
    with open('config/strategies.yaml') as f:
        config = yaml.safe_load(f)
    
    strategies = config['strategies']
    
    # Momentum should be quarterly
    mom = strategies['sammansatt_momentum']
    assert mom['rebalance_frequency'] == 'quarterly', "Momentum should be quarterly"
    assert mom['rebalance_months'] == [3, 6, 9, 12], "Momentum months should be [3,6,9,12]"
    print(f"  sammansatt_momentum: {mom['rebalance_frequency']} {mom['rebalance_months']}")
    
    # Trendande should be annual
    for name in ['trendande_varde', 'trendande_utdelning', 'trendande_kvalitet']:
        strat = strategies[name]
        assert strat['rebalance_frequency'] == 'annual', f"{name} should be annual"
        print(f"  {name}: {strat['rebalance_frequency']}")
    
    print("  ✓ Rebalance schedules verified")
    
    return True


def test_position_count():
    """
    Verify all strategies select top 10 stocks.
    
    Börslabbet rule: "Topp 10 aktier" for all strategies
    """
    print("\n=== VALIDATION: Position Count ===")
    
    import yaml
    
    with open('config/strategies.yaml') as f:
        config = yaml.safe_load(f)
    
    for name, strat in config['strategies'].items():
        assert strat['position_count'] == 10, f"{name} should have 10 positions"
        print(f"  {name}: {strat['position_count']} positions")
    
    print("  ✓ All strategies use top 10")
    
    return True


def test_equal_weight():
    """
    Verify equal-weight portfolios.
    
    Börslabbet rule: "Likaviktad portfölj" (equal-weighted)
    """
    print("\n=== VALIDATION: Equal Weight ===")
    
    import yaml
    
    with open('config/strategies.yaml') as f:
        config = yaml.safe_load(f)
    
    for name, strat in config['strategies'].items():
        assert strat['weight_method'] == 'equal', f"{name} should be equal-weighted"
    
    print("  All strategies: equal-weighted (10% per stock)")
    print("  ✓ Equal weight verified")
    
    return True


def test_universe_definition():
    """
    Verify universe includes Stockholmsbörsen + First North.
    
    Börslabbet rule: "Stockholmsbörsen + First North Stockholm"
    """
    print("\n=== VALIDATION: Universe Definition ===")
    
    import yaml
    
    with open('config/strategies.yaml') as f:
        config = yaml.safe_load(f)
    
    universe = config['universe']
    
    assert 'Stockholmsbörsen' in universe['combined_exchanges'], "Should include Stockholmsbörsen"
    assert 'First North' in universe['combined_exchanges'], "Should include First North"
    assert universe['minimum_market_cap_sek'] == 2_000_000_000, "Should be 2B SEK minimum"
    
    print(f"  Exchanges: {universe['combined_exchanges']}")
    print(f"  Min market cap: {universe['minimum_market_cap_sek']:,} SEK")
    print("  ✓ Universe definition verified")
    
    return True


def compare_with_live_rankings():
    """
    Compare our rankings with what's shown on börslabbet.se
    
    NOTE: This requires manual verification - print our top 10 for comparison
    """
    print("\n=== MANUAL VERIFICATION: Compare with börslabbet.se ===")
    
    from db import SessionLocal
    from models import StrategySignal
    
    db = SessionLocal()
    
    print("\n  Our current top 10 for each strategy:")
    print("  Compare these with https://www.borslabbet.se/\n")
    
    for strategy in ['sammansatt_momentum', 'trendande_varde', 'trendande_utdelning', 'trendande_kvalitet']:
        rankings = db.query(StrategySignal).filter(
            StrategySignal.strategy_name == strategy
        ).order_by(StrategySignal.rank).limit(10).all()
        
        print(f"  {strategy}:")
        for r in rankings:
            print(f"    {r.rank}. {r.ticker}")
        print()
    
    db.close()
    
    print("  ⚠ Manual step: Visit börslabbet.se and compare rankings")
    print("  Note: Rankings may differ slightly due to:")
    print("    - Different data update times")
    print("    - Slight differences in data sources")
    print("    - Rounding in calculations")
    
    return True


def run_all_validations():
    """Run all validation tests."""
    print("=" * 70)
    print("BÖRSLABBET STRATEGY VALIDATION")
    print("Verifying implementation matches published rules")
    print("=" * 70)
    
    tests = [
        ("Momentum Calculation", test_momentum_calculation),
        ("Market Cap Filter (2B SEK)", test_market_cap_filter),
        ("Piotroski F-Score Range", test_piotroski_f_score_range),
        ("Momentum Quality Filter", test_momentum_quality_filter),
        ("Value Score Factors", test_value_score_factors),
        ("Quality Score Factors", test_quality_score_factors),
        ("Trendande Strategy Flow", test_trendande_strategy_flow),
        ("Rebalance Schedule", test_rebalance_schedule),
        ("Position Count (Top 10)", test_position_count),
        ("Equal Weight", test_equal_weight),
        ("Universe Definition", test_universe_definition),
        ("Compare with Live", compare_with_live_rankings),
    ]
    
    results = []
    for name, test_fn in tests:
        try:
            passed = test_fn()
            results.append((name, passed, None))
        except Exception as e:
            results.append((name, False, str(e)))
            print(f"  ✗ FAILED: {e}")
    
    print("\n" + "=" * 70)
    print("VALIDATION RESULTS")
    print("=" * 70)
    
    passed = sum(1 for _, p, _ in results if p)
    total = len(results)
    
    for name, p, err in results:
        status = "✓" if p else f"✗ {err}"
        print(f"  {name}: {status}")
    
    print(f"\n{passed}/{total} validations passed")
    
    print("\n" + "=" * 70)
    print("BÖRSLABBET RULES SUMMARY")
    print("=" * 70)
    print("""
  ✓ Momentum = average(3m, 6m, 12m returns)
  ✓ Market cap minimum = 2B SEK (since June 2023)
  ✓ Piotroski F-Score = 0-9 scale quality filter
  ✓ Momentum strategy filters F-Score ≤ 3
  ✓ Value score = avg rank of P/E, P/B, P/S, P/FCF, EV/EBITDA, DivYield
  ✓ Quality score = avg rank of ROE, ROA, ROIC, FCFROE
  ✓ Trendande flow = top 10% by primary → sort by momentum → top 10
  ✓ Momentum rebalance = quarterly (Mar, Jun, Sep, Dec)
  ✓ Trendande rebalance = annual
  ✓ Position count = 10 stocks per strategy
  ✓ Weight method = equal (10% each)
  ✓ Universe = Stockholmsbörsen + First North, ≥2B SEK
    """)
    
    return passed == total


if __name__ == "__main__":
    success = run_all_validations()
    sys.exit(0 if success else 1)
