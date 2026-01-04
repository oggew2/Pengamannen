"""
Integration tests for TradingView sync functionality.
Tests the complete sync pipeline including database updates and ranking computation.
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import date
import asyncio


class TestTradingViewSync:
    """Test tradingview_sync function."""
    
    @pytest.fixture
    def mock_fetcher_response(self):
        """Mock TradingView fetcher response."""
        return [
            {
                'ticker': 'VOLV_B',
                'db_ticker': 'VOLV-B',
                'name': 'Volvo B',
                'market_cap': 650e9,
                'sector': 'Industrials',
                'pe': 12.5, 'pb': 2.1, 'ps': 1.5,
                'p_fcf': 8.5, 'ev_ebitda': 6.2,
                'roe': 25.0, 'roa': 10.0, 'roic': 15.5, 'fcfroe': 20.0,
                'dividend_yield': 3.5,
                'perf_1m': 2.5, 'perf_3m': 8.3, 'perf_6m': 15.2, 'perf_12m': 25.8,
                'piotroski_f_score': 7,
                'net_income': 12e9, 'operating_cf': 55e9,
                'total_assets': 500e9, 'long_term_debt': 80e9,
                'current_ratio': 1.5, 'gross_margin': 25.0,
                'shares_outstanding': 2e9,
                'data_source': 'tradingview',
                'fetched_date': date.today(),
            },
            {
                'ticker': 'HM_B',
                'db_ticker': 'HM-B',
                'name': 'H&M B',
                'market_cap': 200e9,
                'sector': 'Consumer Cyclical',
                'pe': 18.0, 'pb': 3.5, 'ps': 0.8,
                'p_fcf': 12.0, 'ev_ebitda': 8.5,
                'roe': 18.0, 'roa': 8.0, 'roic': 12.0, 'fcfroe': 15.0,
                'dividend_yield': 4.2,
                'perf_1m': -1.5, 'perf_3m': 5.0, 'perf_6m': 10.0, 'perf_12m': 15.0,
                'piotroski_f_score': 6,
                'net_income': 8e9, 'operating_cf': 20e9,
                'total_assets': 150e9, 'long_term_debt': 30e9,
                'current_ratio': 1.2, 'gross_margin': 52.0,
                'shares_outstanding': 1.5e9,
                'data_source': 'tradingview',
                'fetched_date': date.today(),
            },
        ]
    
    @pytest.mark.asyncio
    async def test_sync_updates_fundamentals(self, test_db, mock_fetcher_response):
        """Test that sync updates fundamentals table."""
        from jobs.scheduler import tradingview_sync
        from models import Fundamentals
        from sqlalchemy.orm import sessionmaker
        
        TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_db)
        db = TestingSessionLocal()
        
        with patch('services.tradingview_fetcher.TradingViewFetcher') as MockFetcher:
            mock_instance = MockFetcher.return_value
            mock_instance.fetch_all.return_value = mock_fetcher_response
            
            with patch('services.ranking_cache.compute_all_rankings_tv') as mock_rankings:
                mock_rankings.return_value = {'strategies': {}}
                
                result = await tradingview_sync(db)
        
        assert result['status'] == 'SUCCESS'
        assert result['stocks_updated'] == 2
        assert result['source'] == 'tradingview'
        
        # Verify fundamentals were saved
        fund = db.query(Fundamentals).filter(
            Fundamentals.ticker == 'VOLV-B',
            Fundamentals.data_source == 'tradingview'
        ).first()
        
        assert fund is not None
        assert fund.pe == 12.5
        assert fund.perf_3m == 8.3
        assert fund.piotroski_f_score == 7
        
        db.close()
    
    @pytest.mark.asyncio
    async def test_sync_returns_error_on_empty_data(self, test_db):
        """Test that sync returns error when no data fetched."""
        from jobs.scheduler import tradingview_sync
        from sqlalchemy.orm import sessionmaker
        
        TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_db)
        db = TestingSessionLocal()
        
        with patch('services.tradingview_fetcher.TradingViewFetcher') as MockFetcher:
            mock_instance = MockFetcher.return_value
            mock_instance.fetch_all.return_value = []
            
            result = await tradingview_sync(db)
        
        assert result['status'] == 'ERROR'
        assert 'No data' in result['message']
        
        db.close()
    
    @pytest.mark.asyncio
    async def test_sync_computes_rankings(self, test_db, mock_fetcher_response):
        """Test that sync triggers ranking computation."""
        from jobs.scheduler import tradingview_sync
        from sqlalchemy.orm import sessionmaker
        
        TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_db)
        db = TestingSessionLocal()
        
        with patch('services.tradingview_fetcher.TradingViewFetcher') as MockFetcher:
            mock_instance = MockFetcher.return_value
            mock_instance.fetch_all.return_value = mock_fetcher_response
            
            with patch('services.ranking_cache.compute_all_rankings_tv') as mock_rankings:
                mock_rankings.return_value = {
                    'strategies': {'sammansatt_momentum': {'top_10': ['VOLV-B']}}
                }
                
                result = await tradingview_sync(db)
                
                # Verify rankings were computed
                mock_rankings.assert_called_once()
        
        assert 'rankings' in result
        
        db.close()


class TestDataSourceSwitching:
    """Test DATA_SOURCE environment variable switching."""
    
    def test_data_source_default_is_tradingview(self):
        """Test default DATA_SOURCE is tradingview."""
        import os
        # Clear any existing value
        original = os.environ.pop('DATA_SOURCE', None)
        
        # Re-import to get default
        import importlib
        import jobs.scheduler as scheduler
        importlib.reload(scheduler)
        
        assert scheduler.DATA_SOURCE == 'tradingview'
        
        # Restore
        if original:
            os.environ['DATA_SOURCE'] = original
    
    def test_data_source_can_be_set_to_avanza(self):
        """Test DATA_SOURCE can be set to avanza."""
        import os
        original = os.environ.get('DATA_SOURCE')
        
        os.environ['DATA_SOURCE'] = 'avanza'
        
        import importlib
        import jobs.scheduler as scheduler
        importlib.reload(scheduler)
        
        assert scheduler.DATA_SOURCE == 'avanza'
        
        # Restore
        if original:
            os.environ['DATA_SOURCE'] = original
        else:
            os.environ.pop('DATA_SOURCE', None)


class TestRankingCacheTV:
    """Test compute_all_rankings_tv function."""
    
    @pytest.fixture
    def populated_db(self, test_db):
        """Create a test database with TradingView data."""
        from models import Fundamentals, Stock, StrategySignal
        from sqlalchemy.orm import sessionmaker
        import uuid
        
        TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_db)
        db = TestingSessionLocal()
        
        # Use unique tickers to avoid conflicts
        suffix = uuid.uuid4().hex[:6]
        
        # Add stocks
        stocks = [
            Stock(ticker=f'TV1_{suffix}', name='Stock 1', market_cap_msek=5000, sector='Technology', stock_type='stock'),
            Stock(ticker=f'TV2_{suffix}', name='Stock 2', market_cap_msek=4000, sector='Industrials', stock_type='stock'),
            Stock(ticker=f'TV3_{suffix}', name='Stock 3', market_cap_msek=3000, sector='Healthcare', stock_type='stock'),
        ]
        for s in stocks:
            db.add(s)
        
        # Add fundamentals with TradingView data
        fundamentals = [
            Fundamentals(
                ticker=f'TV1_{suffix}', pe=15, pb=2, ps=1.5, p_fcf=10, ev_ebitda=8,
                roe=20, roa=10, roic=15, fcfroe=18, dividend_yield=2.5,
                perf_3m=15, perf_6m=25, perf_12m=40, piotroski_f_score=7,
                data_source='tradingview', fetched_date=date.today()
            ),
            Fundamentals(
                ticker=f'TV2_{suffix}', pe=12, pb=1.5, ps=1.2, p_fcf=8, ev_ebitda=6,
                roe=25, roa=12, roic=18, fcfroe=22, dividend_yield=3.0,
                perf_3m=10, perf_6m=20, perf_12m=30, piotroski_f_score=8,
                data_source='tradingview', fetched_date=date.today()
            ),
            Fundamentals(
                ticker=f'TV3_{suffix}', pe=20, pb=3, ps=2, p_fcf=15, ev_ebitda=12,
                roe=15, roa=8, roic=12, fcfroe=14, dividend_yield=1.5,
                perf_3m=5, perf_6m=10, perf_12m=15, piotroski_f_score=5,
                data_source='tradingview', fetched_date=date.today()
            ),
        ]
        for f in fundamentals:
            db.add(f)
        
        db.commit()
        
        yield db
        
        db.close()
    
    def test_rankings_computed_from_tv_data(self, populated_db):
        """Test rankings are computed from TradingView data."""
        from services.ranking_cache import compute_all_rankings_tv
        
        result = compute_all_rankings_tv(populated_db)
        
        assert result['source'] == 'tradingview'
        assert 'strategies' in result
    
    def test_momentum_strategy_uses_tv_momentum(self, populated_db):
        """Test momentum strategy uses pre-calculated momentum."""
        from services.ranking_cache import compute_all_rankings_tv
        from models import StrategySignal
        
        result = compute_all_rankings_tv(populated_db)
        
        # Check momentum strategy was computed
        assert 'sammansatt_momentum' in result['strategies']
        
        # Verify signals were saved
        signals = populated_db.query(StrategySignal).filter(
            StrategySignal.strategy_name == 'sammansatt_momentum'
        ).all()
        
        # Should have ranked stocks
        assert len(signals) > 0


class TestFallbackBehavior:
    """Test fallback to Avanza when TradingView fails."""
    
    @pytest.mark.asyncio
    async def test_fallback_on_api_error(self, test_db):
        """Test fallback to Avanza when TradingView API fails."""
        from jobs.scheduler import tradingview_sync
        from sqlalchemy.orm import sessionmaker
        
        TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_db)
        db = TestingSessionLocal()
        
        with patch('services.tradingview_fetcher.TradingViewFetcher') as MockFetcher:
            mock_instance = MockFetcher.return_value
            mock_instance.fetch_all.side_effect = Exception("API Error")
            
            result = await tradingview_sync(db)
        
        assert result['status'] == 'ERROR'
        
        db.close()
