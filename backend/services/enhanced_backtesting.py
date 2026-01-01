"""
Enhanced backtesting service with extended historical data fetching.
Optimized for separate backtesting page - does NOT interfere with main app performance.
"""
import pandas as pd
import numpy as np
from datetime import date, timedelta, datetime
from dateutil.relativedelta import relativedelta
import json
import logging
from typing import Dict, List, Optional, Tuple
from services.avanza_fetcher_v2 import AvanzaDirectFetcher
from services.smart_cache import smart_cache

logger = logging.getLogger(__name__)

class BacktestingDataFetcher:
    """Separate data fetcher for backtesting - isolated from main app."""
    
    def __init__(self):
        self.fetcher = AvanzaDirectFetcher()
        # Use separate cache namespace for backtesting
        self.backtest_cache_ttl = 24 * 30  # 30 days for backtesting data (very stable)
        
    def fetch_long_term_historical_data(self, ticker: str, years: int = 10) -> Optional[pd.DataFrame]:
        """
        Fetch long-term historical data specifically for backtesting.
        Uses separate cache namespace to avoid interfering with main app.
        """
        cache_key = f"backtest_hist_{ticker}_{years}y"
        
        # Check backtest-specific cache (30-day TTL)
        cached_data = smart_cache.get(f"backtesting_historical", {"ticker": ticker, "years": years})
        
        if cached_data and not cached_data.get('_cache_metadata', {}).get('is_expired', True):
            logger.info(f"Using cached backtesting data for {ticker} ({years}y)")
            return pd.DataFrame(cached_data['data'])
        
        # Fetch extended data for backtesting
        days = years * 365 + 100  # Extra buffer for long periods
        logger.info(f"Fetching {years} years of data for {ticker} (backtesting)")
        
        hist_data = self.fetcher.get_historical_prices(ticker, days=days)
        
        if hist_data is not None and len(hist_data) > 0:
            # Cache with very long TTL for backtesting (30 days)
            cache_data = {
                'data': hist_data.to_dict('records'),
                'ticker': ticker,
                'years': years,
                'fetched_at': datetime.now().isoformat(),
                'data_points': len(hist_data),
                'purpose': 'backtesting'
            }
            
            smart_cache.set(
                "backtesting_historical", 
                {"ticker": ticker, "years": years}, 
                cache_data, 
                ttl_hours=self.backtest_cache_ttl
            )
            
            logger.info(f"Cached {len(hist_data)} backtesting data points for {ticker}")
            return hist_data
        else:
            logger.warning(f"Failed to fetch backtesting data for {ticker}")
            return None

class EnhancedBacktester:
    """Enhanced backtesting with long-term horizons - separate from main app."""
    
    def __init__(self):
        self.data_fetcher = BacktestingDataFetcher()
        
    def prepare_long_term_backtest_universe(self, tickers: List[str], years: int = 10) -> Dict[str, pd.DataFrame]:
        """
        Prepare long-term historical data for backtesting universe.
        Optimized with threading for fast parallel fetching.
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        universe_data = {}
        
        logger.info(f"Preparing LONG-TERM backtest universe: {len(tickers)} stocks, {years} years")
        
        def fetch_ticker(ticker):
            hist_data = self.data_fetcher.fetch_long_term_historical_data(ticker, years)
            if hist_data is not None and len(hist_data) > 252:
                return ticker, hist_data.sort_values('date')
            return ticker, None
        
        # Parallel fetch with 10 threads
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(fetch_ticker, t): t for t in tickers}
            
            for i, future in enumerate(as_completed(futures)):
                ticker, hist_data = future.result()
                if hist_data is not None:
                    universe_data[ticker] = hist_data
                
                if (i + 1) % 50 == 0 or i == len(tickers) - 1:
                    logger.info(f"Backtest data progress: {i+1}/{len(tickers)} ({len(universe_data)} successful)")
        
        logger.info(f"Long-term backtest universe ready: {len(universe_data)}/{len(tickers)} stocks")
        return universe_data
    
    def run_long_term_momentum_backtest(
        self, 
        tickers: List[str], 
        start_date: date, 
        end_date: date,
        top_n: int = 10,
        rebalance_frequency: str = 'quarterly'
    ) -> Dict:
        """
        Run long-term momentum backtest (5-10+ years).
        Completely separate from main app - runs on demand only.
        """
        years_needed = (end_date - start_date).days / 365 + 1
        logger.info(f"Starting LONG-TERM momentum backtest: {years_needed:.1f} years ({start_date} to {end_date})")
        logger.info("This is a separate backtesting process - main app performance unaffected")
        
        # Prepare long-term data
        universe_data = self.prepare_long_term_backtest_universe(tickers, years=int(years_needed) + 1)
        
        if len(universe_data) < 5:
            return {"error": "Insufficient long-term historical data for backtest"}
        
        # Generate rebalance dates
        rebalance_dates = self._get_rebalance_dates(start_date, end_date, rebalance_frequency)
        logger.info(f"Generated {len(rebalance_dates)} rebalance dates over {years_needed:.1f} years")
        
        # Initialize backtest
        portfolio_value = 100000
        portfolio_history = []
        holdings = {}
        
        for i, rebalance_date in enumerate(rebalance_dates):
            logger.info(f"Rebalancing {i+1}/{len(rebalance_dates)}: {rebalance_date}")
            
            # Calculate momentum scores
            momentum_scores = self.calculate_momentum_scores(universe_data, rebalance_date)
            
            if len(momentum_scores) < top_n:
                logger.warning(f"Only {len(momentum_scores)} stocks have momentum scores")
                continue
            
            # Select top momentum stocks
            sorted_stocks = sorted(momentum_scores.items(), key=lambda x: x[1], reverse=True)
            selected_stocks = [ticker for ticker, score in sorted_stocks[:top_n]]
            
            # Equal weight allocation
            weight_per_stock = 1.0 / len(selected_stocks)
            new_holdings = {ticker: weight_per_stock for ticker in selected_stocks}
            
            # Calculate transaction costs
            transaction_cost = self._calculate_transaction_costs(holdings, new_holdings, portfolio_value)
            portfolio_value -= transaction_cost
            
            # Update holdings
            holdings = new_holdings
            
            # Record portfolio state
            portfolio_history.append({
                'date': rebalance_date,
                'value': portfolio_value,
                'holdings': holdings.copy(),
                'top_momentum_stocks': selected_stocks,
                'transaction_cost': transaction_cost,
                'top_momentum_score': sorted_stocks[0][1] if sorted_stocks else 0
            })
        
        # Calculate comprehensive performance metrics
        if len(portfolio_history) >= 2:
            returns = self._calculate_returns(portfolio_history, universe_data, end_date)
            metrics = self._calculate_performance_metrics(returns, portfolio_history, years_needed)
            
            return {
                'strategy': 'Long-Term Sammansatt Momentum',
                'period': f"{start_date} to {end_date}",
                'years': round(years_needed, 1),
                'universe_size': len(universe_data),
                'rebalance_count': len(rebalance_dates),
                'final_value': portfolio_history[-1]['value'],
                'total_return_pct': round((portfolio_history[-1]['value'] / 100000 - 1) * 100, 2),
                'metrics': metrics,
                'portfolio_history': portfolio_history,
                'data_quality': {
                    'stocks_with_data': len(universe_data),
                    'total_stocks': len(tickers),
                    'data_coverage_pct': round(len(universe_data) / len(tickers) * 100, 1),
                    'avg_data_years': round(sum((data.iloc[-1]['date'] - data.iloc[0]['date']).days / 365 for data in universe_data.values()) / len(universe_data), 1)
                },
                'performance_summary': {
                    'best_year': max(returns) if returns else 0,
                    'worst_year': min(returns) if returns else 0,
                    'positive_years': sum(1 for r in returns if r > 0) if returns else 0,
                    'total_years': len(returns) if returns else 0
                }
            }
        else:
            return {"error": "Insufficient rebalance periods for long-term backtest"}
    
    def calculate_momentum_scores(self, universe_data: Dict[str, pd.DataFrame], as_of_date: date) -> Dict[str, float]:
        """Calculate momentum scores as of specific date."""
        momentum_scores = {}
        
        for ticker, hist_data in universe_data.items():
            data_subset = hist_data[hist_data['date'] <= pd.to_datetime(as_of_date)]
            
            if len(data_subset) >= 252:
                try:
                    current_price = data_subset.iloc[-1]['close']
                    price_3m = data_subset.iloc[-63]['close']
                    price_6m = data_subset.iloc[-126]['close']
                    price_12m = data_subset.iloc[-252]['close']
                    
                    momentum_3m = (current_price / price_3m - 1) * 100
                    momentum_6m = (current_price / price_6m - 1) * 100
                    momentum_12m = (current_price / price_12m - 1) * 100
                    
                    composite_momentum = (momentum_3m + momentum_6m + momentum_12m) / 3
                    momentum_scores[ticker] = composite_momentum
                    
                except Exception as e:
                    logger.warning(f"Error calculating momentum for {ticker}: {e}")
                    continue
        
        return momentum_scores
    
    def _get_rebalance_dates(self, start_date: date, end_date: date, frequency: str) -> List[date]:
        """Generate rebalance dates."""
        dates = []
        current = start_date
        
        if frequency == 'quarterly':
            months = [3, 6, 9, 12]
            while current <= end_date:
                if current.month in months:
                    if current.month == 12:
                        next_month = current.replace(year=current.year + 1, month=1, day=1)
                    else:
                        next_month = current.replace(month=current.month + 1, day=1)
                    last_day = next_month - timedelta(days=1)
                    dates.append(last_day)
                
                if current.month == 12:
                    current = current.replace(year=current.year + 1, month=1)
                else:
                    current = current.replace(month=current.month + 1)
        elif frequency == 'annual':
            while current <= end_date:
                if current.month == 3:  # March rebalancing
                    dates.append(current.replace(day=31) if current.month in [1,3,5,7,8,10,12] else current.replace(day=30))
                current = current.replace(year=current.year + 1) if current.month >= 3 else current.replace(month=current.month + 1)
        
        return [d for d in dates if start_date <= d <= end_date]
    
    def _calculate_transaction_costs(self, old_holdings: Dict, new_holdings: Dict, portfolio_value: float) -> float:
        """Calculate transaction costs."""
        all_tickers = set(old_holdings.keys()) | set(new_holdings.keys())
        turnover = sum(abs(new_holdings.get(ticker, 0) - old_holdings.get(ticker, 0)) for ticker in all_tickers)
        return turnover * portfolio_value * 0.001  # 0.1% transaction cost
    
    def _calculate_returns(self, portfolio_history: List, universe_data: Dict, end_date: date) -> List[float]:
        """Calculate period returns."""
        returns = []
        for i in range(1, len(portfolio_history)):
            prev_value = portfolio_history[i-1]['value']
            curr_value = portfolio_history[i]['value']
            period_return = (curr_value / prev_value - 1) * 100
            returns.append(period_return)
        return returns
    
    def _calculate_performance_metrics(self, returns: List[float], portfolio_history: List, years: float) -> Dict:
        """Calculate comprehensive performance metrics."""
        if not returns:
            return {}
        
        total_return = (portfolio_history[-1]['value'] / 100000 - 1) * 100
        annualized_return = ((portfolio_history[-1]['value'] / 100000) ** (1/years) - 1) * 100
        
        volatility = np.std(returns) * np.sqrt(4) if len(returns) > 1 else 0
        sharpe_ratio = (annualized_return / volatility) if volatility > 0 else 0
        
        values = [p['value'] for p in portfolio_history]
        max_drawdown = self._calculate_max_drawdown(values)
        
        return {
            'total_return_pct': round(total_return, 2),
            'annualized_return_pct': round(annualized_return, 2),
            'volatility_pct': round(volatility, 2),
            'sharpe_ratio': round(sharpe_ratio, 2),
            'max_drawdown_pct': round(max_drawdown, 2),
            'best_period_pct': round(max(returns), 2) if returns else 0,
            'worst_period_pct': round(min(returns), 2) if returns else 0,
            'win_rate_pct': round(sum(1 for r in returns if r > 0) / len(returns) * 100, 1) if returns else 0
        }
    
    def _calculate_max_drawdown(self, values: List[float]) -> float:
        """Calculate maximum drawdown."""
        peak = values[0]
        max_dd = 0.0
        
        for value in values:
            if value > peak:
                peak = value
            dd = (value - peak) / peak * 100
            if dd < max_dd:
                max_dd = dd
        
        return max_dd

# Global instance for backtesting only
long_term_backtester = EnhancedBacktester()
