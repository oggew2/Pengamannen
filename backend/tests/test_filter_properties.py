"""
Property-Based Filter Tests using Hypothesis

These tests verify filter INVARIANTS that must hold for ALL possible inputs,
not just hand-picked examples. Hypothesis generates hundreds of random test
cases to find edge cases we wouldn't think of.

Key invariants tested:
1. Finance sector → NEVER in output
2. PREF in ticker → NEVER in output
3. F-Score < 5 → NEVER in output
4. Investment company pattern → NEVER in output
5. Output sorted by momentum descending
6. No duplicates in output
"""
import pytest
import pandas as pd
from hypothesis import given, settings, assume
from hypothesis import strategies as st
import sys
sys.path.insert(0, '.')


# =============================================================================
# FILTER FUNCTIONS (must match ranking_cache.py exactly)
# =============================================================================

def apply_finance_filter(df: pd.DataFrame) -> pd.DataFrame:
    """Filter out Finance sector stocks."""
    if len(df) == 0:
        return df
    return df[df['sector'] != 'Finance']


def apply_pref_filter(df: pd.DataFrame) -> pd.DataFrame:
    """Filter out preference shares."""
    if len(df) == 0:
        return df
    return df[~df['ticker'].str.contains('PREF', case=False, na=False)]


def is_investment_company(name: str) -> bool:
    """Check if name matches investment company pattern."""
    name_lower = name.lower()
    name_clean = name_lower.replace(' class a', '').replace(' class b', '').strip()
    if 'investment ab' in name_lower or 'investment a/s' in name_lower:
        return True
    if 'invest ab' in name_lower:
        return True
    if name_clean.endswith('capital ab') or name_clean.endswith('capital a/s'):
        return True
    return False


def apply_investment_company_filter(df: pd.DataFrame) -> pd.DataFrame:
    """Filter out investment companies by name pattern."""
    if len(df) == 0:
        return df
    return df[~df['name'].apply(is_investment_company)]


def apply_fscore_filter(df: pd.DataFrame, min_score: int = 5) -> pd.DataFrame:
    """Filter out stocks with F-Score below minimum."""
    if len(df) == 0:
        return df
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
# HYPOTHESIS STRATEGIES - Generate random stock data
# =============================================================================

# Realistic sector names (including Finance which should be filtered)
SECTORS = [
    'Finance', 'Technology Services', 'Producer Manufacturing',
    'Health Technology', 'Electronic Technology', 'Industrial Services',
    'Consumer Services', 'Energy Minerals', 'Retail Trade',
    'Communications', 'Transportation', 'Utilities'
]

# Base ticker patterns
TICKER_BASES = ['TEST', 'ABC', 'XYZ', 'COMP', 'STOCK', 'FIRM', 'CORP']
TICKER_SUFFIXES = ['', '_A', '_B', '_PREF', 'PREF', '_SDB', '_SDR']

# Company name patterns
NAME_PATTERNS = [
    '{base} AB', '{base} Company AB', '{base} Holdings AB',
    '{base} Capital AB', '{base} Investment AB', '{base} Invest AB',
    '{base} Group AB', '{base} Technology AB', '{base} Services AB',
    '{base} Capital AB Class A', '{base} Capital AB Class B',
]


@st.composite
def stock_strategy(draw):
    """Generate a random stock with all required fields."""
    # Generate ticker - sometimes with PREF
    base = draw(st.sampled_from(TICKER_BASES))
    suffix = draw(st.sampled_from(TICKER_SUFFIXES))
    ticker = f"{base}{suffix}"
    
    # Generate name - sometimes matching investment patterns
    name_base = draw(st.text(min_size=3, max_size=10, alphabet='ABCDEFGHIJKLMNOPQRSTUVWXYZ'))
    name_pattern = draw(st.sampled_from(NAME_PATTERNS))
    name = name_pattern.format(base=name_base.capitalize())
    
    # Generate sector - including Finance
    sector = draw(st.sampled_from(SECTORS))
    
    # Generate F-Score (0-9)
    f_score = draw(st.integers(min_value=0, max_value=9))
    
    # Generate market cap (can be below or above 2B)
    market_cap = draw(st.floats(min_value=0.5e9, max_value=100e9))
    
    # Generate performance metrics
    perf_3m = draw(st.floats(min_value=-50, max_value=100))
    perf_6m = draw(st.floats(min_value=-50, max_value=150))
    perf_12m = draw(st.floats(min_value=-50, max_value=200))
    
    return {
        'ticker': ticker,
        'name': name,
        'sector': sector,
        'piotroski_f_score': f_score,
        'market_cap_sek': market_cap,
        'market_cap': market_cap,
        'perf_3m': perf_3m,
        'perf_6m': perf_6m,
        'perf_12m': perf_12m,
        'close': 100.0,
        'price_sek': 100.0,
        'currency': 'SEK',
        'market': 'sweden',
    }


@st.composite
def stock_list_strategy(draw, min_size=1, max_size=50):
    """Generate a list of random stocks."""
    stocks = draw(st.lists(stock_strategy(), min_size=min_size, max_size=max_size))
    return stocks


# =============================================================================
# PROPERTY-BASED TESTS: FILTER INVARIANTS
# =============================================================================

class TestFinanceFilterInvariant:
    """Finance sector must NEVER appear in filtered output."""
    
    @given(stocks=stock_list_strategy())
    @settings(max_examples=200)
    def test_finance_never_in_output(self, stocks):
        """INVARIANT: No Finance sector stock ever passes the filter."""
        df = pd.DataFrame(stocks)
        result = apply_finance_filter(df)
        
        # Count Finance stocks in result
        finance_in_result = result[result['sector'] == 'Finance']
        assert len(finance_in_result) == 0, \
            f"Finance stocks found in output: {finance_in_result['ticker'].tolist()}"
    
    @given(stocks=stock_list_strategy())
    @settings(max_examples=200)
    def test_non_finance_preserved(self, stocks):
        """INVARIANT: Non-Finance stocks are preserved by the filter."""
        df = pd.DataFrame(stocks)
        non_finance_before = set(df[df['sector'] != 'Finance']['ticker'])
        
        result = apply_finance_filter(df)
        non_finance_after = set(result['ticker'])
        
        assert non_finance_before == non_finance_after, \
            f"Non-Finance stocks were incorrectly filtered"


class TestPrefFilterInvariant:
    """PREF in ticker must NEVER appear in filtered output."""
    
    @given(stocks=stock_list_strategy())
    @settings(max_examples=200)
    def test_pref_never_in_output(self, stocks):
        """INVARIANT: No PREF ticker ever passes the filter."""
        df = pd.DataFrame(stocks)
        result = apply_pref_filter(df)
        
        # Check no PREF in any ticker
        pref_in_result = result[result['ticker'].str.contains('PREF', case=False, na=False)]
        assert len(pref_in_result) == 0, \
            f"PREF stocks found in output: {pref_in_result['ticker'].tolist()}"
    
    @given(stocks=stock_list_strategy())
    @settings(max_examples=200)
    def test_non_pref_preserved(self, stocks):
        """INVARIANT: Non-PREF stocks are preserved by the filter."""
        df = pd.DataFrame(stocks)
        non_pref_before = set(df[~df['ticker'].str.contains('PREF', case=False, na=False)]['ticker'])
        
        result = apply_pref_filter(df)
        non_pref_after = set(result['ticker'])
        
        assert non_pref_before == non_pref_after


class TestFScoreFilterInvariant:
    """F-Score < 5 must NEVER appear in filtered output."""
    
    @given(stocks=stock_list_strategy())
    @settings(max_examples=200)
    def test_low_fscore_never_in_output(self, stocks):
        """INVARIANT: No F-Score < 5 ever passes the filter."""
        df = pd.DataFrame(stocks)
        result = apply_fscore_filter(df)
        
        low_fscore = result[result['piotroski_f_score'] < 5]
        assert len(low_fscore) == 0, \
            f"Low F-Score stocks found: {low_fscore[['ticker', 'piotroski_f_score']].to_dict('records')}"
    
    @given(stocks=stock_list_strategy())
    @settings(max_examples=200)
    def test_high_fscore_preserved(self, stocks):
        """INVARIANT: F-Score >= 5 stocks are preserved by the filter."""
        df = pd.DataFrame(stocks)
        high_fscore_before = set(df[df['piotroski_f_score'] >= 5]['ticker'])
        
        result = apply_fscore_filter(df)
        high_fscore_after = set(result['ticker'])
        
        assert high_fscore_before == high_fscore_after
    
    @given(f_score=st.integers(min_value=0, max_value=9))
    @settings(max_examples=100)
    def test_boundary_condition(self, f_score):
        """INVARIANT: F-Score boundary is exactly at 5."""
        df = pd.DataFrame([{
            'ticker': 'TEST', 'name': 'Test', 'sector': 'Tech',
            'piotroski_f_score': f_score, 'market_cap_sek': 5e9,
            'perf_3m': 10, 'perf_6m': 20, 'perf_12m': 30,
        }])
        result = apply_fscore_filter(df)
        
        if f_score >= 5:
            assert len(result) == 1, f"F-Score {f_score} should be included"
        else:
            assert len(result) == 0, f"F-Score {f_score} should be excluded"


class TestInvestmentCompanyFilterInvariant:
    """Investment company patterns must NEVER appear in filtered output."""
    
    @given(stocks=stock_list_strategy())
    @settings(max_examples=200)
    def test_investment_pattern_never_in_output(self, stocks):
        """INVARIANT: No investment company pattern ever passes the filter."""
        df = pd.DataFrame(stocks)
        result = apply_investment_company_filter(df)
        
        # Check each result doesn't match investment pattern
        for _, row in result.iterrows():
            assert not is_investment_company(row['name']), \
                f"Investment company found in output: {row['name']}"
    
    @given(stocks=stock_list_strategy())
    @settings(max_examples=200)
    def test_non_investment_preserved(self, stocks):
        """INVARIANT: Non-investment companies are preserved."""
        df = pd.DataFrame(stocks)
        non_inv_before = set(df[~df['name'].apply(is_investment_company)]['ticker'])
        
        result = apply_investment_company_filter(df)
        non_inv_after = set(result['ticker'])
        
        assert non_inv_before == non_inv_after


class TestCombinedFiltersInvariant:
    """All invariants must hold when filters are combined."""
    
    @given(stocks=stock_list_strategy(min_size=5, max_size=100))
    @settings(max_examples=300)
    def test_all_invariants_hold(self, stocks):
        """INVARIANT: All filter conditions hold in combined output."""
        df = pd.DataFrame(stocks)
        result = apply_all_filters(df)
        
        # Invariant 1: No Finance
        assert len(result[result['sector'] == 'Finance']) == 0, "Finance found"
        
        # Invariant 2: No PREF
        assert len(result[result['ticker'].str.contains('PREF', case=False, na=False)]) == 0, "PREF found"
        
        # Invariant 3: No low F-Score
        assert len(result[result['piotroski_f_score'] < 5]) == 0, "Low F-Score found"
        
        # Invariant 4: No investment companies
        for _, row in result.iterrows():
            assert not is_investment_company(row['name']), f"Investment company: {row['name']}"
    
    @given(stocks=stock_list_strategy(min_size=10, max_size=100))
    @settings(max_examples=200)
    def test_filter_is_monotonic(self, stocks):
        """INVARIANT: Applying more filters never increases result size."""
        df = pd.DataFrame(stocks)
        
        after_finance = apply_finance_filter(df)
        after_pref = apply_pref_filter(after_finance)
        after_inv = apply_investment_company_filter(after_pref)
        after_fscore = apply_fscore_filter(after_inv)
        
        assert len(after_finance) <= len(df)
        assert len(after_pref) <= len(after_finance)
        assert len(after_inv) <= len(after_pref)
        assert len(after_fscore) <= len(after_inv)


class TestMomentumInvariant:
    """Momentum calculation and ranking invariants."""
    
    @given(stocks=stock_list_strategy(min_size=2, max_size=50))
    @settings(max_examples=200)
    def test_sorted_by_momentum_descending(self, stocks):
        """INVARIANT: Output is sorted by momentum descending."""
        df = pd.DataFrame(stocks)
        result = apply_all_filters(df)
        
        assume(len(result) >= 2)  # Need at least 2 stocks to test sorting
        
        result = calculate_momentum(result)
        momentums = result['momentum'].tolist()
        
        # Check descending order
        for i in range(len(momentums) - 1):
            assert momentums[i] >= momentums[i + 1], \
                f"Not sorted: {momentums[i]} < {momentums[i + 1]}"
    
    @given(stocks=stock_list_strategy(min_size=1, max_size=50))
    @settings(max_examples=200)
    def test_rank_1_has_highest_momentum(self, stocks):
        """INVARIANT: Rank 1 always has highest momentum."""
        df = pd.DataFrame(stocks)
        result = apply_all_filters(df)
        
        assume(len(result) >= 1)
        
        result = calculate_momentum(result)
        rank_1 = result[result['rank'] == 1]
        
        assert len(rank_1) == 1, "Should have exactly one rank 1"
        assert rank_1.iloc[0]['momentum'] == result['momentum'].max()
    
    @given(stocks=stock_list_strategy(min_size=1, max_size=50))
    @settings(max_examples=200)
    def test_ranks_are_consecutive(self, stocks):
        """INVARIANT: Ranks are 1, 2, 3, ... with no gaps."""
        df = pd.DataFrame(stocks)
        result = apply_all_filters(df)
        
        assume(len(result) >= 1)
        
        result = calculate_momentum(result)
        ranks = sorted(result['rank'].tolist())
        expected = list(range(1, len(result) + 1))
        
        assert ranks == expected, f"Ranks not consecutive: {ranks}"
    
    @given(stocks=stock_list_strategy(min_size=1, max_size=50))
    @settings(max_examples=200)
    def test_no_duplicate_tickers_if_input_unique(self, stocks):
        """INVARIANT: If input has unique tickers, output has unique tickers."""
        df = pd.DataFrame(stocks)
        
        # Only test if input has unique tickers
        input_tickers = df['ticker'].tolist()
        assume(len(input_tickers) == len(set(input_tickers)))
        
        result = apply_all_filters(df)
        tickers = result['ticker'].tolist()
        assert len(tickers) == len(set(tickers)), "Duplicate tickers found"


class TestEdgeCases:
    """Test edge cases that might break filters."""
    
    def test_empty_input(self):
        """Edge case: Empty input should return empty output."""
        df = pd.DataFrame(columns=['ticker', 'name', 'sector', 'piotroski_f_score'])
        result = apply_all_filters(df)
        assert len(result) == 0
    
    @given(stock=stock_strategy())
    @settings(max_examples=100)
    def test_single_stock(self, stock):
        """Edge case: Single stock input."""
        df = pd.DataFrame([stock])
        result = apply_all_filters(df)
        
        # Should be included only if passes all filters
        should_include = (
            stock['sector'] != 'Finance' and
            'PREF' not in stock['ticker'].upper() and
            stock['piotroski_f_score'] >= 5 and
            not is_investment_company(stock['name'])
        )
        
        if should_include:
            assert len(result) == 1
        else:
            assert len(result) == 0


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--hypothesis-show-statistics'])
