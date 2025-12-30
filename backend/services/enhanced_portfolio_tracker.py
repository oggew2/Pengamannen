"""
Enhanced Portfolio Performance Tracking with visualization and benchmarking.
Supports Avanza CSV import, performance charts, and OMXS30 comparison.
"""
import pandas as pd
import numpy as np
from datetime import date, datetime, timedelta
from typing import List, Dict, Optional, Tuple
from sqlalchemy.orm import Session
import yfinance as yf
import logging

from services.csv_import import parse_avanza_csv
from services.smart_cache import smart_cache
from services.avanza_fetcher_v2 import AvanzaDirectFetcher

logger = logging.getLogger(__name__)

class PortfolioPerformanceTracker:
    """Enhanced portfolio tracking with performance visualization."""
    
    def __init__(self):
        self.fetcher = AvanzaDirectFetcher()
        
    def import_avanza_transactions(self, csv_content: str) -> Dict:
        """
        Import and process Avanza CSV transactions.
        Returns processed transactions with performance calculations.
        """
        try:
            transactions = parse_avanza_csv(csv_content)
            
            if not transactions:
                return {"error": "No transactions found in CSV"}
            
            # Process transactions into portfolio timeline
            portfolio_timeline = self._build_portfolio_timeline(transactions)
            
            # Calculate performance metrics
            performance_data = self._calculate_performance_metrics(portfolio_timeline)
            
            # Get benchmark data (OMXS30)
            benchmark_data = self._get_benchmark_data(portfolio_timeline)
            
            return {
                "success": True,
                "transactions_count": len(transactions),
                "portfolio_timeline": portfolio_timeline,
                "performance_metrics": performance_data,
                "benchmark_data": benchmark_data,
                "chart_data": self._prepare_chart_data(portfolio_timeline, benchmark_data)
            }
            
        except Exception as e:
            logger.error(f"Error importing Avanza CSV: {e}")
            return {"error": f"Failed to import CSV: {str(e)}"}
    
    def _build_portfolio_timeline(self, transactions: List[Dict]) -> List[Dict]:
        """Build daily portfolio value timeline from transactions."""
        # Sort transactions by date
        sorted_txns = sorted(transactions, key=lambda x: x['date'])
        
        if not sorted_txns:
            return []
        
        # Get date range
        start_date = datetime.strptime(sorted_txns[0]['date'], '%Y-%m-%d').date()
        end_date = date.today()
        
        # Build holdings over time
        timeline = []
        current_holdings = {}
        total_invested = 0
        total_fees = 0
        
        # Generate daily timeline
        current_date = start_date
        txn_index = 0
        
        while current_date <= end_date:
            date_str = current_date.strftime('%Y-%m-%d')
            
            # Process all transactions for this date
            while (txn_index < len(sorted_txns) and 
                   sorted_txns[txn_index]['date'] == date_str):
                
                txn = sorted_txns[txn_index]
                ticker = txn['ticker']
                
                if txn['type'] == 'BUY':
                    if ticker not in current_holdings:
                        current_holdings[ticker] = {'shares': 0, 'avg_cost': 0}
                    
                    # Update average cost
                    old_shares = current_holdings[ticker]['shares']
                    old_cost = current_holdings[ticker]['avg_cost']
                    new_shares = txn['shares']
                    new_cost = txn['price']
                    
                    total_shares = old_shares + new_shares
                    if total_shares > 0:
                        avg_cost = ((old_shares * old_cost) + (new_shares * new_cost)) / total_shares
                        current_holdings[ticker] = {'shares': total_shares, 'avg_cost': avg_cost}
                    
                    total_invested += txn['shares'] * txn['price']
                    total_fees += txn.get('fees', 0)
                    
                elif txn['type'] == 'SELL':
                    if ticker in current_holdings:
                        current_holdings[ticker]['shares'] -= txn['shares']
                        if current_holdings[ticker]['shares'] <= 0:
                            del current_holdings[ticker]
                    
                    total_invested -= txn['shares'] * txn['price']
                    total_fees += txn.get('fees', 0)
                
                txn_index += 1
            
            # Calculate portfolio value for this date
            portfolio_value = self._calculate_portfolio_value(current_holdings, current_date)
            
            if portfolio_value is not None:
                timeline.append({
                    'date': date_str,
                    'portfolio_value': portfolio_value,
                    'total_invested': total_invested,
                    'total_fees': total_fees,
                    'unrealized_pnl': portfolio_value - total_invested,
                    'holdings': current_holdings.copy(),
                    'return_pct': ((portfolio_value - total_invested) / max(total_invested, 1)) * 100
                })
            
            current_date += timedelta(days=1)
        
        return timeline
    
    def _calculate_portfolio_value(self, holdings: Dict, as_of_date: date) -> Optional[float]:
        """Calculate total portfolio value as of specific date."""
        if not holdings:
            return 0.0
        
        total_value = 0.0
        
        for ticker, holding in holdings.items():
            shares = holding['shares']
            if shares <= 0:
                continue
            
            # Get current price (for recent dates) or historical price
            if as_of_date >= date.today() - timedelta(days=7):
                # Use current price for recent dates
                stock_data = self.fetcher.get_complete_stock_data(ticker, include_history=False)
                if stock_data and stock_data.get('current_price'):
                    price = stock_data['current_price']
                    total_value += shares * price
            else:
                # For historical dates, we'd need historical prices
                # For now, use average cost as approximation
                price = holding['avg_cost']
                total_value += shares * price
        
        return total_value
    
    def _calculate_performance_metrics(self, timeline: List[Dict]) -> Dict:
        """Calculate comprehensive performance metrics."""
        if not timeline:
            return {}
        
        latest = timeline[-1]
        first = timeline[0]
        
        # Basic metrics
        total_return_pct = latest['return_pct']
        total_invested = latest['total_invested']
        current_value = latest['portfolio_value']
        total_fees = latest['total_fees']
        
        # Time-based metrics
        days = len(timeline)
        years = days / 365.25
        
        if years > 0 and total_invested > 0:
            annualized_return = ((current_value / total_invested) ** (1/years) - 1) * 100
        else:
            annualized_return = 0
        
        # Calculate volatility from daily returns
        daily_returns = []
        for i in range(1, len(timeline)):
            prev_value = timeline[i-1]['portfolio_value']
            curr_value = timeline[i]['portfolio_value']
            if prev_value > 0:
                daily_return = (curr_value / prev_value - 1) * 100
                daily_returns.append(daily_return)
        
        volatility = np.std(daily_returns) * np.sqrt(252) if daily_returns else 0  # Annualized
        
        # Max drawdown
        max_drawdown = self._calculate_max_drawdown([t['portfolio_value'] for t in timeline])
        
        # Fee impact
        fee_impact_pct = (total_fees / max(total_invested, 1)) * 100
        
        return {
            'total_return_pct': round(total_return_pct, 2),
            'annualized_return_pct': round(annualized_return, 2),
            'total_invested': round(total_invested, 2),
            'current_value': round(current_value, 2),
            'unrealized_pnl': round(current_value - total_invested, 2),
            'total_fees': round(total_fees, 2),
            'fee_impact_pct': round(fee_impact_pct, 2),
            'volatility_pct': round(volatility, 2),
            'max_drawdown_pct': round(max_drawdown, 2),
            'sharpe_ratio': round((annualized_return / volatility) if volatility > 0 else 0, 2),
            'days_tracked': days,
            'years_tracked': round(years, 2)
        }
    
    def _get_benchmark_data(self, timeline: List[Dict]) -> List[Dict]:
        """Get OMXS30 benchmark data for comparison."""
        if not timeline:
            return []
        
        try:
            # Check cache first
            cache_key = f"omxs30_benchmark_{timeline[0]['date']}_{timeline[-1]['date']}"
            cached_data = smart_cache.get("benchmark_data", {"key": cache_key})
            
            if cached_data and not cached_data.get('_cache_metadata', {}).get('is_expired', True):
                return cached_data['data']
            
            # Fetch OMXS30 data
            start_date = timeline[0]['date']
            end_date = timeline[-1]['date']
            
            omxs30 = yf.Ticker("^OMXS30")
            hist = omxs30.history(start=start_date, end=end_date)
            
            if hist.empty:
                return []
            
            # Convert to our format
            benchmark_data = []
            base_value = hist['Close'].iloc[0] if len(hist) > 0 else 100
            
            for date_idx, close_price in hist['Close'].items():
                date_str = date_idx.strftime('%Y-%m-%d')
                return_pct = ((close_price / base_value) - 1) * 100
                
                benchmark_data.append({
                    'date': date_str,
                    'value': close_price,
                    'return_pct': return_pct
                })
            
            # Cache for 24 hours
            smart_cache.set("benchmark_data", {"key": cache_key}, 
                          {"data": benchmark_data}, ttl_hours=24)
            
            return benchmark_data
            
        except Exception as e:
            logger.error(f"Error fetching OMXS30 data: {e}")
            return []
    
    def _prepare_chart_data(self, timeline: List[Dict], benchmark_data: List[Dict]) -> Dict:
        """Prepare data for frontend charts."""
        if not timeline:
            return {}
        
        # Portfolio performance data
        portfolio_chart = []
        portfolio_with_fees = []
        
        for point in timeline:
            portfolio_chart.append({
                'date': point['date'],
                'value': point['portfolio_value'],
                'return_pct': point['return_pct'],
                'invested': point['total_invested']
            })
            
            # Calculate performance with fee impact
            value_after_fees = point['portfolio_value'] - point['total_fees']
            return_after_fees = ((value_after_fees - point['total_invested']) / max(point['total_invested'], 1)) * 100
            
            portfolio_with_fees.append({
                'date': point['date'],
                'value': value_after_fees,
                'return_pct': return_after_fees
            })
        
        # Benchmark data
        benchmark_chart = benchmark_data
        
        return {
            'portfolio': portfolio_chart,
            'portfolio_with_fees': portfolio_with_fees,
            'benchmark': benchmark_chart,
            'comparison': self._create_comparison_data(portfolio_chart, benchmark_chart)
        }
    
    def _create_comparison_data(self, portfolio: List[Dict], benchmark: List[Dict]) -> List[Dict]:
        """Create comparison data between portfolio and benchmark."""
        if not portfolio or not benchmark:
            return []
        
        # Align dates
        portfolio_dict = {p['date']: p for p in portfolio}
        benchmark_dict = {b['date']: b for b in benchmark}
        
        comparison = []
        for date_str in portfolio_dict.keys():
            if date_str in benchmark_dict:
                port_return = portfolio_dict[date_str]['return_pct']
                bench_return = benchmark_dict[date_str]['return_pct']
                
                comparison.append({
                    'date': date_str,
                    'portfolio_return': port_return,
                    'benchmark_return': bench_return,
                    'excess_return': port_return - bench_return
                })
        
        return comparison
    
    def _calculate_max_drawdown(self, values: List[float]) -> float:
        """Calculate maximum drawdown from value series."""
        if not values:
            return 0.0
        
        peak = values[0]
        max_dd = 0.0
        
        for value in values:
            if value > peak:
                peak = value
            dd = (value - peak) / peak * 100
            if dd < max_dd:
                max_dd = dd
        
        return max_dd

# Global instance
portfolio_tracker = PortfolioPerformanceTracker()
