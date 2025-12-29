"""
Portfolio service - portfolio composition and rebalancing.
Based on strategies.yaml configuration.
"""
import pandas as pd
from datetime import date
from dateutil.relativedelta import relativedelta


def combine_strategies(strategy_results: dict[str, pd.DataFrame], equal_weighting: bool = True) -> pd.DataFrame:
    """
    Combine multiple strategy results into a single portfolio.
    
    Börslabbet "Svenska Portföljen" rules:
    - Equal weight across strategies
    - If stock appears in multiple strategies, it gets double weight (overlap_handling)
    """
    if not strategy_results:
        return pd.DataFrame(columns=['ticker', 'weight', 'strategy'])
    
    holdings = []
    num_strategies = len(strategy_results)
    strategy_weight = 1.0 / num_strategies if equal_weighting else 1.0
    
    for strategy_name, df in strategy_results.items():
        if df.empty:
            continue
        positions = len(df)
        position_weight = strategy_weight / positions if positions > 0 else 0
        
        for _, row in df.iterrows():
            holdings.append({
                'ticker': row['ticker'],
                'weight': position_weight,
                'strategy': strategy_name
            })
    
    return pd.DataFrame(holdings)


def get_next_rebalance_dates(strategies_config: dict, from_date: date = None) -> dict[str, date]:
    """
    Calculate next rebalance date for each strategy.
    
    Reads from new YAML structure:
    - rebalance_frequency: "quarterly" or "annual"
    - rebalance_months: [3, 6, 9, 12] for quarterly
    - rebalance_month: 1/2/3 for annual
    """
    if from_date is None:
        from_date = date.today()
    
    result = {}
    
    for name, config in strategies_config.items():
        frequency = config.get('rebalance_frequency', 'annual')
        
        if frequency == 'quarterly':
            months = config.get('rebalance_months', [3, 6, 9, 12])
            next_date = _find_next_month(from_date, months, 15)  # Mid-month
        else:  # annual
            month = config.get('rebalance_month', 3)
            next_date = _find_next_annual(from_date, month, 28)  # End of month
        
        result[name] = next_date
    
    return result


def should_rebalance(strategy_name: str, today: date, strategies_config: dict) -> bool:
    """Check if a strategy should rebalance today."""
    if strategy_name not in strategies_config:
        raise ValueError(f"Unknown strategy: {strategy_name}")
    
    config = strategies_config[strategy_name]
    frequency = config.get('rebalance_frequency', 'annual')
    
    if frequency == 'quarterly':
        months = config.get('rebalance_months', [3, 6, 9, 12])
        # Rebalance mid-month (around 15th)
        return today.month in months and 10 <= today.day <= 20
    else:  # annual
        month = config.get('rebalance_month', 3)
        # Rebalance end of month
        return today.month == month and today.day >= 25
    
    return False


def _find_next_month(from_date: date, months: list[int], day: int) -> date:
    """Find next date in one of the specified months."""
    for offset in range(13):
        check_date = from_date + relativedelta(months=offset)
        if check_date.month in months:
            actual_day = min(day, _last_day_of_month(check_date))
            target = check_date.replace(day=actual_day)
            if target > from_date:
                return target
    return from_date + relativedelta(months=3)


def _find_next_annual(from_date: date, month: int, day: int) -> date:
    """Find next annual rebalance date."""
    year = from_date.year
    target = date(year, month, min(day, 28))
    target = target.replace(day=min(day, _last_day_of_month(target)))
    if target <= from_date:
        target = date(year + 1, month, min(day, 28))
        target = target.replace(day=min(day, _last_day_of_month(target)))
    return target


def _last_day_of_month(d: date) -> int:
    """Get last day of the month for a given date."""
    next_month = d.replace(day=28) + relativedelta(days=4)
    return (next_month - relativedelta(days=next_month.day)).day
