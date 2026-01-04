"""
Unit tests for ticker mapping functions.
Tests conversion between TradingView and database ticker formats.
"""
import pytest


class TestTickerMapping:
    """Test ticker conversion functions."""
    
    def test_tv_to_db_basic(self):
        """Test basic underscore to dash conversion."""
        from services.ticker_mapping import tv_to_db_ticker
        assert tv_to_db_ticker('VOLV_B') == 'VOLV-B'
        assert tv_to_db_ticker('HM_B') == 'HM-B'
        assert tv_to_db_ticker('SSAB_B') == 'SSAB-B'
    
    def test_tv_to_db_sdb(self):
        """Test Swedish Depository Receipt conversion."""
        from services.ticker_mapping import tv_to_db_ticker
        assert tv_to_db_ticker('ALIV_SDB') == 'ALIV-SDB'
    
    def test_tv_to_db_no_underscore(self):
        """Test tickers without underscore pass through."""
        from services.ticker_mapping import tv_to_db_ticker
        assert tv_to_db_ticker('ABB') == 'ABB'
        assert tv_to_db_ticker('ERICB') == 'ERICB'
    
    def test_tv_to_db_multiple_underscores(self):
        """Test tickers with multiple underscores."""
        from services.ticker_mapping import tv_to_db_ticker
        assert tv_to_db_ticker('TEST_A_B') == 'TEST-A-B'
    
    def test_db_to_tv_basic(self):
        """Test basic dash to underscore conversion."""
        from services.ticker_mapping import db_to_tv_ticker
        assert db_to_tv_ticker('VOLV-B') == 'VOLV_B'
        assert db_to_tv_ticker('HM-B') == 'HM_B'
    
    def test_db_to_tv_with_space(self):
        """Test space to underscore conversion."""
        from services.ticker_mapping import db_to_tv_ticker
        assert db_to_tv_ticker('VOLV B') == 'VOLV_B'
        assert db_to_tv_ticker('SEB A') == 'SEB_A'
    
    def test_db_to_tv_no_special_chars(self):
        """Test tickers without special chars pass through."""
        from services.ticker_mapping import db_to_tv_ticker
        assert db_to_tv_ticker('ABB') == 'ABB'
    
    def test_roundtrip_conversion(self):
        """Test that conversion is reversible for standard tickers."""
        from services.ticker_mapping import tv_to_db_ticker, db_to_tv_ticker
        
        tv_tickers = ['VOLV_B', 'HM_B', 'SSAB_B', 'ABB', 'ALIV_SDB']
        for tv in tv_tickers:
            db = tv_to_db_ticker(tv)
            back = db_to_tv_ticker(db)
            assert back == tv


class TestFinancialSectorDetection:
    """Test financial sector detection."""
    
    def test_finance_sector(self):
        """Test Finance sector is detected."""
        from services.ticker_mapping import is_financial_sector
        assert is_financial_sector('Finance') is True
        assert is_financial_sector('finance') is True
        assert is_financial_sector('FINANCE') is True
    
    def test_financial_services_sector(self):
        """Test Financial Services sector is detected."""
        from services.ticker_mapping import is_financial_sector
        assert is_financial_sector('Financial Services') is True
        assert is_financial_sector('financial services') is True
    
    def test_non_financial_sectors(self):
        """Test non-financial sectors return False."""
        from services.ticker_mapping import is_financial_sector
        assert is_financial_sector('Technology') is False
        assert is_financial_sector('Industrials') is False
        assert is_financial_sector('Healthcare') is False
        assert is_financial_sector('Consumer Cyclical') is False
    
    def test_none_sector(self):
        """Test None sector returns False."""
        from services.ticker_mapping import is_financial_sector
        assert is_financial_sector(None) is False
    
    def test_empty_sector(self):
        """Test empty string returns False."""
        from services.ticker_mapping import is_financial_sector
        assert is_financial_sector('') is False


class TestEdgeCases:
    """Test edge cases in ticker mapping."""
    
    def test_empty_string(self):
        """Test empty string handling."""
        from services.ticker_mapping import tv_to_db_ticker, db_to_tv_ticker
        assert tv_to_db_ticker('') == ''
        assert db_to_tv_ticker('') == ''
    
    def test_only_underscore(self):
        """Test string with only underscore."""
        from services.ticker_mapping import tv_to_db_ticker
        assert tv_to_db_ticker('_') == '-'
    
    def test_only_dash(self):
        """Test string with only dash."""
        from services.ticker_mapping import db_to_tv_ticker
        assert db_to_tv_ticker('-') == '_'
    
    def test_numeric_suffix(self):
        """Test tickers with numeric suffixes."""
        from services.ticker_mapping import tv_to_db_ticker, db_to_tv_ticker
        assert tv_to_db_ticker('STOCK_1') == 'STOCK-1'
        assert db_to_tv_ticker('STOCK-1') == 'STOCK_1'
