"""
Tests for Stock Scanner Service.
"""
import pytest
import pandas as pd
from unittest.mock import patch, MagicMock
import json
import os

from services.stock_scanner import (
    classify_stock_type,
    get_scan_status,
    get_scan_ranges,
    DEFAULT_RANGES,
    SCAN_STATE_FILE
)
from services.ranking import filter_real_stocks, VALID_STOCK_TYPES


@pytest.mark.unit
class TestStockClassification:
    """Test stock type classification."""
    
    def test_regular_stock(self):
        """Regular stocks should be classified as 'stock'."""
        assert classify_stock_type('VOLV B') == 'stock'
        assert classify_stock_type('SEB A') == 'stock'
        assert classify_stock_type('HM B') == 'stock'
        assert classify_stock_type('ERIC B') == 'stock'
    
    def test_etf_certificate(self):
        """ETFs and certificates should be classified as 'etf_certificate'."""
        assert classify_stock_type('XACT OMXS30') == 'etf_certificate'
        assert classify_stock_type('BULL VOLV X3 H') == 'etf_certificate'
        assert classify_stock_type('BEAR OMX X2 N') == 'etf_certificate'
        assert classify_stock_type('SHRT HM H') == 'etf_certificate'
        assert classify_stock_type('LONG GULD H') == 'etf_certificate'
    
    def test_preference_shares(self):
        """Preference shares should be classified as 'preference'."""
        assert classify_stock_type('ALM PREF') == 'preference'
        assert classify_stock_type('HEIM PREF') == 'preference'
        assert classify_stock_type('K2A PREF') == 'preference'
    
    def test_sdb(self):
        """Swedish Depository Receipts should be classified as 'sdb'."""
        assert classify_stock_type('ALIV SDB') == 'sdb'


@pytest.mark.unit
class TestRankingFilter:
    """Test ranking filter for real stocks."""
    
    def test_filter_real_stocks(self):
        """Should filter out ETFs and preference shares."""
        df = pd.DataFrame([
            {'ticker': 'VOLV B', 'stock_type': 'stock'},
            {'ticker': 'XACT OMXS30', 'stock_type': 'etf_certificate'},
            {'ticker': 'ALM PREF', 'stock_type': 'preference'},
            {'ticker': 'ALIV SDB', 'stock_type': 'sdb'},
        ])
        
        filtered = filter_real_stocks(df)
        
        assert len(filtered) == 2
        assert 'VOLV B' in filtered['ticker'].values
        assert 'ALIV SDB' in filtered['ticker'].values
        assert 'XACT OMXS30' not in filtered['ticker'].values
        assert 'ALM PREF' not in filtered['ticker'].values
    
    def test_filter_with_include_preference(self):
        """Should include preference shares when flag is set."""
        df = pd.DataFrame([
            {'ticker': 'VOLV B', 'stock_type': 'stock'},
            {'ticker': 'ALM PREF', 'stock_type': 'preference'},
        ])
        
        filtered = filter_real_stocks(df, include_preference=True)
        
        assert len(filtered) == 2
        assert 'ALM PREF' in filtered['ticker'].values
    
    def test_filter_empty_dataframe(self):
        """Should handle empty DataFrame."""
        df = pd.DataFrame(columns=['ticker', 'stock_type'])
        filtered = filter_real_stocks(df)
        assert len(filtered) == 0
    
    def test_filter_missing_column(self):
        """Should return original if stock_type column missing."""
        df = pd.DataFrame([{'ticker': 'VOLV B'}])
        filtered = filter_real_stocks(df)
        assert len(filtered) == 1
    
    def test_valid_stock_types(self):
        """Valid stock types should include stock and sdb."""
        assert 'stock' in VALID_STOCK_TYPES
        assert 'sdb' in VALID_STOCK_TYPES
        assert 'etf_certificate' not in VALID_STOCK_TYPES
        assert 'preference' not in VALID_STOCK_TYPES


@pytest.mark.unit
class TestScanRanges:
    """Test scan range configuration."""
    
    def test_default_ranges_exist(self):
        """Default ranges should be defined."""
        assert len(DEFAULT_RANGES) > 0
    
    def test_default_ranges_structure(self):
        """Each range should have start, end, and name."""
        for r in DEFAULT_RANGES:
            assert 'start' in r
            assert 'end' in r
            assert 'name' in r
            assert r['end'] > r['start']
    
    def test_ranges_cover_known_stocks(self):
        """Ranges should cover known stock ID ranges (5k-650k)."""
        min_start = min(r['start'] for r in DEFAULT_RANGES)
        max_end = max(r['end'] for r in DEFAULT_RANGES)
        
        assert min_start <= 5000
        assert max_end >= 600000
    
    def test_get_scan_ranges(self):
        """get_scan_ranges should return ranges with status."""
        ranges = get_scan_ranges()
        
        assert len(ranges) == len(DEFAULT_RANGES)
        for r in ranges:
            assert 'start' in r
            assert 'end' in r
            assert 'name' in r
            assert 'last_scanned' in r
            assert 'stocks_found' in r


@pytest.mark.unit
class TestScanStatus:
    """Test scan status reporting."""
    
    def test_get_scan_status_structure(self):
        """Scan status should have required fields."""
        status = get_scan_status()
        
        assert 'total' in status
        assert 'by_type' in status
        assert 'by_market' in status
        assert 'real_stocks' in status
        assert 'scan_state' in status
        assert 'default_ranges' in status
    
    def test_real_stocks_count(self):
        """Real stocks should be sum of stock and sdb types."""
        status = get_scan_status()
        
        expected = status['by_type'].get('stock', 0) + status['by_type'].get('sdb', 0)
        assert status['real_stocks'] == expected


@pytest.mark.integration
class TestSwedishMarketsOnly:
    """Test that only Swedish markets are included."""
    
    def test_valid_markets_in_scanner(self):
        """Scanner should only accept Swedish markets."""
        # This is tested by checking the scan_single_id function logic
        # Valid markets: Stockholmsbörsen, First North Stockholm
        from services.stock_scanner import scan_single_id
        import requests
        
        # The function checks for these markets
        valid_markets = ['Stockholmsbörsen', 'First North Stockholm']
        
        # Verify the logic exists (we can't easily test without mocking)
        import inspect
        source = inspect.getsource(scan_single_id)
        assert 'Stockholmsbörsen' in source
        assert 'First North Stockholm' in source
