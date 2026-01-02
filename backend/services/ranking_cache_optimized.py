"""
Optimized ranking computation with memory management.
"""
import logging
from datetime import date
import pandas as pd
import yaml
import gc

logger = logging.getLogger(__name__)

def compute_all_rankings(db) -> dict:
    """
    Memory-optimized ranking computation.
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
    
    logger.info("Loading data for ranking computation...")
    
    # Load stocks and fundamentals (smaller datasets)
    stocks = db.query(Stock).all()
    fundamentals = db.query(Fundamentals).all()
    
    if not fundamentals:
        logger.warning("No fundamentals data available")
        return {"error": "No fundamentals data"}
    
    # Build lookups (memory efficient)
    market_caps = {s.ticker: s.market_cap_msek or 0 for s in stocks}
    stock_types = {s.ticker: getattr(s, 'stock_type', 'stock') for s in stocks}
    stock_names = {s.ticker: s.name for s in stocks}
    stock_sectors = {s.ticker: getattr(s, 'sector', None) for s in stocks}
    
    # Build fundamentals DataFrame
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
    
    # Apply filters early to reduce dataset
    fund_df = filter_real_stocks(fund_df)
    fund_df = filter_by_min_market_cap(fund_df)
    valid_tickers = set(fund_df['ticker'])
    
    logger.info(f"Filtered to {len(valid_tickers)} valid stocks")
    
    # Load prices ONLY for valid tickers (memory optimization)
    prices_query = db.query(DailyPrice).filter(DailyPrice.ticker.in_(valid_tickers))
    
    # Process prices in chunks to avoid memory overload
    chunk_size = 50000  # Process 50k records at a time
    prices_data = []
    
    for i in range(0, prices_query.count(), chunk_size):
        chunk = prices_query.offset(i).limit(chunk_size).all()
        chunk_data = [{"ticker": p.ticker, "date": p.date, "close": p.close} for p in chunk]
        prices_data.extend(chunk_data)
        
        # Force garbage collection after each chunk
        del chunk, chunk_data
        gc.collect()
        
        logger.info(f"Loaded price chunk {i//chunk_size + 1}")
    
    prices_df = pd.DataFrame(prices_data)
    del prices_data  # Free memory
    gc.collect()
    
    logger.info(f"Data loaded: {len(prices_df)} prices, {len(fund_df)} fundamentals")
    
    # Get current holdings before clearing
    current_momentum_holdings = get_current_holdings(db, 'sammansatt_momentum')
    
    # Clear old rankings
    db.query(StrategySignal).delete()
    db.commit()  # Commit deletion immediately
    
    results = {}
    today = date.today()
    
    # Process strategies one by one to manage memory
    for strategy_name, config in strategies.items():
        strategy_type = config.get("category", config.get("type", ""))
        
        try:
            logger.info(f"Computing {strategy_name}...")
            
            if strategy_type == "momentum":
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
            
            # Save to DB in batches
            batch_size = 100
            signals = []
            
            for _, row in ranked_df.iterrows():
                signals.append(StrategySignal(
                    strategy_name=strategy_name,
                    ticker=row['ticker'],
                    rank=int(row['rank']),
                    score=float(row['score']),
                    calculated_date=today
                ))
                
                # Commit in batches
                if len(signals) >= batch_size:
                    db.add_all(signals)
                    db.commit()
                    signals = []
            
            # Commit remaining
            if signals:
                db.add_all(signals)
                db.commit()
            
            results[strategy_name] = len(ranked_df)
            logger.info(f"Computed {len(ranked_df)} rankings for {strategy_name}")
            
            # Clean up strategy-specific data
            del ranked_df
            gc.collect()
            
        except Exception as e:
            logger.error(f"Error computing {strategy_name}: {e}")
            results[strategy_name] = f"error: {str(e)}"
    
    # Final cleanup
    del prices_df, fund_df
    gc.collect()
    
    logger.info(f"Rankings computation complete: {results}")
    
    return {
        "computed_date": today.isoformat(),
        "strategies": results,
        "total_rankings": sum(v for v in results.values() if isinstance(v, int))
    }


def get_current_holdings(db, strategy_name: str) -> list:
    """Get current holdings for a strategy."""
    from models import StrategySignal
    
    holdings = db.query(StrategySignal.ticker).filter(
        StrategySignal.strategy_name == strategy_name
    ).order_by(StrategySignal.rank).limit(10).all()
    
    return [h[0] for h in holdings] if holdings else []
