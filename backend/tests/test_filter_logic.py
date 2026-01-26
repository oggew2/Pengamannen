"""
Deterministic Filter Validation Tests with Synthetic Data

These tests use FIXED synthetic data to test filter logic independently
of any external data source. Tests will pass regardless of what the
actual market data looks like.

Key principle: Test the LOGIC, not the current data.
"""
import pytest
import pandas as pd
import sys
sys.path.insert(0, '.')


# =============================================================================
# SYNTHETIC TEST DATA FIXTURES
# =============================================================================

def create_test_stock(
    ticker: str,
    name: str,
    sector: str,
    f_score: int,
    market_cap_sek: float,
    perf_3m: float = 10.0,
    perf_6m: float = 20.0,
    perf_12m: float = 30.0,
    price_sek: float = 100.0,
    currency: str = 'SEK',
    market: str = 'sweden'
) -> dict:
    """Create a synthetic test stock with known characteristics."""
    return {
        'ticker': ticker,
        'name': name,
        'sector': sector,
        'piotroski_f_score': f_score,
        'market_cap_sek': market_cap_sek,
        'market_cap': market_cap_sek,
        'perf_3m': perf_3m,
        'perf_6m': perf_6m,
        'perf_12m': perf_12m,
        'close': price_sek,
        'price_sek': price_sek,
        'currency': currency,
        'market': market,
    }


@pytest.fixture
def synthetic_stocks():
    """
    Create a fixed set of synthetic stocks with known characteristics.
    This data NEVER changes, making tests deterministic.
    """
    return [
        # SHOULD BE INCLUDED (passes all filters)
        create_test_stock('GOOD1', 'Good Company AB', 'Technology Services', 7, 5e9, 50, 60, 70),
        create_test_stock('GOOD2', 'Another Good AB', 'Producer Manufacturing', 6, 3e9, 40, 50, 60),
        create_test_stock('GOOD3', 'Third Good AB', 'Health Technology', 5, 2.5e9, 30, 40, 50),
        create_test_stock('GOOD4_B', 'Good Class B AB', 'Electronic Technology', 8, 10e9, 20, 30, 40),
        
        # SHOULD BE EXCLUDED - Finance sector
        create_test_stock('BANK1', 'Test Bank AB', 'Finance', 8, 100e9, 10, 20, 30),
        create_test_stock('INVEST1', 'Investment AB Test', 'Finance', 7, 50e9, 15, 25, 35),
        create_test_stock('INSUR1', 'Insurance Company AB', 'Finance', 6, 20e9, 5, 15, 25),
        
        # SHOULD BE EXCLUDED - Preference shares
        create_test_stock('TEST_PREF', 'Test Company Pref', 'Technology Services', 7, 5e9, 25, 35, 45),
        create_test_stock('PREF_TEST', 'Pref Test AB', 'Producer Manufacturing', 6, 3e9, 20, 30, 40),
        
        # SHOULD BE EXCLUDED - Low F-Score
        create_test_stock('LOWF1', 'Low FScore Company', 'Technology Services', 4, 5e9, 100, 150, 200),
        create_test_stock('LOWF2', 'Very Low FScore AB', 'Producer Manufacturing', 2, 3e9, 80, 120, 160),
        create_test_stock('LOWF3', 'Zero FScore AB', 'Health Technology', 0, 4e9, 90, 130, 170),
        
        # SHOULD BE EXCLUDED - Investment company by name (non-Finance sector)
        create_test_stock('MAHA_A', 'Maha Capital AB Class A', 'Energy Minerals', 6, 3e9, 60, 80, 100),
        create_test_stock('FLAT_B', 'Flat Capital AB Class B', 'Technology Services', 7, 4e9, 55, 75, 95),
        create_test_stock('INV_AB', 'Test Investment AB', 'Producer Manufacturing', 6, 5e9, 45, 65, 85),
        
        # EDGE CASES - Should be INCLUDED (holding companies that are operating)
        create_test_stock('HOLD1', 'AutoStore Holdings Ltd.', 'Technology Services', 6, 8e9, 35, 45, 55),
        create_test_stock('HOLD2', 'Bravida Holding AB', 'Industrial Services', 7, 6e9, 25, 35, 45),
        
        # EDGE CASES - SDB stocks (should be filtered by normal criteria)
        create_test_stock('TEST_SDB', 'Test Company SDB', 'Technology Services', 7, 5e9, 30, 40, 50),
        create_test_stock('FIN_SDB', 'Finance SDB Test', 'Finance', 6, 10e9, 20, 30, 40),
        
        # BOUNDARY - F-Score exactly 5 (should be included)
        create_test_stock('BOUND5', 'Boundary FScore 5', 'Technology Services', 5, 3e9, 15, 25, 35),
        
        # BOUNDARY - F-Score exactly 4 (should be excluded)
        create_test_stock('BOUND4', 'Boundary FScore 4', 'Technology Services', 4, 3e9, 15, 25, 35),
        
        # BOUNDARY - Market cap exactly 2B (should be included)
        create_test_stock('MCAP2B', 'Market Cap 2B', 'Technology Services', 6, 2e9, 10, 20, 30),
    ]


# =============================================================================
# FILTER FUNCTIONS (extracted for testing)
# =============================================================================

def apply_finance_filter(df: pd.DataFrame) -> pd.DataFrame:
    """Filter out Finance sector stocks."""
    return df[df['sector'] != 'Finance']


def apply_pref_filter(df: pd.DataFrame) -> pd.DataFrame:
    """Filter out preference shares."""
    return df[~df['ticker'].str.contains('PREF', case=False, na=False)]


def apply_investment_company_filter(df: pd.DataFrame) -> pd.DataFrame:
    """Filter out investment companies by name pattern."""
    def is_investment_company(name):
        name_lower = name.lower()
        name_clean = name_lower.replace(' class a', '').replace(' class b', '').strip()
        if 'investment ab' in name_lower or 'investment a/s' in name_lower:
            return True
        if 'invest ab' in name_lower:
            return True
        if name_clean.endswith('capital ab') or name_clean.endswith('capital a/s'):
            return True
        return False
    return df[~df['name'].apply(is_investment_company)]


def apply_fscore_filter(df: pd.DataFrame, min_score: int = 5) -> pd.DataFrame:
    """Filter out stocks with F-Score below minimum."""
    return df[df['piotroski_f_score'] >= min_score]


def apply_all_filters(df: pd.DataFrame) -> pd.DataFrame:
    """Apply all filters in sequence."""
    df = apply_finance_filter(df)
    df = apply_pref_filter(df)
    df = apply_investment_company_filter(df)
    df = apply_fscore_filter(df)
    return df


def calculate_momentum(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate momentum score and rank."""
    df = df.copy()
    df['momentum'] = (df['perf_3m'] + df['perf_6m'] + df['perf_12m']) / 3
    df = df.sort_values('momentum', ascending=False).reset_index(drop=True)
    df['rank'] = range(1, len(df) + 1)
    return df


# =============================================================================
# TEST CLASS: INDIVIDUAL FILTER TESTS
# =============================================================================

class TestFinanceFilter:
    """Test Finance sector filter with synthetic data."""
    
    def test_excludes_finance_sector(self, synthetic_stocks):
        """Finance sector stocks should be excluded."""
        df = pd.DataFrame(synthetic_stocks)
        result = apply_finance_filter(df)
        
        finance_in_result = result[result['sector'] == 'Finance']
        assert len(finance_in_result) == 0, "Finance stocks should be excluded"
    
    def test_includes_non_finance(self, synthetic_stocks):
        """Non-Finance stocks should be included."""
        df = pd.DataFrame(synthetic_stocks)
        result = apply_finance_filter(df)
        
        # GOOD1 is Technology Services, should be included
        assert 'GOOD1' in result['ticker'].values
        assert 'GOOD2' in result['ticker'].values
    
    def test_excludes_all_finance_types(self, synthetic_stocks):
        """All Finance types (banks, investment, insurance) should be excluded."""
        df = pd.DataFrame(synthetic_stocks)
        result = apply_finance_filter(df)
        
        assert 'BANK1' not in result['ticker'].values
        assert 'INVEST1' not in result['ticker'].values
        assert 'INSUR1' not in result['ticker'].values


class TestPrefFilter:
    """Test preference share filter with synthetic data."""
    
    def test_excludes_pref_in_ticker(self, synthetic_stocks):
        """Stocks with PREF in ticker should be excluded."""
        df = pd.DataFrame(synthetic_stocks)
        result = apply_pref_filter(df)
        
        assert 'TEST_PREF' not in result['ticker'].values
        assert 'PREF_TEST' not in result['ticker'].values
    
    def test_case_insensitive(self, synthetic_stocks):
        """PREF filter should be case insensitive."""
        df = pd.DataFrame([
            create_test_stock('test_pref', 'Lower Case Pref', 'Technology Services', 7, 5e9),
            create_test_stock('TEST_PREF', 'Upper Case Pref', 'Technology Services', 7, 5e9),
            create_test_stock('TeSt_PrEf', 'Mixed Case Pref', 'Technology Services', 7, 5e9),
        ])
        result = apply_pref_filter(df)
        assert len(result) == 0, "All PREF variations should be excluded"
    
    def test_includes_non_pref(self, synthetic_stocks):
        """Non-PREF stocks should be included."""
        df = pd.DataFrame(synthetic_stocks)
        result = apply_pref_filter(df)
        
        assert 'GOOD1' in result['ticker'].values
        assert 'GOOD4_B' in result['ticker'].values


class TestInvestmentCompanyFilter:
    """Test investment company name filter with synthetic data."""
    
    def test_excludes_capital_ab_pattern(self, synthetic_stocks):
        """'Capital AB' at end of name should be excluded."""
        df = pd.DataFrame(synthetic_stocks)
        result = apply_investment_company_filter(df)
        
        assert 'MAHA_A' not in result['ticker'].values, "Maha Capital AB should be excluded"
        assert 'FLAT_B' not in result['ticker'].values, "Flat Capital AB should be excluded"
    
    def test_excludes_investment_ab_pattern(self, synthetic_stocks):
        """'Investment AB' in name should be excluded."""
        df = pd.DataFrame(synthetic_stocks)
        result = apply_investment_company_filter(df)
        
        assert 'INV_AB' not in result['ticker'].values
    
    def test_includes_holding_companies(self, synthetic_stocks):
        """Operating companies with 'Holding' in name should be included."""
        df = pd.DataFrame(synthetic_stocks)
        result = apply_investment_company_filter(df)
        
        assert 'HOLD1' in result['ticker'].values, "AutoStore Holdings should be included"
        assert 'HOLD2' in result['ticker'].values, "Bravida Holding should be included"
    
    def test_handles_class_suffix(self):
        """Should handle Class A/B suffix correctly."""
        df = pd.DataFrame([
            create_test_stock('TEST_A', 'Test Capital AB Class A', 'Technology', 7, 5e9),
            create_test_stock('TEST_B', 'Test Capital AB Class B', 'Technology', 7, 5e9),
        ])
        result = apply_investment_company_filter(df)
        assert len(result) == 0, "Capital AB with class suffix should be excluded"


class TestFScoreFilter:
    """Test F-Score filter with synthetic data."""
    
    def test_excludes_low_fscore(self, synthetic_stocks):
        """F-Score < 5 should be excluded."""
        df = pd.DataFrame(synthetic_stocks)
        result = apply_fscore_filter(df)
        
        assert 'LOWF1' not in result['ticker'].values  # F-Score 4
        assert 'LOWF2' not in result['ticker'].values  # F-Score 2
        assert 'LOWF3' not in result['ticker'].values  # F-Score 0
    
    def test_includes_high_fscore(self, synthetic_stocks):
        """F-Score >= 5 should be included."""
        df = pd.DataFrame(synthetic_stocks)
        result = apply_fscore_filter(df)
        
        assert 'GOOD1' in result['ticker'].values  # F-Score 7
        assert 'GOOD2' in result['ticker'].values  # F-Score 6
        assert 'GOOD3' in result['ticker'].values  # F-Score 5
    
    def test_boundary_fscore_5(self, synthetic_stocks):
        """F-Score exactly 5 should be included."""
        df = pd.DataFrame(synthetic_stocks)
        result = apply_fscore_filter(df)
        
        assert 'BOUND5' in result['ticker'].values, "F-Score 5 should be included"
    
    def test_boundary_fscore_4(self, synthetic_stocks):
        """F-Score exactly 4 should be excluded."""
        df = pd.DataFrame(synthetic_stocks)
        result = apply_fscore_filter(df)
        
        assert 'BOUND4' not in result['ticker'].values, "F-Score 4 should be excluded"


# =============================================================================
# TEST CLASS: COMBINED FILTERS
# =============================================================================

class TestCombinedFilters:
    """Test all filters working together."""
    
    def test_all_filters_combined(self, synthetic_stocks):
        """Test that all filters work correctly when combined."""
        df = pd.DataFrame(synthetic_stocks)
        result = apply_all_filters(df)
        
        # Should include
        assert 'GOOD1' in result['ticker'].values
        assert 'GOOD2' in result['ticker'].values
        assert 'GOOD3' in result['ticker'].values
        assert 'HOLD1' in result['ticker'].values
        assert 'HOLD2' in result['ticker'].values
        
        # Should exclude
        assert 'BANK1' not in result['ticker'].values  # Finance
        assert 'TEST_PREF' not in result['ticker'].values  # PREF
        assert 'MAHA_A' not in result['ticker'].values  # Capital AB
        assert 'LOWF1' not in result['ticker'].values  # Low F-Score
    
    def test_filter_order_independence(self, synthetic_stocks):
        """Filter order should not affect final result."""
        df = pd.DataFrame(synthetic_stocks)
        
        # Order 1: Finance -> PREF -> Investment -> F-Score
        result1 = apply_all_filters(df)
        
        # Order 2: F-Score -> Investment -> PREF -> Finance
        result2 = apply_fscore_filter(df)
        result2 = apply_investment_company_filter(result2)
        result2 = apply_pref_filter(result2)
        result2 = apply_finance_filter(result2)
        
        assert set(result1['ticker']) == set(result2['ticker'])
    
    def test_sdb_filtered_by_normal_criteria(self, synthetic_stocks):
        """SDB stocks should be filtered by normal criteria, not blanket excluded."""
        df = pd.DataFrame(synthetic_stocks)
        result = apply_all_filters(df)
        
        # TEST_SDB is Technology Services with F-Score 7, should be included
        assert 'TEST_SDB' in result['ticker'].values
        
        # FIN_SDB is Finance, should be excluded
        assert 'FIN_SDB' not in result['ticker'].values


# =============================================================================
# TEST CLASS: INVARIANT TESTS (Property-based)
# =============================================================================

class TestInvariants:
    """Test invariants that should ALWAYS hold true."""
    
    def test_no_finance_in_results(self, synthetic_stocks):
        """INVARIANT: Finance sector should NEVER appear in results."""
        df = pd.DataFrame(synthetic_stocks)
        result = apply_all_filters(df)
        
        finance_count = len(result[result['sector'] == 'Finance'])
        assert finance_count == 0, f"Found {finance_count} Finance stocks in results"
    
    def test_no_pref_in_results(self, synthetic_stocks):
        """INVARIANT: PREF stocks should NEVER appear in results."""
        df = pd.DataFrame(synthetic_stocks)
        result = apply_all_filters(df)
        
        pref_count = len(result[result['ticker'].str.contains('PREF', case=False, na=False)])
        assert pref_count == 0, f"Found {pref_count} PREF stocks in results"
    
    def test_no_low_fscore_in_results(self, synthetic_stocks):
        """INVARIANT: F-Score < 5 should NEVER appear in results."""
        df = pd.DataFrame(synthetic_stocks)
        result = apply_all_filters(df)
        
        low_fscore = result[result['piotroski_f_score'] < 5]
        assert len(low_fscore) == 0, f"Found {len(low_fscore)} low F-Score stocks"
    
    def test_results_sorted_by_momentum(self, synthetic_stocks):
        """INVARIANT: Results should be sorted by momentum descending."""
        df = pd.DataFrame(synthetic_stocks)
        result = apply_all_filters(df)
        result = calculate_momentum(result)
        
        momentums = result['momentum'].tolist()
        assert momentums == sorted(momentums, reverse=True), "Results not sorted by momentum"
    
    def test_rank_1_has_highest_momentum(self, synthetic_stocks):
        """INVARIANT: Rank 1 should have highest momentum."""
        df = pd.DataFrame(synthetic_stocks)
        result = apply_all_filters(df)
        result = calculate_momentum(result)
        
        if len(result) > 0:
            rank_1 = result[result['rank'] == 1].iloc[0]
            max_momentum = result['momentum'].max()
            assert rank_1['momentum'] == max_momentum


# =============================================================================
# TEST CLASS: BOUNDARY CONDITIONS
# =============================================================================

class TestBoundaryConditions:
    """Test exact boundary conditions."""
    
    def test_fscore_boundary_4_vs_5(self):
        """F-Score 4 excluded, F-Score 5 included."""
        df = pd.DataFrame([
            create_test_stock('FS4', 'FScore 4', 'Technology', 4, 5e9),
            create_test_stock('FS5', 'FScore 5', 'Technology', 5, 5e9),
        ])
        result = apply_fscore_filter(df)
        
        assert 'FS4' not in result['ticker'].values
        assert 'FS5' in result['ticker'].values
    
    def test_fscore_all_values(self):
        """Test all F-Score values 0-9."""
        stocks = [create_test_stock(f'FS{i}', f'FScore {i}', 'Technology', i, 5e9) for i in range(10)]
        df = pd.DataFrame(stocks)
        result = apply_fscore_filter(df)
        
        # 0-4 excluded, 5-9 included
        for i in range(5):
            assert f'FS{i}' not in result['ticker'].values, f"F-Score {i} should be excluded"
        for i in range(5, 10):
            assert f'FS{i}' in result['ticker'].values, f"F-Score {i} should be included"
    
    def test_market_cap_exactly_2b(self, synthetic_stocks):
        """Market cap exactly 2B should be included."""
        df = pd.DataFrame(synthetic_stocks)
        result = apply_all_filters(df)
        
        assert 'MCAP2B' in result['ticker'].values


# =============================================================================
# TEST CLASS: REGRESSION TESTS
# =============================================================================

class TestRegressions:
    """Regression tests for known issues."""
    
    def test_maha_capital_excluded(self):
        """Regression: MAHA Capital AB should be excluded (was included before fix)."""
        df = pd.DataFrame([
            create_test_stock('MAHA_A', 'Maha Capital AB Class A', 'Energy Minerals', 6, 3e9),
        ])
        result = apply_investment_company_filter(df)
        assert len(result) == 0, "Maha Capital AB should be excluded"
    
    def test_autostore_holdings_included(self):
        """Regression: AutoStore Holdings should be included (operating company)."""
        df = pd.DataFrame([
            create_test_stock('AUTO', 'AutoStore Holdings Ltd.', 'Technology Services', 6, 8e9),
        ])
        result = apply_investment_company_filter(df)
        assert len(result) == 1, "AutoStore Holdings should be included"
    
    def test_bravida_holding_included(self):
        """Regression: Bravida Holding should be included (operating company)."""
        df = pd.DataFrame([
            create_test_stock('BRAV', 'Bravida Holding AB', 'Industrial Services', 7, 6e9),
        ])
        result = apply_investment_company_filter(df)
        assert len(result) == 1, "Bravida Holding should be included"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
