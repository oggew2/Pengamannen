"""
Complete memory-optimized ranking cache with chunked processing.
Fixes memory leaks and implements 2024 best practices.
"""
import logging
from datetime import date
import pandas as pd
import yaml
import gc
from typing import Dict, Any

logger = logging.getLogger(__name__)

def compute_all_rankings_optimized(db) -> Dict[str, Any]:
    """
    Memory-optimized ranking computation with chunked processing.
    Implements 2024 best practices for large dataset handling.
    """
    from models import DailyPrice, Fundamentals, Stock, StrategySignal
    from services.ranking_optimized import (
        optimize_dataframe_memory, filter_real_stocks, filter_financial_companies,
        filter_by_min_market_cap, load_prices_chunked,
        calculate_momentum_with_quality_filter_optimized,
        calculate_value_score_optimized
    )
    
    # Load strategy config
    try:
        with open('config/strategies.yaml') as f:
            strategies = yaml.safe_load(f).get('strategies', {})
    except Exception as e:
        logger.error(f"Failed to load strategies config: {e}")
        return {"error": "Config load failed"}
    
    logger.info("Starting memory-optimized ranking computation...")
    
    # Step 1: Load and optimize smaller datasets first
    logger.info("Loading stocks and fundamentals...")
    stocks = db.query(Stock).all()
    fundamentals = db.query(Fundamentals).all()
    
    if not fundamentals:
        logger.warning("No fundamentals data available")
        return {"error": "No fundamentals data"}
    
    # Step 2: Build efficient lookups
    market_caps = {s.ticker: s.market_cap_msek or 0 for s in stocks}
    stock_types = {s.ticker: getattr(s, 'stock_type', 'stock') for s in stocks}
    stock_sectors = {s.ticker: getattr(s, 'sector', None) for s in stocks}
    
    # Step 3: Create optimized fundamentals DataFrame
    logger.info("Building fundamentals DataFrame...")
    fund_data = []
    for f in fundamentals:
        fund_data.append({
            'ticker': f.ticker,
            'pe': f.pe, 'pb': f.pb, 'ps': f.ps,
            'p_fcf': f.p_fcf, 'ev_ebitda': f.ev_ebitda,
            'dividend_yield': f.dividend_yield,
            'roe': f.roe, 'roa': f.roa, 'roic': f.roic, 'fcfroe': f.fcfroe,
            'payout_ratio': f.payout_ratio,
            'market_cap': market_caps.get(f.ticker, 0),
            'stock_type': stock_types.get(f.ticker, 'stock'),
            'sector': stock_sectors.get(f.ticker)
        })
    
    fund_df = pd.DataFrame(fund_data)
    del fund_data, fundamentals, stocks  # Free memory immediately
    gc.collect()
    
    # Step 4: Optimize DataFrame memory usage
    fund_df = optimize_dataframe_memory(fund_df)
    
    # Step 5: Apply filters early to reduce dataset size
    logger.info("Applying filters...")
    original_count = len(fund_df)
    
    fund_df = filter_real_stocks(fund_df)
    fund_df = filter_financial_companies(fund_df)
    fund_df = filter_by_min_market_cap(fund_df)
    
    valid_tickers = set(fund_df['ticker'])
    logger.info(f"Filtered from {original_count} to {len(valid_tickers)} valid stocks")
    
    if len(valid_tickers) == 0:
        logger.error("No valid stocks after filtering")
        return {"error": "No valid stocks"}
    
    # Step 6: Load prices in chunks (memory-safe)
    prices_df = load_prices_chunked(db, valid_tickers)
    
    if prices_df.empty:
        logger.error("No price data loaded")
        return {"error": "No price data"}
    
    # Step 7: Get current holdings for banding
    current_momentum_holdings = get_current_holdings(db, 'sammansatt_momentum')
    
    # Step 8: Clear old rankings
    logger.info("Clearing old rankings...")
    db.query(StrategySignal).delete()
    db.commit()
    
    # Step 9: Process strategies one by one (memory-safe)
    results = {}
    today = date.today()
    
    for strategy_name, config in strategies.items():
        strategy_type = config.get("category", config.get("type", ""))
        
        try:
            logger.info(f"Computing {strategy_name} ({strategy_type})...")
            
            if strategy_type == "momentum":
                ranked_df = calculate_momentum_with_quality_filter_optimized(
                    prices_df, fund_df,
                    current_holdings=current_momentum_holdings
                )
            elif strategy_type == "value":
                ranked_df = calculate_value_score_optimized(fund_df, prices_df)
            elif strategy_type == "dividend":
                # Simplified dividend strategy
                if 'dividend_yield' in fund_df.columns:
                    div_df = fund_df[fund_df['dividend_yield'] > 0].copy()
                    div_df['rank'] = div_df['dividend_yield'].rank(ascending=False)
                    div_df['score'] = div_df['dividend_yield']
                    ranked_df = div_df[['ticker', 'score', 'rank']].head(10)
                else:
                    ranked_df = pd.DataFrame()
            elif strategy_type == "quality":
                # Simplified quality strategy
                if 'roe' in fund_df.columns:
                    qual_df = fund_df[fund_df['roe'] > 0].copy()
                    qual_df['rank'] = qual_df['roe'].rank(ascending=False)
                    qual_df['score'] = qual_df['roe']
                    ranked_df = qual_df[['ticker', 'score', 'rank']].head(10)
                else:
                    ranked_df = pd.DataFrame()
            else:
                logger.warning(f"Unknown strategy type: {strategy_type}")
                continue
            
            if ranked_df.empty:
                logger.warning(f"No rankings computed for {strategy_name}")
                results[strategy_name] = 0
                continue
            
            # Step 10: Save to database in batches
            batch_size = 50
            signals = []
            
            for _, row in ranked_df.iterrows():
                signals.append(StrategySignal(
                    strategy_name=strategy_name,
                    ticker=row['ticker'],
                    rank=int(row['rank']),
                    score=float(row['score']),
                    calculated_date=today
                ))
                
                if len(signals) >= batch_size:
                    db.add_all(signals)
                    db.commit()
                    signals = []
            
            # Commit remaining
            if signals:
                db.add_all(signals)
                db.commit()
            
            results[strategy_name] = len(ranked_df)
            logger.info(f"✅ {strategy_name}: {len(ranked_df)} rankings saved")
            
            # Clean up strategy-specific data
            del ranked_df
            gc.collect()
            
        except Exception as e:
            logger.error(f"❌ Error computing {strategy_name}: {e}")
            results[strategy_name] = f"error: {str(e)}"
            # Continue with other strategies
            gc.collect()
    
    # Step 11: Final cleanup
    del prices_df, fund_df
    gc.collect()
    
    total_rankings = sum(v for v in results.values() if isinstance(v, int))
    logger.info(f"🎉 Rankings computation complete: {total_rankings} total rankings")
    
    return {
        "computed_date": today.isoformat(),
        "strategies": results,
        "total_rankings": total_rankings,
        "memory_optimized": True
    }


def get_current_holdings(db, strategy_name: str) -> list:
    """Get current holdings for banding."""
    from models import StrategySignal
    
    holdings = db.query(StrategySignal.ticker).filter(
        StrategySignal.strategy_name == strategy_name
    ).order_by(StrategySignal.rank).limit(10).all()
    
    return [h[0] for h in holdings] if holdings else []


def get_cached_rankings(db, strategy_name: str) -> list:
    """Get cached rankings from DB if fresh."""
    from models import StrategySignal
    
    rankings = db.query(StrategySignal).filter(
        StrategySignal.strategy_name == strategy_name,
        StrategySignal.calculated_date == date.today()
    ).order_by(StrategySignal.rank).all()
    
    return rankings
