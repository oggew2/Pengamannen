"""
Automated Rebalancing System for Börslabbet Strategies.
Maintains existing manual functionality while adding optional automation.
"""
import pandas as pd
import numpy as np
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple
from sqlalchemy.orm import Session
import logging

from services.avanza_fetcher_v2 import AvanzaDirectFetcher
from services.smart_cache import smart_cache
from services.ranking import (
    calculate_momentum_score, calculate_value_score, 
    calculate_dividend_score, calculate_quality_score
)

logger = logging.getLogger(__name__)

class AutoRebalancingSystem:
    """Automated rebalancing system with manual/auto toggle."""
    
    def __init__(self):
        self.fetcher = AvanzaDirectFetcher()
        
    def get_strategy_rankings(self, strategy_name: str, manual_mode: bool = True) -> Dict:
        """
        Get current strategy rankings - works in both manual and auto mode.
        
        Args:
            strategy_name: Strategy to rank (sammansatt_momentum, etc.)
            manual_mode: If True, returns rankings for manual viewing
                        If False, includes rebalancing analysis
        """
        try:
            # Get stock universe
            from services.live_universe import get_live_stock_universe
            tickers = get_live_stock_universe('sweden', 'large')
            
            # Fetch current data for all stocks
            stock_data = []
            for ticker in tickers:
                data = self.fetcher.get_complete_stock_data(ticker, include_history=True)
                if data and data.get('fetch_success'):
                    stock_data.append(data)
            
            if not stock_data:
                return {"error": "No stock data available"}
            
            # Calculate rankings based on strategy
            rankings = self._calculate_strategy_rankings(strategy_name, stock_data)
            
            if manual_mode:
                # Return rankings for manual viewing (existing functionality)
                return {
                    "strategy": strategy_name,
                    "mode": "manual",
                    "rankings": rankings[:20],  # Top 20 for viewing
                    "last_updated": datetime.now().isoformat(),
                    "total_stocks": len(stock_data)
                }
            else:
                # Return rankings with rebalancing analysis
                return {
                    "strategy": strategy_name,
                    "mode": "auto",
                    "rankings": rankings,
                    "rebalancing_data": self._prepare_rebalancing_data(strategy_name, rankings),
                    "last_updated": datetime.now().isoformat(),
                    "total_stocks": len(stock_data)
                }
                
        except Exception as e:
            logger.error(f"Error getting strategy rankings: {e}")
            return {"error": f"Failed to get rankings: {str(e)}"}
    
    def _calculate_strategy_rankings(self, strategy_name: str, stock_data: List[Dict]) -> List[Dict]:
        """Calculate rankings using existing Börslabbet strategy logic."""
        
        if strategy_name == "sammansatt_momentum":
            return self._rank_momentum_strategy(stock_data)
        elif strategy_name == "trendande_varde":
            return self._rank_value_strategy(stock_data)
        elif strategy_name == "trendande_utdelning":
            return self._rank_dividend_strategy(stock_data)
        elif strategy_name == "trendande_kvalitet":
            return self._rank_quality_strategy(stock_data)
        else:
            raise ValueError(f"Unknown strategy: {strategy_name}")
    
    def _rank_momentum_strategy(self, stock_data: List[Dict]) -> List[Dict]:
        """Rank stocks using Sammansatt Momentum strategy (UNCHANGED)."""
        ranked_stocks = []
        
        for data in stock_data:
            if data.get('historical_data_points', 0) >= 252:
                # Calculate momentum using existing logic
                hist_df = pd.DataFrame(data['historical_prices'])
                hist_df['date'] = pd.to_datetime(hist_df['date'])
                hist_df = hist_df.sort_values('date')
                
                current = hist_df.iloc[-1]['close']
                price_3m = hist_df.iloc[-63]['close']
                price_6m = hist_df.iloc[-126]['close']
                price_12m = hist_df.iloc[-252]['close']
                
                momentum_3m = (current / price_3m - 1) * 100
                momentum_6m = (current / price_6m - 1) * 100
                momentum_12m = (current / price_12m - 1) * 100
                
                # Sammansatt Momentum: equal weight average
                composite_score = (momentum_3m + momentum_6m + momentum_12m) / 3
                
                ranked_stocks.append({
                    'ticker': data['id'],
                    'name': data.get('name', data['id']),
                    'current_price': data['current_price'],
                    'momentum_score': composite_score,
                    'momentum_3m': momentum_3m,
                    'momentum_6m': momentum_6m,
                    'momentum_12m': momentum_12m,
                    'market_cap': data.get('market_cap'),
                    'sector': data.get('sector')
                })
        
        # Sort by momentum score (highest first)
        return sorted(ranked_stocks, key=lambda x: x['momentum_score'], reverse=True)
    
    def _rank_value_strategy(self, stock_data: List[Dict]) -> List[Dict]:
        """Rank stocks using Trendande Värde strategy (UNCHANGED)."""
        ranked_stocks = []
        
        for data in stock_data:
            # Check if we have required value metrics
            value_metrics = [data.get('pe'), data.get('pb'), data.get('ps'), 
                           data.get('p_fcf'), data.get('ev_ebitda')]
            available_metrics = [m for m in value_metrics if m is not None]
            
            if len(available_metrics) >= 4:  # Need at least 4 metrics
                # Calculate value score (lower is better)
                value_score = sum(available_metrics) / len(available_metrics)
                
                ranked_stocks.append({
                    'ticker': data['id'],
                    'name': data.get('name', data['id']),
                    'current_price': data['current_price'],
                    'value_score': value_score,
                    'pe': data.get('pe'),
                    'pb': data.get('pb'),
                    'ps': data.get('ps'),
                    'p_fcf': data.get('p_fcf'),
                    'ev_ebitda': data.get('ev_ebitda'),
                    'dividend_yield': data.get('dividend_yield'),
                    'market_cap': data.get('market_cap'),
                    'sector': data.get('sector')
                })
        
        # Sort by value score (lowest first - best value)
        return sorted(ranked_stocks, key=lambda x: x['value_score'])
    
    def _rank_dividend_strategy(self, stock_data: List[Dict]) -> List[Dict]:
        """Rank stocks using Trendande Utdelning strategy (UNCHANGED)."""
        ranked_stocks = []
        
        for data in stock_data:
            div_yield = data.get('dividend_yield')
            roe = data.get('roe')
            
            if div_yield is not None and roe is not None:
                # Apply Börslabbet filters
                passes_filters = roe > 5.0 and div_yield > 1.5
                
                ranked_stocks.append({
                    'ticker': data['id'],
                    'name': data.get('name', data['id']),
                    'current_price': data['current_price'],
                    'dividend_yield': div_yield,
                    'roe': roe,
                    'passes_filters': passes_filters,
                    'market_cap': data.get('market_cap'),
                    'sector': data.get('sector')
                })
        
        # Sort by dividend yield (highest first), but prioritize those passing filters
        filtered_stocks = [s for s in ranked_stocks if s['passes_filters']]
        unfiltered_stocks = [s for s in ranked_stocks if not s['passes_filters']]
        
        filtered_sorted = sorted(filtered_stocks, key=lambda x: x['dividend_yield'], reverse=True)
        unfiltered_sorted = sorted(unfiltered_stocks, key=lambda x: x['dividend_yield'], reverse=True)
        
        return filtered_sorted + unfiltered_sorted
    
    def _rank_quality_strategy(self, stock_data: List[Dict]) -> List[Dict]:
        """Rank stocks using Trendande Kvalitet strategy (UNCHANGED)."""
        ranked_stocks = []
        
        for data in stock_data:
            quality_metrics = [data.get('roe'), data.get('roa'), 
                             data.get('roic'), data.get('fcfroe')]
            available_quality = [m for m in quality_metrics if m is not None]
            
            if len(available_quality) >= 3 and data.get('price_history_available'):
                # Calculate quality score
                quality_score = sum(available_quality) / len(available_quality)
                
                # Get momentum component (12M)
                if data.get('historical_prices') and len(data['historical_prices']) >= 252:
                    hist_df = pd.DataFrame(data['historical_prices'])
                    hist_df['date'] = pd.to_datetime(hist_df['date'])
                    hist_df = hist_df.sort_values('date')
                    
                    current = hist_df.iloc[-1]['close']
                    price_12m = hist_df.iloc[-252]['close']
                    momentum_12m = (current / price_12m - 1) * 100
                    
                    # Combined score (50% quality, 50% momentum)
                    combined_score = (quality_score * 0.5) + (momentum_12m * 0.5)
                    
                    ranked_stocks.append({
                        'ticker': data['id'],
                        'name': data.get('name', data['id']),
                        'current_price': data['current_price'],
                        'quality_score': quality_score,
                        'momentum_12m': momentum_12m,
                        'combined_score': combined_score,
                        'roe': data.get('roe'),
                        'roa': data.get('roa'),
                        'roic': data.get('roic'),
                        'fcfroe': data.get('fcfroe'),
                        'market_cap': data.get('market_cap'),
                        'sector': data.get('sector')
                    })
        
        # Sort by combined score (highest first)
        return sorted(ranked_stocks, key=lambda x: x['combined_score'], reverse=True)
    
    def _prepare_rebalancing_data(self, strategy_name: str, rankings: List[Dict]) -> Dict:
        """Prepare rebalancing analysis data."""
        top_10 = rankings[:10]
        
        # Get rebalancing frequency
        rebalance_freq = self._get_rebalancing_frequency(strategy_name)
        next_rebalance = self._get_next_rebalance_date(strategy_name)
        
        return {
            "top_10_picks": top_10,
            "rebalance_frequency": rebalance_freq,
            "next_rebalance_date": next_rebalance.isoformat() if next_rebalance else None,
            "strategy_description": self._get_strategy_description(strategy_name)
        }
    
    def _get_rebalancing_frequency(self, strategy_name: str) -> str:
        """Get rebalancing frequency for strategy."""
        frequencies = {
            "sammansatt_momentum": "quarterly",
            "trendande_varde": "annual_january",
            "trendande_utdelning": "annual_february", 
            "trendande_kvalitet": "annual_march"
        }
        return frequencies.get(strategy_name, "unknown")
    
    def _get_next_rebalance_date(self, strategy_name: str) -> Optional[date]:
        """Calculate next rebalancing date for strategy."""
        today = date.today()
        
        if strategy_name == "sammansatt_momentum":
            # Quarterly: March, June, September, December
            quarters = [3, 6, 9, 12]
            for month in quarters:
                if month > today.month:
                    return date(today.year, month, 28)  # End of month
            return date(today.year + 1, 3, 28)  # Next March
            
        elif strategy_name == "trendande_varde":
            # Annual January
            if today.month >= 1:
                return date(today.year + 1, 1, 31)
            else:
                return date(today.year, 1, 31)
                
        elif strategy_name == "trendande_utdelning":
            # Annual February
            if today.month >= 2:
                return date(today.year + 1, 2, 28)
            else:
                return date(today.year, 2, 28)
                
        elif strategy_name == "trendande_kvalitet":
            # Annual March
            if today.month >= 3:
                return date(today.year + 1, 3, 31)
            else:
                return date(today.year, 3, 31)
        
        return None
    
    def _get_strategy_description(self, strategy_name: str) -> str:
        """Get strategy description."""
        descriptions = {
            "sammansatt_momentum": "Composite momentum (3M+6M+12M returns), rebalanced quarterly",
            "trendande_varde": "Value metrics (P/E, P/B, P/S, P/FCF, EV/EBITDA), rebalanced annually in January",
            "trendande_utdelning": "Dividend yield with quality filters (ROE>5%), rebalanced annually in February",
            "trendande_kvalitet": "Quality metrics + momentum (50/50 weight), rebalanced annually in March"
        }
        return descriptions.get(strategy_name, "Unknown strategy")
    
    def analyze_portfolio_rebalancing(self, current_holdings: List[Dict], strategy_name: str) -> Dict:
        """
        Analyze if portfolio needs rebalancing against strategy.
        
        Args:
            current_holdings: List of current portfolio holdings
            strategy_name: Strategy to check against
        """
        try:
            # Get current strategy rankings
            strategy_data = self.get_strategy_rankings(strategy_name, manual_mode=False)
            
            if "error" in strategy_data:
                return strategy_data
            
            top_10_picks = strategy_data["rebalancing_data"]["top_10_picks"]
            current_tickers = [h["ticker"] for h in current_holdings]
            optimal_tickers = [p["ticker"] for p in top_10_picks]
            
            # Calculate drift
            overlap = set(current_tickers) & set(optimal_tickers)
            drift_pct = (1 - len(overlap) / 10) * 100  # Assuming 10-stock portfolio
            
            # Generate trade suggestions
            to_sell = [t for t in current_tickers if t not in optimal_tickers]
            to_buy = [t for t in optimal_tickers if t not in current_tickers]
            
            # Check if rebalancing is due
            next_rebalance = strategy_data["rebalancing_data"]["next_rebalance_date"]
            rebalance_due = self._is_rebalancing_due(strategy_name, next_rebalance)
            
            return {
                "strategy": strategy_name,
                "drift_percentage": round(drift_pct, 1),
                "rebalancing_due": rebalance_due,
                "next_rebalance_date": next_rebalance,
                "current_holdings": len(current_holdings),
                "optimal_holdings": len(top_10_picks),
                "overlap_count": len(overlap),
                "trades_needed": {
                    "sell": to_sell,
                    "buy": to_buy,
                    "keep": list(overlap)
                },
                "top_10_picks": top_10_picks,
                "recommendation": self._get_rebalancing_recommendation(drift_pct, rebalance_due)
            }
            
        except Exception as e:
            logger.error(f"Error analyzing portfolio rebalancing: {e}")
            return {"error": f"Analysis failed: {str(e)}"}
    
    def _is_rebalancing_due(self, strategy_name: str, next_rebalance_date: str) -> bool:
        """Check if rebalancing is due based on strategy schedule."""
        if not next_rebalance_date:
            return False
        
        next_date = datetime.fromisoformat(next_rebalance_date).date()
        today = date.today()
        
        # Consider rebalancing due if within 7 days
        return (next_date - today).days <= 7
    
    def _get_rebalancing_recommendation(self, drift_pct: float, rebalance_due: bool) -> str:
        """Get rebalancing recommendation based on drift and schedule."""
        if rebalance_due and drift_pct > 20:
            return "REBALANCE_NOW"
        elif rebalance_due:
            return "REBALANCE_SCHEDULED"
        elif drift_pct > 30:
            return "HIGH_DRIFT"
        elif drift_pct > 20:
            return "MODERATE_DRIFT"
        else:
            return "ON_TRACK"

# Global instance
auto_rebalancer = AutoRebalancingSystem()
