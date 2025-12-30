"""Custom strategy builder - user-defined factor combinations."""
import json
import pandas as pd
import numpy as np
from typing import List, Dict, Optional
from sqlalchemy.orm import Session

from models import CustomStrategy
from services.ranking import calculate_momentum_score, filter_by_market_cap


# Available factors for custom strategies
AVAILABLE_FACTORS = {
    # Value factors
    "pe": {"name": "P/E Ratio", "category": "value", "direction": "lower_better"},
    "pb": {"name": "P/B Ratio", "category": "value", "direction": "lower_better"},
    "ps": {"name": "P/S Ratio", "category": "value", "direction": "lower_better"},
    "p_fcf": {"name": "P/FCF", "category": "value", "direction": "lower_better"},
    "ev_ebitda": {"name": "EV/EBITDA", "category": "value", "direction": "lower_better"},
    "dividend_yield": {"name": "Dividend Yield", "category": "value", "direction": "higher_better"},
    
    # Quality factors
    "roe": {"name": "Return on Equity", "category": "quality", "direction": "higher_better"},
    "roa": {"name": "Return on Assets", "category": "quality", "direction": "higher_better"},
    "roic": {"name": "Return on Invested Capital", "category": "quality", "direction": "higher_better"},
    "fcfroe": {"name": "FCF/Equity", "category": "quality", "direction": "higher_better"},
    
    # Momentum factors
    "momentum_3m": {"name": "3-Month Momentum", "category": "momentum", "direction": "higher_better"},
    "momentum_6m": {"name": "6-Month Momentum", "category": "momentum", "direction": "higher_better"},
    "momentum_12m": {"name": "12-Month Momentum", "category": "momentum", "direction": "higher_better"},
    
    # Other
    "market_cap": {"name": "Market Cap", "category": "size", "direction": "higher_better"},
    "payout_ratio": {"name": "Payout Ratio", "category": "dividend", "direction": "lower_better"},
}

FILTER_OPERATORS = ["gt", "gte", "lt", "lte", "eq", "between"]


def get_available_factors() -> Dict:
    """Get list of available factors for custom strategies."""
    return {
        "factors": AVAILABLE_FACTORS,
        "operators": FILTER_OPERATORS
    }


def create_custom_strategy(
    db: Session,
    name: str,
    factors: List[Dict],
    filters: List[Dict] = None,
    description: str = None,
    rebalance_frequency: str = "quarterly",
    position_count: int = 10
) -> int:
    """
    Create a custom strategy.
    
    Args:
        factors: List of {factor, weight, direction} where direction is 'higher_better' or 'lower_better'
        filters: List of {field, operator, value}
    """
    strategy = CustomStrategy(
        name=name,
        description=description,
        factors_json=json.dumps(factors),
        filters_json=json.dumps(filters or []),
        rebalance_frequency=rebalance_frequency,
        position_count=position_count
    )
    db.add(strategy)
    db.commit()
    return strategy.id


def get_custom_strategy(db: Session, strategy_id: int) -> Optional[Dict]:
    """Get a custom strategy by ID."""
    strategy = db.query(CustomStrategy).filter(CustomStrategy.id == strategy_id).first()
    if not strategy:
        return None
    
    return {
        "id": strategy.id,
        "name": strategy.name,
        "description": strategy.description,
        "factors": json.loads(strategy.factors_json),
        "filters": json.loads(strategy.filters_json) if strategy.filters_json else [],
        "rebalance_frequency": strategy.rebalance_frequency,
        "position_count": strategy.position_count
    }


def list_custom_strategies(db: Session) -> List[Dict]:
    """List all custom strategies."""
    strategies = db.query(CustomStrategy).all()
    return [{
        "id": s.id,
        "name": s.name,
        "description": s.description,
        "position_count": s.position_count,
        "rebalance_frequency": s.rebalance_frequency
    } for s in strategies]


def delete_custom_strategy(db: Session, strategy_id: int) -> bool:
    """Delete a custom strategy."""
    strategy = db.query(CustomStrategy).filter(CustomStrategy.id == strategy_id).first()
    if strategy:
        db.delete(strategy)
        db.commit()
        return True
    return False


def apply_filters(df: pd.DataFrame, filters: List[Dict]) -> pd.DataFrame:
    """Apply filters to dataframe."""
    for f in filters:
        field = f.get("field")
        op = f.get("operator")
        value = f.get("value")
        
        if field not in df.columns:
            continue
        
        if op == "gt":
            df = df[df[field] > value]
        elif op == "gte":
            df = df[df[field] >= value]
        elif op == "lt":
            df = df[df[field] < value]
        elif op == "lte":
            df = df[df[field] <= value]
        elif op == "eq":
            df = df[df[field] == value]
        elif op == "between" and isinstance(value, list) and len(value) == 2:
            df = df[(df[field] >= value[0]) & (df[field] <= value[1])]
    
    return df


def run_custom_strategy(
    fund_df: pd.DataFrame,
    prices_df: pd.DataFrame,
    factors: List[Dict],
    filters: List[Dict] = None,
    position_count: int = 10,
    use_market_cap_filter: bool = True
) -> pd.DataFrame:
    """
    Run a custom strategy on data.
    
    Args:
        factors: List of {factor, weight, direction}
        filters: List of {field, operator, value}
    """
    if fund_df.empty:
        return pd.DataFrame(columns=['ticker', 'rank', 'score'])
    
    # Market cap filter
    if use_market_cap_filter:
        fund_df = filter_by_market_cap(fund_df, 40)
    
    df = fund_df.set_index('ticker').copy()
    
    # Add momentum if needed
    momentum_factors = [f for f in factors if f['factor'].startswith('momentum_')]
    if momentum_factors and not prices_df.empty:
        momentum = calculate_momentum_score(prices_df)
        # Split into 3m, 6m, 12m (simplified - use composite for now)
        for ticker in df.index:
            if ticker in momentum.index:
                df.loc[ticker, 'momentum_3m'] = momentum[ticker]
                df.loc[ticker, 'momentum_6m'] = momentum[ticker]
                df.loc[ticker, 'momentum_12m'] = momentum[ticker]
    
    # Apply filters
    if filters:
        df = apply_filters(df, filters)
    
    if df.empty:
        return pd.DataFrame(columns=['ticker', 'rank', 'score'])
    
    # Calculate composite score
    ranks = pd.DataFrame(index=df.index)
    total_weight = sum(f.get('weight', 1) for f in factors)
    
    for f in factors:
        factor_name = f['factor']
        weight = f.get('weight', 1) / total_weight
        direction = f.get('direction', AVAILABLE_FACTORS.get(factor_name, {}).get('direction', 'higher_better'))
        
        if factor_name not in df.columns:
            continue
        
        # Rank (1 = best)
        ascending = direction == 'lower_better'
        ranks[factor_name] = df[factor_name].rank(ascending=ascending, na_option='bottom') * weight
    
    if ranks.empty:
        return pd.DataFrame(columns=['ticker', 'rank', 'score'])
    
    # Composite score (lower rank = better)
    composite = ranks.sum(axis=1)
    top = composite.nsmallest(position_count)
    
    return pd.DataFrame({
        'ticker': top.index,
        'rank': range(1, len(top) + 1),
        'score': top.values
    })
