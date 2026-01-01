"""Tests for strategy output validation - checks for duplicates and data quality."""
import pytest
from collections import Counter


class TestStrategyOutput:
    """Test strategy rankings for duplicates and anomalies."""

    @pytest.fixture
    def db_session(self):
        """Get database session."""
        from db import SessionLocal
        db = SessionLocal()
        yield db
        db.close()

    @pytest.fixture
    def all_strategies(self):
        return ['sammansatt_momentum', 'trendande_varde', 'trendande_utdelning', 'trendande_kvalitet']

    def get_strategy_rankings(self, db, strategy_name):
        """Get rankings for a strategy."""
        from main import _compute_strategy_rankings, STRATEGIES_CONFIG
        config = STRATEGIES_CONFIG.get("strategies", {}).get(strategy_name)
        if not config:
            return []
        return _compute_strategy_rankings(strategy_name, config, db)

    def test_no_duplicate_tickers_in_rankings(self, db_session, all_strategies):
        """Each strategy should return unique tickers only."""
        total_tested = 0
        for strategy in all_strategies:
            rankings = self.get_strategy_rankings(db_session, strategy)
            if not rankings:
                continue  # Skip if no data
            
            total_tested += 1
            tickers = [r.ticker for r in rankings]
            
            counts = Counter(tickers)
            duplicates = [(t, c) for t, c in counts.items() if c > 1]
            
            assert len(duplicates) == 0, f"{strategy}: Found duplicate tickers: {duplicates}"
        
        assert total_tested > 0, "No strategies returned data - tests are meaningless!"

    def test_no_duplicate_ranks(self, db_session, all_strategies):
        """Each rank should be unique within a strategy."""
        total_tested = 0
        for strategy in all_strategies:
            rankings = self.get_strategy_rankings(db_session, strategy)
            if not rankings:
                continue
            
            total_tested += 1
            ranks = [r.rank for r in rankings]
            
            counts = Counter(ranks)
            duplicates = [(r, c) for r, c in counts.items() if c > 1]
            
            assert len(duplicates) == 0, f"{strategy}: Found duplicate ranks: {duplicates}"
        
        assert total_tested > 0, "No strategies returned data - tests are meaningless!"

    def test_ranks_are_sequential(self, db_session, all_strategies):
        """Ranks should be 1, 2, 3, ... without gaps."""
        total_tested = 0
        for strategy in all_strategies:
            rankings = self.get_strategy_rankings(db_session, strategy)
            if not rankings:
                continue
            
            total_tested += 1
            ranks = sorted([r.rank for r in rankings])
            expected = list(range(1, len(ranks) + 1))
            
            assert ranks == expected, f"{strategy}: Ranks not sequential. Got: {ranks[:10]}..."
        
        assert total_tested > 0, "No strategies returned data - tests are meaningless!"

    def test_no_etfs_in_rankings(self, db_session, all_strategies):
        """ETFs and certificates should be excluded from rankings."""
        etf_patterns = ['BULL', 'BEAR', 'XACT', 'MINI', 'TRACKER']
        total_tested = 0
        
        for strategy in all_strategies:
            rankings = self.get_strategy_rankings(db_session, strategy)
            if not rankings:
                continue
            
            total_tested += 1
            for r in rankings:
                for pattern in etf_patterns:
                    assert pattern not in r.ticker.upper(), \
                        f"{strategy}: ETF/certificate found: {r.ticker}"
        
        assert total_tested > 0, "No strategies returned data - tests are meaningless!"

    def test_scores_are_valid(self, db_session, all_strategies):
        """Scores should be finite numbers."""
        import math
        total_tested = 0
        
        for strategy in all_strategies:
            rankings = self.get_strategy_rankings(db_session, strategy)
            if not rankings:
                continue
            
            total_tested += 1
            for r in rankings:
                assert not math.isnan(r.score), f"{strategy}: NaN score for {r.ticker}"
                assert not math.isinf(r.score), f"{strategy}: Infinite score for {r.ticker}"
        
        assert total_tested > 0, "No strategies returned data - tests are meaningless!"

    def test_minimum_market_cap_filter(self, db_session, all_strategies):
        """All ranked stocks should have market cap >= 2B SEK."""
        from models import Stock
        total_tested = 0
        
        for strategy in all_strategies:
            rankings = self.get_strategy_rankings(db_session, strategy)
            if not rankings:
                continue
            
            total_tested += 1
            for r in rankings:
                stock = db_session.query(Stock).filter(Stock.ticker == r.ticker).first()
                if stock and stock.market_cap_msek:
                    assert stock.market_cap_msek >= 2000, \
                        f"{strategy}: {r.ticker} has market cap {stock.market_cap_msek} MSEK (< 2B)"
        
        assert total_tested > 0, "No strategies returned data - tests are meaningless!"


class TestDatabaseIntegrity:
    """Test database for duplicates and anomalies."""

    @pytest.fixture
    def db_connection(self):
        import sqlite3
        conn = sqlite3.connect('app.db')
        yield conn
        conn.close()

    def test_no_duplicate_stock_tickers(self, db_connection):
        """Stock tickers should be unique."""
        cur = db_connection.cursor()
        cur.execute('SELECT ticker, COUNT(*) FROM stocks GROUP BY ticker HAVING COUNT(*) > 1')
        duplicates = cur.fetchall()
        assert len(duplicates) == 0, f"Duplicate stock tickers: {duplicates}"

    def test_no_duplicate_avanza_ids(self, db_connection):
        """Avanza IDs should be unique."""
        cur = db_connection.cursor()
        cur.execute('''
            SELECT avanza_id, COUNT(*) FROM stocks 
            WHERE avanza_id IS NOT NULL AND avanza_id != '' 
            GROUP BY avanza_id HAVING COUNT(*) > 1
        ''')
        duplicates = cur.fetchall()
        assert len(duplicates) == 0, f"Duplicate avanza_ids: {duplicates}"

    def test_no_duplicate_fundamentals(self, db_connection):
        """Each ticker should have at most one fundamentals row."""
        cur = db_connection.cursor()
        cur.execute('SELECT ticker, COUNT(*) FROM fundamentals GROUP BY ticker HAVING COUNT(*) > 1')
        duplicates = cur.fetchall()
        assert len(duplicates) == 0, f"Duplicate fundamentals: {duplicates}"

    def test_consistent_ticker_format(self, db_connection):
        """All tickers should use space format, not dash."""
        cur = db_connection.cursor()
        
        cur.execute('SELECT COUNT(*) FROM stocks WHERE ticker LIKE "%-%"')
        dash_stocks = cur.fetchone()[0]
        
        cur.execute('SELECT COUNT(*) FROM fundamentals WHERE ticker LIKE "%-%"')
        dash_fund = cur.fetchone()[0]
        
        cur.execute('SELECT COUNT(*) FROM daily_prices WHERE ticker LIKE "%-%"')
        dash_prices = cur.fetchone()[0]
        
        assert dash_stocks == 0, f"Found {dash_stocks} stocks with dash format"
        assert dash_fund == 0, f"Found {dash_fund} fundamentals with dash format"
        assert dash_prices == 0, f"Found {dash_prices} prices with dash format"

    def test_no_orphaned_fundamentals(self, db_connection):
        """All fundamentals should have a matching stock."""
        cur = db_connection.cursor()
        cur.execute('''
            SELECT COUNT(*) FROM fundamentals f 
            WHERE NOT EXISTS (SELECT 1 FROM stocks s WHERE s.ticker = f.ticker)
        ''')
        orphans = cur.fetchone()[0]
        assert orphans == 0, f"Found {orphans} orphaned fundamentals"

    def test_real_stocks_have_avanza_id(self, db_connection):
        """All real stocks should have an avanza_id for syncing."""
        cur = db_connection.cursor()
        cur.execute('''
            SELECT COUNT(*) FROM stocks 
            WHERE stock_type = 'stock' AND (avanza_id IS NULL OR avanza_id = '')
        ''')
        missing = cur.fetchone()[0]
        assert missing == 0, f"Found {missing} real stocks without avanza_id"

    def test_no_misclassified_etfs(self, db_connection):
        """ETFs should not be classified as stocks."""
        cur = db_connection.cursor()
        cur.execute('''
            SELECT ticker, name FROM stocks WHERE stock_type = 'stock' AND (
                ticker LIKE 'BULL%' OR ticker LIKE 'BEAR%' OR ticker LIKE 'MINI%' OR
                ticker LIKE 'TRACKER%' OR name LIKE '%ETF%' OR name LIKE '%UCITS%'
            )
        ''')
        misclassified = cur.fetchall()
        assert len(misclassified) == 0, f"Misclassified ETFs: {misclassified[:10]}"
