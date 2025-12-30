"""
Portfolio Comparison Service - Compare current portfolio against all strategies
Shows time until rebalance and suggested changes for each strategy
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import calendar

from .auto_rebalancing import AutoRebalancingSystem


@dataclass
class StrategyComparison:
    strategy_name: str
    display_name: str
    next_rebalance_date: str
    days_until_rebalance: int
    current_drift_percentage: float
    recommendation: str
    suggested_changes: Dict[str, List[Dict[str, Any]]]
    is_rebalance_due: bool


class PortfolioComparisonService:
    def __init__(self):
        self.auto_rebalancing = AutoRebalancingSystem()
        
        # Strategy rebalance schedules
        self.rebalance_schedules = {
            'sammansatt_momentum': {
                'display_name': 'Sammansatt Momentum',
                'frequency': 'quarterly',
                'months': [3, 6, 9, 12]  # March, June, September, December
            },
            'trendande_varde': {
                'display_name': 'Trendande Värde',
                'frequency': 'annual',
                'months': [1]  # January
            },
            'trendande_utdelning': {
                'display_name': 'Trendande Utdelning',
                'frequency': 'annual',
                'months': [2]  # February
            },
            'trendande_kvalitet': {
                'display_name': 'Trendande Kvalitet',
                'frequency': 'annual',
                'months': [3]  # March
            }
        }

    def get_next_rebalance_date(self, strategy_name: str) -> tuple[str, int]:
        """Calculate next rebalance date and days until rebalance"""
        if strategy_name not in self.rebalance_schedules:
            return "Unknown", 0
            
        schedule = self.rebalance_schedules[strategy_name]
        now = datetime.now()
        current_year = now.year
        current_month = now.month
        
        # Find next rebalance month
        next_rebalance_month = None
        for month in schedule['months']:
            if month > current_month:
                next_rebalance_month = month
                next_year = current_year
                break
        
        # If no month found this year, use first month of next year
        if next_rebalance_month is None:
            next_rebalance_month = schedule['months'][0]
            next_year = current_year + 1
        
        # Calculate next rebalance date (first day of the month)
        next_rebalance = datetime(next_year, next_rebalance_month, 1)
        days_until = (next_rebalance - now).days
        
        return next_rebalance.strftime("%Y-%m-%d"), days_until

    def compare_portfolio_to_all_strategies(self, current_holdings: List[Dict[str, Any]]) -> List[StrategyComparison]:
        """Compare current portfolio against all strategies"""
        comparisons = []
        
        for strategy_name, schedule in self.rebalance_schedules.items():
            try:
                # Get rebalancing analysis for this strategy
                analysis = self.auto_rebalancing.analyze_rebalancing(
                    strategy_name=strategy_name,
                    current_holdings=current_holdings
                )
                
                # Get next rebalance date
                next_rebalance_date, days_until = self.get_next_rebalance_date(strategy_name)
                
                # Determine if rebalance is due (within 7 days or overdue)
                is_rebalance_due = days_until <= 7
                
                comparison = StrategyComparison(
                    strategy_name=strategy_name,
                    display_name=schedule['display_name'],
                    next_rebalance_date=next_rebalance_date,
                    days_until_rebalance=days_until,
                    current_drift_percentage=analysis['drift_percentage'],
                    recommendation=analysis['recommendation'],
                    suggested_changes=analysis['suggested_changes'],
                    is_rebalance_due=is_rebalance_due
                )
                
                comparisons.append(comparison)
                
            except Exception as e:
                # If strategy analysis fails, still show basic info
                next_rebalance_date, days_until = self.get_next_rebalance_date(strategy_name)
                
                comparison = StrategyComparison(
                    strategy_name=strategy_name,
                    display_name=schedule['display_name'],
                    next_rebalance_date=next_rebalance_date,
                    days_until_rebalance=days_until,
                    current_drift_percentage=0.0,
                    recommendation="ERROR",
                    suggested_changes={"buy": [], "sell": [], "keep": []},
                    is_rebalance_due=False
                )
                
                comparisons.append(comparison)
        
        return comparisons

    def get_portfolio_overview(self, current_holdings: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Get complete portfolio overview with all strategy comparisons"""
        comparisons = self.compare_portfolio_to_all_strategies(current_holdings)
        
        # Calculate summary statistics
        total_strategies = len(comparisons)
        strategies_due_for_rebalance = sum(1 for c in comparisons if c.is_rebalance_due)
        high_drift_strategies = sum(1 for c in comparisons if c.current_drift_percentage > 20)
        
        return {
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total_strategies": total_strategies,
                "strategies_due_for_rebalance": strategies_due_for_rebalance,
                "high_drift_strategies": high_drift_strategies,
                "next_rebalance_days": min(c.days_until_rebalance for c in comparisons)
            },
            "strategy_comparisons": [
                {
                    "strategy_name": c.strategy_name,
                    "display_name": c.display_name,
                    "next_rebalance_date": c.next_rebalance_date,
                    "days_until_rebalance": c.days_until_rebalance,
                    "current_drift_percentage": round(c.current_drift_percentage, 2),
                    "recommendation": c.recommendation,
                    "suggested_changes": c.suggested_changes,
                    "is_rebalance_due": c.is_rebalance_due
                }
                for c in comparisons
            ]
        }
