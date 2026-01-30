"""
Pre-compute and cache strategy rankings in database.
Called after daily sync to ensure rankings are ready for users.
"""
import logging
import gc
from datetime import date, datetime
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


def compute_nordic_momentum(db=None) -> dict:
    """
    Compute Nordic Sammansatt Momentum rankings directly from TradingView.
    Does not require database - fetches fresh data from all Nordic markets.
    
    Returns:
        dict with rankings and metadata
    """
    from services.tradingview_fetcher import TradingViewFetcher
    from services.ranking import filter_financial_companies, calculate_momentum_score_from_tv, get_fscore_from_tv
    
    logger.info("Computing Nordic Sammansatt Momentum...")
    
    # Fetch Nordic stocks with 2B SEK threshold
    fetcher = TradingViewFetcher()
    stocks = fetcher.fetch_nordic(min_market_cap_sek=2e9)
    
    if not stocks:
        logger.error("No Nordic stocks fetched")
        return {"error": "No data available"}
    
    # Build DataFrame
    df = pd.DataFrame(stocks)
    
    # ========== FILTERS (matching Börslabbet methodology) ==========
    
    # 1. Finance sector - excluded because financial metrics not comparable
    #    (banks, investment companies, insurance, REITs)
    df = df[df['sector'] != 'Finance']
    logger.info(f"After Finance filter: {len(df)} stocks")
    
    # 2. Preference shares - different risk/return profile, fixed dividends
    df = df[~df['ticker'].str.contains('PREF', case=False, na=False)]
    logger.info(f"After preference share filter: {len(df)} stocks")
    
    # 3. Investment/capital companies that slipped through sector classification
    def is_investment_company(name):
        name_lower = name.lower()
        name_clean = name_lower.replace(' class a', '').replace(' class b', '').replace(' ser. a', '').replace(' ser. b', '').strip()
        if 'investment ab' in name_lower or 'investment a/s' in name_lower:
            return True
        if 'invest ab' in name_lower:
            return True
        if name_clean.endswith('capital ab') or name_clean.endswith('capital a/s'):
            return True
        return False
    
    df = df[~df['name'].apply(is_investment_company)]
    logger.info(f"After investment company filter: {len(df)} stocks")
    
    # 4. Momentum confirmation filter - exclude "fading momentum" stocks
    #    Stocks with negative 3m AND 6m but positive 12m are showing reversal, not momentum
    #    This is academically sound: momentum strategies rely on trend continuation
    df = df[~((df['perf_3m'] < 0) & (df['perf_6m'] < 0))]
    logger.info(f"After momentum confirmation filter: {len(df)} stocks")
    
    # Calculate momentum score
    df['momentum'] = (
        df['perf_3m'].fillna(0) + 
        df['perf_6m'].fillna(0) + 
        df['perf_12m'].fillna(0)
    ) / 3
    
    # Apply F-Score filter (>= 5, matching Börslabbet)
    df_quality = df[df['piotroski_f_score'].fillna(0) >= 5]
    logger.info(f"After F-Score >= 5 filter: {len(df_quality)} stocks")
    
    # If too few stocks pass F-Score filter, use all
    if len(df_quality) < 20:
        logger.warning("Too few stocks pass F-Score filter, using all non-financial stocks")
        df_quality = df
    
    # Rank by momentum
    df_ranked = df_quality.sort_values('momentum', ascending=False)
    
    # Get top 40 for display (top 10 for portfolio, 11-40 for reference)
    top40 = df_ranked.head(40)
    
    results = []
    for rank, (_, row) in enumerate(top40.iterrows(), 1):
        price_sek = row.get('price_sek') or row.get('close', 0)
        price_local = row.get('close', 0)
        results.append({
            'rank': rank,
            'ticker': row['ticker'],
            'name': row['name'],
            'market': row['market'],
            'currency': row['currency'],
            'price': round(price_sek, 2),  # Price in SEK (2 decimals)
            'price_local': round(price_local, 2),  # Price in local currency
            'market_cap_sek': row['market_cap_sek'],
            'momentum': round(row['momentum'], 2),
            'perf_3m': row['perf_3m'],
            'perf_6m': row['perf_6m'],
            'perf_12m': row['perf_12m'],
            'f_score': row.get('piotroski_f_score'),
            'sector': row['sector'],
        })
    
    # Save top 10 to database if provided
    if db:
        from models import StrategySignal
        today = date.today()
        
        # Clear old Nordic momentum signals
        db.query(StrategySignal).filter(
            StrategySignal.strategy_name == 'nordic_sammansatt_momentum'
        ).delete()
        
        # Insert new signals (only top 10)
        for r in results[:10]:
            signal = StrategySignal(
                strategy_name='nordic_sammansatt_momentum',
                ticker=r['ticker'],
                rank=r['rank'],
                score=float(r['momentum']),
                calculated_date=today
            )
            db.add(signal)
        db.commit()
        logger.info(f"Saved Nordic momentum rankings to database")
    
    return {
        'strategy': 'nordic_sammansatt_momentum',
        'computed_at': datetime.now().isoformat(),
        'total_universe': len(stocks),
        'after_filters': len(df_quality),
        'rankings': results,
        'by_market': {m: sum(1 for r in results if r['market'] == m) for m in ['sweden', 'finland', 'norway', 'denmark']}
    }


def compute_nordic_momentum_banded(db, current_holdings: list[str] = None) -> dict:
    """
    Compute Nordic momentum with banding logic.
    
    Banding rules (from Börslabbet):
    - Buy: Top 10 stocks by momentum
    - Sell: Only when stock falls below rank 20
    - Replace sold stocks with highest-ranked not in portfolio
    
    Args:
        db: Database session
        current_holdings: List of tickers currently held (if None, loads from DB)
    
    Returns:
        dict with recommendations (hold/buy/sell) and full rankings
    """
    from services.tradingview_fetcher import TradingViewFetcher
    from models import BandingHolding
    
    BUY_THRESHOLD = 10   # Buy top 10
    SELL_THRESHOLD = 20  # Sell when below rank 20
    
    logger.info("Computing Nordic momentum with banding...")
    
    # Fetch fresh rankings
    fetcher = TradingViewFetcher()
    stocks = fetcher.fetch_nordic(min_market_cap_sek=2e9)
    
    if not stocks:
        return {"error": "No data available"}
    
    # Build DataFrame and apply filters (same as compute_nordic_momentum)
    df = pd.DataFrame(stocks)
    
    # 1. Finance sector exclusion
    df = df[df['sector'] != 'Finance']
    
    # 2. Preference shares exclusion
    df = df[~df['ticker'].str.contains('PREF', case=False, na=False)]
    
    # 3. Investment company exclusion
    def is_investment_company(name):
        name_lower = name.lower()
        name_clean = name_lower.replace(' class a', '').replace(' class b', '').replace(' ser. a', '').replace(' ser. b', '').strip()
        if 'investment ab' in name_lower or 'investment a/s' in name_lower:
            return True
        if 'invest ab' in name_lower:
            return True
        if name_clean.endswith('capital ab') or name_clean.endswith('capital a/s'):
            return True
        return False
    
    df = df[~df['name'].apply(is_investment_company)]
    
    # 4. Momentum confirmation filter - exclude fading momentum stocks
    df = df[~((df['perf_3m'] < 0) & (df['perf_6m'] < 0))]
    
    # Calculate momentum
    df['momentum'] = (df['perf_3m'].fillna(0) + df['perf_6m'].fillna(0) + df['perf_12m'].fillna(0)) / 3
    
    # F-Score filter
    df_quality = df[df['piotroski_f_score'].fillna(0) >= 5]
    
    if len(df_quality) < 20:
        df_quality = df
    
    # Rank all stocks
    df_ranked = df_quality.sort_values('momentum', ascending=False).reset_index(drop=True)
    df_ranked['rank'] = range(1, len(df_ranked) + 1)
    
    # Get current holdings from DB if not provided
    if current_holdings is None and db:
        active_holdings = db.query(BandingHolding).filter(
            BandingHolding.strategy == 'nordic_sammansatt_momentum',
            BandingHolding.is_active == True
        ).all()
        current_holdings = [h.ticker for h in active_holdings]
    
    current_holdings = current_holdings or []
    today = date.today()
    
    # Determine actions
    hold = []
    sell = []
    buy = []
    
    # Check current holdings
    for ticker in current_holdings:
        row = df_ranked[df_ranked['ticker'] == ticker]
        if row.empty:
            # Stock no longer in universe - sell
            sell.append({'ticker': ticker, 'reason': 'not_in_universe', 'rank': None})
        else:
            rank = int(row['rank'].iloc[0])
            if rank > SELL_THRESHOLD:
                sell.append({'ticker': ticker, 'reason': 'below_threshold', 'rank': rank})
            else:
                hold.append({'ticker': ticker, 'rank': rank})
    
    # Calculate how many slots to fill
    slots_to_fill = BUY_THRESHOLD - len(hold)
    
    # Find candidates to buy (top ranked not already held)
    held_tickers = set(h['ticker'] for h in hold)
    for _, row in df_ranked.iterrows():
        if slots_to_fill <= 0:
            break
        if row['ticker'] not in held_tickers:
            buy.append({
                'ticker': row['ticker'],
                'name': row['name'],
                'rank': int(row['rank']),
                'momentum': row['momentum'],
                'market': row['market'],
                'currency': row['currency'],
            })
            slots_to_fill -= 1
    
    # Update database if provided
    if db:
        # Mark sold holdings as inactive
        for s in sell:
            holding = db.query(BandingHolding).filter(
                BandingHolding.strategy == 'nordic_sammansatt_momentum',
                BandingHolding.ticker == s['ticker'],
                BandingHolding.is_active == True
            ).first()
            if holding:
                holding.is_active = False
                holding.exit_date = today
                holding.exit_rank = s['rank']
        
        # Update ranks for held stocks
        for h in hold:
            holding = db.query(BandingHolding).filter(
                BandingHolding.strategy == 'nordic_sammansatt_momentum',
                BandingHolding.ticker == h['ticker'],
                BandingHolding.is_active == True
            ).first()
            if holding:
                holding.current_rank = h['rank']
                holding.last_updated = today
        
        # Add new holdings
        for b in buy:
            new_holding = BandingHolding(
                strategy='nordic_sammansatt_momentum',
                ticker=b['ticker'],
                entry_rank=b['rank'],
                entry_date=today,
                current_rank=b['rank'],
                last_updated=today,
                is_active=True
            )
            db.add(new_holding)
        
        db.commit()
        logger.info(f"Banding updated: hold={len(hold)}, sell={len(sell)}, buy={len(buy)}")
    
    # Build full rankings for reference
    top20 = []
    for _, row in df_ranked.head(20).iterrows():
        top20.append({
            'rank': int(row['rank']),
            'ticker': row['ticker'],
            'name': row['name'],
            'momentum': row['momentum'],
            'market': row['market'],
        })
    
    return {
        'strategy': 'nordic_sammansatt_momentum',
        'computed_date': today.isoformat(),
        'banding': {
            'buy_threshold': BUY_THRESHOLD,
            'sell_threshold': SELL_THRESHOLD,
        },
        'recommendations': {
            'hold': hold,
            'sell': sell,
            'buy': buy,
        },
        'portfolio': [h['ticker'] for h in hold] + [b['ticker'] for b in buy],
        'top20_rankings': top20,
    }


def calculate_allocation(investment_amount: float, stocks: list, target_count: int = 10, force_include: set = None) -> dict:
    """
    Calculate equal-weight portfolio allocation with smart rounding.
    
    Args:
        investment_amount: Total SEK to invest
        stocks: List of dicts with ticker, name, price, momentum, etc.
        target_count: Number of stocks (default 10)
        force_include: Set of tickers to include even if too expensive (buy 1 share)
    
    Returns:
        dict with allocations, warnings, and summary
    """
    if not stocks or investment_amount <= 0:
        return {"error": "Invalid input"}
    
    force_include = force_include or set()
    target_weight = 1.0 / target_count  # 10% each
    target_amount = investment_amount * target_weight
    
    allocations = []
    warnings = []
    
    for i, stock in enumerate(stocks[:target_count]):
        price = stock.get('price_sek') or stock.get('price') or stock.get('close') or 0
        
        if price <= 0:
            warnings.append(f"{stock['ticker']}: No price data")
            continue
        
        # Check if stock is too expensive
        if price > target_amount:
            if stock['ticker'] in force_include:
                # User wants to buy 1 share anyway
                shares = 1
                too_expensive = True
                warnings.append(f"{stock['ticker']}: Forced 1 share @ {price:.0f} SEK (over target)")
            else:
                shares = 0
                too_expensive = True
                warnings.append(f"{stock['ticker']}: Price {price:.0f} SEK > target {target_amount:.0f} SEK")
        else:
            shares = int(target_amount // price)  # Floor division
            too_expensive = False
        
        actual_amount = shares * price
        actual_weight = actual_amount / investment_amount if investment_amount > 0 else 0
        deviation = actual_weight - target_weight
        
        currency = stock.get('currency', 'SEK')
        price_local = stock.get('price_local', price)
        
        allocations.append({
            "rank": stock.get('original_rank', i + 1),
            "ticker": stock['ticker'],
            "name": stock.get('name', ''),
            "price": price,  # Always SEK for calculations
            "price_local": price_local if currency != 'SEK' else None,  # Original currency price
            "currency": currency,
            "shares": shares,
            "target_amount": round(target_amount, 2),
            "actual_amount": round(actual_amount, 2),
            "target_weight": round(target_weight * 100, 1),
            "actual_weight": round(actual_weight * 100, 1),
            "deviation": round(deviation * 100, 1),
            "too_expensive": too_expensive,
            "included": shares > 0,
        })
    
    # Calculate totals
    total_invested = sum(a['actual_amount'] for a in allocations if a['included'])
    cash_remaining = investment_amount - total_invested
    
    # Distribute remaining cash (greedy: add to most underweight stocks)
    if cash_remaining > 0:
        # Sort by deviation (most negative first = most underweight)
        for alloc in sorted(allocations, key=lambda x: x['deviation']):
            if not alloc['included'] or alloc['price'] <= 0:
                continue
            
            # How many more shares can we buy?
            extra_shares = int(cash_remaining // alloc['price'])
            if extra_shares > 0:
                alloc['shares'] += extra_shares
                added = extra_shares * alloc['price']
                alloc['actual_amount'] += added
                alloc['actual_weight'] = round((alloc['actual_amount'] / investment_amount) * 100, 1)
                alloc['deviation'] = round(alloc['actual_weight'] - alloc['target_weight'], 1)
                cash_remaining -= added
                
            if cash_remaining < min(a['price'] for a in allocations if a['included'] and a['price'] > 0):
                break
    
    # Recalculate totals
    total_invested = sum(a['actual_amount'] for a in allocations if a['included'])
    cash_remaining = investment_amount - total_invested
    stocks_included = sum(1 for a in allocations if a['included'] and a['shares'] > 0)
    
    # Calculate Avanza transaction costs
    # Start class: 0.25% (min 1 kr) - most common for retail investors
    # Mini class: 0.15% (min 1 kr) - after 50k monthly volume
    # Small class: 0.069% (min 1 kr) - after 500k monthly volume
    # Swedish stocks: base rate, Nordic stocks: +0.09% extra
    commission_start = 0
    commission_mini = 0
    commission_small = 0
    for a in allocations:
        if a['included'] and a['shares'] > 0:
            amt = a['actual_amount']
            commission_start += max(1, amt * 0.0025)
            commission_mini += max(1, amt * 0.0015)
            commission_small += max(1, amt * 0.00069)
    
    return {
        "investment_amount": investment_amount,
        "target_per_stock": round(target_amount, 2),
        "allocations": allocations,
        "summary": {
            "total_invested": round(total_invested, 2),
            "cash_remaining": round(cash_remaining, 2),
            "utilization": round((total_invested / investment_amount) * 100, 1) if investment_amount > 0 else 0,
            "stocks_included": stocks_included,
            "stocks_skipped": len(allocations) - stocks_included,
            "max_deviation": round(max(abs(a['deviation']) for a in allocations if a['included']) if stocks_included > 0 else 0, 1),
            "commission_start": round(commission_start, 0),
            "commission_mini": round(commission_mini, 0),
            "commission_small": round(commission_small, 0),
        },
        "warnings": warnings,
        "optimal_amounts": _find_optimal_amounts([a['price'] for a in allocations if a['included']], investment_amount, target_count),
    }


def _find_optimal_amounts(prices: list, base_amount: float, target_count: int = 10) -> list:
    """Find nearby investment amounts with lower deviation."""
    prices = [p for p in prices if p > 0]
    if not prices or len(prices) < 2:
        return []
    
    results = []
    # Test amounts that are multiples of share counts
    for shares in range(1, 30):
        for price in prices[:5]:  # Use top 5 prices
            amt = shares * price * target_count
            if amt >= base_amount * 0.8 and amt <= base_amount * 1.5:
                target_per = amt / target_count
                max_dev = 0
                total = 0
                for p in prices:
                    s = int(target_per // p)
                    if s > 0:
                        actual = s * p
                        total += actual
                        dev = abs((actual / amt * 100) - (100 / target_count))
                        max_dev = max(max_dev, dev)
                    else:
                        max_dev = 100
                        break
                if max_dev < 100:
                    results.append({'amount': int(amt), 'max_deviation': round(max_dev, 1)})
    
    # Dedupe and sort
    seen = set()
    unique = []
    for r in sorted(results, key=lambda x: (x['max_deviation'], abs(x['amount'] - base_amount))):
        if r['amount'] not in seen:
            seen.add(r['amount'])
            unique.append(r)
        if len(unique) >= 3:
            break
    return unique


def calculate_rebalance_with_banding(
    current_holdings: list,
    new_investment: float,
    ranked_stocks: list,
    price_lookup: dict,
    currency_lookup: dict = None,
    buy_threshold: int = 10,
    sell_threshold: int = 20,
) -> dict:
    """
    Calculate rebalancing trades using banding logic.
    
    Banding rules (from Börslabbet):
    - HOLD: Stocks still in top 20
    - SELL: Stocks that fell below rank 20 (or not in universe)
    - BUY: Fill to 10 stocks from top-ranked not already held
    
    Args:
        current_holdings: List of {ticker, shares, avg_price?}
        new_investment: Additional cash to invest (can be 0)
        ranked_stocks: List of stocks ranked by momentum
        price_lookup: Dict of ticker -> current price
        buy_threshold: Target portfolio size (default 10)
        sell_threshold: Sell when rank exceeds this (default 20)
    
    Returns:
        dict with hold/sell/buy recommendations and share counts
    """
    # Build rank and name lookup
    rank_lookup = {s['ticker']: i + 1 for i, s in enumerate(ranked_stocks)}
    name_lookup = {s['ticker']: s.get('name', '') for s in ranked_stocks}
    currency_lookup = currency_lookup or {}
    
    # Analyze current holdings
    hold = []
    sell = []
    current_value = 0
    
    for h in current_holdings:
        ticker = h['ticker']
        shares = h.get('shares', 0)
        price = price_lookup.get(ticker, 0)
        value = shares * price
        rank = rank_lookup.get(ticker)
        name = name_lookup.get(ticker, '')
        currency = currency_lookup.get(ticker, 'SEK')
        
        if rank is None:
            # Stock not in universe - sell
            sell.append({
                'ticker': ticker,
                'name': name,
                'shares': shares,
                'price': price,
                'value': value,
                'currency': currency,
                'reason': 'not_in_universe',
                'rank': None,
            })
        elif rank > sell_threshold:
            # Below threshold - sell
            sell.append({
                'ticker': ticker,
                'name': name,
                'shares': shares,
                'price': price,
                'value': value,
                'currency': currency,
                'reason': 'below_threshold',
                'rank': rank,
            })
        else:
            # Keep
            hold.append({
                'ticker': ticker,
                'name': name,
                'shares': shares,
                'price': price,
                'value': value,
                'currency': currency,
                'rank': rank,
            })
            current_value += value
    
    # Calculate available cash
    sell_proceeds = sum(s['value'] for s in sell)
    total_cash = new_investment + sell_proceeds
    
    # Find stocks to buy - always buy current top 10 with new investment
    held_tickers = set(h['ticker'] for h in hold)
    buy = []
    
    if new_investment > 0:
        # Buy current top 10 with new money (equal weight)
        top_10 = [s for s in ranked_stocks if rank_lookup.get(s['ticker'], 999) <= buy_threshold][:buy_threshold]
        target_per_stock = new_investment / len(top_10) if top_10 else 0
        
        for stock in top_10:
            price = price_lookup.get(stock['ticker'], 0)
            if price <= 0:
                continue
            shares = int(target_per_stock // price)
            if shares > 0:
                buy.append({
                    'ticker': stock['ticker'],
                    'name': stock.get('name', ''),
                    'rank': rank_lookup.get(stock['ticker']),
                    'price': price,
                    'shares': shares,
                    'value': shares * price,
                    'currency': currency_lookup.get(stock['ticker'], 'SEK'),
                })
    
    # Also fill empty slots from sells (if any)
    slots_to_fill = buy_threshold - len(hold) - len([b for b in buy if b['ticker'] not in held_tickers])
    
    if slots_to_fill > 0 and total_cash > 0:
        # Target value per new stock
        target_per_stock = total_cash / slots_to_fill if slots_to_fill > 0 else 0
        
        for stock in ranked_stocks:
            if slots_to_fill <= 0:
                break
            if stock['ticker'] in held_tickers:
                continue
            
            price = price_lookup.get(stock['ticker'], 0)
            if price <= 0:
                continue
            
            # Calculate shares to buy
            shares = int(target_per_stock // price) if target_per_stock > 0 else 0
            if shares > 0:
                value = shares * price
                currency = currency_lookup.get(stock['ticker'], 'SEK')
                buy.append({
                    'ticker': stock['ticker'],
                    'name': stock.get('name', ''),
                    'rank': rank_lookup.get(stock['ticker']),
                    'price': price,
                    'shares': shares,
                    'value': value,
                    'currency': currency,
                })
                total_cash -= value
                slots_to_fill -= 1
    
    # Calculate final portfolio
    final_portfolio = []
    total_value = current_value + sum(b['value'] for b in buy)
    
    for h in hold:
        weight = (h['value'] / total_value * 100) if total_value > 0 else 0
        final_portfolio.append({**h, 'action': 'HOLD', 'weight': round(weight, 1)})
    
    for b in buy:
        weight = (b['value'] / total_value * 100) if total_value > 0 else 0
        final_portfolio.append({**b, 'action': 'BUY', 'weight': round(weight, 1)})
    
    final_portfolio.sort(key=lambda x: x.get('rank') or 999)
    
    return {
        'mode': 'banding',
        'current_holdings_count': len(current_holdings),
        'hold': hold,
        'sell': sell,
        'buy': buy,
        'final_portfolio': final_portfolio,
        'summary': {
            'stocks_held': len(hold),
            'stocks_sold': len(sell),
            'stocks_bought': len(buy),
            'sell_proceeds': round(sell_proceeds, 2),
            'new_investment': round(new_investment, 2),
            'total_cash_used': round(sum(b['value'] for b in buy), 2),
            'cash_remaining': round(total_cash, 2),
            'final_portfolio_value': round(total_value, 2),
            'final_stock_count': len(final_portfolio),
        },
    }
