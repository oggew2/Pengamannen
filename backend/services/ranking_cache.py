"""
Pre-compute and cache strategy rankings in database.
Called after daily sync to ensure rankings are ready for users.
"""
import logging
import gc
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


from services.memory_monitor import monitor_memory_usage

@monitor_memory_usage
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
    
    # Load data with memory optimization - CRITICAL FIX
    logger.info("Loading data for ranking computation with memory optimization...")
    
    # Load stocks first (small dataset)
    stocks = db.query(Stock).all()
    logger.info(f"Loaded {len(stocks)} stocks")
    
    # Load fundamentals (medium dataset)
    fundamentals = db.query(Fundamentals).all()
    logger.info(f"Loaded {len(fundamentals)} fundamentals")
    
    # CRITICAL: Load only recent prices (last 400 days) instead of ALL prices
    from datetime import timedelta
    cutoff_date = date.today() - timedelta(days=400)
    prices = db.query(DailyPrice).filter(DailyPrice.date >= cutoff_date).all()
    logger.info(f"Loaded {len(prices)} recent price records (last 400 days)")
    
    if not prices or not fundamentals:
        logger.warning("No data available for ranking computation")
        return {"error": "No data available"}
    
    # Import memory optimization
    from services.memory_optimizer import optimize_ranking_computation, MemoryOptimizer
    
    # Build DataFrames with memory optimization
    market_caps = {s.ticker: s.market_cap_msek or 0 for s in stocks}
    stock_types = {s.ticker: getattr(s, 'stock_type', 'stock') for s in stocks}
    stock_names = {s.ticker: s.name for s in stocks}
    stock_sectors = {s.ticker: getattr(s, 'sector', None) for s in stocks}
    
    # Create DataFrames in chunks to prevent memory spikes
    logger.info("Building price DataFrame with memory optimization...")
    prices_data = [
        {"ticker": p.ticker, "date": p.date, "close": p.close} 
        for p in prices
    ]
    prices_df = pd.DataFrame(prices_data)
    del prices_data  # Free memory immediately
    
    logger.info("Building fundamentals DataFrame with memory optimization...")
    fund_data = [{
        "ticker": f.ticker, "pe": f.pe, "pb": f.pb, "ps": f.ps,
        "p_fcf": f.p_fcf, "ev_ebitda": f.ev_ebitda,
        "dividend_yield": f.dividend_yield, "roe": f.roe,
        "roa": f.roa, "roic": f.roic, "fcfroe": f.fcfroe,
        "payout_ratio": f.payout_ratio,
        "operating_cf": f.operating_cf,
        "net_income": f.net_income,
        "market_cap": market_caps.get(f.ticker, 0),
        "stock_type": stock_types.get(f.ticker, 'stock'),
        "sector": stock_sectors.get(f.ticker)
    } for f in fundamentals]
    fund_df = pd.DataFrame(fund_data)
    del fund_data  # Free memory immediately
    
    # Apply comprehensive memory optimization
    prices_df, fund_df = optimize_ranking_computation(prices_df, fund_df)
    
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
                    current_holdings=current_momentum_holdings
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
            
            if ranked_df is None or ranked_df.empty:
                logger.warning(f"No results for strategy {strategy_name}")
                continue
            
            # Memory optimization: process in batches for large results
            if len(ranked_df) > 1000:
                ranked_df = MemoryOptimizer.process_in_batches(
                    ranked_df, 
                    batch_size=500,
                    process_func=lambda x: x.head(100)  # Keep top 100 per batch
                )
            
            # Take top 10 and save to database
            top_stocks = ranked_df.head(10)
            
            # Batch insert for better performance
            signals_to_insert = []
            for rank, (_, row) in enumerate(top_stocks.iterrows(), 1):
                signal = StrategySignal(
                    strategy_name=strategy_name,
                    ticker=row['ticker'],
                    rank=rank,
                    score=float(row.get('score', 0)),
                    calculated_date=today  # CRITICAL FIX: Use correct column name
                )
                signals_to_insert.append(signal)
            
            # Bulk insert
            db.bulk_insert_mappings(StrategySignal, [
                {
                    'strategy_name': s.strategy_name,
                    'ticker': s.ticker,
                    'rank': s.rank,
                    'score': s.score,
                    'calculated_date': s.calculated_date  # CRITICAL FIX: Use correct column name
                } for s in signals_to_insert
            ])
            
            results[strategy_name] = {
                "computed": len(ranked_df),
                "top_10": [row['ticker'] for _, row in top_stocks.iterrows()]
            }
            
            logger.info(f"✓ {strategy_name}: {len(ranked_df)} stocks ranked, "
                       f"top 10: {results[strategy_name]['top_10'][:3]}...")
            
            # Memory cleanup after each strategy
            del ranked_df, top_stocks, signals_to_insert
            gc.collect()
            
        except Exception as e:
            logger.error(f"Error computing {strategy_name}: {e}")
            results[strategy_name] = {"error": str(e)}
    
    # Final memory cleanup
    del prices_df, fund_df
    gc.collect()
    
    # Commit all changes
    db.commit()
    logger.info(f"Rankings computation complete: {results}")
    
    return {
        "computed_date": today.isoformat(),
        "strategies": results,
        "total_rankings": sum(v.get("computed", 0) if isinstance(v, dict) else 0 for v in results.values())
    }


def get_cached_rankings(db, strategy_name: str) -> list:
    """Get cached rankings from DB if fresh (same day)."""
    from models import StrategySignal
    
    rankings = db.query(StrategySignal).filter(
        StrategySignal.strategy_name == strategy_name,
        StrategySignal.calculated_date == date.today()
    ).order_by(StrategySignal.rank).all()
    
    return rankings


@monitor_memory_usage
def compute_all_rankings_tv(db) -> dict:
    """
    Compute rankings using TradingView data.
    Much simpler - no price pivot table needed!
    """
    from models import Fundamentals, Stock, StrategySignal
    from services.ranking import (
        calculate_momentum_score_from_tv, get_fscore_from_tv,
        filter_by_min_market_cap, filter_real_stocks, filter_financial_companies,
        _filter_top_percentile
    )
    
    with open('config/strategies.yaml') as f:
        strategies = yaml.safe_load(f).get('strategies', {})
    
    # Load fundamentals with TradingView data
    fundamentals = db.query(Fundamentals).filter(
        Fundamentals.data_source == 'tradingview'
    ).all()
    
    if not fundamentals:
        logger.warning("No TradingView data found, falling back to Avanza")
        return compute_all_rankings(db)
    
    stocks = db.query(Stock).all()
    market_caps = {s.ticker: s.market_cap_msek or 0 for s in stocks}
    stock_types = {s.ticker: getattr(s, 'stock_type', 'stock') for s in stocks}
    stock_sectors = {s.ticker: getattr(s, 'sector', None) for s in stocks}
    
    fund_df = pd.DataFrame([{
        'ticker': f.ticker,
        'market_cap': market_caps.get(f.ticker, (f.market_cap or 0) / 1e6),
        'pe': f.pe, 'pb': f.pb, 'ps': f.ps,
        'p_fcf': f.p_fcf, 'ev_ebitda': f.ev_ebitda,
        'roe': f.roe, 'roa': f.roa, 'roic': f.roic, 'fcfroe': f.fcfroe,
        'dividend_yield': f.dividend_yield,
        'perf_3m': f.perf_3m, 'perf_6m': f.perf_6m, 'perf_12m': f.perf_12m,
        'piotroski_f_score': f.piotroski_f_score,
        'stock_type': stock_types.get(f.ticker, 'stock'),
        'sector': stock_sectors.get(f.ticker),
    } for f in fundamentals])
    
    fund_df = filter_real_stocks(fund_df)
    fund_df = filter_by_min_market_cap(fund_df)
    
    current_momentum_holdings = get_current_holdings(db, 'sammansatt_momentum')
    db.query(StrategySignal).delete()
    
    results = {}
    today = date.today()
    
    for strategy_name, config in strategies.items():
        strategy_type = config.get("category", config.get("type", ""))
        
        try:
            if strategy_type == "momentum":
                filtered = filter_financial_companies(fund_df, for_momentum=True)
                momentum = calculate_momentum_score_from_tv(filtered)
                f_scores = get_fscore_from_tv(filtered)
                if not f_scores.empty:
                    valid = f_scores[f_scores > 3].index
                    momentum = momentum[momentum.index.isin(valid)]
                ranked = momentum.sort_values(ascending=False)
                ranked_df = pd.DataFrame({
                    'ticker': ranked.index, 'rank': range(1, len(ranked)+1), 'score': ranked.values
                })
            elif strategy_type == "value":
                filtered = filter_financial_companies(fund_df)
                df = filtered.set_index('ticker')
                ranks = pd.DataFrame(index=df.index)
                for col in ['pe', 'pb', 'ps', 'p_fcf', 'ev_ebitda']:
                    if col in df.columns:
                        ranks[col] = df[col].rank(ascending=True)
                if 'dividend_yield' in df.columns:
                    ranks['dividend_yield'] = df['dividend_yield'].rank(ascending=False)
                value_score = ranks.mean(axis=1, skipna=True)
                top_value = _filter_top_percentile(-value_score, 40)
                momentum = calculate_momentum_score_from_tv(filtered)
                filtered_mom = momentum[momentum.index.isin(top_value)]
                n_select = max(10, int(len(filtered_mom) * 0.25))
                top_n = filtered_mom.sort_values(ascending=False).head(n_select)
                top10 = top_n.head(10)
                ranked_df = pd.DataFrame({
                    'ticker': top10.index, 'rank': range(1, len(top10)+1), 'score': top10.values
                })
            elif strategy_type == "dividend":
                filtered = filter_financial_companies(fund_df)
                df = filtered.set_index('ticker')
                top_yield = _filter_top_percentile(df['dividend_yield'], 40)
                momentum = calculate_momentum_score_from_tv(filtered)
                filtered_mom = momentum[momentum.index.isin(top_yield)]
                n_select = max(10, int(len(filtered_mom) * 0.25))
                top_n = filtered_mom.sort_values(ascending=False).head(n_select)
                top10 = top_n.head(10)
                ranked_df = pd.DataFrame({
                    'ticker': top10.index, 'rank': range(1, len(top10)+1), 'score': top10.values
                })
            elif strategy_type == "quality":
                filtered = filter_financial_companies(fund_df)
                df = filtered.set_index('ticker')
                ranks = pd.DataFrame(index=df.index)
                for col in ['roe', 'roa', 'roic', 'fcfroe']:
                    if col in df.columns:
                        ranks[col] = df[col].rank(ascending=False, na_option='bottom')
                quality_score = ranks.mean(axis=1)
                top_quality = _filter_top_percentile(-quality_score, 40)
                momentum = calculate_momentum_score_from_tv(filtered)
                filtered_mom = momentum[momentum.index.isin(top_quality)]
                n_select = max(10, int(len(filtered_mom) * 0.25))
                top_n = filtered_mom.sort_values(ascending=False).head(n_select)
                top10 = top_n.head(10)
                ranked_df = pd.DataFrame({
                    'ticker': top10.index, 'rank': range(1, len(top10)+1), 'score': top10.values
                })
            else:
                continue
            
            if ranked_df.empty:
                continue
            
            top_stocks = ranked_df.head(10)
            db.bulk_insert_mappings(StrategySignal, [{
                'strategy_name': strategy_name,
                'ticker': row['ticker'],
                'rank': rank,
                'score': float(row.get('score', 0)),
                'calculated_date': today
            } for rank, (_, row) in enumerate(top_stocks.iterrows(), 1)])
            
            results[strategy_name] = {
                "computed": len(ranked_df),
                "top_10": list(top_stocks['ticker'])
            }
            logger.info(f"✓ {strategy_name}: {len(ranked_df)} stocks, top: {results[strategy_name]['top_10'][:3]}...")
            
        except Exception as e:
            logger.error(f"Error computing {strategy_name}: {e}")
            results[strategy_name] = {"error": str(e)}
    
    db.commit()
    return {"computed_date": today.isoformat(), "strategies": results, "source": "tradingview"}
