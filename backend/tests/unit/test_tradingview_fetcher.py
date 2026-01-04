"""
Unit tests for TradingView fetcher.
Tests API parsing, ROE/ROA calculation, F-Score fallback.
"""
import pytest
from unittest.mock import patch, MagicMock
from datetime import date


class TestTradingViewFetcher:
    """Test TradingViewFetcher class."""
    
    @pytest.fixture
    def fetcher(self):
        from services.tradingview_fetcher import TradingViewFetcher
        return TradingViewFetcher()
    
    @pytest.fixture
    def mock_api_response(self):
        """Sample TradingView API response."""
        return {
            'data': [{
                's': 'OMXSTO:VOLV_B',
                'd': [
                    'VOLV_B', 'Volvo B', 285.50, 650e9, 'Industrials', 'stock',
                    12.5, 2.1, 1.5, 8.5, 6.2,  # PE, PB, PS, P/FCF, EV/EBITDA
                    50e9, 200e9, 500e9,  # net_income_ttm, equity, assets
                    15.5, 40e9, 3.5,  # ROIC, FCF, div_yield
                    2.5, 8.3, 15.2, 25.8,  # Perf 1M, 3M, 6M, 12M
                    7, 6,  # F-Score TTM, FY
                    12e9, 55e9, 100e9, 1.5, 25.0, 2e9, 400e9, 80e9,  # F-Score components
                    10, -5, 8, 12, 5,  # YoY growth fields
                    60e9, 30e9,  # ebit_ttm, cash_n_short_term_invest_fq
                ]
            }]
        }
    
    def test_fetch_all_returns_list(self, fetcher):
        """Test that fetch_all returns a list."""
        with patch.object(fetcher.session, 'post') as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {'data': []}
            mock_post.return_value.raise_for_status = MagicMock()
            
            result = fetcher.fetch_all()
            assert isinstance(result, list)
    
    def test_fetch_all_api_error_returns_empty(self, fetcher):
        """Test graceful handling of API errors."""
        with patch.object(fetcher.session, 'post') as mock_post:
            mock_post.side_effect = Exception("Connection error")
            result = fetcher.fetch_all()
            assert result == []
    
    def test_roe_calculation_from_ttm(self, fetcher, mock_api_response):
        """Test ROE is calculated from TTM components, not direct field."""
        with patch.object(fetcher.session, 'post') as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = mock_api_response
            mock_post.return_value.raise_for_status = MagicMock()
            
            result = fetcher.fetch_all()
            assert len(result) == 1
            
            # ROE = net_income_ttm / total_equity_fq * 100
            # 50e9 / 200e9 * 100 = 25%
            expected_roe = (50e9 / 200e9) * 100
            assert result[0]['roe'] == pytest.approx(expected_roe, rel=0.01)
    
    def test_roa_calculation_from_ttm(self, fetcher, mock_api_response):
        """Test ROA is calculated from TTM components."""
        with patch.object(fetcher.session, 'post') as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = mock_api_response
            mock_post.return_value.raise_for_status = MagicMock()
            
            result = fetcher.fetch_all()
            # ROA = net_income_ttm / total_assets_fq * 100
            # 50e9 / 500e9 * 100 = 10%
            expected_roa = (50e9 / 500e9) * 100
            assert result[0]['roa'] == pytest.approx(expected_roa, rel=0.01)
    
    def test_fcfroe_calculation(self, fetcher, mock_api_response):
        """Test FCFROE is calculated correctly."""
        with patch.object(fetcher.session, 'post') as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = mock_api_response
            mock_post.return_value.raise_for_status = MagicMock()
            
            result = fetcher.fetch_all()
            # FCFROE = free_cash_flow_ttm / total_equity_fq * 100
            # 40e9 / 200e9 * 100 = 20%
            expected_fcfroe = (40e9 / 200e9) * 100
            assert result[0]['fcfroe'] == pytest.approx(expected_fcfroe, rel=0.01)
    
    def test_ticker_conversion(self, fetcher, mock_api_response):
        """Test ticker is converted from TV format to DB format."""
        with patch.object(fetcher.session, 'post') as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = mock_api_response
            mock_post.return_value.raise_for_status = MagicMock()
            
            result = fetcher.fetch_all()
            assert result[0]['ticker'] == 'VOLV_B'
            assert result[0]['db_ticker'] == 'VOLV-B'
    
    def test_fscore_uses_ttm_first(self, fetcher, mock_api_response):
        """Test F-Score prefers TTM over FY."""
        with patch.object(fetcher.session, 'post') as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = mock_api_response
            mock_post.return_value.raise_for_status = MagicMock()
            
            result = fetcher.fetch_all()
            # TTM F-Score is 7, FY is 6 - should use TTM
            assert result[0]['piotroski_f_score'] == 7
    
    def test_momentum_fields_parsed(self, fetcher, mock_api_response):
        """Test momentum fields are correctly parsed."""
        with patch.object(fetcher.session, 'post') as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = mock_api_response
            mock_post.return_value.raise_for_status = MagicMock()
            
            result = fetcher.fetch_all()
            assert result[0]['perf_1m'] == 2.5
            assert result[0]['perf_3m'] == 8.3
            assert result[0]['perf_6m'] == 15.2
            assert result[0]['perf_12m'] == 25.8
    
    def test_data_source_set_to_tradingview(self, fetcher, mock_api_response):
        """Test data_source is set to 'tradingview'."""
        with patch.object(fetcher.session, 'post') as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = mock_api_response
            mock_post.return_value.raise_for_status = MagicMock()
            
            result = fetcher.fetch_all()
            assert result[0]['data_source'] == 'tradingview'
    
    def test_fetched_date_is_today(self, fetcher, mock_api_response):
        """Test fetched_date is set to today."""
        with patch.object(fetcher.session, 'post') as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = mock_api_response
            mock_post.return_value.raise_for_status = MagicMock()
            
            result = fetcher.fetch_all()
            assert result[0]['fetched_date'] == date.today()


class TestFScoreCalculation:
    """Test F-Score fallback calculation."""
    
    @pytest.fixture
    def fetcher(self):
        from services.tradingview_fetcher import TradingViewFetcher
        return TradingViewFetcher()
    
    def test_fscore_profitable_company(self, fetcher):
        """Test F-Score calculation for profitable company."""
        row = {
            'net_income_ttm': 1000000,
            'cash_f_operating_activities_ttm': 1500000,
            'net_income_yoy_growth_ttm': 10,
            'total_debt_yoy_growth_fy': -5,
            'current_ratio_fq': 1.5,
            'gross_profit_yoy_growth_ttm': 8,
            'total_revenue_yoy_growth_ttm': 12,
            'total_assets_yoy_growth_fy': 5,
        }
        score = fetcher._calculate_fscore(row)
        assert score == 9  # All criteria met
    
    def test_fscore_loss_making_company(self, fetcher):
        """Test F-Score for loss-making company."""
        row = {
            'net_income_ttm': -1000000,
            'cash_f_operating_activities_ttm': -500000,
            'net_income_yoy_growth_ttm': -20,
            'total_debt_yoy_growth_fy': 15,
            'current_ratio_fq': 0.8,
            'gross_profit_yoy_growth_ttm': -5,
            'total_revenue_yoy_growth_ttm': -10,
            'total_assets_yoy_growth_fy': 5,
        }
        score = fetcher._calculate_fscore(row)
        assert score <= 3  # Low score expected
    
    def test_fscore_missing_data(self, fetcher):
        """Test F-Score with missing data returns partial score."""
        row = {
            'net_income_ttm': 1000000,
            'cash_f_operating_activities_ttm': 1500000,
        }
        score = fetcher._calculate_fscore(row)
        assert score is not None
        assert 0 < score <= 9


class TestAPIPayload:
    """Test API request payload construction."""
    
    @pytest.fixture
    def fetcher(self):
        from services.tradingview_fetcher import TradingViewFetcher
        return TradingViewFetcher()
    
    def test_includes_dr_type(self, fetcher):
        """Test that 'dr' type is included for Swedish Depository Receipts."""
        with patch.object(fetcher.session, 'post') as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {'data': []}
            mock_post.return_value.raise_for_status = MagicMock()
            
            fetcher.fetch_all()
            
            call_args = mock_post.call_args
            payload = call_args[1]['json']
            assert 'dr' in payload['symbols']['query']['types']
            assert 'stock' in payload['symbols']['query']['types']
    
    def test_no_is_primary_filter(self, fetcher):
        """Test that is_primary filter is NOT included."""
        with patch.object(fetcher.session, 'post') as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {'data': []}
            mock_post.return_value.raise_for_status = MagicMock()
            
            fetcher.fetch_all()
            
            call_args = mock_post.call_args
            payload = call_args[1]['json']
            
            # Check no is_primary filter
            for f in payload.get('filter', []):
                assert f.get('left') != 'is_primary'
    
    def test_market_cap_filter(self, fetcher):
        """Test market cap filter is applied."""
        with patch.object(fetcher.session, 'post') as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {'data': []}
            mock_post.return_value.raise_for_status = MagicMock()
            
            fetcher.fetch_all(min_market_cap=5e9)
            
            call_args = mock_post.call_args
            payload = call_args[1]['json']
            
            market_cap_filter = next(
                (f for f in payload['filter'] if f['left'] == 'market_cap_basic'),
                None
            )
            assert market_cap_filter is not None
            assert market_cap_filter['right'] == 5e9
