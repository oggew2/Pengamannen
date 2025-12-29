"""
Historical backtesting service for long-term strategy simulation.
Supports backtesting over 20+ years of data.
"""
import pandas as pd
import numpy as np
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

INITIAL_CAPITAL = 100000
TRANSACTION_COST_PCT = 0.001
SLIPPAGE_PCT = 0.0005


def generate_synthetic_history(
    tickers: list[str],
    start_date: date,
    end_date: date,
    seed: int = 42
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Generate synthetic historical data for backtesting when real data unavailable.
    
    Returns:
        Tuple of (prices_df, fundamentals_df)
    """
    np.random.seed(seed)
    
    trading_days = pd.date_range(start_date, end_date, freq='B')  # Business days
    
    prices_data = []
    fundamentals_data = []
    
    for ticker in tickers:
        # Generate price series with random walk + drift
        drift = np.random.uniform(0.05, 0.15) / 252  # 5-15% annual return
        volatility = np.random.uniform(0.15, 0.40) / np.sqrt(252)  # 15-40% annual vol
        
        price = 100.0
        for day in trading_days:
            returns = drift + volatility * np.random.randn()
            price *= (1 + returns)
            prices_data.append({
                'ticker': ticker,
                'date': day.date(),
                'close': round(price, 2),
                'volume': np.random.randint(100000, 10000000)
            })
        
        # Generate fundamentals (yearly snapshots)
        for year in range(start_date.year, end_date.year + 1):
            fundamentals_data.append({
                'ticker': ticker,
                'fiscal_date': date(year, 12, 31),
                'pe': np.random.uniform(5, 50),
                'pb': np.random.uniform(0.5, 10),
                'ps': np.random.uniform(0.3, 8),
                'ev_ebitda': np.random.uniform(3, 25),
                'roe': np.random.uniform(-0.1, 0.4),
                'roa': np.random.uniform(-0.05, 0.2),
                'roic': np.random.uniform(-0.05, 0.3),
                'fcfroe': np.random.uniform(-0.1, 0.3),
                'dividend_yield': np.random.uniform(0, 0.08),
                'payout_ratio': np.random.uniform(0, 1.5)
            })
    
    return pd.DataFrame(prices_data), pd.DataFrame(fundamentals_data)


def run_historical_backtest(
    strategy_name: str,
    strategy_config: dict,
    start_date: date,
    end_date: date,
    prices_df: pd.DataFrame,
    fundamentals_df: pd.DataFrame,
    benchmark_prices: Optional[pd.DataFrame] = None
) -> dict:
    """
    Run a full historical backtest over the specified period.
    
    Args:
        strategy_name: Name of strategy
        strategy_config: Strategy configuration from YAML
        start_date: Backtest start date
        end_date: Backtest end date
        prices_df: Historical prices DataFrame
        fundamentals_df: Historical fundamentals DataFrame
        benchmark_prices: Optional benchmark prices for comparison
    
    Returns:
        Comprehensive backtest results
    """
    from backend.services.ranking import (
        calculate_momentum_score, calculate_piotroski_f_score,
        calculate_value_score, calculate_dividend_score, calculate_quality_score
    )
    
    logger.info(f"Running historical backtest: {strategy_name} from {start_date} to {end_date}")
    
    strategy_type = strategy_config.get('category', strategy_config.get('type', ''))
    frequency = strategy_config.get('rebalance_frequency', 'annual')
    
    if frequency == 'quarterly':
        rebalance_months = strategy_config.get('rebalance_months', [3, 6, 9, 12])
    else:
        rebalance_months = [strategy_config.get('rebalance_month', 3)]
    
    # Get all trading dates
    all_dates = sorted(prices_df['date'].unique())
    trading_dates = [d for d in all_dates if start_date <= d <= end_date]
    
    if len(trading_dates) < 2:
        return {"error": "Insufficient trading dates in range"}
    
    # Initialize tracking
    portfolio_value = INITIAL_CAPITAL
    cash = INITIAL_CAPITAL
    holdings = {}  # ticker -> shares
    
    equity_curve = []
    monthly_returns = []
    yearly_returns = []
    trades = []
    
    last_month_value = INITIAL_CAPITAL
    last_year_value = INITIAL_CAPITAL
    last_year = start_date.year
    last_month = start_date.month
    
    rebalance_count = 0
    
    for i, current_date in enumerate(trading_dates):
        # Get current prices
        current_prices = prices_df[prices_df['date'] == current_date].set_index('ticker')['close'].to_dict()
        
        # Calculate portfolio value
        portfolio_value = cash + sum(
            shares * current_prices.get(ticker, 0)
            for ticker, shares in holdings.items()
        )
        
        # Check for rebalance
        should_rebalance = (
            current_date.month in rebalance_months and
            current_date.day <= 20 and
            (i == 0 or trading_dates[i-1].month != current_date.month)
        )
        
        if should_rebalance:
            # Get data up to current date for scoring
            prices_to_date = prices_df[prices_df['date'] <= current_date]
            
            # Get most recent fundamentals
            fund_to_date = fundamentals_df[fundamentals_df['fiscal_date'] <= current_date]
            if not fund_to_date.empty:
                latest_fund = fund_to_date.loc[fund_to_date.groupby('ticker')['fiscal_date'].idxmax()]
            else:
                latest_fund = pd.DataFrame()
            
            # Calculate scores based on strategy type
            if strategy_type == 'momentum':
                scores = calculate_momentum_score(prices_to_date)
                if not latest_fund.empty:
                    f_scores = calculate_piotroski_f_score(latest_fund)
                    valid_tickers = f_scores[f_scores >= 2].index
                    scores = scores[scores.index.isin(valid_tickers)]
            elif strategy_type == 'value':
                scores = calculate_value_score(latest_fund) if not latest_fund.empty else pd.Series()
            elif strategy_type == 'dividend':
                scores = calculate_dividend_score(latest_fund) if not latest_fund.empty else pd.Series()
            elif strategy_type == 'quality':
                scores = calculate_quality_score(latest_fund, prices_to_date) if not latest_fund.empty else pd.Series()
            else:
                scores = pd.Series()
            
            if not scores.empty:
                # Select top 10
                top_stocks = scores.sort_values(ascending=False).head(10).index.tolist()
                
                # Calculate transaction costs for turnover
                old_tickers = set(holdings.keys())
                new_tickers = set(top_stocks)
                turnover_tickers = old_tickers.symmetric_difference(new_tickers)
                transaction_cost = len(turnover_tickers) * portfolio_value * 0.1 * (TRANSACTION_COST_PCT + SLIPPAGE_PCT)
                
                # Sell all current holdings
                cash = portfolio_value - transaction_cost
                
                # Buy new holdings (equal weight)
                holdings = {}
                if top_stocks:
                    weight_per_stock = cash / len(top_stocks)
                    for ticker in top_stocks:
                        price = current_prices.get(ticker, 0)
                        if price > 0:
                            shares = weight_per_stock / price
                            holdings[ticker] = shares
                    cash = 0
                
                trades.append({
                    'date': current_date.isoformat(),
                    'stocks': top_stocks,
                    'portfolio_value': round(portfolio_value, 2),
                    'transaction_cost': round(transaction_cost, 2)
                })
                rebalance_count += 1
        
        # Record equity curve (daily)
        equity_curve.append({
            'date': current_date.isoformat(),
            'value': round(portfolio_value, 2)
        })
        
        # Calculate monthly returns
        if current_date.month != last_month:
            monthly_return = (portfolio_value - last_month_value) / last_month_value
            monthly_returns.append({
                'year': last_year,
                'month': last_month,
                'return': round(monthly_return * 100, 2)
            })
            last_month_value = portfolio_value
            last_month = current_date.month
        
        # Calculate yearly returns
        if current_date.year != last_year:
            yearly_return = (portfolio_value - last_year_value) / last_year_value
            yearly_returns.append({
                'year': last_year,
                'return': round(yearly_return * 100, 2)
            })
            last_year_value = portfolio_value
            last_year = current_date.year
    
    # Final year return
    if portfolio_value != last_year_value:
        yearly_return = (portfolio_value - last_year_value) / last_year_value
        yearly_returns.append({
            'year': last_year,
            'return': round(yearly_return * 100, 2)
        })
    
    # Calculate summary metrics
    equity_values = [e['value'] for e in equity_curve]
    monthly_ret_values = [m['return'] / 100 for m in monthly_returns]
    
    total_return = (portfolio_value - INITIAL_CAPITAL) / INITIAL_CAPITAL * 100
    years = (end_date - start_date).days / 365.25
    cagr = ((portfolio_value / INITIAL_CAPITAL) ** (1 / years) - 1) * 100 if years > 0 else 0
    
    # Max drawdown
    peak = equity_values[0]
    max_dd = 0
    for val in equity_values:
        if val > peak:
            peak = val
        dd = (val - peak) / peak
        if dd < max_dd:
            max_dd = dd
    
    # Sharpe & Sortino
    if len(monthly_ret_values) > 1:
        mean_ret = np.mean(monthly_ret_values)
        std_ret = np.std(monthly_ret_values, ddof=1)
        sharpe = (mean_ret / std_ret * np.sqrt(12)) if std_ret > 0 else 0
        
        downside = [r for r in monthly_ret_values if r < 0]
        downside_std = np.std(downside, ddof=1) if len(downside) > 1 else 0
        sortino = (mean_ret / downside_std * np.sqrt(12)) if downside_std > 0 else 0
    else:
        sharpe = sortino = 0
    
    # Win rate
    positive_years = sum(1 for y in yearly_returns if y['return'] > 0)
    win_rate = positive_years / len(yearly_returns) * 100 if yearly_returns else 0
    
    # Best/worst years
    if yearly_returns:
        best_year = max(yearly_returns, key=lambda x: x['return'])
        worst_year = min(yearly_returns, key=lambda x: x['return'])
    else:
        best_year = worst_year = {'year': 0, 'return': 0}
    
    result = {
        'strategy_name': strategy_name,
        'start_date': start_date.isoformat(),
        'end_date': end_date.isoformat(),
        'years': round(years, 1),
        
        # Performance
        'initial_capital': INITIAL_CAPITAL,
        'final_value': round(portfolio_value, 2),
        'total_return_pct': round(total_return, 2),
        'cagr_pct': round(cagr, 2),
        
        # Risk metrics
        'sharpe_ratio': round(sharpe, 2),
        'sortino_ratio': round(sortino, 2),
        'max_drawdown_pct': round(max_dd * 100, 2),
        
        # Statistics
        'win_rate_pct': round(win_rate, 1),
        'best_year': best_year,
        'worst_year': worst_year,
        'rebalance_count': rebalance_count,
        
        # Detailed data
        'yearly_returns': yearly_returns,
        'monthly_returns': monthly_returns[-24:],  # Last 2 years
        'equity_curve': equity_curve[::21],  # Monthly samples
        'trades': trades[-20:]  # Last 20 trades
    }
    
    logger.info(f"Backtest complete: CAGR={cagr:.1f}%, Sharpe={sharpe:.2f}, MaxDD={max_dd*100:.1f}%")
    
    return result


def run_all_strategies_backtest(
    start_date: date,
    end_date: date,
    strategies_config: dict,
    prices_df: pd.DataFrame,
    fundamentals_df: pd.DataFrame
) -> dict:
    """
    Run backtests for all strategies and compare.
    """
    results = {}
    
    for name, config in strategies_config.items():
        result = run_historical_backtest(
            name, config, start_date, end_date, prices_df, fundamentals_df
        )
        results[name] = result
    
    # Summary comparison
    summary = []
    for name, result in results.items():
        if 'error' not in result:
            summary.append({
                'strategy': name,
                'cagr': result['cagr_pct'],
                'sharpe': result['sharpe_ratio'],
                'max_dd': result['max_drawdown_pct'],
                'win_rate': result['win_rate_pct']
            })
    
    return {
        'period': f"{start_date} to {end_date}",
        'summary': sorted(summary, key=lambda x: x['cagr'], reverse=True),
        'details': results
    }
