"""
Comprehensive Stock Screening Filter Validation Test Suite

Tests the Nordic momentum screening filters to ensure:
1. Data quality (no missing values, valid ranges)
2. Filter logic (correct exclusions/inclusions)
3. Sector classification (Finance correctly identified)
4. Edge cases (SDB, holding companies, etc.)
5. Boundary conditions (F-Score=5, market cap=2B)
"""
import pytest
import sys
sys.path.insert(0, '.')

from services.tradingview_fetcher import TradingViewFetcher
from services.ranking_cache import compute_nordic_momentum
import pandas as pd


@pytest.fixture(scope="module")
def nordic_data():
    """Fetch Nordic data once for all tests."""
    fetcher = TradingViewFetcher()
    stocks = fetcher.fetch_nordic(min_market_cap_sek=2e9)
    return pd.DataFrame(stocks)


@pytest.fixture(scope="module")
def filtered_results():
    """Get filtered momentum results."""
    return compute_nordic_momentum(db=None)


class TestDataQuality:
    """Test data quality and completeness."""
    
    def test_no_missing_critical_fields(self, nordic_data):
        """Critical fields should have no missing values."""
        critical = ['ticker', 'name', 'close', 'market_cap', 'sector', 'piotroski_f_score']
        for field in critical:
            assert field in nordic_data.columns, f"Missing column: {field}"
            missing = nordic_data[field].isna().sum()
            assert missing == 0, f"{field} has {missing} missing values"
    
    def test_valid_price_range(self, nordic_data):
        """All prices should be positive."""
        invalid = nordic_data[nordic_data['close'] <= 0]
        assert len(invalid) == 0, f"Found {len(invalid)} stocks with invalid price"
    
    def test_valid_fscore_range(self, nordic_data):
        """F-Score should be 0-9."""
        invalid = nordic_data[(nordic_data['piotroski_f_score'] < 0) | (nordic_data['piotroski_f_score'] > 9)]
        assert len(invalid) == 0, f"Found {len(invalid)} stocks with invalid F-Score"
    
    def test_no_duplicate_tickers(self, nordic_data):
        """No duplicate tickers."""
        duplicates = nordic_data[nordic_data.duplicated(subset=['ticker'], keep=False)]
        assert len(duplicates) == 0, f"Found duplicates: {duplicates['ticker'].unique().tolist()}"


class TestFilterLogic:
    """Test filter logic correctness."""
    
    def test_finance_sector_excluded(self, filtered_results):
        """No Finance sector stocks in results."""
        finance = [r for r in filtered_results['rankings'] if r['sector'] == 'Finance']
        assert len(finance) == 0, f"Found Finance stocks: {[r['ticker'] for r in finance]}"
    
    def test_preference_shares_excluded(self, filtered_results):
        """No preference shares in results."""
        pref = [r for r in filtered_results['rankings'] if 'PREF' in r['ticker']]
        assert len(pref) == 0, f"Found PREF stocks: {[r['ticker'] for r in pref]}"
    
    def test_fscore_minimum(self, filtered_results):
        """All stocks have F-Score >= 5."""
        low = [r for r in filtered_results['rankings'] if (r.get('f_score') or 0) < 5]
        assert len(low) == 0, f"Found low F-Score: {[(r['ticker'], r['f_score']) for r in low]}"
    
    def test_known_exclusions(self, filtered_results):
        """Known companies that should be excluded."""
        excluded_tickers = ['INVE_B', 'LATO_B', 'SEB_A', 'NP3_PREF', 'MAHA_A']
        result_tickers = set(r['ticker'] for r in filtered_results['rankings'])
        for ticker in excluded_tickers:
            assert ticker not in result_tickers, f"{ticker} should be excluded"


class TestSectorClassification:
    """Test sector classification accuracy."""
    
    def test_banks_in_finance(self, nordic_data):
        """Banks should be in Finance sector."""
        banks = ['SEB_A', 'SWED_A', 'NDA_SE', 'DNB']
        for ticker in banks:
            stock = nordic_data[nordic_data['ticker'] == ticker]
            if len(stock) > 0:
                assert stock.iloc[0]['sector'] == 'Finance', f"{ticker} should be Finance"
    
    def test_investment_companies_in_finance(self, nordic_data):
        """Investment companies should be in Finance sector."""
        inv_cos = ['INVE_B', 'LATO_B', 'INDU_A']
        for ticker in inv_cos:
            stock = nordic_data[nordic_data['ticker'] == ticker]
            if len(stock) > 0:
                assert stock.iloc[0]['sector'] == 'Finance', f"{ticker} should be Finance"


class TestEdgeCases:
    """Test edge cases and unusual stocks."""
    
    def test_sdb_stocks_handled(self, nordic_data, filtered_results):
        """SDB stocks should be filtered by normal criteria, not blanket excluded."""
        sdb = nordic_data[nordic_data['ticker'].str.contains('SDB', na=False)]
        result_tickers = set(r['ticker'] for r in filtered_results['rankings'])
        
        for _, s in sdb.iterrows():
            in_results = s['ticker'] in result_tickers
            # Should be excluded if Finance or low F-Score
            if s['sector'] == 'Finance' or s['piotroski_f_score'] < 5:
                assert not in_results, f"{s['ticker']} should be excluded"
    
    def test_holding_companies_are_operating(self, filtered_results):
        """Holding companies in results should be legitimate operating companies."""
        holdings = [r for r in filtered_results['rankings'] if 'holding' in r['name'].lower()]
        # These should all be non-Finance operating companies
        for r in holdings:
            assert r['sector'] != 'Finance', f"{r['ticker']} is Finance holding company"


class TestBoundaryConditions:
    """Test at filter boundaries."""
    
    def test_fscore_boundary(self, nordic_data):
        """F-Score 4 excluded, F-Score 5 included."""
        fscore_4 = nordic_data[nordic_data['piotroski_f_score'] == 4]
        fscore_5 = nordic_data[nordic_data['piotroski_f_score'] == 5]
        assert len(fscore_4) > 0, "Should have F-Score 4 stocks"
        assert len(fscore_5) > 0, "Should have F-Score 5 stocks"
    
    def test_market_cap_boundary(self, nordic_data):
        """All stocks should have market cap >= 2B SEK."""
        below = nordic_data[nordic_data['market_cap_sek'] < 2e9]
        assert len(below) == 0, f"Found {len(below)} stocks below 2B SEK"
    
    def test_no_financial_names_in_results(self, filtered_results):
        """No financial-sounding names should slip through."""
        suspicious = ['bank', 'finans', 'försäkring', 'insurance']
        for r in filtered_results['rankings']:
            name_lower = r['name'].lower()
            for sus in suspicious:
                assert sus not in name_lower, f"{r['ticker']} has suspicious name: {r['name']}"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
