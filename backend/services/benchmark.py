"""Benchmark comparison service - compare strategy performance vs OMXS30."""
import numpy as np
import pandas as pd
from typing import Dict, List, Optional
from datetime import date, timedelta


def calculate_returns(values: List[float]) -> np.ndarray:
    """Calculate period returns from value series."""
    values = np.array(values)
    return np.diff(values) / values[:-1]


def calculate_alpha_beta(
    strategy_returns: np.ndarray,
    benchmark_returns: np.ndarray,
    risk_free_rate: float = 0.02
) -> Dict:
    """
    Calculate alpha and beta vs benchmark.
    
    Alpha: Excess return not explained by market exposure
    Beta: Sensitivity to market movements
    """
    if len(strategy_returns) != len(benchmark_returns) or len(strategy_returns) < 2:
        return {"alpha": 0, "beta": 1, "r_squared": 0}
    
    # Annualize risk-free rate to match return frequency
    rf_period = risk_free_rate / 252  # Daily
    
    # Excess returns
    excess_strategy = strategy_returns - rf_period
    excess_benchmark = benchmark_returns - rf_period
    
    # Beta = Cov(strategy, benchmark) / Var(benchmark)
    cov = np.cov(excess_strategy, excess_benchmark)[0, 1]
    var_benchmark = np.var(excess_benchmark)
    beta = cov / var_benchmark if var_benchmark > 0 else 1
    
    # Alpha = mean(excess_strategy) - beta * mean(excess_benchmark)
    alpha_period = np.mean(excess_strategy) - beta * np.mean(excess_benchmark)
    alpha_annual = alpha_period * 252  # Annualize
    
    # R-squared
    predicted = beta * excess_benchmark
    ss_res = np.sum((excess_strategy - predicted) ** 2)
    ss_tot = np.sum((excess_strategy - np.mean(excess_strategy)) ** 2)
    r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
    
    return {
        "alpha": round(alpha_annual * 100, 2),  # As percentage
        "beta": round(beta, 3),
        "r_squared": round(r_squared, 3)
    }


def calculate_information_ratio(
    strategy_returns: np.ndarray,
    benchmark_returns: np.ndarray
) -> float:
    """
    Information Ratio = (Strategy Return - Benchmark Return) / Tracking Error
    Measures risk-adjusted excess return.
    """
    if len(strategy_returns) != len(benchmark_returns) or len(strategy_returns) < 2:
        return 0
    
    excess = strategy_returns - benchmark_returns
    tracking_error = np.std(excess) * np.sqrt(252)  # Annualized
    
    if tracking_error == 0:
        return 0
    
    excess_return = np.mean(excess) * 252  # Annualized
    return round(excess_return / tracking_error, 3)


def calculate_relative_performance(
    strategy_values: List[float],
    benchmark_values: List[float],
    dates: List[str] = None
) -> Dict:
    """
    Calculate comprehensive relative performance metrics.
    """
    if len(strategy_values) < 2 or len(benchmark_values) < 2:
        return {"error": "Insufficient data"}
    
    # Align lengths
    min_len = min(len(strategy_values), len(benchmark_values))
    strategy_values = strategy_values[:min_len]
    benchmark_values = benchmark_values[:min_len]
    
    strategy_returns = calculate_returns(strategy_values)
    benchmark_returns = calculate_returns(benchmark_values)
    
    # Total returns
    strategy_total = (strategy_values[-1] / strategy_values[0] - 1) * 100
    benchmark_total = (benchmark_values[-1] / benchmark_values[0] - 1) * 100
    
    # Alpha/Beta
    ab = calculate_alpha_beta(strategy_returns, benchmark_returns)
    
    # Information Ratio
    ir = calculate_information_ratio(strategy_returns, benchmark_returns)
    
    # Tracking Error
    excess = strategy_returns - benchmark_returns
    tracking_error = np.std(excess) * np.sqrt(252) * 100
    
    # Win rate (days strategy beat benchmark)
    win_days = np.sum(strategy_returns > benchmark_returns)
    win_rate = win_days / len(strategy_returns) * 100 if len(strategy_returns) > 0 else 0
    
    # Max relative drawdown
    relative_values = np.array(strategy_values) / np.array(benchmark_values)
    relative_peak = np.maximum.accumulate(relative_values)
    relative_drawdown = (relative_values - relative_peak) / relative_peak
    max_relative_dd = np.min(relative_drawdown) * 100
    
    return {
        "strategy_return_pct": round(strategy_total, 2),
        "benchmark_return_pct": round(benchmark_total, 2),
        "excess_return_pct": round(strategy_total - benchmark_total, 2),
        "alpha_pct": ab["alpha"],
        "beta": ab["beta"],
        "r_squared": ab["r_squared"],
        "information_ratio": ir,
        "tracking_error_pct": round(tracking_error, 2),
        "win_rate_pct": round(win_rate, 1),
        "max_relative_drawdown_pct": round(max_relative_dd, 2),
        "periods": min_len
    }


def generate_relative_chart_data(
    strategy_values: List[float],
    benchmark_values: List[float],
    dates: List[str] = None
) -> Dict:
    """Generate data for relative performance chart."""
    min_len = min(len(strategy_values), len(benchmark_values))
    
    # Normalize to 100
    strategy_norm = [v / strategy_values[0] * 100 for v in strategy_values[:min_len]]
    benchmark_norm = [v / benchmark_values[0] * 100 for v in benchmark_values[:min_len]]
    
    # Relative performance (strategy / benchmark)
    relative = [s / b * 100 for s, b in zip(strategy_norm, benchmark_norm)]
    
    return {
        "strategy": strategy_norm,
        "benchmark": benchmark_norm,
        "relative": relative,
        "dates": dates[:min_len] if dates else list(range(min_len))
    }


def calculate_rolling_metrics(
    strategy_values: List[float],
    benchmark_values: List[float],
    window: int = 252  # 1 year
) -> Dict:
    """Calculate rolling alpha, beta, and relative performance."""
    min_len = min(len(strategy_values), len(benchmark_values))
    if min_len < window:
        return {"error": f"Need at least {window} data points"}
    
    strategy_returns = calculate_returns(strategy_values[:min_len])
    benchmark_returns = calculate_returns(benchmark_values[:min_len])
    
    rolling_alpha = []
    rolling_beta = []
    rolling_excess = []
    
    for i in range(window, len(strategy_returns)):
        s_window = strategy_returns[i-window:i]
        b_window = benchmark_returns[i-window:i]
        
        ab = calculate_alpha_beta(s_window, b_window)
        rolling_alpha.append(ab["alpha"])
        rolling_beta.append(ab["beta"])
        
        # Rolling excess return
        s_ret = (1 + s_window).prod() - 1
        b_ret = (1 + b_window).prod() - 1
        rolling_excess.append((s_ret - b_ret) * 100)
    
    return {
        "rolling_alpha": rolling_alpha,
        "rolling_beta": rolling_beta,
        "rolling_excess_return": rolling_excess,
        "window_days": window
    }
