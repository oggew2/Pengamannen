"""Track historical data for portfolio performance over time."""
import sqlite3
from datetime import datetime
from typing import Dict, List
import logging

logger = logging.getLogger(__name__)


class HistoricalTracker:
    """Track historical data for portfolio performance over time."""
    
    def __init__(self, history_db_path: str = "history.db"):
        self.history_db_path = history_db_path
        self._init_history_db()
    
    def _init_history_db(self):
        """Initialize historical tracking database."""
        conn = sqlite3.connect(self.history_db_path)
        
        conn.execute("""
            CREATE TABLE IF NOT EXISTS price_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                price REAL NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                source TEXT DEFAULT 'Avanza',
                volume INTEGER,
                change_percent REAL
            )
        """)
        
        conn.execute("""
            CREATE TABLE IF NOT EXISTS portfolio_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                portfolio_name TEXT NOT NULL,
                ticker TEXT NOT NULL,
                shares REAL NOT NULL,
                price REAL NOT NULL,
                value REAL NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.execute("CREATE INDEX IF NOT EXISTS idx_price_ticker_time ON price_history(ticker, timestamp)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_portfolio_time ON portfolio_snapshots(portfolio_name, timestamp)")
        
        conn.commit()
        conn.close()
    
    def record_price(self, ticker: str, price: float, volume: int = None, change_percent: float = None):
        """Record price data point."""
        conn = sqlite3.connect(self.history_db_path)
        conn.execute(
            "INSERT INTO price_history (ticker, price, volume, change_percent) VALUES (?, ?, ?, ?)",
            (ticker, price, volume, change_percent)
        )
        conn.commit()
        conn.close()
    
    def record_portfolio_snapshot(self, portfolio_name: str, holdings: List[Dict]):
        """Record portfolio snapshot for tracking performance."""
        conn = sqlite3.connect(self.history_db_path)
        for holding in holdings:
            conn.execute(
                "INSERT INTO portfolio_snapshots (portfolio_name, ticker, shares, price, value) VALUES (?, ?, ?, ?, ?)",
                (portfolio_name, holding['ticker'], holding['shares'], holding['price'], holding['shares'] * holding['price'])
            )
        conn.commit()
        conn.close()
    
    def get_price_history(self, ticker: str, days: int = 30) -> List[Dict]:
        """Get price history for a ticker."""
        conn = sqlite3.connect(self.history_db_path)
        cursor = conn.cursor()
        cursor.execute(f"""
            SELECT price, timestamp, volume, change_percent
            FROM price_history 
            WHERE ticker = ? AND timestamp >= datetime('now', '-{days} days')
            ORDER BY timestamp ASC
        """, (ticker,))
        results = cursor.fetchall()
        conn.close()
        return [{'price': r[0], 'timestamp': r[1], 'volume': r[2], 'change_percent': r[3]} for r in results]
    
    def get_portfolio_performance(self, portfolio_name: str, days: int = 30) -> Dict:
        """Get portfolio performance over time."""
        conn = sqlite3.connect(self.history_db_path)
        cursor = conn.cursor()
        cursor.execute(f"""
            SELECT DATE(timestamp) as date, SUM(value) as total_value, COUNT(DISTINCT ticker) as num_holdings
            FROM portfolio_snapshots 
            WHERE portfolio_name = ? AND timestamp >= datetime('now', '-{days} days')
            GROUP BY DATE(timestamp)
            ORDER BY date ASC
        """, (portfolio_name,))
        results = cursor.fetchall()
        conn.close()
        
        if not results:
            return {'performance': [], 'total_return': 0, 'days_tracked': 0}
        
        performance = [{'date': r[0], 'total_value': r[1], 'num_holdings': r[2]} for r in results]
        
        if len(performance) > 1:
            total_return = ((performance[-1]['total_value'] - performance[0]['total_value']) / performance[0]['total_value']) * 100
        else:
            total_return = 0
        
        return {'performance': performance, 'total_return': round(total_return, 2), 'days_tracked': len(performance)}
