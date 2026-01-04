"""
Unit tests for TradingView ranking functions.
Tests calculate_momentum_score_from_tv and get_fscore_from_tv.
"""
import pytest
import pandas as pd
import numpy as np


class TestMomentumScoreFromTV:
    """Test calculate_momentum_score_from_tv function."""
    
    def test_basic_momentum_calculation(self):
        """Test basic momentum score calculation."""
        from services.ranking import calculate_momentum_score_from_tv
        
        df = pd.DataFrame({
            'ticker': ['STOCK1', 'STOCK2', 'STOCK3'],
            'perf_3m': [10.0, 20.0, 5.0],
            'perf_6m': [15.0, 25.0, 10.0],
            'perf_12m': [20.0, 30.0, 15.0],
        })
        
        result = calculate_momentum_score_from_tv(df)
        
        # STOCK1: (10 + 15 + 20) / 3 = 15
        # STOCK2: (20 + 25 + 30) / 3 = 25
        # STOCK3: (5 + 10 + 15) / 3 = 10
        assert result['STOCK1'] == pytest.approx(15.0)
        assert result['STOCK2'] == pytest.approx(25.0)
        assert result['STOCK3'] == pytest.approx(10.0)
    
    def test_momentum_with_missing_values(self):
        """Test momentum handles missing values."""
        from services.ranking import calculate_momentum_score_from_tv
        
        df = pd.DataFrame({
            'ticker': ['STOCK1', 'STOCK2'],
            'perf_3m': [10.0, None],
            'perf_6m': [15.0, 20.0],
            'perf_12m': [20.0, 30.0],
        })
        
        result = calculate_momentum_score_from_tv(df)
        
        # STOCK1: (10 + 15 + 20) / 3 = 15
        # STOCK2: (0 + 20 + 30) / 3 = 16.67 (None filled with 0)
        assert result['STOCK1'] == pytest.approx(15.0)
        assert result['STOCK2'] == pytest.approx(16.67, rel=0.01)
    
    def test_momentum_empty_dataframe(self):
        """Test momentum with empty DataFrame."""
        from services.ranking import calculate_momentum_score_from_tv
        
        df = pd.DataFrame()
        result = calculate_momentum_score_from_tv(df)
        assert len(result) == 0
    
    def test_momentum_negative_returns(self):
        """Test momentum with negative returns."""
        from services.ranking import calculate_momentum_score_from_tv
        
        df = pd.DataFrame({
            'ticker': ['LOSER'],
            'perf_3m': [-10.0],
            'perf_6m': [-15.0],
            'perf_12m': [-20.0],
        })
        
        result = calculate_momentum_score_from_tv(df)
        assert result['LOSER'] == pytest.approx(-15.0)
    
    def test_momentum_ranking_order(self):
        """Test that momentum scores rank correctly."""
        from services.ranking import calculate_momentum_score_from_tv
        
        df = pd.DataFrame({
            'ticker': ['LOW', 'MED', 'HIGH'],
            'perf_3m': [5.0, 15.0, 30.0],
            'perf_6m': [5.0, 15.0, 30.0],
            'perf_12m': [5.0, 15.0, 30.0],
        })
        
        result = calculate_momentum_score_from_tv(df)
        sorted_result = result.sort_values(ascending=False)
        
        assert list(sorted_result.index) == ['HIGH', 'MED', 'LOW']


class TestFScoreFromTV:
    """Test get_fscore_from_tv function."""
    
    def test_basic_fscore_retrieval(self):
        """Test basic F-Score retrieval."""
        from services.ranking import get_fscore_from_tv
        
        df = pd.DataFrame({
            'ticker': ['STOCK1', 'STOCK2', 'STOCK3'],
            'piotroski_f_score': [7, 5, 9],
        })
        
        result = get_fscore_from_tv(df)
        
        assert result['STOCK1'] == 7
        assert result['STOCK2'] == 5
        assert result['STOCK3'] == 9
    
    def test_fscore_with_missing_values(self):
        """Test F-Score with missing values."""
        from services.ranking import get_fscore_from_tv
        
        df = pd.DataFrame({
            'ticker': ['STOCK1', 'STOCK2'],
            'piotroski_f_score': [7, None],
        })
        
        result = get_fscore_from_tv(df)
        assert result['STOCK1'] == 7
        assert pd.isna(result['STOCK2'])
    
    def test_fscore_empty_dataframe(self):
        """Test F-Score with empty DataFrame."""
        from services.ranking import get_fscore_from_tv
        
        df = pd.DataFrame()
        result = get_fscore_from_tv(df)
        assert len(result) == 0
    
    def test_fscore_missing_column(self):
        """Test F-Score when column is missing."""
        from services.ranking import get_fscore_from_tv
        
        df = pd.DataFrame({
            'ticker': ['STOCK1'],
            'other_column': [123],
        })
        
        result = get_fscore_from_tv(df)
        assert len(result) == 0
    
    def test_fscore_filtering(self):
        """Test F-Score can be used for filtering."""
        from services.ranking import get_fscore_from_tv
        
        df = pd.DataFrame({
            'ticker': ['LOW', 'MED', 'HIGH'],
            'piotroski_f_score': [2, 5, 8],
        })
        
        result = get_fscore_from_tv(df)
        
        # Filter stocks with F-Score > 3
        valid = result[result > 3].index
        assert 'LOW' not in valid
        assert 'MED' in valid
        assert 'HIGH' in valid


class TestMomentumWithFScoreFilter:
    """Test momentum calculation with F-Score filtering."""
    
    def test_fscore_filter_removes_low_quality(self):
        """Test that low F-Score stocks are filtered out."""
        from services.ranking import calculate_momentum_score_from_tv, get_fscore_from_tv
        
        df = pd.DataFrame({
            'ticker': ['QUALITY', 'JUNK'],
            'perf_3m': [10.0, 50.0],  # JUNK has higher momentum
            'perf_6m': [10.0, 50.0],
            'perf_12m': [10.0, 50.0],
            'piotroski_f_score': [7, 2],  # But JUNK has low F-Score
        })
        
        momentum = calculate_momentum_score_from_tv(df)
        f_scores = get_fscore_from_tv(df)
        
        # Filter by F-Score > 3
        valid = f_scores[f_scores > 3].index
        filtered_momentum = momentum[momentum.index.isin(valid)]
        
        # Only QUALITY should remain
        assert 'QUALITY' in filtered_momentum.index
        assert 'JUNK' not in filtered_momentum.index


class TestIntegrationWithRankingCache:
    """Test integration with ranking cache functions."""
    
    def test_momentum_compatible_with_ranking(self):
        """Test momentum output is compatible with ranking functions."""
        from services.ranking import calculate_momentum_score_from_tv
        
        df = pd.DataFrame({
            'ticker': ['A', 'B', 'C', 'D', 'E'],
            'perf_3m': [10.0, 20.0, 30.0, 40.0, 50.0],
            'perf_6m': [10.0, 20.0, 30.0, 40.0, 50.0],
            'perf_12m': [10.0, 20.0, 30.0, 40.0, 50.0],
        })
        
        result = calculate_momentum_score_from_tv(df)
        
        # Should be a Series with ticker as index
        assert isinstance(result, pd.Series)
        assert result.index.name is None or result.index.name == 'ticker'
        
        # Should be sortable
        sorted_result = result.sort_values(ascending=False)
        assert sorted_result.iloc[0] == 50.0  # Highest momentum
        
        # Should be able to take top N
        top_3 = sorted_result.head(3)
        assert len(top_3) == 3
