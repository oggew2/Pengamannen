"""
Pre-compute and cache strategy rankings in database.
Called after daily sync to ensure rankings are ready for users.
"""
import logging
from datetime import date
import pandas as pd
import yaml

logger = logging.getLogger(__name__)


def get_current_holdings(db, strategy_name: str) -> list:
    """
    Get current holdings for a strategy from the most recent StrategySignal.
    Used for banding in momentum strategy.
    """
    from models import StrategySignal
    
    holdings = db.query(StrategySignal.ticker).filter(
        StrategySignal.strategy_name == strategy_name
    ).order_by(StrategySignal.rank).limit(10).all()
    
    return [h[0] for h in holdings] if holdings else []


def compute_all_rankings(db) -> dict:
    """
    Compute rankings for all strategies and save to StrategySignal table.
    Returns summary of what was computed.
    """
    from models import DailyPrice, Fundamentals, Stock, StrategySignal
    from services.ranking import (
        calculate_momentum_score, calculate_momentum_with_quality_filter,
        calculate_value_score, calculate_dividend_score, calculate_quality_score,
        filter_by_min_market_cap, filter_real_stocks
    )
    
    # Load strategy config
    with open('config/strategies.yaml') as f:
        strategies = yaml.safe_load(f).get('strategies', {})
    
    # Load all data once
    logger.info("Loading data for ranking computation...")
    prices = db.query(DailyPrice).all()
    fundamentals = db.query(Fundamentals).all()
    stocks = db.query(Stock).all()
    
    if not prices or not fundamentals:
        logger.warning("No data available for ranking computation")
        return {"error": "No data available"}
    
    # Build DataFrames
    market_caps = {s.ticker: s.market_cap_msek or 0 for s in stocks}
    stock_types = {s.ticker: getattr(s, 'stock_type', 'stock') for s in stocks}
    stock_names = {s.ticker: s.name for s in stocks}
    stock_sectors = {s.ticker: getattr(s, 'sector', None) for s in stocks}
    
    prices_df = pd.DataFrame([
        {"ticker": p.ticker, "date": p.date, "close": p.close} 
        for p in prices
    ])
    
    fund_df = pd.DataFrame([{
        "ticker": f.ticker, "pe": f.pe, "pb": f.pb, "ps": f.ps,
        "p_fcf": f.p_fcf, "ev_ebitda": f.ev_ebitda,
        "dividend_yield": f.dividend_yield, "roe": f.roe,
        "roa": f.roa, "roic": f.roic, "fcfroe": f.fcfroe,
        "payout_ratio": f.payout_ratio,
        "market_cap": market_caps.get(f.ticker, 0),
        "stock_type": stock_types.get(f.ticker, 'stock'),
        "sector": stock_sectors.get(f.ticker)
    } for f in fundamentals])
    
    # Apply filters
    fund_df = filter_real_stocks(fund_df)
    fund_df = filter_by_min_market_cap(fund_df)
    
    valid_tickers = set(fund_df['ticker'])
    prices_df = prices_df[prices_df['ticker'].isin(valid_tickers)]
    
    logger.info(f"Data loaded: {len(prices_df)} prices, {len(fund_df)} fundamentals")
    
    # Get current holdings before clearing (for banding)
    current_momentum_holdings = get_current_holdings(db, 'sammansatt_momentum')
    
    # Clear old rankings
    db.query(StrategySignal).delete()
    
    results = {}
    today = date.today()
    
    for strategy_name, config in strategies.items():
        strategy_type = config.get("category", config.get("type", ""))
        
        try:
            if strategy_type == "momentum":
                # Use banding with current holdings
                ranked_df = calculate_momentum_with_quality_filter(
                    prices_df, fund_df, 
                    current_holdings=current_momentum_holdings if current_momentum_holdings else None
                )
            elif strategy_type == "value":
                ranked_df = calculate_value_score(fund_df, prices_df)
            elif strategy_type == "dividend":
                ranked_df = calculate_dividend_score(fund_df, prices_df)
            elif strategy_type == "quality":
                ranked_df = calculate_quality_score(fund_df, prices_df)
            else:
                logger.warning(f"Unknown strategy type: {strategy_type}")
                continue
            
            if ranked_df.empty:
                logger.warning(f"No rankings computed for {strategy_name}")
                results[strategy_name] = 0
                continue
            
            # Save to DB
            for _, row in ranked_df.iterrows():
                db.add(StrategySignal(
                    strategy_name=strategy_name,
                    ticker=row['ticker'],
                    rank=int(row['rank']),
                    score=float(row['score']),
                    calculated_date=today
                ))
            
            results[strategy_name] = len(ranked_df)
            logger.info(f"Computed {len(ranked_df)} rankings for {strategy_name}")
            
        except Exception as e:
            logger.error(f"Error computing {strategy_name}: {e}")
            results[strategy_name] = f"error: {str(e)}"
    
    db.commit()
    logger.info(f"Rankings computation complete: {results}")
    
    return {
        "computed_date": today.isoformat(),
        "strategies": results,
        "total_rankings": sum(v for v in results.values() if isinstance(v, int))
    }


def get_cached_rankings(db, strategy_name: str) -> list:
    """Get cached rankings from DB if fresh (same day)."""
    from models import StrategySignal
    
    rankings = db.query(StrategySignal).filter(
        StrategySignal.strategy_name == strategy_name,
        StrategySignal.calculated_date == date.today()
    ).order_by(StrategySignal.rank).all()
    
    return rankings
