"""
Backtesting service for strategy performance simulation.
Runs strategies on historical data and calculates returns/metrics.
"""
import pandas as pd
import numpy as np
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
import json
import logging
import gc

# Import memory optimization
from services.memory_optimizer import MemoryOptimizer

logger = logging.getLogger(__name__)

INITIAL_CAPITAL = 100000
TRANSACTION_COST_PCT = 0.001  # 0.1% per trade (buy or sell)
SLIPPAGE_PCT = 0.0005  # 0.05% slippage


def calculate_max_drawdown(equity_curve: list) -> float:
    """
    Calculate maximum drawdown from equity curve.
    
    Returns:
        Max drawdown as negative percentage (e.g., -25.5)
    """
    if not equity_curve or len(equity_curve) < 2:
        return 0.0
    
    peak = equity_curve[0]
    max_dd = 0.0
    
    for value in equity_curve:
        if value > peak:
            peak = value
        dd = (value - peak) / peak
        if dd < max_dd:
            max_dd = dd
    
    return round(max_dd * 100, 2)


def calculate_sharpe_ratio(returns: list, annualize: bool = True, risk_free_rate: float = 0.0) -> float:
    """
    Calculate Sharpe ratio from returns.
    
    Returns:
        Sharpe ratio (assumes risk-free rate = 0)
    """
    if not returns or len(returns) < 2:
        return 0.0
    
    returns_arr = np.array(returns) - risk_free_rate / 12  # Monthly risk-free rate
    mean_return = np.mean(returns_arr)
    std_return = np.std(returns_arr, ddof=1)
    
    if std_return == 0:
        return 0.0
    
    sharpe = mean_return / std_return
    if annualize:
        sharpe *= np.sqrt(12)  # Annualize monthly returns
    
    return round(sharpe, 2)


def calculate_sortino_ratio(returns: list, annualize: bool = True, risk_free_rate: float = 0.0) -> float:
    """
    Calculate Sortino ratio (only penalizes downside volatility).
    """
    if not returns or len(returns) < 2:
        return 0.0
    
    returns_arr = np.array(returns) - risk_free_rate / 12
    mean_return = np.mean(returns_arr)
    
    # Downside deviation (only negative returns)
    downside_returns = returns_arr[returns_arr < 0]
    if len(downside_returns) == 0:
        return 0.0 if mean_return <= 0 else 99.0  # No downside
    
    downside_std = np.std(downside_returns, ddof=1)
    if downside_std == 0:
        return 0.0
    
    sortino = mean_return / downside_std
    if annualize:
        sortino *= np.sqrt(12)
    
    return round(sortino, 2)


def calculate_transaction_costs(old_holdings: dict, new_holdings: dict, portfolio_value: float) -> float:
    """
    Calculate transaction costs for rebalancing.
    
    Returns:
        Total cost in currency units
    """
    # Calculate turnover
    all_tickers = set(old_holdings.keys()) | set(new_holdings.keys())
    turnover = 0.0
    
    for ticker in all_tickers:
        old_weight = old_holdings.get(ticker, 0)
        new_weight = new_holdings.get(ticker, 0)
        turnover += abs(new_weight - old_weight)
    
    # Cost = turnover * portfolio_value * (transaction_cost + slippage)
    cost = turnover * portfolio_value * (TRANSACTION_COST_PCT + SLIPPAGE_PCT)
    return cost


def get_rebalance_dates(start_date: date, end_date: date, config: dict) -> list[date]:
    """Get rebalance dates based on strategy config."""
    frequency = config.get('rebalance_frequency', config.get('rebalance', {}).get('frequency', 'annual'))
    
    dates = []
    current = start_date
    
    if frequency == 'quarterly':
        months = config.get('rebalance_months', config.get('rebalance', {}).get('months', [3, 6, 9, 12]))
        while current <= end_date:
            if current.month in months:
                next_month = current.replace(day=28) + timedelta(days=4)
                last_day = next_month - timedelta(days=next_month.day)
                dates.append(last_day.date() if hasattr(last_day, 'date') else last_day)
            current += relativedelta(months=1)
    else:  # annually
        rebalance_config = config.get('rebalance', {})
        month = config.get('rebalance_month', rebalance_config.get('month', 3))
        while current <= end_date:
            if current.month == month:
                next_month = current.replace(day=28) + timedelta(days=4)
                last_day = next_month - timedelta(days=next_month.day)
                dates.append(last_day.date() if hasattr(last_day, 'date') else last_day)
            current += relativedelta(months=1)
    
    return [d for d in dates if start_date <= d <= end_date]


def get_historical_market_caps(db, as_of_date: date) -> dict:
    """Get historical market caps from FinBas for a specific date."""
    from sqlalchemy import text
    
    # Find closest date with market cap data (monthly, end of month)
    result = db.execute(text('''
        SELECT t.normalized_ticker as ticker, f.market_cap
        FROM ticker_all_isins t
        JOIN finbas_historical f ON f.isin = t.isin
        WHERE f.market_cap IS NOT NULL 
        AND f.date <= :as_of_date
        AND f.date >= date(:as_of_date, '-35 days')
        ORDER BY f.date DESC
    '''), {'as_of_date': as_of_date.isoformat()}).fetchall()
    
    # Return latest market cap per ticker
    mcaps = {}
    for row in result:
        if row[0] not in mcaps:
            mcaps[row[0]] = row[1]
    return mcaps


def preload_all_market_caps(db, start_date: date, end_date: date) -> pd.DataFrame:
    """Pre-load all market caps for date range with memory optimization."""
    from sqlalchemy import text
    
    logger.info("Loading market cap data with memory optimization...")
    
    # Use chunked reading to prevent memory overflow
    query = '''
        SELECT t.normalized_ticker as ticker, f.date, f.market_cap
        FROM ticker_all_isins t
        JOIN finbas_historical f ON f.isin = t.isin
        WHERE f.market_cap IS NOT NULL 
        AND f.date >= :start_date AND f.date <= :end_date
        ORDER BY f.date
    '''
    
    try:
        # Use chunked SQL reading
        df = MemoryOptimizer.chunked_sql_read(
            db.bind.url.database,  # SQLite database path
            query.replace(':start_date', f"'{start_date.isoformat()}'").replace(':end_date', f"'{end_date.isoformat()}'"),
            chunk_size=25000  # Smaller chunks for memory safety
        )
        
        if df.empty:
            logger.warning("No market cap data found for date range")
            return pd.DataFrame()
        
        logger.info(f"Loaded {len(df)} market cap records with memory optimization")
        return df
        
    except Exception as e:
        logger.error(f"Error loading market caps with optimization: {e}")
        # Fallback to original method with smaller result set
        result = db.execute(text(query), {
            'start_date': start_date.isoformat(), 
            'end_date': end_date.isoformat()
        }).fetchmany(50000)  # Limit to prevent memory overflow
        
        if not result:
            return pd.DataFrame()
        
        df = pd.DataFrame([{'ticker': r[0], 'date': r[1], 'market_cap': r[2]} for r in result])
        df = MemoryOptimizer.optimize_dtypes(df)
        
        # Force garbage collection
        del result
        gc.collect()
        
        return df


def get_market_caps_for_date(mcap_df: pd.DataFrame, as_of_date: date, financial_tickers: set) -> set:
    """Get valid tickers (top 40% by market cap) for a date from pre-loaded data."""
    if mcap_df.empty:
        return set()
    
    # Get data within 35 days before as_of_date
    mask = (mcap_df['date'] <= as_of_date) & (mcap_df['date'] >= as_of_date - timedelta(days=35))
    recent = mcap_df[mask]
    if recent.empty:
        return set()
    
    # Get latest market cap per ticker
    latest = recent.loc[recent.groupby('ticker')['date'].idxmax()]
    latest = latest[~latest['ticker'].isin(financial_tickers)]
    
    # Top 40% by market cap
    sorted_df = latest.sort_values('market_cap', ascending=False)
    top_40_pct = int(len(sorted_df) * 0.4)
    return set(sorted_df.head(top_40_pct)['ticker'])


def get_finbas_prices(db, start_date: date, end_date: date) -> pd.DataFrame:
    """Load historical prices from FinBas (includes delisted stocks)."""
    from sqlalchemy import text
    
    result = db.execute(text('''
        SELECT t.normalized_ticker as ticker, f.date, f.close
        FROM ticker_all_isins t
        JOIN finbas_historical f ON f.isin = t.isin
        WHERE f.date >= :start_date AND f.date <= :end_date
        AND f.close IS NOT NULL AND f.close > 0
        ORDER BY f.date
    '''), {'start_date': start_date.isoformat(), 'end_date': end_date.isoformat()}).fetchall()
    
    if not result:
        return pd.DataFrame()
    
    df = pd.DataFrame([{'ticker': r[0], 'date': r[1], 'close': r[2]} for r in result])
    df['date'] = pd.to_datetime(df['date']).dt.date  # Convert string to date
    return df


def get_financial_tickers(db) -> set:
    """Get set of financial sector tickers to exclude."""
    from sqlalchemy import text
    
    result = db.execute(text('''
        SELECT DISTINCT t.normalized_ticker
        FROM ticker_all_isins t
        JOIN stocks s ON s.ticker = t.normalized_ticker
        WHERE s.sector IN (
            'Traditionell Bankverksamhet', 'Investmentbolag', 'Försäkring',
            'Sparande & Investering', 'Kapitalförvaltning', 'Konsumentkredit'
        )
    ''')).fetchall()
    return {row[0] for row in result}


from services.memory_monitor import monitor_memory_usage

@monitor_memory_usage
def backtest_strategy(
    strategy_name: str,
    start_date: date,
    end_date: date,
    db,
    config: dict
) -> dict:
    """
    Run backtest for a strategy on historical data.
    
    Uses FinBas historical data for market cap filtering (no look-ahead bias).
    """
    from models import DailyPrice, Fundamentals, Stock
    from services.ranking import (
        calculate_momentum_score, calculate_value_score,
        calculate_dividend_score, calculate_quality_score,
        rank_and_select_top_n, filter_by_market_cap
    )
    
    logger.info(f"Starting backtest: {strategy_name} from {start_date} to {end_date}")
    
    # Check if we should use historical data (before June 2023)
    use_finbas = end_date <= date(2023, 6, 30)
    
    # Get financial tickers to exclude (applies to all periods)
    financial_tickers = get_financial_tickers(db)
    
    # Pre-load all market caps for the date range (avoids repeated queries)
    mcap_df = pd.DataFrame()
    if use_finbas:
        mcap_df = preload_all_market_caps(db, start_date - timedelta(days=35), end_date)
        logger.info(f"Pre-loaded {len(mcap_df)} market cap records")
    
    # 1. Load price data with memory optimization
    logger.info("Loading price data from database with memory optimization...")
    if use_finbas:
        prices_df = get_finbas_prices(db, start_date - timedelta(days=400), end_date)
        logger.info(f"Loaded {len(prices_df)} FinBas price records (includes delisted stocks)")
    else:
        # Use chunked loading for large price datasets
        prices = db.query(
            DailyPrice.ticker, DailyPrice.date, DailyPrice.close
        ).filter(
            DailyPrice.date >= start_date - timedelta(days=400),
            DailyPrice.date <= end_date
        ).all()
        
        # Build DataFrame in chunks to prevent memory spikes
        logger.info("Building price DataFrame with memory optimization...")
        prices_data = [{'ticker': p.ticker, 'date': p.date, 'close': p.close} for p in prices]
        prices_df = pd.DataFrame(prices_data)
        del prices_data, prices  # Free memory immediately
        
        # Apply memory optimization
        prices_df = MemoryOptimizer.optimize_dtypes(prices_df)
        logger.info(f"Loaded {len(prices_df)} Avanza price records")
    
    if prices_df.empty:
        return {"error": f"No price data available for {start_date} to {end_date}"}
    
    # Memory-optimized pivot table creation
    logger.info("Creating price pivot table with memory optimization...")
    
    # Filter to only needed date range first to reduce pivot size
    date_mask = (prices_df['date'] >= start_date - timedelta(days=30)) & (prices_df['date'] <= end_date)
    prices_subset = prices_df[date_mask].copy()
    
    # Create pivot in chunks if too large
    if len(prices_subset) > 500000:  # If more than 500k records
        logger.info("Large dataset detected - using chunked pivot creation")
        unique_dates = sorted(prices_subset['date'].unique())
        pivot_chunks = []
        
        chunk_size = 50  # 50 dates at a time
        for i in range(0, len(unique_dates), chunk_size):
            date_chunk = unique_dates[i:i + chunk_size]
            chunk_data = prices_subset[prices_subset['date'].isin(date_chunk)]
            chunk_pivot = chunk_data.pivot_table(index='date', columns='ticker', values='close', aggfunc='last')
            pivot_chunks.append(chunk_pivot)
            
            # Memory cleanup
            del chunk_data
            if i % (chunk_size * 5) == 0:  # Every 5 chunks
                gc.collect()
        
        price_pivot = pd.concat(pivot_chunks, axis=0).sort_index()
        del pivot_chunks
        gc.collect()
    else:
        price_pivot = prices_subset.pivot_table(index='date', columns='ticker', values='close', aggfunc='last').sort_index()
    
    # Clean up large DataFrames
    del prices_subset
    gc.collect()
    
    trading_dates = price_pivot.index
    trading_dates_in_range = trading_dates[(trading_dates >= start_date) & (trading_dates <= end_date)]
    
    if len(trading_dates_in_range) == 0:
        return {"error": "No trading dates in range"}
    
    # Cache current fundamentals with memory optimization
    fundamentals = db.query(Fundamentals).all()
    stocks = {s.ticker: s.market_cap_msek for s in db.query(Stock).all()}
    
    logger.info("Building fundamentals DataFrame with memory optimization...")
    fund_data = [{
        'ticker': f.ticker, 'pe': f.pe, 'pb': f.pb, 'ps': f.ps,
        'p_fcf': f.p_fcf, 'ev_ebitda': f.ev_ebitda, 'dividend_yield': f.dividend_yield,
        'roe': f.roe, 'roa': f.roa, 'roic': f.roic, 'fcfroe': f.fcfroe,
        'payout_ratio': f.payout_ratio, 'market_cap': stocks.get(f.ticker, 0)
    } for f in fundamentals] if fundamentals else []
    
    fund_df = pd.DataFrame(fund_data) if fund_data else pd.DataFrame()
    del fund_data, fundamentals, stocks  # Free memory
    
    if not fund_df.empty:
        fund_df = MemoryOptimizer.optimize_dtypes(fund_df)
    
    # For historical backtests, we'll filter by market cap at each rebalance date
    filtered_fund_df = filter_by_market_cap(fund_df, 40) if not fund_df.empty else fund_df
    
    # 2. Map rebalance dates to actual trading days
    rebalance_dates = get_rebalance_dates(start_date, end_date, config)
    if not rebalance_dates:
        return {"error": "No rebalance dates in the specified range"}
    
    def next_trading_day(d):
        idx = trading_dates.searchsorted(d)
        return trading_dates[min(idx, len(trading_dates) - 1)]
    
    actual_rebal_dates = sorted(set(next_trading_day(rb) for rb in rebalance_dates))
    
    # Handle initial period - rebalance on first trading day if before first scheduled rebalance
    first_trading = trading_dates_in_range[0]
    if first_trading < actual_rebal_dates[0]:
        actual_rebal_dates = [first_trading] + actual_rebal_dates
    
    logger.info(f"Actual rebalance dates: {[d.strftime('%Y-%m-%d') for d in actual_rebal_dates]}")
    
    # 3. Initialize
    strategy_type = config.get('type', config.get('category', ''))
    holdings = {}  # ticker -> shares
    portfolio_value = INITIAL_CAPITAL
    equity_curve = []
    monthly_values = {}
    total_transaction_costs = 0.0
    
    # 4. Iterate rebalance periods
    for i, rebal_date in enumerate(actual_rebal_dates):
        # Determine period end
        if i + 1 < len(actual_rebal_dates):
            next_rebal = actual_rebal_dates[i + 1]
            period_mask = (trading_dates_in_range >= rebal_date) & (trading_dates_in_range < next_rebal)
        else:
            period_mask = trading_dates_in_range >= rebal_date
        period_dates = trading_dates_in_range[period_mask]
        
        if len(period_dates) == 0:
            continue
        
        # Calculate rankings using sliced pivot (prices up to rebal_date)
        pivot_to_date = price_pivot.loc[:rebal_date]
        
        # Get valid tickers based on historical market cap (if using FinBas)
        if use_finbas and not mcap_df.empty:
            valid_tickers = get_market_caps_for_date(mcap_df, rebal_date, financial_tickers)
            logger.info(f"FinBas: top 40% = {len(valid_tickers)} stocks (excl financials) on {rebal_date}")
        else:
            valid_tickers = set(filtered_fund_df['ticker'].values) if not filtered_fund_df.empty else None
            if valid_tickers:
                valid_tickers = valid_tickers - financial_tickers
        
        if strategy_type == 'momentum':
            # Filter pivot to only include stocks meeting market cap threshold
            if valid_tickers:
                valid_cols = [c for c in pivot_to_date.columns if c in valid_tickers]
                pivot_filtered = pivot_to_date[valid_cols]
            else:
                pivot_filtered = pivot_to_date
            scores = calculate_momentum_score(None, price_pivot=pivot_filtered)
            ranked = rank_and_select_top_n(scores, config, n=10) if not scores.empty else pd.DataFrame()
        elif strategy_type == 'value':
            ranked = calculate_value_score(filtered_fund_df, None, pivot_to_date) if not filtered_fund_df.empty else pd.DataFrame()
        elif strategy_type == 'dividend':
            ranked = calculate_dividend_score(filtered_fund_df, None, pivot_to_date) if not filtered_fund_df.empty else pd.DataFrame()
        elif strategy_type == 'quality':
            ranked = calculate_quality_score(filtered_fund_df, None, pivot_to_date) if not filtered_fund_df.empty else pd.DataFrame()
        else:
            ranked = pd.DataFrame()
        
        # Update holdings
        if not ranked.empty and 'ticker' in ranked.columns:
            selected_tickers = ranked['ticker'].tolist()[:10]
            rebal_prices = pivot_to_date.iloc[-1]
            
            if selected_tickers:
                # Calculate old weights for transaction cost calculation
                old_weights = {}
                if holdings:
                    for ticker, shares in holdings.items():
                        price = rebal_prices.get(ticker, 0)
                        if price and portfolio_value > 0:
                            old_weights[ticker] = (shares * price) / portfolio_value
                
                # New weights (equal weight)
                new_weights = {t: 1.0 / len(selected_tickers) for t in selected_tickers}
                
                # Calculate and deduct transaction costs
                costs = calculate_transaction_costs(old_weights, new_weights, portfolio_value)
                if not np.isnan(costs):
                    portfolio_value -= costs
                    total_transaction_costs += costs
                
                # Allocate to new positions
                weight_per_stock = portfolio_value / len(selected_tickers)
                holdings = {}
                for ticker in selected_tickers:
                    price = rebal_prices.get(ticker, 0)
                    if price and price > 0:
                        holdings[ticker] = weight_per_stock / price
                
                logger.info(f"Rebalanced on {rebal_date}: {list(holdings.keys())} (costs: {costs:.2f})")
        
        if not holdings:
            continue
        
        # Vectorized portfolio values for period
        held_tickers = list(holdings.keys())
        period_prices = price_pivot.loc[period_dates, held_tickers].ffill()
        holdings_arr = np.array([holdings[t] for t in held_tickers])
        period_values = (period_prices.values * holdings_arr).sum(axis=1)
        
        # Record equity curve and monthly values
        for d, v in zip(period_dates, period_values):
            if v > 0:
                equity_curve.append((d, v))
                monthly_values[d.strftime('%Y-%m')] = v
                portfolio_value = v
    
    if len(equity_curve) < 2:
        return {"error": "Insufficient data to calculate returns"}
    
    # 5. Calculate metrics
    months = sorted(monthly_values.keys())
    monthly_returns = []
    for i in range(1, len(months)):
        prev_val = monthly_values[months[i-1]]
        curr_val = monthly_values[months[i]]
        if prev_val > 0:
            monthly_returns.append((curr_val - prev_val) / prev_val)
    
    final_value = equity_curve[-1][1]
    total_return_pct = ((final_value - INITIAL_CAPITAL) / INITIAL_CAPITAL) * 100
    equity_values = [e[1] for e in equity_curve]
    max_drawdown_pct = calculate_max_drawdown(equity_values)
    sharpe = calculate_sharpe_ratio(monthly_returns)
    
    logger.info(f"Backtest complete: Return={total_return_pct:.2f}%, Sharpe={sharpe}, MaxDD={max_drawdown_pct}%, Costs={total_transaction_costs:.2f}")
    
    # Determine if strategy has look-ahead bias
    has_look_ahead_bias = strategy_type in ['value', 'dividend', 'quality']
    
    result = {
        "strategy_name": strategy_name,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "total_return_pct": round(total_return_pct, 2),
        "sharpe": sharpe,
        "max_drawdown_pct": max_drawdown_pct,
        "equity_curve": [(d.isoformat(), round(v, 2)) for d, v in equity_curve[::5]],
        "monthly_returns": [round(r * 100, 2) for r in monthly_returns],
        "portfolio_values": [round(v, 2) for v in equity_values[::21]],
        "total_transaction_costs": round(total_transaction_costs, 2),
        "transaction_cost_pct": round((total_transaction_costs / INITIAL_CAPITAL) * 100, 2),
    }
    
    # Add look-ahead bias warning for strategies using current fundamentals
    if has_look_ahead_bias:
        result["warnings"] = [{
            "type": "look_ahead_bias",
            "message": f"This backtest uses current fundamental data (P/E, ROE, dividend yield, etc.) for historical periods. Results may be overly optimistic and not reflect actual historical performance.",
            "details": "Historical fundamental data requires Börsdata API integration. Only momentum-based strategies use purely historical price data."
        }]
    
    save_backtest_result(db, result)
    
    # Critical memory cleanup
    logger.info("Cleaning up memory after backtest...")
    del prices_df, price_pivot, fund_df, filtered_fund_df, mcap_df
    del equity_curve, equity_values, monthly_returns
    gc.collect()
    logger.info("Memory cleanup complete")
    
    return result


def save_backtest_result(db, result: dict):
    """Save backtest result to database."""
    from models import BacktestResult
    from datetime import datetime
    
    bt = BacktestResult(
        strategy_name=result['strategy_name'],
        start_date=datetime.fromisoformat(result['start_date']).date(),
        end_date=datetime.fromisoformat(result['end_date']).date(),
        total_return_pct=result['total_return_pct'],
        sharpe=result['sharpe'],
        max_drawdown_pct=result['max_drawdown_pct'],
        json_data=json.dumps(result)
    )
    db.add(bt)
    db.commit()
    logger.info(f"Saved backtest result: {result['strategy_name']}")
    return bt


def get_backtest_results(db, strategy_name: str = None) -> list[dict]:
    """
    Get backtest results from database.
    
    Args:
        db: Database session
        strategy_name: Optional filter by strategy name
    
    Returns:
        List of backtest results sorted by date DESC
    """
    from models import BacktestResult
    
    query = db.query(BacktestResult)
    if strategy_name:
        query = query.filter(BacktestResult.strategy_name == strategy_name)
    
    results = query.order_by(BacktestResult.end_date.desc()).all()
    
    return [
        {
            "id": r.id,
            "strategy_name": r.strategy_name,
            "start_date": r.start_date.isoformat(),
            "end_date": r.end_date.isoformat(),
            "total_return_pct": r.total_return_pct,
            "sharpe": r.sharpe,
            "max_drawdown_pct": r.max_drawdown_pct
        }
        for r in results
    ]
