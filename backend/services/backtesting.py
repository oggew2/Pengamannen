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
        month = rebalance.get('month', 3)
        while current <= end_date:
            if current.month == month:
                next_month = current.replace(day=28) + timedelta(days=4)
                last_day = next_month - timedelta(days=next_month.day)
                dates.append(last_day.date() if hasattr(last_day, 'date') else last_day)
            current += relativedelta(months=1)
    
    return [d for d in dates if start_date <= d <= end_date]


def backtest_strategy(
    strategy_name: str,
    start_date: date,
    end_date: date,
    db,
    config: dict
) -> dict:
    """
    Run backtest for a strategy on historical data.
    
    Args:
        strategy_name: Name of strategy from config
        start_date: Backtest start date
        end_date: Backtest end date
        db: Database session
        config: Strategy configuration from strategies.yaml
    
    Returns:
        Dict with backtest results including equity_curve, monthly_returns, metrics
    """
    from backend.models import DailyPrice, Fundamentals
    from backend.services.ranking import (
        calculate_momentum_score, calculate_value_score,
        calculate_dividend_score, calculate_quality_score,
        rank_and_select_top_n
    )
    
    logger.info(f"Starting backtest: {strategy_name} from {start_date} to {end_date}")
    
    # Get all prices in date range
    prices = db.query(DailyPrice).filter(
        DailyPrice.date >= start_date,
        DailyPrice.date <= end_date
    ).all()
    
    if not prices:
        return {"error": f"No price data available for {start_date} to {end_date}"}
    
    prices_df = pd.DataFrame([{
        'ticker': p.ticker, 'date': p.date, 'close': p.close
    } for p in prices])
    
    # Get fundamentals
    fundamentals = db.query(Fundamentals).all()
    fund_df = pd.DataFrame([{
        'ticker': f.ticker, 'pe': f.pe, 'pb': f.pb, 'ps': f.ps,
        'pfcf': f.pfcf, 'ev_ebitda': f.ev_ebitda, 'dividend_yield': f.dividend_yield,
        'roe': f.roe, 'roa': f.roa, 'roic': f.roic, 'fcfroe': f.fcfroe,
        'payout_ratio': f.payout_ratio
    } for f in fundamentals]) if fundamentals else pd.DataFrame()
    
    # Get rebalance dates
    rebalance_dates = get_rebalance_dates(start_date, end_date, config)
    if not rebalance_dates:
        return {"error": "No rebalance dates in the specified range"}
    
    logger.info(f"Rebalance dates: {rebalance_dates}")
    
    # Get unique trading dates
    trading_dates = sorted(prices_df['date'].unique())
    
    # Initialize portfolio
    portfolio_value = INITIAL_CAPITAL
    holdings = {}  # ticker -> shares
    equity_curve = [(start_date, INITIAL_CAPITAL)]
    monthly_values = {start_date.strftime('%Y-%m'): INITIAL_CAPITAL}
    
    strategy_type = config.get('type', '')
    
    for i, current_date in enumerate(trading_dates):
        if current_date < start_date:
            continue
        if current_date > end_date:
            break
        
        # Check if rebalance needed
        should_rebalance = any(
            rb <= current_date and (i == 0 or trading_dates[i-1] < rb)
            for rb in rebalance_dates
        )
        
        if should_rebalance or not holdings:
            # Calculate scores based on strategy type
            prices_to_date = prices_df[prices_df['date'] <= current_date]
            
            if strategy_type == 'momentum':
                scores = calculate_momentum_score(prices_to_date)
            elif strategy_type == 'value':
                scores = calculate_value_score(fund_df) if not fund_df.empty else pd.Series()
            elif strategy_type == 'dividend':
                scores = calculate_dividend_score(fund_df) if not fund_df.empty else pd.Series()
            elif strategy_type == 'quality':
                scores = calculate_quality_score(fund_df) if not fund_df.empty else pd.Series()
            else:
                scores = pd.Series()
            
            if not scores.empty:
                # Select top 10
                ranked = rank_and_select_top_n(scores, config, n=10)
                selected_tickers = ranked['ticker'].tolist()
                
                # Get current prices for selected stocks
                current_prices = prices_to_date.groupby('ticker')['close'].last()
                
                # Equal weight allocation
                if selected_tickers:
                    weight_per_stock = portfolio_value / len(selected_tickers)
                    holdings = {}
                    for ticker in selected_tickers:
                        if ticker in current_prices.index and current_prices[ticker] > 0:
                            holdings[ticker] = weight_per_stock / current_prices[ticker]
                    
                    logger.info(f"Rebalanced on {current_date}: {list(holdings.keys())}")
        
        # Calculate portfolio value
        current_prices = prices_df[prices_df['date'] == current_date].set_index('ticker')['close']
        portfolio_value = sum(
            shares * current_prices.get(ticker, 0)
            for ticker, shares in holdings.items()
        )
        
        if portfolio_value > 0:
            equity_curve.append((current_date, portfolio_value))
            month_key = current_date.strftime('%Y-%m')
            monthly_values[month_key] = portfolio_value
    
    if len(equity_curve) < 2:
        return {"error": "Insufficient data to calculate returns"}
    
    # Calculate monthly returns
    months = sorted(monthly_values.keys())
    monthly_returns = []
    for i in range(1, len(months)):
        prev_val = monthly_values[months[i-1]]
        curr_val = monthly_values[months[i]]
        if prev_val > 0:
            monthly_returns.append((curr_val - prev_val) / prev_val)
    
    # Calculate metrics
    final_value = equity_curve[-1][1]
    total_return_pct = ((final_value - INITIAL_CAPITAL) / INITIAL_CAPITAL) * 100
    equity_values = [e[1] for e in equity_curve]
    max_drawdown_pct = calculate_max_drawdown(equity_values)
    sharpe = calculate_sharpe_ratio(monthly_returns)
    
    logger.info(f"Backtest complete: Return={total_return_pct:.2f}%, Sharpe={sharpe}, MaxDD={max_drawdown_pct}%")
    
    result = {
        "strategy_name": strategy_name,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "total_return_pct": round(total_return_pct, 2),
        "sharpe": sharpe,
        "max_drawdown_pct": max_drawdown_pct,
        "equity_curve": [(d.isoformat(), round(v, 2)) for d, v in equity_curve[::5]],  # Sample every 5 days
        "monthly_returns": [round(r * 100, 2) for r in monthly_returns],
        "portfolio_values": [round(v, 2) for v in equity_values[::21]]  # Monthly samples
    }
    
    # Save to database
    save_backtest_result(db, result)
    
    return result


def save_backtest_result(db, result: dict):
    """Save backtest result to database."""
    from backend.models import BacktestResult
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
    from backend.models import BacktestResult
    
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
